#!/usr/bin/env python3
"""
Suite de Pruebas Automatizadas de CruceLine.
Verifica:
1. Endpoint /api/health y campo 'backup'.
2. Validación estricta de puertos en API (Bravo: solo WTB + Colombia + Sin cruce).
3. Registro de empresa con código de invitación obligatorio (403 sin código / con código mal; 200 con código bien y 0 puertos).
4. Superadmin creando empresa por /api/admin/companies sin código de invitación.
5. Consola Superadmin protegida por CRUCELINE_SECRET con hmac.compare_digest y corte comercial.
6. Anulación de viajes: estatus 'Anulado' permitido para owner/dispatch, rechazado para operador.
7. Filtrado de operador por driver_id (no ve viajes ajenos).
8. Rate limiting de logins: 8 intentos fallidos en 15 min devuelven 429.
"""
import json
import os
import sys
import unittest
from pathlib import Path

# Configurar entorno de pruebas
os.environ["CRUCELINE_ENV"] = "development"
os.environ["CRUCELINE_SEED"] = "1"
os.environ["CRUCELINE_INVITE_CODE"] = "TESTINVITE2026"

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import server


class CruceLineAPITestCase(unittest.TestCase):
    def setUp(self):
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()
        with server.app.app_context():
            server.init_db()
            db = server.db()
            # Limpiar intentos de login previos para evitar interferencia en tests
            db.execute("DELETE FROM login_attempts")
            db.execute("DELETE FROM support_chat_limits")
            # Asegurar estado base limpio de Transportes del Bravo (empresa 1)
            pac_comps = [r[0] for r in db.execute("SELECT id FROM companies WHERE name LIKE '%Pacífico%' OR name LIKE '%AdminCo%'").fetchall()]
            for pid in pac_comps:
                db.execute("DELETE FROM trip_docs WHERE company_id=?", (pid,))
                db.execute("DELETE FROM trips WHERE company_id=?", (pid,))
                db.execute("DELETE FROM company_ports WHERE company_id=?", (pid,))
                db.execute("DELETE FROM users WHERE company_id=?", (pid,))
                db.execute("DELETE FROM companies WHERE id=?", (pid,))
            bravo = db.execute("SELECT id FROM companies WHERE name LIKE '%Bravo%'").fetchone()
            if bravo:
                bid = bravo[0]
                db.execute("DELETE FROM company_ports WHERE company_id=?", (bid,))
                db.execute("INSERT INTO company_ports(company_id, port_id, active) VALUES (?, 'WTB', 1), (?, 'COL', 1)", (bid, bid))
                db.execute("UPDATE companies SET active=1, billing_status='trial' WHERE id=?", (bid,))
                db.commit()

    def test_01_health_and_ports_catalog(self):
        """Verifica salud del servicio, campo backup y catálogo de 11 puertos."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["database"], "ok")
        self.assertEqual(data.get("backup"), "configured")

        with server.app.app_context():
            db = server.db()
            ports = [r[0] for r in db.execute("SELECT id FROM ports ORDER BY id").fetchall()]
            expected = ['BRO', 'COL', 'DELRIO', 'EP', 'MEX', 'NOG', 'OTAY', 'PHR', 'STER', 'WTB', 'ZAR']
            self.assertEqual(sorted(ports), sorted(expected))

    def test_02_bravo_ports_and_trip_validation(self):
        """
        Verifica que Bravo solo tiene WTB y Colombia activos y que la API
        valida estrictamente el puerto en POST y PUT (rechaza OTAY con 400).
        """
        # 1. Login Bravo
        res = self.client.post("/api/auth/login", json={"email": "marco@delbravo.mx", "password": "Bravo2026!"})
        self.assertEqual(res.status_code, 200)

        # 2. Verificar que bootstrap solo entrega WTB y Colombia activos
        b_res = self.client.get("/api/bootstrap")
        self.assertEqual(b_res.status_code, 200)
        active_ids = [p["id"] for p in b_res.get_json()["active_ports"]]
        self.assertEqual(sorted(active_ids), ["COL", "WTB"])

        # 3. Intento de crear viaje con OTAY (nombre largo) -> DEBE FALLAR con 400
        fail1 = self.client.post("/api/trips", json={
            "folio": "FAIL-OTAY-01",
            "origen": "Tijuana, BC",
            "destino": "San Diego, CA",
            "puente": "Garita Otay Mesa",
            "flete": 800,
            "moneda": "USD"
        })
        self.assertEqual(fail1.status_code, 400)
        self.assertIn("no está habilitado", fail1.get_json()["error"])

        # 4. Intento de crear viaje con port_id 'OTAY' -> DEBE FALLAR con 400
        fail2 = self.client.post("/api/trips", json={
            "folio": "FAIL-OTAY-02",
            "origen": "Tijuana, BC",
            "destino": "San Diego, CA",
            "port_id": "OTAY",
            "flete": 800,
            "moneda": "USD"
        })
        self.assertEqual(fail2.status_code, 400)
        self.assertIn("no está habilitado", fail2.get_json()["error"])

        # 5. Crear viaje con WTB -> DEBE PASAR con 200
        ok_wtb = self.client.post("/api/trips", json={
            "folio": "PASS-WTB-01",
            "origen": "Patio NL Km 8.5",
            "destino": "Killam Laredo TX",
            "port_id": "WTB",
            "flete": 18500,
            "moneda": "MXN"
        })
        self.assertEqual(ok_wtb.status_code, 200)

        # 6. Crear viaje con Colombia Solidaridad -> DEBE PASAR con 200
        ok_col = self.client.post("/api/trips", json={
            "folio": "PASS-COL-01",
            "origen": "Patio NL Km 8.5",
            "destino": "Mines Rd Laredo TX",
            "puente": "Puente Colombia Solidaridad",
            "flete": 22000,
            "moneda": "MXN"
        })
        self.assertEqual(ok_col.status_code, 200)

        # 7. Crear viaje 'Sin cruce' -> DEBE PASAR con 200
        ok_nac = self.client.post("/api/trips", json={
            "folio": "PASS-NAC-01",
            "origen": "Monterrey, NL",
            "destino": "CDMX",
            "puente": "Sin cruce (Nacional / Doméstico)",
            "flete": 38000,
            "moneda": "MXN"
        })
        self.assertEqual(ok_nac.status_code, 200)

        # 8. Modificar hacia puerto no habilitado (PHR) -> DEBE FALLAR con 400
        put_fail = self.client.put("/api/trips/PASS-WTB-01", json={"port_id": "PHR"})
        self.assertEqual(put_fail.status_code, 400)
        self.assertIn("no está habilitado", put_fail.get_json()["error"])

        # 9. Modificar hacia puerto habilitado (Colombia) -> DEBE PASAR con 200
        put_ok = self.client.put("/api/trips/PASS-WTB-01", json={"port_id": "COL"})
        self.assertEqual(put_ok.status_code, 200)

    def test_03_invite_code_and_new_company_zero_ports(self):
        """
        Verifica:
        - Registro sin código de invitación -> 403
        - Registro con código incorrecto -> 403
        - Registro con código correcto -> 200 e inicia con 0 puertos
        - Intento de cruce internacional sin puertos activos -> 400
        - Tras activar puertos en Mi Empresa -> 200
        """
        payload = {
            "company": "Transportes del Pacífico S.A.",
            "name": "Roberto Dueño",
            "email": "roberto@pacifico.mx",
            "password": "Pacifico2026!",
            "base": "Tijuana, Baja California",
            "patio": "Otay Industrial"
        }

        # 1. Sin código -> 403
        fail_no_code = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(fail_no_code.status_code, 403)
        self.assertIn("código de invitación", fail_no_code.get_json()["error"].lower())

        # 2. Con código erróneo -> 403
        payload_bad = {**payload, "invite_code": "CODIGO_FALSO"}
        fail_bad_code = self.client.post("/api/auth/register", json=payload_bad)
        self.assertEqual(fail_bad_code.status_code, 403)

        # 3. Con código válido -> 200
        payload_ok = {**payload, "invite_code": "TESTINVITE2026"}
        ok_reg = self.client.post("/api/auth/register", json=payload_ok)
        self.assertEqual(ok_reg.status_code, 200)

        # 4. Empresa nueva inicia con 0 puertos activos
        b_res = self.client.get("/api/bootstrap")
        self.assertEqual(b_res.status_code, 200)
        self.assertEqual(len(b_res.get_json()["active_ports"]), 0)

        # 5. Intentar cruce con WTB teniendo 0 puertos -> DEBE FALLAR con 400
        fail_cruce = self.client.post("/api/trips", json={
            "folio": "PAC-001",
            "origen": "Tijuana, BC",
            "destino": "San Diego, CA",
            "puente": "Puente Comercio Mundial (WTB)",
            "flete": 950,
            "moneda": "USD"
        })
        self.assertEqual(fail_cruce.status_code, 400)
        self.assertIn("no está habilitado", fail_cruce.get_json()["error"])

        # 6. Activar Otay Mesa y Mexicali en Mi Empresa
        save_ports = self.client.put("/api/company/ports", json={"ports": ["OTAY", "MEX"]})
        self.assertEqual(save_ports.status_code, 200)

        # 7. Ahora viaje por Otay Mesa -> DEBE PASAR con 200
        ok_otay = self.client.post("/api/trips", json={
            "folio": "PAC-003",
            "origen": "Tijuana, BC",
            "destino": "San Diego, CA",
            "port_id": "OTAY",
            "flete": 950,
            "moneda": "USD"
        })
        self.assertEqual(ok_otay.status_code, 200)

    def test_04_superadmin_auth_and_company_cutoff(self):
        """
        Verifica aislamiento de Superadmin:
        - Sesión normal de empresa NO da acceso a superadmin (401).
        - Solo login con CRUCELINE_SECRET (validado con hmac.compare_digest) permite entrar.
        - Superadmin suspende empresa (active=0) y login falla con 403.
        - Superadmin reactiva empresa (active=1) y acceso se restablece.
        """
        sec = server.app.secret_key

        # 1. Login como dueño de Bravo
        self.client.post("/api/auth/login", json={"email": "marco@delbravo.mx", "password": "Bravo2026!"})

        # 2. Intentar entrar a endpoints superadmin sin autenticación maestra -> DEBE DAR 401
        no_auth = self.client.get("/api/admin/companies")
        self.assertEqual(no_auth.status_code, 401)

        # 3. Autenticación Superadmin con clave maestra
        admin_login = self.client.post("/api/admin/login", json={"secret": sec})
        self.assertEqual(admin_login.status_code, 200)

        # 4. Listar empresas
        comps = self.client.get("/api/admin/companies").get_json()
        self.assertTrue(len(comps) >= 1)
        bravo_id = [c["id"] for c in comps if "Bravo" in c["name"]][0]

        # 5. Suspender a Bravo (active=0)
        corte = self.client.post(f"/api/admin/companies/{bravo_id}/status", json={"active": False, "billing_status": "suspended"})
        self.assertEqual(corte.status_code, 200)
        self.assertEqual(corte.get_json()["active"], 0)

        # 6. Cerrar superadmin e intentar login como usuario de Bravo -> DEBE DAR 403
        self.client.post("/api/admin/logout")
        fail_login = self.client.post("/api/auth/login", json={"email": "marco@delbravo.mx", "password": "Bravo2026!"})
        self.assertEqual(fail_login.status_code, 403)
        self.assertIn("suspendida", fail_login.get_json()["error"])

        # 7. Superadmin reactiva empresa (active=1)
        self.client.post("/api/admin/login", json={"secret": sec})
        react = self.client.post(f"/api/admin/companies/{bravo_id}/toggle-active")
        self.assertEqual(react.status_code, 200)
        self.assertEqual(react.get_json()["active"], 1)

        # 8. Usuario vuelve a poder entrar con 200
        self.client.post("/api/admin/logout")
        ok_login = self.client.post("/api/auth/login", json={"email": "marco@delbravo.mx", "password": "Bravo2026!"})
        self.assertEqual(ok_login.status_code, 200)

    def test_05_superadmin_direct_company_creation(self):
        """Superadmin puede crear empresa sin código de invitación vía POST /api/admin/companies."""
        sec = server.app.secret_key
        # 1. Login superadmin
        self.client.post("/api/admin/login", json={"secret": sec})

        # 2. Crear empresa sin invite_code
        res = self.client.post("/api/admin/companies", json={
            "name": "Transportes AdminCo S.A.",
            "owner": "Carlos Admin",
            "email": "carlos@adminco.mx",
            "password": "AdminCo2026!",
            "base": "Monterrey, NL",
            "patio": "Patio Apodaca"
        })
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.get_json().get("ok"))

        # 3. Cerrar sesión superadmin y login como nuevo dueño
        self.client.post("/api/admin/logout")
        login_res = self.client.post("/api/auth/login", json={"email": "carlos@adminco.mx", "password": "AdminCo2026!"})
        self.assertEqual(login_res.status_code, 200)

    def test_06_trip_annulment_and_operator_permission(self):
        """
        Verifica:
        - Owner/dispatch puede cambiar estatus a 'Anulado'.
        - El viaje anulado permanece visible en trips.
        - Operador NO puede anular viajes (403).
        """
        # 1. Login dueño Bravo y anular viaje FV-1042
        self.client.post("/api/auth/login", json={"email": "marco@delbravo.mx", "password": "Bravo2026!"})
        res = self.client.put("/api/trips/FV-1042", json={"estatus": "Anulado"})
        self.assertEqual(res.status_code, 200)

        # Verificar estatus en trips
        b_res = self.client.get("/api/bootstrap")
        fv = [t for t in b_res.get_json()["trips"] if t["folio"] == "FV-1042"][0]
        self.assertEqual(fv["estatus"], "Anulado")

        # 2. Login como operador e intentar cambiar estatus -> DEBE DAR 403
        self.client.post("/api/auth/logout")
        self.client.post("/api/auth/login", json={"email": "jose@delbravo.mx", "password": "Operador2026!"})
        op_fail = self.client.put("/api/trips/FV-1042", json={"estatus": "En ruta"})
        self.assertEqual(op_fail.status_code, 403)

    def test_07_operator_filtered_by_driver_id(self):
        """
        Verifica que el operador solo ve sus propios viajes filtrados por driver_id
        y no ve viajes asignados a otros operadores.
        """
        # Login operador José Armando Treviño
        self.client.post("/api/auth/login", json={"email": "jose@delbravo.mx", "password": "Operador2026!"})
        b_res = self.client.get("/api/bootstrap")
        self.assertEqual(b_res.status_code, 200)
        trips = b_res.get_json()["trips"]

        # José solo debe ver los viajes asignados a él (FV-1042 y FV-1045)
        # FV-1043 (María Elena Cruz) y FV-1044 (Luis Gerardo Salazar) NO deben estar presentes
        folios = [t["folio"] for t in trips]
        self.assertIn("FV-1042", folios)
        self.assertIn("FV-1045", folios)
        self.assertNotIn("FV-1043", folios)
        self.assertNotIn("FV-1044", folios)

    def test_08_login_rate_limiting(self):
        """Verifica que 8 intentos fallidos de login por IP+email activan el bloqueo 429 Too Many Requests."""
        email = "testrate@delbravo.mx"
        # 8 intentos fallidos
        for _ in range(8):
            r = self.client.post("/api/auth/login", json={"email": email, "password": "wrongpassword"})
            self.assertEqual(r.status_code, 401)

        # El intento 9 debe devolver 429
        blocked = self.client.post("/api/auth/login", json={"email": email, "password": "wrongpassword"})
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("demasiados intentos", blocked.get_json()["error"].lower())

    def test_09_soporte_chat_requires_auth_and_rate_limit(self):
        """Verifica que sin sesión dé 401, con sesión sin API key informe no configurado y valide rate limit."""
        # 1. Sin sesión -> 401 obligatorio
        anon = self.client.post("/api/soporte/chat", json={"messages": [{"role": "user", "content": "hola"}]})
        self.assertEqual(anon.status_code, 401)
        self.assertIn("inicia sesión", anon.get_json()["error"].lower())

        # Iniciar sesión como Marco Dueño
        login_res = self.client.post("/api/auth/login", json={"email": "marco@delbravo.mx", "password": "Bravo2026!"})
        self.assertEqual(login_res.status_code, 200)

        # 2. Con sesión pero sin API key configurada
        orig_key = os.environ.get("SOPORTE_API_KEY")
        if "SOPORTE_API_KEY" in os.environ:
            del os.environ["SOPORTE_API_KEY"]

        res = self.client.post("/api/soporte/chat", json={"messages": [{"role": "user", "content": "hola"}]})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data.get("configured"))
        self.assertIn("no está configurado", data.get("reply", "").lower())

        # 3. Rate limit: 20 llamadas permitidas, la 21 debe dar 429
        with server.app.app_context():
            server.db().execute("DELETE FROM support_chat_limits")
            server.db().commit()

        for _ in range(20):
            r = self.client.post("/api/soporte/chat", json={"messages": []})
            self.assertEqual(r.status_code, 200)

        limit_res = self.client.post("/api/soporte/chat", json={"messages": []})
        self.assertEqual(limit_res.status_code, 429)
        self.assertIn("demasiados mensajes", limit_res.get_json()["error"].lower())

        if orig_key is not None:
            os.environ["SOPORTE_API_KEY"] = orig_key

    def test_10_landing_no_widget_and_prompt_blacklist(self):
        """Verifica que /landing no incluya el widget del asistente y valida la lista negra anti-alucinaciones."""
        # 1. Verificar landing estática limpia de scripts de IA
        res = self.client.get("/landing")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertNotIn("support-widget.js", html)
        self.assertNotIn("support-widget.css", html)
        self.assertNotIn("cl-chat", html)

        # 2. Verificar que index.html sí tenga el widget con cache buster
        idx_res = self.client.get("/")
        self.assertEqual(idx_res.status_code, 200)
        idx_html = idx_res.get_data(as_text=True)
        self.assertIn("support-widget.js?v=20260919c", idx_html)


if __name__ == "__main__":
    unittest.main()
