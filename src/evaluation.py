"""Agent evaluation utilities for CX Agent Studio.

Provides automated evaluation of agent quality including accuracy,
latency, and safety checks. Integrates with CES SessionService
to run test conversations and assess agent responses.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import httpx
import yaml
from rich.console import Console

from src.auth import CES_API_ENDPOINT, get_auth_headers

console = Console()

API_VERSION = "v1beta"


@dataclass
class TestCase:
    """A single evaluation test case."""

    name: str
    user_input: str
    expected_intent: str = ""
    expected_keywords: list[str] = field(default_factory=list)
    expected_not_contain: list[str] = field(default_factory=list)
    max_latency_ms: int = 5000


@dataclass
class EvalResult:
    """Result of a single test case evaluation."""

    test_name: str
    passed: bool
    latency_ms: float
    response_text: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalReport:
    """Consolidated evaluation report."""

    total_tests: int
    passed_tests: int
    failed_tests: int
    avg_latency_ms: float
    results: list[EvalResult]
    test_type: str = "default"

    @property
    def score(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return self.passed_tests / self.total_tests

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_type": self.test_type,
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "score": round(self.score, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "results": [
                {
                    "test_name": r.test_name,
                    "passed": r.passed,
                    "latency_ms": round(r.latency_ms, 2),
                    "response_text": r.response_text[:500],
                    "details": r.details,
                }
                for r in self.results
            ],
        }


def load_test_suite(test_suite_path: str | Path) -> list[TestCase]:
    """Load test cases from a YAML file."""
    path = Path(test_suite_path)
    if not path.exists():
        msg = f"Test suite not found: {path}"
        raise FileNotFoundError(msg)

    with path.open() as f:
        data = yaml.safe_load(f)

    test_cases = []
    for tc in data.get("test_cases", []):
        test_cases.append(TestCase(**tc))

    return test_cases


def run_session(
    project_id: str,
    app_id: str,
    user_input: str,
    region: str = "us",
    session_id: str | None = None,
) -> dict[str, Any]:
    """Run a single session turn via the CES v1beta SessionService.

    API: POST /v1beta/{config.session=projects/*/locations/*/apps/*/sessions/*}:runSession

    The session resource name is used in both the URL path (gRPC transcoding)
    AND the request body config.session field — they must match.

    Request body:
      {
        "config": { "session": "<full session resource name>" },
        "inputs": [{ "text": "<user input>" }]   ← note: "inputs" (array), not "input"
      }

    Response body: { "outputs": [{ "text": "...", "turnCompleted": true, ... }] }
    """
    import uuid

    # Generate a stable session ID if not provided
    sid = session_id or uuid.uuid4().hex
    session_resource = (
        f"projects/{project_id}/locations/{region}/apps/{app_id}/sessions/{sid}"
    )

    # URL uses the session resource name for gRPC-transcoding path binding
    url = f"{CES_API_ENDPOINT}/{API_VERSION}/{session_resource}:runSession"

    payload: dict[str, Any] = {
        "config": {
            # Required: full resource name of the session
            "session": session_resource,
        },
        # "inputs" is an array of SessionInput objects (not "input")
        "inputs": [
            {"text": user_input},
        ],
    }

    headers = get_auth_headers()
    headers["Content-Type"] = "application/json"

    with httpx.Client(timeout=30) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return cast(dict[str, Any], response.json())


def evaluate_accuracy(
    project_id: str,
    app_id: str,
    test_cases: list[TestCase],
    region: str = "us",
) -> EvalReport:
    """Run accuracy evaluation: checks if agent responses match expectations."""
    results: list[EvalResult] = []

    for tc in test_cases:
        start = time.monotonic()
        try:
            resp = run_session(project_id, app_id, tc.user_input, region)
            latency_ms = (time.monotonic() - start) * 1000

            response_text = _extract_response_text(resp)
            passed = True
            details: dict[str, Any] = {}

            if tc.expected_keywords:
                resp_lower = response_text.lower()
                missing = [kw for kw in tc.expected_keywords if kw.lower() not in resp_lower]
                if missing:
                    passed = False
                    details["missing_keywords"] = missing

            if tc.expected_not_contain:
                resp_lower = response_text.lower()
                found = [kw for kw in tc.expected_not_contain if kw.lower() in resp_lower]
                if found:
                    passed = False
                    details["unexpected_content"] = found

            results.append(
                EvalResult(
                    test_name=tc.name,
                    passed=passed,
                    latency_ms=latency_ms,
                    response_text=response_text,
                    details=details,
                )
            )

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            results.append(
                EvalResult(
                    test_name=tc.name,
                    passed=False,
                    latency_ms=latency_ms,
                    response_text="",
                    details={"error": str(e)},
                )
            )

    return _build_report(results, "accuracy")


def evaluate_latency(
    project_id: str,
    app_id: str,
    test_cases: list[TestCase],
    region: str = "us",
) -> EvalReport:
    """Run latency evaluation: checks if agent responses are within time limits."""
    results: list[EvalResult] = []

    for tc in test_cases:
        start = time.monotonic()
        try:
            resp = run_session(project_id, app_id, tc.user_input, region)
            latency_ms = (time.monotonic() - start) * 1000
            response_text = _extract_response_text(resp)

            passed = latency_ms <= tc.max_latency_ms
            results.append(
                EvalResult(
                    test_name=tc.name,
                    passed=passed,
                    latency_ms=latency_ms,
                    response_text=response_text,
                    details={"max_latency_ms": tc.max_latency_ms},
                )
            )

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            results.append(
                EvalResult(
                    test_name=tc.name,
                    passed=False,
                    latency_ms=latency_ms,
                    response_text="",
                    details={"error": str(e)},
                )
            )

    return _build_report(results, "latency")


def evaluate_safety(
    project_id: str,
    app_id: str,
    test_cases: list[TestCase],
    region: str = "us",
) -> EvalReport:
    """Run safety evaluation: ensures agent does not produce harmful content."""
    results: list[EvalResult] = []

    for tc in test_cases:
        start = time.monotonic()
        try:
            resp = run_session(project_id, app_id, tc.user_input, region)
            latency_ms = (time.monotonic() - start) * 1000
            response_text = _extract_response_text(resp)

            passed = True
            details: dict[str, Any] = {}

            if tc.expected_not_contain:
                resp_lower = response_text.lower()
                found = [kw for kw in tc.expected_not_contain if kw.lower() in resp_lower]
                if found:
                    passed = False
                    details["safety_violations"] = found

            results.append(
                EvalResult(
                    test_name=tc.name,
                    passed=passed,
                    latency_ms=latency_ms,
                    response_text=response_text,
                    details=details,
                )
            )

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            results.append(
                EvalResult(
                    test_name=tc.name,
                    passed=False,
                    latency_ms=latency_ms,
                    response_text="",
                    details={"error": str(e)},
                )
            )

    return _build_report(results, "safety")


def run_smoke_test(
    project_id: str,
    app_id: str,
    region: str = "us",
) -> bool:
    """Run a basic smoke test to verify the agent is responding."""
    test_inputs = [
        "Hello",
        "What can you help me with?",
    ]

    for user_input in test_inputs:
        try:
            resp = run_session(project_id, app_id, user_input, region)
            response_text = _extract_response_text(resp)
            if not response_text:
                console.print(f"[red]Smoke test failed:[/] empty response for '{user_input}'")
                return False
            console.print(f"[green]Smoke test passed:[/] '{user_input}' -> got response")
        except Exception as e:
            console.print(f"[red]Smoke test failed:[/] {e}")
            return False

    console.print("[bold green]All smoke tests passed![/]")
    return True


def generate_report_markdown(reports: list[EvalReport]) -> str:
    """Generate a Markdown evaluation report from multiple eval reports."""
    lines = ["# CX Agent Studio - Evaluation Report\n"]

    for report in reports:
        lines.append(f"## {report.test_type.title()} Evaluation\n")
        lines.append(f"- **Score:** {report.score:.1%}")
        lines.append(f"- **Passed:** {report.passed_tests}/{report.total_tests}")
        lines.append(f"- **Avg Latency:** {report.avg_latency_ms:.0f}ms\n")

        lines.append("| Test | Status | Latency | Details |")
        lines.append("|------|--------|---------|---------|")
        for r in report.results:
            status = "PASS" if r.passed else "FAIL"
            details = json.dumps(r.details) if r.details else "-"
            lines.append(f"| {r.test_name} | {status} | {r.latency_ms:.0f}ms | {details} |")

        lines.append("")

    return "\n".join(lines)


def _extract_response_text(response: dict[str, Any]) -> str:
    """Extract the agent's text response from a v1beta runSession response.

    Response schema:
      { "outputs": [ { "text": "...", "turnCompleted": true, ... }, ... ] }

    outputs[] is a list of SessionOutput objects. Each can have one of:
      text, audio, toolCalls, citations, googleSearchSuggestions, endSession, payload
    We collect all text outputs and join them.
    """
    outputs = response.get("outputs", [])
    if outputs and isinstance(outputs, list):
        texts = [
            out["text"]
            for out in outputs
            if isinstance(out, dict) and "text" in out
        ]
        if texts:
            return " ".join(texts)

    # Fallback: return raw JSON so smoke tests don't fail silently
    return json.dumps(response)


def _build_report(results: list[EvalResult], test_type: str) -> EvalReport:
    """Build an evaluation report from results."""
    passed = sum(1 for r in results if r.passed)
    latencies = [r.latency_ms for r in results]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    return EvalReport(
        total_tests=len(results),
        passed_tests=passed,
        failed_tests=len(results) - passed,
        avg_latency_ms=avg_latency,
        results=results,
        test_type=test_type,
    )
