#!/usr/bin/env python3
"""Próximo paso de una oferta, determinista y de SOLO LECTURA (ayuda detallada; `engine.orq siguiente` existe y manda si difiere).

Lee `ofertas/<id>/estado.json`, `contratos/gates.json`, `empresa/autonomia.yaml`, `empresa/PAUSA` y `00-brief.yaml`; NO escribe nada, NO
ejecuta nada, NO firma. Dice qué etapa toca, qué gate rige, qué falta y el comando EXACTO que correría el dueño (o el motor).
`engine/orq.py` existe: manda el motor (`orq siguiente`/`orq estado`); si difieren, se registra como conflicto y manda el motor.
Los comandos que emite son los de la CLI REAL (SC-7): `orq firmar` exige `--hash-objetivo` y `--clave-privada` (la ruta la pone el dueño); `orq ejecutar`
solo corre `--modo fixture --fixture DIR`; `reanudar` y `activar --live` no están en la CLI (los avisos lo dicen).

Uso (raíz del repositorio):
    .venv/bin/python .claude/skills/o0-lanzar-oferta/scripts/proximo_paso.py (--oferta OF-AAAAMM-NN | --estado RUTA) [--raiz RAIZ] [--autonomia RUTA] [--json]
Salida: 0 hay un próximo paso (o la oferta está en operación) · 3 estado ilegible o inválido · 2 uso.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CADENA = ["D1", "M1", "D2", "D3", "D4", "D5", "D6", "D7"]
POSTERIORES = ["D8", "D9", "D10"]
DEPS = {"D1": [], "M1": ["D1"], "D2": ["D1", "M1"], "D3": ["D2"], "D4": ["D3"], "D5": ["D3", "D4"], "D6": ["D3", "D5"], "D7": ["D5", "D6"],
        "D8": ["D7"], "D9": ["D8"], "D10": ["D4", "D5"]}
NIVELES = ["N0", "N1", "N2", "N3", "N4"]
RIGOR = {"A": 0, "S": 1, "H": 2}
# Respaldo de `scripts.validar_esquemas.ACCIONES_GATE_MINIMAS` / `limites.acciones_gate_humano` (siempre H en cualquier nivel).
GATE_H_SIEMPRE = {"activar_campana", "reactivar_tras_pausa", "subir_presupuesto_sobre_tope", "cambiar_limites", "cambiar_entidad_stripe",
                  "lanzamiento_pais_idioma_nuevo"}
ORQ = ".venv/bin/python -m engine.orq"
# La ruta de la clave privada la pone el dueño en su terminal: nunca en un chat ni en el repositorio.
CLAVE_PRIVADA = "<RUTA_DE_TU_CLAVE_PRIVADA>"
FIXTURE_DIR = "<DIR_CON_LAS_RONDAS_GRABADAS>"
# Avisos que acompañan a cada acción cuando el comando usa algo que la CLI aún no tiene o tiene a medias.
AVISOS_POR_ACCION = {
    "ejecutar": "[PENDIENTE: SB-9] `orq ejecutar` solo corre `--modo fixture --fixture DIR` (rondas grabadas); `--modo dry-run|live` con `agentes.runner` no está integrado y la CLI lo rechaza (salida 4)",
    "reejecutar": "[PENDIENTE: SB-9] `orq ejecutar` solo corre `--modo fixture --fixture DIR`; `--modo dry-run|live` no está integrado",
    "firmar": "`orq firmar` exige `--hash-objetivo` y `--clave-privada`: la ruta de la clave la pones tú en tu terminal (nunca en un chat ni en el repositorio). Tras firmar, repite el mismo `ingresar`/`ejecutar` para que el motor aplique la orden",
    "orden_humana": "`orq firmar` exige `--hash-objetivo` y `--clave-privada`: la ruta de la clave la pones tú en tu terminal (nunca en un chat ni en el repositorio)",
    "activar": "[PENDIENTE: B5] `orq activar --live` no está integrado: la CLI lo rechaza (salida 4) y sin `--live` solo simula el guard y mueve la fase a `en_test` sin tocar Meta (no lo uses para activar). Antes, la orden: `orq firmar --accion activar_campana --hash-objetivo <hash_config> --clave-privada <RUTA>`",
    "ingresar": "`orq ingresar` acepta `--origen humano|sesion_code` pero hoy el motor no lo propaga (el ingreso queda como `humano`) [PENDIENTE: S-B]; los costos manuales (créditos) tampoco se asientan en `empresa/costos.jsonl` [PENDIENTE: SB-10]",
    "pausa": "`orq reanudar` no está en la CLI (solo la API de Python con firma verificada y preflight VERDE) [PENDIENTE]",
}

# Etapas cuyo Maker necesita conectores MCP que solo existen en la sesión INTERACTIVA del dueño (docs/09 H2: `claude -p` no los carga).
# Hasta N2 se hacen en Code y entran con `ingresar --origen sesion_code`; desde N3 la alternativa por API/script propio es [PENDIENTE] (W6 de la auditoría).
INTERACTIVAS = {"D1": "Biblioteca de Anuncios (ads_library_search) y fuentes con muro", "D2": "Biblioteca de Anuncios (ads_library_search)",
                "D6": "Higgsfield (generate_*, ads_studio_*: cotizar y aprobar créditos)"}


def _cargar(ruta: Path):
    import yaml  # PyYAML ya está en el .venv del proyecto
    texto = ruta.read_text(encoding="utf-8")
    return json.loads(texto) if ruta.suffix == ".json" else yaml.safe_load(texto)


def nivel_efectivo(estado: dict, etapa: str, aut: dict | None) -> str:
    """El MENOR entre el nivel de la oferta, el de la etapa en estado.json y el de autonomia.yaml (docs/contratos.md §2)."""
    niveles = [estado["nivel"], estado["etapas"][etapa]["nivel"]]
    if aut:
        n = ((aut.get("nivel_por_etapa") or {}).get(etapa) or {}).get("nivel")
        niveles.append(n if n in NIVELES else "N0")  # sin dato de autonomía: lo más estricto
    return min(niveles, key=NIVELES.index)


def gate_efectivo(gates: dict, estado: dict, etapa: str, aut: dict | None) -> tuple[str, str]:
    """(gate, nivel efectivo): el más estricto entre gates.json (por nivel efectivo) y el gate guardado en estado.json."""
    nivel = nivel_efectivo(estado, etapa, aut)
    g = gates["entradas"][f"etapa:{etapa}"]["gate"][nivel]
    guardado = estado["etapas"][etapa].get("gate")
    if guardado in RIGOR and RIGOR[guardado] > RIGOR[g]:
        g = guardado
    return g, nivel


def _cmd(*partes: str) -> str:
    return " ".join([ORQ, *partes])


def _firmar(oid: str, etapa: str, estado: dict) -> str:
    """Comando de firma de un gate H de etapa, con los flags que la CLI exige (hash_salida de la etapa si ya existe)."""
    h = (estado["etapas"].get(etapa) or {}).get("hash_salida") or "<hash_salida de la etapa>"
    return _cmd("firmar", "--oferta", oid, "--etapa", etapa, "--como", "dueno", "--hash-objetivo", h, "--clave-privada", CLAVE_PRIVADA)


def _ejecutar(oid: str, etapa: str) -> str:
    return _cmd("ejecutar", "--oferta", oid, "--etapa", etapa, "--modo", "fixture", "--fixture", FIXTURE_DIR)


def resumen_etapas(estado: dict, gates: dict, aut: dict | None) -> list[dict]:
    filas = []
    for e in CADENA + POSTERIORES:
        et = estado["etapas"][e]
        g, n = gate_efectivo(gates, estado, e, aut)
        filas.append({"etapa": e, "estado": et["estado"], "gate": g, "nivel": n, "gate_pendiente": et["gate_pendiente"], "obsoleta": et["obsoleta"]})
    return filas


def _obsoleta_por_hash(estado: dict, etapa: str) -> str | None:
    et = estado["etapas"][etapa]
    for dep in DEPS[etapa]:
        vigente = estado["etapas"][dep]["hash_salida"]
        if et["estado"] == "aprobado" and et["entradas"].get(dep) not in (None, vigente):
            return f"{etapa} consumió {dep} con un hash que ya no es el vigente"
    return None


def proximo(estado: dict, gates: dict, aut: dict | None, *, pausa: dict | None, brief: dict | None, acciones_h: set[str]) -> dict:
    """Decide el próximo paso y agrega el aviso de CLI de su acción (ver AVISOS_POR_ACCION)."""
    r = _proximo(estado, gates, aut, pausa=pausa, brief=brief, acciones_h=acciones_h)
    if r["accion"] in AVISOS_POR_ACCION:
        r["avisos"].append(AVISOS_POR_ACCION[r["accion"]])
    return r


def _proximo(estado: dict, gates: dict, aut: dict | None, *, pausa: dict | None, brief: dict | None, acciones_h: set[str]) -> dict:
    oid = estado["oferta_id"]
    base = {"oferta_id": oid, "fase": estado["fase"], "nivel_oferta": estado["nivel"], "etapas": resumen_etapas(estado, gates, aut),
            "avisos": ["Las excepciones que fuerzan H en cualquier nivel (candidato amarillo-b, primer idioma de un macro-nicho, nombre de marca nuevo, "
                       "precio fuera de rango…) no se calculan aquí: ver references/cadena-y-gates.md §3"]}
    if pausa is not None or estado["pausa"]:
        return {**base, "accion": "pausa", "etapa": None, "gate": None, "espera_firma": False, "comando": None,
                "motivo": "Hay PAUSA (kill switch): no se ejecuta ni se activa nada. Solo el dueño la levanta tras revisar la causa; reactivar una campaña pausada es H en todo nivel.",
                "falta": ["decisión del dueño sobre la causa de la pausa"]}
    if estado["fase"] == "borrador":
        firmado = bool(brief and (brief.get("aprobado_por") or {}).get("firma"))
        if not firmado:
            # La firma del brief va ANTES de `orq crear` (gate H del paso 3) y `orq firmar` no admite etapa O0 (orden_firmada.etapa): [PENDIENTE: LT-54]; no se inventa un comando que falla.
            return {**base, "accion": "firmar", "etapa": "O0", "gate": "H", "espera_firma": True, "comando": None,
                    "motivo": "El brief no tiene firma humana (gate H de O0 hasta N3); nada avanza sin ella. La firma del brief va antes de `orq crear` y su mecanismo [PENDIENTE: LT-54] no está en `orq firmar` (la orden firmada no admite etapa O0).",
                    "falta": ["firma Ed25519 del dueño sobre el hash del brief"]}
    for e in CADENA:
        et = estado["etapas"][e]
        g, nivel = gate_efectivo(gates, estado, e, aut)
        if e == "M1" and RIGOR[g] < RIGOR["H"] and "lanzamiento_pais_idioma_nuevo" in acciones_h:
            base["avisos"].append("M1: si es el primer lanzamiento en este país o idioma, el gate es H aunque la tabla diga S (limites.acciones_gate_humano)")
        desc = {"etapa": e, "gate": g, "nivel_efectivo": nivel}
        rancia = et["obsoleta"] or _obsoleta_por_hash(estado, e)
        if et["estado"] == "aprobado" and not rancia:
            continue
        if rancia:
            return {**base, **desc, "accion": "reejecutar", "espera_firma": False, "falta": [f"volver a producir {e}"],
                    "motivo": f"{e} está obsoleta (una entrada aguas arriba cambió; la campaña activa, si la hubiera, queda pausada). La versión previa se conserva.",
                    "comando": _ejecutar(oid, e) if (nivel != "N0" and e not in INTERACTIVAS)
                    else _cmd("ingresar", "--oferta", oid, "--etapa", e, "--desde", "<DIR>", "--origen", "humano" if nivel == "N0" else "sesion_code")}
        if et["estado"] == "pendiente":
            faltan = [d for d in DEPS[e] if estado["etapas"][d]["estado"] != "aprobado"]
            if faltan:
                return {**base, **desc, "accion": "esperar", "espera_firma": False, "comando": None, "falta": faltan,
                        "motivo": f"{e} espera a {', '.join(faltan)} (dependencias aprobadas y vigentes)."}
            if nivel == "N0":
                return {**base, **desc, "accion": "ingresar", "espera_firma": False, "falta": [f"hacer {e} a mano en la pestaña Code y entrarla a la máquina de estados"],
                        "motivo": f"{e} está en N0: la haces tú a mano con su skill; sin `ingresar` el estado no se mueve.",
                        "comando": _cmd("ingresar", "--oferta", oid, "--etapa", e, "--desde", "<DIR_CON_LOS_ARTEFACTOS>", "--origen", "humano")}
            if e in INTERACTIVAS:
                return {**base, **desc, "accion": "ingresar", "espera_firma": False, "requiere_sesion_interactiva": True,
                        "falta": [f"hacer {e} en la sesión Code con conectores y entrarla a la máquina de estados"],
                        "motivo": f"{e} usa {INTERACTIVAS[e]}: esos conectores solo existen en tu sesión interactiva (un `claude -p` desatendido no los carga). "
                                  + ("Desde N3 la alternativa por API propia es [PENDIENTE]." if nivel in ("N3", "N4") else "Hazla en Code con su skill y entra con `ingresar --origen sesion_code`."),
                        "comando": _cmd("ingresar", "--oferta", oid, "--etapa", e, "--desde", "<DIR_CON_LOS_ARTEFACTOS>", "--origen", "sesion_code")}
            return {**base, **desc, "accion": "ejecutar", "espera_firma": False, "falta": [f"correr el Maker de {e}"],
                    "motivo": f"{e} está pendiente y sus dependencias están aprobadas: la corre el motor. Hoy `orq ejecutar` solo admite `--modo fixture` (rondas grabadas); el modo con Maker real (dry-run, luego live) falta [PENDIENTE: SB-9].",
                    "comando": _ejecutar(oid, e)}
        if et["estado"] == "en_progreso":
            return {**base, **desc, "accion": "esperar", "espera_firma": False, "comando": _cmd("estado", "--oferta", oid), "falta": [f"fin de {e} (ronda {et['ronda_qa']}, intento {et['intentos']})"],
                    "motivo": f"{e} está en curso; si supera el timeout de parametros.orquestador.timeout_etapa_min pasa a bloqueado."}
        if et["estado"] == "en_QA":
            if et["gate_pendiente"] and g in ("H", "S"):
                que = "firma obligatoria" if g == "H" else "revisión por excepción (QA con notas o muestreo; con PASS limpio el motor aprueba solo)"
                return {**base, **desc, "accion": "firmar", "espera_firma": g == "H", "falta": [f"{que} de {e}"],
                        "motivo": f"{e} pasó QA y espera tu gate {g}. Revisa `ofertas/{oid}/qa/` y el artefacto antes de firmar (hash congelado: todo cambio = versión nueva).",
                        "comando": _firmar(oid, e, estado)}
            return {**base, **desc, "accion": "esperar", "espera_firma": False, "comando": _cmd("estado", "--oferta", oid), "falta": [f"veredicto del QA de {e}"],
                    "motivo": f"{e} está en QA (máximo parametros.orquestador.max_rondas_qa rondas; luego ESCALAR)."}
        if et["estado"] == "bloqueado":
            return {**base, **desc, "accion": "resolver_bloqueo", "espera_firma": False, "comando": _cmd("estado", "--oferta", oid),
                    "falta": ["causa del bloqueo"], "motivo": f"{e} bloqueada: {(et['bloqueo'] or {}).get('motivo', 'sin motivo registrado (anomalía)')}"}
        if et["estado"] == "escalado":
            return {**base, **desc, "accion": "orden_humana", "espera_firma": True, "falta": [f"decisión humana firmada sobre {e}"],
                    "motivo": f"{e} escalada (2 rondas con BLOQ/MAYOR, ESCALAR o veto de X1): sale solo por orden humana firmada tras leer qa/ y el veto.",
                    "comando": _firmar(oid, e, estado)}
    # D1..D7 aprobadas y vigentes
    if estado["fase"] in ("en_construccion", "listo_para_activar"):
        d = {"etapa": "D7", "gate": "H" if "activar_campana" in acciones_h else gate_efectivo(gates, estado, "D7", aut)[0]}
        if estado["fase"] == "en_construccion":
            return {**base, **d, "accion": "esperar", "espera_firma": False, "comando": _cmd("estado", "--oferta", oid),
                    "falta": ["campana.estado = aprobada, sello de X1 vigente, infra VERDE en modo vivo con menos de 6 h (el motor pasa la fase a listo_para_activar)"],
                    "motivo": "D1-D7 están aprobadas; antes de activar el motor exige preflight, sello de X1 y la compra real mínima (accion:compra_real_minima, H)."}
        return {**base, **d, "accion": "activar", "espera_firma": True, "falta": ["firma de accion:activar_campana y object_ids exactos"],
                "motivo": "Todo aprobado: activar es la única acción que gasta. Gate efectivo H hasta que el dueño decida D-02 (C-04: las seis acciones mínimas no se pueden quitar de limites.acciones_gate_humano); la ejecuta `orq activar`, nunca un LLM.",
                "comando": _cmd("activar", "--oferta", oid, "--object-ids", "<de 07-campana/ids_meta.json>", "--hash-config", "<de 07-campana/campana.json>", "--live")}
    return {**base, "accion": "operacion", "etapa": None, "gate": None, "espera_firma": False, "falta": [],
            "motivo": f"La oferta está en fase {estado['fase']}: la cadena de construcción terminó. Sigue D8 (ciclo diario), veredicto, D9 y cierre; ver references/cadena-y-gates.md §5.",
            "comando": _cmd("estado", "--oferta", oid)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--oferta", help="id de la oferta (lee ofertas/<id>/estado.json)")
    ap.add_argument("--estado", help="ruta de un estado.json (prueba/plantilla); el brief, si existe, es 00-brief.yaml de su carpeta")
    ap.add_argument("--raiz", default=None)
    ap.add_argument("--autonomia", default=None, help="por defecto empresa/autonomia.yaml; sin archivo se asume N0 (lo más estricto)")
    ap.add_argument("--json", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code not in (0, None) else 0
    if not a.oferta and not a.estado:
        print("ERROR: pasa --oferta o --estado", file=sys.stderr)
        return 2
    raiz = Path(a.raiz) if a.raiz else next(p for p in Path(__file__).resolve().parents if (p / "contratos").is_dir() and (p / "empresa").is_dir())
    try:
        ruta_estado = Path(a.estado) if a.estado else raiz / "ofertas" / a.oferta / "estado.json"
        estado = _cargar(ruta_estado)
        gates = _cargar(raiz / "contratos" / "gates.json")
        ruta_aut = Path(a.autonomia) if a.autonomia else raiz / "empresa" / "autonomia.yaml"
        aut = _cargar(ruta_aut) if ruta_aut.is_file() else None
        ruta_brief = ruta_estado.parent / "00-brief.yaml"
        brief = _cargar(ruta_brief) if ruta_brief.is_file() else None
        ruta_lim = raiz / "empresa" / "limites.yaml"
        lim = _cargar(ruta_lim) if ruta_lim.is_file() else {}
        res = proximo(estado, gates, aut, pausa={} if (raiz / "empresa" / "PAUSA").exists() else None, brief=brief,
                      acciones_h=GATE_H_SIEMPRE | set((lim or {}).get("acciones_gate_humano") or ()))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: estado ilegible o inválido ({type(exc).__name__}: {str(exc)[:160]})", file=sys.stderr)
        return 3
    if res.get("comando") and not (raiz / "engine" / "orq.py").is_file():
        res["avisos"].append("engine/orq.py no existe en esta raíz: el comando es el diseñado en docs/06 §4.2 y no se puede ejecutar aquí")
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(f"Oferta {res['oferta_id']} · fase {res['fase']} · nivel {res['nivel_oferta']}")
        for f in res["etapas"][:8]:
            marca = "firma pendiente" if f["gate_pendiente"] else ("OBSOLETA" if f["obsoleta"] else "")
            print(f"  {f['etapa']:<4}{f['estado']:<12} gate {f['gate']} ({f['nivel']}) {marca}")
        print(f"PRÓXIMO PASO: {res['accion']}" + (f" · {res['etapa']}" if res.get("etapa") else ""))
        print(f"  Por qué: {res['motivo']}")
        print(f"  Falta: {'; '.join(res['falta']) or 'nada'}")
        print(f"  Espera tu firma: {'sí' if res['espera_firma'] else 'no'}" + ("  · requiere sesión interactiva con conectores" if res.get("requiere_sesion_interactiva") else ""))
        print(f"  Comando: {res['comando'] or '(ninguno: no hay nada que ejecutar)'}")
        for w in res["avisos"]:
            print(f"  AVISO: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
