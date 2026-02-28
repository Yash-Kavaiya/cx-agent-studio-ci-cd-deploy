"""Configuration management for CX Agent Studio CI/CD pipeline.

Handles loading and validating environment-specific configurations
for deploying agents across dev, staging, and production environments.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class GCPConfig(BaseModel):
    """Google Cloud Platform configuration."""

    project_id: str = Field(..., description="GCP Project ID")
    region: str = Field(default="us-central1", description="GCP region")
    multi_region: str = Field(default="us", description="Multi-region (us or eu)")


class CESConfig(BaseModel):
    """CX Agent Studio (CES) specific configuration."""

    app_id: str = Field(..., description="CES Agent Application ID")
    agent_id: str = Field(default="", description="CES Agent ID")
    api_endpoint: str = Field(
        default="ces.googleapis.com", description="CES API endpoint"
    )
    oauth_scope: str = Field(
        default="https://www.googleapis.com/auth/ces",
        description="OAuth scope for CES API",
    )


class StorageConfig(BaseModel):
    """Cloud Storage configuration for agent exports/backups."""

    bucket_name: str = Field(..., description="GCS bucket name")
    export_prefix: str = Field(default="agent-exports", description="Export path prefix")
    backup_prefix: str = Field(default="agent-backups", description="Backup path prefix")


class DeploymentConfig(BaseModel):
    """Deployment-specific configuration."""

    environment: str = Field(..., description="Target environment name")
    auto_rollback: bool = Field(default=True, description="Enable auto-rollback on failure")
    smoke_test_timeout: int = Field(default=120, description="Smoke test timeout in seconds")
    max_retries: int = Field(default=3, description="Max retries for API calls")


class EnvironmentOverrides(BaseModel):
    """Environment-specific overrides for agent environment.json."""

    data_store_uris: dict[str, str] = Field(default_factory=dict)
    service_endpoints: dict[str, str] = Field(default_factory=dict)
    storage_buckets: dict[str, str] = Field(default_factory=dict)
    custom_settings: dict[str, Any] = Field(default_factory=dict)


class PipelineConfig(BaseModel):
    """Complete pipeline configuration for an environment."""

    gcp: GCPConfig
    ces: CESConfig
    storage: StorageConfig
    deployment: DeploymentConfig
    overrides: EnvironmentOverrides = Field(default_factory=EnvironmentOverrides)


def load_config(config_path: str | Path) -> PipelineConfig:
    """Load pipeline configuration from a YAML file."""
    path = Path(config_path)
    if not path.exists():
        msg = f"Configuration file not found: {path}"
        raise FileNotFoundError(msg)

    with path.open() as f:
        raw = yaml.safe_load(f)

    return PipelineConfig(**raw)


def load_all_configs(configs_dir: str | Path) -> dict[str, PipelineConfig]:
    """Load all environment configurations from a directory."""
    configs_dir = Path(configs_dir)
    configs: dict[str, PipelineConfig] = {}

    for config_file in sorted(configs_dir.glob("*.yaml")):
        env_name = config_file.stem
        configs[env_name] = load_config(config_file)

    return configs


def validate_environment_json(env_json_path: str | Path) -> list[str]:
    """Validate an agent's environment.json file. Returns list of issues found."""
    path = Path(env_json_path)
    issues: list[str] = []

    if not path.exists():
        issues.append(f"environment.json not found at {path}")
        return issues

    try:
        with path.open() as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        issues.append(f"Invalid JSON in environment.json: {e}")
        return issues

    if not isinstance(data, dict):
        issues.append("environment.json root must be a JSON object")

    return issues


def transform_environment_json(
    env_json_path: str | Path,
    overrides: EnvironmentOverrides,
    output_path: str | Path | None = None,
) -> Path:
    """Transform an agent's environment.json with environment-specific overrides."""
    path = Path(env_json_path)
    with path.open() as f:
        data = json.load(f)

    if overrides.data_store_uris:
        data.setdefault("dataStoreUris", {}).update(overrides.data_store_uris)

    if overrides.service_endpoints:
        data.setdefault("serviceEndpoints", {}).update(overrides.service_endpoints)

    if overrides.storage_buckets:
        data.setdefault("storageBuckets", {}).update(overrides.storage_buckets)

    if overrides.custom_settings:
        data.setdefault("customSettings", {}).update(overrides.custom_settings)

    out = Path(output_path) if output_path else path
    with out.open("w") as f:
        json.dump(data, f, indent=2)

    return out
