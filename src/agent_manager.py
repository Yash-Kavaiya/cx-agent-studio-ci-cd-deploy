"""Agent management operations for CX Agent Studio.

Handles export, import, validation, and deployment of CES agent applications
via the ces.googleapis.com API. Supports both direct API calls and
the export/import workflow recommended for CI/CD pipelines.
"""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console

from src.auth import CES_API_ENDPOINT, get_auth_headers
from src.config import PipelineConfig, transform_environment_json

console = Console()

API_VERSION = "v1"


def _build_url(project_id: str, path: str) -> str:
    """Build a CES API URL."""
    return f"{CES_API_ENDPOINT}/{API_VERSION}/projects/{project_id}/{path}"


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


def export_agent(
    project_id: str,
    app_id: str,
    output_dir: str | Path,
    region: str = "us-central1",
) -> Path:
    """Export an agent application from CX Agent Studio.

    Downloads the agent configuration as a zip archive containing
    all agent resources including the environment.json file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    url = _build_url(
        project_id,
        f"locations/{region}/agentApps/{app_id}:export",
    )

    console.print(f"[bold blue]Exporting agent[/] {app_id} from project {project_id}...")

    response = _api_request("POST", url)
    result = response.json()

    if "agentContent" in result:
        zip_path = output_dir / f"{app_id}.zip"
        import base64

        content = base64.b64decode(result["agentContent"])
        zip_path.write_bytes(content)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(output_dir)

        zip_path.unlink()
        console.print(f"[bold green]Agent exported to[/] {output_dir}")
    elif "agentUri" in result:
        console.print(f"[bold green]Agent exported to GCS:[/] {result['agentUri']}")
    else:
        export_manifest = output_dir / "export_manifest.json"
        with export_manifest.open("w") as f:
            json.dump(result, f, indent=2)
        console.print(f"[bold green]Export manifest saved to[/] {export_manifest}")

    return output_dir


def import_agent(
    project_id: str,
    app_id: str,
    agent_dir: str | Path,
    region: str = "us-central1",
) -> dict[str, Any]:
    """Import an agent application to CX Agent Studio.

    Packages the agent directory into a zip and uploads it
    to the target project/app via the CES API.
    """
    agent_dir = Path(agent_dir)

    if not agent_dir.exists():
        msg = f"Agent directory not found: {agent_dir}"
        raise FileNotFoundError(msg)

    console.print(f"[bold blue]Importing agent[/] to {app_id} in project {project_id}...")

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in agent_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(agent_dir)
                    zf.write(file_path, arcname)

        import base64

        agent_content = base64.b64encode(tmp_path.read_bytes()).decode()

        url = _build_url(
            project_id,
            f"locations/{region}/agentApps/{app_id}:import",
        )

        response = _api_request("POST", url, json_body={"agentContent": agent_content})
        result = response.json()

        console.print(f"[bold green]Agent imported successfully[/] to {app_id}")
        return result

    finally:
        tmp_path.unlink(missing_ok=True)


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

    json_files = list(agent_dir.rglob("*.json"))
    for jf in json_files:
        try:
            with jf.open() as f:
                json.load(f)
        except json.JSONDecodeError as e:
            issues.append(f"Invalid JSON in {jf.relative_to(agent_dir)}: {e}")

    if strict and not json_files:
        issues.append("No JSON configuration files found in agent directory")

    return issues


def transform_agent_config(
    agent_dir: str | Path,
    config: PipelineConfig,
) -> Path:
    """Transform an agent's configuration for a target environment.

    Updates environment.json with environment-specific overrides
    from the pipeline configuration.
    """
    agent_dir = Path(agent_dir)
    env_json = agent_dir / "environment.json"

    if env_json.exists():
        transform_environment_json(env_json, config.overrides)
        console.print(f"[bold green]Transformed config for[/] {config.deployment.environment}")
    else:
        console.print("[yellow]No environment.json found - creating from overrides[/]")
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


def backup_to_gcs(
    agent_dir: str | Path,
    bucket_name: str,
    prefix: str,
    project_id: str,
) -> str:
    """Backup an exported agent to Google Cloud Storage."""
    from google.cloud import storage

    agent_dir = Path(agent_dir)
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)

    import datetime

    timestamp = datetime.datetime.now(tz=datetime.UTC).strftime("%Y%m%d-%H%M%S")

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in agent_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(agent_dir)
                    zf.write(file_path, arcname)

        blob_name = f"{prefix}/backup-{timestamp}.zip"
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(tmp_path))

        gcs_uri = f"gs://{bucket_name}/{blob_name}"
        console.print(f"[bold green]Backup uploaded to[/] {gcs_uri}")
        return gcs_uri

    finally:
        tmp_path.unlink(missing_ok=True)


def list_agent_versions(
    project_id: str,
    app_id: str,
    region: str = "us-central1",
) -> list[dict[str, Any]]:
    """List available versions of an agent application."""
    url = _build_url(
        project_id,
        f"locations/{region}/agentApps/{app_id}/versions",
    )
    response = _api_request("GET", url)
    result = response.json()
    return result.get("versions", [])


def restore_agent_version(
    project_id: str,
    app_id: str,
    version_id: str,
    region: str = "us-central1",
) -> dict[str, Any]:
    """Restore a specific version of an agent application."""
    url = _build_url(
        project_id,
        f"locations/{region}/agentApps/{app_id}:restoreVersion",
    )
    response = _api_request("POST", url, json_body={"versionId": version_id})
    result = response.json()
    console.print(f"[bold green]Restored version[/] {version_id}")
    return result
