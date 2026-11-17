"""``orq``: orquestador de una oferta (docs/06 §4.2). Única CLI de efecto de este componente.

Subcomandos (todos de solo este alcance de B1a): ``crear``, ``estado``, ``siguiente``, ``ejecutar``,
``firmar``, ``ingresar``, ``nivel``, ``activar``, ``ciclo-d8``, ``veredicto``, ``cerrar``, ``pausar``,
``reanudar``. La máquina de estados y el almacén viven en :mod:`engine.estado`; la única escritura
viva sin gate (pausar un objeto) vive en :mod:`engine.ejecutor`; el cierre de fase y el post-mortem
viven en :mod:`engine.cerrar`. ``engine.limites proponer/sellar``, ``engine.d8`` (ciclo y veredicto de
D8) y ``decision/entradas.py`` son de otra sesión (B1b): se consumen por import diferido, con un
``ErrorBloqueado`` claro si todavía no existen (ver README, «Pedidos»); ``meta.activar`` (B5) se
inyecta como ``activador_meta`` (ver ``activar``).

Flujo de una etapa con IA en este alcance (sin ``agentes.runner`` todavía, docs/06 §7.2): ``ejecutar
--modo fixture --fixture DIR`` sustituye al Maker leyendo rondas GRABADAS de ``DIR`` (una por
subcarpeta ``ronda-N/``, cada una con ``salida/`` —la misma forma relativa que
``ARCHIVOS_SELLADOS``/``DIRECTORIOS_SELLADOS`` de ``scripts.validar_esquemas``— y un ``qa.json``
válido contra ``qa.schema.json``); valida, promueve atómicamente a la carpeta real de la oferta
(archivando la versión previa, nunca sobrescribiéndola) y aplica el gate (A/S aprueban solos; H
busca una orden firmada de ``firmar``). ``ingresar`` es el mismo camino sin rondas de QA (contenido
ya revisado a mano, ``origen_version=humano``): por diseño, para la MISMA entrada final, produce el
mismo ``hash_salida`` y el mismo gate que ``ejecutar --modo fixture`` (B0-23).
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import secrets
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from engine import comun, estado, guard, limites, parametros
from engine.ejecutor import Ejecutor, EjecutorMotor
from engine.errores import ErrorBloqueado, ErrorFabrica, ErrorLimite, ErrorUso, ErrorValidacion
from scripts.validar_esquemas import ARCHIVOS_SELLADOS, DEPENDENCIAS, DIRECTORIOS_SELLADOS, hash_contenido_brief, hash_salida_etapa

__all__ = [
    "activar", "cerrar", "ciclo_d8", "crear", "ejecutar", "firmar", "ingresar", "ingresar_desde_cuerpo", "main", "nivel",
    "pausar", "reanudar", "siguiente", "ver_estado", "veredicto",
]

_RX_OFERTA = re.compile(r"^OF-[0-9]{6}-[0-9]{2}$")
_RX_NONCE = re.compile(r"^[a-z0-9_-]{16,64}$")
PARAMETRO_MAX_RONDAS_QA = "orquestador.max_rondas_qa"
PARAMETRO_CUERPO_MAX_BYTES = "ingesta.cuerpo_max_bytes"  # tope del cuerpo de POST /ingresar (docs/06 §4.7); ausente => ParametroFaltante (5)
PARAMETRO_VIGENCIA_ORDEN = "campana.preflight_vigencia_h"  # mismo parámetro que usa engine.guard (README, Decisión 3)


# ----------------------------------------------------------------------------------------------
# Utilidades de archivos (staging, promoción, archivo de versiones previas)
# ----------------------------------------------------------------------------------------------
def _sin_symlinks(origen: Path) -> None:
    """``ErrorValidacion`` si ``origen`` contiene un symlink: ``ingresar``/``ejecutar`` no siguen enlaces
    que podrían salir de la carpeta (B0-23, «un archivo fuera de ruta se rechaza»)."""
    for ruta in origen.rglob("*"):
        if ruta.is_symlink():
            raise ErrorValidacion(f"entrada rechazada: {ruta.relative_to(origen)} es un symlink (no se admiten enlaces)")


def _preparar_staging(staging: Path, origen: Path) -> Path:
    """Vacía ``staging`` y copia el árbol de ``origen`` dentro (sin symlinks). Devuelve ``staging``."""
    if not origen.is_dir():
        raise ErrorValidacion(f"la fixture no existe o no es una carpeta: {origen}")
    _sin_symlinks(origen)
    if staging.is_symlink():
        raise ErrorValidacion(f"{staging.name}: la carpeta de staging es un enlace simbólico; no se escribe a través de enlaces")
    if staging.exists():
        shutil.rmtree(staging)
    staging.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(origen, staging)
    return staging


def _hash_salida_de(staging: Path, etapa: str) -> "str | None":
    """``hash_salida_etapa`` con los fallos de contenido (JSON/UTF-8 inválido, BOM) convertidos en
    ``ErrorValidacion`` (3): un artefacto ilegible es dato de entrada inválido, nunca un fallo interno (1)."""
    try:
        return hash_salida_etapa(staging, etapa)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ErrorValidacion(f"{etapa}: un archivo de la entrega no es JSON/UTF-8 válido ({type(exc).__name__})") from exc


def _rutas_selladas(etapa: str) -> list[str]:
    return list(ARCHIVOS_SELLADOS.get(etapa, [])) + list(DIRECTORIOS_SELLADOS.get(etapa, []))


def _archivar_version_previa(dir_oferta: Path, etapa: str, version_previa: str) -> None:
    """Copia el contenido APROBADO vigente a ``.versiones/<etapa>/<version_previa>/`` antes de sobrescribirlo
    (convenciones §1: «el código NO sobrescribe un artefacto versionado aprobado»)."""
    destino_base = dir_oferta / ".versiones" / etapa / version_previa
    for rel in _rutas_selladas(etapa):
        origen = dir_oferta / rel
        if not origen.exists():
            continue
        destino = destino_base / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        if origen.is_dir():
            if destino.exists():
                shutil.rmtree(destino)
            shutil.copytree(origen, destino)
        else:
            shutil.copy2(origen, destino)


def _promover(staging: Path, dir_oferta: Path, etapa: str) -> None:
    """Copia los archivos/carpetas sellados de ``staging`` a su ubicación real en ``dir_oferta``."""
    for rel in _rutas_selladas(etapa):
        origen = staging / rel
        destino = dir_oferta / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        if origen.is_dir():
            if destino.exists():
                shutil.rmtree(destino)
            shutil.copytree(origen, destino)
        else:
            destino.write_bytes(origen.read_bytes())


def _siguiente_version(version_previa: str | None) -> str:
    if version_previa is None:
        return "v1"
    return f"v{int(version_previa[1:]) + 1}"


# ----------------------------------------------------------------------------------------------
# Órdenes firmadas (empresa/ordenes/<nonce>.json): mismo formato que consume engine.guard
# ----------------------------------------------------------------------------------------------
def firmar(*, oferta_id: str, accion: str = "aprobar_etapa", etapa: str | None, hash_objetivo: str,
          clave_privada: Path, raiz: Path | None = None, ahora: Callable[[], datetime] = comun.ahora_utc,
          nonce: str | None = None) -> dict:
    """Firma una orden (Ed25519, clave PRIVADA del dueño) y la escribe en ``empresa/ordenes/<nonce>.json``.

    ``accion="aprobar_etapa"`` exige ``etapa`` (gate H de una etapa); cualquier otra acción (p. ej.
    ``activar_campana``) no la admite (``orden_firmada.schema.json``, condición ``allOf``). Un
    ``nonce`` repetido se rechaza (B0-25): un nonce es de un solo uso.
    """
    base = raiz or comun.raiz()
    if accion == "aprobar_etapa" and not etapa:
        raise ErrorUso("firmar --accion aprobar_etapa exige --etapa")
    if accion != "aprobar_etapa" and etapa:
        raise ErrorUso(f"firmar: --etapa no se usa con --accion {accion}")
    n = nonce or secrets.token_hex(16)
    if not _RX_NONCE.fullmatch(n):
        raise ErrorValidacion("nonce inválido: se esperan 16-64 caracteres [a-z0-9_-]")
    destino = base / "empresa" / "ordenes" / f"{n}.json"
    if destino.exists():
        raise ErrorValidacion(f"nonce repetido: ya existe una orden {n} (un nonce es de un solo uso)", detalle={"nonce": n})
    orden: dict[str, Any] = {
        "schema_version": "1.1.0", "accion": accion, "oferta_id": oferta_id, "hash_objetivo": hash_objetivo,
        "ts": comun.iso_z(comun.instante(ahora)), "nonce": n,
    }
    if etapa:
        orden["etapa"] = etapa
    orden["firma"] = comun.firmar_ed25519(comun.json_canonico(orden), Path(clave_privada))
    errores = comun.errores_de_esquema("orden_firmada", orden)
    if errores:
        raise ErrorValidacion(f"orden firmada inválida: {comun.resumir_errores_esquema(errores)}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    comun.escribir_atomico(destino, comun.json_canonico(orden))
    return orden


def _buscar_orden(base: Path, *, accion: str, oferta_id: str, etapa: str | None, hash_objetivo: str,
                  env: Mapping[str, str], ahora: Callable[[], datetime]) -> dict | None:
    """Busca en ``empresa/ordenes/`` una orden vigente y válida para ``(accion, oferta_id, etapa, hash_objetivo)``.

    Misma semántica de lectura que ``engine.guard._paso_aprobacion`` (no la reimplementa porque esa es
    privada y específica de los 7 pasos de ``--live``; aquí se usa también fuera de ``--live``, para
    aprobar un gate H en modo fixture/dry-run)."""
    clave_publica = env.get("FABRICA_FIRMA_PUBLICA")
    if not clave_publica:
        return None
    carpeta = base / "empresa" / "ordenes"
    if not carpeta.is_dir():
        return None
    t = comun.instante(ahora)
    try:
        vigencia_h = parametros.cargar_parametros(base / "empresa" / "parametros.yaml").valor(PARAMETRO_VIGENCIA_ORDEN)
    except ErrorFabrica:
        vigencia_h = None
    for archivo in sorted(carpeta.glob("*.json")):
        try:
            orden = comun.cargar_json(archivo)
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        if not isinstance(orden, dict) or orden.get("accion") != accion or orden.get("oferta_id") != oferta_id:
            continue
        if etapa is not None and orden.get("etapa") != etapa:
            continue
        if orden.get("hash_objetivo") != hash_objetivo:
            continue
        try:
            momento = comun.parsear_z(orden.get("ts"))
        except ErrorValidacion:
            continue
        if momento > t:
            continue
        if vigencia_h is not None and (t - momento).total_seconds() > vigencia_h * 3600:
            continue
        cuerpo = {k: v for k, v in orden.items() if k != "firma"}
        if comun.verificar_ed25519(comun.json_canonico(cuerpo), str(orden.get("firma")), clave_publica):
            return orden
    return None


# ----------------------------------------------------------------------------------------------
# crear
# ----------------------------------------------------------------------------------------------
def _mes_de(oferta_id: str) -> str:
    return oferta_id.split("-")[1]


def _siguiente_numero(base: Path, prefijo: str, mes: str) -> int:
    carpeta = base / "ofertas"
    maximo = 0
    patron = re.compile(rf"^{re.escape(prefijo)}-{mes}-([0-9]{{2}})$")
    if carpeta.is_dir():
        for d in carpeta.iterdir():
            if not d.is_dir():
                continue
            m = patron.match(d.name)
            if m:
                maximo = max(maximo, int(m.group(1)))
    return maximo + 1


def crear(*, ruta_brief: Path, raiz: Path | None = None, ahora: Callable[[], datetime] = comun.ahora_utc) -> dict:
    """``orq crear --brief RUTA``: da de alta una oferta nueva (idempotente por contenido del brief).

    ``RUTA`` trae un brief YA firmado por el dueño (``hash``, ``aprobado_por``) pero SIN
    ``oferta_id``/``familia_id``/``creado_en`` (los asigna el motor). Mismo contenido (ignorando esos
    tres campos y la firma) devuelve el mismo ``oferta_id`` sin crear nada nuevo. Errores:
    ``ErrorLimite`` (5) si la moneda del brief no coincide con ``moneda_limites`` o el país no está en
    ``paises_permitidos`` (fail-closed: sin eso no se crea nada); ``ErrorValidacion`` (3) si el brief
    resultante no cumple ``brief.schema.json``.
    """
    base = raiz or comun.raiz()
    previo = comun.cargar_yaml(Path(ruta_brief))
    if not isinstance(previo, dict):
        raise ErrorValidacion("el brief debe ser un mapa YAML")
    hash_contenido = hash_contenido_brief(previo)
    carpeta_ofertas = base / "ofertas"
    if carpeta_ofertas.is_dir():
        for d in sorted(carpeta_ofertas.iterdir()):
            ruta_existente = d / "00-brief.yaml"
            if not ruta_existente.is_file():
                continue
            existente = comun.cargar_yaml(ruta_existente)
            if isinstance(existente, dict) and hash_contenido_brief(existente) == hash_contenido:
                return {"oferta_id": existente["oferta_id"], "creado": False}
    lim = limites.cargar_limites(base / "empresa" / "limites.yaml")
    moneda_brief = str(previo.get("mercado_objetivo", {}).get("moneda_cobro", ""))
    if moneda_brief != lim.moneda:
        raise ErrorLimite(f"el brief cobra en {moneda_brief} y moneda_limites es {lim.moneda}: no se crea la oferta",
                          detalle={"faltantes": ["moneda_limites"]})
    paises_permitidos = set(lim.valor("paises_permitidos"))
    paises_brief = set(previo.get("mercado_objetivo", {}).get("paises_segmentacion", []))
    fuera = paises_brief - paises_permitidos
    if fuera:
        raise ErrorLimite(f"países fuera de paises_permitidos: {', '.join(sorted(fuera))}", detalle={"faltantes": ["paises_permitidos"]})
    t = comun.instante(ahora)
    mes = t.strftime("%Y%m")
    numero = _siguiente_numero(base, "OF", mes)
    oferta_id = f"OF-{mes}-{numero:02d}"
    familia_id = f"FAM-{mes}-{numero:02d}"
    completo = {**previo, "oferta_id": oferta_id, "familia_id": familia_id, "creado_en": comun.iso_z(t)}
    errores = comun.errores_de_esquema("brief", completo)
    if errores:
        raise ErrorValidacion(f"el brief no cumple brief.schema.json tras asignar el ID: {comun.resumir_errores_esquema(errores)}")
    comun.escribir_atomico(base / "ofertas" / oferta_id / "00-brief.yaml", _dump_yaml(completo))
    estado.crear(completo, oferta_id=oferta_id, familia_id=familia_id, nivel=str(completo.get("nivel_autonomia", "N0")), raiz=raiz, ahora=ahora)
    return {"oferta_id": oferta_id, "creado": True}


def _dump_yaml(datos: Mapping[str, Any]) -> bytes:
    import yaml
    return yaml.safe_dump(dict(datos), sort_keys=False, allow_unicode=True).encode("utf-8")


# ----------------------------------------------------------------------------------------------
# estado / siguiente
# ----------------------------------------------------------------------------------------------
def ver_estado(oferta_id: str, *, raiz: Path | None = None) -> dict:
    """``orq estado --oferta OF``: etapa y gate pendientes (solo lectura)."""
    est = estado.cargar(oferta_id, raiz=raiz)
    pendientes = [e for e, c in est["etapas"].items() if c["estado"] == "en_QA" and c["gate_pendiente"]]
    return {"oferta_id": oferta_id, "fase": est["fase"], "pausa": estado.hay_pausa(raiz=raiz),
            "etapas": {e: c["estado"] for e, c in est["etapas"].items()}, "gates_pendientes": pendientes}


def siguiente(oferta_id: str, *, raiz: Path | None = None) -> dict:
    """``orq siguiente --oferta OF``: próxima etapa ejecutable (``None`` si no hay ninguna)."""
    return {"oferta_id": oferta_id, "siguiente": estado.siguiente_etapa(oferta_id, raiz=raiz)}


# ----------------------------------------------------------------------------------------------
# ejecutar / ingresar (comparten la promoción y el gate; B0-23)
# ----------------------------------------------------------------------------------------------
def _listar_rondas(fixture_dir: Path) -> list[Path]:
    sub = sorted((p for p in fixture_dir.iterdir() if p.is_dir() and p.name.startswith("ronda-")), key=lambda p: p.name)
    return sub or [fixture_dir]


def _salida_de_ronda(ronda_dir: Path) -> Path:
    candidata = ronda_dir / "salida"
    return candidata if candidata.is_dir() else ronda_dir


def _qa_de_ronda(ronda_dir: Path) -> dict | None:
    ruta = ronda_dir / "qa.json"
    return comun.cargar_json(ruta) if ruta.is_file() else None


def _aplicar_gate(oferta_id: str, etapa: str, *, hash_salida: str, version_nueva: str, raiz: Path | None,
                  ahora: Callable[[], datetime], origen_version: str, env: Mapping[str, str]) -> tuple[str, dict | None]:
    """Decide y, si corresponde, aplica la aprobación de ``etapa``. Devuelve ``(resultado, estado_guardado)``."""
    gate = estado.gate_de(oferta_id, f"etapa:{etapa}", raiz=raiz)
    if gate == "NA":
        raise ErrorBloqueado(f"{etapa}: gate NA en el nivel vigente: esta etapa no se puede ejecutar")
    if gate in ("A", "S"):
        aprobado_por = {
            "tipo": "humano" if origen_version == "humano" else "qa_pass",
            "id": "ingresar" if origen_version == "humano" else f"{etapa.lower()}-qa",
            "fecha": comun.iso_z(comun.instante(ahora)), "firma": None,
        }
        return "aprobado", estado.aprobar(oferta_id, etapa, version=version_nueva, aprobado_por=aprobado_por, raiz=raiz, ahora=ahora)
    base = raiz or comun.raiz()
    orden = _buscar_orden(base, accion="aprobar_etapa", oferta_id=oferta_id, etapa=etapa, hash_objetivo=hash_salida, env=env, ahora=ahora)
    if orden is None:
        return "pendiente_firma", None
    aprobado_por = {"tipo": "humano", "id": "dueno", "fecha": comun.iso_z(comun.instante(ahora)), "firma": orden["firma"]}
    return "aprobado", estado.aprobar(oferta_id, etapa, version=version_nueva, aprobado_por=aprobado_por, raiz=raiz, ahora=ahora)


def _a_en_progreso(oferta_id: str, etapa: str, *, actor: str, causa: str, raiz: Path | None,
                   ahora: Callable[[], datetime]) -> None:
    """Lleva ``etapa`` a ``en_progreso`` desde cualquier estado previo, incl. ``aprobado`` (reabrir una
    etapa YA aprobada con contenido nuevo pasa primero por ``pendiente``: ``TRANSICIONES`` no admite
    ``aprobado -> en_progreso`` directo, docs/06 §5)."""
    actual = estado.cargar(oferta_id, raiz=raiz)["etapas"][etapa]["estado"]
    if actual == "aprobado":
        estado.transicionar(oferta_id, etapa, "pendiente", actor=actor, causa=f"{causa} (reabre una etapa aprobada)", raiz=raiz, ahora=ahora)
        actual = "pendiente"
    if actual != "en_progreso":
        estado.transicionar(oferta_id, etapa, "en_progreso", actor=actor, causa=causa, raiz=raiz, ahora=ahora)


def _preflight_etapa(oferta_id: str, etapa: str, *, raiz: Path | None) -> dict:
    if estado.hay_pausa(raiz=raiz):
        raise ErrorBloqueado("existe PAUSA: no se ejecutan etapas")
    est = estado.cargar(oferta_id, raiz=raiz)
    if etapa not in est["etapas"]:
        raise ErrorUso(f"etapa desconocida: {etapa}")
    for d in DEPENDENCIAS.get(etapa, []):
        dc = est["etapas"][d]
        if dc["estado"] != "aprobado" or dc["obsoleta"]:
            raise ErrorBloqueado(f"{etapa}: la dependencia {d} no está aprobada (o quedó obsoleta); ejecute {d} primero")
    return est


def ejecutar(oferta_id: str, etapa: str, *, fixture_dir: Path, raiz: Path | None = None,
            ahora: Callable[[], datetime] = comun.ahora_utc, ejecutor_obj: Ejecutor | None = None,
            env: Mapping[str, str] | None = None, max_rondas: int | None = None) -> dict:
    """``orq ejecutar --oferta OF --etapa Dn --modo fixture --fixture DIR``.

    Lee rondas grabadas (ver módulo), promueve y aprueba según el gate. Si ya estaba aprobada con el
    MISMO ``hash_salida`` (misma fixture, mismas entradas), no hace nada y devuelve ``reutilizado``
    (B0-06). Si ya estaba aprobada con OTRO hash, propaga obsolescencia a las etapas que dependen de
    ésta y pausa la campaña si estaba ``en_test`` (B0-07, vía :func:`engine.estado.propagar_obsolescencia`).
    """
    base = raiz or comun.raiz()
    variables = dict(os.environ) if env is None else dict(env)
    par = parametros.cargar_parametros(base / "empresa" / "parametros.yaml")
    tope_rondas = max_rondas if max_rondas is not None else par.valor(PARAMETRO_MAX_RONDAS_QA)
    est = _preflight_etapa(oferta_id, etapa, raiz=raiz)
    entradas = {d: est["etapas"][d]["hash_salida"] for d in DEPENDENCIAS.get(etapa, [])}
    dir_oferta = base / "ofertas" / oferta_id
    staging = dir_oferta / ".staging" / etapa

    rondas = _listar_rondas(Path(fixture_dir))
    _preparar_staging(staging, _salida_de_ronda(rondas[-1]))
    hash_final_posible = _hash_salida_de(staging, etapa)
    if hash_final_posible is None:
        raise ErrorValidacion(f"{etapa}: la fixture no produce los archivos esperados ({_rutas_selladas(etapa)})")

    campo = est["etapas"][etapa]
    if campo["estado"] == "aprobado" and not campo["obsoleta"] and campo["hash_salida"] == hash_final_posible and campo["entradas"] == entradas:
        return {"oferta_id": oferta_id, "etapa": etapa, "resultado": "reutilizado", "hash_salida": hash_final_posible,
                "version": campo["version_aprobada"]}

    version_previa = campo["version_aprobada"]
    intentos = campo["intentos"]
    veredicto_final: str | None = None
    ronda_qa = 0
    hash_salida = hash_final_posible
    for indice, ronda_dir in enumerate(rondas, start=1):
        if indice > tope_rondas:
            break
        ronda_qa = indice
        intentos += 1
        _preparar_staging(staging, _salida_de_ronda(ronda_dir))
        hash_salida = _hash_salida_de(staging, etapa)
        if hash_salida is None:
            raise ErrorValidacion(f"{etapa}: la ronda {indice} no produce los archivos esperados")
        _a_en_progreso(oferta_id, etapa, actor="orq", causa=f"ronda {indice} en curso", raiz=raiz, ahora=ahora)
        estado.transicionar(oferta_id, etapa, "en_QA", actor="orq", causa=f"ronda {indice} lista para QA", raiz=raiz, ahora=ahora,
                            cambios={"hash_salida": hash_salida, "entradas": entradas, "ronda_qa": ronda_qa, "intentos": intentos})
        qa = _qa_de_ronda(ronda_dir)
        if qa is None:
            raise ErrorValidacion(f"{etapa}: la ronda {indice} no trae qa.json (obligatorio en modo fixture)")
        if comun.errores_de_esquema("qa", qa):
            raise ErrorValidacion(f"{etapa}: qa.json de la ronda {indice} no cumple qa.schema.json")
        veredicto_final = qa["veredicto"]
        if veredicto_final in ("PASS", "PASS_CON_NOTAS"):
            break
        if indice < len(rondas) and indice < tope_rondas:
            estado.transicionar(oferta_id, etapa, "en_progreso", actor="orq", causa=f"QA {veredicto_final} en ronda {indice}: nueva ronda",
                                raiz=raiz, ahora=ahora)
            continue
        break

    if veredicto_final in ("PASS", "PASS_CON_NOTAS"):
        version_nueva = _siguiente_version(version_previa)
        if version_previa is not None:
            _archivar_version_previa(dir_oferta, etapa, version_previa)
        _promover(staging, dir_oferta, etapa)
        resultado, _ = _aplicar_gate(oferta_id, etapa, hash_salida=hash_salida, version_nueva=version_nueva, raiz=raiz,
                                     ahora=ahora, origen_version="maker", env=variables)
        if resultado == "aprobado" and version_previa is not None:
            estado.propagar_obsolescencia(oferta_id, etapa, raiz=raiz, ejecutor=ejecutor_obj or EjecutorMotor(raiz=raiz, ahora=ahora), ahora=ahora)
        return {"oferta_id": oferta_id, "etapa": etapa, "resultado": resultado, "hash_salida": hash_salida,
                "version": version_nueva if resultado == "aprobado" else None, "rondas": ronda_qa}

    estado.transicionar(oferta_id, etapa, "escalado", actor="orq", causa=f"QA {veredicto_final} tras {ronda_qa} rondas", raiz=raiz, ahora=ahora)
    return {"oferta_id": oferta_id, "etapa": etapa, "resultado": "escalado", "hash_salida": hash_salida, "version": None, "rondas": ronda_qa}


def ingresar(oferta_id: str, etapa: str, *, desde: Path, raiz: Path | None = None,
            ahora: Callable[[], datetime] = comun.ahora_utc, env: Mapping[str, str] | None = None,
            ejecutor_obj: Ejecutor | None = None) -> dict:
    """``orq ingresar --oferta OF --etapa Dn --desde DIR``: para lo hecho a mano (sin rondas de QA).

    Misma validación y promoción que :func:`ejecutar`, con ``origen_version=humano``: ante la MISMA
    entrada final, produce el mismo ``hash_salida`` y el mismo gate que ``ejecutar --modo fixture``
    (B0-23). Un archivo fuera de ruta (symlink) se rechaza con ``ErrorValidacion`` (3).
    """
    base = raiz or comun.raiz()
    variables = dict(os.environ) if env is None else dict(env)
    est = _preflight_etapa(oferta_id, etapa, raiz=raiz)
    entradas = {d: est["etapas"][d]["hash_salida"] for d in DEPENDENCIAS.get(etapa, [])}
    dir_oferta = base / "ofertas" / oferta_id
    staging = dir_oferta / ".staging" / etapa
    _preparar_staging(staging, Path(desde))
    hash_salida = _hash_salida_de(staging, etapa)
    if hash_salida is None:
        raise ErrorValidacion(f"{etapa}: --desde no trae los archivos esperados ({_rutas_selladas(etapa)})")

    campo = est["etapas"][etapa]
    if campo["estado"] == "aprobado" and not campo["obsoleta"] and campo["hash_salida"] == hash_salida and campo["entradas"] == entradas:
        return {"oferta_id": oferta_id, "etapa": etapa, "resultado": "reutilizado", "hash_salida": hash_salida,
                "version": campo["version_aprobada"]}

    version_previa = campo["version_aprobada"]
    _a_en_progreso(oferta_id, etapa, actor="orq", causa="ingreso humano", raiz=raiz, ahora=ahora)
    estado.transicionar(oferta_id, etapa, "en_QA", actor="orq", causa="contenido ingresado a mano", raiz=raiz, ahora=ahora,
                        cambios={"hash_salida": hash_salida, "entradas": entradas, "ronda_qa": max(campo["ronda_qa"], 1),
                                 "intentos": campo["intentos"] + 1})
    version_nueva = _siguiente_version(version_previa)
    if version_previa is not None:
        _archivar_version_previa(dir_oferta, etapa, version_previa)
    _promover(staging, dir_oferta, etapa)
    resultado, _ = _aplicar_gate(oferta_id, etapa, hash_salida=hash_salida, version_nueva=version_nueva, raiz=raiz,
                                 ahora=ahora, origen_version="humano", env=variables)
    if resultado == "aprobado" and version_previa is not None:
        estado.propagar_obsolescencia(oferta_id, etapa, raiz=raiz, ejecutor=ejecutor_obj or EjecutorMotor(raiz=raiz, ahora=ahora), ahora=ahora)
    return {"oferta_id": oferta_id, "etapa": etapa, "resultado": resultado, "hash_salida": hash_salida,
            "version": version_nueva if resultado == "aprobado" else None}


def _rutas_de_cuerpo(archivos: Any, etapa: str) -> list[tuple[str, bytes]]:
    """Valida ``archivos`` de un cuerpo de ``POST /ingresar`` y devuelve ``(ruta, bytes)``; falla CERRADO.

    Cada ruta es relativa a la carpeta de la oferta, sin ``..``, sin barra inicial, sin barra invertida,
    sin segmentos vacíos ni ``.``, única, y cae dentro de lo SELLADO de la etapa (``ARCHIVOS_SELLADOS`` /
    ``DIRECTORIOS_SELLADOS``): nada fuera de eso se acepta, ni siquiera como archivo auxiliar.
    """
    import base64
    import binascii

    if not isinstance(archivos, list) or not archivos:
        raise ErrorValidacion("«archivos» debe ser una lista no vacía de {ruta, contenido_b64}")
    sellado = _rutas_selladas(etapa)
    vistos: set[str] = set()
    resultado: list[tuple[str, bytes]] = []
    for i, item in enumerate(archivos):
        if not isinstance(item, dict) or set(item) != {"ruta", "contenido_b64"}:
            raise ErrorValidacion(f"archivos[{i}] debe tener exactamente «ruta» y «contenido_b64»")
        ruta, b64 = item["ruta"], item["contenido_b64"]
        if not isinstance(ruta, str) or not ruta or not isinstance(b64, str):
            raise ErrorValidacion(f"archivos[{i}]: ruta o contenido inválidos")
        segmentos = ruta.split("/")
        if ("\\" in ruta or "\x00" in ruta or ruta.startswith("/") or any(seg in ("", ".", "..") for seg in segmentos)
                or len(ruta) > 255):
            raise ErrorValidacion(f"archivos[{i}]: ruta fuera de ruta o malformada")
        if not any(ruta == base or ruta.startswith(base.rstrip("/") + "/") for base in sellado):
            raise ErrorValidacion(f"archivos[{i}]: {ruta!r} no es un archivo sellado de {etapa} ({', '.join(sellado)})")
        if ruta in vistos:
            raise ErrorValidacion(f"archivos[{i}]: ruta repetida {ruta!r}")
        vistos.add(ruta)
        try:
            contenido = base64.b64decode(b64.encode("ascii"), validate=True)
        except (binascii.Error, UnicodeEncodeError) as exc:
            raise ErrorValidacion(f"archivos[{i}]: contenido_b64 no es base64 válido") from exc
        resultado.append((ruta, contenido))
    return resultado


def ingresar_desde_cuerpo(cuerpo: "bytes | str", *, raiz: Path | None = None,
                          ahora: Callable[[], datetime] = comun.ahora_utc, env: Mapping[str, str] | None = None,
                          ejecutor_obj: Ejecutor | None = None) -> dict:
    """``POST /ingresar`` (docs/06 §4.7): ``orq ingresar`` con el contenido en el CUERPO de la petición.

    Cuerpo JSON ``{"oferta_id": "OF-AAAAMM-NN", "etapa": "Dn", "archivos": [{"ruta": "<relativa a la carpeta
    de la oferta>", "contenido_b64": "<base64 estricto>"}, …]}``. Escribe los archivos en una carpeta temporal
    dentro de ``.staging/`` y delega en :func:`ingresar` (validación, promoción y gate IDÉNTICOS al flujo con
    IA y al CLI: mismo ``hash_salida``). Falla CERRADO: JSON inválido o con claves de más, oferta/etapa
    desconocidas, rutas fuera de lo sellado de la etapa, base64 inválido, cuerpo mayor que
    ``ingesta.cuerpo_max_bytes`` (parámetro; ausente ⇒ ``ParametroFaltante``, 5; nunca un literal).
    No autentica: la firma de la petición es de la capa HTTP (``dashboard/api.py``).
    """
    base = raiz or comun.raiz()
    datos_param = parametros.cargar_parametros(parametros.ruta_por_defecto(base))
    tope = datos_param.valor(PARAMETRO_CUERPO_MAX_BYTES)
    if not isinstance(tope, int) or isinstance(tope, bool) or tope <= 0:
        raise ErrorValidacion(f"{PARAMETRO_CUERPO_MAX_BYTES} debe ser un entero positivo")
    crudo = cuerpo.encode("utf-8") if isinstance(cuerpo, str) else bytes(cuerpo)
    if len(crudo) > tope:
        raise ErrorValidacion(f"cuerpo de {len(crudo)} bytes sobre el máximo {tope} ({PARAMETRO_CUERPO_MAX_BYTES})")
    try:
        obj = json.loads(crudo.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ErrorValidacion("el cuerpo no es JSON UTF-8 válido") from exc
    if not isinstance(obj, dict) or set(obj) != {"oferta_id", "etapa", "archivos"}:
        raise ErrorValidacion("el cuerpo debe ser un objeto con exactamente oferta_id, etapa y archivos")
    oferta_id, etapa = obj["oferta_id"], obj["etapa"]
    if not isinstance(oferta_id, str) or not _RX_OFERTA.match(oferta_id):
        raise ErrorValidacion("oferta_id inválido (OF-AAAAMM-NN)")
    if not isinstance(etapa, str) or etapa not in DEPENDENCIAS:
        raise ErrorValidacion(f"etapa desconocida: {etapa!r}")
    archivos = _rutas_de_cuerpo(obj["archivos"], etapa)
    _preflight_etapa(oferta_id, etapa, raiz=raiz)  # oferta y etapa existen antes de escribir nada
    temporal = base / "ofertas" / oferta_id / ".staging" / f"_ingreso-{secrets.token_hex(8)}"
    try:
        for ruta, contenido in archivos:
            destino = temporal / ruta
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(contenido)
        return ingresar(oferta_id, etapa, desde=temporal, raiz=raiz, ahora=ahora, env=env, ejecutor_obj=ejecutor_obj)
    finally:
        shutil.rmtree(temporal, ignore_errors=True)


# ----------------------------------------------------------------------------------------------
# nivel
# ----------------------------------------------------------------------------------------------
def nivel(oferta_id: str, etapa: str, *, a: str, evidencia: Path, aprobado_por: str,
         raiz: Path | None = None, ahora: Callable[[], datetime] = comun.ahora_utc) -> dict:
    """``orq nivel --etapa Dn --a N1|N2 --evidencia RUTA --como dueno``: asciende el nivel de una etapa.

    Solo asciende (el descenso es automático, fuera de este alcance: lo haría ``autonomia.yaml``, de
    otra sesión); exige que ``evidencia`` exista y sea legible (``ErrorUso`` si no). Sube como MUCHO un
    nivel por llamada (fail-closed: saltar niveles sin evidencia intermedia no es más seguro).
    """
    from scripts.validar_esquemas import NIVELES
    if not Path(evidencia).is_file():
        raise ErrorUso(f"--evidencia no existe: {evidencia}")
    est = estado.cargar(oferta_id, raiz=raiz)
    if etapa not in est["etapas"]:
        raise ErrorUso(f"etapa desconocida: {etapa}")
    actual = est["etapas"][etapa]["nivel"]
    if a not in NIVELES:
        raise ErrorUso(f"nivel inválido: {a}")
    if NIVELES.index(a) <= NIVELES.index(actual):
        raise ErrorValidacion(f"{etapa}: {a} no es un ascenso sobre el nivel actual {actual}")
    if NIVELES.index(a) - NIVELES.index(actual) > 1:
        raise ErrorValidacion(f"{etapa}: un ascenso sube como mucho un nivel por llamada ({actual} -> {NIVELES[NIVELES.index(actual)+1]})")
    nuevo = copy.deepcopy(est)
    nuevo["etapas"][etapa]["nivel"] = a
    nuevo["revision"] = est["revision"] + 1
    nuevo["actualizado_en"] = comun.iso_z(comun.instante(ahora))
    guardado = estado.guardar(oferta_id, nuevo, revision_esperada=est["revision"], raiz=raiz)
    return {"oferta_id": oferta_id, "etapa": etapa, "nivel": a, "aprobado_por": aprobado_por}


# ----------------------------------------------------------------------------------------------
# activar (gate + guard; el POST real a Meta es de B5, inyectable)
# ----------------------------------------------------------------------------------------------
def activar(oferta_id: str, *, object_ids: Sequence[str], hash_config: str, modo: str = "fixture",
           raiz: Path | None = None, ahora: Callable[[], datetime] = comun.ahora_utc,
           activador_meta: "Callable[[str, Sequence[str], str], dict] | None" = None,
           env: Mapping[str, str] | None = None, transporte: Any = None, cuenta: Any = None,
           monto_minor: int | None = None, moneda: str | None = None) -> dict:
    """``orq activar --oferta OF --object-ids … --hash-config … [--live]``: ``guard`` + activación.

    Los 7 pasos de ``--live`` (incl. la orden firmada ``activar_campana``) corren SIEMPRE, también en
    modo ``fixture`` (``comprobar_live(simulacion=True)``): es la única forma de que B0-13 ejerza el
    camino real. Tras pasarlos, el POST idempotente a Meta (relectura, activar anuncios → conjunto →
    campaña) es de ``meta.activar`` (B5): se inyecta como ``activador_meta``; sin él, esta función deja
    la fase en ``en_test`` igualmente (modo fixture: no hay nada más que simular aquí) pero lo deja
    anotado en el resultado como pendiente de integrar.
    """
    base = raiz or comun.raiz()
    variables = dict(os.environ) if env is None else dict(env)
    simulacion = modo == "fixture"
    ctx = guard.comprobar_live(
        "activar", oferta_id=oferta_id, monto_minor=monto_minor, moneda=moneda, sello=hash_config, ahora=ahora,
        simulacion=simulacion, transporte=transporte, env=variables, raiz=base, cuenta=cuenta,
    )
    resultado_meta = None
    if activador_meta is not None:
        resultado_meta = activador_meta(oferta_id, list(object_ids), hash_config)
    estado.transicionar_fase(oferta_id, "en_test", actor="orq", causa="activar_campana", raiz=raiz, ahora=ahora)
    return {"oferta_id": oferta_id, "modo": ctx.modo, "object_ids": list(object_ids), "hash_config": hash_config,
            "meta": resultado_meta, "pendiente": resultado_meta is None}


# ----------------------------------------------------------------------------------------------
# ciclo-d8 / veredicto (engine.d8 es de B1b: import diferido, honesto si todavía no existe)
# ----------------------------------------------------------------------------------------------
def _importar_d8():
    try:
        from engine import d8  # noqa: PLC0415 - import diferido a propósito (ver docstring del módulo)
    except ImportError as exc:
        raise ErrorBloqueado("engine.d8 todavía no existe en este árbol (lo construye B1b, ola 1); "
                             "ciclo-d8/veredicto no pueden correr hasta entonces (ver README, Pedidos)") from exc
    return d8


def ciclo_d8(oferta_id: str, *, raiz: Path | None = None, ahora: Callable[[], datetime] = comun.ahora_utc,
            ejecutor_obj: Ejecutor | None = None, modo: str = "dry_run") -> list[dict]:
    """``orq ciclo-d8 --oferta OF [--live]``: una lectura diaria de D8 (envoltorio de ``engine.d8.ciclo``)."""
    d8 = _importar_d8()
    conn = estado.abrir_base(raiz)  # control del motor + hechos de datos + vistas v_d8_* (una sola fuente)
    try:
        par = parametros.cargar_parametros((raiz or comun.raiz()) / "empresa" / "parametros.yaml")
        lim = limites.cargar_limites((raiz or comun.raiz()) / "empresa" / "limites.yaml")
        return d8.ciclo(oferta_id, conn=conn, ahora=ahora, par=par, lim=lim, ejecutor=ejecutor_obj or EjecutorMotor(raiz=raiz, ahora=ahora), modo=modo)
    finally:
        conn.close()


def veredicto(oferta_id: str, *, raiz: Path | None = None, ahora: Callable[[], datetime] = comun.ahora_utc) -> dict:
    """``orq veredicto --oferta OF [--live]``: calcula (si corresponde) ``veredicto_oferta.json`` (``engine.d8.veredicto``)."""
    d8 = _importar_d8()
    conn = estado.abrir_base(raiz)  # control del motor + hechos de datos + vistas v_d8_* (una sola fuente)
    try:
        par = parametros.cargar_parametros((raiz or comun.raiz()) / "empresa" / "parametros.yaml")
        lim = limites.cargar_limites((raiz or comun.raiz()) / "empresa" / "limites.yaml")
        return d8.veredicto(oferta_id, conn=conn, ahora=ahora, par=par, lim=lim)
    finally:
        conn.close()


# ----------------------------------------------------------------------------------------------
# cerrar / pausar / reanudar
# ----------------------------------------------------------------------------------------------
def cerrar(oferta_id: str, *, raiz: Path | None = None, ahora: Callable[[], datetime] = comun.ahora_utc) -> dict:
    """``orq cerrar --oferta OF [--live]``: fase final y post-mortem (envoltorio de ``engine.cerrar``)."""
    from engine import cerrar as _cerrar
    return _cerrar.cerrar_oferta(oferta_id, raiz=raiz, ahora=ahora, actor="orq")


def pausar(oferta_id: str | None = None, *, motivo: str = "pausa manual", raiz: Path | None = None,
          ahora: Callable[[], datetime] = comun.ahora_utc, ejecutor_obj: Ejecutor | None = None) -> dict:
    """``orq pausar [--oferta OF]``: crea ``PAUSA`` (global) y, si hay ``--oferta``, pausa esa oferta."""
    estado.fijar_pausa(motivo, raiz=raiz, ahora=ahora)
    resultado = None
    if oferta_id is not None:
        resultado = (ejecutor_obj or EjecutorMotor(raiz=raiz, ahora=ahora)).pausar(oferta_id, motivo=motivo)
    return {"pausa": True, "oferta_id": oferta_id, "resultado": resultado.__dict__ if resultado else None}


def reanudar(*, raiz: Path | None = None, ahora: Callable[[], datetime] = comun.ahora_utc,
            firma_verificada: bool = False, infra_verde: bool = False) -> dict:
    """``orq reanudar``: quita ``PAUSA``. Exige firma y preflight VERDE (gate H en todos los niveles,
    docs/contratos.md §2, ``accion:reactivar_tras_pausa``): ambas condiciones las verifica el llamador
    (la firma, con una orden de :func:`firmar`; el preflight, con ``empresa/infra/estado.json``) y se
    declaran EXPLÍCITAMENTE aquí para que nadie reanude por descuido con el valor por defecto."""
    if not firma_verificada:
        raise ErrorBloqueado("reanudar exige una orden firmada (accion:reactivar_tras_pausa) verificada por el llamador")
    if not infra_verde:
        raise ErrorBloqueado("reanudar exige preflight VERDE antes de quitar PAUSA")
    estado.quitar_pausa(raiz=raiz, ahora=ahora)
    return {"pausa": False}


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def _raiz_de(args: argparse.Namespace, env: dict[str, str]) -> Path | None:
    if args.raiz:
        if comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz no existe con FABRICA_ENTORNO=produccion")
        return Path(args.raiz).resolve()
    return None


def _reloj_de(args: argparse.Namespace, env: dict[str, str]) -> Callable[[], datetime]:
    if args.ahora:
        if comun.entorno(env) == "produccion":
            raise ErrorUso("--ahora no existe con FABRICA_ENTORNO=produccion")
        return lambda: comun.parsear_z(args.ahora)
    return comun.ahora_utc


def _imprimir(args: argparse.Namespace, datos: Any, *, modo: str, codigo: int = 0, avisos: Sequence[str] = ()) -> None:
    if args.json:
        print(json.dumps({"ok": codigo == 0, "modo": modo, "codigo": codigo, "datos": datos, "avisos": list(avisos)},
                         sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(datos, sort_keys=True, ensure_ascii=False))


def main(argv: Sequence[str] | None = None) -> int:
    """CLI ``python -m engine.orq <subcomando> …`` (docs/06 §4.2)."""
    ap = argparse.ArgumentParser(prog="python -m engine.orq", description="Orquestador de una oferta.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def comun_args(p: argparse.ArgumentParser, *, oferta: bool = True) -> None:
        if oferta:
            p.add_argument("--oferta", required=True)
        p.add_argument("--live", action="store_true")
        p.add_argument("--raiz")
        p.add_argument("--ahora")
        p.add_argument("--json", action="store_true")

    p = sub.add_parser("crear"); p.add_argument("--brief", required=True); comun_args(p, oferta=False)
    p = sub.add_parser("estado"); comun_args(p)
    p = sub.add_parser("siguiente"); comun_args(p)
    p = sub.add_parser("ejecutar")
    p.add_argument("--etapa", required=True); p.add_argument("--modo", choices=("dry-run", "fixture", "live"), default="fixture")
    p.add_argument("--fixture"); comun_args(p)
    p = sub.add_parser("firmar")
    p.add_argument("--etapa"); p.add_argument("--accion", default="aprobar_etapa"); p.add_argument("--hash-objetivo", required=True)
    p.add_argument("--como", default="dueno"); p.add_argument("--clave-privada", required=True); p.add_argument("--nonce")
    comun_args(p)
    p = sub.add_parser("ingresar")
    p.add_argument("--etapa", required=True); p.add_argument("--desde", required=True)
    p.add_argument("--origen", choices=("humano", "sesion_code"), default="humano"); comun_args(p)
    p = sub.add_parser("nivel")
    p.add_argument("--etapa", required=True); p.add_argument("--a", required=True); p.add_argument("--evidencia", required=True)
    p.add_argument("--como", default="dueno"); comun_args(p, oferta=False); p.add_argument("--oferta", required=True)
    p = sub.add_parser("activar")
    p.add_argument("--object-ids", nargs="+", default=[]); p.add_argument("--hash-config", required=True); comun_args(p)
    p = sub.add_parser("ciclo-d8"); comun_args(p)
    p = sub.add_parser("veredicto"); comun_args(p)
    p = sub.add_parser("cerrar"); comun_args(p)
    p = sub.add_parser("pausar"); comun_args(p, oferta=False); p.add_argument("--oferta")
    p = sub.add_parser("reanudar"); comun_args(p, oferta=False)

    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        raiz = _raiz_de(args, env)
        ahora = _reloj_de(args, env)
        modo = "live" if getattr(args, "live", False) else "dry_run"
        if args.cmd == "crear":
            datos = crear(ruta_brief=Path(args.brief), raiz=raiz, ahora=ahora)
        elif args.cmd == "estado":
            datos = ver_estado(args.oferta, raiz=raiz)
        elif args.cmd == "siguiente":
            datos = siguiente(args.oferta, raiz=raiz)
        elif args.cmd == "ejecutar":
            if args.modo != "fixture":
                raise ErrorBloqueado(f"orq ejecutar --modo {args.modo}: todavía no hay agentes.runner (B9); solo --modo fixture corre en este alcance")
            if not args.fixture:
                raise ErrorUso("--modo fixture exige --fixture DIR")
            datos = ejecutar(args.oferta, args.etapa, fixture_dir=Path(args.fixture), raiz=raiz, ahora=ahora, env=env)
        elif args.cmd == "firmar":
            datos = firmar(oferta_id=args.oferta, accion=args.accion, etapa=args.etapa, hash_objetivo=args.hash_objetivo,
                           clave_privada=Path(args.clave_privada), raiz=raiz, ahora=ahora, nonce=args.nonce)
        elif args.cmd == "ingresar":
            datos = ingresar(args.oferta, args.etapa, desde=Path(args.desde), raiz=raiz, ahora=ahora, env=env)
        elif args.cmd == "nivel":
            datos = nivel(args.oferta, args.etapa, a=args.a, evidencia=Path(args.evidencia), aprobado_por=args.como, raiz=raiz, ahora=ahora)
        elif args.cmd == "activar":
            if args.live:
                raise ErrorBloqueado("orq activar --live: meta.activar (B5) todavía no está integrado en este alcance")
            datos = activar(args.oferta, object_ids=args.object_ids, hash_config=args.hash_config, modo="fixture", raiz=raiz, ahora=ahora, env=env)
        elif args.cmd == "ciclo-d8":
            datos = {"decisiones": ciclo_d8(args.oferta, raiz=raiz, ahora=ahora, modo=modo)}
        elif args.cmd == "veredicto":
            datos = veredicto(args.oferta, raiz=raiz, ahora=ahora)
        elif args.cmd == "cerrar":
            datos = cerrar(args.oferta, raiz=raiz, ahora=ahora)
        elif args.cmd == "pausar":
            datos = pausar(args.oferta, raiz=raiz, ahora=ahora)
        else:  # reanudar
            raise ErrorBloqueado("orq reanudar: requiere --firma-verificada/--infra-verde explícitos; use la API de Python, no esta CLI mínima")
        _imprimir(args, datos, modo=modo)
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
