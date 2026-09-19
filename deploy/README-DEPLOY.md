# Subir CruceLine a una VPS sin tocar otros proyectos

5.6 GB de RAM libre y 90 GB de disco alcanzan. CruceLine usa ~150–250 MB y menos de 1 GB en disco.

## Regla

No lo pongas en la carpeta de otro sitio. No edites el `nginx.conf` que ya sirve tus proyectos.  
Usa **subdominio nuevo** + **puerto 5055 solo en localhost** + **carpeta /opt/cruceline**.

Ejemplo: `app.tudominio.com` → `127.0.0.1:5055`

## Opción A — Docker (la más limpia)

Si ya tienes Docker:

```bash
cd /opt
mkdir cruceline && cd cruceline
# sube aquí el código
cp .env.example .env
nano .env   # cambia CRUCELINE_SECRET
docker compose up -d --build
```

Eso crea un contenedor llamado `cruceline`, limitado a **256 MB RAM y medio CPU**.  
El puerto 5055 queda en `127.0.0.1`, no abierto al mundo. Tus otros contenedores no se tocan.

## Opción B — systemd aislado

```bash
sudo bash deploy/install-isolated.sh
```

Crea usuario `cruceline`, venv propio, servicio propio y tope de 256 MB.

## Nginx: solo un sitio extra

Copia `deploy/nginx-cruceline.conf` a `/etc/nginx/sites-available/cruceline`  
Cambia `app.tudominio.com`  
Activa:

```bash
sudo ln -s /etc/nginx/sites-available/cruceline /etc/nginx/sites-enabled/cruceline
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d app.tudominio.com
```

`nginx -t` tiene que pasar. Si falla, **no hagas reload**. Tus otros sitios siguen con sus archivos.

Si usas Apache o Caddy, la idea es la misma: un virtual host nuevo, no reescribir el default.

## DNS

En tu dominio crea un registro A:

`app` → IP de la VPS

No muevas el registro de tus sitios actuales.

## Lo que NO debes hacer

- Instalar encima de `/var/www/html` de otro proyecto
- Cambiar el `root` de un site que ya funciona
- Abrir el puerto 5055 a internet (`0.0.0.0`). Debe ser `127.0.0.1`
- Reutilizar la base de datos o el `.env` de otra app
- Correr `pip install` en el Python del sistema

## Recursos

| Recurso | CruceLine | Tu VPS libre | ¿Pega? |
|---|---|---|---|
| RAM | 256 MB tope | 5.6 GB | No |
| Disco | < 1 GB + backups | 90 GB | No |
| CPU | 50% de 1 núcleo | el resto sigue para ti | No |
| Puerto público | 80/443 del subdominio | los demás server_name intactos | No |

## Después de subir

1. Entra a `https://app.tudominio.com`
2. Cambia las contraseñas demo
3. Crea tu empresa real
4. Cron diario solo de esta base:

```
15 3 * * * /opt/cruceline/deploy/backup.sh
```
