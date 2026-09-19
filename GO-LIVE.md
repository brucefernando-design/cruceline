# CruceLine — Guía de Despliegue Rápido (Go-Live en 5 Minutos)

Esta guía permite instalar CruceLine en tu VPS **sin interferir con ningún otro proyecto, contenedor o sitio web ya activo**.

---

## Reglas de Convivencia en VPS

- **Puerto interno:** `127.0.0.1:5055` (nunca expuesto directamente a internet).
- **Consumo de recursos:** Limitado estrictamente a 256 MB de RAM y 0.5 CPU.
- **Nginx:** Se agrega **únicamente** un archivo nuevo en `/etc/nginx/sites-available/`. No edites el `nginx.conf` principal ni los sitios existentes.

---

## Opción A — Despliegue con Docker Compose (Recomendada)

### 1. Clonar o subir a la VPS
```bash
sudo mkdir -p /opt/cruceline && cd /opt/cruceline
# Sube el contenido del repositorio a /opt/cruceline
```

### 2. Configurar Variables de Entorno
```bash
cp .env.example .env
# Generar clave secreta segura
SECRET=$(openssl rand -hex 32)
sed -i "s/cambia-esta-clave-secreta-larga-en-produccion-123456789/$SECRET/" .env
sed -i "s/CRUCELINE_ENV=development/CRUCELINE_ENV=production/" .env
sed -i "s/CRUCELINE_HTTPS=0/CRUCELINE_HTTPS=1/" .env
sed -i "s/CRUCELINE_SEED=1/CRUCELINE_SEED=0/" .env
```

### 3. Levantar Contenedor
```bash
docker compose up -d --build
```

### 4. Verificar Salud del Servicio
```bash
curl http://127.0.0.1:5055/api/health
# Debe responder: {"database":"ok","status":"ok","version":"1.0.0-pilot",...}
```

---

## Opción B — Despliegue Nativo con systemd y venv

```bash
cd /opt/cruceline
sudo bash deploy/install-isolated.sh
```

---

## Configurar Dominio y HTTPS (Nginx + Certbot)

### 1. Crear registro DNS
En tu panel de DNS (Cloudflare, Namecheap, GoDaddy, etc.):
- Tipo: `A`
- Nombre: `tms` (o tu subdominio deseado)
- Valor: `<IP_PUBLICA_DE_TU_VPS>`

### 2. Agregar el sitio en Nginx
```bash
sudo cp deploy/nginx-cruceline.conf /etc/nginx/sites-available/cruceline
# Reemplaza 'app.tudominio.com' por tu subdominio real:
sudo sed -i 's/app.tudominio.com/tms.tudominio.com/g' /etc/nginx/sites-available/cruceline

# Habilitar sitio
sudo ln -s /etc/nginx/sites-available/cruceline /etc/nginx/sites-enabled/cruceline

# Validar que no haya errores de sintaxis en Nginx
sudo nginx -t

# Si la prueba es exitosa, recargar Nginx
sudo systemctl reload nginx
```

### 3. Obtener Certificado SSL Gratuito
```bash
sudo certbot --nginx -d tms.tudominio.com
```

---

## Después del primer deploy

- **Poner `CRUCELINE_INVITE_CODE` en `.env`:**
  - Para proteger el alta pública en internet, define la variable `CRUCELINE_INVITE_CODE` en `/opt/cruceline/.env` (puedes generar uno seguro con `openssl rand -hex 8`).
  - **Alta pública:** Cualquier registro desde la pantalla de inicio ("Crear empresa") o vía `POST /api/auth/register` requiere obligatoriamente ingresar este código; de lo contrario el servidor responde `403 Forbidden`.
  - **Superadmin:** Puede crear empresas directamente sin código de invitación a través del endpoint `POST /api/admin/companies` o desde la consola de Superadmin.
- **Backup Docker y Cron Automatizado:**
  - El script `deploy/backup.sh` detecta si el contenedor `cruceline` está activo y realiza un respaldo atómico vía SQLite dentro del volumen de Docker, conservando hasta un máximo de 14 copias históricas.
  - Configura la ejecución periódica en el crontab del host (`sudo crontab -e`):
    ```cron
    15 3 * * * /opt/cruceline/deploy/backup.sh >/dev/null 2>&1
    ```

---

## Primer Acceso y Creación de Empresa Piloto

1. Ingresa a `https://tms.tudominio.com`.
2. Haz clic en **"Crear empresa"** e ingresa el `CRUCELINE_INVITE_CODE` configurado.
3. Registra el nombre de la línea transportista, nombre del dueño y contraseña segura.
4. Desde el módulo **"Usuarios"**, el dueño podrá dar de alta a sus despachadores, mecánicos de taller y operadores.
5. ¡Listo para operar fletes nacionales e internacionales!

