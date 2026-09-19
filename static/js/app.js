const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const STATUSES = ["Cotizado", "Asignado", "En ruta", "En frontera", "Entregado", "Liquidado"];
const TRIP_TYPES = [
  "Trailer transfer (Frontera)",
  "Internacional MX → USA (FTL)",
  "Internacional USA → MX (FTL)",
  "Nacional México (FTL)",
  "Doméstico USA (FTL)",
  "Rabón / 3.5 Cruce Local",
  "Rabón / 3.5 Ciudad / Nacional",
];
const CURRENCIES = ["MXN", "USD"];

let state = {
  user: null,
  units: [],
  drivers: [],
  clients: [],
  trips: [],
  appointments: [],
  money: [],
  workorders: [],
  docs: {},
  active_ports: [],
  all_ports: [],
  bridges: [],
};
let currentView = "dashboard";
let isSuperadminMode = false;

async function api(path, opts = {}) {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : opts.body,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Error de servidor");
  return data;
}

function money(n, cur = "MXN") {
  const c = cur || "MXN";
  const formatted = new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: c,
    maximumFractionDigits: 0,
  }).format(n || 0);
  return c === "USD" ? `${formatted} USD` : formatted;
}

function daysTo(dateStr) {
  if (!dateStr || dateStr === "—") return null;
  const target = new Date(dateStr + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.ceil((target - today) / 86400000);
}

function expiryBadge(dateStr) {
  const d = daysTo(dateStr);
  if (d === null) return `<span class="badge info">N/A</span>`;
  if (d < 0) return `<span class="badge bad">Vencido (${Math.abs(d)}d)</span>`;
  if (d <= 30) return `<span class="badge warn">${d} días</span>`;
  return `<span class="badge ok">${dateStr}</span>`;
}

function statusBadge(s) {
  const map = {
    Disponible: "ok",
    "En ruta": "info",
    "En frontera": "warn",
    Taller: "bad",
    "En cruce WTB": "warn",
    "Disponible patio NL": "ok",
    "En ruta a Colombia": "info",
    "En patio Laredo": "warn",
    "Documentos por vencer": "warn",
    Cotizado: "info",
    Asignado: "info",
    Entregado: "ok",
    Liquidado: "ok",
    Confirmada: "ok",
    "En proceso": "warn",
    Pendiente: "warn",
    "Por confirmar broker": "warn",
    Pagado: "ok",
    Descontar: "warn",
    "Por cobrar": "warn",
    Cobrado: "ok",
    Abierta: "warn",
    Cerrada: "ok",
    owner: "ok",
    dispatch: "info",
    taller: "warn",
    operador: "info",
    Activo: "ok",
    Inactivo: "bad",
    Activa: "ok",
    Suspendida: "bad",
  };
  return `<span class="badge ${map[s] || "info"}">${s}</span>`;
}

function can(roles) {
  return !roles || roles.includes(state.user.role);
}

async function loadApp() {
  const data = await api("/api/bootstrap");
  state = data;
  $("#auth").classList.add("hidden");
  $("#app").classList.remove("hidden");
  $("#side-company").textContent = state.user.company;
  $("#whoami").innerHTML = `<b>${state.user.name}</b><br><small class="muted">${state.user.role.toUpperCase()} · ${state.user.billing_status.toUpperCase()}</small>`;

  $$(".nav-btn").forEach((b) => {
    if (b.dataset.view === "superadmin") return;
    const roles = b.dataset.roles ? b.dataset.roles.split(",") : null;
    b.classList.toggle("hidden", !can(roles));
  });
  go(currentView || "dashboard");
}

function go(view) {
  currentView = view;
  $$(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  render();
}

const views = {
  dashboard: renderDashboard,
  flota: renderFlota,
  operadores: renderOperadores,
  clientes: renderClientes,
  viajes: renderViajes,
  citas: renderCitas,
  dinero: renderDinero,
  taller: renderTaller,
  expediente: renderExpediente,
  cartaporte: renderCartaPorte,
  puentes: renderPuentes,
  empresa: renderEmpresa,
  equipo: renderEquipo,
  terminos: renderTerminos,
  superadmin: renderSuperadmin,
};

function render() {
  $("#view").innerHTML = views[currentView] ? views[currentView]() : renderDashboard();
  bindViewEvents();
}

function renderDashboard() {
  const enCurso = state.trips.filter((t) => ["Asignado", "En ruta", "En frontera"].includes(t.estatus)).length;
  const porCobrarMXN = state.money
    .filter((m) => m.estatus === "Por cobrar" && (m.moneda || "MXN") === "MXN")
    .reduce((a, b) => a + Number(b.monto || 0), 0);
  const porCobrarUSD = state.money
    .filter((m) => m.estatus === "Por cobrar" && m.moneda === "USD")
    .reduce((a, b) => a + Number(b.monto || 0), 0);

  const alertas = [
    ...state.drivers.filter((d) => {
      const f = daysTo(d.fast);
      const m = daysTo(d.medico);
      return (f !== null && f <= 30) || (m !== null && m <= 30);
    }),
    ...state.units.filter((u) => {
      const s = daysTo(u.seguro);
      const v = daysTo(u.verif);
      return (s !== null && s <= 30) || (v !== null && v <= 30);
    }),
  ].length;
  const abiertas = state.workorders.filter((w) => w.estatus !== "Cerrada").length;

  return `
    <div class="top">
      <div>
        <h2>Tablero de Operaciones</h2>
        <p>${state.user.company} · Base: ${state.user.base} · ${state.user.patio || "Patio principal"}</p>
      </div>
    </div>
    <div class="grid kpis">
      <div class="card kpi"><span>Viajes Activos</span><strong>${enCurso}</strong><small>En ruta o frontera</small></div>
      <div class="card kpi">
        <span>Cartera por Cobrar</span>
        <strong>${money(porCobrarMXN, "MXN")}</strong>
        ${porCobrarUSD > 0 ? `<small>+ ${money(porCobrarUSD, "USD")}</small>` : `<small>Fletes confirmados</small>`}
      </div>
      <div class="card kpi"><span>Alertas de Documentos</span><strong>${alertas}</strong><small>Seguro, FAST o examen médico</small></div>
      <div class="card kpi"><span>Órdenes de Taller</span><strong>${abiertas}</strong><small>Unidades en mantenimiento</small></div>
    </div>
    <div class="card" style="margin-top:14px">
      <h3>Viajes y Fletes en Tránsito</h3>
      <table>
        <thead><tr><th>Folio</th><th>Ruta / Tipo</th><th>Cruce / Puerto</th><th>Operador / Equipo</th><th>Flete</th><th>Estatus</th></tr></thead>
        <tbody>
          ${
            state.trips.filter((t) => !["Entregado", "Liquidado"].includes(t.estatus)).map(
              (t) => `
            <tr style="cursor:pointer" data-trip="${t.folio}">
              <td><b>${t.folio}</b><div class="muted">${t.tipo}</div></td>
              <td><b>${t.origen}</b><div class="muted">→ ${t.destino}</div></td>
              <td>${t.puente || "Nacional"}</td>
              <td>${t.operador || "Sin asignar"}<div class="muted">${t.equipo || ""}</div></td>
              <td><b>${money(t.flete, t.moneda)}</b></td>
              <td>${statusBadge(t.estatus)}</td>
            </tr>`
            ).join("") || `<tr><td colspan="6" class="muted" style="text-align:center;padding:18px">Sin viajes activos actualmente</td></tr>`
          }
        </tbody>
      </table>
    </div>`;
}

function renderFlota() {
  return moduleTable(
    "Flota y Equipo",
    "Tractores, cajas 53' y camiones 3.5 registrados para fletes nacionales y cruces.",
    "add-unit",
    "Alta de unidad",
    ["Económico", "Tipo", "Placas", "Estatus", "Póliza de Seguro", "Verificación Físico-Mecánica"],
    state.units
      .map(
        (u) => `<tr>
      <td><b>${u.code}</b><div class="muted">${u.vin || ""}</div></td>
      <td>${u.tipo}</td>
      <td>${u.placas || "—"}</td>
      <td>${statusBadge(u.estatus)}</td>
      <td>${expiryBadge(u.seguro)}</td>
      <td>${expiryBadge(u.verif)}</td>
    </tr>`
      )
      .join("")
  );
}

function renderOperadores() {
  return moduleTable(
    "Operadores / Choferes",
    "Control de licencias federales, FAST / B1 para cruce a EE.UU. y aptitud médica.",
    "add-driver",
    "Alta de operador",
    ["Operador", "Licencias", "Tarjeta FAST / Visa B1", "Aptitud Médica", "Estatus"],
    state.drivers
      .map(
        (d) => `<tr>
      <td><b>${d.nombre}</b><div class="muted">ID: ${d.code}</div></td>
      <td>${d.lic || "—"}</td>
      <td>${expiryBadge(d.fast)}</td>
      <td>${expiryBadge(d.medico)}</td>
      <td>${statusBadge(d.estatus)}</td>
    </tr>`
      )
      .join("")
  );
}

function renderClientes() {
  return moduleTable(
    "Clientes y Brokers",
    "Brokers, transfer partners y dueños de carga en México y Estados Unidos.",
    "add-client",
    "Alta de cliente",
    ["Cliente", "RFC / Tax ID (EIN)", "Términos de Pago", "Rutas Frecuentes"],
    state.clients
      .map(
        (c) => `<tr>
      <td><b>${c.nombre}</b><div class="muted">${c.code}</div></td>
      <td>${c.rfc || "—"}</td>
      <td>${c.pago || "Contado"}</td>
      <td>${c.cruzes || "Nacional / Cruce"}</td>
    </tr>`
      )
      .join("")
  );
}

function moduleTable(title, sub, btnId, btnLabel, heads, body) {
  const showBtn =
    (can(["owner", "dispatch", "taller"]) && btnId === "add-unit") ||
    (can(["owner", "dispatch"]) && btnId !== "add-unit");
  return `
    <div class="top">
      <div><h2>${title}</h2><p>${sub}</p></div>
      ${showBtn ? `<button class="btn" id="${btnId}">${btnLabel}</button>` : ""}
    </div>
    <div class="card">
      <table>
        <thead><tr>${heads.map((h) => `<th>${h}</th>`).join("")}</tr></thead>
        <tbody>${body || `<tr><td colspan="${heads.length}" class="muted" style="text-align:center">Sin registros</td></tr>`}</tbody>
      </table>
    </div>`;
}

function renderViajes() {
  const groups = Object.fromEntries(STATUSES.map((s) => [s, state.trips.filter((t) => t.estatus === s)]));
  return `
    <div class="top">
      <div>
        <h2>Viajes y Fletes</h2>
        <p>Órdenes de flete nacional, transfer fronterizo e internacional.</p>
      </div>
      ${can(["owner", "dispatch"]) ? `<button class="btn" id="add-trip">Nueva orden de flete</button>` : ""}
    </div>
    <div class="pipeline">
      ${STATUSES.map(
        (s) => `
        <div class="card pipe">
          <h3>${s} (${groups[s].length})</h3>
          ${groups[s]
            .map(
              (t) => `
            <div class="trip" data-trip="${t.folio}">
              <b>${t.folio}</b>
              <div style="font-size:12px;font-weight:600">${t.origen}</div>
              <div class="muted" style="font-size:11.5px">→ ${t.destino}</div>
              <div style="margin-top:6px;display:flex;justify-content:space-between;align-items:center">
                <span class="badge currency">${t.moneda || "MXN"}</span>
                <span style="font-weight:700;font-size:12px">${money(t.flete, t.moneda)}</span>
              </div>
              <div class="muted" style="font-size:11px;margin-top:4px">${t.puente || "Nacional"}</div>
            </div>`
            )
            .join("")}
        </div>`
      ).join("")}
    </div>`;
}

function tripModal(trip) {
  // El combo respeta ESTRICTAMENTE los puertos activos de la empresa
  const activePortNames = (state.active_ports && state.active_ports.length > 0)
    ? state.active_ports.map((p) => p.name)
    : [];

  const portOptions = [...activePortNames, "Sin cruce (Nacional / Doméstico)"];

  const t = trip || {
    folio: "",
    cliente: state.clients[0]?.nombre || "",
    origen: state.user.base || "Nuevo Laredo, Tamaulipas",
    destino: "Laredo, TX",
    puente: portOptions[0],
    equipo: state.units[0]?.code || "",
    operador: state.drivers[0]?.nombre || "",
    tipo: "Trailer transfer (Frontera)",
    estatus: "Cotizado",
    flete: 0,
    moneda: "MXN",
    cita: "",
    sello: "",
  };
  return `
    <div class="modal-bg show" id="modal"><div class="modal">
      <div class="top">
        <div>
          <h2>${trip ? "Viaje " + t.folio : "Nueva Orden de Flete"}</h2>
          <p>Flete nacional o cruce fronterizo</p>
        </div>
        <button class="btn ghost" id="close-modal">Cerrar</button>
      </div>
      <form id="trip-form" class="form-grid">
        <div class="field"><label>Folio</label><input name="folio" value="${t.folio}" placeholder="Automático si se deja vacío"></div>
        <div class="field"><label>Estatus</label><select name="estatus">${STATUSES.map((s) => `<option ${s === t.estatus ? "selected" : ""}>${s}</option>`).join("")}</select></div>
        <div class="field"><label>Cliente / Broker</label><select name="cliente">${state.clients.map((c) => `<option ${c.nombre === t.cliente ? "selected" : ""}>${c.nombre}</option>`).join("")}</select></div>
        <div class="field"><label>Tipo de Flete / Modalidad</label><select name="tipo">${TRIP_TYPES.map((x) => `<option ${x === t.tipo ? "selected" : ""}>${x}</option>`).join("")}</select></div>
        <div class="field"><label>Cruce / Puerto Habilitado</label>
          <select name="puente">${portOptions.map((x) => `<option ${x === (t.puente || portOptions[0]) ? "selected" : ""}>${x}</option>`).join("")}</select>
          ${activePortNames.length === 0 ? '<small class="muted" style="color:var(--bad);display:block;margin-top:4px">⚠️ Sin puertos habilitados. Configúralos en <b>Mi Empresa & Puertos</b> o usa flete nacional.</small>' : ''}
        </div>
        <div class="field"><label>Moneda</label><select name="moneda">${CURRENCIES.map((m) => `<option ${m === (t.moneda || "MXN") ? "selected" : ""}>${m}</option>`).join("")}</select></div>
        <div class="field"><label>Origen (Ciudad, Estado o Patio)</label><input name="origen" value="${t.origen || ""}" required placeholder="Ej: Patio NL Km 8.5 / Monterrey / CDMX"></div>
        <div class="field"><label>Destino (Ciudad, Estado o Bodega)</label><input name="destino" value="${t.destino || ""}" required placeholder="Ej: Laredo TX / San Antonio / Guadalajara"></div>
        <div class="field"><label>Equipo Asignado</label><input name="equipo" value="${t.equipo || ""}" placeholder="Ej: T-12 + C-53-18"></div>
        <div class="field"><label>Operador / Chofer</label><select name="operador">${state.drivers.map((d) => `<option ${d.nombre === t.operador ? "selected" : ""}>${d.nombre}</option>`).join("")}</select></div>
        <div class="field"><label>Monto de Flete</label><input name="flete" type="number" step="any" value="${t.flete || 0}"></div>
        <div class="field"><label>Cita de Carga / Cruce / Entrega</label><input name="cita" value="${t.cita || ""}" placeholder="Fecha y hora o referencia"></div>
        <div class="field full"><label>Número de Sello / Precinto Fiscal</label><input name="sello" value="${t.sello || ""}" placeholder="Ej: CBP-889120 / SAT-0912"></div>
        <div class="full" style="margin-top:8px">
          <button class="btn" type="submit">Guardar Orden en Servidor</button>
        </div>
      </form>
    </div></div>`;
}

function renderCitas() {
  return moduleTable(
    "Citas, Andenes & Aduana",
    "Programación de cruces por puente, recintos aduanales y citas de descarga en México y EE.UU.",
    "add-appt",
    "Nueva cita",
    ["ID Cita", "Viaje Asignado", "Tipo", "Lugar / Andén", "Fecha & Hora", "Estatus"],
    state.appointments
      .map(
        (a) => `<tr>
      <td><b>${a.code}</b></td>
      <td><b>${a.viaje}</b></td>
      <td>${a.tipo}</td>
      <td>${a.lugar}</td>
      <td>${a.fecha}</td>
      <td>${statusBadge(a.estatus)}</td>
    </tr>`
      )
      .join("")
  );
}

function renderDinero() {
  const cobrarMXN = state.money
    .filter((m) => m.estatus === "Por cobrar" && (m.moneda || "MXN") === "MXN")
    .reduce((a, b) => a + Number(b.monto || 0), 0);
  const cobrarUSD = state.money
    .filter((m) => m.estatus === "Por cobrar" && m.moneda === "USD")
    .reduce((a, b) => a + Number(b.monto || 0), 0);

  return `
    <div class="top">
      <div>
        <h2>Liquidación y Cartera</h2>
        <p>Control de fletes por cobrar, anticipos de diesel, casetas y liquidaciones a operadores.</p>
      </div>
      ${can(["owner", "dispatch"]) ? `<button class="btn" id="add-money">Registrar Movimiento</button>` : ""}
    </div>
    <div class="grid two">
      <div class="card kpi"><span>Por cobrar en Moneda Nacional</span><strong>${money(cobrarMXN, "MXN")}</strong></div>
      <div class="card kpi"><span>Por cobrar en Dólares (USD)</span><strong>${money(cobrarUSD, "USD")}</strong></div>
    </div>
    <div class="card" style="margin-top:14px">
      <table>
        <thead><tr><th>Folio</th><th>Viaje</th><th>Concepto</th><th>Beneficiario / Cliente</th><th>Monto</th><th>Moneda</th><th>Estatus</th></tr></thead>
        <tbody>
          ${state.money
            .map(
              (m) => `<tr>
            <td><b>${m.code}</b></td>
            <td><b>${m.viaje || "—"}</b></td>
            <td>${m.concepto}<div class="muted">${m.tipo}</div></td>
            <td>${m.persona}</td>
            <td><b>${money(m.monto, m.moneda)}</b></td>
            <td><span class="badge currency">${m.moneda || "MXN"}</span></td>
            <td>${statusBadge(m.estatus)}</td>
          </tr>`
            )
            .join("")}
        </tbody>
      </table>
    </div>`;
}

function renderTaller() {
  return moduleTable(
    "Taller y Mantenimiento",
    "Inspecciones pre-viaje, reparaciones preventivas y órdenes de trabajo en patio.",
    "add-ot",
    "Nueva OT",
    ["Folio OT", "Unidad", "Falla / Mantenimiento", "Taller", "Costo Estimado", "ETA Salida", "Estatus"],
    state.workorders
      .map(
        (w) => `<tr>
      <td><b>${w.code}</b></td>
      <td><b>${w.unidad}</b></td>
      <td>${w.falla}</td>
      <td>${w.taller}</td>
      <td><b>${money(w.costo, "MXN")}</b></td>
      <td>${w.eta || "Por definir"}</td>
      <td>${statusBadge(w.estatus)}</td>
    </tr>`
      )
      .join("")
  );
}

function renderExpediente() {
  const folio = state.trips[0]?.folio;
  const trip = state.trips.find((t) => t.folio === (window._expFolio || folio));
  if (!trip) return `<div class="card">Crea una orden de flete primero para consultar su expediente.</div>`;
  const docs = state.docs[trip.folio] || [];
  const ready = docs.filter((d) => d.ok).length;
  return `
    <div class="top">
      <div>
        <h2>Expediente Operativo y Documentos</h2>
        <p>${trip.folio} · Ruta: ${trip.origen} → ${trip.destino} · Sello: ${trip.sello || "Pendiente"}</p>
      </div>
      <select id="exp-trip">${state.trips.map((t) => `<option ${t.folio === trip.folio ? "selected" : ""}>${t.folio}</option>`).join("")}</select>
    </div>
    <div class="card">
      <h3>Checklist de Salida y Cruce (${ready}/${docs.length || 0} completados)</h3>
      <p class="muted" style="margin-bottom:14px">Haz clic en cada requisito conforme sea verificado físicamente y en sistema.</p>
      <div class="docs">
        ${
          docs
            .map(
              (d) => `<label class="doc">
          <input type="checkbox" data-doc="${d.id}" data-folio="${trip.folio}" ${d.ok ? "checked" : ""}>
          <span>${d.name}</span>
        </label>`
            )
            .join("") || "Sin documentos asignados"
        }
      </div>
    </div>`;
}

function renderCartaPorte() {
  const trip = state.trips.find((t) => t.estatus === "En frontera") || state.trips[0];
  if (!trip) return `<div class="card">Sin órdenes de viaje activas.</div>`;
  return `
    <div class="top">
      <div>
        <h2>Borrador de Carta Porte Operativa</h2>
        <p>Generación de datos de transporte. Formato operativo interno para el operador y patio (no timbrado fiscal PAC).</p>
      </div>
      <button class="btn" id="print-cp">Imprimir Borrador</button>
    </div>
    <div class="card">
      <div class="form-grid">
        <div class="field"><label>Viaje / Folio</label><input value="${trip.folio}" readonly></div>
        <div class="field"><label>Tipo de Flete</label><input value="${trip.tipo}" readonly></div>
        <div class="field"><label>Cruce / Puerto</label><input value="${trip.puente || "Nacional"}" readonly></div>
        <div class="field"><label>Operador Asignado</label><input value="${trip.operador || "Sin asignar"}" readonly></div>
        <div class="field"><label>Origen de Carga</label><input value="${trip.origen || ""}"></div>
        <div class="field"><label>Destino de Entrega</label><input value="${trip.destino || ""}"></div>
        <div class="field"><label>Equipo y Remolque</label><input value="${trip.equipo || ""}"></div>
        <div class="field"><label>Número de Sello</label><input value="${trip.sello || ""}"></div>
        <div class="field full"><label>Declaración Operativa</label>
          <textarea>Transporte de carga amparado bajo orden ${trip.folio}. Origen: ${trip.origen} con destino a ${trip.destino}. Cruce fronterizo vía ${trip.puente || "Nacional"}. Sello registrado: ${trip.sello || "N/A"}. Documento operativo para control interno de patio y ruta.</textarea>
        </div>
      </div>
    </div>`;
}

function renderPuentes() {
  const activeIds = new Set((state.active_ports || []).map((p) => p.id));
  return `
    <div class="top">
      <div>
        <h2>Puertos de Cruce Fronterizo</h2>
        <p>Puertos autorizados para tu línea. Activa o desactiva puertos en la pestaña <b>Mi Empresa</b>.</p>
      </div>
    </div>
    <div class="grid three">
      ${(state.all_ports || state.active_ports || [])
        .map((b) => {
          const isActive = activeIds.has(b.id);
          return `
        <div class="card" style="border-color:${isActive ? "rgba(61,214,140,.35)" : "var(--line)"}">
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <h3 style="margin:0 0 6px">${b.name}</h3>
            <span class="badge ${isActive ? "ok" : "muted"}">${isActive ? "Activo en tu línea" : "No asignado"}</span>
          </div>
          <p style="font-size:12.5px;color:var(--accent);margin:2px 0 8px"><b>${b.lado_mx}</b> ⇄ <b>${b.lado_us}</b></p>
          <p class="muted" style="font-size:12px">${b.nota}</p>
        </div>`;
        })
        .join("")}
    </div>`;
}

function renderEmpresa() {
  const u = state.user;
  const activeIds = new Set((state.active_ports || []).map((p) => p.id));

  return `
    <div class="top">
      <div>
        <h2>Datos de Mi Empresa & Puertos Autorizados</h2>
        <p>Configura los datos de tu línea de transporte y selecciona qué puertos fronterizos opera tu empresa.</p>
      </div>
    </div>
    <div class="grid two">
      <div class="card">
        <h3>Datos de la Línea</h3>
        <form id="company-form" class="form-grid" style="margin-top:14px">
          <div class="field full"><label>Razón Social / Nombre de la Línea</label><input name="name" value="${u.company}" required></div>
          <div class="field full"><label>Base de Operaciones (Ciudad y Estado)</label><input name="base" value="${u.base || ""}" placeholder="Ej: Nuevo Laredo / Monterrey / Laredo TX" required></div>
          <div class="field full"><label>Patio Principal / Dirección de Maniobras</label><input name="patio" value="${u.patio || ""}" placeholder="Ej: Carretera Nacional Km 14 / Patio Colombia"></div>
          <div class="field full"><label>Estatus Comercial de la Cuenta</label><input value="${(u.billing_status || "trial").toUpperCase()} - ${u.company_active ? "ACTIVA" : "SUSPENDIDA"}" readonly></div>
          <div class="full" style="margin-top:10px">
            <button class="btn" type="submit">Actualizar Datos de Empresa</button>
          </div>
        </form>
      </div>

      <div class="card">
        <h3>Puertos de Cruce Autorizados</h3>
        <p class="muted" style="font-size:12.5px;margin-bottom:12px">Solo los puertos marcados aparecerán en el selector de órdenes de viaje.</p>
        <form id="ports-form">
          <div style="display:flex;flex-direction:column;gap:8px;max-height:360px;overflow-y:auto;padding-right:6px">
            ${(state.all_ports || [])
              .map(
                (p) => `
              <label class="doc" style="display:flex;justify-content:space-between;align-items:center">
                <div>
                  <b>${p.name}</b>
                  <div class="muted" style="font-size:11px">${p.lado_mx} ⇄ ${p.lado_us}</div>
                </div>
                <input type="checkbox" name="port_${p.id}" value="${p.id}" ${activeIds.has(p.id) ? "checked" : ""}>
              </label>`
              )
              .join("")}
          </div>
          <div style="margin-top:14px">
            <button class="btn" type="submit">Guardar Puertos de la Línea</button>
          </div>
        </form>
      </div>
    </div>`;
}

function renderEquipo() {
  return `
    <div class="top">
      <div>
        <h2>Usuarios y Permisos de la Línea</h2>
        <p>Invita a personal de despacho, taller y operadores. Controla contraseñas y accesos.</p>
      </div>
      <div class="actions">
        <button class="btn" id="add-user">Invitar Usuario</button>
        <a class="btn secondary" href="/api/backup" target="_blank">Descargar Respaldo JSON</a>
      </div>
    </div>
    <div class="card" id="users-table"><p class="muted">Cargando personal...</p></div>`;
}

function renderTerminos() {
  return `
    <div class="top">
      <div>
        <h2>Términos y Deslinde Legal del Piloto CruceLine</h2>
        <p>Condiciones operativas aplicables para la etapa de piloto comercial de pago.</p>
      </div>
    </div>
    <div class="card terms-content" style="max-width:850px">
      <h3>1. Naturaleza del Software (Piloto Operativo)</h3>
      <p>CruceLine es una solución especializada en el despacho de fletes, control de flota, seguimiento de mantenimiento y trazabilidad documental para empresas de transporte en México y EE.UU.</p>

      <h3>2. Deslinde Fiscal y Tributario (Carta Porte / CFDI SAT)</h3>
      <p><b>CruceLine no emite timbrado fiscal ni sustituye la obligación de generar el Comprobante Fiscal Digital por Internet (CFDI) con Complemento Carta Porte 3.1</b> a través de un Proveedor Autorizado de Certificación (PAC) del SAT. Todos los borradores e impresiones emitidos por la plataforma tienen carácter estrictamente operativo y de control interno.</p>

      <h3>3. Trámites Aduanales y Cruce Fronterizo</h3>
      <p>La plataforma no reemplaza la intervención de agentes aduanales, agencias de aduanas, brokers ni los sistemas oficiales de la Agencia Nacional de Aduanas de México (ANAM) ni de U.S. Customs and Border Protection (CBP). La validez, vigencia y presentación del DODA, pedimento, gafetes FAST y sellos de seguridad son responsabilidad exclusiva del transportista y su cliente.</p>

      <h3>4. Soporte y Continuidad del Piloto</h3>
      <p>El periodo de piloto tiene una tarifa preferencial acordada. El acceso al sistema está sujeto al pago puntual de la mensualidad o suscripción del piloto. En caso de suspensión por falta de pago, el dueño de la empresa podrá solicitar el respaldo íntegro de su base de datos en formato JSON mediante soporte técnico.</p>
    </div>`;
}

// =====================================================================
// Vista y Pantalla Superadmin
// =====================================================================
function renderSuperadmin() {
  if (!isSuperadminMode) {
    return `
      <div class="top">
        <div>
          <h2>Consola Superadmin CruceLine</h2>
          <p>Acceso exclusivo para administración maestra y corte por falta de pago.</p>
        </div>
      </div>
      <div class="card" style="max-width:480px;margin:20px 0">
        <h3>Autenticación Maestra</h3>
        <p class="muted" style="margin-bottom:14px">Ingresa la clave secreta <code>CRUCELINE_SECRET</code> configurada en el servidor:</p>
        <form id="admin-auth-form">
          <div class="field"><label>Clave Maestra</label><input type="password" id="admin-secret-input" required placeholder="CRUCELINE_SECRET"></div>
          <p id="admin-auth-error" class="muted" style="color:var(--bad)"></p>
          <button class="btn danger" type="submit">Ingresar a Consola</button>
        </form>
      </div>`;
  }

  return `
    <div class="top">
      <div>
        <h2>Consola Superadministrador</h2>
        <p>Control maestro de empresas de transporte, estado de pago y corte de servicio (active=0).</p>
      </div>
      <button class="btn ghost" id="btn-admin-logout">Cerrar Sesión Superadmin</button>
    </div>
    <div id="admin-companies-container"><p class="muted">Cargando empresas...</p></div>`;
}

async function loadSuperadminCompanies() {
  try {
    const list = await api("/api/admin/companies");
    const container = $("#admin-companies-container");
    if (!container) return;

    const total = list.length;
    const activas = list.filter((c) => c.active === 1).length;
    const suspendidas = total - activas;

    container.innerHTML = `
      <div class="grid three" style="margin-bottom:18px">
        <div class="card kpi"><span>Total Empresas</span><strong>${total}</strong><small>Líneas registradas</small></div>
        <div class="card kpi"><span>Empresas Activas</span><strong>${activas}</strong><small>Con acceso al sistema</small></div>
        <div class="card kpi"><span>Empresas Suspendidas</span><strong style="color:var(--bad)">${suspendidas}</strong><small>Corte por falta de pago</small></div>
      </div>
      <div class="card">
        <h3>Empresas en la Plataforma</h3>
        <table>
          <thead><tr><th>ID</th><th>Línea / Razón Social</th><th>Base y Patio</th><th>Fecha Alta</th><th>Viajes</th><th>Usuarios</th><th>Estatus</th><th>Facturación</th><th>Acciones de Corte</th></tr></thead>
          <tbody>
            ${list
              .map(
                (c) => `
              <tr>
                <td><b>#${c.id}</b></td>
                <td><b>${c.name}</b></td>
                <td>${c.base}<div class="muted" style="font-size:11px">${c.patio || "—"}</div></td>
                <td>${c.created_at || "—"}</td>
                <td>${c.total_trips}</td>
                <td>${c.total_users}</td>
                <td>${statusBadge(c.active ? "Activa" : "Suspendida")}</td>
                <td>
                  <select onchange="changeCompanyBilling(${c.id}, this.value)" style="padding:4px 8px;font-size:11.5px">
                    <option value="trial" ${c.billing_status === "trial" ? "selected" : ""}>Trial / Piloto</option>
                    <option value="active" ${c.billing_status === "active" ? "selected" : ""}>Al corriente (Paid)</option>
                    <option value="suspended" ${c.billing_status === "suspended" ? "selected" : ""}>Suspendida (Impago)</option>
                  </select>
                </td>
                <td>
                  <button class="btn sm ${c.active ? "danger" : "ok"}" onclick="toggleCompanyActive(${c.id}, ${c.active ? 0 : 1})">
                    ${c.active ? "Suspender (active=0)" : "Reactivar (active=1)"}
                  </button>
                </td>
              </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>`;
  } catch (err) {
    if ($("#admin-companies-container")) {
      $("#admin-companies-container").innerHTML = `<div class="card" style="color:var(--bad)">${err.message}</div>`;
    }
  }
}

window.toggleCompanyActive = async (cid, newActive) => {
  const actionText = newActive ? "reactivar" : "suspender el acceso por impago (active=0)";
  if (!confirm(`¿Confirmas que deseas ${actionText} a la empresa #${cid}?`)) return;
  try {
    await api(`/api/admin/companies/${cid}/status`, {
      method: "POST",
      body: { active: newActive, billing_status: newActive ? "active" : "suspended" },
    });
    await loadSuperadminCompanies();
  } catch (err) {
    alert(err.message);
  }
};

window.changeCompanyBilling = async (cid, newStatus) => {
  try {
    await api(`/api/admin/companies/${cid}/status`, {
      method: "POST",
      body: { billing_status: newStatus, active: newStatus !== "suspended" },
    });
    await loadSuperadminCompanies();
  } catch (err) {
    alert(err.message);
  }
};

function promptAdd(title, fields, onSave) {
  $("#modals").innerHTML = `
    <div class="modal-bg show" id="modal"><div class="modal">
      <div class="top"><h2>${title}</h2><button class="btn ghost" id="close-modal">Cerrar</button></div>
      <form id="generic-form" class="form-grid">
        ${fields
          .map(
            (f) =>
              `<div class="field ${f.full ? "full" : ""}"><label>${f.label}</label><input name="${f.name}" value="${f.value || ""}" ${f.type ? `type="${f.type}"` : ""} ${f.required ? "required" : ""}></div>`
          )
          .join("")}
        <div class="full" style="margin-top:8px"><button class="btn" type="submit">Guardar Registro</button></div>
      </form>
    </div></div>`;
  $("#close-modal").onclick = () => ($("#modals").innerHTML = "");
  $("#generic-form").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await onSave(Object.fromEntries(new FormData(e.target).entries()));
      $("#modals").innerHTML = "";
      await loadApp();
    } catch (err) {
      alert(err.message);
    }
  };
}

function bindViewEvents() {
  if ($("#add-trip")) {
    $("#add-trip").onclick = () => {
      $("#modals").innerHTML = tripModal(null);
      $("#close-modal").onclick = () => ($("#modals").innerHTML = "");
      $("#trip-form").onsubmit = async (e) => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(e.target).entries());
        data.flete = Number(data.flete || 0);
        try {
          await api("/api/trips", { method: "POST", body: data });
          $("#modals").innerHTML = "";
          await loadApp();
          go("viajes");
        } catch (err) {
          alert(err.message);
        }
      };
    };
  }

  $$("[data-trip]").forEach((el) => {
    el.onclick = () => {
      const trip = state.trips.find((t) => t.folio === el.dataset.trip);
      if (!trip) return;
      $("#modals").innerHTML = tripModal(trip);
      $("#close-modal").onclick = () => ($("#modals").innerHTML = "");
      $("#trip-form").onsubmit = async (e) => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(e.target).entries());
        data.flete = Number(data.flete || 0);
        try {
          await api("/api/trips/" + trip.folio, { method: "PUT", body: data });
          $("#modals").innerHTML = "";
          await loadApp();
          go("viajes");
        } catch (err) {
          alert(err.message);
        }
      };
    };
  });

  if ($("#add-unit")) {
    $("#add-unit").onclick = () =>
      promptAdd(
        "Alta de Unidad",
        [
          { label: "Número Económico", name: "code", required: true },
          { label: "Tipo (Tractor, Caja 53', Rabón 3.5)", name: "tipo", value: "Tractor", required: true },
          { label: "Placas (MX o USA)", name: "placas" },
          { label: "Número de Serie / VIN", name: "vin" },
          { label: "Vencimiento Póliza Seguro", name: "seguro", type: "date" },
          { label: "Vencimiento Verificación Mecánica", name: "verif", type: "date" },
        ],
        (d) => api("/api/units", { method: "POST", body: { ...d, estatus: "Disponible" } })
      );
  }

  if ($("#add-driver")) {
    $("#add-driver").onclick = () =>
      promptAdd(
        "Alta de Operador",
        [
          { label: "Identificador / Clave", name: "code", required: true },
          { label: "Nombre Completo", name: "nombre", required: true },
          { label: "Licencias (Federal, Estatal, CDL)", name: "lic" },
          { label: "Vencimiento Tarjeta FAST / Visa", name: "fast", type: "date" },
          { label: "Vencimiento Examen Médico", name: "medico", type: "date" },
        ],
        (d) => api("/api/drivers", { method: "POST", body: d })
      );
  }

  if ($("#add-client")) {
    $("#add-client").onclick = () =>
      promptAdd(
        "Alta de Cliente / Broker",
        [
          { label: "Código / Referencia", name: "code", required: true },
          { label: "Nombre de la Empresa / Razón Social", name: "nombre", required: true },
          { label: "RFC (México) o EIN / Tax ID (USA)", name: "rfc" },
          { label: "Plazo de Pago (Contado, 15 días, 30 días)", name: "pago" },
          { label: "Rutas / Puentes Frecuentes", name: "cruzes", value: "Comercio Mundial / Nacional" },
        ],
        (d) => api("/api/clients", { method: "POST", body: d })
      );
  }

  if ($("#add-appt")) {
    $("#add-appt").onclick = () =>
      promptAdd(
        "Nueva Cita / Andén",
        [
          { label: "Folio Cita (opcional)", name: "code" },
          { label: "Folio de Viaje Asignado", name: "viaje", required: true },
          { label: "Tipo (Cruce Puente, Aduana, Andén)", name: "tipo", value: "Cruce Puente" },
          { label: "Lugar / Terminal", name: "lugar", value: "Puente Comercio Mundial", required: true },
          { label: "Fecha y Hora Programada", name: "fecha", required: true },
        ],
        (d) => api("/api/appointments", { method: "POST", body: d })
      );
  }

  if ($("#add-money")) {
    $("#add-money").onclick = () =>
      promptAdd(
        "Registrar Movimiento Financiero",
        [
          { label: "Folio Movimiento (opcional)", name: "code" },
          { label: "Viaje Relacionado", name: "viaje" },
          { label: "Concepto (Flete, Anticipo, Caseta, Diesel)", name: "concepto", required: true },
          { label: "Beneficiario / Cliente / Operador", name: "persona", required: true },
          { label: "Monto", name: "monto", type: "number", required: true },
          { label: "Moneda (MXN o USD)", name: "moneda", value: "MXN", required: true },
          { label: "Tipo (Ingreso, Egreso, Anticipo)", name: "tipo", value: "Ingreso", required: true },
        ],
        (d) => api("/api/money", { method: "POST", body: d })
      );
  }

  if ($("#add-ot")) {
    $("#add-ot").onclick = () =>
      promptAdd(
        "Nueva Orden de Trabajo (Taller)",
        [
          { label: "Folio OT (opcional)", name: "code" },
          { label: "Económico de Unidad", name: "unidad", required: true },
          { label: "Descripción de Falla o Mantenimiento", name: "falla", full: true, required: true },
          { label: "Taller / Proveedor", name: "taller", value: "Taller Patio Principal" },
          { label: "Costo Estimado", name: "costo", type: "number" },
          { label: "Fecha Estimada de Salida (ETA)", name: "eta", type: "date" },
        ],
        (d) => api("/api/workorders", { method: "POST", body: { ...d, costo: Number(d.costo || 0) } })
      );
  }

  $$("[data-doc]").forEach((chk) => {
    chk.onchange = async () => {
      await api(`/api/docs/${chk.dataset.folio}/${chk.dataset.doc}`, {
        method: "PUT",
        body: { ok: chk.checked },
      });
    };
  });

  if ($("#exp-trip")) {
    $("#exp-trip").onchange = () => {
      window._expFolio = $("#exp-trip").value;
      render();
    };
  }

  if ($("#print-cp")) $("#print-cp").onclick = () => window.print();

  if ($("#company-form")) {
    $("#company-form").onsubmit = async (e) => {
      e.preventDefault();
      const data = Object.fromEntries(new FormData(e.target).entries());
      try {
        await api("/api/company", { method: "PUT", body: data });
        alert("Datos de la empresa actualizados correctamente.");
        await loadApp();
      } catch (err) {
        alert(err.message);
      }
    };
  }

  if ($("#ports-form")) {
    $("#ports-form").onsubmit = async (e) => {
      e.preventDefault();
      const checkedPorts = $$("#ports-form input[type=checkbox]:checked").map((cb) => cb.value);
      try {
        await api("/api/company/ports", { method: "PUT", body: { ports: checkedPorts } });
        alert("Puertos actualizados. Solo los puertos seleccionados aparecerán en las órdenes de flete.");
        await loadApp();
        go("empresa");
      } catch (err) {
        alert(err.message);
      }
    };
  }

  if ($("#banner-terms-btn")) {
    $("#banner-terms-btn").onclick = () => go("terminos");
  }

  if ($("#admin-auth-form")) {
    $("#admin-auth-form").onsubmit = async (e) => {
      e.preventDefault();
      const secret = $("#admin-secret-input").value;
      try {
        await api("/api/admin/login", { method: "POST", body: { secret } });
        isSuperadminMode = true;
        render();
      } catch (err) {
        $("#admin-auth-error").textContent = err.message;
      }
    };
  }

  if ($("#btn-admin-logout")) {
    $("#btn-admin-logout").onclick = async () => {
      await api("/api/admin/logout", { method: "POST", body: {} });
      isSuperadminMode = false;
      go("dashboard");
    };
  }

  if ($("#add-user")) {
    $("#add-user").onclick = () =>
      promptAdd(
        "Invitar Nuevo Usuario",
        [
          { label: "Nombre Completo", name: "name", required: true },
          { label: "Correo Electrónico", name: "email", type: "email", required: true },
          { label: "Contraseña Temporal (mín. 6 car.)", name: "password", required: true },
          { label: "Rol (owner, dispatch, taller, operador)", name: "role", value: "dispatch", required: true },
        ],
        (d) => api("/api/users", { method: "POST", body: d })
      );
  }

  if ($("#users-table")) {
    api("/api/users")
      .then((list) => {
        $("#users-table").innerHTML = `
        <table>
          <thead><tr><th>Nombre</th><th>Correo</th><th>Rol</th><th>Estatus</th><th>Acciones</th></tr></thead>
          <tbody>
            ${list
              .map(
                (u) => `
              <tr>
                <td><b>${u.name}</b></td>
                <td>${u.email}</td>
                <td>${statusBadge(u.role)}</td>
                <td>${statusBadge(u.active ? "Activo" : "Inactivo")}</td>
                <td>
                  <button class="btn sm secondary" onclick="resetUserPw(${u.id}, '${u.name}')">Contraseña</button>
                  ${
                    u.id !== state.user.id
                      ? `<button class="btn sm ${u.active ? "danger" : "ok"}" onclick="toggleUser(${u.id})">${u.active ? "Desactivar" : "Activar"}</button>`
                      : ""
                  }
                </td>
              </tr>`
              )
              .join("")}
          </tbody>
        </table>`;
      })
      .catch((err) => {
        $("#users-table").textContent = err.message;
      });
  }

  if (currentView === "superadmin" && isSuperadminMode) {
    loadSuperadminCompanies();
  }
}

window.resetUserPw = (userId, name) => {
  const newPw = prompt(`Ingresa la nueva contraseña para ${name}:`);
  if (!newPw) return;
  api(`/api/users/${userId}/password`, { method: "POST", body: { password: newPw } })
    .then(() => alert("Contraseña actualizada exitosamente."))
    .catch((err) => alert(err.message));
};

window.toggleUser = (userId) => {
  if (!confirm("¿Deseas cambiar el estado de acceso de este usuario?")) return;
  api(`/api/users/${userId}/toggle-active`, { method: "POST", body: {} })
    .then(() => renderEquipo())
    .catch((err) => alert(err.message));
};

document.addEventListener("DOMContentLoaded", async () => {
  $("#show-register").onclick = () => {
    $("#login-box").classList.add("hidden");
    $("#superadmin-box").classList.add("hidden");
    $("#register-box").classList.remove("hidden");
  };
  $("#show-login").onclick = () => {
    $("#register-box").classList.add("hidden");
    $("#superadmin-box").classList.add("hidden");
    $("#login-box").classList.remove("hidden");
  };
  $("#show-login-from-admin").onclick = () => {
    $("#superadmin-box").classList.add("hidden");
    $("#register-box").classList.add("hidden");
    $("#login-box").classList.remove("hidden");
  };
  $("#show-superadmin").onclick = () => {
    $("#login-box").classList.add("hidden");
    $("#register-box").classList.add("hidden");
    $("#superadmin-box").classList.remove("hidden");
  };

  $("#superadmin-form").onsubmit = async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target).entries());
    try {
      await api("/api/admin/login", { method: "POST", body: data });
      isSuperadminMode = true;
      // Load app in superadmin view
      try {
        await loadApp();
      } catch {
        $("#auth").classList.add("hidden");
        $("#app").classList.remove("hidden");
      }
      go("superadmin");
    } catch (err) {
      $("#superadmin-error").textContent = err.message;
    }
  };

  $("#login-form").onsubmit = async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target).entries());
    try {
      await api("/api/auth/login", { method: "POST", body: data });
      await loadApp();
    } catch (err) {
      $("#login-error").textContent = err.message;
    }
  };
  $("#register-form").onsubmit = async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target).entries());
    try {
      await api("/api/auth/register", { method: "POST", body: data });
      await loadApp();
    } catch (err) {
      $("#register-error").textContent = err.message;
    }
  };
  $("#logout").onclick = async () => {
    await api("/api/auth/logout", { method: "POST", body: {} });
    location.reload();
  };
  $$(".nav-btn").forEach((b) => (b.onclick = () => go(b.dataset.view)));

  try {
    const adminStatus = await api("/api/admin/check").catch(() => ({}));
    if (adminStatus.is_superadmin) {
      isSuperadminMode = true;
    }
  } catch {
    /* Ignore */
  }

  const checkSuperadminHash = () => {
    if (location.hash === "#superadmin" && (!state || !state.user)) {
      $("#login-box")?.classList.add("hidden");
      $("#register-box")?.classList.add("hidden");
      $("#superadmin-box")?.classList.remove("hidden");
    }
  };
  window.addEventListener("hashchange", checkSuperadminHash);

  try {
    await api("/api/me");
    await loadApp();
  } catch {
    /* Muestra login */
    checkSuperadminHash();
  }
});
