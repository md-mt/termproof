#!/usr/bin/env bash
# Smoke-test that a published termproof distribution installs and runs.
# Usage:
#   bash scripts/smoke-install.sh                 # installs latest `termproof` from PyPI
#   bash scripts/smoke-install.sh <version>        # installs termproof==<version>
#                                                  # a version that is actually on
#                                                  # PyPI — this said 0.2.0 for a
#                                                  # long time, which never was
#   bash scripts/smoke-install.sh "" dist/*.whl    # installs local wheel instead of PyPI
#   TERM_PROOF_SMOKE_INDEX_URL=https://test.pypi.org/simple bash scripts/smoke-install.sh --pre
#
# Exit non-zero on any failure. Safe to run in CI: uses a temporary venv and
# never touches the current environment.
set -euo pipefail

VERSION="${1:-}"
WHEEL_PATH="${2:-}"
INDEX_URL="${TERM_PROOF_SMOKE_INDEX_URL:-}"
VENV_DIR="${TERM_PROOF_SMOKE_VENV:-.smoke-install-venv}"

if [[ -n "${WHEEL_PATH}" && ! -f "${WHEEL_PATH}" ]]; then
  echo "Wheel not found: ${WHEEL_PATH}" >&2
  exit 1
fi

cleanup() {
  if [[ "${KEEP:-}" != "1" && -d "${VENV_DIR}" ]]; then
    rm -rf "${VENV_DIR}"
  fi
}
trap cleanup EXIT

echo "==> Creating isolated venv at ${VENV_DIR}"
rm -rf "${VENV_DIR}"
python3 -m venv "${VENV_DIR}"
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

PIP_ARGS=()
if [[ -n "${INDEX_URL}" ]]; then
  PIP_ARGS+=(--index-url "${INDEX_URL}" --extra-index-url https://pypi.org/simple)
fi

if [[ -n "${WHEEL_PATH}" ]]; then
  echo "==> Installing from wheel: ${WHEEL_PATH}"
  pip install "${WHEEL_PATH}"
elif [[ -n "${VERSION}" ]]; then
  echo "==> Installing termproof==${VERSION} from ${INDEX_URL:-PyPI}"
  pip install "termproof==${VERSION}" "${PIP_ARGS[@]}"
else
  echo "==> Installing latest termproof from ${INDEX_URL:-PyPI}"
  if [[ "${#PIP_ARGS[@]}" -gt 0 ]]; then
    pip install termproof "${PIP_ARGS[@]}"
  else
    pip install termproof
  fi
fi

echo "==> Verifying import and CLI"
# Must run from /tmp so Python doesn't resolve the repo-local `termproof/` package via CWD/symlink
TMP_VENV_CHECK="$(mktemp -d)"
(
  cd "${TMP_VENV_CHECK}"
  python -c "import importlib.metadata, pathlib; v=importlib.metadata.version('termproof'); import termproof; p=pathlib.Path(termproof.__file__).resolve(); assert 'site-packages' in str(p) or 'dist-packages' in str(p), f'not installed to site-packages: {p}'; print(f'termproof {v} at {p}')"
)
rm -rf "${TMP_VENV_CHECK}"

TMPDIR="$(mktemp -d)"
echo "==> Checking termproof --help from ${TMPDIR}"
(
  cd "${TMPDIR}"
  termproof --help >/dev/null
  echo "termproof --help: ok"
  python -c "import termproof; print('import termproof: ok')"
)
rm -rf "${TMPDIR}"

echo "==> Smoke install passed"
