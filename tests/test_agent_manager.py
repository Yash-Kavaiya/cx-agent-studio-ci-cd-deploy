"""Tests for agent management operations."""

from __future__ import annotations

import json
from pathlib import Path

from src.agent_manager import validate_agent


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
