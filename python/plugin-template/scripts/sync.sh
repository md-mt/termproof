#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false
for arg in "$@"; do
  case "${arg}" in
    --dry-run) DRY_RUN=true ; shift ;;
    *) break ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_DIR="${1:-../termproof-plugin-template}"

if [ ! -d "${TARGET_DIR}/.git" ]; then
  echo "Target ${TARGET_DIR} is not a git repo. Run bootstrap.sh first." >&2
  exit 1
fi

# --- Guard: refuse destructive sync when target worktree is dirty -------------
CLEAN_CHECK=$(cd "${TARGET_DIR}" && git status --porcelain 2>/dev/null || true)
if [ -n "${CLEAN_CHECK}" ]; then
  echo "Target worktree is dirty. Commit or stash changes before syncing:" >&2
  echo "${CLEAN_CHECK}" >&2
  exit 1
fi

echo "Syncing ${TEMPLATE_DIR} -> ${TARGET_DIR}"
if [ "${DRY_RUN}" = true ]; then
  echo "[DRY RUN — no changes will be made]"
fi

RSYNC_FLAGS="-av"
if [ "${DRY_RUN}" = true ]; then
  RSYNC_FLAGS="${RSYNC_FLAGS}n"
else
  RSYNC_FLAGS="${RSYNC_FLAGS} --delete"
  echo "WARNING: --delete is active — files missing from source will be removed from target."
fi

rsync ${RSYNC_FLAGS} \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude 'dist' \
  --exclude 'build' \
  --exclude '*.egg-info' \
  --exclude '.termproof' \
  "${TEMPLATE_DIR}/" "${TARGET_DIR}/"

if [ "${DRY_RUN}" = false ]; then
  echo "Sync complete. Review changes:"
  echo "  cd ${TARGET_DIR} && git status && git diff"
  echo ""
  echo "To commit:"
  echo "  cd ${TARGET_DIR}"
  echo "  git add -A"
  echo "  git diff --cached   # review what will be committed"
  echo "  git commit -m \"Sync template from termproof@\$(git -C \"${TEMPLATE_DIR}\" rev-parse --short HEAD)\""
  echo "  git push"
fi
