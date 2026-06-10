#!/usr/bin/env bash
#
# One-command setup for the Daily Brief Agent (macOS / Linux).
#
# What it does (idempotent, safe to re-run):
#   1. Creates a local virtual environment (.venv) using uv if available, else python -m venv.
#   2. Installs the package in editable mode with dev dependencies.
#   3. Copies .env.example -> .env if .env is missing (defaults need no secrets).
#   4. Initializes the SQLite database (daily-brief init-db).
#   5. Prints the next steps.
#
# Usage:
#   ./scripts/setup.sh
#
set -euo pipefail

# Resolve repo root (parent of this script's directory) and run from there.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

VENV_DIR=".venv"
PY_MIN_MAJOR=3
PY_MIN_MINOR=11

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m!! \033[0m %s\n' "$*"; }

have() { command -v "$1" >/dev/null 2>&1; }

# Pick an interpreter that satisfies the >=3.11 requirement (for the venv fallback path).
find_python() {
  local candidate
  for candidate in python3.13 python3.12 python3.11 python3 python; do
    if have "${candidate}"; then
      if "${candidate}" -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (${PY_MIN_MAJOR}, ${PY_MIN_MINOR}) else 1)" 2>/dev/null; then
        echo "${candidate}"
        return 0
      fi
    fi
  done
  return 1
}

if have uv; then
  info "Using uv ($(uv --version))"
  # uv manages/downloads a compatible Python automatically.
  uv venv --allow-existing --python ">=${PY_MIN_MAJOR}.${PY_MIN_MINOR}" "${VENV_DIR}"
  uv pip install --python "${VENV_DIR}" -e ".[dev]"
  PYTHON="${VENV_DIR}/bin/python"
else
  warn "uv not found; falling back to python -m venv + pip."
  if ! PYBIN="$(find_python)"; then
    warn "Could not find Python >= ${PY_MIN_MAJOR}.${PY_MIN_MINOR}."
    warn "Install Python 3.11+ (https://www.python.org/downloads/) or uv (https://docs.astral.sh/uv/) and re-run."
    exit 1
  fi
  info "Using ${PYBIN} ($("${PYBIN}" --version 2>&1))"
  if [ ! -d "${VENV_DIR}" ]; then
    "${PYBIN}" -m venv "${VENV_DIR}"
  fi
  PYTHON="${VENV_DIR}/bin/python"
  "${PYTHON}" -m pip install --upgrade pip
  "${PYTHON}" -m pip install -e ".[dev]"
fi

if [ ! -f .env ]; then
  info "Creating .env from .env.example (safe console defaults, no secrets required)."
  cp .env.example .env
else
  info ".env already exists; leaving it untouched."
fi

info "Initializing database."
"${PYTHON}" -m daily_brief.cli init-db

cat <<EOF

$(printf '\033[1;32m')Setup complete.$(printf '\033[0m')

Activate the environment:
  source ${VENV_DIR}/bin/activate

Then try the zero-config demo (writes a preview to var/outbox/):
  daily-brief dry-run
  daily-brief preview-email

Or without activating:
  ${VENV_DIR}/bin/daily-brief dry-run

Other useful commands:
  daily-brief doctor        # readiness checks
  daily-brief serve         # web dashboard at http://127.0.0.1:8000
  daily-brief list-runs     # recent run history

Edit .env to enable live sources or a real delivery channel.
EOF
