# CruceLine — contexto para Antigravity

Producto: TMS para líneas de trailers y camiones 3.5 con base en **Nuevo Laredo, Tamaulipas** y cruces a **Laredo, TX**.

Puentes: Comercio Mundial (WTB) y Colombia Solidaridad.

## Stack

- Flask + SQLite + sesiones
- Front en `static/`
- Multi-empresa (`company_id` en todas las tablas)
- Roles: `owner`, `dispatch`, `taller`, `operador`
- Deploy aislado: Docker / systemd + Nginx en subdominio, puerto `127.0.0.1:5055`

## Qué NO está (hazlo en este orden)

1. Publicar en VPS con HTTPS (archivos en `deploy/`)
2. Quitar usuarios demo o forzar cambio de contraseña
3. Vista móvil del operador (gastos, sello, “llegué a WTB”)
4. Integración PAC Carta Porte 3.1 (hoy solo borrador)
5. Cobro de renta (Mercado Pago) y corte por falta de pago
6. Transferista: caja se queda en Laredo, tractor regresa a NL

## Cómo correr local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export CRUCELINE_DB=./data/cruceline.db
python3 server.py
```

Demo: `marco@delbravo.mx` / `Bravo2026!`

No subas `.env` ni la base `.db`.
