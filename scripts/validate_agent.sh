#!/usr/bin/env bash
# Validate an exported agent's configuration.

set -euo pipefail

AGENT_DIR="${1:-agents/exported}"
STRICT="${2:-}"

echo "Validating agent at ${AGENT_DIR}..."

FLAGS=""
if [ "${STRICT}" = "--strict" ] || [ "${STRICT}" = "strict" ]; then
    FLAGS="--strict"
fi

python -m src.cli validate-agent \
    --agent-dir="${AGENT_DIR}" \
    ${FLAGS}
