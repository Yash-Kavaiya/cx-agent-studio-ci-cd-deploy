#!/usr/bin/env bash
# Export an agent application from CX Agent Studio.

set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
APP_ID="${CES_APP_ID:?Set CES_APP_ID}"
OUTPUT_DIR="${1:-agents/exported}"
REGION="${GCP_REGION:-us-central1}"

echo "Exporting agent ${APP_ID} from project ${PROJECT_ID}..."
python -m src.cli export-agent \
    --project-id="${PROJECT_ID}" \
    --app-id="${APP_ID}" \
    --output-dir="${OUTPUT_DIR}" \
    --region="${REGION}"

echo "Agent exported to ${OUTPUT_DIR}"
