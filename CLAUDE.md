# CLAUDE.md

## Project Overview

CI/CD pipeline for Google Cloud CX Agent Studio (Gemini Enterprise for Customer Experience). Uses the `ces.googleapis.com` API to manage conversational AI agents across dev/staging/production environments.

## Tech Stack

- **Language**: Python 3.11+
- **CLI Framework**: Click + Rich
- **Config Validation**: Pydantic
- **Testing**: pytest + pytest-cov
- **Linting**: Ruff + mypy
- **CI/CD**: GitHub Actions (primary), Google Cloud Build (alternative)
- **GCP APIs**: ces.googleapis.com (google.cloud.ces.v1)
- **Auth**: Workload Identity Federation, Application Default Credentials

## Key Commands

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v

# Run linter
ruff check src/ tests/

# Format code
ruff format src/ tests/

# Validate configs
python -m src.cli validate-configs
```

## Project Structure

- `src/` - Python source code (agent_manager, auth, config, evaluation, cli)
- `tests/` - Unit tests
- `.github/workflows/` - CI/CD pipelines
- `configs/environments/` - Per-environment YAML configs (dev, staging, production)
- `configs/evaluation/` - Agent evaluation test suites
- `scripts/` - Shell scripts for GCP setup and deployment
