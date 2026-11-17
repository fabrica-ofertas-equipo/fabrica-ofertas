"""Regenera negocio.json (fixture de tests/dashboard/test_web_negocio.mjs) desde el libro de prueba de test_servidor_negocio.py.

El fixture NO es el libro tal cual: suma anuncios, un cambio programado y una oferta pausada para cubrir el render.
Ejecutar desde la raíz: .venv/bin/python tests/fixtures/dashboard/negocio/generar_fixture.py
"""
import copy
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ))
from dashboard import negocio as N  # noqa: E402
from tests.dashboard.test_servidor_negocio import AHORA, LIBRO  # noqa: E402

libro = copy.deepcopy(LIBRO)
libro["tests"][0]["ficha"]["campanas"][0].update({"nombre": "MX | Kit Uno", "leido": "2026-11-12T20:15-03:00", "conjuntos": [{"id": "8", "nombre": "MX abierto", "estado": "ACTIVE"}]})
libro["tests"][0]["anuncios"] = {"leido": "2026-11-12T23:25-03:00", "lista": [
    {"id": "9", "nombre": "A01 | <img src=x onerror=alert(1)>", "conjunto": "MX abierto", "estado": "ACTIVE", "gasto_usd": 20, "impresiones": 900, "clics_enlace": 30, "ctr_pct": 3.33, "inicios_pago_meta": 6, "compras_meta": 4, "valor_compras_meta_usd": 60, "video_p25": 270, "video_p100": 90},
    {"id": "10", "nombre": "A02 | flojo", "conjunto": "MX R3", "estado": "ACTIVE", "gasto_usd": 26, "impresiones": 800, "clics_enlace": 10, "inicios_pago_meta": 0, "compras_meta": 0},
    {"id": "11", "nombre": "A03 | nuevo", "conjunto": "MX R3", "estado": "ADSET_PAUSED", "gasto_usd": 0, "impresiones": 0, "clics_enlace": 0, "compras_meta": 0}]}
libro["tests"][0]["programado"] = [{"cuando": "2026-11-13T00:00:00-06:00", "que": "Sube a 65 USD por día y entra el conjunto R3", "corto": "65 USD/día + conjunto R3"}]
libro["tests"][2]["estado"] = "pausado"
d = N.calcular(libro, AHORA)
for o in d["ofertas"]:
    o["documentos"] = [{"titulo": "Expediente del funnel", "ruta": f"ofertas/_funnels/{o['nombre']}/FUNNEL.md"}]
d["libro"] = {"ruta": "ofertas/_funnels/libro-de-tests.json", "modificado": "2026-11-12T23:00:00Z", "version": 2}
d.pop("avisos")
(Path(__file__).parent / "negocio.json").write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("negocio.json:", [(o["nombre"], o["etapa"]["corto"], o["backend"]["texto"]) for o in d["ofertas"]])
