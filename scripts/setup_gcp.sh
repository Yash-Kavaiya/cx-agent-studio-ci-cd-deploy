#!/usr/bin/env bash
# Setup script for Google Cloud CX Agent Studio CI/CD pipeline.
# Configures GCP project, enables APIs, creates service accounts,
# and sets up Workload Identity Federation for GitHub Actions.

set -euo pipefail

# ============================================================
# Configuration - Update these values for your environment
# ============================================================
PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID environment variable}"
REGION="${GCP_REGION:-us-central1}"
GITHUB_REPO="${GITHUB_REPO:?Set GITHUB_REPO (e.g., owner/repo)}"

SA_NAME="cx-agent-cicd"
SA_DISPLAY_NAME="CX Agent Studio CI/CD Service Account"
WIF_POOL_NAME="github-actions-pool"
WIF_PROVIDER_NAME="github-actions-provider"

echo "=== CX Agent Studio CI/CD - GCP Setup ==="
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "GitHub Repo: ${GITHUB_REPO}"
echo ""

# ============================================================
# 1. Enable required APIs
# ============================================================
echo "--- Enabling APIs ---"
gcloud services enable \
    ces.googleapis.com \
    cloudresourcemanager.googleapis.com \
    iam.googleapis.com \
    iamcredentials.googleapis.com \
    storage.googleapis.com \
    --project="${PROJECT_ID}"

echo "Enabling CES MCP server..."
gcloud beta services mcp enable ces.googleapis.com --project="${PROJECT_ID}" || true

echo "APIs enabled."

# ============================================================
# 2. Create Service Account
# ============================================================
echo "--- Creating Service Account ---"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "Service account already exists: ${SA_EMAIL}"
else
    gcloud iam service-accounts create "${SA_NAME}" \
        --display-name="${SA_DISPLAY_NAME}" \
        --project="${PROJECT_ID}"
    echo "Service account created: ${SA_EMAIL}"
fi

# ============================================================
# 3. Grant IAM roles to service account
# ============================================================
echo "--- Granting IAM roles ---"
ROLES=(
    "roles/dialogflow.admin"
    "roles/storage.admin"
    "roles/serviceusage.serviceUsageAdmin"
)

for ROLE in "${ROLES[@]}"; do
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="${ROLE}" \
        --condition=None \
        --quiet
    echo "  Granted: ${ROLE}"
done

# ============================================================
# 4. Setup Workload Identity Federation (for GitHub Actions)
# ============================================================
echo "--- Setting up Workload Identity Federation ---"

# Create Workload Identity Pool
if gcloud iam workload-identity-pools describe "${WIF_POOL_NAME}" \
    --location="global" --project="${PROJECT_ID}" &>/dev/null; then
    echo "Workload Identity Pool already exists."
else
    gcloud iam workload-identity-pools create "${WIF_POOL_NAME}" \
        --location="global" \
        --display-name="GitHub Actions Pool" \
        --project="${PROJECT_ID}"
    echo "Workload Identity Pool created."
fi

# Create Workload Identity Provider
if gcloud iam workload-identity-pools providers describe "${WIF_PROVIDER_NAME}" \
    --workload-identity-pool="${WIF_POOL_NAME}" \
    --location="global" --project="${PROJECT_ID}" &>/dev/null; then
    echo "Workload Identity Provider already exists."
else
    gcloud iam workload-identity-pools providers create-oidc "${WIF_PROVIDER_NAME}" \
        --workload-identity-pool="${WIF_POOL_NAME}" \
        --location="global" \
        --issuer-uri="https://token.actions.githubusercontent.com" \
        --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
        --attribute-condition="assertion.repository=='${GITHUB_REPO}'" \
        --project="${PROJECT_ID}"
    echo "Workload Identity Provider created."
fi

# Allow GitHub Actions to impersonate the service account
WIF_POOL_ID=$(gcloud iam workload-identity-pools describe "${WIF_POOL_NAME}" \
    --location="global" --project="${PROJECT_ID}" --format="value(name)")

gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/${WIF_POOL_ID}/attribute.repository/${GITHUB_REPO}" \
    --project="${PROJECT_ID}" \
    --quiet

echo "Workload Identity Federation configured."

# ============================================================
# 5. Create GCS bucket for agent exports/backups
# ============================================================
echo "--- Creating GCS bucket ---"
BUCKET_NAME="${PROJECT_ID}-agent-exports"
if gsutil ls -b "gs://${BUCKET_NAME}" &>/dev/null; then
    echo "Bucket already exists: gs://${BUCKET_NAME}"
else
    gsutil mb -p "${PROJECT_ID}" -l "${REGION}" "gs://${BUCKET_NAME}"
    gsutil versioning set on "gs://${BUCKET_NAME}"
    echo "Bucket created: gs://${BUCKET_NAME}"
fi

# ============================================================
# 6. Print configuration for GitHub Secrets
# ============================================================
WIF_PROVIDER_FULL=$(gcloud iam workload-identity-pools providers describe "${WIF_PROVIDER_NAME}" \
    --workload-identity-pool="${WIF_POOL_NAME}" \
    --location="global" --project="${PROJECT_ID}" --format="value(name)")

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "Add these GitHub repository secrets:"
echo "  GCP_PROJECT_ID=${PROJECT_ID}"
echo "  GCP_SERVICE_ACCOUNT=${SA_EMAIL}"
echo "  GCP_WORKLOAD_IDENTITY_PROVIDER=${WIF_PROVIDER_FULL}"
echo "  GCS_BACKUP_BUCKET=${BUCKET_NAME}"
echo ""
echo "For each environment (staging/production), create GitHub environments"
echo "with their own project IDs and app IDs as environment secrets."
