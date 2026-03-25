"""Agent management operations for CX Agent Studio.

Handles export, import, validation, and deployment of CES agent applications
via the ces.googleapis.com API (v1beta). Supports both direct API calls and
the export/import workflow recommended for CI/CD pipelines.

API reference: https://docs.cloud.google.com/customer-engagement-ai/conversational-agents/ps/reference/rest/v1beta-overview
"""

from __future__ import annotations

import json
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, cast

import httpx
from rich.console import Console

from src.auth import CES_API_ENDPOINT, get_auth_headers
from src.config import PipelineConfig, transform_environment_json

console = Console()

# CES API is currently on v1beta (v1 lacks evaluations, scheduled runs, etc.)
API_VERSION = "v1beta"

# CES uses multi-region locations ("us" or "eu"), NOT zone-based regions
DEFAULT_REGION = "us"

# Long-running operation polling
POLL_INTERVAL_SECONDS = 5
POLL_MAX_WAIT_SECONDS = 300


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def _app_url(project_id: str, region: str, app_id: str, suffix: str = "") -> str:
    """Build a CES API URL for an app resource."""
    base = (
        f"{CES_API_ENDPOINT}/{API_VERSION}"
        f"/projects/{project_id}/locations/{region}/apps/{app_id}"
    )
    return f"{base}{suffix}" if suffix else base


def _location_url(project_id: str, region: str, suffix: str = "") -> str:
    """Build a CES API URL for a location (parent) resource."""
    base = f"{CES_API_ENDPOINT}/{API_VERSION}/projects/{project_id}/locations/{region}"
    return f"{base}{suffix}" if suffix else base


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


def _api_request(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: int = 120,
) -> httpx.Response:
    """Make an authenticated API request to the CES API."""
    auth_headers = headers or get_auth_headers()
    auth_headers["Content-Type"] = "application/json"

    with httpx.Client(timeout=timeout) as client:
        response = client.request(
            method=method,
            url=url,
            headers=auth_headers,
            json=json_body,
        )
        response.raise_for_status()
        return response


# ---------------------------------------------------------------------------
# Long-Running Operation (LRO) polling
# Both exportApp and importApp return Operations, not immediate results.
# ---------------------------------------------------------------------------


def _poll_operation(
    operation_name: str,
    project_id: str,
    region: str,
    max_wait: int = POLL_MAX_WAIT_SECONDS,
    interval: int = POLL_INTERVAL_SECONDS,
) -> dict[str, Any]:
    """Poll a long-running operation until it completes.

    Returns the completed operation dict (with response or error).
    Raises RuntimeError on timeout or operation failure.

    API: GET /v1beta/{name=projects/*/locations/*/operations/*}
    """
    op_url = f"{CES_API_ENDPOINT}/{API_VERSION}/{operation_name}"
    deadline = time.monotonic() + max_wait

    console.print(f"[dim]Waiting for operation {operation_name}...[/]")

    while time.monotonic() < deadline:
        resp = _api_request("GET", op_url)
        op: dict[str, Any] = resp.json()

        if op.get("done"):
            if "error" in op:
                err = op["error"]
                msg = f"Operation failed: {err.get('message', err)}"
                raise RuntimeError(msg)
            console.print("[dim]Operation completed.[/]")
            return op

        time.sleep(interval)

    msg = f"Operation timed out after {max_wait}s: {operation_name}"
    raise TimeoutError(msg)


# ---------------------------------------------------------------------------
# App read operations
# ---------------------------------------------------------------------------


def get_agent(
    project_id: str,
    app_id: str,
    region: str = DEFAULT_REGION,
) -> dict[str, Any]:
    """Get details of a CX Agent Studio app.

    API: GET /v1beta/projects/{project}/locations/{region}/apps/{app}
    Returns the full App resource including name, displayName, state, config.
    """
    url = _app_url(project_id, region, app_id)
    console.print(f"[bold blue]Fetching app[/] {app_id} ({region})...")

    resp = _api_request("GET", url)
    result: dict[str, Any] = resp.json()

    console.print(f"[bold green]App found:[/] {result.get('displayName', app_id)}")
    console.print(f"  Name:  {result.get('name', '')}")
    console.print(f"  State: {result.get('state', 'UNKNOWN')}")
    return result


def list_apps(
    project_id: str,
    region: str = DEFAULT_REGION,
) -> list[dict[str, Any]]:
    """List all CX Agent Studio apps in a project/location.

    API: GET /v1beta/projects/{project}/locations/{region}/apps
    """
    url = _location_url(project_id, region, "/apps")
    console.print(f"[bold blue]Listing apps[/] in {project_id} ({region})...")

    resp = _api_request("GET", url)
    result: dict[str, Any] = resp.json()
    apps = cast(list[dict[str, Any]], result.get("apps", []))

    console.print(f"[bold green]Found {len(apps)} app(s)[/]")
    return apps


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------


def export_agent(
    project_id: str,
    app_id: str,
    output_dir: str | Path,
    region: str = DEFAULT_REGION,
    gcs_uri: str | None = None,
    app_version: str | None = None,
) -> Path:
    """Export an agent application from CX Agent Studio.

    exportApp is a Long-Running Operation. This function:
    1. POSTs the export request (returns an Operation)
    2. Polls the operation until done
    3. Downloads/extracts the agent zip to output_dir

    API: POST /v1beta/projects/{project}/locations/{region}/apps/{app}:exportApp
    Request body: { exportFormat: "JSON", gcsUri?: ..., appVersion?: ... }
    Response: Operation (poll to get result)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    url = _app_url(project_id, region, app_id, ":exportApp")

    body: dict[str, Any] = {
        # exportFormat is required — use JSON for portability
        "exportFormat": "JSON",
    }
    if gcs_uri:
        body["gcsUri"] = gcs_uri
    if app_version:
        body["appVersion"] = app_version

    console.print(f"[bold blue]Exporting app[/] {app_id} from {project_id} ({region})...")

    resp = _api_request("POST", url, json_body=body)
    operation: dict[str, Any] = resp.json()

    # exportApp is an LRO — poll until done
    op_name = operation.get("name", "")
    if op_name:
        operation = _poll_operation(op_name, project_id, region)

    # Extract result from completed operation
    op_response = operation.get("response", operation)

    if "appContent" in op_response:
        import base64

        zip_path = output_dir / f"{app_id}.zip"
        content = base64.b64decode(op_response["appContent"])
        zip_path.write_bytes(content)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(output_dir)

        zip_path.unlink()
        console.print(f"[bold green]App exported to[/] {output_dir}")

    elif "appUri" in op_response or "gcsUri" in op_response:
        uri = op_response.get("appUri") or op_response.get("gcsUri")
        console.print(f"[bold green]App exported to GCS:[/] {uri}")

    else:
        # Save the raw operation response for inspection
        manifest = output_dir / "export_operation.json"
        manifest.write_text(json.dumps(operation, indent=2))
        console.print(f"[yellow]Unexpected response — saved to[/] {manifest}")
        console.print("[dim]Check export_operation.json for details[/]")

    return output_dir


def import_agent(
    project_id: str,
    app_id: str,
    agent_dir: str | Path,
    region: str = DEFAULT_REGION,
    conflict_resolution: str = "REPLACE",
) -> dict[str, Any]:
    """Import an agent application to CX Agent Studio.

    importApp is a Long-Running Operation. This function:
    1. Zips the agent dir and base64-encodes it
    2. POSTs the import request (returns an Operation)
    3. Polls the operation until done

    API: POST /v1beta/projects/{project}/locations/{region}/apps:importApp
    Note: importApp posts to the parent location, not the app resource.
    Request body: { appId, appContent (base64 zip), importOptions }
    Response: Operation (poll to completion)
    """
    agent_dir = Path(agent_dir)
    if not agent_dir.exists():
        msg = f"Agent directory not found: {agent_dir}"
        raise FileNotFoundError(msg)

    console.print(f"[bold blue]Importing app[/] to {app_id} in {project_id} ({region})...")

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in agent_dir.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, file_path.relative_to(agent_dir))

        import base64

        # Field is "appContent" (not "agentContent") per v1beta spec
        app_content = base64.b64encode(tmp_path.read_bytes()).decode()

        url = _location_url(project_id, region, "/apps:importApp")

        body: dict[str, Any] = {
            "appId": app_id,
            "appContent": app_content,
            "importOptions": {
                "conflictResolutionStrategy": conflict_resolution,
            },
        }

        resp = _api_request("POST", url, json_body=body)
        operation: dict[str, Any] = resp.json()

        # importApp is an LRO — poll until done
        op_name = operation.get("name", "")
        if op_name:
            operation = _poll_operation(op_name, project_id, region)

        console.print(f"[bold green]App imported successfully[/] to {app_id}")
        return operation

    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Validate / Transform
# ---------------------------------------------------------------------------


def validate_agent(agent_dir: str | Path, strict: bool = False) -> list[str]:
    """Validate an exported agent's configuration.

    Checks for required files, valid JSON, and configuration consistency.
    Returns a list of issues found (empty list means valid).
    """
    agent_dir = Path(agent_dir)
    issues: list[str] = []

    if not agent_dir.exists():
        issues.append(f"Agent directory does not exist: {agent_dir}")
        return issues

    env_json = agent_dir / "environment.json"
    if env_json.exists():
        try:
            with env_json.open() as f:
                env_data = json.load(f)
            if not isinstance(env_data, dict):
                issues.append("environment.json root must be a JSON object")
        except json.JSONDecodeError as e:
            issues.append(f"Invalid JSON in environment.json: {e}")
    elif strict:
        issues.append("environment.json not found (required in strict mode)")

    for jf in agent_dir.rglob("*.json"):
        try:
            with jf.open() as f:
                json.load(f)
        except json.JSONDecodeError as e:
            issues.append(f"Invalid JSON in {jf.relative_to(agent_dir)}: {e}")

    if strict and not list(agent_dir.rglob("*.json")):
        issues.append("No JSON configuration files found in agent directory")

    return issues


def transform_agent_config(
    agent_dir: str | Path,
    config: PipelineConfig,
) -> Path:
    """Transform an agent's configuration for a target environment.

    Updates environment.json with environment-specific overrides.
    """
    agent_dir = Path(agent_dir)
    env_json = agent_dir / "environment.json"

    if env_json.exists():
        transform_environment_json(env_json, config.overrides)
        console.print(f"[bold green]Transformed config for[/] {config.deployment.environment}")
    else:
        console.print("[yellow]No environment.json found — creating from overrides[/]")
        data: dict[str, Any] = {}
        if config.overrides.data_store_uris:
            data["dataStoreUris"] = config.overrides.data_store_uris
        if config.overrides.service_endpoints:
            data["serviceEndpoints"] = config.overrides.service_endpoints
        if config.overrides.storage_buckets:
            data["storageBuckets"] = config.overrides.storage_buckets
        if config.overrides.custom_settings:
            data["customSettings"] = config.overrides.custom_settings

        with env_json.open("w") as f:
            json.dump(data, f, indent=2)

    return agent_dir


# ---------------------------------------------------------------------------
# GCS Backup
# ---------------------------------------------------------------------------


def backup_to_gcs(
    agent_dir: str | Path,
    bucket_name: str,
    prefix: str,
    project_id: str,
) -> str:
    """Backup an exported agent to Google Cloud Storage."""
    import datetime

    from google.cloud import storage  # type: ignore[import-untyped]

    agent_dir = Path(agent_dir)
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    timestamp = datetime.datetime.now(tz=datetime.UTC).strftime("%Y%m%d-%H%M%S")

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in agent_dir.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, file_path.relative_to(agent_dir))

        blob_name = f"{prefix}/backup-{timestamp}.zip"
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(tmp_path))

        gcs_uri = f"gs://{bucket_name}/{blob_name}"
        console.print(f"[bold green]Backup uploaded to[/] {gcs_uri}")
        return gcs_uri

    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


def list_agent_versions(
    project_id: str,
    app_id: str,
    region: str = DEFAULT_REGION,
) -> list[dict[str, Any]]:
    """List available versions of a CX Agent Studio app.

    API: GET /v1beta/projects/{project}/locations/{region}/apps/{app}/versions
    """
    url = _app_url(project_id, region, app_id, "/versions")
    console.print(f"[bold blue]Listing versions[/] for app {app_id}...")

    resp = _api_request("GET", url)
    result: dict[str, Any] = resp.json()
    versions = cast(list[dict[str, Any]], result.get("appVersions", []))

    console.print(f"[bold green]Found {len(versions)} version(s)[/]")
    return versions


def create_agent_version(
    project_id: str,
    app_id: str,
    display_name: str,
    description: str = "",
    region: str = DEFAULT_REGION,
) -> dict[str, Any]:
    """Create (snapshot) a new immutable version of a CX Agent Studio app.

    API: POST /v1beta/projects/{project}/locations/{region}/apps/{app}/versions
    Request body: AppVersion resource { displayName, description }
    Response: AppVersion (synchronous, not an LRO)
    """
    url = _app_url(project_id, region, app_id, "/versions")

    body: dict[str, Any] = {"displayName": display_name}
    if description:
        body["description"] = description

    resp = _api_request("POST", url, json_body=body)
    result: dict[str, Any] = resp.json()
    console.print(f"[bold green]Created version:[/] {display_name}")
    return result


def restore_agent_version(
    project_id: str,
    app_id: str,
    version_id: str,
    region: str = DEFAULT_REGION,
) -> dict[str, Any]:
    """Restore a specific version of a CX Agent Studio app.

    Creates a new auto-version from the current draft, then overwrites
    the draft with the specified version.

    API: POST /v1beta/projects/{project}/locations/{region}/apps/{app}/versions/{version}:restore
    Request body: empty (required per spec)
    Response: Operation (LRO)
    """
    url = _app_url(project_id, region, app_id, f"/versions/{version_id}:restore")

    resp = _api_request("POST", url, json_body={})
    operation: dict[str, Any] = resp.json()

    op_name = operation.get("name", "")
    if op_name:
        operation = _poll_operation(op_name, project_id, region)

    console.print(f"[bold green]Restored version[/] {version_id}")
    return operation
