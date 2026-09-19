#!/bin/bash
# Instala CruceLine en /opt/cruceline SIN tocar otros sitios.
# Uso: sudo bash deploy/install-isolated.sh
set -e
APP=/opt/cruceline
if [ "$(id -u)" -ne 0 ]; then
  echo "Corre con sudo"
  exit 1
fi

id cruceline >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin cruceline
mkdir -p "$APP/data" "$APP/backups"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
rsync -a --exclude '.venv' --exclude 'data/*.db' "$SCRIPT_DIR/" "$APP/"
python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"
if [ ! -f "$APP/.env" ]; then
  SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  cat > "$APP/.env" <<EOF
CRUCELINE_SECRET=$SECRET
CRUCELINE_HTTPS=1
PORT=5055
EOF
fi
chown -R cruceline:cruceline "$APP"
chmod +x "$APP/deploy/backup.sh"
cp "$APP/deploy/cruceline.service" /etc/systemd/system/cruceline.service
systemctl daemon-reload
systemctl enable --now cruceline
echo "CruceLine quedó en 127.0.0.1:5055"
echo "Ahora agrega deploy/nginx-cruceline.conf como SITIO NUEVO y apunta un subdominio."
echo "No edites el nginx.conf de tus otros proyectos; solo un archivo extra en sites-available."
