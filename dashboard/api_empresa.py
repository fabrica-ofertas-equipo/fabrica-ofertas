"""Lectores de empresa: ``/api/finanzas``, ``/api/cumplimiento``, ``/api/parametros`` y ``/api/skills``.

Solo lectura de ``empresa/**``, ``ofertas/*/qa/`` y ``.claude/``. YAML con ``safe_load`` sin alias. Lo que no existe
todavía (el motor se está construyendo) se devuelve vacío con ``fuente`` y un aviso que dice qué lo produce.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from dashboard.api_base import Ctx, Sobre, carpetas_por_id_interno, ids_de_ofertas
from dashboard.api_ofertas import leer_archivo
from dashboard.archivos import Raiz, cargar_yaml_seguro
from dashboard.seguridad import ErrorHttp

__all__ = ["cumplimiento", "finanzas", "gates", "parametros", "skill_archivo", "skills"]

_MAX_LEDGER = 500
_MAX_ALERTAS = 200
_MAX_CLAVES = 500
_RX_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_RX_AGENTE = re.compile(r"^[a-z0-9][a-z0-9-]*-(maker|qa)\.md$")
_RX_FRONT = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_RX_VERSION = re.compile(r"^#{1,3}\s*\[?v?([0-9]+\.[0-9]+\.[0-9]+)", re.MULTILINE)
_RX_DOD = re.compile(r"^#{1,6}\s*(definici[oó]n de listo|dod)\b", re.IGNORECASE)
_RX_CASILLA = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+(.*\S)\s*$")
_RX_VINETA = re.compile(r"^\s*[-*]\s+(.*\S)\s*$")


def _lineas(r: Raiz, rel: str, maximo: int, avisos: list[str]) -> tuple[list[dict[str, Any]], bool, int | None, bool]:
    """``(objetos, existe, total de líneas del archivo, truncado)``: ``truncado`` si hay más líneas que las devueltas."""
    lec = r.jsonl_cola(rel, maximo=maximo)
    avisos.extend(lec.avisos)
    if lec.estado != "ok":
        return [], False, None, False
    objetos = [obj for _, obj, _ in lec.lineas if isinstance(obj, dict)]
    truncado = lec.truncado or (lec.total is not None and lec.total > len(lec.lineas))
    return objetos, True, lec.total, truncado


def finanzas(ctx: Ctx) -> Sobre:
    """``{ledger, pnl, conciliacion, alertas}`` de ``empresa/finanzas/`` y ``empresa/datos/alertas.jsonl``.

    El ledger y las alertas se cortan a sus últimas ``_MAX_LEDGER``/``_MAX_ALERTAS`` líneas: el sobre lleva ``truncado`` (¿se cortó
    alguno?), ``total`` (líneas del ledger) y ``total_alertas``/``truncado_ledger``/``truncado_alertas`` para saber cuál.
    """
    emp = ctx.empresa()
    avisos: list[str] = []
    fuente = ["empresa/finanzas/ledger.jsonl", "empresa/finanzas/pnl.json", "empresa/finanzas/conciliacion.json",
              "empresa/datos/alertas.jsonl"]
    ledger, hay_l, total_l, trunc_l = _lineas(emp, "finanzas/ledger.jsonl", _MAX_LEDGER, avisos)
    pnl = emp.json("finanzas/pnl.json")
    conc = emp.json("finanzas/conciliacion.json")
    alertas, hay_a, total_a, trunc_a = _lineas(emp, "datos/alertas.jsonl", _MAX_ALERTAS, avisos)
    for lec in (pnl, conc):
        if lec.estado not in ("ok", "ausente") and lec.aviso:
            avisos.append(lec.aviso)
    if trunc_l:
        avisos.append(f"Del libro de movimientos se muestran solo los últimos {_MAX_LEDGER} (hay {total_l} en total).")
    if trunc_a:
        avisos.append(f"Se muestran solo las últimas {_MAX_ALERTAS} alertas (hay {total_a} en total).")
    vacio = not (hay_l or pnl.ok or conc.ok or hay_a)
    if vacio:
        avisos.append("Todavía no hay datos de finanzas. El libro de movimientos, las ganancias y pérdidas y la conciliación "
                      "(que lo cobrado, lo registrado y lo gastado en anuncios cuadren) se generan con `python -m datos.ledger`; "
                      "las alertas, con `python -m dashboard.alertas` (carpeta empresa/finanzas/).")
    datos = {"ledger": ledger, "pnl": pnl.dato if pnl.ok else None, "conciliacion": conc.dato if conc.ok else None,
             "alertas": alertas}
    extra = {"truncado": bool(trunc_l or trunc_a), "truncado_ledger": trunc_l, "truncado_alertas": trunc_a,
             "total": total_l, "total_alertas": total_a}
    return Sobre(datos, fuente, vacio=vacio, avisos=avisos, extra=extra)


def _txt(d: dict[str, Any], clave: str) -> str | None:
    return d.get(clave) if isinstance(d.get(clave), str) else None


def _resumen_dictamen(carpeta: str, nombre: str, d: dict[str, Any], interno: str | None) -> dict[str, Any]:
    hallazgos = d.get("hallazgos")
    return {
        "oferta_id": carpeta, "oferta_id_interno": _txt(d, "oferta_id") or interno,
        "archivo": f"qa/{nombre}", "ruta": f"ofertas/{carpeta}/qa/{nombre}",
        "etapa": _txt(d, "etapa"), "etapa_objetivo": _txt(d, "etapa_objetivo"), "version": _txt(d, "version"),
        "ronda": d.get("ronda") if isinstance(d.get("ronda"), int) and not isinstance(d.get("ronda"), bool) else None,
        "ambito": _txt(d, "ambito"), "veredicto": _txt(d, "veredicto"), "semaforo": _txt(d, "semaforo"),
        "creado_en": _txt(d, "creado_en"), "vigencia_hasta": _txt(d, "vigencia_hasta"), "reglas_version": _txt(d, "reglas_version"),
        "artefacto_ref": _txt(d, "artefacto_ref"), "artefacto_sha256": _txt(d, "artefacto_sha256"),
        "n_hallazgos": len(hallazgos) if isinstance(hallazgos, list) else None,
    }


_TOPE_HASH_ARCHIVOS = 400
_TOPE_HASH_BYTES = 20 * 1024 * 1024


def _hash_seguro(real: Path) -> tuple[str | None, str | None]:
    """Hash con la convención de ``compliance.sellar`` (archivo o carpeta) SOLO si es barato y seguro; si no, ``(None, motivo)``.

    Seguro: la ruta ya salió del resolvedor confinado, la carpeta no contiene enlaces simbólicos. Barato: ≤ 400 archivos y ≤ 20 MB.
    """
    try:
        if real.is_dir():
            archivos = tamano = 0
            for base, carpetas, nombres in os.walk(real, followlinks=False):
                if any(os.path.islink(os.path.join(base, n)) for n in (*carpetas, *nombres)):
                    return None, "Lo revisado contiene enlaces simbólicos (accesos directos a otros lugares): por seguridad no se vuelve a calcular su huella."
                archivos += len(nombres)
                tamano += sum(os.path.getsize(os.path.join(base, n)) for n in nombres)
                if archivos > _TOPE_HASH_ARCHIVOS or tamano > _TOPE_HASH_BYTES:
                    return None, "Lo revisado es demasiado grande para volver a calcular su huella desde el panel."
        elif real.is_file():
            if real.stat().st_size > _TOPE_HASH_BYTES:
                return None, "Lo revisado es demasiado grande para volver a calcular su huella desde el panel."
        else:
            return None, "Lo revisado ya no existe."
        from scripts.validar_esquemas import hash_archivo, hash_directorio
        return (hash_directorio(real) if real.is_dir() else hash_archivo(real)), None
    except Exception:  # noqa: BLE001 - un archivo ilegible no debe romper la pantalla de cumplimiento
        return None, "No se pudo volver a calcular la huella de lo revisado."


def _verificacion_de_sello(ctx: Ctx, carpeta: str | None, sello: dict[str, Any]) -> dict[str, Any]:
    """``hash_actual`` (artefacto) y ``dictamen_hash_actual`` recalculados; ``alterado`` solo si hay con qué comparar."""
    salida: dict[str, Any] = {"hash_actual": None, "hash_coincide": None, "dictamen_hash_actual": None, "dictamen_coincide": None,
                              "alterado": None, "firma_valida": None, "verificacion": None}
    if carpeta is None:
        salida["verificacion"] = "La oferta de este visto bueno no existe en la carpeta ofertas/: no se puede comprobar si lo revisado cambió."
        return salida
    ref = _txt(sello, "dictamen_ref")
    if not ref:
        salida["verificacion"] = "Este visto bueno firmado no cita ningún informe de cumplimiento (dictamen): no se puede comprobar."
        return salida
    r = ctx.oferta(carpeta)
    try:
        real_dictamen = r.real(ref)
    except ErrorHttp:
        salida["verificacion"] = "El informe de cumplimiento (dictamen) que cita el visto bueno no existe o no se puede leer."
        return salida
    dictamen = r.json(ref)
    dh, _ = _hash_seguro(real_dictamen)
    salida["dictamen_hash_actual"] = dh
    esperado_d = _txt(sello, "dictamen_sha256")
    if dh is not None and esperado_d:
        salida["dictamen_coincide"] = dh == esperado_d
    artefacto = _txt(dictamen.dato, "artefacto_ref") if dictamen.ok and isinstance(dictamen.dato, dict) else None
    if not artefacto:
        salida["verificacion"] = "El informe de cumplimiento no dice qué archivos revisó: no se puede comprobar si cambiaron."
    else:
        try:
            real = r.real(artefacto)
        except ErrorHttp:
            salida["verificacion"] = "Lo que revisó el informe de cumplimiento no existe o queda fuera de la oferta."
        else:
            hash_actual, motivo = _hash_seguro(real)
            salida["hash_actual"], salida["verificacion"] = hash_actual, motivo
            sellado = _txt(sello, "artefacto_sha256")
            if hash_actual is not None and sellado:
                salida["hash_coincide"] = hash_actual == sellado
    if salida["hash_coincide"] is False or salida["dictamen_coincide"] is False:
        salida["alterado"] = True
    elif salida["hash_coincide"] is True and salida["dictamen_coincide"] is not False:
        salida["alterado"] = False
    # La firma del sello es un HMAC con una clave que el panel NO tiene (ni debe tener): no se verifica, se muestra tal cual.
    return salida


def cumplimiento(ctx: Ctx) -> Sobre:
    """``{dictamenes, sellos}``: dictámenes de X1 (``ofertas/*/qa/x1-*.json``) y sellos de ``empresa/compliance/sellos/``.

    ``oferta_id`` es SIEMPRE la carpeta de la oferta (``OF-…``/``_ejemplo``) en ambas listas; el id que trae el archivo va en
    ``oferta_id_interno``. Cada sello lleva ``firma``, ``object_ids``, ``dictamen_sha256`` tal cual están en el archivo y, si es
    barato y seguro, ``hash_actual`` (recalculado del artefacto del dictamen citado), ``hash_coincide`` y ``alterado``.
    """
    avisos: list[str] = []
    mapa = carpetas_por_id_interno(ctx)
    interno_de: dict[str, str] = {}
    for interno_id, carpeta_id in mapa.items():
        if interno_id != carpeta_id:
            interno_de.setdefault(carpeta_id, interno_id)
    dictamenes: list[dict[str, Any]] = []
    for carpeta in ids_de_ofertas(ctx):
        r = ctx.oferta(carpeta)
        for nombre in r.listar("qa", solo="archivo"):
            if not (nombre.startswith("x1-") and nombre.endswith(".json")):
                continue
            lec = r.json(f"qa/{nombre}")
            if lec.ok and isinstance(lec.dato, dict):
                dictamenes.append(_resumen_dictamen(carpeta, nombre, lec.dato, interno_de.get(carpeta)))
            else:
                dictamenes.append(_resumen_dictamen(carpeta, nombre, {}, interno_de.get(carpeta)))
                if lec.aviso:
                    avisos.append(lec.aviso)
    emp = ctx.empresa()
    sellos: list[dict[str, Any]] = []
    ahora = ctx.iso_ahora()
    for nombre in emp.listar("compliance/sellos", solo="archivo"):
        if not nombre.endswith(".json"):
            continue
        lec = emp.json(f"compliance/sellos/{nombre}")
        if not (lec.ok and isinstance(lec.dato, dict)):
            sellos.append({"archivo": nombre, "legible": False})
            if lec.aviso:
                avisos.append(lec.aviso)
            continue
        d = lec.dato
        vig = _txt(d, "vigencia_hasta")
        interno = _txt(d, "oferta_id")
        carpeta = mapa.get(interno) if interno else None
        ids = d.get("object_ids")
        sello = {
            "archivo": nombre, "legible": True,
            "oferta_id": carpeta or interno, "oferta_id_interno": interno, "oferta_resuelta": carpeta is not None,
            "etapa_objetivo": _txt(d, "etapa_objetivo"), "emitido_en": _txt(d, "emitido_en"),
            "vigencia_hasta": vig, "vigente": (vig >= ahora) if vig else None,
            "dictamen_ref": _txt(d, "dictamen_ref"), "dictamen_sha256": _txt(d, "dictamen_sha256"),
            "artefacto_sha256": _txt(d, "artefacto_sha256"), "reglas_version": _txt(d, "reglas_version"),
            "object_ids": [x for x in ids if isinstance(x, str)] if isinstance(ids, list) else None,
            "firma": _txt(d, "firma"),
        }
        sello.update(_verificacion_de_sello(ctx, carpeta, sello))
        sellos.append(sello)
    vacio = not dictamenes and not sellos
    if vacio:
        avisos.append("Todavía no hay informes de cumplimiento (dictámenes) ni vistos buenos firmados (sellos). "
                      "Los produce el revisor de cumplimiento (X1) cuando firma una aprobación con `compliance.sellar` "
                      "(archivos ofertas/*/qa/x1-*.json y empresa/compliance/sellos/).")
    return Sobre({"dictamenes": dictamenes, "sellos": sellos},
                 ["ofertas/*/qa/x1-*.json", "empresa/compliance/sellos/*.json"], vacio=vacio, avisos=avisos)


# ----------------------------------------------------------------------------------------------
# Parámetros y límites
# ----------------------------------------------------------------------------------------------
# Claves de riesgo de ``limites`` 1.3.0 (decisión 13 / nota 25 §10.1) que pueden ser ``null``: con ``null`` el motor opera SOLO EN VERDE;
# no son un dato faltante ni las exige ninguna operación crítica (S-A, CT-3 lote A). El panel no las cuenta como «límites que bloquean».
CLAVES_NULO_SOLO_VERDE = frozenset({
    "nivel_max_lanzable", "cuota_gasto_amarillo_max_pct", "cuota_gasto_amarillo_b_max_pct", "envios_amarillo_a_semana",
    "envios_amarillo_b_mes", "dias_limpios_para_subir_cuota", "edad_minima_audiencia", "reserva_dias_stripe",
})


def _nulos(valor: Any, prefijo: str = "", _nivel: int = 0) -> tuple[list[str], list[str]]:
    """``(claves con null, claves con lista vacía)`` de un mapa anidado, con rutas ``a.b.c``."""
    nulos: list[str] = []
    vacias: list[str] = []
    if _nivel > 8 or not isinstance(valor, dict):
        return nulos, vacias
    for k, v in valor.items():
        clave = f"{prefijo}.{k}" if prefijo else str(k)
        if v is None:
            nulos.append(clave)
        elif isinstance(v, list) and not v:
            vacias.append(clave)
        elif isinstance(v, dict):
            n, e = _nulos(v, clave, _nivel + 1)
            nulos += n
            vacias += e
    return nulos, vacias


def _claves_propuesta(doc: Any) -> list[str]:
    if not isinstance(doc, dict):
        return []
    grupos = doc.get("grupos")
    if isinstance(grupos, dict):
        claves = [f"{g}.{k}" for g, v in grupos.items() if isinstance(v, dict) for k in v]
    else:
        claves = [str(k) for k in doc]
    return claves[:_MAX_CLAVES]


def parametros(ctx: Ctx) -> Sobre:
    """``{limites:{valores, nulos, nulos_solo_verde}, parametros, autonomia, propuestas}``; limites con ``null`` = pendiente del dueño,
    salvo ``nulos_solo_verde`` (claves de riesgo 1.3.0: ``null`` = solo verde, no bloquea nada)."""
    emp = ctx.empresa()
    avisos: list[str] = []
    fuente = ["empresa/limites.yaml", "empresa/parametros.yaml", "empresa/autonomia.yaml", "empresa/propuestas/*",
              "scripts/modelado/*.propuesta.yaml", "scripts/modelado/barrido/*.propuesta.yaml"]
    lim = emp.yaml("limites.yaml")
    par = emp.yaml("parametros.yaml")
    aut = emp.yaml("autonomia.yaml")
    for lec in (lim, par, aut):
        if lec.estado not in ("ok", "ausente") and lec.aviso:
            avisos.append(lec.aviso)
    nulos, listas_vacias = _nulos(lim.dato) if lim.ok else ([], [])
    nulos_solo_verde = [c for c in nulos if c.split(".")[0] in CLAVES_NULO_SOLO_VERDE]
    parametros_d: Any = par.dato if par.ok else None
    if par.ok and isinstance(par.dato, dict) and isinstance(par.dato.get("grupos"), dict):
        sin_valor: list[str] = []
        for g, claves in par.dato["grupos"].items():
            if isinstance(claves, dict):
                sin_valor += [f"{g}.{k}" for k, v in claves.items() if isinstance(v, dict) and "valor" in v and v["valor"] is None]
        parametros_d = {**par.dato, "sin_valor": sin_valor[:_MAX_CLAVES]}
    propuestas: list[dict[str, Any]] = []
    for nombre in emp.listar("propuestas", solo="archivo"):
        if not nombre.endswith((".yaml", ".yml", ".json")):
            continue
        lec = emp.json(f"propuestas/{nombre}") if nombre.endswith(".json") else emp.yaml(f"propuestas/{nombre}")
        propuestas.append({"archivo": f"empresa/propuestas/{nombre}", "origen": "empresa/propuestas",
                           "claves": _claves_propuesta(lec.dato) if lec.ok else []})
        if not lec.ok and lec.aviso:
            avisos.append(lec.aviso)
    # Propuestas de D1 Modo D (solo lectura): scripts/modelado/*.propuesta.yaml y scripts/modelado/barrido/*.propuesta.yaml.
    modelado = Raiz(ctx.raiz / "scripts" / "modelado", limite=ctx.raiz)
    for sub in ("", "barrido"):
        for nombre in modelado.listar(sub, solo="archivo"):
            if not nombre.endswith(".propuesta.yaml"):
                continue
            rel = f"{sub}/{nombre}" if sub else nombre
            lec = modelado.yaml(rel)
            propuestas.append({"archivo": f"scripts/modelado/{rel}", "origen": "scripts/modelado",
                               "claves": _claves_propuesta(lec.dato) if lec.ok else []})
            if not lec.ok and lec.aviso:
                avisos.append(lec.aviso)
    vacio = not (lim.ok or par.ok or aut.ok or propuestas)
    if vacio:
        avisos.append("Todavía no están cargados los límites de seguridad, los parámetros ni los niveles de autonomía (faltan los archivos empresa/limites.yaml, parametros.yaml y autonomia.yaml).")
    datos = {"limites": {"valores": lim.dato if lim.ok else None, "nulos": nulos, "nulos_solo_verde": nulos_solo_verde,
                           "listas_vacias": listas_vacias},
             "parametros": parametros_d, "autonomia": aut.dato if aut.ok else None, "propuestas": propuestas}
    return Sobre(datos, fuente, vacio=vacio, avisos=avisos)


# ----------------------------------------------------------------------------------------------
# Gates (#/quien-decide): contratos/gates.json, solo lectura
# ----------------------------------------------------------------------------------------------
_RX_CLAVE_GATE = re.compile(r"^(etapa|accion):[A-Za-z0-9_]{1,64}$")
_NIVELES_GATE = ("N0", "N1", "N2", "N3", "N4")
_GATES_VALIDOS = frozenset({"A", "S", "H", "NA"})
_TOPE_GATES = 256 * 1024
_MAX_ENTRADAS_GATES = 200
_MAX_DESCRIPCION_GATE = 600


def _acciones_minimas_h() -> list[str] | None:
    """Las acciones que SIEMPRE exigen gate H aunque ``limites.yaml`` no las traiga (``scripts.validar_esquemas``); ``None`` si no se puede importar."""
    try:
        from scripts.validar_esquemas import ACCIONES_GATE_MINIMAS
    except Exception:  # noqa: BLE001 - sin el validador del proyecto no se afirma nada
        return None
    return sorted(str(a) for a in ACCIONES_GATE_MINIMAS)


def gates(ctx: Ctx) -> Sobre:
    """``{gates:{schema_version, niveles, entradas:{"etapa:D1"|"accion:x": {descripcion, gate:{N0…N4: A|S|H|NA}}}}, acciones_minimas_h}``.

    Lee ``contratos/gates.json`` con el mismo resolvedor confinado que las demás APIs y con tope de tamaño; deja pasar SOLO lo que tiene la forma
    del contrato (claves ``etapa:``/``accion:``, niveles N0-N4, valores A|S|H|NA, descripción recortada): lo demás se omite con un aviso. Si falta o
    no se puede leer: ``vacio`` y ``gates: null``. ``acciones_minimas_h`` viene del validador del proyecto (el gate efectivo es el más estricto entre
    la tabla, ``autonomia.yaml``, ``limites.acciones_gate_humano`` y esas acciones).
    """
    fuente = ["contratos/gates.json"]
    minimas = _acciones_minimas_h()
    lec = ctx.raiz_confinada.json("contratos/gates.json", tope=_TOPE_GATES)
    if not lec.ok:
        avisos = [lec.aviso] if lec.aviso else []
        avisos.append("No se pudo leer la tabla de puntos de control: quién aprueba cada paso según el nivel de autonomía (archivo contratos/gates.json).")
        return Sobre({"gates": None, "acciones_minimas_h": minimas}, fuente, vacio=True, avisos=avisos)
    doc = lec.dato
    crudas = doc.get("entradas") if isinstance(doc, dict) else None
    if not isinstance(crudas, dict):
        return Sobre({"gates": None, "acciones_minimas_h": minimas}, fuente, vacio=True,
                     avisos=["La tabla de puntos de control está mal armada: falta la lista «entradas» con el formato esperado (contratos/gates.json)."])
    entradas: dict[str, Any] = {}
    omitidas = 0
    for clave, entrada in crudas.items():
        if len(entradas) >= _MAX_ENTRADAS_GATES or not isinstance(clave, str) or not _RX_CLAVE_GATE.fullmatch(clave) \
                or not isinstance(entrada, dict) or not isinstance(entrada.get("gate"), dict):
            omitidas += 1
            continue
        gate = {n: g for n, g in entrada["gate"].items() if n in _NIVELES_GATE and isinstance(g, str) and g in _GATES_VALIDOS}
        if not gate:
            omitidas += 1
            continue
        descripcion = entrada.get("descripcion")
        entradas[clave] = {"descripcion": descripcion[:_MAX_DESCRIPCION_GATE] if isinstance(descripcion, str) else None, "gate": gate}
    avisos = [f"Se omitieron {omitidas} entradas de la tabla de puntos de control porque no tienen el formato esperado (contratos/gates.json)."] if omitidas else []
    if not entradas:
        return Sobre({"gates": None, "acciones_minimas_h": minimas}, fuente, vacio=True,
                     avisos=avisos + ["La tabla de puntos de control no tiene ninguna entrada válida (contratos/gates.json)."])
    niveles = [n for n in doc.get("niveles", []) if isinstance(n, str) and n in _NIVELES_GATE] if isinstance(doc.get("niveles"), list) else []
    version = doc.get("schema_version")
    datos = {"gates": {"schema_version": version if isinstance(version, str) and len(version) <= 20 else None,
                       "niveles": niveles or list(_NIVELES_GATE), "entradas": entradas},
             "acciones_minimas_h": minimas}
    return Sobre(datos, fuente, vacio=False, avisos=avisos)


# ----------------------------------------------------------------------------------------------
# Skills
# ----------------------------------------------------------------------------------------------
def _frontmatter(texto: str) -> dict[str, Any]:
    m = _RX_FRONT.match(texto)
    if not m:
        return {}
    try:
        dato = cargar_yaml_seguro(m.group(1))
    except ValueError:
        return {}
    return dato if isinstance(dato, dict) else {}


def _dod(texto: str) -> list[dict[str, Any]]:
    salida: list[dict[str, Any]] = []
    dentro = False
    for linea in texto.splitlines():
        if linea.lstrip().startswith("#"):
            dentro = bool(_RX_DOD.match(linea.strip()))
            continue
        if not dentro:
            continue
        m = _RX_CASILLA.match(linea)
        if m:
            salida.append({"criterio": m.group(2)[:300], "ok": m.group(1) in "xX"})
            continue
        m = _RX_VINETA.match(linea)
        if m:
            salida.append({"criterio": m.group(1)[:300], "ok": None})
    return salida[:50]


def _version(front: dict[str, Any], changelog: str | None) -> str | None:
    v = front.get("version")
    if isinstance(v, (str, int, float)) and re.fullmatch(r"[0-9]+(\.[0-9]+){0,2}", str(v)):
        return str(v)
    if changelog:
        m = _RX_VERSION.search(changelog)
        if m:
            return m.group(1)
    return None


def skills(ctx: Ctx) -> Sobre:
    """Una fila por ``.claude/skills/<slug>/`` con su versión, archivos, agentes y criterios de listo (DoD)."""
    base = Raiz(ctx.raiz / ".claude", limite=ctx.raiz)
    avisos: list[str] = []
    slugs = [s for s in base.listar("skills", solo="dir") if _RX_SLUG.fullmatch(s)]
    agentes_todos = [n[:-3] for n in base.listar("agents", solo="archivo") if n.endswith(".md") and n.lower() != "readme.md"]
    filas: list[dict[str, Any]] = []
    for slug in slugs:
        s = base.sub("skills", slug)
        md = s.texto("SKILL.md", tope=200 * 1024)
        texto = md.dato if md.ok and isinstance(md.dato, str) else ""
        if md.estado not in ("ok", "ausente") and md.aviso:
            avisos.append(md.aviso)
        front = _frontmatter(texto)
        cl = s.texto("CHANGELOG.md", tope=100 * 1024)
        version = _version(front, cl.dato if cl.ok else None)
        estado = front.get("estado") if front.get("estado") in ("borrador", "v1") else (
            "v1" if version and int(version.split(".")[0]) >= 1 else "borrador")
        desc = front.get("description")
        archivos: dict[str, Any] = {"SKILL.md": md.ok, "rubric.md": s.existe("rubric.md"), "CHANGELOG.md": cl.ok}
        for carpeta in ("references", "templates", "scripts", "evals"):
            archivos[carpeta] = len(s.recorrer(carpeta, maximo=500)) if s.es_directorio(carpeta) else 0
        agentes = [a for a in agentes_todos
                   if a.rsplit("-", 1)[0] and (slug == a.rsplit("-", 1)[0] or slug.startswith(a.rsplit("-", 1)[0] + "-"))]
        filas.append({
            "slug": slug, "version": version, "estado": estado,
            "descripcion": desc if isinstance(desc, str) else None,
            "lineas_skill_md": len(texto.splitlines()) if md.ok else None,
            "archivos": archivos, "agentes": agentes, "dod": _dod(texto),
        })
    if not filas:
        avisos.append("Todavía no hay guías de trabajo (skills) creadas: la carpeta .claude/skills/ solo tiene su README. Se crean desde la pestaña Code.")
    return Sobre(filas, [".claude/skills/*/SKILL.md", ".claude/agents/*.md"], vacio=not filas, avisos=avisos)


def skill_archivo(ctx: Ctx, slug: str, ruta: str | None) -> Sobre:
    """``GET /api/skills/<slug>/archivo?ruta=…``: texto de un archivo de ``.claude/skills/<slug>/``.

    ``ruta`` es relativa a la carpeta de la skill (``SKILL.md``, ``references/x.md``…). Para el Maker/QA de la skill:
    ``ruta=agentes/<id>-maker.md`` o ``agentes/<id>-qa.md`` (de ``.claude/agents/``; ninguna otra cosa de esa carpeta).
    Mismo resolvedor confinado que ``/oferta/<id>/archivo``: sin ``..``, rutas absolutas, enlaces que escapen ni secretos;
    tope 400 KB; solo texto.
    """
    if not _RX_SLUG.fullmatch(slug or ""):
        raise ErrorHttp(400, "skill_invalida", "El nombre de la guía de trabajo (skill) no es válido.")
    base = Raiz(ctx.raiz / ".claude", limite=ctx.raiz)
    if ruta and ruta.startswith("agentes/"):
        nombre = ruta[len("agentes/"):]
        if not _RX_AGENTE.fullmatch(nombre):
            raise ErrorHttp(403, "ruta_prohibida", "De esa carpeta solo se pueden ver las instrucciones de la IA que prepara (<nombre>-maker.md) y de la que revisa (<nombre>-qa.md).")
        sobre = leer_archivo(base.sub("agents"), nombre, ".claude/agents", permitir_imagen=False)
        if isinstance(sobre.datos, dict):
            sobre.datos = {**sobre.datos, "ruta": f"agentes/{sobre.datos['ruta']}"}
        return sobre
    carpeta = base.sub("skills", slug)
    if not Path(carpeta.base).is_dir():
        raise ErrorHttp(404, "skill_no_encontrada", "No encontramos esa guía de trabajo (skill).")
    return leer_archivo(carpeta, ruta, f".claude/skills/{slug}", permitir_imagen=False)
