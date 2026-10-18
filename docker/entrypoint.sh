#!/usr/bin/env sh
set -eu

echo "Waiting for PostgreSQL..."

python - <<'PY'
import os
import socket
import time

host = os.environ.get("DB_HOST", "db")
port = int(os.environ.get("DB_PORT", "5432"))

for _ in range(60):
    try:
        with socket.create_connection((host, port), timeout=2):
            break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit(
        f"PostgreSQL unavailable on {host}:{port}"
    )
PY

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting StockPro..."
exec "$@"
