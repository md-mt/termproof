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

# --- Guard: target must not exist or be empty --------------------------------
if [ -e "${TARGET_DIR}" ]; then
  if [ -d "${TARGET_DIR}/.git" ]; then
    echo "Target dir already a git repo: ${TARGET_DIR}" >&2
    echo "Use sync.sh for updates. Aborting bootstrap." >&2
    exit 1
  fi
  if [ -d "${TARGET_DIR}" ] && [ "$(ls -A "${TARGET_DIR}" 2>/dev/null)" ]; then
    echo "Target directory ${TARGET_DIR} exists and is not empty." >&2
    echo "Refusing to overwrite. Remove or empty it first." >&2
    exit 1
  fi
fi

mkdir -p "${TARGET_DIR}"

# --- Copy without suppressing errors -----------------------------------------
cp -R "${TEMPLATE_DIR}/." "${TARGET_DIR}/"

# --- Verify the copy produced expected files ---------------------------------
REQUIRED_FILES=(
  "README.md"
  "pyproject.toml"
  "src/termproof_my_plugin/__init__.py"
  "tests/test_config_wiring.py"
)
MISSING=0
for f in "${REQUIRED_FILES[@]}"; do
  if [ ! -f "${TARGET_DIR}/${f}" ]; then
    echo "ERROR: expected file missing after copy: ${f}" >&2
    MISSING=1
  fi
done
if [ "${MISSING}" -ne 0 ]; then
  echo "Bootstrap copy incomplete — aborting." >&2
  exit 1
fi

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
