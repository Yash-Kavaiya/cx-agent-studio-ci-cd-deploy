# CX Agent Studio CI/CD Pipeline

Production-grade CI/CD pipeline for **Google Cloud CX Agent Studio** (Gemini Enterprise for Customer Experience). Automates the build, test, validate, and deploy lifecycle for conversational AI agents using the `ces.googleapis.com` API.

## Architecture

```
                    ┌─────────────┐
                    │  Developer   │
                    │  Push/PR     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   GitHub    │
                    │   Actions   │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌───▼───┐ ┌─────▼─────┐
        │   Lint &   │ │ Unit  │ │ Security  │
        │   Format   │ │ Tests │ │   Scan    │
        └─────┬─────┘ └───┬───┘ └─────┬─────┘
              └────────────┼────────────┘
                           │
                    ┌──────▼──────┐
                    │  Validate   │
                    │   Configs   │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │                         │
        ┌─────▼──────┐          ┌──────▼──────┐
        │  Deploy to  │          │  Deploy to   │
        │   Staging   │──────▶  │  Production  │
        │  (auto)     │  eval   │  (tag-based) │
        └─────┬──────┘          └──────┬──────┘
              │                         │
        ┌─────▼──────┐          ┌──────▼──────┐
        │   Smoke    │          │   Smoke     │
        │   Tests    │          │   Tests     │
        └────────────┘          └─────┬──────┘
                                      │
                                ┌─────▼──────┐
                                │  Rollback   │
                                │  (on fail)  │
                                └────────────┘
```

## Features

- **CI Pipeline**: Linting (Ruff), type checking (mypy), unit tests with coverage, security scanning, and agent config validation
- **CD Pipeline**: Automated staging deployment on `develop` branch push; production deployment on version tags (`v*.*.*`)
- **Agent Lifecycle**: Export from source → transform config → validate → import to target → smoke test
- **Environment Management**: YAML-based configs for dev/staging/production with `environment.json` overrides
- **Agent Evaluation**: Scheduled and on-demand evaluation of agent quality (accuracy, latency, safety)
- **Auto-Rollback**: Pre-deployment backups with automatic rollback on production failures
- **GCS Backups**: Agent archives backed up to Cloud Storage with versioning
- **Workload Identity Federation**: Keyless authentication from GitHub Actions to GCP
- **Docker Support**: Containerized CLI for portable execution
- **Cloud Build**: Alternative `cloudbuild.yaml` for teams using Google Cloud Build

## Quick Start

### Prerequisites

- Python 3.11+
- Google Cloud SDK (`gcloud`)
- A GCP project with CX Agent Studio enabled

### 1. Clone and Install

```bash
git clone https://github.com/Yash-Kavaiya/cx-agent-studio-ci-cd-deploy.git
cd cx-agent-studio-ci-cd-deploy
pip install -r requirements-dev.txt
```

### 2. Configure GCP Project

```bash
# Set your environment variables
export GCP_PROJECT_ID="your-project-id"
export GITHUB_REPO="owner/repo"

# Run the setup script (enables APIs, creates service account, configures WIF)
bash scripts/setup_gcp.sh
```

### 3. Configure Environments

Edit the environment config files in `configs/environments/`:

```bash
configs/environments/
├── dev.yaml         # Development settings
├── staging.yaml     # Staging settings
└── production.yaml  # Production settings
```

Update `project_id`, `app_id`, and `bucket_name` in each file to match your GCP projects.

### 4. Set GitHub Secrets

Add these secrets to your GitHub repository (output by the setup script):

| Secret | Description |
|--------|-------------|
| `GCP_PROJECT_ID` | Default GCP project ID |
| `GCP_PROJECT_ID_DEV` | Dev environment project ID |
| `GCP_PROJECT_ID_STAGING` | Staging environment project ID |
| `GCP_PROJECT_ID_PRODUCTION` | Production environment project ID |
| `GCP_SERVICE_ACCOUNT` | Service account email |
| `GCP_SERVICE_ACCOUNT_PROD` | Production service account email |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | WIF provider resource name |
| `CES_APP_ID` | Default CES Application ID |
| `CES_APP_ID_STAGING` | Staging CES Application ID |
| `CES_APP_ID_PRODUCTION` | Production CES Application ID |
| `GCS_BACKUP_BUCKET` | GCS bucket for backups |
| `SLACK_WEBHOOK_URL` | (Optional) Slack notifications |

### 5. Run Tests

```bash
make test
```

## CLI Reference

```bash
# Export an agent application
python -m src.cli export-agent --project-id=PROJECT --app-id=APP --output-dir=agents/exported

# Import an agent application
python -m src.cli import-agent --project-id=PROJECT --app-id=APP --agent-dir=agents/exported

# Transform config for target environment
python -m src.cli transform-config --agent-dir=agents/exported --env-config=configs/environments/staging.yaml

# Validate agent configuration
python -m src.cli validate-agent --agent-dir=agents/exported --strict

# Validate all environment configs
python -m src.cli validate-configs

# Run smoke tests
python -m src.cli smoke-test --project-id=PROJECT --app-id=APP

# Run agent evaluation
python -m src.cli evaluate-agent --project-id=PROJECT --app-id=APP --test-type=accuracy --min-score=0.85

# Generate evaluation report
python -m src.cli generate-eval-report --results-dir=. --output=report.md
```

## Pipeline Workflows

### CI (`.github/workflows/ci.yml`)

Runs on every push/PR to `main` or `develop`:

1. **Lint & Format** - Ruff linter + formatter check + mypy
2. **Unit Tests** - pytest with coverage reporting
3. **Validate Configs** - Environment YAML + agent template validation
4. **Security Scan** - Ruff security rules + secrets detection

### CD Staging (`.github/workflows/cd-staging.yml`)

Runs on push to `develop`:

1. Authenticate to GCP via Workload Identity
2. Export agent from dev environment
3. Transform config for staging
4. Validate agent
5. Import agent to staging
6. Run smoke tests
7. Notify via Slack

### CD Production (`.github/workflows/cd-production.yml`)

Runs on version tags (`v*.*.*`):

1. Pre-deploy agent evaluation (quality gate)
2. Create production backup
3. Export agent from staging
4. Transform config for production
5. Validate agent (strict mode)
6. Import agent to production
7. Run smoke tests
8. Auto-rollback on failure
9. Notify via Slack

### Agent Evaluation (`.github/workflows/agent-evaluation.yml`)

Scheduled (Mon-Fri 6AM UTC) or manual:

- Tests accuracy, latency, and safety in parallel
- Generates consolidated Markdown report
- Configurable test suites in `configs/evaluation/`

## Project Structure

```
├── .github/workflows/          # GitHub Actions CI/CD pipelines
│   ├── ci.yml                  # CI: lint, test, validate, security
│   ├── cd-staging.yml          # CD: deploy to staging
│   ├── cd-production.yml       # CD: deploy to production
│   └── agent-evaluation.yml    # Scheduled agent evaluation
├── src/                        # Python source code
│   ├── agent_manager.py        # Agent export/import/validate/deploy
│   ├── auth.py                 # GCP authentication (ADC, WIF, SA)
│   ├── cli.py                  # Click CLI entry point
│   ├── config.py               # Config loading and transformation
│   └── evaluation.py           # Agent quality evaluation
├── tests/                      # Unit tests (pytest)
├── scripts/                    # Shell scripts
│   ├── setup_gcp.sh            # GCP project setup + WIF
│   ├── deploy.sh               # Full deployment orchestration
│   ├── export_agent.sh         # Agent export helper
│   ├── import_agent.sh         # Agent import helper
│   └── validate_agent.sh       # Agent validation helper
├── configs/
│   ├── environments/           # Per-environment YAML configs
│   ├── evaluation/             # Evaluation test suites
│   └── agent_template/         # Template environment.json
├── agents/                     # Agent export/backup directory
├── Dockerfile                  # Container image
├── docker-compose.yml          # Docker Compose config
├── cloudbuild.yaml             # Google Cloud Build alternative
├── Makefile                    # Development shortcuts
├── pyproject.toml              # Python project config
└── requirements.txt            # Production dependencies
```

## CX Agent Studio API Reference

This pipeline integrates with the `ces.googleapis.com` API (`google.cloud.ces.v1`):

| Service | Description |
|---------|-------------|
| **AgentService** | Manage agent resources, toolsets, app versions |
| **SessionService** | Run interactive sessions with agents |
| **ToolService** | Manage and retrieve agent tools |
| **WidgetService** | Widget interaction APIs |

Key operations used:
- `export` / `import` - Agent application lifecycle
- `RestoreAppVersion` - Version rollback
- `RunSession` - Agent testing and evaluation

Authentication: OAuth 2.0 with scope `https://www.googleapis.com/auth/ces`

## Documentation

- [CX Agent Studio Overview](https://docs.cloud.google.com/customer-engagement-ai/conversational-agents/ps)
- [CES API Reference (google.cloud.ces.v1)](https://docs.cloud.google.com/customer-engagement-ai/conversational-agents/ps/reference/rpc/google.cloud.ces.v1)
- [Authentication](https://docs.cloud.google.com/customer-engagement-ai/conversational-agents/ps/reference/authentication)
- [MCP Server](https://docs.cloud.google.com/customer-engagement-ai/conversational-agents/ps/mcp-server)
- [Export & Import](https://docs.cloud.google.com/customer-engagement-ai/conversational-agents/ps/export)
- [CCaaS Deployment](https://docs.cloud.google.com/customer-engagement-ai/conversational-agents/ps/deploy/ccaas)
- [Gemini Enterprise for CX](https://cloud.google.com/products/gemini-enterprise-for-customer-experience)

## License

Apache 2.0
