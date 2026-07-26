#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_DIR="${1:-../termproof-plugin-template}"
if [ ! -d "${TARGET_DIR}/.git" ]; then
  echo "Target ${TARGET_DIR} is not a git repo. Run bootstrap.sh first." >&2
  exit 1
fi
echo "Syncing ${TEMPLATE_DIR} -> ${TARGET_DIR}"
rsync -av --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude 'dist' \
  --exclude 'build' \
  --exclude '*.egg-info' \
  --exclude '.termproof' \
  "${TEMPLATE_DIR}/" "${TARGET_DIR}/"
echo "Sync complete. Review changes:"
echo "  cd ${TARGET_DIR} && git status && git diff"
