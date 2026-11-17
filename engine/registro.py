"""Registro encadenado por hash (``empresa/registro.jsonl``) y costos (``empresa/costos.jsonl``).

El motor es el ÚNICO escritor del registro (docs/06 D-14): los hooks de los agentes escriben en un
*spool* por corrida y :func:`ingerir_spool` lo incorpora a la cadena. Cada línea cumple
``contratos/registro.schema.json`` y lleva ``hash_previo`` (el ``hash`` de la línea anterior) y
``hash`` (SHA-256 del JSON canónico de la línea sin el propio ``hash``): alterar, borrar o reordenar
una línea rompe la cadena y :func:`verificar_cadena` lo informa.

Además, :func:`anclar` firma con HMAC (``REGISTRO_HMAC``, clave que el runner no tiene) el hash de
cabeza y el número de líneas en ``registro.anclas.jsonl``. Sin ancla, quien reescribe TODO el
archivo desde el principio produce una cadena válida; con ancla, borrar el final o reescribir el
pasado se detecta. La publicación del ancla en el KV del watchdog (``registro:cabeza``) y la cadencia
(cada N líneas u hora) las decide el motor con parámetros (ver «Pedidos» del README).

Garantías:

* Escritura con bloqueo de archivo (``flock``) y UNA llamada de escritura por línea.
* Todo texto libre pasa por :func:`engine.comun.ocultar_datos_sensibles` (correos, IP, tarjetas,
  secretos) y ``entrada_resumen`` se limita a 300 caracteres.
* Una cadena corrupta (en CUALQUIER línea, no solo la última) hace que ``registrar`` se NIEGUE a
  escribir (falla cerrado, ``ErrorValidacion``; ver :func:`_cadena_intacta`).

CLI::

    python -m engine.registro verificar [--raiz RUTA] [--json]   # solo lectura; 0 sano, 3 roto
    python -m engine.registro anclar    [--raiz RUTA] [--json]   # exige REGISTRO_HMAC
"""
from __future__ import annotations

import argparse
import copy
import functools
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, BinaryIO, Mapping, Sequence

from engine import comun
from engine.errores import ErrorBloqueado, ErrorUso, ErrorValidacion
from scripts.validar_esquemas import DIR_CONTRATOS, cadena_registro_valida

__all__ = [
    "MAX_ENTRADA_RESUMEN", "MONEDA_COSTO_IA", "VAR_CLAVE_ANCLA", "anclar", "costo", "ingerir_spool", "main",
    "registrar", "ruta_anclas", "ruta_costos", "ruta_registro", "verificar_cadena",
]

SCHEMA_VERSION = "1.0.0"
MAX_ENTRADA_RESUMEN = 300  # maxLength de entrada_resumen en registro.schema.json
MONEDA_COSTO_IA = "USD"  # la API de IA se factura en USD; una conversión exige tipo de cambio registrado (convenciones §3)
VAR_CLAVE_ANCLA = "REGISTRO_HMAC"

_RX_EJECUCION = re.compile(r"^(RUN-[0-9]{8}-[0-9]{2}|[a-z0-9-]{6,40})$")
_RX_OFERTA = re.compile(r"^OF-[0-9]{6}-[0-9]{2}$")
_RX_AGENTE = re.compile(r"^[a-z0-9][a-z0-9:_-]*$")
_HASH_CERO = "sha256:" + "0" * 64  # relleno solo para validar el esquema antes de tomar el bloqueo
_CAMPOS_OBLIGATORIOS = ("ejecucion_id", "oferta_id", "etapa", "agente", "evento", "herramienta", "entrada_resumen",
                        "resultado", "costo_estimado", "modo")
_PASO_LECTURA = 4096
_MAX_EJECUCION_ID = 40  # largo máximo de ejecucion_id según registro.schema.json
_LARGO_HASH_CORTO = 16
_MIN_EJECUCION_ID = 6


def ruta_registro(raiz: Path | None = None) -> Path:
    """Ruta de ``empresa/registro.jsonl`` bajo la raíz."""
    return (raiz or comun.raiz()) / "empresa" / "registro.jsonl"


def ruta_costos(raiz: Path | None = None) -> Path:
    """Ruta de ``empresa/costos.jsonl`` bajo la raíz."""
    return (raiz or comun.raiz()) / "empresa" / "costos.jsonl"


def ruta_anclas(ruta: Path) -> Path:
    """Archivo de anclas hermano del registro (``registro.jsonl`` → ``registro.anclas.jsonl``)."""
    return ruta.with_name(ruta.stem + ".anclas.jsonl")


@functools.lru_cache(maxsize=1)
def _etapas_validas() -> frozenset[str]:
    """Etapas permitidas, leídas de ``comunes.schema.json`` (los enumerados se definen una sola vez)."""
    comunes = comun.cargar_json(DIR_CONTRATOS / "comunes.schema.json")
    return frozenset(comunes["$defs"]["etapa"]["enum"])


def _resumir(texto: Any) -> str:
    """Oculta datos sensibles y recorta a ``MAX_ENTRADA_RESUMEN`` caracteres (primero oculta, luego recorta)."""
    if not isinstance(texto, str):
        raise ErrorValidacion("entrada_resumen debe ser texto")
    limpio = comun.ocultar_datos_sensibles(texto)
    return limpio if len(limpio) <= MAX_ENTRADA_RESUMEN else limpio[: MAX_ENTRADA_RESUMEN - 1] + "…"


def _ultima_linea(f: BinaryIO) -> bytes | None:
    """Última línea no vacía del archivo abierto (leyendo desde el final), o ``None`` si está vacío."""
    f.flush()
    tamano = os.fstat(f.fileno()).st_size
    pos, acumulado = tamano, b""
    while pos > 0:
        inicio = max(0, pos - _PASO_LECTURA)
        f.seek(inicio)
        acumulado = f.read(pos - inicio) + acumulado
        pos = inicio
        recortado = acumulado.rstrip(b"\n")
        if b"\n" in recortado:
            return recortado.rsplit(b"\n", 1)[1]
    return acumulado.rstrip(b"\n") or None


def _hash_de_cabeza(f: BinaryIO) -> str | None:
    """``hash`` de la última línea (o ``None`` si el registro está vacío); ``ErrorValidacion`` si está corrupta.

    Solo mira la ÚLTIMA línea: lo usa :func:`anclar` (que solo necesita la cabeza). :func:`registrar`
    usa :func:`_cadena_intacta`, que recorre TODA la cadena antes de escribir.
    """
    cruda = _ultima_linea(f)
    if cruda is None:
        return None
    try:
        ultima = json.loads(cruda)
        previo = ultima["hash"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ErrorValidacion("registro.jsonl corrupto: la última línea no es una línea válida; se rechaza escribir (ver verificar_cadena)") from exc
    if not isinstance(previo, str) or not previo.startswith("sha256:"):
        raise ErrorValidacion("registro.jsonl corrupto: la última línea no tiene hash válido")
    return previo


def _cadena_intacta(f: BinaryIO) -> str | None:
    """``hash`` de la última línea TRAS comprobar que la cadena completa es válida, o ``None`` si está vacío.

    Antes :func:`registrar` solo miraba la última línea (como :func:`_hash_de_cabeza`): una línea
    INTERMEDIA manipulada (hash o ``hash_previo`` alterados) no se detectaba hasta la siguiente
    ``verificar_cadena()``, y mientras tanto ``registrar`` seguía escribiendo encima sin avisar. Aquí
    se recorre TODO el contenido (ya bajo ``flock``, con el archivo abierto) y se usa la misma
    comprobación que ``engine.registro.verificar_cadena`` (:func:`cadena_registro_valida`) antes de
    encadenar la línea nueva: una cadena rota se RECHAZA (``ErrorValidacion``), nunca se escribe encima.
    """
    f.seek(0)
    crudo = f.read()
    crudas = [x for x in crudo.split(b"\n") if x.strip()]
    if not crudas:
        return None
    lineas: list[dict] = []
    for numero, cruda in enumerate(crudas, start=1):
        try:
            obj = json.loads(cruda)
            if not isinstance(obj, dict):
                raise ValueError("no es un objeto")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ErrorValidacion(f"registro.jsonl corrupto en la línea {numero}: no es JSON válido; se rechaza escribir (ver verificar_cadena)") from exc
        if not isinstance(obj.get("hash"), str) or "hash_previo" not in obj:
            raise ErrorValidacion(f"registro.jsonl corrupto en la línea {numero}: sin hash o hash_previo válidos; se rechaza escribir")
        lineas.append(obj)
    problemas = cadena_registro_valida(lineas)
    if problemas:
        raise ErrorValidacion(f"registro.jsonl corrupto ({'; '.join(problemas[:3])}); se rechaza escribir sobre una cadena rota (ver verificar_cadena)")
    return str(lineas[-1]["hash"])


def registrar(evento: Mapping[str, Any], *, ruta: Path | None = None,
              ahora: Callable[[], datetime] = comun.ahora_utc) -> dict:
    """Agrega un evento a la cadena y devuelve la línea escrita (con ``ts``, ``hash_previo`` y ``hash``).

    ``evento`` trae los campos de ``registro.schema.json`` salvo los que asigna el registro:
    ``schema_version``, ``ts`` (si falta), ``hash_previo`` y ``hash`` (pasarlos es un error de uso).
    Obligatorios: ``ejecucion_id, oferta_id, etapa, agente, evento, herramienta, entrada_resumen,
    resultado{estado,codigo}, costo_estimado{monto,moneda}, modo``.

    Errores: ``ErrorValidacion`` si falta un campo, no cumple el esquema o la cadena está corrupta.
    """
    if not isinstance(evento, Mapping):
        raise ErrorValidacion("registrar exige un mapa")
    if "hash" in evento or "hash_previo" in evento:
        raise ErrorValidacion("hash y hash_previo los asigna el registro; no se pasan")
    linea = copy.deepcopy(dict(evento))
    faltan = [c for c in _CAMPOS_OBLIGATORIOS if c not in linea]
    if faltan:
        raise ErrorValidacion(f"evento de registro incompleto: faltan {', '.join(faltan)}")
    linea.setdefault("schema_version", SCHEMA_VERSION)
    if "ts" in linea:
        comun.parsear_z(linea["ts"])
    else:
        linea["ts"] = comun.iso_z(comun.instante(ahora))
    linea["entrada_resumen"] = _resumir(linea["entrada_resumen"])
    if isinstance(linea.get("herramienta"), str):
        linea["herramienta"] = comun.ocultar_datos_sensibles(linea["herramienta"])
    flotantes = comun.buscar_floats(linea)
    if flotantes:
        raise ErrorValidacion(f"números de coma flotante prohibidos en {', '.join(flotantes[:3])}")
    prueba = {**linea, "hash_previo": None, "hash": _HASH_CERO}
    errores = comun.errores_de_esquema("registro", prueba)
    if errores:
        raise ErrorValidacion(f"evento de registro inválido: {comun.resumir_errores_esquema(errores)}")
    destino = Path(ruta) if ruta is not None else ruta_registro()
    with comun.archivo_bloqueado(destino) as f:
        linea["hash_previo"] = _cadena_intacta(f)
        linea["hash"] = comun.hash_objeto(linea, excluir=("hash",))
        comun.escribir_linea(f, comun.json_canonico(linea) + b"\n")
    return linea


def costo(oferta_id: str, origen: str, monto_minor: int, moneda: str, *, ruta: Path | None = None,
          ahora: Callable[[], datetime] = comun.ahora_utc, **meta: Any) -> dict:
    """Anota un costo de IA, créditos o herramientas en ``empresa/costos.jsonl`` (F1 lo imputa a la oferta).

    ``oferta_id`` es un ``OF-AAAAMM-NN`` o la constante ``"empresa"``; ``origen`` ∈ ``ia|creditos|herramienta``;
    ``monto_minor`` es un entero en la unidad menor de ``moneda``. ``meta`` DEBE traer ``etapa``,
    ``ejecucion_id`` y ``concepto`` y puede traer ``tokens`` (``{entrada, salida}``) y ``creditos``.
    Devuelve la línea escrita. Errores: ``ErrorValidacion`` si algo no cumple ``costos.schema.json``.
    """
    sobran = set(meta) - {"etapa", "ejecucion_id", "concepto", "tokens", "creditos"}
    if sobran:
        raise ErrorValidacion(f"costo: campos desconocidos {', '.join(sorted(sobran))}")
    faltan = [c for c in ("etapa", "ejecucion_id", "concepto") if not meta.get(c)]
    if faltan:
        raise ErrorValidacion(f"costo: faltan {', '.join(faltan)}")
    linea: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "ts": comun.iso_z(comun.instante(ahora)),
        "oferta_id": oferta_id,
        "etapa": meta["etapa"],
        "ejecucion_id": meta["ejecucion_id"],
        "origen": origen,
        "concepto": comun.ocultar_datos_sensibles(str(meta["concepto"])),
        "monto": {"monto": comun.exigir_importe(monto_minor, "monto_minor"), "moneda": comun.exigir_moneda(moneda)},
    }
    for opcional in ("tokens", "creditos"):
        if meta.get(opcional) is not None:
            linea[opcional] = meta[opcional]
    flotantes = comun.buscar_floats(linea)
    if flotantes:
        raise ErrorValidacion(f"números de coma flotante prohibidos en {', '.join(flotantes[:3])}")
    errores = comun.errores_de_esquema("costos", linea)
    if errores:
        raise ErrorValidacion(f"costo inválido: {comun.resumir_errores_esquema(errores)}")
    comun.anexar_jsonl(Path(ruta) if ruta is not None else ruta_costos(), linea)
    return linea


# ----------------------------------------------------------------------------------------------
# Spool de hooks
# ----------------------------------------------------------------------------------------------
_RESULTADOS_SPOOL = {"ok": ("ok", 0), "error": ("error", 1), "deny": ("bloqueado", 4), "bloqueado": ("bloqueado", 4), "dry_run": ("dry_run", 0)}


def _ejecucion_id(run_id: Any) -> str:
    """Convierte el ``run_id`` del spool en un ``ejecucion_id`` válido (patrón de ``registro.schema.json``)."""
    if isinstance(run_id, str) and _RX_EJECUCION.match(run_id):
        return run_id
    base = re.sub(r"[^a-z0-9-]", "-", str(run_id or "").lower()).strip("-")[:_MAX_EJECUCION_ID]
    return base if len(base) >= _MIN_EJECUCION_ID else ("spool-" + base)[:_MAX_EJECUCION_ID]


def _evento_desde_spool(cruda: bytes, moneda_costo: str) -> dict:
    """Traduce una línea del spool de ``posttooluse_registro`` (docs/09 §14.4) a un evento de registro.

    Una línea ilegible NO se descarta ni detiene la ingesta: se registra una alerta con el hash corto de
    la línea, para que la cadena refleje que hubo un hueco.
    """
    try:
        obj = json.loads(cruda)
        if not isinstance(obj, dict):
            raise ValueError("no es un objeto")
    except (ValueError, UnicodeDecodeError):
        corto = comun.hash_bytes(cruda)[len("sha256:"):][:_LARGO_HASH_CORTO]
        return {
            "ejecucion_id": "spool-ilegible", "oferta_id": None, "etapa": "O0", "agente": "hook:spool", "evento": "alerta",
            "herramienta": "ingerir_spool", "entrada_resumen": f"línea de spool ilegible (sha256 {corto})",
            "resultado": {"estado": "error", "codigo": 3}, "costo_estimado": {"monto": 0, "moneda": moneda_costo}, "modo": "dry_run",
        }
    herramienta = str(obj.get("tool") or obj.get("herramienta") or "desconocida")
    estado, codigo = _RESULTADOS_SPOOL.get(str(obj.get("resultado")), ("error", 1))
    centavos = obj.get("costo_estimado_centavos")
    evento_hook = str(obj.get("evento") or "")
    if estado == "bloqueado":
        evento = "bloqueo"
    elif evento_hook == "PostToolUse" or evento_hook == "PostToolUseFailure":
        evento = "llamada_herramienta"
    else:
        evento = "accion"
    salida: dict[str, Any] = {
        "ejecucion_id": _ejecucion_id(obj.get("run_id")),
        "oferta_id": obj["oferta_id"] if isinstance(obj.get("oferta_id"), str) and _RX_OFERTA.match(obj["oferta_id"]) else None,
        "etapa": obj["etapa"] if obj.get("etapa") in _etapas_validas() else "O0",
        "agente": obj["agente"] if isinstance(obj.get("agente"), str) and _RX_AGENTE.match(obj["agente"]) else "hook",
        "evento": evento,
        "herramienta": herramienta,
        "entrada_resumen": f"{herramienta}: " + comun.json_canonico(obj.get("entrada")).decode("utf-8"),
        "resultado": {"estado": estado, "codigo": codigo},
        "costo_estimado": {"monto": centavos if isinstance(centavos, int) and not isinstance(centavos, bool) and centavos >= 0 else 0,
                           "moneda": moneda_costo},
        "modo": "live" if obj.get("modo") == "live" else "dry_run",
    }
    if isinstance(obj.get("ts"), str):
        try:
            comun.parsear_z(obj["ts"])
            salida["ts"] = obj["ts"]
        except ErrorValidacion:
            pass
    return salida


def _leer_cursor(ruta_cursor: Path) -> int:
    """Líneas del spool ya ingeridas (``0`` si no hay cursor)."""
    if not ruta_cursor.exists():
        return 0
    try:
        valor = json.loads(ruta_cursor.read_text(encoding="utf-8"))["lineas"]
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise ErrorValidacion("cursor del spool ilegible; se rechaza ingerir para no duplicar ni perder líneas") from exc
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise ErrorValidacion("cursor del spool inválido")
    return valor


def ingerir_spool(ruta: Path, *, destino: Path | None = None, ahora: Callable[[], datetime] = comun.ahora_utc,
                  moneda_costo: str = MONEDA_COSTO_IA) -> int:
    """Incorpora a la cadena las líneas NUEVAS de un spool de hooks y devuelve cuántas ingirió.

    El avance se guarda en ``<spool>.cursor`` (escritura atómica) después de cada línea, así que llamar
    de nuevo no duplica nada. Solo se consideran las líneas completas (terminadas en salto de línea): la
    última, si un hook la está escribiendo, espera a la próxima llamada. Una caída entre «registrar» y
    «guardar cursor» puede repetir, como máximo, la última línea (entrega al-menos-una-vez).

    Errores: ``ErrorValidacion`` si el cursor es ilegible o el spool se acortó respecto del cursor.
    """
    spool = Path(ruta)
    if not spool.exists():
        return 0
    cursor = spool.with_name(spool.name + ".cursor")
    hechas = _leer_cursor(cursor)
    contenido = spool.read_bytes()
    completas = contenido.split(b"\n")[:-1]  # lo que sigue al último salto de línea es una línea en escritura
    lineas = [x for x in completas if x.strip()]
    if hechas > len(lineas):
        raise ErrorValidacion("el spool es más corto que su cursor: fue truncado; se rechaza ingerir")
    nuevas = 0
    for cruda in lineas[hechas:]:
        registrar(_evento_desde_spool(cruda, moneda_costo), ruta=destino, ahora=ahora)
        hechas += 1
        nuevas += 1
        comun.escribir_atomico(cursor, comun.json_canonico({"lineas": hechas}))
    return nuevas


# ----------------------------------------------------------------------------------------------
# Ancla firmada y verificación
# ----------------------------------------------------------------------------------------------
def anclar(ruta: Path | None = None, *, clave: bytes | None = None, ahora: Callable[[], datetime] = comun.ahora_utc,
           env: Mapping[str, str] | None = None) -> dict:
    """Firma con HMAC el hash de cabeza y el número de líneas y lo agrega a ``registro.anclas.jsonl``.

    La clave sale de ``clave`` o de ``REGISTRO_HMAC`` (``env``). Devuelve el ancla
    ``{ts, n, hash_cabeza, firma}``. Errores: ``ErrorBloqueado`` si falta la clave;
    ``ErrorValidacion`` si el registro está vacío o corrupto.
    """
    env = os.environ if env is None else env
    secreto = clave if clave is not None else (env.get(VAR_CLAVE_ANCLA) or "").encode("utf-8")
    if not secreto:
        raise ErrorBloqueado(f"falta {VAR_CLAVE_ANCLA}: no se puede firmar el ancla del registro")
    destino = Path(ruta) if ruta is not None else ruta_registro()
    with comun.archivo_bloqueado(destino) as f:
        f.seek(0)
        lineas = [x for x in f.read().split(b"\n") if x.strip()]
        if not lineas:
            raise ErrorValidacion("no hay nada que anclar: el registro está vacío")
        cabeza = _hash_de_cabeza(f)
        ancla: dict[str, Any] = {"ts": comun.iso_z(comun.instante(ahora)), "n": len(lineas), "hash_cabeza": cabeza}
        ancla["firma"] = comun.firma_hmac(ancla, secreto)
        comun.anexar_jsonl(ruta_anclas(destino), ancla)
    return ancla


def verificar_cadena(ruta: Path | None = None, *, clave_ancla: bytes | None = None) -> list[str]:
    """Errores de integridad del registro (lista vacía = sano). Solo lectura.

    Comprueba: cada línea es JSON y cumple el esquema; ``hash_previo`` enlaza con la línea anterior; cada
    ``hash`` coincide con el contenido. Si existe ``registro.anclas.jsonl`` y se pasa ``clave_ancla``
    (``REGISTRO_HMAC``), comprueba además la firma de cada ancla, que el registro NO esté más corto que el
    último ancla (truncado) y que la línea ``n`` siga teniendo el ``hash_cabeza`` anclado (historia
    reescrita). Sin ``clave_ancla`` las firmas de ancla no se verifican y se avisa.
    """
    destino = Path(ruta) if ruta is not None else ruta_registro()
    anclas_ruta = ruta_anclas(destino)
    errores: list[str] = []
    crudo = destino.read_bytes() if destino.exists() else b""
    lineas: list[dict] = []
    legibles = True
    for numero, texto in enumerate((x for x in crudo.split(b"\n") if x.strip()), start=1):
        try:
            obj = json.loads(texto)
            if not isinstance(obj, dict):
                raise ValueError("no es un objeto")
        except (ValueError, UnicodeDecodeError):
            errores.append(f"línea {numero}: no es JSON válido")
            legibles = False
            continue
        lineas.append(obj)
        fallos = comun.errores_de_esquema("registro", obj)
        if fallos:
            errores.append(f"línea {numero}: esquema {comun.resumir_errores_esquema(fallos)}")
    if legibles and all(isinstance(x.get("hash"), str) and "hash_previo" in x for x in lineas):
        errores.extend(cadena_registro_valida(lineas))
    elif legibles and lineas:
        errores.append("hay líneas sin hash o hash_previo: la cadena no se puede comprobar")
    try:
        anclas = comun.leer_jsonl(anclas_ruta)
    except ErrorValidacion as exc:
        return errores + [f"anclas ilegibles: {exc.mensaje}"]
    if anclas and not destino.exists():
        errores.append("el registro no existe pero hay anclas: fue borrado")
    for k, ancla in enumerate(anclas, start=1):
        try:
            n, cabeza, firma = ancla["n"], ancla["hash_cabeza"], ancla["firma"]
            if isinstance(n, bool) or not isinstance(n, int) or n < 1:
                raise ValueError
        except (KeyError, ValueError):
            errores.append(f"ancla {k}: estructura inválida")
            continue
        if clave_ancla is not None:
            esperada = comun.firma_hmac({c: v for c, v in ancla.items() if c != "firma"}, clave_ancla)
            if not isinstance(firma, str) or not comun.comparar_hash(esperada, firma):
                errores.append(f"ancla {k}: firma inválida (ancla alterada o clave equivocada)")
                continue
        if n > len(lineas):
            errores.append(f"ancla {k}: el registro tiene {len(lineas)} líneas y el ancla fija {n}: registro truncado")
        elif lineas[n - 1].get("hash") != cabeza:
            errores.append(f"ancla {k}: la línea {n} ya no tiene el hash anclado: historia reescrita")
    return errores


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    """CLI: ``verificar`` (solo lectura) y ``anclar`` (agrega un ancla firmada junto al registro)."""
    ap = argparse.ArgumentParser(prog="python -m engine.registro", description="Registro encadenado por hash.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nombre, ayuda in (("verificar", "comprueba la cadena y las anclas"), ("anclar", "firma el hash de cabeza")):
        p = sub.add_parser(nombre, help=ayuda)
        p.add_argument("--raiz", help="raíz alternativa (solo con FABRICA_ENTORNO distinto de produccion)")
        p.add_argument("--json", action="store_true", help="una línea JSON en stdout")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        if args.raiz:
            if comun.entorno(env) == "produccion":
                raise ErrorUso("--raiz no existe con FABRICA_ENTORNO=produccion")
            env["FABRICA_RAIZ"] = str(Path(args.raiz).resolve())
        destino = ruta_registro(comun.raiz(env))
        clave = (env.get(VAR_CLAVE_ANCLA) or "").encode("utf-8") or None
        if args.cmd == "anclar":
            datos: Any = anclar(destino, env=env)
            codigo, avisos = 0, []
        else:
            problemas = verificar_cadena(destino, clave_ancla=clave)
            datos = {"problemas": problemas}
            avisos = []
            if clave is None and ruta_anclas(destino).exists():
                avisos.append(f"hay anclas pero {VAR_CLAVE_ANCLA} no está definida: sus firmas no se verificaron")
            codigo = 3 if problemas else 0
        if args.json:
            print(json.dumps({"ok": codigo == 0, "modo": "dry_run", "codigo": codigo, "datos": datos, "avisos": avisos},
                             sort_keys=True, ensure_ascii=False))
        else:
            print("REGISTRO SANO" if codigo == 0 and args.cmd == "verificar" else json.dumps(datos, ensure_ascii=False, sort_keys=True))
            for a in avisos:
                print(a)
        return codigo

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
