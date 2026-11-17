"""``GET /api/cerebro``: lo que el sistema recuerda (solo lectura; alimenta ``#/cerebro``).

Reúne, sin escribir nada y sin lanzar por un archivo ausente o corrupto, lo que el Cerebro v0 muestra además de la lista
única de pendientes (que sale de ``GET /api/pulido``):

* ``memoria``: los archivos de ``empresa/memoria/`` (existencia, líneas, última fecha, tamaño y hash). La carpeta la crean las
  skills ``/cerebro-cerrar`` al escribir; el panel no la crea.
* ``decisiones``: los dos documentos de decisiones del dueño. SOLO se enlazan y se cuentan (ruta, bytes, hash, nº de decisiones
  y de tareas); su texto no viaja. Además, las últimas guardadas en ``empresa/memoria/decisiones_dueno.jsonl`` (memoria propia).
* ``reglas``: resumen de ``empresa/parametros.yaml``, ``limites.yaml`` (con su sello) y ``autonomia.yaml``. Solo lectura: las
  reglas las cambia únicamente el dueño.
* ``lecciones``: hallazgos y aprendizajes de los QA por oferta, post-mortems y las lecciones guardadas en ``lecciones.jsonl``.
* ``jardin``: propuestas del jardinero del domingo (aún no existe: devuelve ``propuestas: 0``).

Todo texto que viene de archivos es dato no confiable: se recorta por campo y el cliente lo muestra siempre como texto.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from dashboard.api_base import Ctx, Sobre, ids_de_ofertas
from dashboard.archivos import Raiz, TOPE_JSON, iso_mtime

__all__ = ["cerebro", "REL_MEMORIA", "ARCHIVOS_MEMORIA", "FUENTES_DECISIONES"]

REL_MEMORIA = "empresa/memoria"
ARCHIVOS_MEMORIA = (
    ("decisiones_dueno", f"{REL_MEMORIA}/decisiones_dueno.jsonl", "Decisiones del dueño guardadas al cerrar una sesión"),
    ("lecciones", f"{REL_MEMORIA}/lecciones.jsonl", "Lecciones con su prueba guardadas al cerrar una sesión"),
    ("eventos", f"{REL_MEMORIA}/eventos.jsonl", "Libro de eventos del aprendizaje (lo escribe el sistema automático, no las guías de trabajo del Cerebro)"),
)
FUENTES_DECISIONES = (
    ("decisiones_y_tareas", "Decisiones y tareas del dueño", "docs/00-decisiones-y-tareas-del-dueno.md"),
    ("decisiones_adopcion", "Decisiones tomadas al adoptar el sistema (J1 a J9)", "docs/_historial/mentor-sistema/decisiones-del-dueno.md"),
)
REL_JARDIN = f"{REL_MEMORIA}/jardin"

_TOPE_DOC = 400 * 1024
_MAX_HALLAZGOS = 300
_MAX_APRENDIZAJES = 120
_MAX_POSTMORTEMS = 60
_MAX_LECCIONES = 60
_MAX_DECISIONES = 60
_MAX_TEXTO = 300
_RX_SEPARADOR = re.compile(r"^\|[\s:|\-]+\|?\s*$")
_RX_CASILLA_ABIERTA = re.compile(r"^\s*[-*] \[ \]")
_RX_CASILLA_HECHA = re.compile(r"^\s*[-*] \[[xX]\]")
_RX_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _texto(valor: Any, maximo: int = _MAX_TEXTO) -> str | None:
    if not isinstance(valor, str):
        return None
    limpio = _RX_CONTROL.sub("", valor).strip()
    return limpio[:maximo] if limpio else None


def _entero(valor: Any) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


# ----------------------------------------------------------------------------------------------
# memoria
# ----------------------------------------------------------------------------------------------
def _hash_archivo(base: Raiz, rel: str, tope: int) -> tuple[str | None, int | None]:
    """``(sha256 hex, bytes)`` del archivo entero; ``(None, bytes)`` si supera el tope o no se puede leer."""
    try:
        datos, truncado, st = base.bytes(rel, tope)
    except Exception:  # noqa: BLE001 - ErrorHttp/OSError: la ausencia no es un error del panel
        return None, None
    return (None if truncado else hashlib.sha256(datos).hexdigest()), st.st_size


def _memoria(ctx: Ctx, avisos: list[str]) -> dict[str, Any]:
    base = ctx.raiz_confinada
    archivos: list[dict[str, Any]] = []
    for clave, rel, titulo in ARCHIVOS_MEMORIA:
        st = base.stat(rel)
        fila: dict[str, Any] = {"clave": clave, "ruta": rel, "titulo": titulo, "existe": st is not None, "lineas": 0,
                                "ultima_ts": None, "bytes": None, "sha256": None, "modificado": None}
        if st is not None:
            lec = base.jsonl_cola(rel, maximo=1)
            avisos.extend(lec.avisos)
            fila["lineas"] = lec.total or 0
            fila["modificado"] = iso_mtime(st)
            fila["sha256"], fila["bytes"] = _hash_archivo(base, rel, 8 * 1024 * 1024)
            for _, obj, _crudo in reversed(lec.lineas):
                if isinstance(obj, dict) and isinstance(obj.get("ts"), str):
                    fila["ultima_ts"] = obj["ts"][:40]
                    break
        archivos.append(fila)
    return {"carpeta": {"ruta": REL_MEMORIA, "existe": base.es_directorio(REL_MEMORIA)}, "archivos": archivos}


# ----------------------------------------------------------------------------------------------
# decisiones: solo ruta, hash y conteos
# ----------------------------------------------------------------------------------------------
def contar_decisiones(texto: str) -> dict[str, int]:
    """Cuenta (sin devolver texto): filas de las tablas bajo un título «Decisiones … tomadas» y casillas ``[ ]`` / ``[x]``."""
    decisiones = 0
    en_seccion = False
    cabecera_vista = False
    for linea in texto.splitlines():
        if linea.startswith("#"):
            titulo = linea.lstrip("#").strip().lower()
            en_seccion = "decisiones" in titulo and "tomadas" in titulo
            cabecera_vista = False
            continue
        if not en_seccion or not linea.startswith("|"):
            continue
        if _RX_SEPARADOR.match(linea):
            continue
        if not cabecera_vista:
            cabecera_vista = True       # la primera fila de cada tabla es su cabecera
            continue
        decisiones += 1
    lineas = texto.splitlines()
    return {"decisiones": decisiones,
            "tareas_abiertas": sum(1 for x in lineas if _RX_CASILLA_ABIERTA.match(x)),
            "tareas_hechas": sum(1 for x in lineas if _RX_CASILLA_HECHA.match(x))}


def _decisiones(ctx: Ctx, avisos: list[str]) -> dict[str, Any]:
    base = ctx.raiz_confinada
    fuentes: list[dict[str, Any]] = []
    for clave, titulo, rel in FUENTES_DECISIONES:
        fila: dict[str, Any] = {"clave": clave, "titulo": titulo, "ruta": rel, "existe": False, "bytes": None, "sha256": None,
                                "modificado": None, "decisiones": None, "tareas_abiertas": None, "tareas_hechas": None}
        try:
            datos, truncado, st = base.bytes(rel, _TOPE_DOC)
        except Exception:  # noqa: BLE001
            fuentes.append(fila)
            continue
        fila.update({"existe": True, "bytes": st.st_size, "modificado": iso_mtime(st)})
        if truncado:
            avisos.append(f"Un documento de decisiones es demasiado grande (supera {_TOPE_DOC // 1024} KB) y no se cuenta ({rel}).")
        else:
            fila["sha256"] = hashlib.sha256(datos).hexdigest()
            fila.update(contar_decisiones(datos.decode("utf-8", "replace")))
        fuentes.append(fila)
    return {"fuentes": fuentes, "memoria": _decisiones_guardadas(ctx, avisos)}


def _decisiones_guardadas(ctx: Ctx, avisos: list[str]) -> dict[str, Any]:
    rel = f"{REL_MEMORIA}/decisiones_dueno.jsonl"
    lec = ctx.raiz_confinada.jsonl_cola(rel, maximo=_MAX_DECISIONES)
    if lec.estado != "ok":
        return {"ruta": rel, "existe": False, "total": 0, "vigentes": 0, "ultimas": []}
    avisos.extend(lec.avisos)
    ultimas: list[dict[str, Any]] = []
    for _, obj, _crudo in lec.lineas:
        if not isinstance(obj, dict):
            continue
        ultimas.append({"id": _texto(obj.get("id"), 20), "ts": _texto(obj.get("ts"), 40), "titulo": _texto(obj.get("titulo"), 140),
                        "detalle": _texto(obj.get("detalle")), "alcance": _texto(obj.get("alcance"), 30), "etapa": _texto(obj.get("etapa"), 12),
                        "oferta_id": _texto(obj.get("oferta_id"), 40), "origen": _texto(obj.get("origen"), 80),
                        "vigente": obj.get("vigente") is not False, "reemplaza": _texto(obj.get("reemplaza"), 20)})
    # Vigente = no marcada como no vigente y no reemplazada por una línea posterior (las decisiones nunca se editan: se reemplazan).
    reemplazadas = {u["reemplaza"] for u in ultimas if u["reemplaza"]}
    for u in ultimas:
        u["vigente"] = u["vigente"] and u["id"] not in reemplazadas
    return {"ruta": rel, "existe": True, "total": lec.total or 0, "vigentes": sum(1 for u in ultimas if u["vigente"]), "ultimas": ultimas}


# ----------------------------------------------------------------------------------------------
# reglas: resumen de solo lectura
# ----------------------------------------------------------------------------------------------
def _contar_nulos(valor: Any, _nivel: int = 0) -> tuple[int, int]:
    """``(claves con null, claves totales)`` de un mapa anidado."""
    if _nivel > 6 or not isinstance(valor, dict):
        return 0, 0
    nulos = total = 0
    for v in valor.values():
        if isinstance(v, dict):
            n, t = _contar_nulos(v, _nivel + 1)
            nulos += n
            total += t
        else:
            total += 1
            nulos += 1 if v is None else 0
    return nulos, total


def _reglas(ctx: Ctx, avisos: list[str]) -> dict[str, Any]:
    emp = ctx.empresa()
    base = ctx.raiz_confinada
    salida: dict[str, Any] = {}

    def hash_de(rel: str) -> str | None:
        return _hash_archivo(base, rel, 2 * 1024 * 1024)[0]

    par = emp.yaml("parametros.yaml")
    fila_par: dict[str, Any] = {"ruta": "empresa/parametros.yaml", "existe": par.estado != "ausente", "sha256": hash_de("empresa/parametros.yaml"),
                                "version": None, "grupos": 0, "claves": 0, "hipotesis": 0, "sin_valor": 0}
    if par.ok and isinstance(par.dato, dict):
        fila_par["version"] = _entero(par.dato.get("version"))
        grupos = par.dato.get("grupos") if isinstance(par.dato.get("grupos"), dict) else {}
        fila_par["grupos"] = len(grupos)
        for claves in grupos.values():
            if not isinstance(claves, dict):
                continue
            for v in claves.values():
                if isinstance(v, dict) and "valor" in v:
                    fila_par["claves"] += 1
                    fila_par["hipotesis"] += 1 if v.get("hipotesis") is True else 0
                    fila_par["sin_valor"] += 1 if v["valor"] is None else 0
    elif par.aviso:
        avisos.append(par.aviso)
    salida["parametros"] = fila_par

    lim = emp.yaml("limites.yaml")
    fila_lim: dict[str, Any] = {"ruta": "empresa/limites.yaml", "existe": lim.estado != "ausente", "sha256": hash_de("empresa/limites.yaml"),
                                "version": None, "sellado": False, "claves": 0, "sin_valor": 0}
    if lim.ok and isinstance(lim.dato, dict):
        fila_lim["version"] = _entero(lim.dato.get("version"))
        fila_lim["sellado"] = lim.dato.get("sello") is not None
        propios = {k: v for k, v in lim.dato.items() if k not in ("sello", "schema_version", "version")}
        fila_lim["sin_valor"], fila_lim["claves"] = _contar_nulos({"x": propios})
    elif lim.aviso:
        avisos.append(lim.aviso)
    salida["limites"] = fila_lim

    aut = emp.yaml("autonomia.yaml")
    fila_aut: dict[str, Any] = {"ruta": "empresa/autonomia.yaml", "existe": aut.estado != "ausente", "sha256": hash_de("empresa/autonomia.yaml"),
                                "version": None, "etapas": 0, "por_nivel": {}}
    if aut.ok and isinstance(aut.dato, dict):
        fila_aut["version"] = _entero(aut.dato.get("version"))
        niveles = aut.dato.get("nivel_por_etapa") if isinstance(aut.dato.get("nivel_por_etapa"), dict) else {}
        fila_aut["etapas"] = len(niveles)
        for v in niveles.values():
            n = v.get("nivel") if isinstance(v, dict) else None
            if isinstance(n, str) and re.fullmatch(r"N[0-4]", n):
                fila_aut["por_nivel"][n] = fila_aut["por_nivel"].get(n, 0) + 1
    elif aut.aviso:
        avisos.append(aut.aviso)
    salida["autonomia"] = fila_aut
    salida["sellos_compliance"] = {"ruta": "empresa/compliance/sellos", "archivos": len([n for n in emp.listar("compliance/sellos", solo="archivo") if n.endswith(".json")])}
    return salida


# ----------------------------------------------------------------------------------------------
# lecciones
# ----------------------------------------------------------------------------------------------
def _lecciones_qa_y_postmortems(ctx: Ctx, avisos: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    hallazgos: list[dict[str, Any]] = []
    aprendizajes: list[dict[str, Any]] = []
    archivos_qa = 0
    truncado = False
    postmortems: list[dict[str, Any]] = []
    for oferta_id in ids_de_ofertas(ctx):
        demo = oferta_id.startswith("_")
        r = ctx.oferta(oferta_id)
        for nombre in r.listar("qa", solo="archivo"):
            if not nombre.endswith(".json"):
                continue
            lec = r.json(f"qa/{nombre}", tope=TOPE_JSON)
            if not (lec.ok and isinstance(lec.dato, dict)):
                if lec.aviso:
                    avisos.append(lec.aviso)
                continue
            archivos_qa += 1
            d = lec.dato
            etapa = _texto(d.get("etapa"), 12)
            for h in d.get("hallazgos") if isinstance(d.get("hallazgos"), list) else []:
                if not isinstance(h, dict):
                    continue
                if len(hallazgos) >= _MAX_HALLAZGOS:
                    truncado = True
                    break
                hallazgos.append({"oferta_id": oferta_id, "demo": demo, "etapa": _texto(h.get("etapa"), 12) or etapa, "archivo": f"qa/{nombre}",
                                  "check_id": _texto(h.get("check_id"), 40), "patron_clave": _texto(h.get("patron_clave"), 60),
                                  "severidad": _texto(h.get("severidad"), 20), "descripcion": _texto(h.get("descripcion")),
                                  "estado": _texto(h.get("estado"), 40)})
            for a in d.get("aprendizajes_para_skill") if isinstance(d.get("aprendizajes_para_skill"), list) else []:
                texto = _texto(a)
                if not texto:
                    continue
                if len(aprendizajes) >= _MAX_APRENDIZAJES:
                    truncado = True
                    break
                aprendizajes.append({"oferta_id": oferta_id, "demo": demo, "etapa": etapa, "archivo": f"qa/{nombre}", "texto": texto})
        rel_pm = "08-operacion/postmortem.json"
        lec = r.json(rel_pm, tope=TOPE_JSON)
        if lec.ok and isinstance(lec.dato, dict) and len(postmortems) < _MAX_POSTMORTEMS:
            d = lec.dato
            lista = [t for t in (_texto(x) for x in (d.get("aprendizajes") if isinstance(d.get("aprendizajes"), list) else [])) if t][:8]
            postmortems.append({"oferta_id": oferta_id, "demo": demo, "ruta": f"ofertas/{oferta_id}/{rel_pm}", "veredicto": _texto(d.get("veredicto"), 20),
                                "causa_principal": _texto(d.get("causa_principal"), 80), "generado_en": _texto(d.get("generado_en"), 40),
                                "origen_version": _texto(d.get("origen_version"), 20), "aprendizajes": lista,
                                "sha256": _hash_archivo(ctx.raiz_confinada, f"ofertas/{oferta_id}/{rel_pm}", TOPE_JSON)[0]})
        elif lec.aviso:
            avisos.append(lec.aviso)
    qa = {"archivos": archivos_qa, "hallazgos": hallazgos, "aprendizajes": aprendizajes, "truncado": truncado}
    return qa, postmortems


def _lecciones_guardadas(ctx: Ctx, avisos: list[str]) -> dict[str, Any]:
    rel = f"{REL_MEMORIA}/lecciones.jsonl"
    lec = ctx.raiz_confinada.jsonl_cola(rel, maximo=_MAX_LECCIONES)
    if lec.estado != "ok":
        return {"ruta": rel, "existe": False, "total": 0, "ultimas": []}
    avisos.extend(lec.avisos)
    ultimas: list[dict[str, Any]] = []
    for _, obj, _crudo in lec.lineas:
        if not isinstance(obj, dict):
            continue
        evidencia = []
        for ev in obj.get("evidencia") if isinstance(obj.get("evidencia"), list) else []:
            if isinstance(ev, dict) and _texto(ev.get("ruta"), 200):
                evidencia.append({"ruta": _texto(ev.get("ruta"), 200), "sha256": _texto(ev.get("sha256"), 80)})
        ultimas.append({"id": _texto(obj.get("id"), 20), "ts": _texto(obj.get("ts"), 40), "titulo": _texto(obj.get("titulo"), 140),
                        "leccion": _texto(obj.get("leccion")), "etapa": _texto(obj.get("etapa"), 12), "oferta_id": _texto(obj.get("oferta_id"), 40),
                        "confianza": _texto(obj.get("confianza"), 4), "alcance": _texto(obj.get("alcance"), 30), "estado": _texto(obj.get("estado"), 30),
                        "evidencia": evidencia[:5]})
    return {"ruta": rel, "existe": True, "total": lec.total or 0, "ultimas": ultimas}


# ----------------------------------------------------------------------------------------------
# jardín
# ----------------------------------------------------------------------------------------------
def _jardin(ctx: Ctx) -> dict[str, Any]:
    nombres = [n for n in ctx.raiz_confinada.listar(REL_JARDIN, solo="archivo") if n.endswith((".json", ".jsonl", ".md"))]
    return {"ruta": REL_JARDIN, "existe": ctx.raiz_confinada.es_directorio(REL_JARDIN), "propuestas": len(nombres), "ultima": nombres[-1] if nombres else None}


# ----------------------------------------------------------------------------------------------
def cerebro(ctx: Ctx) -> Sobre:
    """Resumen de solo lectura del Cerebro (ver el docstring del módulo). Nunca lanza por datos ausentes o corruptos."""
    avisos: list[str] = []
    memoria = _memoria(ctx, avisos)
    decisiones = _decisiones(ctx, avisos)
    reglas = _reglas(ctx, avisos)
    qa, postmortems = _lecciones_qa_y_postmortems(ctx, avisos)
    guardadas = _lecciones_guardadas(ctx, avisos)
    jardin = _jardin(ctx)
    datos = {"memoria": memoria, "decisiones": decisiones, "reglas": reglas,
             "lecciones": {"qa": qa, "postmortems": postmortems, "memoria": guardadas}, "jardin": jardin}
    hay_algo = (any(f["existe"] for f in memoria["archivos"]) or any(f["existe"] for f in decisiones["fuentes"])
                or reglas["parametros"]["existe"] or reglas["limites"]["existe"] or qa["archivos"] or postmortems)
    fuente = [f for _, f, _ in ARCHIVOS_MEMORIA] + [f for _, _, f in FUENTES_DECISIONES] + [
        "empresa/parametros.yaml", "empresa/limites.yaml", "empresa/autonomia.yaml", "ofertas/*/qa/*.json", "ofertas/*/08-operacion/postmortem.json"]
    if not memoria["carpeta"]["existe"]:
        avisos.append("Todavía no hay memoria guardada. Se crea sola la primera vez que cierras una sesión con /cerebro-cerrar y se guarda una decisión o una lección (carpeta empresa/memoria/).")
    return Sobre(datos, fuente, vacio=not hay_algo, avisos=avisos)
