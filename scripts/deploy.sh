#!/usr/bin/env bash
# Deploy script for CX Agent Studio agent applications.
# Orchestrates the export -> transform -> validate -> import pipeline.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"

# ============================================================
# Configuration
# ============================================================
SOURCE_PROJECT="${SOURCE_PROJECT_ID:?Set SOURCE_PROJECT_ID}"
TARGET_PROJECT="${TARGET_PROJECT_ID:?Set TARGET_PROJECT_ID}"
APP_ID="${CES_APP_ID:?Set CES_APP_ID}"
TARGET_APP_ID="${CES_TARGET_APP_ID:-${APP_ID}}"
DEPLOY_ENV="${DEPLOY_ENV:?Set DEPLOY_ENV (dev|staging|production)}"
REGION="${GCP_REGION:-us-central1}"

EXPORT_DIR="${PROJECT_ROOT}/agents/exported"
BACKUP_DIR="${PROJECT_ROOT}/agents/backup"
ENV_CONFIG="${PROJECT_ROOT}/configs/environments/${DEPLOY_ENV}.yaml"

echo "=== CX Agent Studio Deployment ==="
echo "Source: ${SOURCE_PROJECT} / ${APP_ID}"
echo "Target: ${TARGET_PROJECT} / ${TARGET_APP_ID}"
echo "Environment: ${DEPLOY_ENV}"
echo ""

# ============================================================
# 1. Pre-deployment backup (production only)
# ============================================================
if [ "${DEPLOY_ENV}" = "production" ]; then
    echo "--- Creating pre-deployment backup ---"
    python -m src.cli export-agent \
        --project-id="${TARGET_PROJECT}" \
        --app-id="${TARGET_APP_ID}" \
        --output-dir="${BACKUP_DIR}" \
        --region="${REGION}"
    echo "Backup created at ${BACKUP_DIR}"
fi

# ============================================================
# 2. Export agent from source
# ============================================================
echo "--- Exporting agent ---"
python -m src.cli export-agent \
    --project-id="${SOURCE_PROJECT}" \
    --app-id="${APP_ID}" \
    --output-dir="${EXPORT_DIR}" \
    --region="${REGION}"

# ============================================================
# 3. Transform config for target environment
# ============================================================
echo "--- Transforming configuration ---"
if [ -f "${ENV_CONFIG}" ]; then
    python -m src.cli transform-config \
        --agent-dir="${EXPORT_DIR}" \
        --env-config="${ENV_CONFIG}"
else
    echo "Warning: No environment config found at ${ENV_CONFIG} - skipping transform"
fi

# ============================================================
# 4. Validate agent
# ============================================================
echo "--- Validating agent ---"
STRICT_FLAG=""
if [ "${DEPLOY_ENV}" = "production" ]; then
    STRICT_FLAG="--strict"
fi
python -m src.cli validate-agent \
    --agent-dir="${EXPORT_DIR}" \
    ${STRICT_FLAG}

# ============================================================
# 5. Import agent to target
# ============================================================
echo "--- Importing agent ---"
python -m src.cli import-agent \
    --project-id="${TARGET_PROJECT}" \
    --app-id="${TARGET_APP_ID}" \
    --agent-dir="${EXPORT_DIR}" \
    --region="${REGION}"

# ============================================================
# 6. Smoke test
# ============================================================
echo "--- Running smoke tests ---"
python -m src.cli smoke-test \
    --project-id="${TARGET_PROJECT}" \
    --app-id="${TARGET_APP_ID}" \
    --region="${REGION}"

echo ""
echo "=== Deployment Complete ==="
