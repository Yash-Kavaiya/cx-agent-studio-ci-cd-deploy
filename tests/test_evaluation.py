"""Tests for agent evaluation utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.evaluation import (
    EvalReport,
    EvalResult,
    TestCase,
    _build_report,
    _extract_response_text,
    generate_report_markdown,
    load_test_suite,
)


class TestTestCase:
    def test_create_test_case(self) -> None:
        tc = TestCase(
            name="greeting",
            user_input="Hello",
            expected_keywords=["hello", "hi"],
            max_latency_ms=3000,
        )
        assert tc.name == "greeting"
        assert tc.user_input == "Hello"
        assert len(tc.expected_keywords) == 2
        assert tc.max_latency_ms == 3000

    def test_default_values(self) -> None:
        tc = TestCase(name="test", user_input="Hi")
        assert tc.expected_intent == ""
        assert tc.expected_keywords == []
        assert tc.expected_not_contain == []
        assert tc.max_latency_ms == 5000


class TestLoadTestSuite:
    def test_load_valid_suite(self, sample_test_suite: Path) -> None:
        test_cases = load_test_suite(sample_test_suite)
        assert len(test_cases) == 2
        assert test_cases[0].name == "greeting"
        assert test_cases[1].name == "help_request"

    def test_load_missing_suite(self, tmp_dir: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_test_suite(tmp_dir / "missing.yaml")


class TestExtractResponseText:
    def test_extract_from_output_text(self) -> None:
        response = {"output": {"text": "Hello there!"}}
        assert _extract_response_text(response) == "Hello there!"

    def test_extract_from_output_string(self) -> None:
        response = {"output": "Direct string response"}
        assert _extract_response_text(response) == "Direct string response"

    def test_extract_from_messages(self) -> None:
        response = {"messages": [{"text": "First"}, {"text": "Last message"}]}
        assert _extract_response_text(response) == "Last message"

    def test_extract_fallback_to_json(self) -> None:
        response = {"some_other_field": "value"}
        result = _extract_response_text(response)
        assert "some_other_field" in result


class TestBuildReport:
    def test_build_report_all_passed(self) -> None:
        results = [
            EvalResult("test1", True, 100.0, "response1"),
            EvalResult("test2", True, 200.0, "response2"),
        ]
        report = _build_report(results, "accuracy")
        assert report.total_tests == 2
        assert report.passed_tests == 2
        assert report.failed_tests == 0
        assert report.score == 1.0
        assert report.avg_latency_ms == 150.0

    def test_build_report_mixed(self) -> None:
        results = [
            EvalResult("test1", True, 100.0, "response1"),
            EvalResult("test2", False, 200.0, "response2"),
        ]
        report = _build_report(results, "accuracy")
        assert report.total_tests == 2
        assert report.passed_tests == 1
        assert report.failed_tests == 1
        assert report.score == 0.5

    def test_build_report_empty(self) -> None:
        report = _build_report([], "accuracy")
        assert report.total_tests == 0
        assert report.score == 0.0
        assert report.avg_latency_ms == 0


class TestEvalReport:
    def test_to_dict(self) -> None:
        report = EvalReport(
            total_tests=2,
            passed_tests=1,
            failed_tests=1,
            avg_latency_ms=150.5,
            results=[
                EvalResult("test1", True, 100.0, "response1"),
                EvalResult("test2", False, 200.0, "response2", {"error": "timeout"}),
            ],
            test_type="accuracy",
        )

        d = report.to_dict()
        assert d["test_type"] == "accuracy"
        assert d["total_tests"] == 2
        assert d["score"] == 0.5
        assert len(d["results"]) == 2

    def test_score_property(self) -> None:
        report = EvalReport(
            total_tests=4,
            passed_tests=3,
            failed_tests=1,
            avg_latency_ms=100,
            results=[],
        )
        assert report.score == 0.75


class TestGenerateReportMarkdown:
    def test_generate_report(self) -> None:
        reports = [
            EvalReport(
                total_tests=2,
                passed_tests=2,
                failed_tests=0,
                avg_latency_ms=100,
                results=[
                    EvalResult("test1", True, 80.0, "resp1"),
                    EvalResult("test2", True, 120.0, "resp2"),
                ],
                test_type="accuracy",
            )
        ]

        markdown = generate_report_markdown(reports)
        assert "# CX Agent Studio" in markdown
        assert "Accuracy Evaluation" in markdown
        assert "100.0%" in markdown
        assert "test1" in markdown

    def test_generate_empty_report(self) -> None:
        markdown = generate_report_markdown([])
        assert "# CX Agent Studio" in markdown
