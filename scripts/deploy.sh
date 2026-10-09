#!/usr/bin/env bash
# Actualiza y rebuildea la instancia principal y todas las creadas con
# nueva-instancia.sh (carpetas hermanas Nicogenoud-*).
#
# Uso:  ./scripts/deploy.sh [servicios...]
# Ej.:  ./scripts/deploy.sh                    (backend y frontend)
#       ./scripts/deploy.sh backend            (sólo backend)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SERVICIOS=("$@")
[ ${#SERVICIOS[@]} -eq 0 ] && SERVICIOS=(backend frontend)

# El git pull de la principal va primero para que este script ya esté al día.
for DIR in "$REPO" "$REPO"-*/; do
  DIR="${DIR%/}"
  [ -f "$DIR/docker-compose.yml" ] || continue
  echo "== $(basename "$DIR")"
  git -C "$DIR" pull --ff-only
  (cd "$DIR" && docker compose up -d --build "${SERVICIOS[@]}")
done
