"""Tests for authentication module."""

from __future__ import annotations

from src.auth import CES_API_ENDPOINT, CES_SCOPES


class TestAuthConstants:
    def test_ces_scopes(self) -> None:
        assert CES_SCOPES == ["https://www.googleapis.com/auth/ces"]

    def test_ces_endpoint(self) -> None:
        assert CES_API_ENDPOINT == "https://ces.googleapis.com"
