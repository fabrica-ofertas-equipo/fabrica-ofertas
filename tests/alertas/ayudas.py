"""Ayudas comunes de las pruebas de alertas, semáforo e informe: una raíz temporal mínima que se arma archivo por archivo."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from dashboard.api_base import Ctx

AHORA = _dt.datetime(2026, 11, 7, 8, 30, 0, tzinfo=_dt.timezone.utc)
AHORA_Z = "2026-11-07T08:30:00Z"
RAIZ_REPO = Path(__file__).resolve().parents[2]

PARAMETROS = """\
schema_version: "1.0.0"
version: 1
grupos:
  infra:
    hc_preflight_vigencia_horas: {valor: 6, unidad: horas, hipotesis: true}
  watchdog:
    latido_max_min: {valor: 30, unidad: minutos, hipotesis: true}
"""
LIMITES_VACIOS = """\
schema_version: "1.3.0"
moneda_limites: null
gasto_diario_global: null
perdida_neta_acumulada_max: null
capital_en_riesgo_total: null
cuentas_permitidas: []
nivel_max_lanzable: null
sello: null
"""
LIMITES_COMPLETOS = """\
schema_version: "1.3.0"
moneda_limites: USD
gasto_diario_global: 30000
perdida_neta_acumulada_max: 300000
capital_en_riesgo_total: 500000
cuentas_permitidas: [act_1234]
nivel_max_lanzable: null
sello: {hash: "sha256:aa", firma: "ed25519:bb", clave_id: k1}
"""


def item(id_: str, estado: str = "VERDE", critico: bool = True, mensaje: str = "ok") -> dict[str, Any]:
    return {"id": id_, "bloque": id_[0], "estado": estado, "evidencia_ruta": "empresa/infra/x.json", "medido_en": "2026-11-07T08:00:00Z",
            "expira_en": "2026-11-07T14:00:00Z", "critico": critico, "mensaje": mensaje}


def estado_infra(semaforo: str = "VERDE", modo: str = "vivo", generado_en: str = "2026-11-07T07:00:00Z", items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"schema_version": "1.1.0", "modo": modo, "semaforo": semaforo, "items": items if items is not None else [item("K-01")],
            "generado_en": generado_en, "valido_hasta": "2026-11-07T13:00:00Z", "firma": "hmac-sha256:" + "0" * 64}


ITEMS_BUENOS = [item("M-02"), item("M-03"), item("E-01"), item("S-02"), item("S-01"), item("S-07"), item("K-01")]


class Base(unittest.TestCase):
    """Raíz temporal vacía (solo las carpetas) y sockets bloqueados."""

    def setUp(self) -> None:
        super().setUp()
        p = mock.patch("socket.socket", side_effect=AssertionError("prueba sin red: socket.socket está bloqueado"))
        p.start()
        self.addCleanup(p.stop)
        self.raiz = Path(tempfile.mkdtemp(prefix="alertas-prueba-")).resolve()
        self.addCleanup(shutil.rmtree, self.raiz, True)
        (self.raiz / "empresa").mkdir()
        (self.raiz / "ofertas").mkdir()

    def ctx(self, ahora: _dt.datetime = AHORA) -> Ctx:
        return Ctx(self.raiz, ahora=lambda: ahora)

    def poner(self, rel: str, contenido: str | bytes | dict | list) -> Path:
        destino = self.raiz / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(contenido, (dict, list)):
            contenido = json.dumps(contenido)
        if isinstance(contenido, bytes):
            destino.write_bytes(contenido)
        else:
            destino.write_text(contenido, encoding="utf-8")
        return destino

    def jsonl(self, rel: str, filas: list[dict[str, Any]]) -> Path:
        return self.poner(rel, "".join(json.dumps(f) + "\n" for f in filas))

    def base_sana(self) -> None:
        """Todo en orden: límites firmados, chequeo real y reciente, dos canales probados, planificador con señal reciente, cuenta de Meta."""
        self.poner("empresa/parametros.yaml", PARAMETROS)
        self.poner("empresa/limites.yaml", LIMITES_COMPLETOS)
        self.poner("empresa/infra/estado.json", estado_infra(items=ITEMS_BUENOS))
        self.poner("empresa/avisos.yaml", "canales:\n  - {tipo: telegram, estado: probado}\n  - {tipo: correo, estado: probado}\n")
        self.poner("empresa/infra/latidos.json", {"trabajos": [{"id": "informe", "ultimo_latido": "2026-11-07T08:25:00Z"}, {"id": "escalera", "ultimo_latido": "2026-11-07T08:10:00Z"}]})

    def oferta(self, oferta_id: str = "OF-202611-91", *, fase: str = "en_construccion", gate: str | None = None, estado: bool = True) -> None:
        if not estado:
            (self.raiz / "ofertas" / oferta_id).mkdir(parents=True, exist_ok=True)
            return
        etapas = {"M1": {"estado": "aprobado", "gate_pendiente": False}}
        if gate:
            etapas[gate] = {"estado": "en_QA", "gate_pendiente": True, "gate": "H"}
        self.poner(f"ofertas/{oferta_id}/estado.json", {"schema_version": "1.0.0", "oferta_id": oferta_id, "fase": fase, "nivel": "N0", "pausa": False, "etapas": etapas,
                                                         "actualizado_en": "2026-11-06T08:30:00Z", "gasto": {"hoy": {"monto": 0, "moneda": "USD"}, "acumulado": {"monto": 0, "moneda": "USD"}}})

    def hash_arbol(self) -> str:
        h = hashlib.sha256()
        for d, ds, fs in os.walk(self.raiz):
            ds.sort()
            for f in sorted(fs):
                p = Path(d) / f
                h.update(str(p.relative_to(self.raiz)).encode())
                h.update(p.read_bytes())
        return h.hexdigest()

    def arbol(self) -> set[str]:
        return {str(Path(d, f).relative_to(self.raiz)) for d, _, fs in os.walk(self.raiz) for f in fs}
