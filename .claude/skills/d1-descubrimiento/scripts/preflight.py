#!/usr/bin/env python3
"""Preflight de D1 (paso 0 del SOP). Solo lectura: no escribe, no usa la red, no toca el freno.

Uso (desde la raíz, con ``.venv/bin/python``):
  .claude/skills/d1-descubrimiento/scripts/preflight.py [--locale es-MX] [--modo A|B|C|D] [--sello-esperado SELLO]
                                                          [--raiz DIR] [--json]

Comprueba lo que la spec §4 paso 0 exige y que hoy se puede decidir leyendo archivos:
  P-01 ``empresa/PAUSA`` ausente · P-02 ``limites.yaml`` fail-closed (``evaluar_limites(..., "descubrir")`` + ``locales_permitidos`` +
  ``max_consultas_biblioteca``) · P-03 ``empresa/infra/estado.json`` VERDE y < 6 h (si existe) · P-04 freno compartido de captura (informa;
  el Maker no lo levanta) · P-05 parámetros de D1 · P-06 sello de reglas del Modo D · P-07 ``locales_activos.yaml`` de M1 ·
  P-08 veredicto del preflight de código de S-B (``scripts.modelado.preflight_descubrir``), solo informativo.
Salida: 0 puede seguir · 5 hay un BLOQUEA (falla cerrado; el Maker escala al dueño y no consulta). Los AVISO no bloquean.
No decide por el Maker si un límite en ``null`` se acepta como tope de sesión: eso lo escribe el dueño en el encargo (references/modo-d-rutina.md §0).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[4]
if str(RAIZ_REPO) not in sys.path:
    sys.path.insert(0, str(RAIZ_REPO))

PARAMETROS_D1 = ("umbral_score_min", "evidencia_min_fuentes", "evidencia_min_tipos", "antiguedad_max_evidencia_meses", "sim_dup_bloqueo",
                 "sim_penalizacion_desde", "top1_estable_min_pct", "max_por_nicho_topn", "caducidad_banco_dias",
                 "cuota_min_exploracion_por_macro_nicho_pct", "anunciante_sostenido_conceptos_min", "anunciante_sostenido_dias_min")


def cargar_yaml(ruta: Path):
    import yaml
    try:
        return yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None


def revisar(raiz: Path, locale: str | None, modo: str | None, sello_esperado: str | None,
            via: str = "conector") -> list[dict[str, str]]:
    from scripts.validar_esquemas import evaluar_limites, infra_verde  # noqa: PLC0415

    r: list[dict[str, str]] = []

    def add(id_: str, estado: str, detalle: str) -> None:
        r.append({"id": id_, "estado": estado, "detalle": detalle})

    # P-01
    if (raiz / "empresa" / "PAUSA").exists():
        add("P-01", "BLOQUEA", "empresa/PAUSA existe: no se hace nada, se cancelan los barridos y se avisa")
    else:
        add("P-01", "OK", "empresa/PAUSA ausente")
    # P-02
    limites = cargar_yaml(raiz / "empresa" / "limites.yaml")
    if not isinstance(limites, dict):
        add("P-02", "BLOQUEA", "empresa/limites.yaml no se pudo cargar")
    else:
        res = evaluar_limites(limites, "descubrir")
        faltan = list(res.faltantes)
        if limites.get("max_consultas_biblioteca") is None and "max_consultas_biblioteca" not in faltan:
            faltan.append("max_consultas_biblioteca")
        locales = limites.get("locales_permitidos") or []
        if not locales:
            faltan.append("locales_permitidos (vacío = ningún locale permitido)")
        elif locale and locale not in locales:
            faltan.append(f"locale {locale} fuera de locales_permitidos")
        if faltan:
            add("P-02", "BLOQUEA", "límites del dueño sin fijar o incumplidos: " + ", ".join(faltan)
                + ". El Maker no consulta el conector ni gasta cuota; lo pide al dueño (solo él escribe limites.yaml)")
        else:
            add("P-02", "OK", "límites del dueño suficientes para descubrir")
        if limites.get("nivel_max_lanzable") is None:
            add("P-02b", "AVISO", "limites.nivel_max_lanzable es null o no existe: SOLO VERDE (fail-closed; limites 1.3.0); nada amarillo llega a la lista")
        else:
            add("P-02b", "OK", f"nivel_max_lanzable = {limites['nivel_max_lanzable']}")
        if limites.get("hojas_pausadas"):
            add("P-02c", "AVISO", f"hojas pausadas por el dueño: {', '.join(map(str, limites['hojas_pausadas']))} (no se ofrecen candidatos de esas hojas)")
    # P-03
    infra = raiz / "empresa" / "infra" / "estado.json"
    if not infra.is_file():
        add("P-03", "AVISO", "empresa/infra/estado.json no existe [PENDIENTE: D0]: en sesión interactiva el dueño lo acepta por escrito en el encargo; desatendido, no se corre")
    else:
        try:
            ok, motivo = infra_verde(json.loads(infra.read_text(encoding="utf-8")), lambda: _dt.datetime.now(_dt.timezone.utc), 6)
        except (OSError, ValueError, KeyError) as exc:
            ok, motivo = False, f"ilegible ({type(exc).__name__})"
        add("P-03", "OK" if ok else "BLOQUEA", f"infra/estado.json: {motivo}")
    # P-04
    freno = raiz / "empresa" / "captura" / "freno.json"
    if freno.exists():
        try:
            f = json.loads(freno.read_text(encoding="utf-8"))
            motivo = str(f.get("motivo", "?"))[:80]
            ts = str(f.get("ts", "?"))
        except (OSError, ValueError):
            motivo, ts = "ilegible", "?"
        add("P-04", "AVISO", f"FRENO COMPARTIDO PUESTO ({ts}: {motivo}). Prohibido todo lo que use Chrome (captura.py, enlaces.py, ruta_d); "
            "el Modo D sigue con material aportado a mano. Solo una persona lo borra; el Maker ni lo borra ni lo evade")
    else:
        add("P-04", "OK", "sin freno de captura (igual, el Maker nunca lanza la captura: solo el CLI con sus frenos y por orden expresa del dueño)")
    # P-05
    parametros = cargar_yaml(raiz / "empresa" / "parametros.yaml") or {}
    grupo = (parametros.get("grupos") or {}).get("descubrimiento") or {}
    faltan = [k for k in PARAMETROS_D1 if k not in grupo]
    add("P-05", "BLOQUEA" if faltan else "OK", ("faltan en parametros.yaml: " + ", ".join(faltan)) if faltan else "parámetros de D1 presentes")
    integrados = sum(1 for k in grupo if k.startswith("modelado_"))
    if modo in (None, "D"):
        if integrados == 0:
            add("P-05b", "AVISO", "los modelado_* NO están integrados en parametros.yaml [PENDIENTE: dueño/CT-4]: usar --parametros scripts/modelado/parametros_modelado.propuesta.yaml")
        else:
            add("P-05b", "OK", f"{integrados} claves modelado_* integradas")
    # P-06
    if sello_esperado and modo in (None, "D"):
        try:
            from scripts.modelado import puntaje_modelar as pm  # noqa: PLC0415
            propuesta = raiz / "scripts" / "modelado" / "parametros_modelado.propuesta.yaml"
            en_uso = pm.sello_reglas(pm.cargar_parametros(propuesta if not integrados else raiz / "empresa" / "parametros.yaml"))
            add("P-06", "OK" if en_uso == sello_esperado else "BLOQUEA",
                "sello de reglas = el aprobado" if en_uso == sello_esperado else f"sello de reglas en uso {en_uso[:19]}… ≠ aprobado: no se calcula (código 4 del CLI)")
        except Exception as exc:  # noqa: BLE001
            add("P-06", "BLOQUEA", f"no se pudo calcular el sello de reglas ({type(exc).__name__})")
    elif modo in (None, "D"):
        add("P-06", "AVISO", "sin --sello-esperado: pasa el sello aprobado (spec §12.7) para verificarlo")
    # P-08: el preflight de código de S-B (PAUSA, freno, infra, límites sellados); informa, no decide por este script
    try:
        from scripts.modelado.preflight_descubrir import comprobar_descubrir  # noqa: PLC0415
        try:
            # `via` es OBLIGATORIA en S-B (D1d): «conector» (barrido por ads_library_search; el freno de captura NO bloquea)
            # o «captura_web» (Chrome; el freno SÍ bloquea). PAUSA, infraestructura y límites bloquean ambas vías.
            comprobar_descubrir(raiz, via=via)
            add("P-08", "OK", f"scripts.modelado.preflight_descubrir (vía {via}): verde")
        except TypeError as exc:  # firma cambiada: no la ocultes como «bloqueo» del dueño
            add("P-08", "BLOQUEA", f"scripts.modelado.preflight_descubrir tiene otra firma ({str(exc)[:160]}): actualizar este script")
        except Exception as exc:  # noqa: BLE001 - ErrorBloqueado (4) / ErrorLimite (5) / ErrorUso (2): se informa su mensaje
            add("P-08", "AVISO", f"scripts.modelado.preflight_descubrir (vía {via}) bloquearía la corrida: {str(exc)[:200]}")
    except ImportError:
        add("P-08", "AVISO", "scripts/modelado/preflight_descubrir.py no existe [PENDIENTE: S-B]: este preflight es el único candado")
    # P-07
    if not (raiz / "empresa" / "mercados" / "locales_activos.yaml").is_file():
        add("P-07", "AVISO", "empresa/mercados/locales_activos.yaml no existe [PENDIENTE: M1]: el locale y los países salen del brief; el dueño confirma en el encargo")
    else:
        add("P-07", "OK", "locales_activos.yaml presente")
    return r


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--locale")
    ap.add_argument("--modo", choices=("A", "B", "C", "D"))
    ap.add_argument("--sello-esperado")
    ap.add_argument("--raiz", type=Path, default=RAIZ_REPO)
    ap.add_argument("--via", choices=("conector", "captura_web"), default="conector",
                    help="vía de la corrida: conector (barrido, sin Chrome; el freno de captura no bloquea) o captura_web (Chrome; el freno bloquea)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    resultado = revisar(a.raiz, a.locale, a.modo, a.sello_esperado, a.via)
    bloquea = any(x["estado"] == "BLOQUEA" for x in resultado)
    if a.json:
        print(json.dumps({"puede_seguir": not bloquea, "checks": resultado}, ensure_ascii=False, indent=2))
    else:
        for x in resultado:
            print(f"[{x['estado']}] {x['id']}: {x['detalle']}")
        print("-> " + ("BLOQUEADO: escalar al dueño con las preguntas bloqueantes; no consultar" if bloquea else "puede seguir (revisa los AVISO)"))
    return 5 if bloquea else 0


if __name__ == "__main__":
    sys.exit(main())
