---
name: align-api-contract-and-endpoints
description: Workflow command scaffold for align-api-contract-and-endpoints in cx-agent-studio-ci-cd-deploy.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /align-api-contract-and-endpoints

Use this workflow when working on **align-api-contract-and-endpoints** in `cx-agent-studio-ci-cd-deploy`.

## Goal

Aligns the codebase with the latest CES API contract, including endpoint URLs, request/response formats, and required fields.

## Common Files

- `src/agent_manager.py`
- `src/evaluation.py`
- `src/cli.py`
- `configs/environments/dev.yaml`
- `configs/environments/production.yaml`
- `configs/environments/staging.yaml`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Update src/agent_manager.py with new/changed API fields, endpoints, and LRO handling.
- Update src/evaluation.py to match new payload/request/response schemas.
- Update src/cli.py if CLI commands or options change.
- Update environment configs (configs/environments/*.yaml) if project IDs, app IDs, or regions change.
- Update workflow YAMLs (.github/workflows/*.yml) to reflect new CLI flags or region defaults.

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.