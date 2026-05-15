#!/bin/sh
set -e

mkdir -p /data

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

echo "[entrypoint] seed"
python -m app.seed

echo "[entrypoint] starting uvicorn"
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --proxy-headers \
  --forwarded-allow-ips="*"
