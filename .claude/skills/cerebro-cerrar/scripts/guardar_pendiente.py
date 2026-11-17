#!/usr/bin/env python3
"""Guarda UNA línea saneada en la memoria del Cerebro: pendientes y propuestas de regla en la lista única, decisiones y lecciones aparte.

Biblioteca estándar. Solo AGREGA: nunca sobrescribe, nunca borra, nunca edita una línea anterior. Por defecto NO escribe (previsualiza): hace falta
``--escribir`` y lo pone la skill ``/cerebro-cerrar`` solo después de que el dueño confirmó esa línea.

Uso (desde la raíz del repositorio):
    .venv/bin/python .claude/skills/cerebro-cerrar/scripts/guardar_pendiente.py <clase> [--stdin | --json '{...}'] [--escribir] [--raiz R]
    .venv/bin/python .claude/skills/cerebro-cerrar/scripts/guardar_pendiente.py listar [--clase todas|pendiente|regla_propuesta|decision|leccion] [--abiertas] [--raiz R]

Clases y destino:
    pendiente · regla_propuesta  → empresa/panel/pulido.jsonl      (la misma bitácora que lee el panel; formato de dashboard/pulido.py)
    preferencia                  → empresa/panel/pulido.jsonl      (una corrección REPETIDA ≥ 2 veces, con la prueba de cada instancia: queda como
                                                                    regla_propuesta/pref ABIERTA, para que la apruebe el dueño; nunca se aplica sola)
    preferencia_resolver         → empresa/memoria/preferencias.jsonl  (SOLO con las palabras del dueño: aprobada · rechazada · revocada)
    decision                     → empresa/memoria/decisiones_dueno.jsonl
    leccion                      → empresa/memoria/lecciones.jsonl  (exige prueba: un archivo del repositorio; el script calcula su sha256)
``empresa/memoria/`` se crea solo al escribir (con ``--escribir``); previsualizar no crea nada.

Salida: JSON en stdout (``ok``, ``modo``, ``destino``, ``linea``, ``similares``). Errores: JSON en stderr con ``codigo`` y ``mensaje``; nunca imprime el
valor que parecía un secreto. Códigos de salida: 0 ok · 2 uso · 3 campo inválido · 4 parece una clave o un token (no se guarda) ·
5 repetido (parecido ≥ 0,80 a algo ya guardado; ``--permitir-repetido`` lo permite) · 6 no se pudo escribir (destino no regular, enlace, lleno…).

Los textos son DATOS: no se interpretan, solo se limpian de controles y de caracteres de dirección y se guardan como JSON ASCII.
Una «corrección» NUNCA se vuelve regla aquí: una regla nueva solo la aprueba el dueño, a mano; ``regla_propuesta`` es un pendiente para eso.
Una preferencia propuesta tampoco rige hasta que el dueño la aprueba con sus palabras (``preferencia_resolver``); quien la lee (D6 y otras skills)
usa ``scripts/cerebro/preferencias.py``, que solo devuelve las aprobadas y vigentes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import fcntl
import hashlib
import json
import os
import re
import stat
import sys
import unicodedata
from pathlib import Path
from typing import Any

# ── constantes: espejo de dashboard/pulido.py (la prueba test_guardar_pendiente.py comprueba que no se desvíen) ──────────────────────────
ETAPAS = ("M1", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10")
ETAPAS_PULIDO = frozenset([*ETAPAS, "O0", "D0", "F1", "F2", "X1", "X2"])
SEVERIDADES = ("baja", "media", "alta")
RESPONSABLES = ("dueno", "ia", "robot", "otro")
PRIORIDADES = ("P0", "P1", "P2", "P3")
CATEGORIAS = ("error", "regla", "pref", "riesgo", "contexto")
LIMITE_TITULO = 140
LIMITE_DETALLE = 4000
LIMITE_ORIGEN = 80
LIMITE_BLOQUEA = 8
LIMITE_ITEM_BLOQUEA = 40
SEVERIDAD_DE_PRIORIDAD = {"P0": "alta", "P1": "alta", "P2": "media", "P3": "baja"}
RX_OFERTA = re.compile(r"^(OF-[0-9]{6}-[0-9]{2}|_[a-z0-9][a-z0-9_-]{0,31})$")
RX_ORIGEN = re.compile(r"^[\w/#@][\w ._:/#@()+,§\-]*$")
RX_ITEM_BLOQUEA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:\-]{0,39}$")
RX_FECHA = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
RX_FECHA_HORA = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
RX_ID_PUL = re.compile(r"^PUL-([0-9]{4,9})$")
RX_ID_PRF = re.compile(r"^PRF-([0-9]{4,9})$")

# ── propias del Cerebro (alineadas con X2: departamentos/15-memoria-aprendizaje.md, Anexo C y §3.2) ────────────────────────────────────────
CLASES = ("pendiente", "regla_propuesta", "preferencia", "decision", "leccion")
RESOLVER = "preferencia_resolver"      # no es una clase de línea nueva en la lista única: escribe en el buzón de preferencias
ALCANCES_DECISION = ("sistema", "oferta", "etapa", "macro_nicho", "nicho", "locale", "formato", "universal")
ALCANCES_LECCION = ("solo_esta_vez", "formato", "locale", "nicho", "macro_nicho", "universal")   # «universal» exige ≥ 2 macro_nichos y ≥ 2 locale: lo decide X2
CONFIANZAS = ("B", "C")        # A (replicada en ≥ 2 ofertas) solo la asigna X2 al ver los datos: una sesión no puede
LIMITE_DECISION_DETALLE = 1000
LIMITE_LECCION = 280           # X2: afirmacion ≤ 280
MAX_EVIDENCIAS = 5
TOPE_EVIDENCIA = 8 * 1024 * 1024
TOPE_ARCHIVO = 20 * 1024 * 1024
SIM_DUP = 0.80                 # empresa/parametros.yaml, grupo memoria: sim_dup
SIM_RELEVANTE = 0.60           # ídem: sim_relevante
# Carril de preferencias (informe de brechas B1-05, «con 2-3 correcciones aprende» [V 27:30]). N_MIN_PREFERENCIA es un [SUPUESTO] tomado del video de referencia,
# no un parámetro firmado: X2 usa n_min_patron_eventos = 3 para PATRONES DE SKILL; una preferencia del dueño (criterio con fecha, nunca regla) pide menos.
N_MIN_PREFERENCIA = 2
MAX_INSTANCIAS = 5
LIMITE_CRITERIO = 280          # como la afirmación de X2
LIMITE_SOBRE = 140
LIMITE_CITA = 200              # las palabras del dueño; ≤ 25 palabras
MAX_PALABRAS_CITA = 25
ALCANCES_PREFERENCIA = ("etapa", "formato", "oferta", "nicho", "locale")      # «universal» y «macro_nicho» los decide X2 con datos de varias ofertas
PRIORIDADES_PREFERENCIA = ("P2", "P3")       # una preferencia nunca frena gastar ni una etapa
ESTADOS_RESOLUCION = ("aprobada", "rechazada", "revocada")
REL_PULIDO = "empresa/panel/pulido.jsonl"
REL_DECISIONES = "empresa/memoria/decisiones_dueno.jsonl"
REL_LECCIONES = "empresa/memoria/lecciones.jsonl"
REL_PREFERENCIAS = "empresa/memoria/preferencias.jsonl"
DESTINOS = {"pendiente": REL_PULIDO, "regla_propuesta": REL_PULIDO, "preferencia": REL_PULIDO, "decision": REL_DECISIONES, "leccion": REL_LECCIONES}
PREFIJO_ID = {REL_PULIDO: "PUL", REL_DECISIONES: "DEC", REL_LECCIONES: "LEC", REL_PREFERENCIAS: "PRF"}

_RX_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_RX_DIRECCION = re.compile("[​-‏‪-‮⁠-⁤⁦-⁩﻿]")
_RX_NOMBRE_SECRETO = re.compile(r"(^|/)(\.env[^/]*|[^/]*\.(pem|key|p12|pfx|keystore)|secretos?[^/]*|[^/]*(clave|key)[_-]?privada[^/]*|id_(rsa|ed25519)[^/]*)$", re.IGNORECASE)


class ErrorCerebro(Exception):
    """Error con código de salida y código corto; el mensaje nunca incluye el valor sospechoso."""

    def __init__(self, salida: int, codigo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.salida, self.codigo, self.mensaje = salida, codigo, mensaje


# ───────────────────────────────────────── secretos ─────────────────────────────────────────
_PATRONES_SECRETO: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("clave privada (PEM)", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY")),
    ("clave de acceso de AWS", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("clave tipo sk-", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}")),
    ("token de GitHub", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})")),
    ("token de Slack", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("clave de Stripe", re.compile(r"\b([rsp]k_(live|test)_[A-Za-z0-9]{16,}|whsec_[A-Za-z0-9]{16,})")),
    ("clave de Google", re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}")),
    ("token de bot de Telegram", re.compile(r"\b[0-9]{8,10}:[A-Za-z0-9_\-]{35}\b")),
    ("cabecera Bearer", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/\-]{20,}", re.IGNORECASE)),
    ("URL con usuario y contraseña", re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s/:@]+:[^\s/@]{3,}@", re.IGNORECASE)),
)
_RX_ASIGNACION = re.compile(
    r"[A-Za-z_]*(?:secret|token|passw(?:or)?d|passwd|api[_\-]?key|private[_\-]?key|access[_\-]?key|clave|contrase(?:ñ|n)a|credencial)[A-Za-z_]*"
    r"\s*[:=]\s*[\"']?([^\s\"',;]{12,})", re.IGNORECASE)
_RX_FICHA_ALEATORIA = re.compile(r"[A-Za-z0-9+_\-]{32,}={0,2}")


def _parece_marcador(valor: str) -> bool:
    """Marcadores de posición, nombres de variables y rutas de archivo (``<RUTA_DE_TU_CLAVE_PRIVADA>``, ``STRIPE_SECRET_KEY``, ``ofertas/x/qa/d3-v1.json``) no son un secreto."""
    if re.fullmatch(r"[A-Z][A-Z0-9_]*", valor) or valor.startswith(("<", "$", "{", "[", "RUTA", "ruta", "xxx", "XXX", "…", "...")):
        return True
    return bool(re.fullmatch(r"[\w./\-]+", valor)) and "/" in valor and ("." in valor or valor.count("/") >= 2)


def buscar_secreto(texto: str) -> str | None:
    """Tipo de secreto que ``texto`` parece contener, o ``None``. No devuelve el valor."""
    for tipo, rx in _PATRONES_SECRETO:
        if rx.search(texto):
            return tipo
    for m in _RX_ASIGNACION.finditer(texto):
        if not _parece_marcador(m.group(1)):
            return "asignación de clave, token o contraseña"
    for m in _RX_FICHA_ALEATORIA.finditer(texto):
        ficha = m.group(0).rstrip("=")
        if re.fullmatch(r"[0-9a-fA-F]+", ficha):
            continue                    # hash (sha256, sha1, git): es una prueba, no un secreto
        if re.search(r"[a-z]", ficha) and re.search(r"[A-Z]", ficha) and re.search(r"[0-9]", ficha) and ficha.count("-") + ficha.count("_") <= 3:
            return "cadena larga con aspecto de clave"          # una clave aleatoria casi no lleva guiones; un título largo con guiones sí
    return None


def _revisar_secretos(valor: Any, ruta: str = "") -> None:
    if isinstance(valor, str):
        tipo = buscar_secreto(valor)
        if tipo:
            raise ErrorCerebro(4, "parece_secreto", f"El campo {ruta or 'entrada'} parece contener {tipo}: no se guarda. Quita el valor (deja solo dónde vive).")
    elif isinstance(valor, dict):
        for k, v in valor.items():
            _revisar_secretos(v, f"{ruta}.{k}" if ruta else str(k))
    elif isinstance(valor, list):
        for i, v in enumerate(valor):
            _revisar_secretos(v, f"{ruta}[{i}]")


# ───────────────────────────────────────── validación ─────────────────────────────────────────
def _limpio(valor: str, *, multilinea: bool = False) -> str:
    valor = _RX_DIRECCION.sub("", _RX_CONTROL.sub("", valor))
    valor = unicodedata.normalize("NFC", valor)
    if multilinea:
        return "\n".join(" ".join(linea.split()) for linea in valor.strip().splitlines()).strip()
    return " ".join(valor.split())


def _texto(cuerpo: dict[str, Any], clave: str, *, minimo: int = 0, maximo: int, multilinea: bool = False, defecto: str | None = None) -> str:
    valor = cuerpo.get(clave, defecto)
    if valor is None:
        valor = ""
    if not isinstance(valor, str):
        raise ErrorCerebro(3, "campo_invalido", f"El campo {clave} debe ser texto.")
    valor = _limpio(valor, multilinea=multilinea)
    if len(valor) < minimo:
        raise ErrorCerebro(3, "campo_invalido", f"El campo {clave} es obligatorio.")
    if len(valor) > maximo:
        raise ErrorCerebro(3, "campo_invalido", f"El campo {clave} supera {maximo} caracteres.")
    return valor


def _opcion(cuerpo: dict[str, Any], clave: str, validas: tuple[str, ...], defecto: str | None = None) -> str | None:
    valor = cuerpo.get(clave)
    if valor is None or valor == "":
        return defecto
    if not isinstance(valor, str) or valor not in validas:
        raise ErrorCerebro(3, "campo_invalido", f"El campo {clave} debe ser uno de: {', '.join(validas)}.")
    return valor


def _oferta(cuerpo: dict[str, Any]) -> str | None:
    valor = cuerpo.get("oferta_id")
    if valor is None or valor == "":
        return None
    if not isinstance(valor, str) or not RX_OFERTA.fullmatch(valor):
        raise ErrorCerebro(3, "campo_invalido", "El campo oferta_id no tiene el formato de una oferta (OF-AAAAMM-NN o _ejemplo).")
    return valor


def _etapa(cuerpo: dict[str, Any], defecto: str | None) -> str | None:
    valor = cuerpo.get("etapa", defecto)
    if valor is None or valor == "":
        return defecto
    if valor not in ETAPAS_PULIDO:
        raise ErrorCerebro(3, "campo_invalido", "El campo etapa debe ser una etapa válida (M1, D1…D10, O0, D0, F1, F2, X1, X2).")
    return valor


def _origen(cuerpo: dict[str, Any], hoy: str) -> str:
    valor = cuerpo.get("origen")
    if valor is None or valor == "":
        return f"sesión {hoy} /cerebro-cerrar"
    if not isinstance(valor, str):
        raise ErrorCerebro(3, "campo_invalido", "El campo origen debe ser texto.")
    limpio = _limpio(valor)
    if not limpio:
        return f"sesión {hoy} /cerebro-cerrar"
    if len(limpio) > LIMITE_ORIGEN:
        raise ErrorCerebro(3, "campo_invalido", f"El campo origen supera {LIMITE_ORIGEN} caracteres.")
    if not RX_ORIGEN.fullmatch(limpio):
        raise ErrorCerebro(3, "campo_invalido", "El campo origen solo admite letras, números y los signos . _ : / # @ ( ) + , § -.")
    return limpio


def _bloquea(cuerpo: dict[str, Any]) -> list[str] | None:
    valor = cuerpo.get("bloquea")
    if valor is None or valor == []:
        return None
    if not isinstance(valor, list):
        raise ErrorCerebro(3, "campo_invalido", "El campo bloquea debe ser una lista de ids o etapas.")
    salida: list[str] = []
    for item in valor:
        if not isinstance(item, str) or not RX_ITEM_BLOQUEA.fullmatch(item.strip()):
            raise ErrorCerebro(3, "campo_invalido", f"Cada elemento de bloquea debe ser un id o una etapa (letras, números y . _ : -, hasta {LIMITE_ITEM_BLOQUEA}).")
        if item.strip() not in salida:
            salida.append(item.strip())
    if len(salida) > LIMITE_BLOQUEA:
        raise ErrorCerebro(3, "campo_invalido", f"El campo bloquea admite hasta {LIMITE_BLOQUEA} elementos.")
    return salida


def _vence(cuerpo: dict[str, Any]) -> str | None:
    valor = cuerpo.get("vence")
    if valor is None or valor == "":
        return None
    if not isinstance(valor, str):
        raise ErrorCerebro(3, "campo_invalido", "El campo vence debe ser una fecha ISO (AAAA-MM-DD).")
    valor = valor.strip()
    try:
        if RX_FECHA.fullmatch(valor):
            dt.date.fromisoformat(valor)
        elif RX_FECHA_HORA.fullmatch(valor):
            dt.datetime.strptime(valor, "%Y-%m-%dT%H:%M:%SZ")
        else:
            raise ValueError(valor)
    except ValueError as exc:
        raise ErrorCerebro(3, "campo_invalido", "El campo vence debe ser una fecha ISO válida (AAAA-MM-DD).") from exc
    return valor


def _sin_extras(cuerpo: dict[str, Any], permitidas: set[str]) -> None:
    extras = set(cuerpo) - permitidas
    if extras:
        raise ErrorCerebro(3, "campo_no_permitido", f"Campos no admitidos: {', '.join(sorted(map(str, extras)))}.")


def _evidencias(cuerpo: dict[str, Any], raiz: Path, *, obligatoria: bool) -> list[dict[str, str]]:
    """Lista ``[{ruta, sha256}]``: la ruta es un archivo del repositorio que EXISTE y el hash lo calcula el script (si viene uno, debe coincidir)."""
    crudo = cuerpo.get("evidencia")
    if crudo is None or crudo == []:
        if obligatoria:
            raise ErrorCerebro(3, "falta_prueba", "Una lección exige prueba: al menos un archivo del repositorio en «evidencia» (ruta; el hash lo calcula el script).")
        return []
    if not isinstance(crudo, list) or len(crudo) > MAX_EVIDENCIAS:
        raise ErrorCerebro(3, "campo_invalido", f"El campo evidencia debe ser una lista de hasta {MAX_EVIDENCIAS} elementos {{ruta, sha256?}}.")
    salida: list[dict[str, str]] = []
    base = Path(os.path.realpath(raiz))
    for item in crudo:
        if isinstance(item, str):
            item = {"ruta": item}
        if not isinstance(item, dict) or set(item) - {"ruta", "sha256"} or not isinstance(item.get("ruta"), str):
            raise ErrorCerebro(3, "campo_invalido", "Cada prueba es {ruta, sha256?} con ruta de texto.")
        ruta = item["ruta"].strip().replace("\\", "/")
        partes = ruta.split("/")
        if (not ruta or ruta.startswith("/") or ".." in partes or "" in partes or len(ruta) > 200 or _RX_CONTROL.search(ruta)
                or _RX_NOMBRE_SECRETO.search(ruta)):
            raise ErrorCerebro(3, "campo_invalido", "La ruta de una prueba debe ser relativa al repositorio, sin «..» y sin archivos de claves o secretos.")
        real = Path(os.path.realpath(base / ruta))
        if base not in real.parents or not real.is_file():
            raise ErrorCerebro(3, "prueba_inexistente", f"La prueba {ruta} no existe como archivo dentro del repositorio.")
        if real.stat().st_size > TOPE_EVIDENCIA:
            raise ErrorCerebro(3, "campo_invalido", f"La prueba {ruta} pesa más de {TOPE_EVIDENCIA // (1024 * 1024)} MB.")
        digest = hashlib.sha256(real.read_bytes()).hexdigest()
        dado = item.get("sha256")
        if dado is not None:
            if not isinstance(dado, str) or dado.removeprefix("sha256:").lower() != digest:
                raise ErrorCerebro(3, "hash_no_coincide", f"El sha256 dado para {ruta} no coincide con el del archivo.")
        salida.append({"ruta": ruta, "sha256": f"sha256:{digest}"})
    return salida


def _cita(valor: Any, campo: str) -> str:
    """Las palabras del dueño: texto limpio, 1..LIMITE_CITA caracteres y hasta MAX_PALABRAS_CITA palabras."""
    if not isinstance(valor, str):
        raise ErrorCerebro(3, "campo_invalido", f"El campo {campo} debe ser texto: las palabras del dueño entre comillas.")
    limpio = _limpio(valor)
    if not limpio:
        raise ErrorCerebro(3, "campo_invalido", f"El campo {campo} es obligatorio: cita las palabras del dueño.")
    if len(limpio) > LIMITE_CITA or len(limpio.split()) > MAX_PALABRAS_CITA:
        raise ErrorCerebro(3, "campo_invalido", f"El campo {campo} admite hasta {MAX_PALABRAS_CITA} palabras ({LIMITE_CITA} caracteres): cita solo lo esencial.")
    return limpio


def _instancias(cuerpo: dict[str, Any], raiz: Path, hoy: str) -> list[dict[str, Any]]:
    """Las correcciones repetidas que respaldan una preferencia: cada una con fecha, sobre qué fue y las palabras del dueño; el archivo (con hash) es opcional.

    Hacen falta ``N_MIN_PREFERENCIA`` correcciones DISTINTAS (otra fecha o sobre otra pieza, y otras palabras): la misma corrección copiada dos veces no es repetida.
    """
    crudo = cuerpo.get("instancias")
    if not isinstance(crudo, list) or not crudo:
        raise ErrorCerebro(3, "pocas_correcciones", f"Una preferencia exige «instancias»: al menos {N_MIN_PREFERENCIA} correcciones del dueño, cada una con fecha, sobre qué y sus palabras.")
    if len(crudo) > MAX_INSTANCIAS:
        raise ErrorCerebro(3, "campo_invalido", f"El campo instancias admite hasta {MAX_INSTANCIAS} correcciones.")
    salida: list[dict[str, Any]] = []
    vistas: set[tuple[str, str]] = set()
    citas: list[str] = []
    for i, item in enumerate(crudo, 1):
        if not isinstance(item, dict) or set(item) - {"fecha", "sobre", "cita", "evidencia"}:
            raise ErrorCerebro(3, "campo_invalido", f"La corrección {i} debe ser {{fecha, sobre, cita, evidencia?}}.")
        fecha = item.get("fecha")
        try:
            if not isinstance(fecha, str) or not RX_FECHA.fullmatch(fecha):
                raise ValueError(fecha)
            dia = dt.date.fromisoformat(fecha)
        except ValueError as exc:
            raise ErrorCerebro(3, "campo_invalido", f"La corrección {i} necesita una fecha real AAAA-MM-DD.") from exc
        if dia > dt.date.fromisoformat(hoy) + dt.timedelta(days=1):       # un día de margen: la fecha del dueño puede ir un día adelante de la hora UTC del sistema
            raise ErrorCerebro(3, "campo_invalido", f"La corrección {i} tiene una fecha futura ({dia.isoformat()}): una corrección ya ocurrió.")
        sobre = _texto(item, "sobre", minimo=1, maximo=LIMITE_SOBRE)
        cita = _cita(item.get("cita"), f"cita de la corrección {i}")
        clave = (fecha, _normal(sobre))
        if clave in vistas or any(similitud(cita, c) >= SIM_DUP for c in citas):
            raise ErrorCerebro(3, "correcciones_repetidas", f"La corrección {i} es la misma que otra (misma fecha y pieza, o las mismas palabras): no cuenta como una corrección más.")
        vistas.add(clave)
        citas.append(cita)
        fila: dict[str, Any] = {"fecha": fecha, "sobre": sobre, "cita": cita}
        evidencia = _evidencias({"evidencia": item.get("evidencia")}, raiz, obligatoria=False) if item.get("evidencia") not in (None, [], "") else []
        if evidencia:
            fila["evidencia"] = evidencia
        salida.append(fila)
    if len(salida) < N_MIN_PREFERENCIA:
        raise ErrorCerebro(3, "pocas_correcciones", f"Con {len(salida)} corrección no hay preferencia: hacen falta al menos {N_MIN_PREFERENCIA} distintas. Una sola queda como pendiente o como nota.")
    return salida


def _respaldo(instancias: list[dict[str, Any]]) -> str:
    """``archivo`` si todas las correcciones traen un archivo con hash · ``parcial`` si algunas · ``citas`` si solo hay las palabras del dueño."""
    con = sum(1 for i in instancias if i.get("evidencia"))
    return "archivo" if con == len(instancias) else ("parcial" if con else "citas")


def _detalle_preferencia(criterio: str, alcance: str, etapa: str, instancias: list[dict[str, Any]], respaldo: str) -> str:
    lineas = [f"PREFERENCIA PROPUESTA (no rige hasta que tú la apruebes) · etapa {etapa} · alcance {alcance} · {len(instancias)} correcciones · respaldo: {respaldo}",
              f"Criterio: «{criterio}»"]
    for n, i in enumerate(instancias, 1):
        prueba = "; ".join(f"{e['ruta']} {e['sha256'][:19]}…" for e in i.get("evidencia", [])) or "sin archivo (solo tus palabras)"
        lineas.append(f"{n}) {i['fecha']} · {i['sobre']} · «{i['cita']}» · prueba: {prueba}")
    lineas.append("Si la apruebas, las skills la leen como criterio con fecha: nunca como regla ni límite, y no pisa compliance, límites ni X1. Aprobarla es solo tuyo (/cerebro-cerrar).")
    return "\n".join(lineas)


def validar(clase: str, cuerpo: Any, *, raiz: Path, hoy: str, existentes: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Campos saneados de la línea (sin ``id`` ni ``ts``). Lanza ``ErrorCerebro`` si algo no cumple. Revisa secretos en TODA la entrada."""
    if clase not in CLASES:
        raise ErrorCerebro(2, "uso", f"La clase debe ser una de: {', '.join(CLASES)}.")
    if not isinstance(cuerpo, dict):
        raise ErrorCerebro(3, "cuerpo_invalido", "La entrada debe ser un objeto JSON.")
    _revisar_secretos(cuerpo)
    if clase in ("pendiente", "regla_propuesta"):
        _sin_extras(cuerpo, {"titulo", "detalle", "etapa", "oferta_id", "severidad", "prioridad", "responsable", "categoria", "origen", "bloquea", "vence"})
        titulo = _texto(cuerpo, "titulo", minimo=1, maximo=LIMITE_TITULO)
        detalle = _texto(cuerpo, "detalle", maximo=LIMITE_DETALLE, multilinea=True)
        prioridad = _opcion(cuerpo, "prioridad", PRIORIDADES)
        severidad = _opcion(cuerpo, "severidad", SEVERIDADES, SEVERIDAD_DE_PRIORIDAD.get(prioridad or "", "media"))
        responsable = _opcion(cuerpo, "responsable", RESPONSABLES, "dueno" if clase == "regla_propuesta" else None)
        if clase == "regla_propuesta" and responsable != "dueno":
            raise ErrorCerebro(3, "campo_invalido", "Una regla propuesta la aprueba solo el dueño: responsable debe ser «dueno».")
        linea: dict[str, Any] = {"oferta_id": _oferta(cuerpo), "etapa": _etapa(cuerpo, "O0"), "titulo": titulo, "detalle": detalle, "severidad": severidad, "tipo": clase,
                                 "estado": "abierta"}
        for clave, valor in (("responsable", responsable), ("prioridad", prioridad), ("origen", _origen(cuerpo, hoy)), ("categoria", _opcion(cuerpo, "categoria", CATEGORIAS)),
                             ("bloquea", _bloquea(cuerpo)), ("vence", _vence(cuerpo))):
            if valor is not None:
                linea[clave] = valor
        return linea
    if clase == "preferencia":
        _sin_extras(cuerpo, {"titulo", "criterio", "etapa", "oferta_id", "alcance", "instancias", "origen", "prioridad", "vence"})
        etapa = _etapa(cuerpo, None)
        if etapa is None:
            raise ErrorCerebro(3, "campo_invalido", "El campo etapa es obligatorio en una preferencia: es la etapa que la va a leer (D6, D5…).")
        alcance = _opcion(cuerpo, "alcance", ALCANCES_PREFERENCIA, "etapa")
        oferta = _oferta(cuerpo)
        if alcance == "oferta" and oferta is None:
            raise ErrorCerebro(3, "campo_invalido", "El alcance «oferta» exige oferta_id: la preferencia vale solo para esa oferta.")
        prioridad = _opcion(cuerpo, "prioridad", PRIORIDADES_PREFERENCIA, "P2")
        titulo = _texto(cuerpo, "titulo", minimo=1, maximo=LIMITE_TITULO)
        criterio = _texto(cuerpo, "criterio", minimo=1, maximo=LIMITE_CRITERIO)
        instancias = _instancias(cuerpo, raiz, hoy)
        respaldo = _respaldo(instancias)
        linea = {"oferta_id": oferta, "etapa": etapa, "titulo": titulo, "detalle": _detalle_preferencia(criterio, alcance or "etapa", etapa, instancias, respaldo),
                 "severidad": SEVERIDAD_DE_PRIORIDAD[prioridad or "P2"], "tipo": "regla_propuesta", "estado": "abierta"}
        for clave, valor in (("responsable", "dueno"), ("prioridad", prioridad), ("origen", _origen(cuerpo, hoy)), ("categoria", "pref"), ("vence", _vence(cuerpo))):
            if valor is not None:
                linea[clave] = valor
        linea["preferencia"] = {"criterio": criterio, "alcance": alcance, "n": len(instancias), "respaldo": respaldo, "instancias": instancias}
        if len(json.dumps(linea, ensure_ascii=True)) > 12_000:
            raise ErrorCerebro(3, "campo_invalido", "La preferencia es demasiado larga: acorta las citas.")
        return linea
    if clase == "decision":
        _sin_extras(cuerpo, {"titulo", "detalle", "alcance", "etapa", "oferta_id", "origen", "reemplaza", "evidencia"})
        reemplaza = cuerpo.get("reemplaza")
        if reemplaza not in (None, ""):
            if not isinstance(reemplaza, str) or not re.fullmatch(r"DEC-[0-9]{4,9}", reemplaza):
                raise ErrorCerebro(3, "campo_invalido", "El campo reemplaza debe tener la forma DEC-0001.")
            if existentes is not None and not any(e.get("id") == reemplaza for e in existentes):
                raise ErrorCerebro(3, "campo_invalido", f"No existe la decisión {reemplaza} para reemplazarla.")
        linea = {"tipo": "decision", "titulo": _texto(cuerpo, "titulo", minimo=1, maximo=LIMITE_TITULO),
                 "detalle": _texto(cuerpo, "detalle", maximo=LIMITE_DECISION_DETALLE, multilinea=True), "alcance": _opcion(cuerpo, "alcance", ALCANCES_DECISION, "sistema")}
        for clave, valor in (("etapa", _etapa(cuerpo, None)), ("oferta_id", _oferta(cuerpo))):
            if valor is not None:
                linea[clave] = valor
        linea.update({"origen": _origen(cuerpo, hoy), "vigente": True, "reemplaza": reemplaza or None})
        ev = _evidencias(cuerpo, raiz, obligatoria=False)
        if ev:
            linea["evidencia"] = ev
        return linea
    # leccion
    _sin_extras(cuerpo, {"titulo", "leccion", "etapa", "oferta_id", "confianza", "alcance", "origen", "evidencia"})
    etapa = _etapa(cuerpo, None)
    if etapa is None:
        raise ErrorCerebro(3, "campo_invalido", "El campo etapa es obligatorio en una lección.")
    confianza = cuerpo.get("confianza", "C")
    if confianza == "A":
        raise ErrorCerebro(3, "campo_invalido", "La confianza A (replicada en ≥ 2 ofertas) solo la asigna X2 al ver los datos: usa B o C.")
    if confianza not in CONFIANZAS:
        raise ErrorCerebro(3, "campo_invalido", "El campo confianza debe ser B (una oferta conclusiva) o C (anecdótica o externa).")
    oferta = _oferta(cuerpo)
    if confianza == "B" and oferta is None:
        raise ErrorCerebro(3, "campo_invalido", "La confianza B exige oferta_id: es lo observado en una oferta concreta.")
    linea = {"tipo": "leccion", "titulo": _texto(cuerpo, "titulo", minimo=1, maximo=LIMITE_TITULO), "leccion": _texto(cuerpo, "leccion", minimo=1, maximo=LIMITE_LECCION),
             "etapa": etapa}
    if oferta is not None:
        linea["oferta_id"] = oferta
    linea.update({"confianza": confianza, "alcance": _opcion(cuerpo, "alcance", ALCANCES_LECCION, "solo_esta_vez"), "estado": "candidata", "origen": _origen(cuerpo, hoy),
                  "evidencia": _evidencias(cuerpo, raiz, obligatoria=True)})
    return linea


# ───────────────────────────────────────── repetidos ─────────────────────────────────────────
def _normal(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def similitud(a: str, b: str) -> float:
    """Parecido 0-1 entre dos textos (sin tildes, mayúsculas ni signos): lo mayor entre la razón de secuencia y el solapamiento de palabras."""
    na, nb = _normal(a), _normal(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    palabras_a, palabras_b = set(na.split()), set(nb.split())
    jaccard = len(palabras_a & palabras_b) / len(palabras_a | palabras_b)
    return round(max(difflib.SequenceMatcher(None, na, nb).ratio(), jaccard), 3)


def _clave_texto(linea: dict[str, Any]) -> str:
    return str(linea.get("titulo") or "")


def _criterio(linea: dict[str, Any]) -> str:
    """El criterio de una preferencia: en la propuesta vive dentro de ``preferencia``; en el buzón es un campo propio."""
    pref = linea.get("preferencia")
    return str((pref.get("criterio") if isinstance(pref, dict) else linea.get("criterio")) or "")


def buscar_similares(linea: dict[str, Any], existentes: list[dict[str, Any]], *, minimo: float = SIM_RELEVANTE) -> list[dict[str, Any]]:
    """Líneas ya guardadas parecidas a la nueva (≥ ``minimo``), de más a menos parecida. Compara el título (y la lección o el criterio, si los hay)."""
    salida = []
    for e in existentes:
        s = similitud(_clave_texto(linea), _clave_texto(e))
        if linea.get("leccion") and e.get("leccion"):
            s = max(s, similitud(str(linea["leccion"]), str(e["leccion"])))
        if _criterio(linea) and _criterio(e):
            s = max(s, similitud(_criterio(linea), _criterio(e)))
        if s >= minimo:
            salida.append({"id": e.get("id"), "titulo": _clave_texto(e)[:140], "similitud": s, "repetido": s >= SIM_DUP, "estado": e.get("estado")})
    return sorted(salida, key=lambda x: -x["similitud"])[:5]


# ───────────────────────────────────────── archivo (solo agrega) ─────────────────────────────────────────
def _objetos(crudo: bytes) -> list[dict[str, Any]]:
    salida = []
    for parte in crudo.split(b"\n"):
        if not parte.strip():
            continue
        try:
            obj = json.loads(parte.decode("utf-8"), parse_constant=_rechazar_constante)
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(obj, dict):
            salida.append(obj)
    return salida


def _rechazar_constante(nombre: str) -> None:
    raise ValueError(nombre)


def existentes_vigentes(rel: str, crudo: bytes) -> list[dict[str, Any]]:
    """Entradas ya guardadas, plegadas: para la bitácora, cada alta con su estado vigente; para memoria, las líneas tal cual."""
    objetos = _objetos(crudo)
    if rel != REL_PULIDO:
        return objetos
    altas: dict[str, dict[str, Any]] = {}
    for o in objetos:
        pid = o.get("id")
        if not isinstance(pid, str) or not RX_ID_PUL.fullmatch(pid):
            continue
        if o.get("evento") == "alta" or isinstance(o.get("titulo"), str):
            altas[pid] = dict(o)
        elif pid in altas and o.get("estado") in ("abierta", "en_curso", "resuelta"):
            altas[pid]["estado"] = o["estado"]
    return list(altas.values())


def _siguiente_id(rel: str, objetos: list[dict[str, Any]]) -> str:
    prefijo = PREFIJO_ID[rel]
    rx = re.compile(rf"^{prefijo}-([0-9]{{4,9}})$")
    numeros = [int(m.group(1)) for o in objetos if isinstance(o.get("id"), str) and (m := rx.fullmatch(o["id"]))]
    return f"{prefijo}-{(max(numeros) if numeros else 0) + 1:04d}"


def _linea_json(obj: dict[str, Any], actual: bytes) -> bytes:
    cuerpo = json.dumps(obj, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii") + b"\n"
    return (b"\n" if actual and not actual.endswith(b"\n") else b"") + cuerpo     # cierra una línea anterior a medias sin tocarla


def _ruta_destino(raiz: Path, rel: str, *, crear: bool) -> Path:
    """Ruta absoluta del destino sin salir de la raíz por enlaces; con ``crear`` crea las carpetas que falten (nunca la raíz)."""
    base = os.path.realpath(raiz)
    actual = base
    partes = rel.split("/")
    for p in partes[:-1]:
        siguiente = os.path.join(actual, p)
        if os.path.islink(siguiente):
            real = os.path.realpath(siguiente)
            if real != base and not real.startswith(base + os.sep):
                raise ErrorCerebro(6, "destino_fuera_de_raiz", "El destino escapa de la raíz del proyecto por un enlace simbólico.")
            siguiente = real
        elif not os.path.isdir(siguiente):
            if not crear:
                return Path(os.path.join(actual, *partes[partes.index(p):]))
            os.mkdir(siguiente, 0o755)
        actual = siguiente
    destino = os.path.join(actual, partes[-1])
    if os.path.islink(destino):
        raise ErrorCerebro(6, "destino_fuera_de_raiz", "El destino es un enlace simbólico: no se escribe.")
    return Path(destino)


def _leer_existente(raiz: Path, rel: str) -> bytes:
    destino = _ruta_destino(raiz, rel, crear=False)
    try:
        if destino.is_file():
            if destino.stat().st_size > TOPE_ARCHIVO:
                raise ErrorCerebro(6, "archivo_lleno", "El archivo de destino supera su tamaño máximo.")
            return destino.read_bytes()
    except OSError:
        pass
    return b""


def ahora_iso(ahora: dt.datetime | None = None) -> str:
    momento = ahora or dt.datetime.now(dt.timezone.utc)
    return momento.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _transaccion(raiz: Path, rel: str, armar: Any, escribir: bool) -> dict[str, Any]:
    """Agrega UNA línea a ``rel`` (o, sin ``escribir``, solo la previsualiza). ``armar(actual)`` devuelve ``(linea, similares)`` sobre lo último escrito."""
    if not escribir:
        linea, similares = armar(_leer_existente(raiz, rel))
        return {"ok": True, "modo": "previsualizacion", "destino": rel, "linea": linea, "similares": similares}

    armar(_leer_existente(raiz, rel))                    # prevalida ANTES de crear nada: una entrada rechazada no deja ni una carpeta ni un archivo vacío
    destino = _ruta_destino(raiz, rel, crear=True)
    fd = -1
    try:
        fd = os.open(destino, os.O_RDWR | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0), 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX)                  # el mismo candado que usa el panel (dashboard/archivos.anexar_calculado)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ErrorCerebro(6, "destino_no_regular", "El destino no es un archivo regular.")
            tamano = os.fstat(fd).st_size
            if tamano > TOPE_ARCHIVO:
                raise ErrorCerebro(6, "archivo_lleno", "El archivo de destino supera su tamaño máximo.")
            os.lseek(fd, 0, os.SEEK_SET)
            actual = b""
            while len(actual) < tamano:
                parte = os.read(fd, min(1 << 20, tamano - len(actual)))
                if not parte:
                    break
                actual += parte
            linea, similares = armar(actual)             # otra vez, ya con el candado: el id y los repetidos se calculan sobre lo último escrito
            datos = _linea_json(linea, actual)
            if tamano + len(datos) > TOPE_ARCHIVO:
                raise ErrorCerebro(6, "archivo_lleno", "El archivo de destino alcanzó su tamaño máximo.")
            if os.write(fd, datos) != len(datos):
                raise ErrorCerebro(6, "escritura_incompleta", "No se pudo escribir la línea completa.")
            os.fsync(fd)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError as exc:
        raise ErrorCerebro(6, "escritura_imposible", f"No se pudo escribir: {exc.strerror or exc.__class__.__name__}.") from exc
    finally:
        if fd >= 0:
            os.close(fd)
    return {"ok": True, "modo": "escrito", "destino": rel, "linea": linea, "similares": similares}


def guardar(clase: str, cuerpo: Any, *, raiz: Path, escribir: bool = False, permitir_repetido: bool = False, ahora: dt.datetime | None = None) -> dict[str, Any]:
    """Valida y (solo con ``escribir``) agrega UNA línea. Devuelve ``{ok, modo, destino, linea, similares}``. Lanza ``ErrorCerebro``."""
    ts = ahora_iso(ahora)
    rel = DESTINOS.get(clase)
    if rel is None:
        raise ErrorCerebro(2, "uso", f"La clase debe ser una de: {', '.join(CLASES)}.")
    raiz = Path(raiz)

    def armar(actual: bytes) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        objetos = _objetos(actual)
        existentes = existentes_vigentes(rel, actual)
        campos = validar(clase, cuerpo, raiz=raiz, hoy=ts[:10], existentes=existentes)
        if clase == "decision":
            reemplazadas = {o.get("reemplaza") for o in existentes if o.get("reemplaza")}
            existentes = [e for e in existentes if e.get("vigente") is not False and e.get("id") not in reemplazadas]
        if clase == "decision":     # una decisión ya anotada en la bitácora (tipo «decision») también cuenta como ya guardada
            existentes = existentes + [e for e in existentes_vigentes(REL_PULIDO, _leer_existente(raiz, REL_PULIDO)) if e.get("tipo") == "decision"]
        if clase == "preferencia":  # lo ya aprobado o rechazado por el dueño también cuenta: no se vuelve a proponer lo que dijo que no
            # Una propuesta ya cerrada en la lista no bloquea (si la aprobó o la rechazó, lo dice el buzón); así, tras revocar una, nuevas correcciones pueden proponerla otra vez.
            existentes = [e for e in existentes if not (e.get("tipo") == "regla_propuesta" and e.get("categoria") == "pref" and e.get("estado") == "resuelta")]
            existentes = existentes + _preferencias_bloqueantes(raiz)
        similares = buscar_similares(campos, existentes)
        if any(s["repetido"] for s in similares) and not permitir_repetido:
            ya = similares[0]
            estado = f", {ya['estado']}" if ya.get("estado") else ""
            raise ErrorCerebro(5, "repetido", f"Ya está guardado como {ya['id']} («{ya['titulo']}», parecido {ya['similitud']}{estado}): no se repite. "
                                              f"Si de verdad es otra cosa, cambia el título o usa --permitir-repetido.")
        identificador = _siguiente_id(rel, objetos)
        if rel == REL_PULIDO:
            linea = {"id": identificador, "ts": ts, "autor": "dueno", "evento": "alta", **campos}
        else:
            linea = {"id": identificador, "ts": ts, "autor": "dueno", **campos}
        return linea, similares

    return _transaccion(raiz, rel, armar, escribir)


# ───────────────────────────────────────── preferencias: aprobar, rechazar, revocar (solo con las palabras del dueño) ─────────────────────────────────────────
def preferencias_vigentes(objetos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Del buzón: las aprobadas por el dueño que nadie revocó después. Una línea con otro autor, otro tipo o sin criterio no cuenta (defensa en profundidad)."""
    revocadas = {o.get("revoca") for o in objetos if o.get("estado") == "revocada" and o.get("autor") == "dueno"}
    return [o for o in objetos if o.get("estado") == "aprobada" and o.get("autor") == "dueno" and o.get("tipo") == "preferencia"
            and isinstance(o.get("criterio"), str) and o.get("id") not in revocadas and o.get("vigente") is not False]


def _preferencias_bloqueantes(raiz: Path) -> list[dict[str, Any]]:
    objetos = _objetos(_leer_existente(raiz, REL_PREFERENCIAS))
    rechazadas = [o for o in objetos if o.get("estado") == "rechazada" and o.get("autor") == "dueno" and isinstance(o.get("criterio"), str)]
    return [{"id": o["id"], "titulo": str(o["criterio"])[:140], "criterio": o["criterio"], "estado": o["estado"]} for o in preferencias_vigentes(objetos) + rechazadas
            if isinstance(o.get("id"), str)]


def resolver_preferencia(cuerpo: Any, *, raiz: Path, escribir: bool = False, ahora: dt.datetime | None = None) -> dict[str, Any]:
    """Registra que el dueño APROBÓ, RECHAZÓ o REVOCÓ una preferencia, con sus palabras. Es la ÚNICA función que escribe «aprobada».

    ``{id: "PUL-0021", estado: "aprobada" | "rechazada", cita}`` sobre una propuesta abierta de la lista única, o
    ``{id: "PRF-0001", estado: "revocada", cita}`` sobre una aprobada. Sin ``escribir`` solo previsualiza. Nada la llama sola: la dispara únicamente la skill
    ``/cerebro-cerrar`` después de que el dueño lo dijo en esta sesión.
    """
    ts = ahora_iso(ahora)
    raiz = Path(raiz)
    if not isinstance(cuerpo, dict):
        raise ErrorCerebro(3, "cuerpo_invalido", "La entrada debe ser un objeto JSON.")
    _revisar_secretos(cuerpo)
    _sin_extras(cuerpo, {"id", "estado", "cita", "origen"})
    estado = _opcion(cuerpo, "estado", ESTADOS_RESOLUCION)
    if estado is None:
        raise ErrorCerebro(3, "campo_invalido", f"El campo estado debe ser uno de: {', '.join(ESTADOS_RESOLUCION)}.")
    cita = _cita(cuerpo.get("cita"), "cita")
    identificador = cuerpo.get("id")
    rx = RX_ID_PRF if estado == "revocada" else RX_ID_PUL
    if not isinstance(identificador, str) or not rx.fullmatch(identificador):
        raise ErrorCerebro(3, "campo_invalido", "Para revocar, id es el PRF-0001 de la preferencia aprobada; para aprobar o rechazar, el PUL-0001 de la propuesta.")
    origen = _origen(cuerpo, ts[:10])

    def armar(actual: bytes) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        objetos = _objetos(actual)
        nuevo_id = _siguiente_id(REL_PREFERENCIAS, objetos)
        if estado == "revocada":
            vigentes = {o["id"]: o for o in preferencias_vigentes(objetos) if isinstance(o.get("id"), str)}
            previa = vigentes.get(identificador)
            if previa is None:
                raise ErrorCerebro(3, "no_vigente", f"{identificador} no es una preferencia aprobada y vigente: no hay nada que revocar.")
            linea = {"id": nuevo_id, "ts": ts, "autor": "dueno", "tipo": "preferencia", "estado": "revocada", "revoca": identificador, "pul_id": previa.get("pul_id"),
                     "etapa": previa.get("etapa"), "criterio": previa["criterio"], "cita": cita, "origen": origen, "vigente": False}
            return {k: v for k, v in linea.items() if v is not None}, []
        propuesta = {e["id"]: e for e in existentes_vigentes(REL_PULIDO, _leer_existente(raiz, REL_PULIDO))}.get(identificador)
        if propuesta is None or propuesta.get("tipo") != "regla_propuesta" or propuesta.get("categoria") != "pref" or not isinstance(propuesta.get("preferencia"), dict):
            raise ErrorCerebro(3, "no_es_propuesta", f"{identificador} no es una preferencia propuesta (regla propuesta de categoría «pref» con su prueba).")
        if propuesta.get("estado") == "resuelta":
            raise ErrorCerebro(3, "no_abierta", f"{identificador} ya está cerrada en la lista única: si cambió de opinión, que se proponga de nuevo con sus correcciones.")
        for o in objetos:
            if o.get("pul_id") == identificador and o.get("estado") in ("aprobada", "rechazada") and o.get("autor") == "dueno":
                raise ErrorCerebro(5, "repetido", f"{identificador} ya fue {o['estado']} como {o.get('id')}: una resolución no se repite.")
        pref = propuesta["preferencia"]
        linea = {"id": nuevo_id, "ts": ts, "autor": "dueno", "tipo": "preferencia", "estado": estado, "pul_id": identificador, "etapa": propuesta.get("etapa"),
                 "oferta_id": propuesta.get("oferta_id"), "criterio": pref.get("criterio"), "alcance": pref.get("alcance"), "n_instancias": pref.get("n"),
                 "respaldo": pref.get("respaldo")}
        if estado == "aprobada":
            linea["instancias"] = pref.get("instancias")
        linea.update({"cita": cita, "origen": origen, "vigente": estado == "aprobada"})
        return {k: v for k, v in linea.items() if v is not None}, []

    return _transaccion(raiz, REL_PREFERENCIAS, armar, escribir)


def listar(raiz: Path, clase: str = "todas", *, solo_abiertas: bool = False) -> dict[str, Any]:
    """Lo ya guardado, compacto (id, título, estado, prioridad…), para no repetirlo. Solo lectura; no crea nada."""
    raiz = Path(raiz)
    salida: dict[str, list[dict[str, Any]]] = {}
    pedidos = {"pendiente": REL_PULIDO, "regla_propuesta": REL_PULIDO, "preferencia": REL_PULIDO, "decision": REL_DECISIONES, "leccion": REL_LECCIONES}
    clases = list(pedidos) if clase == "todas" else [clase]
    for c in clases:
        if c not in pedidos:
            raise ErrorCerebro(2, "uso", f"La clase debe ser todas o una de: {', '.join(CLASES)}.")
        rel = pedidos[c]
        filas = existentes_vigentes(rel, _leer_existente(raiz, rel))
        if c == "preferencia":
            filas = [f for f in filas if f.get("tipo") == "regla_propuesta" and f.get("categoria") == "pref"]
            buzon = _objetos(_leer_existente(raiz, REL_PREFERENCIAS))
            if solo_abiertas:       # abiertas = propuestas sin resolver + aprobadas vigentes (las rechazadas y revocadas ya no cuentan)
                resueltas = {o.get("pul_id") for o in buzon if o.get("estado") in ("aprobada", "rechazada")}
                filas = [f for f in filas if f.get("id") not in resueltas and f.get("estado") != "resuelta"]
                buzon = preferencias_vigentes(buzon)
            filas = filas + [dict(o, titulo=o.get("criterio")) for o in buzon]
        elif rel == REL_PULIDO:
            filas = [f for f in filas if (f.get("tipo") or "pulido") == c or (c == "pendiente" and f.get("tipo") in (None, "pulido", "observacion", "nota", "pendiente"))]
        if c == "decision":
            reemplazadas = {f.get("reemplaza") for f in filas if f.get("reemplaza")}
            filas = [f for f in filas if f.get("vigente") is not False and f.get("id") not in reemplazadas]
            filas += [f for f in existentes_vigentes(REL_PULIDO, _leer_existente(raiz, REL_PULIDO)) if f.get("tipo") == "decision"]
        if solo_abiertas and c != "preferencia":
            filas = [f for f in filas if f.get("estado") != "resuelta"]
        salida[c] = [{k: f.get(k) for k in ("id", "titulo", "estado", "prioridad", "responsable", "vence", "etapa", "oferta_id", "alcance", "confianza", "pul_id") if f.get(k) is not None} for f in filas]
    return {"ok": True, "guardado": salida, "conteo": {k: len(v) for k, v in salida.items()}}


# ───────────────────────────────────────── línea de comandos ─────────────────────────────────────────
def _raiz_por_defecto() -> Path:
    if os.environ.get("FABRICA_RAIZ"):
        return Path(os.environ["FABRICA_RAIZ"])
    for p in Path(__file__).resolve().parents:
        if (p / "empresa").is_dir() and (p / "dashboard").is_dir():
            return p
    return Path.cwd()


def _cargar_entrada(args: argparse.Namespace) -> Any:
    if args.json_texto is not None and args.stdin:
        raise ErrorCerebro(2, "uso", "Usa --json o --stdin, no los dos.")
    if args.json_texto is None and not args.stdin:
        raise ErrorCerebro(2, "uso", "Falta la entrada: --json '{...}' o --stdin.")
    crudo = sys.stdin.read(200_000) if args.stdin else args.json_texto
    if len(crudo) > 100_000:
        raise ErrorCerebro(3, "cuerpo_invalido", "La entrada supera 100 KB.")
    try:
        return json.loads(crudo, parse_constant=_rechazar_constante)
    except ValueError as exc:
        raise ErrorCerebro(3, "cuerpo_invalido", "La entrada no es JSON válido (sin NaN ni Infinity).") from exc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="guardar_pendiente.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("clase", help=f"{', '.join(CLASES)} · {RESOLVER} · listar")
    ap.add_argument("--json", dest="json_texto", default=None, help="la línea como objeto JSON")
    ap.add_argument("--stdin", action="store_true", help="lee el objeto JSON de la entrada estándar (evita problemas de comillas)")
    ap.add_argument("--escribir", action="store_true", help="agrega la línea (sin esto solo se previsualiza)")
    ap.add_argument("--permitir-repetido", action="store_true", help="guarda aunque haya algo parecido ≥ 0,80")
    ap.add_argument("--raiz", default=None, help="raíz del repositorio (defecto: FABRICA_RAIZ o la carpeta del código)")
    ap.add_argument("--clase", dest="clase_listar", default="todas", help="solo con «listar»")
    ap.add_argument("--abiertas", action="store_true", help="solo con «listar»: oculta lo resuelto")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code not in (0, None) else 0
    raiz = Path(args.raiz) if args.raiz else _raiz_por_defecto()
    try:
        if not raiz.is_dir():
            raise ErrorCerebro(2, "uso", "--raiz no es una carpeta.")
        if args.clase == "listar":
            resultado = listar(raiz, args.clase_listar, solo_abiertas=args.abiertas)
        elif args.clase == RESOLVER:
            resultado = resolver_preferencia(_cargar_entrada(args), raiz=raiz, escribir=args.escribir)
        else:
            resultado = guardar(args.clase, _cargar_entrada(args), raiz=raiz, escribir=args.escribir, permitir_repetido=args.permitir_repetido)
    except ErrorCerebro as exc:
        print(json.dumps({"ok": False, "codigo": exc.codigo, "mensaje": exc.mensaje}, ensure_ascii=False), file=sys.stderr)
        return exc.salida
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
