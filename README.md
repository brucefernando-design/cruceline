# CruceLine — TMS Nacional & Transfronterizo México ⇄ EE.UU.

**CruceLine** es un sistema integral de gestión de transporte (TMS) multi-empresa diseñado para líneas de autotransporte de carga que operan fletes nacionales en México, cruces fronterizos transfer y viajes internacionales hacia Estados Unidos.

---

## 🚚 Alcance Operativo y Puertos Fronterizos

- **Rutas Nacionales México:** Fletes FTL y locales entre cualquier estado de la República Mexicana.
- **Catálogo de Puertos Fronterizos México ⇄ EE.UU.:**
  - **Otay Mesa** (Tijuana, BC ⇄ San Diego, CA)
  - **Mexicali II** (Mexicali, BC ⇄ Calexico East, CA)
  - **Nogales Mariposa** (Nogales, SON ⇄ Nogales, AZ)
  - **San Jerónimo - Santa Teresa** (San Jerónimo, CHIH ⇄ Santa Teresa, NM)
  - **Juárez Zaragoza / Ysleta** (Cd. Juárez, CHIH ⇄ El Paso, TX)
  - **Camino Real / Eagle Pass II** (Piedras Negras, COAH ⇄ Eagle Pass, TX)
  - **Comercio Mundial / WTB** (Nuevo Laredo, TAMPS ⇄ Laredo, TX)
  - **Colombia Solidaridad** (Anáhuac, NL ⇄ Laredo, TX)
  - **Pharr–Reynosa** (Reynosa, TAMPS ⇄ Pharr, TX)
  - **Los Indios / Veteranos (Brownsville)** (Matamoros, TAMPS ⇄ Brownsville, TX)
  - **Acuña–Del Rio** (Cd. Acuña, COAH ⇄ Del Rio, TX)
  - Opción *Sin cruce (Nacional / Doméstico)* para rutas interiores.
- **Puertos Activos por Empresa:** Cada línea de transporte activa únicamente los cruces por donde opera desde el módulo **"Mi Empresa"**. Por ejemplo, la línea demo *Transportes del Bravo* opera exclusivamente por **Comercio Mundial (WTB)** y **Colombia Solidaridad**. El selector de viajes respeta estrictamente los puertos autorizados para cada empresa.
- **Moneda Dual:** Soporte nativo para registrar fletes y liquidaciones en **MXN** y **USD**.
- **Equipos Soportados:** Tractocamiones con caja 53', plataformas y camiones tipo rabón / 3.5 toneladas.

---

## 👥 Roles y Permisos de Acceso

1. **Dueño (`owner`):** Control total de la empresa, configuración de puertos autorizados, gestión de usuarios, reseteo de contraseñas, activación/desactivación de empleados y descarga de respaldos JSON.
2. **Despacho (`dispatch`):** Alta y asignación de órdenes de flete (con combo restringido a puertos activos de la línea), programación de citas y control de expedientes.
3. **Taller (`taller`):** Órdenes de trabajo, reparaciones mecánicas y control de costos en patio.
4. **Operador (`operador`):** Consulta enfocada exclusivamente a sus viajes y citas asignadas.
5. **Superadministrador CruceLine:** Consola maestra protegida por `CRUCELINE_SECRET` para listar todas las empresas registradas y suspender acceso de inmediato (`active=0`) ante falta de pago.

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

---

## 🔐 Cuentas y Accesos

### En Producción (`CRUCELINE_ENV=production`)
La base de datos arranca limpia sin usuarios predeterminados (`CRUCELINE_SEED=0`). Cada línea de transporte se registra desde **"Crear empresa"** y el dueño define su propia contraseña segura. El superadministrador accede mediante la clave maestra `CRUCELINE_SECRET` desde la consola de superadmin.

### Semilla de Demostración (Únicamente en Desarrollo con `CRUCELINE_SEED=1`)
Si en desarrollo local activas `CRUCELINE_SEED=1` en tu `.env`, se cargará la línea demo *Transportes del Bravo*:
- **Dueño:** `marco@delbravo.mx` (Contraseña de prueba: `Bravo2026!`)
- **Despacho:** `despacho@delbravo.mx` (Contraseña de prueba: `Despacho2026!`)
- **Taller:** `taller@delbravo.mx` (Contraseña de prueba: `Taller2026!`)
- **Operador:** `jose@delbravo.mx` (Contraseña de prueba: `Operador2026!`)

⚠️ *No uses estas contraseñas de demostración en ningún servidor de producción.*

---

## 🚀 Despliegue en Producción (VPS Compartida)

CruceLine está optimizado para convivir en servidores VPS compartidos, limitando su consumo a **256 MB de RAM** y operando en un puerto local aislado (`127.0.0.1:5055`).

Consulta la guía paso a paso de una página:
👉 **[GO-LIVE.md](GO-LIVE.md)**

---

## 💼 Esquema Comercial Sugerido para Piloto de Pago

Para comercializar como piloto de pago a las primeras 1–3 líneas de transporte:

- **Cuota de Implementación / Onboarding:** \$3,500 – \$5,000 MXN (pago único: configuración de subdominio, carga inicial de flota/operadores y capacitación).
- **Renta Mensual Piloto:** \$2,500 – \$4,000 MXN / mes por empresa (incluye usuarios ilimitados, soporte vía WhatsApp y respaldos diarios automáticos).
- **Corte por Falta de Pago:** Desde la pantalla **Superadmin**, el dueño de CruceLine puede suspender a cualquier empresa morosa (`active=0`) con un solo clic.

---

## ⚖️ Alcance Legal y Fiscal del Piloto

- **No emite timbrado oficial CFDI / Carta Porte SAT:** El módulo genera un borrador operativo interno para el operador y patio. No sustituye la emisión fiscal ante un PAC autorizado por el SAT.
- **No sustituye a la agencia aduanal:** El pedimento, DODA, validación de sellos y trámites ante CBP/ANAM siguen siendo responsabilidad del transportista y su agente aduanal.
