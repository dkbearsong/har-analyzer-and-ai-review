#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"
REQ_FILE="$PROJECT_ROOT/requirements.txt"

echo "==> Har analyzer and AI reviewer: Installer"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Error: Python 3 is required but not found in PATH." >&2
  exit 1
fi

echo "==> Using Python: $($PY -V)"

if [ ! -d "$VENV_DIR" ]; then
  echo "==> Creating virtual environment at $VENV_DIR"
  $PY -m venv "$VENV_DIR"
else
  echo "==> Virtual environment already exists at $VENV_DIR"
fi

echo "==> Activating virtual environment"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "==> Upgrading pip/setuptools/wheel"
python -m pip install --upgrade pip setuptools wheel

if [ -f "$REQ_FILE" ]; then
  echo "==> Installing Python dependencies from $REQ_FILE"
  pip install -r "$REQ_FILE"
else
  echo "Warning: requirements.txt not found at $REQ_FILE"
  exit 1
fi

echo "==> Creating .env if missing and documenting required variables"
ENV_FILE="$PROJECT_ROOT/.env"
if [ ! -f "$ENV_FILE" ]; then
  cat > "$ENV_FILE" <<'EOF'
# Har analyzer and AI reviewer configuration
# Required:
# GEMINI_API_KEY=your_api_token
EOF
  echo "    Wrote template .env to $ENV_FILE"
else
  echo "    .env already exists at $ENV_FILE (skipping)"
fi

echo "==> Done. To start using the environment:"
echo "    source .venv/bin/activate"
echo "    # edit .env to include GEMINI_API_KEY"
echo ""
echo "To run the har analyzer and AI reviewer:"
echo "    python -m har_analyzer.py"