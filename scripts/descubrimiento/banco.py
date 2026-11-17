"""Banco de problemas de D1 (interfaces d1-v2 §2, §2.3, §2.4, §8.2 n.2): alta, estados, índice y
caducidad de `empresa/descubrimiento/problemas/*.json`.

Único escritor de `empresa/descubrimiento/problemas/` y `empresa/descubrimiento/banco.json`: ningún
otro módulo de este repositorio escribe ahí directamente (backbone §4, "un archivo, un propietario").
`scripts.descubrimiento.ficha_a_candidato` NO persiste el banco; solo decide si un par pasa la puerta
de §3.8.1 -- es este módulo, vía :func:`agregar_pares_modelado`, el que guarda sus `pares_modelado[]`
dentro del problema.

No existe todavía `contratos/problema.schema.json` (interfaces §1, tabla; pedido a CT §8.1 n.3): este
módulo valida solo las invariantes mínimas que puede sostener sin ese contrato (``problema_id`` con la
forma `PRB-AAAAMM-NNNN`, ``estado`` en el enumerado de §2.3, transición permitida). El resto de los
campos de §3.3 se escribe tal cual los entrega el llamador, sin inventar valores.

**Estados y transiciones (§2.3).** `TRANSICIONES_PERMITIDAS` es el grafo de qué salto de estado es
válido; NO reimplementa las condiciones de negocio de "cuándo" (evidencia mínima, QA PASS, elección
del dueño...): esas las decide el llamador (Maker, QA, `ficha_a_candidato`, el dueño vía O0) y las pasa
como el estado destino. Transiciones ambiguas en la especificación (`rechazado -> normalizado` como
reapertura; `vencido -> vigente` como refresco) se resolvieron de forma genérica y conservadora: ver
README, «Decisiones».

Dry-run por defecto (convenciones §9): todo lo que escribe en disco exige ``--aplicar`` y revisa
``empresa/PAUSA`` primero (``ErrorBloqueado``, 4). ``caducar`` exige
``empresa/parametros.yaml#descubrimiento.caducidad_banco_dias`` -- ausente o `null` ⇒ `ErrorLimite`/
`ParametroFaltante` (5), nunca un valor por defecto. Escritura atómica (`engine.comun.escribir_atomico`).
Sin red, sin LLM.

Uso::

    python -m scripts.descubrimiento.banco crear --via oferta_primero --locale-origen es-MX \\
        --problema "..." --raiz . [--aplicar] [--json]
    python -m scripts.descubrimiento.banco transicionar PRB-202611-0001 --a normalizado --raiz . [--aplicar]
    python -m scripts.descubrimiento.banco indice --raiz . [--aplicar]
    python -m scripts.descubrimiento.banco caducar --raiz . [--aplicar]

Códigos de salida (convenciones §8): 0 ok · 2 uso · 3 validación (id/estado/transición inválidos) ·
4 bloqueado (`empresa/PAUSA`) · 5 falta `caducidad_banco_dias`.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from engine import parametros as motor_parametros
from engine.comun import (
    ahora_utc,
    ejecutar_cli,
    escribir_atomico,
    hash_objeto,
    iso_z,
    json_canonico,
    raiz as raiz_repositorio,
)
from engine.errores import ErrorBloqueado, ErrorUso, ErrorValidacion
from engine.guard import hay_pausa

SCHEMA_VERSION = "1.0.0"  # propio de este módulo; sin contrato CT todavía (ver docstring)

ESTADOS = (
    "semilla", "normalizado", "con_evidencia", "con_ficha", "vigente", "en_reencuadre",
    "elegido", "devuelto_d2", "rechazado", "vencido", "archivado",
)

# Grafo de transiciones permitidas (interfaces §2.3, columna "Sale cuando" + "Quién puede moverlo").
# Dos saltos son ambiguos en la especificación y se resolvieron de forma genérica (ver README):
# `rechazado -> normalizado` (reapertura con evidencia nueva, §2.4) y `vencido -> vigente` (refresco
# de evidencia dentro de `refresco_evidencia_max_dias`).
TRANSICIONES_PERMITIDAS: dict[str, frozenset[str]] = {
    "semilla": frozenset({"normalizado", "rechazado"}),
    "normalizado": frozenset({"con_evidencia", "rechazado"}),
    "con_evidencia": frozenset({"con_ficha", "rechazado"}),
    "con_ficha": frozenset({"vigente", "en_reencuadre", "rechazado"}),
    "vigente": frozenset({"elegido", "vencido", "rechazado"}),
    "en_reencuadre": frozenset({"con_ficha", "rechazado"}),
    "elegido": frozenset({"devuelto_d2"}),
    "devuelto_d2": frozenset({"en_reencuadre", "vigente", "rechazado"}),
    "rechazado": frozenset({"normalizado"}),
    "vencido": frozenset({"vigente", "archivado"}),
    "archivado": frozenset(),
}

_RX_PROBLEMA_ID = re.compile(r"^PRB-([0-9]{6})-([0-9]{4})$")
_RX_PROBLEMA_ARCHIVO = re.compile(r"^PRB-([0-9]{6})-([0-9]{4})\.json$")


def _carpeta_problemas(raiz: Path) -> Path:
    return Path(raiz) / "empresa" / "descubrimiento" / "problemas"


def ruta_problema(raiz: Path, problema_id: str) -> Path:
    """Ruta de ``problemas/<problema_id>.json`` bajo ``raiz``. No valida que exista."""
    if not isinstance(problema_id, str) or not _RX_PROBLEMA_ID.fullmatch(problema_id):
        raise ErrorValidacion(f"problema_id inválido: {problema_id!r} (se espera PRB-AAAAMM-NNNN)")
    return _carpeta_problemas(raiz) / f"{problema_id}.json"


def ruta_indice(raiz: Path) -> Path:
    return Path(raiz) / "empresa" / "descubrimiento" / "banco.json"


# ---------------------------------------------------------------------------
# Alta: generación de problema_id correlativo por mes (§3.1) y construcción del documento "semilla"
# ---------------------------------------------------------------------------
def generar_problema_id(raiz: Path, *, ahora: Callable[[], datetime] = ahora_utc) -> str:
    """``PRB-AAAAMM-NNNN``: AAAAMM del mes de creación, NNNN correlativo del mes (interfaces §3.1).

    Lee los archivos ya existentes en ``problemas/`` para el mes; no asume un contador externo.
    """
    momento = ahora()
    aaaamm = momento.strftime("%Y%m")
    carpeta = _carpeta_problemas(raiz)
    maximo = 0
    if carpeta.is_dir():
        for ruta in carpeta.iterdir():
            m = _RX_PROBLEMA_ARCHIVO.fullmatch(ruta.name)
            if m and m.group(1) == aaaamm:
                maximo = max(maximo, int(m.group(2)))
    return f"PRB-{aaaamm}-{maximo + 1:04d}"


def nuevo_problema(problema_id: str, *, via: str, locale_origen: str,
                   problema: str | None = None, audiencia: str | None = None,
                   resultado: str | None = None, obstaculo: str | None = None,
                   padre_id: str | None = None, ahora: Callable[[], datetime] = ahora_utc) -> dict[str, Any]:
    """Documento "semilla" de un problema nuevo (interfaces §2.3, §3.3). Pura: no escribe nada.

    ``via``: ``"dolor_primero"`` o ``"oferta_primero"`` (§3.3). Los campos que solo existen desde
    estados posteriores (``macro_nicho``, ``riesgo``, ``mecanismo``...) se omiten: nunca se inventan
    (fail-closed); los añade quien los calcula (clasificador, Maker, QA) en una transición posterior.
    """
    if via not in ("dolor_primero", "oferta_primero"):
        raise ErrorValidacion(f"via inválida: {via!r} (se espera 'dolor_primero' u 'oferta_primero')")
    if not _RX_PROBLEMA_ID.fullmatch(problema_id):
        raise ErrorValidacion(f"problema_id inválido: {problema_id!r}")
    ts = iso_z(ahora())
    return {
        "schema_version": SCHEMA_VERSION, "problema_id": problema_id, "version": "v1",
        "origen_version": "maker" if via == "oferta_primero" else "script",
        "estado": "semilla", "via": via, "locale_origen": locale_origen, "locales": [],
        "problema": problema, "audiencia": audiencia, "resultado": resultado, "obstaculo": obstaculo,
        "senal_ids": [], "pares_modelado": [], "intentos_reencuadre": 0, "padre_id": padre_id,
        "rechazo": None, "elegido_en": None, "creado_en": ts, "actualizado_en": ts,
        "evidencia_vigente_hasta": None,
    }


def crear_problema(raiz: Path, *, via: str, locale_origen: str, ahora: Callable[[], datetime] = ahora_utc,
                   aplicar: bool = False, **campos: Any) -> dict[str, Any]:
    """Genera el ``problema_id``, construye el documento "semilla" y lo guarda si ``aplicar``.

    Dry-run (``aplicar=False``, por defecto): devuelve el documento sin escribir nada ni comprobar
    PAUSA (no hay efecto). Con ``aplicar=True``: ``empresa/PAUSA`` bloquea (4) antes de escribir.
    """
    problema_id = generar_problema_id(raiz, ahora=ahora)
    doc = nuevo_problema(problema_id, via=via, locale_origen=locale_origen, ahora=ahora, **campos)
    if aplicar:
        guardar_problema(raiz, doc, aplicar=True)
    return doc


# ---------------------------------------------------------------------------
# Transiciones (§2.3): valida el salto contra el grafo, nunca las condiciones de negocio
# ---------------------------------------------------------------------------
def transicionar(doc: Mapping[str, Any], nuevo_estado: str, *, motivo: Mapping[str, Any] | None = None,
                 ahora: Callable[[], datetime] = ahora_utc) -> dict[str, Any]:
    """Devuelve una COPIA de ``doc`` con ``estado = nuevo_estado`` si la transición es válida.

    ``ErrorValidacion`` (3) si ``nuevo_estado`` no está en :data:`ESTADOS` o el salto no figura en
    :data:`TRANSICIONES_PERMITIDAS`. ``motivo`` (§7) se guarda en ``rechazo`` SOLO si
    ``nuevo_estado == "rechazado"``; se ignora en cualquier otro destino (no se inventa un rechazo).
    """
    estado_actual = doc.get("estado")
    if estado_actual not in TRANSICIONES_PERMITIDAS:
        raise ErrorValidacion(f"estado actual desconocido: {estado_actual!r}")
    if nuevo_estado not in ESTADOS:
        raise ErrorValidacion(f"estado destino desconocido: {nuevo_estado!r} (se espera uno de {ESTADOS})")
    if nuevo_estado not in TRANSICIONES_PERMITIDAS[estado_actual]:
        raise ErrorValidacion(f"transición no permitida: {estado_actual!r} -> {nuevo_estado!r}")
    nuevo = dict(doc)
    nuevo["estado"] = nuevo_estado
    nuevo["actualizado_en"] = iso_z(ahora())
    if nuevo_estado == "rechazado":
        nuevo["rechazo"] = dict(motivo) if motivo is not None else nuevo.get("rechazo")
    if nuevo_estado == "en_reencuadre":
        nuevo["intentos_reencuadre"] = int(doc.get("intentos_reencuadre") or 0) + 1
    return nuevo


# ---------------------------------------------------------------------------
# Persistencia (único escritor): dry-run por defecto, PAUSA antes de --aplicar, escritura atómica
# ---------------------------------------------------------------------------
def cargar_problema(raiz: Path, problema_id: str) -> dict[str, Any]:
    ruta = ruta_problema(raiz, problema_id)
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ErrorUso(f"no existe {ruta}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ErrorValidacion(f"{ruta}: JSON inválido ({exc})") from exc
    if not isinstance(datos, dict):
        raise ErrorValidacion(f"{ruta}: se esperaba un objeto")
    return datos


def guardar_problema(raiz: Path, doc: Mapping[str, Any], *, aplicar: bool = False) -> Path:
    """Ruta donde se guardaría (o se guardó) ``doc``. Sin ``aplicar``, no toca el disco."""
    problema_id = doc.get("problema_id")
    if not isinstance(problema_id, str):
        raise ErrorValidacion("doc.problema_id ausente o inválido")
    if doc.get("estado") not in ESTADOS:
        raise ErrorValidacion(f"doc.estado desconocido: {doc.get('estado')!r}")
    ruta = ruta_problema(raiz, problema_id)
    if aplicar:
        if hay_pausa(raiz):
            raise ErrorBloqueado("existe empresa/PAUSA: el banco de problemas no escribe")
        escribir_atomico(ruta, json_canonico(doc))
    return ruta


def listar_problemas(raiz: Path) -> list[dict[str, Any]]:
    """Todos los ``problemas/*.json`` bajo ``raiz``, ordenados por ``problema_id``. Solo lectura."""
    carpeta = _carpeta_problemas(raiz)
    if not carpeta.is_dir():
        return []
    docs = []
    for ruta in sorted(carpeta.glob("PRB-*.json")):
        if not _RX_PROBLEMA_ARCHIVO.fullmatch(ruta.name):
            continue
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        if isinstance(datos, dict):
            docs.append(datos)
    return docs


# ---------------------------------------------------------------------------
# Índice derivado (banco.json, interfaces §2.1): una fila por problema, hash del conjunto
# ---------------------------------------------------------------------------
def construir_indice(problemas: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """``banco.json`` DERIVADO (regenerable, nunca la fuente de verdad: eso es ``problemas/*.json``)."""
    filas = [{
        "problema_id": p.get("problema_id"), "estado": p.get("estado"),
        "macro_nicho": p.get("macro_nicho"), "locale_origen": p.get("locale_origen"),
        "actualizado_en": p.get("actualizado_en"),
    } for p in sorted(problemas, key=lambda p: str(p.get("problema_id")))]
    return {"schema_version": SCHEMA_VERSION, "problemas": filas, "banco_hash": hash_objeto({"problemas": filas})}


def reconstruir_indice(raiz: Path, *, aplicar: bool = False) -> dict[str, Any]:
    """Regenera ``banco.json`` leyendo ``problemas/*.json``. Dry-run por defecto; PAUSA bloquea escribir."""
    indice = construir_indice(listar_problemas(raiz))
    if aplicar:
        if hay_pausa(raiz):
            raise ErrorBloqueado("existe empresa/PAUSA: el banco de problemas no escribe")
        escribir_atomico(ruta_indice(raiz), json_canonico(indice))
    return indice


# ---------------------------------------------------------------------------
# pares_modelado[] (interfaces §3.3, §3.8.1): los pares que NO llegan a candidatos.json
# ---------------------------------------------------------------------------
def agregar_pares_modelado(doc: Mapping[str, Any], pares: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Copia de ``doc`` con ``pares_modelado[]`` fusionado por ``par_id`` (el último gana).

    Cada ``par`` trae al menos ``par_id`` y ``estado_par`` (``incompleta``·``no_pasa``·``vetada``);
    ``pendiente[]``/``detalle`` son opcionales. No valida el contenido de cada par (eso lo hizo
    ``ficha_a_candidato``); solo exige la forma mínima para no perder la trazabilidad.
    """
    for par in pares:
        if not isinstance(par, Mapping) or not par.get("par_id") or "estado_par" not in par:
            raise ErrorValidacion("cada par de pares_modelado necesita 'par_id' y 'estado_par'")
    existentes = {p["par_id"]: dict(p) for p in (doc.get("pares_modelado") or [])}
    for par in pares:
        existentes[par["par_id"]] = dict(par)
    nuevo = dict(doc)
    nuevo["pares_modelado"] = [existentes[k] for k in sorted(existentes)]
    return nuevo


# ---------------------------------------------------------------------------
# Caducidad (interfaces §2.3, §5.2 `caducidad_banco_dias`): vigente -> vencido sin reconfirmar
# ---------------------------------------------------------------------------
def evaluar_caducidad(raiz: Path, *, ahora: Callable[[], datetime] = ahora_utc,
                      aplicar: bool = False) -> list[dict[str, Any]]:
    """Problemas ``vigente`` cuya ``actualizado_en`` supera ``caducidad_banco_dias`` -> ``vencido``.

    ``caducidad_banco_dias`` ausente o ``null`` en ``empresa/parametros.yaml``: ``ParametroFaltante``
    (5), falla cerrado, no transiciona nada. Devuelve la lista de transiciones hechas (o que se
    harían, en dry-run); con ``aplicar=True`` las guarda (PAUSA bloquea antes de escribir).
    """
    dias = motor_parametros.cargar_parametros(Path(raiz) / "empresa" / "parametros.yaml").valor(
        "descubrimiento.caducidad_banco_dias")
    if isinstance(dias, bool) or not isinstance(dias, int) or dias < 1:
        raise ErrorValidacion(f"descubrimiento.caducidad_banco_dias inválido: {dias!r}")
    limite = ahora() - timedelta(days=dias)
    transiciones = []
    for doc in listar_problemas(raiz):
        if doc.get("estado") != "vigente":
            continue
        actualizado = doc.get("actualizado_en")
        if not isinstance(actualizado, str):
            continue
        from engine.comun import parsear_z  # import local: evita un ciclo si algún día esto crece

        if parsear_z(actualizado) >= limite:
            continue
        nuevo = transicionar(doc, "vencido", ahora=ahora)
        if aplicar:
            guardar_problema(raiz, nuevo, aplicar=True)
        transiciones.append({"problema_id": doc.get("problema_id"), "de": "vigente", "a": "vencido"})
    return transiciones


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.descubrimiento.banco",
                                description="Banco de problemas de D1 (interfaces §2, §2.3, §2.4)")
    p.add_argument("--raiz", type=Path, help="raíz del repositorio; por defecto FABRICA_RAIZ o la del archivo")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("crear")
    c.add_argument("--via", required=True, choices=("dolor_primero", "oferta_primero"))
    c.add_argument("--locale-origen", required=True)
    c.add_argument("--problema")
    c.add_argument("--audiencia")
    c.add_argument("--resultado")
    c.add_argument("--obstaculo")
    c.add_argument("--aplicar", action="store_true")
    c.add_argument("--json", action="store_true")

    t = sub.add_parser("transicionar")
    t.add_argument("problema_id")
    t.add_argument("--a", dest="nuevo_estado", required=True, choices=ESTADOS)
    t.add_argument("--motivo", help="JSON del objeto 'rechazo' (solo se usa si --a rechazado)")
    t.add_argument("--aplicar", action="store_true")
    t.add_argument("--json", action="store_true")

    i = sub.add_parser("indice")
    i.add_argument("--aplicar", action="store_true")
    i.add_argument("--json", action="store_true")

    k = sub.add_parser("caducar")
    k.add_argument("--ahora", help="instante UTC ISO con Z, solo fuera de producción (pruebas)")
    k.add_argument("--aplicar", action="store_true")
    k.add_argument("--json", action="store_true")
    return p


def _raiz(a: argparse.Namespace) -> Path:
    return a.raiz or raiz_repositorio()


def _imprimir(a: argparse.Namespace, datos: Mapping[str, Any]) -> None:
    if a.json:
        print(json.dumps(datos, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(datos, ensure_ascii=False, sort_keys=True, indent=2))


def _cuerpo_crear(a: argparse.Namespace) -> int:
    doc = crear_problema(
        _raiz(a), via=a.via, locale_origen=a.locale_origen, problema=a.problema, audiencia=a.audiencia,
        resultado=a.resultado, obstaculo=a.obstaculo, aplicar=a.aplicar)
    _imprimir(a, {"problema_id": doc["problema_id"], "estado": doc["estado"], "escrito": bool(a.aplicar)})
    return 0


def _cuerpo_transicionar(a: argparse.Namespace) -> int:
    raiz = _raiz(a)
    doc = cargar_problema(raiz, a.problema_id)
    motivo = json.loads(a.motivo) if a.motivo else None
    nuevo = transicionar(doc, a.nuevo_estado, motivo=motivo)
    if a.aplicar:
        guardar_problema(raiz, nuevo, aplicar=True)
    _imprimir(a, {"problema_id": a.problema_id, "de": doc.get("estado"), "a": nuevo["estado"],
                 "escrito": bool(a.aplicar)})
    return 0


def _cuerpo_indice(a: argparse.Namespace) -> int:
    indice = reconstruir_indice(_raiz(a), aplicar=a.aplicar)
    _imprimir(a, {"problemas_n": len(indice["problemas"]), "banco_hash": indice["banco_hash"],
                 "escrito": bool(a.aplicar)})
    return 0


def _cuerpo_caducar(a: argparse.Namespace) -> int:
    from engine.comun import parsear_z

    reloj = (lambda: parsear_z(a.ahora)) if a.ahora else ahora_utc
    transiciones = evaluar_caducidad(_raiz(a), ahora=reloj, aplicar=a.aplicar)
    _imprimir(a, {"vencidos_n": len(transiciones), "transiciones": transiciones, "escrito": bool(a.aplicar)})
    return 0


def main(argv: list[str] | None = None) -> int:
    def _principal() -> int:
        try:
            a = _parser().parse_args(argv)
        except SystemExit as exc:
            if exc.code in (0, None):
                return 0
            raise ErrorUso("argumentos inválidos (ver --help)") from None
        cuerpos = {"crear": _cuerpo_crear, "transicionar": _cuerpo_transicionar, "indice": _cuerpo_indice,
                  "caducar": _cuerpo_caducar}
        return cuerpos[a.cmd](a)

    return ejecutar_cli(_principal)


if __name__ == "__main__":
    raise SystemExit(main())
