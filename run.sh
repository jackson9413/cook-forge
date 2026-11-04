#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PORT="$PORT"
if [ -z "$PORT" ]; then PORT=5057; fi
export PORT

if ! python3 -c "import flask" >/dev/null 2>&1; then
  echo "Flask is not installed. Installing requirements..."
  python3 -m pip install -r requirements.txt
fi

echo "cook-forge -> http://127.0.0.1:$PORT"
exec python3 app.py
