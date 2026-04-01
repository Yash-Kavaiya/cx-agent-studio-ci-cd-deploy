"""Tests for agent management operations."""

from __future__ import annotations

import base64
import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.agent_manager import export_agent, import_agent, validate_agent


class TestExportAgent:
    """Tests for agent export pipeline."""

    def _make_zip_content(self, files: dict[str, str]) -> str:
        """Create a base64-encoded zip from a dict of filename->content."""
        import io

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, content in files.items():
                zf.writestr(name, content)
        return base64.b64encode(buf.getvalue()).decode()

    @patch("src.agent_manager._api_request")
    def test_export_inline_content(self, mock_request: MagicMock, tmp_dir: Path) -> None:
        """Test export with inline appContent (no GCS URI)."""
        agent_files = {
            "environment.json": json.dumps({"dataStoreUris": {}}),
            "agent.json": json.dumps({"displayName": "Test Agent"}),
        }
        zip_b64 = self._make_zip_content(agent_files)

        # First call: POST exportApp returns completed operation (no LRO polling needed)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "done": True,
            "response": {"appContent": zip_b64},
        }
        mock_request.return_value = mock_response

        output = tmp_dir / "exported"
        result = export_agent("test-project", "test-app", output, region="us")

        assert result == output
        assert (output / "environment.json").exists()
        assert (output / "agent.json").exists()

        env_data = json.loads((output / "environment.json").read_text())
        assert "dataStoreUris" in env_data

    @patch("src.agent_manager._api_request")
    def test_export_gcs_uri_response(self, mock_request: MagicMock, tmp_dir: Path) -> None:
        """Test export that returns a GCS URI instead of inline content."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "done": True,
            "response": {"gcsUri": "gs://my-bucket/exports/test-app.zip"},
        }
        mock_request.return_value = mock_response

        output = tmp_dir / "exported"
        result = export_agent("test-project", "test-app", output, gcs_uri="gs://my-bucket/exports")

        assert result == output
        manifest = output / "export_manifest.json"
        assert manifest.exists()
        manifest_data = json.loads(manifest.read_text())
        assert manifest_data["gcsUri"] == "gs://my-bucket/exports/test-app.zip"
        assert manifest_data["appId"] == "test-app"

    @patch("src.agent_manager._poll_operation")
    @patch("src.agent_manager._api_request")
    def test_export_with_lro_polling(
        self, mock_request: MagicMock, mock_poll: MagicMock, tmp_dir: Path
    ) -> None:
        """Test export that requires LRO polling."""
        agent_files = {
            "agent.json": json.dumps({"displayName": "Polled Agent"}),
        }
        zip_b64 = self._make_zip_content(agent_files)

        # POST exportApp returns an operation name (not done yet)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "name": "projects/test-project/locations/us/operations/op-123",
            "done": False,
        }
        mock_request.return_value = mock_response

        # Poll returns completed operation with inline content
        mock_poll.return_value = {
            "done": True,
            "response": {"appContent": zip_b64},
        }

        output = tmp_dir / "exported"
        export_agent("test-project", "test-app", output)

        mock_poll.assert_called_once_with(
            "projects/test-project/locations/us/operations/op-123",
            "test-project",
            "us",
        )
        assert (output / "agent.json").exists()

    @patch("src.agent_manager._api_request")
    def test_export_unexpected_response(self, mock_request: MagicMock, tmp_dir: Path) -> None:
        """Test export with an unexpected response saves raw JSON."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "done": True,
            "response": {"unknownField": "value"},
        }
        mock_request.return_value = mock_response

        output = tmp_dir / "exported"
        export_agent("test-project", "test-app", output)

        assert (output / "export_operation.json").exists()

    @patch("src.agent_manager._api_request")
    def test_export_data_format_parameter(self, mock_request: MagicMock, tmp_dir: Path) -> None:
        """Test that data_format parameter is passed in the request body."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "done": True,
            "response": {"gcsUri": "gs://bucket/path"},
        }
        mock_request.return_value = mock_response

        output = tmp_dir / "exported"
        export_agent(
            "test-project", "test-app", output,
            gcs_uri="gs://bucket/path", data_format="BLOB",
        )

        # Verify request body contains the data_format
        call_args = mock_request.call_args
        body = call_args.kwargs.get("json_body") or call_args[1].get("json_body")
        assert body["dataFormat"] == "BLOB"
        assert body["gcsUri"] == "gs://bucket/path"


class TestImportAgent:
    """Tests for agent import pipeline."""

    @patch("src.agent_manager._api_request")
    def test_import_agent_success(self, mock_request: MagicMock, sample_agent_dir: Path) -> None:
        """Test importing an agent directory."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "done": True,
            "response": {"name": "projects/test-project/locations/us/apps/test-app"},
        }
        mock_request.return_value = mock_response

        result = import_agent("test-project", "test-app", sample_agent_dir)
        assert result["done"] is True

        # Verify the request was made with correct URL and body structure
        call_args = mock_request.call_args
        body = call_args.kwargs.get("json_body") or call_args[1].get("json_body")
        assert body["appId"] == "test-app"
        assert "appContent" in body
        assert body["importOptions"]["conflictResolutionStrategy"] == "REPLACE"

    def test_import_missing_directory(self, tmp_dir: Path) -> None:
        """Test importing from a nonexistent directory raises FileNotFoundError."""
        import pytest

        with pytest.raises(FileNotFoundError, match="not found"):
            import_agent("test-project", "test-app", tmp_dir / "nonexistent")


class TestValidateAgent:
    def test_validate_valid_agent(self, sample_agent_dir: Path) -> None:
        issues = validate_agent(sample_agent_dir)
        assert issues == []

    def test_validate_missing_directory(self, tmp_dir: Path) -> None:
        issues = validate_agent(tmp_dir / "nonexistent")
        assert len(issues) == 1
        assert "does not exist" in issues[0]

    def test_validate_invalid_json(self, sample_agent_dir: Path) -> None:
        bad_file = sample_agent_dir / "broken.json"
        bad_file.write_text("{not valid json")

        issues = validate_agent(sample_agent_dir)
        assert len(issues) == 1
        assert "Invalid JSON" in issues[0]

    def test_validate_strict_no_env_json(self, tmp_dir: Path) -> None:
        agent_dir = tmp_dir / "agent"
        agent_dir.mkdir()
        config = {"name": "test"}
        with (agent_dir / "agent.json").open("w") as f:
            json.dump(config, f)

        issues = validate_agent(agent_dir, strict=True)
        assert any("environment.json not found" in i for i in issues)

    def test_validate_strict_no_json_files(self, tmp_dir: Path) -> None:
        agent_dir = tmp_dir / "empty_agent"
        agent_dir.mkdir()
        (agent_dir / "readme.txt").write_text("hello")

        issues = validate_agent(agent_dir, strict=True)
        assert any("No JSON configuration files" in i for i in issues)

    def test_validate_non_strict_missing_env_json(self, tmp_dir: Path) -> None:
        agent_dir = tmp_dir / "agent"
        agent_dir.mkdir()
        config = {"name": "test"}
        with (agent_dir / "agent.json").open("w") as f:
            json.dump(config, f)

        issues = validate_agent(agent_dir, strict=False)
        assert issues == []

    def test_validate_invalid_env_json_root(self, tmp_dir: Path) -> None:
        agent_dir = tmp_dir / "agent"
        agent_dir.mkdir()
        with (agent_dir / "environment.json").open("w") as f:
            json.dump(["not", "an", "object"], f)

        issues = validate_agent(agent_dir)
        assert any("must be a JSON object" in i for i in issues)
