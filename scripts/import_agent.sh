#!/usr/bin/env bash
# Import an agent application to CX Agent Studio.

set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
APP_ID="${CES_APP_ID:?Set CES_APP_ID}"
AGENT_DIR="${1:-agents/exported}"
REGION="${GCP_REGION:-us-central1}"

echo "Importing agent to ${APP_ID} in project ${PROJECT_ID}..."
python -m src.cli import-agent \
    --project-id="${PROJECT_ID}" \
    --app-id="${APP_ID}" \
    --agent-dir="${AGENT_DIR}" \
    --region="${REGION}"

echo "Agent imported successfully"
