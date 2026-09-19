#!/bin/bash
set -e

cd /opt/cruceline

# Traer últimos cambios de main
git pull origin main

# Si no existe .env, crearlo desde .env.example
if [ ! -f .env ]; then
  cp .env.example .env
fi

# Asegurar variables de producción
if grep -q '^CRUCELINE_ENV=' .env; then
  sed -i 's/^CRUCELINE_ENV=.*/CRUCELINE_ENV=production/' .env
else
  echo 'CRUCELINE_ENV=production' >> .env
fi

if grep -q '^CRUCELINE_SEED=' .env; then
  sed -i 's/^CRUCELINE_SEED=.*/CRUCELINE_SEED=0/' .env
else
  echo 'CRUCELINE_SEED=0' >> .env
fi

if grep -q '^CRUCELINE_HTTPS=' .env; then
  sed -i 's/^CRUCELINE_HTTPS=.*/CRUCELINE_HTTPS=1/' .env
else
  echo 'CRUCELINE_HTTPS=1' >> .env
fi

# Si no existe CRUCELINE_INVITE_CODE o está vacío, generar uno seguro
if ! grep -q '^CRUCELINE_INVITE_CODE=' .env || [ -z "$(grep '^CRUCELINE_INVITE_CODE=' .env | cut -d'=' -f2-)" ]; then
  NEW_INVITE=$(openssl rand -hex 8)
  if grep -q '^CRUCELINE_INVITE_CODE=' .env; then
    sed -i "s/^CRUCELINE_INVITE_CODE=.*/CRUCELINE_INVITE_CODE=${NEW_INVITE}/" .env
  else
    echo "CRUCELINE_INVITE_CODE=${NEW_INVITE}" >> .env
  fi
fi

# Reconstruir y levantar contenedor
docker compose up -d --build
sleep 2

# Verificar salud
echo "Healthcheck:"
curl -s http://127.0.0.1:5055/api/health
echo ""

# Ejecutar respaldo atómico
bash deploy/backup.sh

# Listar respaldos
docker exec cruceline ls -l /backups || ls -l backups
