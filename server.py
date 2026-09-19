#!/usr/bin/env python3
"""CruceLine — TMS para fletes nacionales y transfronterizos México ⇄ Estados Unidos."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, request, send_from_directory, session

ROOT = Path(__file__).resolve().parent
ENV_MODE = os.environ.get("CRUCELINE_ENV", "development").lower()
SECRET_DEFAULT = "cruceline-nl-laredo-cambia-esto-en-produccion"
app_secret = os.environ.get("CRUCELINE_SECRET", SECRET_DEFAULT)

if ENV_MODE == "production" and (not app_secret or app_secret == SECRET_DEFAULT):
    raise RuntimeError(
        "CRUCELINE_SECRET no está configurada o usa el valor por defecto en producción. "
        "Define una clave segura en la variable de entorno CRUCELINE_SECRET."
    )

DB_PATH = Path(os.environ.get("CRUCELINE_DB", ROOT / "data" / "cruceline.db"))
STATIC = ROOT / "static"

app = Flask(__name__, static_folder=str(STATIC))
app.secret_key = app_secret
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_NAME"] = "cruceline_session"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("CRUCELINE_HTTPS", "0") == "1"
app.config["SESSION_COOKIE_PATH"] = "/"

BORDER_PORTS = [
    ("OTAY", "Garita Otay Mesa", "Tijuana, BC", "San Diego, CA", "Carga comercial", "Principal cruce comercial del noroeste hacia California."),
    ("MEX", "Garita Mexicali II (Nuevo Mexicali)", "Mexicali, BC", "Calexico East, CA", "Carga comercial", "Acceso comercial para el Valle Imperial y Mexicali."),
    ("NOG", "Puente Nogales Mariposa", "Nogales, SON", "Nogales, AZ", "Carga perecederos e industrial", "Corredor principal de hortalizas y manufactura de Sonora."),
    ("STER", "Cruce San Jerónimo - Santa Teresa", "San Jerónimo, CHIH", "Santa Teresa, NM", "Carga sobredimensionada e industrial", "Acceso ágil evitando el área urbana de El Paso."),
    ("ZAR", "Puente Zaragoza (Ysleta–Zaragoza)", "Cd. Juárez, CHIH", "El Paso, TX", "Carga maquiladora", "Principal cruce comercial de Ciudad Juárez hacia Texas."),
    ("EP", "Puente Camino Real (Eagle Pass II)", "Piedras Negras, COAH", "Eagle Pass, TX", "Carga pesada y transfer", "Cruce comercial clave para Coahuila y el centro de Texas."),
    ("WTB", "Puente Comercio Mundial (WTB)", "Nuevo Laredo, TAMPS", "Laredo, TX", "Carga pesada / trailers 53'", "Mayor puerto terrestre de carga en el continente."),
    ("COL", "Puente Colombia Solidaridad", "Anáhuac, NL", "Laredo, TX", "Carga / trailers y transfer", "Ruta alterna ágil conectada directamente con Nuevo León."),
    ("PHR", "Puente Internacional Pharr–Reynosa", "Reynosa, TAMPS", "Pharr, TX", "Carga comercial y perecederos", "Cruce clave para la industria maquiladora de Reynosa y Valle de Texas."),
    ("BRO", "Puente Los Indios / Veteranos (Brownsville)", "Matamoros, TAMPS", "Brownsville, TX", "Carga industrial y marítima", "Conexión comercial cercana al Golfo de México y puerto de Brownsville."),
    ("DELRIO", "Puente Internacional Acuña–Del Rio", "Cd. Acuña, COAH", "Del Rio, TX", "Carga y manufactura", "Cruce fronterizo para la región norte de Coahuila y Del Rio."),
]


def db() -> sqlite3.Connection:
    if "db" not in g:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
        g.db.execute("PRAGMA synchronous = NORMAL")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 180_000)
    return f"{salt.hex()}:{dk.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split(":")
    except ValueError:
        return False
    test = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 180_000)
    return hmac.compare_digest(test.hex(), dk_hex)


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", email))


def ensure_column(conn: sqlite3.Connection, table: str, column: str, col_type: str):
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            base TEXT NOT NULL DEFAULT 'Nuevo Laredo, Tamaulipas',
            patio TEXT NOT NULL DEFAULT 'Patio Km 8.5 · Carretera a Colombia',
            active INTEGER NOT NULL DEFAULT 1,
            billing_status TEXT NOT NULL DEFAULT 'trial',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL REFERENCES companies(id),
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('owner','dispatch','taller','operador')),
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            tipo TEXT NOT NULL,
            placas TEXT,
            vin TEXT,
            estatus TEXT,
            seguro TEXT,
            verif TEXT
        );
        CREATE TABLE IF NOT EXISTS drivers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            nombre TEXT NOT NULL,
            lic TEXT,
            fast TEXT,
            medico TEXT,
            estatus TEXT
        );
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            nombre TEXT NOT NULL,
            rfc TEXT,
            pago TEXT,
            cruzes TEXT
        );
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            folio TEXT NOT NULL,
            cliente TEXT,
            origen TEXT,
            destino TEXT,
            puente TEXT,
            equipo TEXT,
            operador TEXT,
            tipo TEXT,
            estatus TEXT,
            flete REAL DEFAULT 0,
            moneda TEXT DEFAULT 'MXN',
            cita TEXT,
            sello TEXT
        );
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            viaje TEXT,
            tipo TEXT,
            lugar TEXT,
            fecha TEXT,
            estatus TEXT
        );
        CREATE TABLE IF NOT EXISTS money (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            viaje TEXT,
            concepto TEXT,
            persona TEXT,
            monto REAL,
            moneda TEXT DEFAULT 'MXN',
            tipo TEXT,
            estatus TEXT
        );
        CREATE TABLE IF NOT EXISTS workorders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            unidad TEXT,
            falla TEXT,
            taller TEXT,
            costo REAL,
            estatus TEXT,
            eta TEXT
        );
        CREATE TABLE IF NOT EXISTS trip_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            folio TEXT NOT NULL,
            name TEXT NOT NULL,
            ok INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS ports (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            lado_mx TEXT NOT NULL,
            lado_us TEXT NOT NULL,
            uso TEXT,
            nota TEXT
        );
        CREATE TABLE IF NOT EXISTS company_ports (
            company_id INTEGER NOT NULL REFERENCES companies(id),
            port_id TEXT NOT NULL REFERENCES ports(id),
            active INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (company_id, port_id)
        );
        """
    )
    # Migraciones seguras para bases de datos existentes
    ensure_column(conn, "companies", "active", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "companies", "billing_status", "TEXT NOT NULL DEFAULT 'trial'")
    ensure_column(conn, "trips", "moneda", "TEXT NOT NULL DEFAULT 'MXN'")
    ensure_column(conn, "money", "moneda", "TEXT NOT NULL DEFAULT 'MXN'")

    # Semilla de los 11 puertos de cruce autorizados
    for p in BORDER_PORTS:
        conn.execute(
            "INSERT OR REPLACE INTO ports(id, name, lado_mx, lado_us, uso, nota) VALUES (?,?,?,?,?,?)",
            p,
        )

    conn.commit()

    # Asegurar que si la empresa demo Transportes del Bravo existe, active solo WTB + Colombia
    bravo = conn.execute("SELECT id FROM companies WHERE name LIKE '%Bravo%'").fetchone()
    if bravo:
        bid = bravo[0]
        if conn.execute("SELECT COUNT(*) FROM company_ports WHERE company_id=?", (bid,)).fetchone()[0] == 0:
            conn.execute("INSERT OR REPLACE INTO company_ports(company_id, port_id, active) VALUES (?, 'WTB', 1)", (bid,))
            conn.execute("INSERT OR REPLACE INTO company_ports(company_id, port_id, active) VALUES (?, 'COL', 1)", (bid,))
            conn.commit()

    seed_env = os.environ.get("CRUCELINE_SEED")
    should_seed = seed_env == "1" if seed_env is not None else (ENV_MODE != "production")
    if should_seed and conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 0:
        seed(conn)
    conn.close()


def seed(conn: sqlite3.Connection):
    cur = conn.execute(
        "INSERT INTO companies(name, base, patio, active, billing_status, created_at) VALUES (?,?,?,?,?,?)",
        (
            "Transportes del Bravo S.A. de C.V.",
            "Nuevo Laredo, Tamaulipas",
            "Patio Km 8.5 · Carretera a Colombia",
            1,
            "trial",
            now(),
        ),
    )
    cid = cur.lastrowid
    # Para Bravo: solo WTB y Colombia activos
    conn.execute("INSERT OR REPLACE INTO company_ports(company_id, port_id, active) VALUES (?, 'WTB', 1)", (cid,))
    conn.execute("INSERT OR REPLACE INTO company_ports(company_id, port_id, active) VALUES (?, 'COL', 1)", (cid,))

    users = [
        ("Marco Dueño", "marco@delbravo.mx", "Bravo2026!", "owner"),
        ("Ana Despacho", "despacho@delbravo.mx", "Despacho2026!", "dispatch"),
        ("Taller Patio", "taller@delbravo.mx", "Taller2026!", "taller"),
        ("José Armando Treviño", "jose@delbravo.mx", "Operador2026!", "operador"),
    ]
    for name, email, pw, role in users:
        conn.execute(
            "INSERT INTO users(company_id,name,email,password_hash,role,active) VALUES (?,?,?,?,?,1)",
            (cid, name, email, hash_password(pw), role),
        )
    units = [
        ("T-12", "Tractor", "25AZ8C TAMPS / TX-3L9201", "3HSDZAPR7LN123456", "En frontera", "2027-11-12", "2027-10-03"),
        ("T-07", "Tractor", "24BR1P TAMPS / TX-4K3310", "1XPBDP9X8LD554210", "Disponible", "2027-01-20", "2026-12-01"),
        ("T-21", "Tractor", "26CT4L TAMPS / TX-8M1022", "1XPBDP9X5ND771209", "En ruta", "2027-12-08", "2026-11-02"),
        ("C-53-18", "Caja 53'", "15CJ9M TAMPS", "1UYVS2538L3458901", "En frontera", "2027-09-30", "2026-11-22"),
        ("C-53-04", "Caja 53'", "18DK2A TAMPS", "1UYVS2535N2981112", "Disponible", "2027-03-14", "2026-11-09"),
        ("C-53-09", "Caja 53'", "21EM8P TAMPS", "1UYVS2532P4012288", "En patio Laredo", "2027-02-01", "2026-10-15"),
        ("R-3.5-02", "Rabón 3.5", "22HL6T TAMPS", "3ALACWDT8JD889001", "Taller", "2026-10-18", "2026-10-28"),
        ("R-3.5-05", "Rabón 3.5", "23JN1B TAMPS", "3ALACWDT2KD112334", "Disponible", "2027-01-05", "2026-12-12"),
    ]
    for u in units:
        conn.execute(
            "INSERT INTO units(company_id,code,tipo,placas,vin,estatus,seguro,verif) VALUES (?,?,?,?,?,?,?,?)",
            (cid, *u),
        )
    drivers = [
        ("OP-01", "José Armando Treviño", "LF Federal + CDL A + FAST", "2027-04-11", "2026-11-02", "En cruce WTB"),
        ("OP-02", "María Elena Cruz", "LF Federal", "—", "2026-12-19", "Disponible patio NL"),
        ("OP-03", "Ricardo Peña", "LF Federal + FAST", "2027-09-25", "2026-11-21", "Disponible patio NL"),
        ("OP-04", "Luis Gerardo Salazar", "LF Federal + FAST", "2027-01-18", "2026-11-30", "En ruta"),
    ]
    for d in drivers:
        conn.execute(
            "INSERT INTO drivers(company_id,code,nombre,lic,fast,medico,estatus) VALUES (?,?,?,?,?,?,?)",
            (cid, *d),
        )
    clients = [
        ("CL-01", "Rio Grande Transfer LLC", "— / EIN 74-118902", "30 días", "Comercio Mundial"),
        ("CL-02", "Industrias del Norte SA de CV", "INO980214AB3", "15 días", "Colombia / WTB"),
        ("CL-03", "Laredo Bonded Warehouses", "— / EIN 74-330221", "7 días", "Comercio Mundial"),
        ("CL-04", "Logística Nacional del Centro SC", "LNC190412KJ9", "15 días", "Sin cruce (Nacional)"),
    ]
    for c in clients:
        conn.execute(
            "INSERT INTO clients(company_id,code,nombre,rfc,pago,cruzes) VALUES (?,?,?,?,?,?)",
            (cid, *c),
        )
    trips = [
        ("FV-1042", "Rio Grande Transfer LLC", "Patio NL Km 8.5", "Killam Industrial, Laredo TX", "Puente Comercio Mundial (WTB)", "T-12 + C-53-18", "José Armando Treviño", "Trailer transfer (Frontera)", "En frontera", 18500, "MXN", "2026-10-19 16:30 WTB export", "CBP-889120"),
        ("FV-1043", "Industrias del Norte SA de CV", "Santa Catarina, NL", "Mines Rd yard, Laredo TX", "Puente Colombia Solidaridad", "T-07 + C-53-04", "María Elena Cruz", "Internacional MX → USA (FTL)", "Asignado", 24800, "MXN", "2026-10-20 09:00 Colombia", "Pendiente"),
        ("FV-1044", "Logística Nacional del Centro SC", "Apodaca, NL", "Cuautitlán Izcalli, Edo. Mex", "Sin cruce (Nacional / Doméstico)", "T-21 + C-53-09", "Luis Gerardo Salazar", "Nacional México (FTL)", "En ruta", 42000, "MXN", "Entrega 2026-10-22", "N/A"),
        ("FV-1045", "Rio Grande Transfer LLC", "Laredo, TX", "San Antonio / Austin, TX", "Sin cruce (Nacional / Doméstico)", "T-12 + C-53-18", "José Armando Treviño", "Doméstico USA (FTL)", "Cotizado", 1450, "USD", "2026-10-21 14:00", "USA-9921"),
    ]
    for t in trips:
        conn.execute(
            """INSERT INTO trips(company_id,folio,cliente,origen,destino,puente,equipo,operador,tipo,estatus,flete,moneda,cita,sello)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cid, *t),
        )
    appts = [
        ("CT-88", "FV-1042", "Cruce WTB", "Puente Comercio Mundial · export lane", "2026-10-19 16:30", "Confirmada"),
        ("CT-89", "FV-1042", "Aduana MX", "Recinto fiscalizado Nuevo Laredo", "2026-10-19 13:00", "En proceso"),
        ("CT-90", "FV-1043", "Cruce Colombia", "Puente Colombia Solidaridad", "2026-10-20 09:00", "Pendiente"),
        ("CT-91", "FV-1044", "Carga en Planta", "Parque Industrial Apodaca", "2026-10-20 08:00", "Confirmada"),
    ]
    for a in appts:
        conn.execute(
            "INSERT INTO appointments(company_id,code,viaje,tipo,lugar,fecha,estatus) VALUES (?,?,?,?,?,?,?)",
            (cid, *a),
        )
    money_rows = [
        ("LQ-101", "FV-1042", "Flete acordado", "Rio Grande Transfer LLC", 18500, "MXN", "Ingreso", "Por cobrar"),
        ("LQ-102", "FV-1042", "Anticipo diesel y casetas", "José Armando Treviño", 4500, "MXN", "Anticipo", "Pagado"),
        ("LQ-103", "FV-1044", "Flete nacional", "Logística Nacional del Centro SC", 42000, "MXN", "Ingreso", "Por cobrar"),
        ("LQ-104", "FV-1045", "Flete interestatal US", "Rio Grande Transfer LLC", 1450, "USD", "Ingreso", "Por cobrar"),
    ]
    for m in money_rows:
        conn.execute(
            "INSERT INTO money(company_id,code,viaje,concepto,persona,monto,moneda,tipo,estatus) VALUES (?,?,?,?,?,?,?,?,?)",
            (cid, *m),
        )
    workorders = [
        ("OT-14", "T-12", "Frenos y balatas tractor", "Taller patio NL", 6800, "Abierta", "2026-10-21"),
        ("OT-15", "C-53-18", "Luces de galibo y perno rey", "Taller patio NL", 2100, "Cerrada", "2026-10-18"),
    ]
    for w in workorders:
        conn.execute(
            "INSERT INTO workorders(company_id,code,unidad,falla,taller,costo,estatus,eta) VALUES (?,?,?,?,?,?,?,?)",
            (cid, *w),
        )
    for folio in ("FV-1042", "FV-1043", "FV-1044", "FV-1045"):
        for name in (
            "Carta Porte / CFDI (Borrador)",
            "BOL / Bill of Lading",
            "Pedimento / DODA broker",
            "Fotos de sellos de seguridad",
            "Inspección mecánica / CTPAT",
            "Póliza de seguro vigente",
            "Licencia / FAST de operador",
            "Comprobante de entrega (POD)",
        ):
            conn.execute(
                "INSERT INTO trip_docs(company_id,folio,name,ok) VALUES (?,?,?,0)",
                (cid, folio, name),
            )
    conn.commit()


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    row = db().execute(
        """SELECT users.*, companies.name AS company_name, companies.base, companies.patio,
                  companies.active AS company_active, companies.billing_status
           FROM users JOIN companies ON companies.id = users.company_id
           WHERE users.id=? AND users.active=1""",
        (uid,),
    ).fetchone()
    return row


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"error": "Inicia sesión"}), 401
        if user["company_active"] == 0:
            return jsonify({
                "error": "Cuenta de empresa suspendida por falta de pago o periodo piloto concluido. Contacte a soporte de CruceLine."
            }), 403
        request.user = user
        return fn(*args, **kwargs)

    return wrapper


def roles_allowed(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                return jsonify({"error": "Inicia sesión"}), 401
            if user["company_active"] == 0:
                return jsonify({
                    "error": "Cuenta de empresa suspendida. Contacte a soporte de CruceLine."
                }), 403
            if user["role"] not in roles:
                return jsonify({"error": "Sin permiso para este módulo"}), 403
            request.user = user
            return fn(*args, **kwargs)

        return wrapper

    return deco


def is_superadmin():
    return bool(session.get("is_superadmin")) or request.headers.get("X-Admin-Secret") == app.secret_key


def row_to_dict(row):
    return dict(row) if row else None


def rows(query, args=()):
    return [dict(r) for r in db().execute(query, args).fetchall()]


@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.get("/api/health")
def health():
    try:
        db().execute("SELECT 1").fetchone()
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"
    is_healthy = db_status == "ok"
    return jsonify({
        "status": "ok" if is_healthy else "degraded",
        "database": db_status,
        "time": now(),
        "version": "1.0.0-pilot"
    }), 200 if is_healthy else 503


@app.post("/api/auth/register")
def register():
    data = request.get_json(force=True)
    required = ("company", "name", "email", "password")
    if not all(data.get(k) for k in required):
        return jsonify({"error": "Completa empresa, nombre, correo y contraseña"}), 400

    email = data["email"].strip().lower()
    if not is_valid_email(email):
        return jsonify({"error": "El correo ingresado no tiene un formato válido"}), 400
    if len(data["password"]) < 8:
        return jsonify({"error": "La contraseña debe tener al menos 8 caracteres"}), 400

    if db().execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
        return jsonify({"error": "Ese correo ya existe en la plataforma"}), 409

    cur = db().execute(
        "INSERT INTO companies(name, base, patio, active, billing_status, created_at) VALUES (?,?,?,1,'trial',?)",
        (
            data["company"].strip(),
            data.get("base") or "Nuevo Laredo, Tamaulipas",
            data.get("patio") or "Patio Km 8.5 · Carretera a Colombia",
            now(),
        ),
    )
    cid = cur.lastrowid
    db().execute(
        "INSERT INTO users(company_id,name,email,password_hash,role,active) VALUES (?,?,?,?, 'owner', 1)",
        (cid, data["name"].strip(), email, hash_password(data["password"])),
    )
    # Empresa nueva inicia con 0 puertos de cruce activos (el dueño los activa en Mi Empresa)
    db().commit()

    user = db().execute(
        """SELECT users.*, companies.name AS company_name, companies.base, companies.patio,
                  companies.active AS company_active, companies.billing_status
           FROM users JOIN companies ON companies.id = users.company_id
           WHERE users.email=?""",
        (email,),
    ).fetchone()
    session["user_id"] = user["id"]
    return jsonify({"ok": True, "user": public_user(user, user)})


@app.post("/api/auth/login")
def login():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    user = db().execute(
        """SELECT users.*, companies.name AS company_name, companies.base, companies.patio,
                  companies.active AS company_active, companies.billing_status
           FROM users JOIN companies ON companies.id = users.company_id
           WHERE users.email=? AND users.active=1""",
        (email,),
    ).fetchone()
    if not user or not check_password(data.get("password") or "", user["password_hash"]):
        print(f"[AUTH FAIL] Login fallido para correo: '{email}' desde IP: {request.remote_addr}")
        return jsonify({"error": "Correo o contraseña incorrectos"}), 401

    if user["company_active"] == 0:
        return jsonify({
            "error": "Cuenta de empresa suspendida por falta de pago o periodo piloto vencido. Contacte a soporte de CruceLine."
        }), 403

    session["user_id"] = user["id"]
    return jsonify({"ok": True, "user": public_user(user, user)})


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/me")
@login_required
def me():
    u = request.user
    return jsonify({"user": public_user(u, u)})


def public_user(user, company):
    if company is None:
        company = {}
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "company_id": user["company_id"],
        "company": user["company_name"] if "company_name" in user.keys() else company.get("name", ""),
        "base": user["base"] if "base" in user.keys() else company.get("base", "Nuevo Laredo, Tamaulipas"),
        "patio": user["patio"] if "patio" in user.keys() else company.get("patio", ""),
        "company_active": user["company_active"] if "company_active" in user.keys() else company.get("active", 1),
        "billing_status": user["billing_status"] if "billing_status" in user.keys() else company.get("billing_status", "trial"),
    }


@app.put("/api/company")
@roles_allowed("owner")
def update_company():
    data = request.get_json(force=True)
    cid = request.user["company_id"]
    name = (data.get("name") or "").strip()
    base = (data.get("base") or "").strip()
    patio = (data.get("patio") or "").strip()
    if not name:
        return jsonify({"error": "El nombre de la empresa es obligatorio"}), 400
    db().execute(
        "UPDATE companies SET name=?, base=?, patio=? WHERE id=?",
        (name, base or "Nuevo Laredo, Tamaulipas", patio or "", cid),
    )
    db().commit()
    return jsonify({"ok": True})


@app.get("/api/company/ports")
@login_required
def get_company_ports():
    cid = request.user["company_id"]
    port_list = rows(
        """SELECT p.id, p.name, p.lado_mx, p.lado_us, p.uso, p.nota,
                  COALESCE(cp.active, 0) as active
           FROM ports p
           LEFT JOIN company_ports cp ON cp.port_id = p.id AND cp.company_id = ?
           ORDER BY p.name""",
        (cid,),
    )
    for p in port_list:
        p["active"] = bool(p["active"])
    return jsonify(port_list)


@app.put("/api/company/ports")
@roles_allowed("owner")
def update_company_ports():
    data = request.get_json(force=True)
    port_ids = data.get("ports") or []
    cid = request.user["company_id"]
    db().execute("DELETE FROM company_ports WHERE company_id=?", (cid,))
    for pid in port_ids:
        if db().execute("SELECT id FROM ports WHERE id=?", (pid,)).fetchone():
            db().execute("INSERT INTO company_ports(company_id, port_id, active) VALUES (?, ?, 1)", (cid, pid))
    db().commit()
    active_ports = rows(
        """SELECT p.* FROM ports p
           JOIN company_ports cp ON cp.port_id = p.id
           WHERE cp.company_id = ? AND cp.active = 1
           ORDER BY p.name""",
        (cid,),
    )
    return jsonify({"ok": True, "active_ports": active_ports})


@app.get("/api/bootstrap")
@login_required
def bootstrap():
    cid = request.user["company_id"]
    role = request.user["role"]
    trips = rows("SELECT * FROM trips WHERE company_id=? ORDER BY id DESC", (cid,))
    if role == "operador":
        trips = [t for t in trips if t["operador"] == request.user["name"]]

    active_ports = rows(
        """SELECT p.* FROM ports p
           JOIN company_ports cp ON cp.port_id = p.id
           WHERE cp.company_id = ? AND cp.active = 1
           ORDER BY p.name""",
        (cid,),
    )
    all_ports = rows(
        """SELECT p.id, p.name, p.lado_mx, p.lado_us, p.uso, p.nota,
                  COALESCE(cp.active, 0) as active
           FROM ports p
           LEFT JOIN company_ports cp ON cp.port_id = p.id AND cp.company_id = ?
           ORDER BY p.name""",
        (cid,),
    )
    for p in all_ports:
        p["active"] = bool(p["active"])

    payload = {
        "user": public_user(request.user, request.user),
        "units": rows("SELECT * FROM units WHERE company_id=? ORDER BY code", (cid,)),
        "drivers": rows("SELECT * FROM drivers WHERE company_id=? ORDER BY nombre", (cid,)),
        "clients": rows("SELECT * FROM clients WHERE company_id=? ORDER BY nombre", (cid,)),
        "trips": trips,
        "appointments": rows("SELECT * FROM appointments WHERE company_id=? ORDER BY fecha", (cid,)),
        "money": rows("SELECT * FROM money WHERE company_id=? ORDER BY id DESC", (cid,)),
        "workorders": rows("SELECT * FROM workorders WHERE company_id=? ORDER BY id DESC", (cid,)),
        "docs": {},
        "active_ports": active_ports,
        "all_ports": all_ports,
        "bridges": active_ports,
    }
    for d in rows("SELECT * FROM trip_docs WHERE company_id=?", (cid,)):
        payload["docs"].setdefault(d["folio"], []).append({"id": d["id"], "name": d["name"], "ok": bool(d["ok"])})
    return jsonify(payload)


def create_row(table, fields, extra, allowed_roles):
    if request.user["role"] not in allowed_roles:
        return jsonify({"error": "Sin permiso"}), 403
    data = request.get_json(force=True)
    cols = ["company_id", *fields]
    vals = [request.user["company_id"], *[data.get(f) if data.get(f) is not None else extra.get(f, "") for f in fields]]
    placeholders = ",".join("?" * len(cols))
    cur = db().execute(f"INSERT INTO {table}({','.join(cols)}) VALUES ({placeholders})", vals)
    db().commit()
    return jsonify({"ok": True, "id": cur.lastrowid})


@app.post("/api/units")
@login_required
def add_unit():
    data = request.get_json(force=True)
    if not (data.get("code") or "").strip():
        return jsonify({"error": "El número económico de la unidad es obligatorio"}), 400
    return create_row(
        "units",
        ["code", "tipo", "placas", "vin", "estatus", "seguro", "verif"],
        {"estatus": "Disponible", "tipo": "Tractor"},
        ("owner", "dispatch", "taller"),
    )


@app.post("/api/drivers")
@login_required
def add_driver():
    data = request.get_json(force=True)
    if not (data.get("nombre") or "").strip():
        return jsonify({"error": "El nombre del operador es obligatorio"}), 400
    return create_row(
        "drivers",
        ["code", "nombre", "lic", "fast", "medico", "estatus"],
        {"estatus": "Disponible patio NL"},
        ("owner", "dispatch"),
    )


@app.post("/api/clients")
@login_required
def add_client():
    data = request.get_json(force=True)
    if not (data.get("nombre") or "").strip():
        return jsonify({"error": "El nombre del cliente es obligatorio"}), 400
    return create_row(
        "clients",
        ["code", "nombre", "rfc", "pago", "cruzes"],
        {},
        ("owner", "dispatch"),
    )


def validate_and_resolve_port(cid: int, port_raw: str | None) -> tuple[str | None, str | None]:
    """
    Valida que el puerto/puente sea 'Sin cruce (Nacional / Doméstico)' o un puerto activo
    en company_ports para la empresa especificada.
    Acepta tanto el port_id (OTAY, WTB, COL...) como el nombre largo ("Puente Comercio Mundial (WTB)").
    Retorna (canonical_name, None) si es válido, o (None, error_msg) si es inválido.
    """
    val = (port_raw or "").strip()
    sin_cruce_options = (
        "sin cruce",
        "sin cruce (nacional / doméstico)",
        "sin cruce (nacional / domestico)",
        "sin cruce (nacional)",
        "nacional",
        "nac",
        "",
    )
    if val.lower() in sin_cruce_options:
        return "Sin cruce (Nacional / Doméstico)", None

    active_rows = db().execute(
        """SELECT p.id, p.name FROM ports p
           JOIN company_ports cp ON cp.port_id = p.id
           WHERE cp.company_id = ? AND cp.active = 1""",
        (cid,),
    ).fetchall()

    active_map = {}
    for r in active_rows:
        pid = r["id"].upper()
        pname = r["name"]
        active_map[pid] = pname
        active_map[pname.lower()] = pname
        if "(" in pname and ")" in pname:
            tag = pname[pname.find("(") + 1 : pname.find(")")].strip().upper()
            active_map[tag] = pname

    val_upper = val.upper()
    val_lower = val.lower()
    if val_upper in active_map:
        return active_map[val_upper], None
    if val_lower in active_map:
        return active_map[val_lower], None

    global_port = db().execute(
        "SELECT id, name FROM ports WHERE UPPER(id)=? OR LOWER(name)=? OR name LIKE ?",
        (val_upper, val_lower, f"%{val}%"),
    ).fetchone()

    if global_port:
        return None, (
            f"El puerto '{global_port['name']}' ({global_port['id']}) no está habilitado para tu empresa. "
            "Actívalo en 'Mi Empresa & Puertos' antes de asignarlo a una orden de viaje."
        )

    if len(active_rows) == 0:
        return None, (
            "Tu empresa no tiene ningún puerto fronterizo activo. "
            "Activa tus puertos en 'Mi Empresa & Puertos' o selecciona 'Sin cruce (Nacional / Doméstico)'."
        )

    return None, f"El puerto o cruce '{val}' no es válido o no está autorizado para tu empresa."


@app.post("/api/trips")
@login_required
def add_trip():
    if request.user["role"] not in ("owner", "dispatch"):
        return jsonify({"error": "Sin permiso"}), 403
    data = request.get_json(force=True)
    cid = request.user["company_id"]
    folio = (data.get("folio") or "").strip() or next_folio(cid)
    origen = (data.get("origen") or "").strip()
    destino = (data.get("destino") or "").strip()
    if not origen or not destino:
        return jsonify({"error": "Origen y destino son obligatorios"}), 400

    moneda = (data.get("moneda") or "MXN").strip().upper()
    if moneda not in ("MXN", "USD"):
        moneda = "MXN"

    try:
        flete = float(data.get("flete") or 0)
    except ValueError:
        return jsonify({"error": "Monto de flete inválido"}), 400

    port_input = data.get("puente") or data.get("port_id")
    puente, err = validate_and_resolve_port(cid, port_input)
    if err:
        return jsonify({"error": err}), 400

    db().execute(
        """INSERT INTO trips(company_id,folio,cliente,origen,destino,puente,equipo,operador,tipo,estatus,flete,moneda,cita,sello)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            cid,
            folio,
            data.get("cliente"),
            origen,
            destino,
            puente,
            data.get("equipo"),
            data.get("operador"),
            data.get("tipo") or "Trailer transfer (Frontera)",
            data.get("estatus") or "Cotizado",
            flete,
            moneda,
            data.get("cita"),
            data.get("sello"),
        ),
    )
    for name in (
        "Carta Porte / CFDI (Borrador)",
        "BOL / Bill of Lading",
        "Pedimento / DODA broker",
        "Fotos de sellos de seguridad",
        "Inspección mecánica / CTPAT",
        "Póliza de seguro vigente",
        "Licencia / FAST de operador",
        "Comprobante de entrega (POD)",
    ):
        db().execute(
            "INSERT INTO trip_docs(company_id,folio,name,ok) VALUES (?,?,?,0)",
            (cid, folio, name),
        )
    db().commit()
    return jsonify({"ok": True, "folio": folio})


@app.put("/api/trips/<folio>")
@login_required
def update_trip(folio):
    if request.user["role"] not in ("owner", "dispatch"):
        return jsonify({"error": "Sin permiso"}), 403
    data = request.get_json(force=True)
    cid = request.user["company_id"]

    if "puente" in data or "port_id" in data:
        port_input = data.get("puente") or data.get("port_id")
        puente, err = validate_and_resolve_port(cid, port_input)
        if err:
            return jsonify({"error": err}), 400
        data["puente"] = puente

    fields = ["cliente", "origen", "destino", "puente", "equipo", "operador", "tipo", "estatus", "flete", "moneda", "cita", "sello"]
    sets = []
    vals = []
    for f in fields:
        if f in data:
            sets.append(f"{f}=?")
            vals.append(float(data[f]) if f == "flete" else data[f])
    if not sets:
        return jsonify({"error": "No hay campos para actualizar"}), 400

    vals.extend([cid, folio])
    db().execute(f"UPDATE trips SET {','.join(sets)} WHERE company_id=? AND folio=?", vals)
    db().commit()
    return jsonify({"ok": True})


@app.post("/api/appointments")
@login_required
def add_appt():
    data = request.get_json(force=True)
    if not (data.get("code") or "").strip():
        data["code"] = f"CT-{int(datetime.now().timestamp()) % 10000}"
    return create_row(
        "appointments",
        ["code", "viaje", "tipo", "lugar", "fecha", "estatus"],
        {"estatus": "Pendiente", "tipo": "Cruce WTB"},
        ("owner", "dispatch"),
    )


@app.post("/api/money")
@login_required
def add_money():
    if request.user["role"] not in ("owner", "dispatch"):
        return jsonify({"error": "Sin permiso"}), 403
    data = request.get_json(force=True)
    tipo = data.get("tipo") or "Ingreso"
    estatus = data.get("estatus") or ("Por cobrar" if tipo == "Ingreso" else "Descontar")
    moneda = (data.get("moneda") or "MXN").strip().upper()
    if moneda not in ("MXN", "USD"):
        moneda = "MXN"
    try:
        monto = float(data.get("monto") or 0)
    except ValueError:
        return jsonify({"error": "Monto monetario inválido"}), 400

    db().execute(
        "INSERT INTO money(company_id,code,viaje,concepto,persona,monto,moneda,tipo,estatus) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            request.user["company_id"],
            data.get("code") or f"LQ-{int(datetime.now().timestamp())}",
            data.get("viaje"),
            data.get("concepto"),
            data.get("persona"),
            monto,
            moneda,
            tipo,
            estatus,
        ),
    )
    db().commit()
    return jsonify({"ok": True})


@app.post("/api/workorders")
@login_required
def add_ot():
    data = request.get_json(force=True)
    if not (data.get("code") or "").strip():
        data["code"] = f"OT-{int(datetime.now().timestamp()) % 10000}"
    return create_row(
        "workorders",
        ["code", "unidad", "falla", "taller", "costo", "estatus", "eta"],
        {"estatus": "Abierta", "taller": "Taller patio NL"},
        ("owner", "dispatch", "taller"),
    )


@app.put("/api/docs/<folio>/<int:doc_id>")
@login_required
def toggle_doc(folio, doc_id):
    if request.user["role"] not in ("owner", "dispatch", "operador"):
        return jsonify({"error": "Sin permiso"}), 403
    data = request.get_json(force=True)
    db().execute(
        "UPDATE trip_docs SET ok=? WHERE id=? AND company_id=? AND folio=?",
        (1 if data.get("ok") else 0, doc_id, request.user["company_id"], folio),
    )
    db().commit()
    return jsonify({"ok": True})


@app.post("/api/users")
@roles_allowed("owner")
def add_user():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    role = data.get("role") or "dispatch"
    if role not in ("owner", "dispatch", "taller", "operador"):
        return jsonify({"error": "Rol inválido"}), 400
    if not email or not data.get("password") or not data.get("name"):
        return jsonify({"error": "Nombre, correo y contraseña son obligatorios"}), 400
    if not is_valid_email(email):
        return jsonify({"error": "Formato de correo no válido"}), 400
    if len(data["password"]) < 6:
        return jsonify({"error": "La contraseña debe tener al menos 6 caracteres"}), 400

    try:
        db().execute(
            "INSERT INTO users(company_id,name,email,password_hash,role,active) VALUES (?,?,?,?,?,1)",
            (request.user["company_id"], data["name"].strip(), email, hash_password(data["password"]), role),
        )
        db().commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Ese correo ya existe en el sistema"}), 409
    return jsonify({"ok": True})


@app.get("/api/users")
@roles_allowed("owner")
def list_users():
    cid = request.user["company_id"]
    return jsonify(rows("SELECT id,name,email,role,active FROM users WHERE company_id=? ORDER BY id", (cid,)))


@app.post("/api/users/<int:user_id>/password")
@roles_allowed("owner")
def reset_user_password(user_id):
    data = request.get_json(force=True)
    new_pw = data.get("password")
    if not new_pw or len(new_pw) < 6:
        return jsonify({"error": "La nueva contraseña debe tener al menos 6 caracteres"}), 400
    cur = db().execute(
        "UPDATE users SET password_hash=? WHERE id=? AND company_id=?",
        (hash_password(new_pw), user_id, request.user["company_id"]),
    )
    db().commit()
    if cur.rowcount == 0:
        return jsonify({"error": "Usuario no encontrado"}), 404
    return jsonify({"ok": True})


@app.post("/api/users/<int:user_id>/toggle-active")
@roles_allowed("owner")
def toggle_user_active(user_id):
    if user_id == request.user["id"]:
        return jsonify({"error": "No puedes desactivar tu propio usuario dueño"}), 400
    target = db().execute("SELECT active FROM users WHERE id=? AND company_id=?", (user_id, request.user["company_id"])).fetchone()
    if not target:
        return jsonify({"error": "Usuario no encontrado"}), 404
    new_active = 0 if target["active"] == 1 else 1
    db().execute("UPDATE users SET active=? WHERE id=? AND company_id=?", (new_active, user_id, request.user["company_id"]))
    db().commit()
    return jsonify({"ok": True, "active": new_active})


@app.get("/api/backup")
@roles_allowed("owner")
def backup():
    cid = request.user["company_id"]
    dump = {
        "exported_at": now(),
        "company": public_user(request.user, request.user),
        "units": rows("SELECT * FROM units WHERE company_id=?", (cid,)),
        "drivers": rows("SELECT * FROM drivers WHERE company_id=?", (cid,)),
        "clients": rows("SELECT * FROM clients WHERE company_id=?", (cid,)),
        "trips": rows("SELECT * FROM trips WHERE company_id=?", (cid,)),
        "appointments": rows("SELECT * FROM appointments WHERE company_id=?", (cid,)),
        "money": rows("SELECT * FROM money WHERE company_id=?", (cid,)),
        "workorders": rows("SELECT * FROM workorders WHERE company_id=?", (cid,)),
        "docs": rows("SELECT * FROM trip_docs WHERE company_id=?", (cid,)),
        "company_ports": rows(
            """SELECT p.id, p.name FROM ports p
               JOIN company_ports cp ON cp.port_id = p.id
               WHERE cp.company_id = ? AND cp.active = 1""",
            (cid,),
        ),
    }
    return jsonify(dump)


# =====================================================================
# Control y Pantalla Superadmin para CruceLine
# =====================================================================
@app.post("/api/admin/login")
def admin_login():
    data = request.get_json(force=True)
    secret = (data.get("secret") or "").strip()
    if not secret or secret != app.secret_key:
        return jsonify({"error": "Clave maestra de Superadmin incorrecta"}), 401
    session["is_superadmin"] = True
    return jsonify({"ok": True})


@app.post("/api/admin/logout")
def admin_logout():
    session.pop("is_superadmin", None)
    return jsonify({"ok": True})


@app.get("/api/admin/check")
def admin_check():
    return jsonify({"is_superadmin": is_superadmin()})


@app.get("/api/admin/companies")
def admin_list_companies():
    if not is_superadmin():
        return jsonify({"error": "No autorizado como superadministrador de CruceLine"}), 401
    comps = rows(
        """SELECT id, name, base, patio, created_at, active, billing_status,
                  (SELECT COUNT(*) FROM trips WHERE trips.company_id = companies.id) as total_trips,
                  (SELECT COUNT(*) FROM users WHERE users.company_id = companies.id) as total_users
           FROM companies ORDER BY id DESC"""
    )
    return jsonify(comps)


@app.post("/api/admin/companies/<int:company_id>/toggle-active")
def admin_toggle_company_active(company_id):
    if not is_superadmin():
        return jsonify({"error": "No autorizado como superadministrador de CruceLine"}), 401
    cur = db().execute("SELECT active FROM companies WHERE id=?", (company_id,)).fetchone()
    if not cur:
        return jsonify({"error": "Empresa no encontrada"}), 404
    new_active = 0 if cur["active"] == 1 else 1
    new_billing = "suspended" if new_active == 0 else "active"
    db().execute("UPDATE companies SET active=?, billing_status=? WHERE id=?", (new_active, new_billing, company_id))
    db().commit()
    return jsonify({"ok": True, "company_id": company_id, "active": new_active, "billing_status": new_billing})


@app.post("/api/admin/companies/<int:company_id>/status")
def admin_company_status(company_id):
    if not is_superadmin():
        return jsonify({"error": "No autorizado como superadministrador de CruceLine"}), 401
    data = request.get_json(force=True)
    active = 1 if data.get("active") else 0
    billing_status = data.get("billing_status") or ("active" if active else "suspended")
    cur = db().execute(
        "UPDATE companies SET active=?, billing_status=? WHERE id=?",
        (active, billing_status, company_id),
    )
    db().commit()
    if cur.rowcount == 0:
        return jsonify({"error": "Empresa no encontrada"}), 404
    return jsonify({"ok": True, "company_id": company_id, "active": active, "billing_status": billing_status})


def next_folio(cid):
    row = db().execute("SELECT COUNT(*) AS n FROM trips WHERE company_id=?", (cid,)).fetchone()
    return f"FV-{1046 + row['n']}"


init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5055))
    print(f"CruceLine listo en http://127.0.0.1:{port} (Entorno: {ENV_MODE})")
    app.run(host="0.0.0.0", port=port, debug=False)
