---
name: ci-cd-workflow-update
description: Workflow command scaffold for ci-cd-workflow-update in cx-agent-studio-ci-cd-deploy.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /ci-cd-workflow-update

Use this workflow when working on **ci-cd-workflow-update** in `cx-agent-studio-ci-cd-deploy`.

## Goal

Updates CI/CD pipeline workflows to fix, enhance, or align deployment and evaluation automation.

## Common Files

- `.github/workflows/agent-evaluation.yml`
- `.github/workflows/cd-production.yml`
- `.github/workflows/cd-staging.yml`
- `.github/workflows/ci.yml`
- `scripts/setup_gcp.sh`
- `src/cli.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit .github/workflows/*.yml to update steps, flags, or triggers.
- Edit scripts (scripts/*.sh) if deployment/evaluation scripts need changes.
- Optionally update src/cli.py or related Python files to support new CLI flags or behaviors.
- Test and validate workflow changes via pushes or PRs.

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.