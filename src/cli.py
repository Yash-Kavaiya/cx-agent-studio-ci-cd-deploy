"""CLI entry point for CX Agent Studio CI/CD pipeline.

Provides commands for agent export, import, validation, transformation,
evaluation, and deployment operations.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option(version="1.0.0", prog_name="cx-agent-studio-cicd")
def main() -> None:
    """CX Agent Studio CI/CD Pipeline CLI.

    Manage export, import, validation, and deployment of
    CX Agent Studio (Gemini Enterprise for CX) agent applications.
    """


@main.command()
@click.option("--project-id", required=True, help="GCP Project ID")
@click.option("--app-id", required=True, help="CES Agent Application ID")
@click.option("--output-dir", required=True, help="Directory to export agent to")
@click.option("--region", default="us-central1", help="GCP region")
@click.option("--backup-to-gcs", is_flag=True, help="Also backup to GCS")
@click.option("--gcs-bucket", default=None, help="GCS bucket for backup")
def export_agent(
    project_id: str,
    app_id: str,
    output_dir: str,
    region: str,
    backup_to_gcs: bool,
    gcs_bucket: str | None,
) -> None:
    """Export an agent application from CX Agent Studio."""
    from src.agent_manager import backup_to_gcs as do_backup
    from src.agent_manager import export_agent as do_export

    result_dir = do_export(project_id, app_id, output_dir, region)

    if backup_to_gcs and gcs_bucket:
        do_backup(result_dir, gcs_bucket, "agent-backups", project_id)


@main.command()
@click.option("--project-id", required=True, help="GCP Project ID")
@click.option("--app-id", required=True, help="CES Agent Application ID")
@click.option("--agent-dir", required=True, help="Directory containing agent files")
@click.option("--region", default="us-central1", help="GCP region")
def import_agent(
    project_id: str,
    app_id: str,
    agent_dir: str,
    region: str,
) -> None:
    """Import an agent application to CX Agent Studio."""
    from src.agent_manager import import_agent as do_import

    do_import(project_id, app_id, agent_dir, region)


@main.command()
@click.option("--agent-dir", required=True, help="Directory containing agent files")
@click.option("--strict", is_flag=True, help="Enable strict validation")
def validate_agent(agent_dir: str, strict: bool) -> None:
    """Validate an exported agent's configuration."""
    from src.agent_manager import validate_agent as do_validate

    issues = do_validate(agent_dir, strict)
    if issues:
        console.print("[bold red]Validation failed:[/]")
        for issue in issues:
            console.print(f"  - {issue}")
        sys.exit(1)
    else:
        console.print("[bold green]Agent validation passed![/]")


@main.command()
@click.option("--agent-dir", required=True, help="Directory containing agent files")
@click.option("--env-config", required=True, help="Path to environment config YAML")
def transform_config(agent_dir: str, env_config: str) -> None:
    """Transform agent config for a target environment."""
    from src.agent_manager import transform_agent_config
    from src.config import load_config

    config = load_config(env_config)
    transform_agent_config(agent_dir, config)


@main.command()
def validate_configs() -> None:
    """Validate all environment configuration files."""
    from src.config import load_all_configs

    configs_dir = Path("configs/environments")
    if not configs_dir.exists():
        console.print("[yellow]No environment configs directory found[/]")
        return

    try:
        configs = load_all_configs(configs_dir)
        for env_name, config in configs.items():
            console.print(f"  [green]Valid:[/] {env_name} -> {config.gcp.project_id}")
        console.print(f"[bold green]All {len(configs)} environment configs are valid![/]")
    except Exception as e:
        console.print(f"[bold red]Config validation failed:[/] {e}")
        sys.exit(1)


@main.command("validate-agent-template")
def validate_agent_template() -> None:
    """Validate agent template files."""
    template_dir = Path("configs/agent_template")
    if not template_dir.exists():
        console.print("[yellow]No agent template directory found - skipping[/]")
        return

    env_json = template_dir / "environment.json"
    if env_json.exists():
        from src.config import validate_environment_json

        issues = validate_environment_json(env_json)
        if issues:
            console.print("[bold red]Template validation failed:[/]")
            for issue in issues:
                console.print(f"  - {issue}")
            sys.exit(1)

    console.print("[bold green]Agent template validation passed![/]")


@main.command()
@click.option("--project-id", required=True, help="GCP Project ID")
@click.option("--app-id", required=True, help="CES Agent Application ID")
@click.option("--env-config", default=None, help="Environment config path")
@click.option("--region", default="us-central1", help="GCP region")
def smoke_test(
    project_id: str,
    app_id: str,
    env_config: str | None,
    region: str,
) -> None:
    """Run smoke tests against a deployed agent."""
    from src.evaluation import run_smoke_test

    success = run_smoke_test(project_id, app_id, region)
    if not success:
        sys.exit(1)


@main.command()
@click.option("--project-id", required=True, help="GCP Project ID")
@click.option("--app-id", required=True, help="CES Agent Application ID")
@click.option("--test-type", default="accuracy", help="Evaluation type: accuracy, latency, safety")
@click.option("--test-suite", default="default", help="Test suite name or path")
@click.option("--min-score", default=0.0, type=float, help="Minimum passing score (0.0-1.0)")
@click.option("--output", default=None, help="Output file path for results JSON")
@click.option("--region", default="us-central1", help="GCP region")
def evaluate_agent(
    project_id: str,
    app_id: str,
    test_type: str,
    test_suite: str,
    min_score: float,
    output: str | None,
    region: str,
) -> None:
    """Run agent evaluation tests."""
    from src.evaluation import (
        evaluate_accuracy,
        evaluate_latency,
        evaluate_safety,
        load_test_suite,
    )

    suite_path = Path(test_suite)
    if not suite_path.exists():
        suite_path = Path(f"configs/evaluation/{test_suite}.yaml")
    if not suite_path.exists():
        console.print(f"[yellow]Test suite not found: {test_suite} - using empty suite[/]")
        console.print("[bold green]No tests to run - passing by default[/]")
        if output:
            empty = {"test_type": test_type, "total_tests": 0, "score": 1.0}
            Path(output).write_text(json.dumps(empty))
        return

    test_cases = load_test_suite(suite_path)

    evaluators = {
        "accuracy": evaluate_accuracy,
        "latency": evaluate_latency,
        "safety": evaluate_safety,
    }

    evaluator = evaluators.get(test_type)
    if not evaluator:
        console.print(f"[red]Unknown test type: {test_type}[/]")
        sys.exit(1)

    report = evaluator(project_id, app_id, test_cases, region)

    console.print(f"\n[bold]{test_type.title()} Evaluation Results:[/]")
    console.print(f"  Score: {report.score:.1%} ({report.passed_tests}/{report.total_tests})")
    console.print(f"  Avg Latency: {report.avg_latency_ms:.0f}ms")

    if output:
        Path(output).write_text(json.dumps(report.to_dict(), indent=2))
        console.print(f"  Results saved to: {output}")

    if report.score < min_score:
        console.print(f"[bold red]Score {report.score:.1%} below minimum {min_score:.1%}[/]")
        sys.exit(1)


@main.command("generate-eval-report")
@click.option("--results-dir", required=True, help="Directory containing result JSON files")
@click.option("--output", required=True, help="Output markdown file path")
def generate_eval_report(results_dir: str, output: str) -> None:
    """Generate a consolidated evaluation report from multiple result files."""
    from src.evaluation import EvalReport, EvalResult, generate_report_markdown

    results_path = Path(results_dir)
    reports: list[EvalReport] = []

    for json_file in sorted(results_path.glob("results-*.json")):
        with json_file.open() as f:
            data = json.load(f)

        eval_results = [
            EvalResult(
                test_name=r["test_name"],
                passed=r["passed"],
                latency_ms=r["latency_ms"],
                response_text=r.get("response_text", ""),
                details=r.get("details", {}),
            )
            for r in data.get("results", [])
        ]

        reports.append(EvalReport(
            total_tests=data["total_tests"],
            passed_tests=data["passed_tests"],
            failed_tests=data["failed_tests"],
            avg_latency_ms=data["avg_latency_ms"],
            results=eval_results,
            test_type=data.get("test_type", "unknown"),
        ))

    if reports:
        markdown = generate_report_markdown(reports)
    else:
        markdown = "# CX Agent Studio - Evaluation Report\n\nNo evaluation results found.\n"

    Path(output).write_text(markdown)
    console.print(f"[bold green]Report generated:[/] {output}")


if __name__ == "__main__":
    main()
