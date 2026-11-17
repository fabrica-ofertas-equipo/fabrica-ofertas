"""``GET /api/registro`` y ``GET /api/agentes[/<ejecucion_id>]`` desde ``empresa/registro.jsonl`` y ``empresa/costos.jsonl``.

El registro es una cadena ``hash_previo → hash`` que solo escribe ``engine.registro.registrar``; aquí se lee la cola,
se comprueba la cadena (``cadena_ok``) y se agrupan las líneas por ``ejecucion_id``. Si el registro real aún no existe
y existe la oferta demo, se muestran los datos de ``ofertas/_ejemplo/_empresa/`` marcados con ``demo: true``.
"""
from __future__ import annotations

import re
import threading
from typing import Any

from dashboard.api_base import Ctx, RX_EJECUCION, RX_OFERTA, Sobre, carpetas_por_id_interno
from dashboard.archivos import Raiz
from dashboard.seguridad import ErrorHttp

__all__ = ["agentes", "agente_detalle", "registro"]

_MAX_VENTANA = 20000          # líneas del registro que se leen para filtrar/agrupar
_MAX_EJECUCIONES = 500
_MAX_COSTOS = 20000
_LIMITE_DEFECTO = 200
_LIMITE_MAX = 1000

_RX_QA = re.compile(r"(^|[-:_])qa$|^qa[-:_]", re.IGNORECASE)   # misma regla que el frontend (agentes.js)
_CACHE_CADENA: dict[tuple[str, int, int], tuple[bool | None, str | None]] = {}
_CERROJO_CADENA = threading.Lock()


def _fuente(ctx: Ctx, oferta: str | None = None) -> tuple[Raiz, str, str, str, bool]:
    """``(base, rel_registro, rel_costos, etiqueta_registro, es_demo)``.

    * ``oferta`` = carpeta de una oferta DEMO (``_ejemplo``…): se lee SU registro propio
      (``ofertas/<demo>/_empresa/registro.jsonl``), sin mezclarlo con ``empresa/registro.jsonl``; si no existe, queda vacío.
    * Si no, el registro real; y solo si éste no existe y hay una demo con registro, se muestra ese (marcado ``demo``).
    """
    emp = ctx.empresa()
    if oferta and RX_OFERTA.fullmatch(oferta) and oferta.startswith("_"):
        demo = ctx.oferta(oferta)
        return demo, "_empresa/registro.jsonl", "_empresa/costos.jsonl", f"ofertas/{oferta}/_empresa/registro.jsonl", True
    if emp.stat("registro.jsonl") is not None:
        return emp, "registro.jsonl", "costos.jsonl", "empresa/registro.jsonl", False
    demo = ctx.oferta("_ejemplo")
    if demo.stat("_empresa/registro.jsonl") is not None:
        return demo, "_empresa/registro.jsonl", "_empresa/costos.jsonl", "ofertas/_ejemplo/_empresa/registro.jsonl", True
    return emp, "registro.jsonl", "costos.jsonl", "empresa/registro.jsonl", False


def _es_oferta_demo(oferta: str | None) -> bool:
    return bool(oferta and RX_OFERTA.fullmatch(oferta) and oferta.startswith("_"))


def _cadena(base: Raiz, rel: str) -> tuple[bool | None, str | None]:
    """¿La cadena de hashes es válida? ``(True|False|None, motivo)``. Se cachea por (ruta, mtime, tamaño)."""
    st = base.stat(rel)
    if st is None:
        return None, None
    clave = (str(base.base / rel), st.st_mtime_ns, st.st_size)
    with _CERROJO_CADENA:
        if clave in _CACHE_CADENA:
            return _CACHE_CADENA[clave]
    objetos, motivo = base.jsonl_completo(rel)
    if objetos is None:
        resultado: tuple[bool | None, str | None] = (False if motivo == "hay líneas ilegibles" else None, motivo)
    elif any("hash" not in o or "hash_previo" not in o for o in objetos):
        resultado = (False, "hay líneas sin su huella (hash) o sin la huella de la línea anterior")
    else:
        try:
            from scripts.validar_esquemas import cadena_registro_valida
        except Exception:  # noqa: BLE001 - sin el verificador del proyecto no se afirma nada
            resultado = (None, "no se pudo cargar el verificador de la cadena (scripts.validar_esquemas)")
        else:
            try:
                errores = cadena_registro_valida(objetos)
            except (KeyError, TypeError, ValueError):
                errores = ["no se pudo verificar la cadena"]
            resultado = (not errores, errores[0] if errores else None)
    with _CERROJO_CADENA:
        if len(_CACHE_CADENA) > 16:
            _CACHE_CADENA.clear()
        _CACHE_CADENA[clave] = resultado
    return resultado


def _entero(consulta: dict[str, list[str]], nombre: str, minimo: int, maximo: int, defecto: int | None) -> int | None:
    crudo = (consulta.get(nombre) or [""])[0]
    if crudo == "":
        return defecto
    try:
        return max(minimo, min(maximo, int(crudo)))
    except ValueError as exc:
        raise ErrorHttp(400, "parametro_invalido", f"El valor de «{nombre}» tiene que ser un número entero.") from exc


def _texto(consulta: dict[str, list[str]], nombre: str) -> str | None:
    crudo = ((consulta.get(nombre) or [""])[0]).strip()[:80]
    return crudo or None


def registro(ctx: Ctx, consulta: dict[str, list[str]]) -> Sobre:
    """Cola del registro: ``{lineas:[{n, …}], total, siguiente, cadena_ok}``; ``desde``/``limite`` y filtros opcionales."""
    desde = _entero(consulta, "desde", 1, 10**12, None)
    limite = _entero(consulta, "limite", 1, _LIMITE_MAX, _LIMITE_DEFECTO) or _LIMITE_DEFECTO
    f_oferta, f_etapa, f_agente = _texto(consulta, "oferta"), _texto(consulta, "etapa"), _texto(consulta, "agente")
    base, rel, _, etiqueta, demo = _fuente(ctx, f_oferta)
    propia = _es_oferta_demo(f_oferta)   # el registro propio de una demo solo trae líneas de esa demo: no se filtra por oferta_id
    lec = base.jsonl_cola(rel, maximo=_MAX_VENTANA)
    avisos = list(lec.avisos)
    extra: dict[str, Any] = {"demo": demo}
    if lec.estado != "ok":
        avisos.append(f"Todavía no hay historial de actividad ({etiqueta}): " + ("la oferta de demostración no trae uno propio." if propia else
                      "lo va escribiendo el sistema automático cada vez que ejecuta algo."))
        return Sobre({"lineas": [], "total": 0, "siguiente": 1, "cadena_ok": None}, [etiqueta], vacio=True, avisos=avisos, extra=extra)
    if demo:
        avisos.append(f"Son datos de DEMOSTRACIÓN, no reales (carpeta {etiqueta.rsplit('/', 1)[0]}/)."
                      + ("" if propia else " Todavía no existe el historial real (empresa/registro.jsonl)."))
    items: list[dict[str, Any]] = []
    for n, obj, texto in lec.lineas:
        if obj is None:
            if (f_oferta and not propia) or f_etapa or f_agente:
                continue
            items.append({"n": n, "_ilegible": True, "_texto": texto})
            continue
        if f_oferta and not propia and obj.get("oferta_id") != f_oferta:
            continue
        if f_etapa and obj.get("etapa") != f_etapa:
            continue
        if f_agente and obj.get("agente") != f_agente:
            continue
        items.append({"n": n, **obj})
    total = lec.total or 0
    if desde is not None:
        elegidas = [i for i in items if i["n"] >= desde][:limite]
        siguiente = elegidas[-1]["n"] + 1 if len(elegidas) == limite else total + 1
    else:
        elegidas = items[-limite:]
        siguiente = total + 1
    cadena_ok, motivo = _cadena(base, rel)
    if cadena_ok is False:
        avisos.append(f"Historial alterado: el historial pudo haberse modificado ({etiqueta}). Motivo: {str(motivo or '').rstrip('.')}. No uses estos datos para decidir.")
    elif cadena_ok is None and motivo:
        avisos.append(f"No se pudo comprobar que el historial esté intacto: {motivo}")
    return Sobre({"lineas": elegidas, "total": total, "siguiente": siguiente, "cadena_ok": cadena_ok},
                 [etiqueta], vacio=False, avisos=avisos, extra=extra)


# ----------------------------------------------------------------------------------------------
# Ejecuciones
# ----------------------------------------------------------------------------------------------
def _suma(por_moneda: dict[str, int], dinero: Any) -> None:
    if isinstance(dinero, dict) and isinstance(dinero.get("monto"), int) and not isinstance(dinero.get("monto"), bool) \
            and isinstance(dinero.get("moneda"), str):
        por_moneda[dinero["moneda"]] = por_moneda.get(dinero["moneda"], 0) + dinero["monto"]


def _estado_ejecucion(resultados: list[str]) -> str:
    if "error" in resultados:
        return "error"
    if "bloqueado" in resultados:
        return "bloqueado"
    if resultados and all(r == "dry_run" for r in resultados):
        return "dry_run"
    return "ok"


def _agrupar(lineas: list[tuple[int, Any, str]], costos: dict[str, dict[str, int]]) -> dict[str, dict[str, Any]]:
    grupos: dict[str, dict[str, Any]] = {}
    for n, obj, _ in lineas:
        if obj is None or not isinstance(obj.get("ejecucion_id"), str):
            continue
        g = grupos.setdefault(obj["ejecucion_id"], {"lineas": [], "resultados": [], "por_moneda": {}})
        g["lineas"].append({"n": n, **obj})
        res = obj.get("resultado")
        g["resultados"].append(res.get("estado") if isinstance(res, dict) and isinstance(res.get("estado"), str) else "")
        _suma(g["por_moneda"], obj.get("costo_estimado"))
    salida: dict[str, dict[str, Any]] = {}
    for eid, g in grupos.items():
        ls = g["lineas"]
        tss = [l.get("ts") for l in ls if isinstance(l.get("ts"), str)]
        por_moneda = costos.get(eid) or g["por_moneda"]
        costo = None
        if len(por_moneda) == 1:
            (moneda, monto), = por_moneda.items()
            costo = {"monto": monto, "moneda": moneda}
        salida[eid] = {
            "ejecucion_id": eid, "oferta_id": ls[0].get("oferta_id"), "etapa": ls[0].get("etapa"), "agente": ls[0].get("agente"),
            "inicio": min(tss) if tss else None, "fin": max(tss) if tss else None,
            "estado": _estado_ejecucion(g["resultados"]), "costo": costo, "costo_por_moneda": dict(por_moneda),
            "costo_fuente": "costos.jsonl" if eid in costos else "registro", "modo": ls[0].get("modo"),
            "agentes": sorted({l["agente"] for l in ls if isinstance(l.get("agente"), str)}),
            "n_eventos": len(ls), "_lineas": ls,
        }
    return salida


def _agregar_rondas_qa(ctx: Ctx, grupos: dict[str, dict[str, Any]]) -> None:
    """Agrega a cada ejecución ``ronda_qa``, ``rondas_qa`` y ``rondas_qa_fuente`` (aditivo; ``null`` = sin dato, nunca 0 inventado).

    * ``ronda_qa``: si la ejecución es de un agente QA, su ORDINAL (1, 2…) entre las ejecuciones QA de la misma (oferta, etapa)
      ordenadas por inicio; ``null`` en las demás.
    * ``rondas_qa``: rondas de QA de la (oferta, etapa): el contador del motor (``estado.json`` → ``etapas.<E>.ronda_qa``) si
      existe (``rondas_qa_fuente: "estado"``); si no, el nº de ejecuciones QA distintas del registro (``"registro"``).
    """
    cubos: dict[tuple[Any, Any], list[tuple[str, str]]] = {}
    for eid, g in grupos.items():
        if any(_RX_QA.search(a) for a in g["agentes"]):
            cubos.setdefault((g["oferta_id"], g["etapa"]), []).append((g["inicio"] or "", eid))
    ordinal = {eid: k for lista in cubos.values() for k, (_, eid) in enumerate(sorted(lista), start=1)}
    mapa = carpetas_por_id_interno(ctx)
    estados: dict[str, Any] = {}
    for eid, g in grupos.items():
        etapa, oferta = g["etapa"], g["oferta_id"]
        rondas, fuente = None, None
        carpeta = mapa.get(oferta) if isinstance(oferta, str) else None
        if carpeta is not None and isinstance(etapa, str):
            if carpeta not in estados:
                lec = ctx.oferta(carpeta).json("estado.json")
                estados[carpeta] = lec.dato.get("etapas") if lec.ok and isinstance(lec.dato, dict) and isinstance(lec.dato.get("etapas"), dict) else {}
            info = estados[carpeta].get(etapa)
            valor = info.get("ronda_qa") if isinstance(info, dict) else None
            if isinstance(valor, int) and not isinstance(valor, bool):
                rondas, fuente = valor, "estado"
        if rondas is None and (oferta, etapa) in cubos:
            rondas, fuente = len(cubos[(oferta, etapa)]), "registro"
        g["ronda_qa"] = ordinal.get(eid)
        g["rondas_qa"] = rondas
        g["rondas_qa_fuente"] = fuente


def _costos(base: Raiz, rel: str, avisos: list[str]) -> dict[str, dict[str, int]]:
    lec = base.jsonl_cola(rel, maximo=_MAX_COSTOS)
    avisos.extend(lec.avisos)
    salida: dict[str, dict[str, int]] = {}
    if lec.estado != "ok":
        return salida
    for _, obj, _ in lec.lineas:
        if obj is not None and isinstance(obj.get("ejecucion_id"), str):
            _suma(salida.setdefault(obj["ejecucion_id"], {}), obj.get("monto"))
    return salida


def _cargar(ctx: Ctx, oferta: str | None = None) -> tuple[dict[str, dict[str, Any]], list[str], list[str], bool, bool]:
    base, rel, rel_costos, etiqueta, demo = _fuente(ctx, oferta)
    avisos: list[str] = []
    lec = base.jsonl_cola(rel, maximo=_MAX_VENTANA)
    avisos.extend(lec.avisos)
    if lec.estado != "ok":
        avisos.append(f"Todavía no hay historial de actividad ({etiqueta}): lo va escribiendo el sistema automático cada vez que ejecuta algo.")
        return {}, [etiqueta], avisos, False, demo
    if demo:
        avisos.append(f"Son datos de DEMOSTRACIÓN, no reales (carpeta {etiqueta.rsplit('/', 1)[0]}/)."
                      + ("" if _es_oferta_demo(oferta) else " Todavía no existe el historial real (empresa/registro.jsonl)."))
    costos = _costos(base, rel_costos, avisos)
    fuente = [etiqueta, etiqueta.replace("registro.jsonl", "costos.jsonl")]
    grupos = _agrupar(lec.lineas, costos)
    _agregar_rondas_qa(ctx, grupos)
    return grupos, fuente, avisos, True, demo


def agentes(ctx: Ctx, consulta: dict[str, list[str]]) -> Sobre:
    """Ejecuciones agrupadas (más recientes primero) con filtros ``oferta``, ``etapa``, ``agente`` y ``limite``."""
    f_oferta, f_etapa, f_agente = _texto(consulta, "oferta"), _texto(consulta, "etapa"), _texto(consulta, "agente")
    grupos, fuente, avisos, hay, demo = _cargar(ctx, f_oferta)
    limite = _entero(consulta, "limite", 1, _MAX_EJECUCIONES, _MAX_EJECUCIONES) or _MAX_EJECUCIONES
    filas = []
    for g in grupos.values():
        if f_oferta and not _es_oferta_demo(f_oferta) and g["oferta_id"] != f_oferta:
            continue
        if f_etapa and g["etapa"] != f_etapa:
            continue
        if f_agente and f_agente not in g["agentes"]:
            continue
        fila = {k: v for k, v in g.items() if k != "_lineas"}
        fila["eventos"] = fila.pop("n_eventos")
        filas.append(fila)
    filas.sort(key=lambda f: f["inicio"] or "", reverse=True)
    if len(filas) > limite:
        avisos.append(f"Se muestran las {limite} ejecuciones más recientes (hay {len(filas)} en total).")
        filas = filas[:limite]
    return Sobre(filas, fuente, vacio=not hay, avisos=avisos, extra={"demo": demo})


def agente_detalle(ctx: Ctx, ejecucion_id: str, consulta: dict[str, list[str]] | None = None) -> Sobre:
    """Una ejecución con la lista completa de sus eventos (``eventos``; ``n_eventos`` es el conteo).

    ``?oferta=<carpeta demo>`` busca en el registro propio de esa oferta demo (igual que ``/agentes`` y ``/registro``).
    """
    if not RX_EJECUCION.fullmatch(ejecucion_id or ""):
        raise ErrorHttp(400, "ejecucion_invalida", "El código de la ejecución no es válido.")
    grupos, fuente, avisos, hay, demo = _cargar(ctx, _texto(consulta or {}, "oferta"))
    if not hay:
        return Sobre(None, fuente, vacio=True, avisos=avisos, extra={"demo": demo})
    g = grupos.get(ejecucion_id)
    if g is None:
        raise ErrorHttp(404, "ejecucion_no_encontrada", "No encontramos esa ejecución entre las más recientes del historial.")
    fila = {k: v for k, v in g.items() if k not in ("_lineas",)}
    fila["eventos"] = g["_lineas"]
    return Sobre(fila, fuente, vacio=False, avisos=avisos, extra={"demo": demo})
