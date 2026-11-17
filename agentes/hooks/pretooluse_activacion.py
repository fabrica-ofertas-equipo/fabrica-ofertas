#!/usr/bin/env python3
"""``pretooluse_activacion.py`` — activar/publicar solo con sello de X1 y ``object_ids`` exactos.

Matcher ``mcp__.*|Bash`` (docs/09 §14.3). Dos ramas (crítica M07): el conector MCP en modo borrador
(``ads_activate_entity``/``ads_update_entity``, parámetros propios de ese conector) y la Marketing
API por ``Bash`` (``meta_activar.py``/``meta_crear.py``/``subir_presupuesto.py`` con ``--live``, sin
esos parámetros: se parsean los argumentos de la orden; cubre ``--live`` y ``--modo live``, la forma ``python -m meta.*`` y
``python -m engine.orq activar``, con ids de ``--object-ids`` y/o de ``--ids-meta``). Cualquier ambigüedad deniega (regla 5).

Decisión de diseño (documentada en ``agentes/README.md``, «Decisiones»): el esquema de
``ads_activate_entity`` no trae ``hash_config``; el hook busca, entre los sellos vigentes de
``AGENT_OFERTA_ID`` en ``empresa/compliance/sellos/``, uno cuyo ``object_ids`` sea EXACTAMENTE
``{entity_id} ∪ object_ids`` del tool_input. Ninguno o más de uno que empate ⇒ deny.
"""
from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # bootstrap: ver agentes/hooks/_comun.py

from agentes.hooks import _comun as c  # noqa: E402
from engine import comun as motor  # noqa: E402
from engine import limites as motor_limites  # noqa: E402
from engine.errores import ErrorFabrica  # noqa: E402

_HERRAMIENTAS_ACTIVACION = ("ads_activate_entity",)
_HERRAMIENTAS_UPDATE = ("ads_update_entity",)
_HERRAMIENTAS_PROHIBIDAS_SIEMPRE = ("ads_delete_", "ads_catalog_")
_SCRIPTS_ACTIVACION = ("meta_activar.py", "meta_crear.py", "subir_presupuesto.py")


def _nombre_corto(tool_name: str) -> str:
    """Último segmento tras ``__`` de un nombre MCP (``mcp__servidor__ads_activate_entity`` -> ads_activate_entity)."""
    return tool_name.rsplit("__", 1)[-1] if "__" in tool_name else tool_name


def _sellos_candidatos(raiz: Path, oferta_id: str) -> list[dict[str, Any]]:
    carpeta = raiz / "empresa" / "compliance" / "sellos"
    if not carpeta.is_dir():
        return []
    candidatos: list[dict[str, Any]] = []
    for archivo in sorted(carpeta.glob("*.json")):
        try:
            sello = motor.cargar_json(archivo)
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        if isinstance(sello, dict) and sello.get("oferta_id") == oferta_id:
            candidatos.append(sello)
    return candidatos


def _sello_firmado_y_vigente(sello: Mapping[str, Any], env: Mapping[str, str]) -> bool:
    firma = sello.get("firma")
    clave_publica = env.get("FABRICA_FIRMA_PUBLICA")
    if not isinstance(firma, str) or not clave_publica:
        return False
    cuerpo = {k: v for k, v in sello.items() if k != "firma"}
    try:
        if not motor.verificar_ed25519(motor.json_canonico(cuerpo), firma, clave_publica):
            return False
        vigencia = motor.parsear_z(str(sello.get("vigencia_hasta")))
    except ErrorFabrica:
        return False
    return motor.ahora_utc() <= vigencia


def _sello_para_object_ids(raiz: Path, env: Mapping[str, str], oferta_id: str, conjunto_pedido: set[str]) -> str | None:
    """``None`` si hay EXACTAMENTE un sello vigente de ``oferta_id`` cuyo ``object_ids`` coincide; si no, el motivo."""
    candidatos = [s for s in _sellos_candidatos(raiz, oferta_id) if _sello_firmado_y_vigente(s, env)]
    coincidencias = [s for s in candidatos if set(map(str, s.get("object_ids") or ())) == conjunto_pedido]
    if len(coincidencias) == 1:
        return None
    if not coincidencias:
        if not candidatos:
            return f"activación sin sello vigente para {oferta_id}"
        faltan = sorted(set(map(str, candidatos[0].get("object_ids") or ())) - conjunto_pedido) if len(candidatos) == 1 else []
        extra = sorted(conjunto_pedido - set(map(str, candidatos[0].get("object_ids") or ()))) if len(candidatos) == 1 else []
        detalle = f" (object_ids difieren: faltan {faltan}, de más {extra})" if (faltan or extra) else ""
        return f"activación sin sello vigente para {oferta_id}{detalle}"
    return f"activación ambigua para {oferta_id}: {len(coincidencias)} sellos vigentes coinciden"


def _cuenta_permitida(raiz: Path, env: Mapping[str, str], ad_account_id: Any) -> bool:
    try:
        lim = motor_limites.cargar_limites(raiz / "empresa" / "limites.yaml", env=env)
        permitidas = lim.valor("cuentas_permitidas")
    except ErrorFabrica:
        return False
    return isinstance(ad_account_id, str) and ad_account_id in (permitidas or ())


def _comprobar_activacion(tool_input: Mapping[str, Any], raiz: Path, env: Mapping[str, str]) -> str | None:
    oferta_id = (env.get("AGENT_OFERTA_ID") or "").strip()
    if not oferta_id:
        return "activación sin AGENT_OFERTA_ID"
    if not (raiz / "ofertas" / oferta_id / "07-campana" / "aprobacion.json").is_file():
        return f"activación sin aprobacion.json para {oferta_id}"
    if tool_input.get("allow_partial_publish"):
        return "allow_partial_publish debe ser falso o ausente"
    if tool_input.get("ignore_validation_errors"):
        return "ignore_validation_errors debe ser falso o ausente"
    entity_id = tool_input.get("entity_id")
    conjunto = {str(o) for o in (tool_input.get("object_ids") or ())}
    if entity_id is not None:
        conjunto.add(str(entity_id))
    if not conjunto:
        return "activación sin entity_id ni object_ids"
    motivo_sello = _sello_para_object_ids(raiz, env, oferta_id, conjunto)
    if motivo_sello:
        return motivo_sello
    ad_account_id = tool_input.get("ad_account_id")
    if ad_account_id is not None and not _cuenta_permitida(raiz, env, ad_account_id):
        return f"ad_account_id fuera de cuentas_permitidas: {ad_account_id!r}"
    return None


def _comprobar_update_entity(tool_input: Mapping[str, Any], raiz: Path, env: Mapping[str, str]) -> str | None:
    """H9: ``fields`` llega como cadena JSON. Solo ``{"status":"PAUSED"}`` pasa sin más; cualquier
    otra cosa (incluida activación) exige las mismas condiciones que :func:`_comprobar_activacion`."""
    if tool_input.get("discard_draft_changes"):
        return "discard_draft_changes distinto de falso: borra objetos no publicados"
    fields_crudo = tool_input.get("fields")
    if isinstance(fields_crudo, str):
        try:
            fields = json.loads(fields_crudo)
        except json.JSONDecodeError:
            return "fields: JSON inválido (se esperaba una cadena JSON, H9)"
    else:
        fields = fields_crudo
    if not isinstance(fields, dict) or not fields:
        return "fields: se esperaba un objeto JSON no vacío"
    if fields == {"status": "PAUSED"}:
        return None  # pausar es la acción segura
    if fields.get("status") == "ACTIVE" and set(fields) == {"status"}:
        return _comprobar_activacion(tool_input, raiz, env)
    return "solo subir_presupuesto.py/pausar.py pueden cambiar este campo (ads_update_entity está restringido a pausar o activar)"


_MODULOS_ACTIVACION = ("meta.activar", "meta.crear", "meta.subir_presupuesto")
_MODOS_SIN_EFECTO = ("dry-run", "fixture")


def _invoca_activacion(partes: list[str]) -> bool:
    """¿El comando invoca un CLI que puede activar o gastar? Cubre la forma por archivo
    (``scripts/meta_activar.py``…), la forma módulo (``python -m meta.activar``…) y ``python -m engine.orq activar``."""
    if any(any(script in p for script in _SCRIPTS_ACTIVACION) for p in partes):
        return True
    if any(p in _MODULOS_ACTIVACION or p.endswith(("/meta/activar.py", "/meta/crear.py", "/meta/subir_presupuesto.py")) for p in partes):
        return True
    for k, p in enumerate(partes):
        if p == "engine.orq" or p.endswith("engine/orq.py"):
            if "activar" in partes[k + 1:]:
                return True
    return False


def _es_modo_vivo(partes: list[str]) -> bool:
    """``--live`` o ``--modo <v>``/``--modo=<v>`` con ``v`` distinto de dry-run/fixture. Un ``--modo`` sin valor, o repetido
    con valores distintos, cuenta como vivo (falla cerrado)."""
    if "--live" in partes:
        return True
    modos: list[str | None] = []
    for k, p in enumerate(partes):
        if p == "--modo":
            modos.append(partes[k + 1] if k + 1 < len(partes) else None)
        elif p.startswith("--modo="):
            modos.append(p.split("=", 1)[1])
    return any(m not in _MODOS_SIN_EFECTO for m in modos)


def _valores_de_bandera(partes: list[str], bandera: str) -> list[str] | None:
    """Valores de ``--bandera`` (``--b v1 v2`` o ``--b=v1``) hasta la siguiente bandera; ``None`` si no aparece."""
    valores: list[str] = []
    hallada = False
    k = 0
    while k < len(partes):
        p = partes[k]
        if p == bandera:
            hallada = True
            k += 1
            while k < len(partes) and not partes[k].startswith("--"):
                valores.append(partes[k])
                k += 1
            continue
        if p.startswith(bandera + "="):
            hallada = True
            valores.append(p.split("=", 1)[1])
        k += 1
    return valores if hallada else None


def _ids_desde_archivo_ids_meta(ruta_txt: str, raiz: Path, oferta_id: str) -> set[str] | str:
    """Conjunto ``{campaign_id} ∪ adset_ids ∪ ad_ids`` del ``ids_meta.json`` indicado (mismo que activa ``meta.activar``);
    texto con el motivo si el archivo está fuera de la oferta, no existe o no tiene la forma."""
    ruta = Path(ruta_txt)
    ruta = ruta if ruta.is_absolute() else raiz / ruta
    base = raiz / "ofertas" / oferta_id
    if not c.ruta_dentro_de(ruta, base):
        return f"--ids-meta fuera de ofertas/{oferta_id}/: {ruta_txt}"
    try:
        doc = motor.cargar_json(ruta)
        return {str(doc["campaign_id"]), *map(str, doc["adset_ids"]), *map(str, doc["ad_ids"])}
    except (OSError, ValueError, UnicodeDecodeError, KeyError, TypeError):
        return f"--ids-meta ilegible o sin campaign_id/adset_ids/ad_ids: {ruta_txt}"


def _comprobar_bash(comando: str, raiz: Path, env: Mapping[str, str]) -> str | None:
    """Rama de la Marketing API por ``Bash``: los CLI REALES de activación (``meta_activar.py``/``meta_crear.py``/
    ``subir_presupuesto.py``, ``python -m meta.*`` y ``python -m engine.orq activar``) en modo VIVO (``--live`` o
    ``--modo live``) exigen sello vigente de X1 con ``object_ids`` exactos. Los ids salen de ``--object-ids`` (coma o
    espacios) y/o del archivo de ``--ids-meta``; si vienen de las dos fuentes deben coincidir. Fail-closed."""
    try:
        partes = shlex.split(comando)
    except ValueError:
        return "Bash: comando ilegible para el analizador de argumentos"
    if not _invoca_activacion(partes):
        return None  # no es una activación: el resto del comando lo evalúa pretooluse_bash
    if not _es_modo_vivo(partes):
        return None  # dry-run/fixture: sin efecto, no hace falta sello

    oferta_vals = _valores_de_bandera(partes, "--oferta")
    oferta_id = (oferta_vals[0] if oferta_vals else "") or (env.get("AGENT_OFERTA_ID") or "")
    hash_vals = _valores_de_bandera(partes, "--hash-config")
    hash_config = hash_vals[0] if hash_vals else None
    if not oferta_id or not hash_config:
        return "Bash de activación sin --oferta/--hash-config completos"

    del_comando: set[str] = set()
    ids_vals = _valores_de_bandera(partes, "--object-ids")
    for v in ids_vals or ():
        del_comando.update(x for x in v.split(",") if x)
    del_archivo: set[str] | None = None
    meta_vals = _valores_de_bandera(partes, "--ids-meta")
    if meta_vals:
        resultado = _ids_desde_archivo_ids_meta(meta_vals[0], raiz, oferta_id)
        if isinstance(resultado, str):
            return f"Bash de activación: {resultado}"
        del_archivo = resultado
    if del_archivo is not None and ids_vals is not None and del_comando != del_archivo:
        return "Bash de activación: --object-ids no coincide con los ids de --ids-meta"
    objetos = del_archivo if del_archivo is not None else del_comando
    if not objetos:
        return "Bash de activación sin --object-ids ni --ids-meta: no se sabe qué se activa"

    ruta_sello = raiz / "empresa" / "compliance" / "sellos" / f"{hash_config}.json"
    try:
        sello = motor.cargar_json(ruta_sello)
    except (OSError, ValueError, UnicodeDecodeError, FileNotFoundError):
        return f"Bash de activación sin sello vigente para {hash_config}"
    if sello.get("oferta_id") != oferta_id or not _sello_firmado_y_vigente(sello, env):
        return f"Bash de activación: sello inválido o vencido para {hash_config}"
    if set(map(str, sello.get("object_ids") or ())) != {str(o) for o in objetos}:
        return "Bash de activación: object_ids no coinciden con el sello"
    return None


def manejar(datos: Mapping[str, Any]) -> str | None:
    import os

    env = os.environ
    tool_name = str(datos.get("tool_name") or "")
    corto = _nombre_corto(tool_name)
    tool_input = datos.get("tool_input") if isinstance(datos.get("tool_input"), Mapping) else {}

    if any(corto.startswith(p) for p in _HERRAMIENTAS_PROHIBIDAS_SIEMPRE):
        return f"{corto} está prohibida (borra o toca el catálogo: fuera de alcance)"

    motivo: str | None = None
    if tool_name == "Bash":
        comando = str(tool_input.get("command") or "")
        motivo = _comprobar_bash(comando, c.raiz_agente(env), env)
    elif corto in _HERRAMIENTAS_ACTIVACION:
        motivo = _comprobar_activacion(tool_input, c.raiz_agente(env), env)
    elif corto in _HERRAMIENTAS_UPDATE:
        motivo = _comprobar_update_entity(tool_input, c.raiz_agente(env), env)
    else:
        return None  # fuera del alcance de este hook (lo ve pretooluse_gasto)

    if motivo:
        c.anotar_spool(env, c.construir_entrada_registro(
            env, evento="PreToolUse", tool=tool_name, tool_use_id=datos.get("tool_use_id"), entrada={}, resultado="deny",
        ))
    return motivo


if __name__ == "__main__":
    c.ejecutar(manejar)
