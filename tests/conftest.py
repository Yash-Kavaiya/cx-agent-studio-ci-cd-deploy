"""Shared test fixtures for CX Agent Studio CI/CD pipeline tests."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_env_config(tmp_dir: Path) -> Path:
    """Create a sample environment config YAML file."""
    config = {
        "gcp": {
            "project_id": "test-project-123",
            "region": "us-central1",
            "multi_region": "us",
        },
        "ces": {
            "app_id": "test-app-456",
            "agent_id": "",
            "api_endpoint": "ces.googleapis.com",
            "oauth_scope": "https://www.googleapis.com/auth/ces",
        },
        "storage": {
            "bucket_name": "test-project-123-agent-exports",
            "export_prefix": "agent-exports/test",
            "backup_prefix": "agent-backups/test",
        },
        "deployment": {
            "environment": "test",
            "auto_rollback": True,
            "smoke_test_timeout": 60,
            "max_retries": 3,
        },
        "overrides": {
            "data_store_uris": {"main": "gs://test-bucket/data"},
            "service_endpoints": {"backend": "https://api.test.example.com"},
            "storage_buckets": {"uploads": "test-uploads-bucket"},
            "custom_settings": {"log_level": "DEBUG"},
        },
    }

    config_path = tmp_dir / "test.yaml"
    with config_path.open("w") as f:
        yaml.dump(config, f)

    return config_path


@pytest.fixture
def sample_environment_json(tmp_dir: Path) -> Path:
    """Create a sample agent environment.json file."""
    env_data = {
        "dataStoreUris": {"default": "gs://original-bucket/data"},
        "serviceEndpoints": {"api": "https://api.dev.example.com"},
        "storageBuckets": {},
        "customSettings": {"log_level": "INFO"},
    }

    env_path = tmp_dir / "environment.json"
    with env_path.open("w") as f:
        json.dump(env_data, f, indent=2)

    return env_path


@pytest.fixture
def sample_agent_dir(tmp_dir: Path) -> Path:
    """Create a sample agent directory with configuration files."""
    agent_dir = tmp_dir / "agent"
    agent_dir.mkdir()

    env_data = {
        "dataStoreUris": {},
        "serviceEndpoints": {},
        "storageBuckets": {},
        "customSettings": {},
    }
    with (agent_dir / "environment.json").open("w") as f:
        json.dump(env_data, f, indent=2)

    agent_config = {
        "displayName": "Test Agent",
        "description": "A test agent for CI/CD pipeline testing",
    }
    with (agent_dir / "agent.json").open("w") as f:
        json.dump(agent_config, f, indent=2)

    return agent_dir


@pytest.fixture
def sample_test_suite(tmp_dir: Path) -> Path:
    """Create a sample evaluation test suite."""
    suite = {
        "test_cases": [
            {
                "name": "greeting",
                "user_input": "Hello",
                "expected_keywords": ["hello", "hi"],
                "expected_not_contain": ["error"],
                "max_latency_ms": 5000,
            },
            {
                "name": "help_request",
                "user_input": "Help me",
                "expected_keywords": ["help"],
                "expected_not_contain": [],
                "max_latency_ms": 5000,
            },
        ]
    }

    suite_path = tmp_dir / "test_suite.yaml"
    with suite_path.open("w") as f:
        yaml.dump(suite, f)

    return suite_path
