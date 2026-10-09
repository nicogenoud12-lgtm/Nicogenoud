#!/usr/bin/env bash
# Crea una instancia separada del dashboard para otra cuenta de IOL
# (otra persona, otra base de datos, otro login), al lado de la principal.
#
# Uso:  ./scripts/nueva-instancia.sh <nombre> <puerto> [usuario]
# Ej.:  ./scripts/nueva-instancia.sh papa 8086
#
# Queda en ../Nicogenoud-<nombre>, apuntando al mismo repo (se actualiza con
# git pull como la principal) y con su propio data/app.db y backend/.env.
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Uso: $0 <nombre> <puerto> [usuario]" >&2
  echo "Ej.: $0 papa 8086" >&2
  exit 1
fi

NOMBRE="$1"
PUERTO="$2"
USUARIO="${3:-$NOMBRE}"

if ! [[ "$NOMBRE" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "El nombre sólo puede tener minúsculas, números y guiones." >&2
  exit 1
fi
if ! [[ "$PUERTO" =~ ^[0-9]+$ ]]; then
  echo "El puerto tiene que ser un número (ej. 8086)." >&2
  exit 1
fi

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DESTINO="$(dirname "$REPO")/$(basename "$REPO")-$NOMBRE"

if [ -e "$DESTINO" ]; then
  echo "Ya existe $DESTINO — no toco nada." >&2
  exit 1
fi
if (ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null) | grep -q ":$PUERTO "; then
  echo "El puerto $PUERTO ya está en uso. Elegí otro." >&2
  exit 1
fi

REMOTO="$(git -C "$REPO" remote get-url origin)"

echo "Clonando en $DESTINO ..."
git clone --quiet --branch main "$REPO" "$DESTINO"
git -C "$DESTINO" remote set-url origin "$REMOTO"

# Secretos propios de esta instancia (no se comparten con la principal).
JWT_SECRET="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
FERNET_KEY="$(head -c 32 /dev/urandom | base64 | tr '+/' '-_' | tr -d '\n')"
PASSWORD="$(head -c 12 /dev/urandom | base64 | tr -d '+/=\n')"

IP_LAN="$(hostname -I 2>/dev/null | awk '{print $1}')"
CORS="http://localhost:$PUERTO"
[ -n "$IP_LAN" ] && CORS="$CORS,http://$IP_LAN:$PUERTO"

sed \
  -e "s|^CORS_ORIGINS=.*|CORS_ORIGINS=$CORS|" \
  -e "s|^JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|" \
  -e "s|^FERNET_KEY=.*|FERNET_KEY=$FERNET_KEY|" \
  -e "s|^ADMIN_USERNAME=.*|ADMIN_USERNAME=$USUARIO|" \
  -e "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=$PASSWORD|" \
  "$DESTINO/backend/.env.example" > "$DESTINO/backend/.env"
chmod 600 "$DESTINO/backend/.env"

# Puerto del frontend (docker compose lee este .env de la raíz).
echo "FRONTEND_PORT=$PUERTO" > "$DESTINO/.env"

echo "Levantando contenedores ..."
(cd "$DESTINO" && docker compose up -d --build)

URL="http://${IP_LAN:-localhost}:$PUERTO"
cat <<EOF

Listo. Instancia "$NOMBRE" corriendo en $URL

  Usuario:     $USUARIO
  Contraseña:  $PASSWORD

Guardá la contraseña (también queda en $DESTINO/backend/.env).
Primer uso: entrar, Ajustes → Conexión IOL con la cuenta de IOL de esta persona,
después Operaciones → Sincronizar.
EOF
