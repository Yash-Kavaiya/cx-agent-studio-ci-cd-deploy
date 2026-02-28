"""Authentication helpers for CX Agent Studio API (ces.googleapis.com).

Supports Application Default Credentials (ADC), service account keys,
and Workload Identity Federation for CI/CD environments.

Google Cloud SDK imports are deferred to function call time so that
modules can be imported without the SDK installed (e.g., during testing).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.auth import credentials as ga_credentials

CES_SCOPES = ["https://www.googleapis.com/auth/ces"]
CES_API_ENDPOINT = "https://ces.googleapis.com"


def get_credentials(
    scopes: list[str] | None = None,
    service_account_file: str | None = None,
) -> ga_credentials.Credentials:
    """Obtain Google Cloud credentials for CES API access.

    Priority:
    1. Explicit service account key file
    2. GOOGLE_APPLICATION_CREDENTIALS env var
    3. Application Default Credentials (ADC) / Workload Identity
    """
    import google.auth
    from google.oauth2 import service_account

    target_scopes = scopes or CES_SCOPES

    if service_account_file:
        return service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=target_scopes,
        )

    env_key_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if env_key_file and os.path.exists(env_key_file):
        return service_account.Credentials.from_service_account_file(
            env_key_file,
            scopes=target_scopes,
        )

    creds, project = google.auth.default(scopes=target_scopes)
    return creds


def get_auth_headers(credentials: ga_credentials.Credentials | None = None) -> dict[str, str]:
    """Get authorization headers for HTTP requests to CES API."""
    import google.auth.transport.requests

    creds = credentials or get_credentials()

    request = google.auth.transport.requests.Request()
    creds.refresh(request)

    return {"Authorization": f"Bearer {creds.token}"}


def get_project_id() -> str:
    """Detect the current GCP project ID from credentials or environment."""
    project_id = os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if project_id:
        return project_id

    import google.auth

    _, project = google.auth.default()
    if project:
        return project

    msg = "Could not determine GCP project ID. Set GCP_PROJECT_ID environment variable."
    raise RuntimeError(msg)


def validate_auth(project_id: str | None = None) -> dict[str, Any]:
    """Validate authentication is working and return credential info."""
    import google.auth.transport.requests

    creds = get_credentials()
    request = google.auth.transport.requests.Request()
    creds.refresh(request)

    detected_project = project_id or get_project_id()

    return {
        "authenticated": True,
        "project_id": detected_project,
        "credential_type": type(creds).__name__,
        "scopes": getattr(creds, "scopes", CES_SCOPES),
    }
