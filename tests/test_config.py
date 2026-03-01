"""Tests for configuration management module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from src.config import (
    EnvironmentOverrides,
    PipelineConfig,
    load_all_configs,
    load_config,
    transform_environment_json,
    validate_environment_json,
)


class TestLoadConfig:
    def test_load_valid_config(self, sample_env_config: Path) -> None:
        config = load_config(sample_env_config)
        assert isinstance(config, PipelineConfig)
        assert config.gcp.project_id == "test-project-123"
        assert config.gcp.region == "us-central1"
        assert config.ces.app_id == "test-app-456"
        assert config.deployment.environment == "test"

    def test_load_missing_config(self, tmp_dir: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_config(tmp_dir / "nonexistent.yaml")

    def test_load_config_with_defaults(self, tmp_dir: Path) -> None:
        minimal_config = {
            "gcp": {"project_id": "proj-1"},
            "ces": {"app_id": "app-1"},
            "storage": {"bucket_name": "bucket-1"},
            "deployment": {"environment": "dev"},
        }
        config_path = tmp_dir / "minimal.yaml"
        with config_path.open("w") as f:
            yaml.dump(minimal_config, f)

        config = load_config(config_path)
        assert config.gcp.region == "us-central1"
        assert config.ces.api_endpoint == "ces.googleapis.com"
        assert config.deployment.auto_rollback is True


class TestLoadAllConfigs:
    def test_load_all_configs(self, tmp_dir: Path) -> None:
        for env in ["dev", "staging"]:
            config = {
                "gcp": {"project_id": f"proj-{env}"},
                "ces": {"app_id": f"app-{env}"},
                "storage": {"bucket_name": f"bucket-{env}"},
                "deployment": {"environment": env},
            }
            with (tmp_dir / f"{env}.yaml").open("w") as f:
                yaml.dump(config, f)

        configs = load_all_configs(tmp_dir)
        assert len(configs) == 2
        assert "dev" in configs
        assert "staging" in configs
        assert configs["dev"].gcp.project_id == "proj-dev"


class TestValidateEnvironmentJson:
    def test_valid_environment_json(self, sample_environment_json: Path) -> None:
        issues = validate_environment_json(sample_environment_json)
        assert issues == []

    def test_missing_environment_json(self, tmp_dir: Path) -> None:
        issues = validate_environment_json(tmp_dir / "missing.json")
        assert len(issues) == 1
        assert "not found" in issues[0]

    def test_invalid_json(self, tmp_dir: Path) -> None:
        bad_path = tmp_dir / "bad.json"
        bad_path.write_text("{invalid json}")
        issues = validate_environment_json(bad_path)
        assert len(issues) == 1
        assert "Invalid JSON" in issues[0]

    def test_non_object_json(self, tmp_dir: Path) -> None:
        arr_path = tmp_dir / "array.json"
        arr_path.write_text("[]")
        issues = validate_environment_json(arr_path)
        assert len(issues) == 1
        assert "must be a JSON object" in issues[0]


class TestTransformEnvironmentJson:
    def test_transform_adds_overrides(self, sample_environment_json: Path) -> None:
        overrides = EnvironmentOverrides(
            data_store_uris={"new_store": "gs://new-bucket/data"},
            service_endpoints={"backend": "https://api.staging.example.com"},
            custom_settings={"log_level": "WARNING"},
        )

        transform_environment_json(sample_environment_json, overrides)

        with sample_environment_json.open() as f:
            data = json.load(f)

        assert data["dataStoreUris"]["new_store"] == "gs://new-bucket/data"
        assert data["dataStoreUris"]["default"] == "gs://original-bucket/data"
        assert data["serviceEndpoints"]["backend"] == "https://api.staging.example.com"
        assert data["customSettings"]["log_level"] == "WARNING"

    def test_transform_to_different_output(
        self, sample_environment_json: Path, tmp_dir: Path
    ) -> None:
        output_path = tmp_dir / "output_env.json"
        overrides = EnvironmentOverrides(
            storage_buckets={"uploads": "new-uploads-bucket"},
        )

        result = transform_environment_json(sample_environment_json, overrides, output_path)

        assert result == output_path
        with output_path.open() as f:
            data = json.load(f)
        assert data["storageBuckets"]["uploads"] == "new-uploads-bucket"

        # Original should be unchanged
        with sample_environment_json.open() as f:
            original = json.load(f)
        assert "uploads" not in original.get("storageBuckets", {})
