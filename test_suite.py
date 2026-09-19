#!/usr/bin/env python3
"""
Suite de Pruebas Automatizadas de CruceLine.
Verifica:
1. Endpoint /api/health y catálogo de los 11 puertos fronterizos.
2. Validación estricta de puertos en API (Bravo: solo WTB + Colombia + Sin cruce).
3. Registro de empresa nueva con 0 puertos por default y restricción de cruce hasta activarlos.
4. Consola Superadmin protegida por CRUCELINE_SECRET y corte comercial (active=0 / 403).
"""
import json
import os
import sys
import unittest
from pathlib import Path

# Configurar entorno de pruebas
os.environ["CRUCELINE_ENV"] = "development"
os.environ["CRUCELINE_SEED"] = "1"

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
            # Asegurar estado base limpio de Transportes del Bravo (empresa 1)
            pac_comps = [r[0] for r in db.execute("SELECT id FROM companies WHERE name LIKE '%Pacífico%'").fetchall()]
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
        """Verifica salud del servicio y catálogo de 11 puertos en base de datos."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["database"], "ok")

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

        # 5. Crear viaje con WTB (nombre largo o port_id) -> DEBE PASAR con 200
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

        # 7. Crear viaje 'Sin cruce (Nacional / Doméstico)' -> DEBE PASAR con 200
        ok_nac = self.client.post("/api/trips", json={
            "folio": "PASS-NAC-01",
            "origen": "Monterrey, NL",
            "destino": "CDMX",
            "puente": "Sin cruce (Nacional / Doméstico)",
            "flete": 38000,
            "moneda": "MXN"
        })
        self.assertEqual(ok_nac.status_code, 200)

        # 8. Intentar modificar viaje existente hacia un puerto no habilitado (PHR) -> DEBE FALLAR con 400
        put_fail = self.client.put("/api/trips/PASS-WTB-01", json={"port_id": "PHR"})
        self.assertEqual(put_fail.status_code, 400)
        self.assertIn("no está habilitado", put_fail.get_json()["error"])

        # 9. Modificar viaje hacia un puerto habilitado (Colombia) -> DEBE PASAR con 200
        put_ok = self.client.put("/api/trips/PASS-WTB-01", json={"port_id": "COL"})
        self.assertEqual(put_ok.status_code, 200)

    def test_03_new_company_has_zero_ports_and_requires_activation(self):
        """
        Verifica que al registrar una empresa:
        - Inicia con 0 puertos activos.
        - Solo puede crear fletes 'Sin cruce'.
        - Falla con 400 si intenta cruce sin puertos activos.
        - Tras activar puertos en Mi Empresa, ya puede crear fletes de cruce.
        """
        # 1. Registrar empresa nueva
        reg = self.client.post("/api/auth/register", json={
            "company": "Transportes del Pacífico S.A.",
            "name": "Roberto Dueño",
            "email": "roberto@pacifico.mx",
            "password": "Pacifico2026!",
            "base": "Tijuana, Baja California",
            "patio": "Otay Industrial"
        })
        self.assertEqual(reg.status_code, 200)

        # 2. Verificar que inicia con 0 puertos activos
        b_res = self.client.get("/api/bootstrap")
        self.assertEqual(b_res.status_code, 200)
        self.assertEqual(len(b_res.get_json()["active_ports"]), 0)

        # 3. Intentar crear viaje con WTB -> DEBE FALLAR con 400
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

        # 4. Crear viaje Sin cruce -> DEBE PASAR con 200
        ok_nac = self.client.post("/api/trips", json={
            "folio": "PAC-002",
            "origen": "Tijuana, BC",
            "destino": "Mexicali, BC",
            "puente": "Sin cruce (Nacional / Doméstico)",
            "flete": 14000,
            "moneda": "MXN"
        })
        self.assertEqual(ok_nac.status_code, 200)

        # 5. El dueño activa Otay Mesa y Mexicali en Mi Empresa
        save_ports = self.client.put("/api/company/ports", json={"ports": ["OTAY", "MEX"]})
        self.assertEqual(save_ports.status_code, 200)

        # 6. Ahora viaje por Otay Mesa -> DEBE PASAR con 200
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
        - Solo login con CRUCELINE_SECRET permite entrar.
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


if __name__ == "__main__":
    unittest.main()
