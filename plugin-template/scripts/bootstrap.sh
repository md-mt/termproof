#!/usr/bin/env bash
set -euo pipefail
if [ $# -lt 1 ]; then
  echo "Usage: $0 <github_repo_or_local_dir> [local_clone_dir]" >&2
  echo "Example: $0 md-mt/termproof-plugin-template" >&2
  exit 1
fi
TARGET_REPO="$1"
TARGET_DIR="${2:-../termproof-plugin-template}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
echo "Template source: ${TEMPLATE_DIR}"
echo "Target repo: ${TARGET_REPO}"
echo "Target local dir: ${TARGET_DIR}"
if [ -d "${TARGET_DIR}/.git" ]; then
  echo "Target dir already a git repo: ${TARGET_DIR}"
  echo "Use sync.sh for updates. Aborting bootstrap."
  exit 1
fi
mkdir -p "${TARGET_DIR}"
cp -R "${TEMPLATE_DIR}/." "${TARGET_DIR}/" 2>/dev/null || true
echo "Copied template to ${TARGET_DIR}"
echo ""
echo "Next steps (human gate):"
echo "  1. cd ${TARGET_DIR}"
echo "  2. git init"
echo "  3. git remote add origin https://github.com/${TARGET_REPO}.git"
echo "  4. git add ."
echo "  5. git commit -m 'Initial commit: TermProof plugin template'"
echo "  6. git branch -M main && git push -u origin main"
echo "  7. In GitHub: enable Template repository checkbox + branch protection"
