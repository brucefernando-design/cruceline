# CruceLine — TMS Nacional & Transfronterizo México ⇄ EE.UU.

**CruceLine** es un sistema integral de gestión de transporte (TMS) multi-empresa diseñado para líneas de autotransporte de carga que operan fletes nacionales en México, cruces fronterizos transfer y viajes internacionales puerta a puerta hacia Estados Unidos.

---

## 🚚 Alcance Operativo

- **Rutas Nacionales México:** Cobertura de fletes FTL y consolidados entre cualquier estado de la República Mexicana (ej. Monterrey, Guadalajara, CDMX, Bajío).
- **Cruces Fronterizos / Transfer:** Puertos de entrada clave México ⇄ EE.UU.:
  - Puente Comercio Mundial / World Trade Bridge (Nuevo Laredo, TAMPS ⇄ Laredo, TX)
  - Puente Colombia Solidaridad (Anáhuac, NL ⇄ Laredo, TX)
  - Puente Internacional Pharr–Reynosa (Reynosa, TAMPS ⇄ Pharr, TX)
  - Puente Zaragoza / Ysleta (Cd. Juárez, CHIH ⇄ El Paso, TX)
  - Garita Otay Mesa (Tijuana, BC ⇄ San Diego, CA)
  - Rutas sin cruce (nacionales o domésticas).
- **Rutas Internacionales & EE.UU.:** Viajes de exportación/importación y recorridos domésticos en territorio estadounidense en dólares (USD).
- **Moneda Dual:** Soporte nativo para registrar fletes y liquidaciones en **MXN** y **USD**.
- **Equipos Soportados:** Tractocamiones con caja seca o refrigerada de 53', plataformas y camiones tipo rabón / 3.5 toneladas.

---

## 👥 Roles y Permisos de Acceso

1. **Dueño (`owner`):** Control total de la empresa, configuración de bases y patios, creación y gestión de usuarios, reseteo de contraseñas, activación/desactivación de empleados y descarga de respaldos JSON.
2. **Despacho (`dispatch`):** Alta y asignación de viajes, programación de citas, control de expedientes y checklist documental, registro de fletes y anticipos.
3. **Taller (`taller`):** Órdenes de trabajo, reparaciones mecánicas, seguimiento de fechas estimadas de entrega (ETA) y costos de mantenimiento en patio.
4. **Operador (`operador`):** Acceso enfocado a consultar únicamente los viajes y citas en los que se encuentra asignado, así como verificación de documentos en ruta.

---

## ⚙️ Cómo Correr en Desarrollo Local

1. Asegúrate de tener Python 3.10+ instalado.
2. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Copia el archivo de variables de entorno:
   ```bash
   cp .env.example .env
   ```
4. Inicia el servidor:
   ```bash
   python server.py
   ```
5. Abre en tu navegador: [http://127.0.0.1:5055](http://127.0.0.1:5055)

### Credenciales de Demostración (Solo Desarrollo)

| Rol | Correo | Contraseña |
|---|---|---|
| Dueño | `marco@delbravo.mx` | `Bravo2026!` |
| Despacho | `despacho@delbravo.mx` | `Despacho2026!` |
| Taller | `taller@delbravo.mx` | `Taller2026!` |
| Operador | `jose@delbravo.mx` | `Operador2026!` |

> También puedes dar de alta una nueva empresa desde el botón **"Crear empresa"**; esa línea contará con una base de datos 100% aislada.

---

## 🚀 Despliegue en Producción (VPS Compartida)

CruceLine está optimizado para convivir en servidores VPS que ya ejecutan otros proyectos web, limitando su consumo a **256 MB de RAM** y operando en un puerto local aislado (`127.0.0.1:5055`).

Consulta la guía paso a paso de una página:
👉 **[GO-LIVE.md](GO-LIVE.md)**

---

## 💼 Esquema Comercial Sugerido para Piloto de Pago

Para comercializar como piloto de pago a las primeras 1–3 líneas de transporte:

- **Cuota de Implementación / Onboarding:** \$3,500 – \$5,000 MXN (pago único: configuración de subdominio, carga inicial de tractores, choferes y capacitación rápida a despacho).
- **Renta Mensual Piloto:** \$2,500 – \$4,000 MXN / mes por empresa (incluye usuarios ilimitados, soporte vía WhatsApp y respaldos diarios automáticos).
- **Control de Acceso:** El dueño de CruceLine puede suspender temporalmente el acceso de cualquier empresa mediante la bandera `active=0` ante falta de pago.

---

## ⚖️ Alcance Legal y Fiscal del Piloto

- **No emite timbrado oficial CFDI / Carta Porte SAT:** El módulo de Carta Porte genera un borrador operativo interno para el operador y patio. No sustituye la emisión fiscal ante un PAC autorizado por el SAT.
- **No sustituye a la agencia aduanal:** El pedimento, DODA, validación de sellos y trámites ante CBP/ANAM siguen siendo responsabilidad del transportista y su agente aduanal.
