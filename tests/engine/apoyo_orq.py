"""Ayudas de prueba propias de ``estado``/``ejecutor``/``cerrar``/``orq`` (B1a).

Reutiliza ``tests/engine/apoyo.py`` (``crear_empresa``, ``par_de_claves``, ``PruebaBase``) para no
repetir ``limites.yaml``/``parametros.yaml``/claves Ed25519 de prueba, y agrega lo propio de este
alcance: un «pre-brief» válido (es-ES, EUR, como la fixture de límites) y helpers para construir
rondas de Maker+QA grabadas a partir de los artefactos ya válidos de ``ofertas/_ejemplo/``.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from scripts.validar_esquemas import cargar_json

RAIZ_REPO = Path(__file__).resolve().parents[2]
EJEMPLO = RAIZ_REPO / "ofertas" / "_ejemplo"

_SHA_DUMMY = "sha256:" + "a" * 64
_HMAC_DUMMY = "hmac-sha256:" + "b" * 64


def pre_brief(*, nivel_autonomia: str = "N4", slug: str = "prueba-orq") -> dict:
    """Un brief YA «firmado» (hash/aprobado_por de relleno) pero SIN oferta_id/familia_id/creado_en
    (los asigna ``orq.crear``). Mercado es-ES/EUR, como ``tests/fixtures/engine/empresa_prueba/limites.yaml``.
    ``slug`` distingue el CONTENIDO de dos briefs (``orq.crear`` es idempotente por contenido: dos
    briefs iguales devuelven el mismo ``oferta_id``; para forzar ofertas distintas, cambiar ``slug``)."""
    return {
        "schema_version": "1.1.0", "slug": slug, "version": "v1", "origen_version": "humano",
        "mercado_objetivo": {"locale": "es-ES", "paises_segmentacion": ["ES"], "moneda_cobro": "EUR", "es_hipotesis": True},
        "nichos": {"permitidos": ["dinero"], "subnichos_prohibidos": []},
        "precio_rango": {"min": {"monto": 900, "moneda": "EUR"}, "max": {"monto": 2900, "moneda": "EUR"}},
        "presupuesto": {"test_total_max": {"monto": 30000, "moneda": "EUR"}, "test_diario_max": {"monto": 5000, "moneda": "EUR"},
                       "ia_max": {"monto": 3000, "moneda": "EUR"}},
        "apetito_riesgo": "conservador", "ventana_test_dias": 10, "nivel_autonomia": nivel_autonomia, "reembolso_dias": 14,
        "politica_ia_creativos": "declarar_siempre", "cuenta_meta_id": "act_100000000000001", "dominio": "prueba-orq.example",
        "canal_alertas": "correo del dueño", "ventana_veto_min": 60, "supuestos": ["[SUPUESTO] fixture de prueba de orq"],
        "hash": _SHA_DUMMY, "aprobado_por": {"tipo": "humano", "id": "dueno", "fecha": "2026-11-06T08:30:00Z", "firma": _HMAC_DUMMY},
    }


def escribir_pre_brief(ruta: Path, *, nivel_autonomia: str = "N4") -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(yaml.safe_dump(pre_brief(nivel_autonomia=nivel_autonomia), sort_keys=False, allow_unicode=True), encoding="utf-8")
    return ruta


def candidatos_ejemplo(*, variante: str = "a") -> dict:
    """Copia de ``ofertas/_ejemplo/01-descubrimiento/candidatos.json``; ``variante="b"`` cambia un
    campo cosmético (no estructural) para producir otro ``hash_salida`` sin romper el esquema."""
    datos = cargar_json(EJEMPLO / "01-descubrimiento" / "candidatos.json")
    if variante == "b":
        datos = copy.deepcopy(datos)
        datos["candidatos"][1]["score_ajustado"] = datos["candidatos"][1]["score_ajustado"] + 1
    return datos


def mercado_ejemplo() -> dict:
    return cargar_json(EJEMPLO / "mercado.json")


def _qa_minimo(*, etapa: str, version: str, ronda: int, veredicto: str, oferta_id: str,
               artefacto_ref: str, entradas: Mapping[str, str] | None = None) -> dict:
    """Un ``qa.json`` mínimo pero válido contra ``qa.schema.json`` (ver contratos/qa.schema.json)."""
    return {
        "schema_version": "1.0.0", "ambito": "oferta", "oferta_id": oferta_id, "periodo": None,
        "etapa": etapa, "version": version, "ronda": ronda, "creado_en": "2026-11-06T09:30:00Z",
        "skill_version_qa": "0.1.0", "skill_version_maker": "0.1.0", "artefacto_ref": artefacto_ref,
        "artefacto_sha256": _SHA_DUMMY, "entradas": dict(entradas or {}), "veredicto": veredicto,
        "puntaje_global": "4.0", "umbral": "3.0",
        "items": [{"item_id": "R1", "nombre": "cumple el esquema", "puntaje": 4, "evidencia": "validado contra el esquema"}],
        "checks_l1": [{"check_id": "L1-01", "resultado": "pass", "detalle": "fixture de prueba"}],
        "simulaciones_l3": [], "hallazgos": [],
        "justificacion_sin_hallazgos": "Fixture de prueba de B1a: sin hallazgos porque el contenido es de ejemplo fijo.",
        "cambios_aplicados": [], "mejoras_propuestas": [], "riesgos_residuales": [], "aprendizajes_para_skill": [], "x1": None,
    }


def escribir_arbol(destino_base: Path, *, archivos: Mapping[str, dict | bytes]) -> Path:
    """Escribe ``destino_base/<rel>`` para cada archivo (sin envoltura ``salida/``): la forma que
    espera ``orq.ingresar --desde DIR`` (y la base de ``escribir_ronda``)."""
    for rel, contenido in archivos.items():
        destino = destino_base / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(contenido, bytes):
            destino.write_bytes(contenido)
        else:
            destino.write_text(json.dumps(contenido, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino_base


def escribir_ronda(ronda_dir: Path, *, archivos: Mapping[str, dict | bytes], qa: dict | None) -> None:
    """Escribe ``ronda_dir/salida/<rel>`` para cada archivo y, si ``qa`` no es ``None``, ``ronda_dir/qa.json``."""
    escribir_arbol(ronda_dir / "salida", archivos=archivos)
    if qa is not None:
        ronda_dir.mkdir(parents=True, exist_ok=True)
        (ronda_dir / "qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")


def fixture_etapa_simple(base_dir: Path, *, oferta_id: str, etapa: str, rel: str, contenido: dict,
                         veredictos: list[str], version: str = "v1") -> Path:
    """Fixture de una etapa de UN solo archivo con ``len(veredictos)`` rondas (p. ej. ``["FAIL", "PASS"]``)."""
    for indice, v in enumerate(veredictos, start=1):
        ronda = base_dir / f"ronda-{indice}"
        qa = _qa_minimo(etapa=etapa, version=version, ronda=min(indice, 2), veredicto=v, oferta_id=oferta_id, artefacto_ref=rel)
        escribir_ronda(ronda, archivos={rel: contenido}, qa=qa)
    return base_dir
