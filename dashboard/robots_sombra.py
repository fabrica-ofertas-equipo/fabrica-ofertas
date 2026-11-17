"""Lectura SANEADA del estado de los robots en sombra (``empresa/robots/estado.json``): solo lectura, la usan ``GET /api/robots/sombra`` y el semáforo.

Qué es: ``python -m scripts.robots.sombra ejecutar --escribir`` (o ``estado --escribir``) deja una FOTO del día (qué robots en sombra corrieron, cuáles faltan, qué latidos
están vencidos). Los robots en sombra son de solo lectura y propuesta: **no son el sistema real** (planificador, reintentos, guard) que construye S-B. Por eso nada de lo
que se lea acá debe dar por bueno el planificador: el panel y el semáforo lo muestran aparte y nunca lo cuentan como «hay planificador».

Reglas de esta lectura (las mismas de todo el panel):

* el contenido del archivo es DATO no confiable: solo pasan claves conocidas, con su tipo, su vocabulario y su largo acotados; el texto se limpia de controles y enlaces;
* la foto NO se da por vigente: «vencido» y «corrió hoy» se RECALCULAN con la hora de ahora (una foto de hace tres días no dice «al día»); lo que depende del día de la foto
  (``faltan_hoy``) solo se informa si la foto es de hoy;
* nada de ``float`` ni de claves que el panel no conozca; tope de tamaño del archivo (256 KB) y de filas (24 robots, 24 trabajos);
* si falta, está dañado o no tiene la forma esperada, devuelve ``None`` con un aviso: nunca inventa un estado.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dashboard.api_base import Ctx

__all__ = [
    "COMANDOS", "REL_ESTADO", "RESULTADOS", "SITUACIONES", "leer_sombra", "limpiar",
]

REL_ESTADO = "empresa/robots/estado.json"
TOPE_ARCHIVO = 256 * 1024
MAX_ROBOTS = 24
MAX_TRABAJOS = 24
MAX_IDS = 24
ESTADOS_LATIDO = ("al_dia", "vencido", "manual", "sin_latido", "apagado", "no_aplica")
RESULTADOS = ("ok", "parcial", "sin_datos", "sin_decidir", "alerta", "error")
SITUACIONES = ("sin_programar", "corriendo", "vencido")
# Comandos que el panel MUESTRA (copiables; los ejecuta una persona). `programar` solo imprime: instalarlo es decisión del dueño.
COMANDOS = {
    "estado": ".venv/bin/python -m scripts.robots.sombra estado",
    "simular": ".venv/bin/python -m scripts.robots.sombra ejecutar --todos --simular",
    "escribir": ".venv/bin/python -m scripts.robots.sombra ejecutar --todos --escribir",
    "programar": ".venv/bin/python -m scripts.robots.sombra programar",
}
_RX_ID = re.compile(r"^[a-z][a-z0-9_]{0,23}$")
_RX_ZONA = re.compile(r"^[A-Za-z][A-Za-z_+-]*(?:/[A-Za-z0-9_+-]+){0,2}$")
_RX_URL = re.compile(r"(?i)\b(?:https?|ftp)://\S+|\bwww\.\S+")
_RX_CONTROL = re.compile(r"[\x00-\x1f\x7f‪-‮⁦-⁩]")
_RX_CLAVE_METRICA = re.compile(r"^[a-z][a-z0-9_]{0,29}$")
_ENTERO_MAX = 10**9


def limpiar(valor: Any, maximo: int) -> str:
    """Texto de un archivo → una línea sin controles, sin marcas de dirección ni enlaces, recortada. Lo no textual → ``""``."""
    if not isinstance(valor, str):
        return ""
    t = _RX_URL.sub("[enlace]", valor)
    t = _RX_CONTROL.sub(" ", t)
    t = " ".join(t.split())
    return t if len(t) <= maximo else t[: maximo - 1].rstrip() + "…"


def _t(valor: Any) -> _dt.datetime | None:
    if not isinstance(valor, str) or len(valor) > 40:
        return None
    try:
        t = _dt.datetime.fromisoformat(valor.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=_dt.timezone.utc)
    return t.astimezone(_dt.timezone.utc)


def _iso(t: _dt.datetime | None) -> str | None:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ") if t is not None else None


def _entero(v: Any, minimo: int = 0) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) and minimo <= v <= _ENTERO_MAX else None


def _zona(nombre: Any) -> tuple[Any, str]:
    """``(tzinfo, nombre)``: la zona declarada en la foto si es válida; si no, UTC."""
    if isinstance(nombre, str) and _RX_ZONA.match(nombre) and len(nombre) <= 40:
        try:
            return ZoneInfo(nombre), nombre
        except (ZoneInfoNotFoundError, ValueError, OSError):
            pass
    return _dt.timezone.utc, "UTC"


def _ids(v: Any, validos: set[str] | None = None) -> list[str]:
    if not isinstance(v, list):
        return []
    salida = [x for x in v if isinstance(x, str) and _RX_ID.match(x) and (validos is None or x in validos)]
    return list(dict.fromkeys(salida))[:MAX_IDS]


def _fila(r: dict[str, Any], ahora: _dt.datetime, tz: Any, hoy_ahora: str) -> dict[str, Any] | None:
    if not isinstance(r.get("id"), str) or not _RX_ID.match(r["id"]):
        return None
    estado = r.get("estado_latido") if r.get("estado_latido") in ESTADOS_LATIDO else "desconocido"
    esperado = r.get("esperado") is True
    maximo = _entero(r.get("latido_max_min"), 1)
    ultimo = _t(r.get("ultimo_latido"))
    edad = max(0, int((ahora - ultimo).total_seconds() // 60)) if ultimo is not None else None
    vencido_foto = r.get("vencido") is True
    vencido_ahora = bool(esperado and maximo and edad is not None and edad > maximo)
    vencido = vencido_foto or vencido_ahora
    motivo = limpiar(r.get("motivo"), 200)
    if vencido_ahora and not vencido_foto:
        motivo = f"último latido hace {edad} min (máximo {maximo}); la foto lo daba al día"
    if vencido and estado == "al_dia":
        estado = "vencido"          # la foto decía «al día»; con la hora de ahora ya no lo está
    metricas: dict[str, int] = {}
    if isinstance(r.get("metricas"), dict):
        for k, v in list(r["metricas"].items())[:8]:
            if isinstance(k, str) and _RX_CLAVE_METRICA.match(k) and _entero(v, -_ENTERO_MAX) is not None:
                metricas[k] = v
    corrio_hoy = bool(ultimo is not None and ultimo.astimezone(tz).date().isoformat() == hoy_ahora)
    return {
        "id": r["id"], "nombre": limpiar(r.get("nombre"), 80) or r["id"], "tipo": r.get("tipo") if r.get("tipo") in ("robot", "apoyo") else "robot",
        "horario": limpiar(r.get("horario"), 60), "ejecutor_hoy": "sombra" if r.get("ejecutor_hoy") == "sombra" else "ninguno", "estado_latido": estado,
        "esperado": esperado, "vencido": vencido, "motivo": motivo, "ultimo_latido": _iso(ultimo),
        "ultimo_resultado": r.get("ultimo_resultado") if r.get("ultimo_resultado") in RESULTADOS else None, "ultima_razon": limpiar(r.get("ultima_razon"), 200),
        "edad_min": edad, "latido_max_min": maximo, "corrio_hoy": corrio_hoy, "debia_correr_hoy": r.get("debia_correr_hoy") is True, "metricas": metricas,
    }


def leer_sombra(ctx: Ctx) -> tuple[dict[str, Any] | None, list[str]]:
    """``(estado saneado | None, avisos)``. ``None`` si la foto no existe (sin aviso) o no se puede usar (con aviso). Nunca lanza."""
    lec = ctx.raiz_confinada.json(REL_ESTADO, tope=TOPE_ARCHIVO)
    if lec.estado == "ausente":
        return None, []
    d = lec.dato
    if not lec.ok or not isinstance(d, dict) or d.get("tipo") != "estado_robots" or not isinstance(d.get("robots"), list):
        return None, [lec.aviso or f"El estado de los robots en sombra ({REL_ESTADO}) no tiene la forma esperada; se ignora."]
    ahora = ctx.ahora().astimezone(_dt.timezone.utc)
    tz, zona_hoy = _zona(d.get("zona_hoy"))
    hoy_ahora = ahora.astimezone(tz).date().isoformat()
    generado = _t(d.get("generado_en"))
    de_hoy = d.get("hoy") == hoy_ahora
    filas = [f for f in (_fila(r, ahora, tz, hoy_ahora) for r in d["robots"][:MAX_ROBOTS] if isinstance(r, dict)) if f is not None]
    con_sombra = [f["id"] for f in filas if f["ejecutor_hoy"] == "sombra" and f["estado_latido"] != "apagado"]
    esperados = [f["id"] for f in filas if f["esperado"]]
    vencidos = [f["id"] for f in filas if f["vencido"]]
    if vencidos:
        situacion = "vencido"
    elif not esperados:
        situacion = "sin_programar"
    else:
        situacion = "corriendo"
    avisos_foto = [limpiar(a, 200) for a in (d.get("avisos") if isinstance(d.get("avisos"), list) else [])[:5] if isinstance(a, str)]
    trabajos = []
    for t in (d.get("trabajos") if isinstance(d.get("trabajos"), list) else [])[:MAX_TRABAJOS]:
        if isinstance(t, dict) and isinstance(t.get("id"), str) and _RX_ID.match(t["id"]):
            trabajos.append({"id": t["id"], "ultimo_latido": _iso(_t(t.get("ultimo_latido"))), "latido_max_min": _entero(t.get("latido_max_min"), 1), "modo": "sombra"})
    aud = None
    if isinstance(d.get("auditoria"), dict):
        aud = {k: v for k, v in d["auditoria"].items() if isinstance(k, str) and _RX_CLAVE_METRICA.match(k) and _entero(v, -_ENTERO_MAX) is not None}
        aud = aud or None
    resumen_foto = d.get("resumen") if isinstance(d.get("resumen"), dict) else {}
    ids = {f["id"] for f in filas}
    corrieron = [f["id"] for f in filas if f["corrio_hoy"]]
    datos = {
        "existe": True, "generado_en": _iso(generado), "edad_min": max(0, int((ahora - generado).total_seconds() // 60)) if generado is not None else None, "de_hoy": de_hoy,
        "hoy": hoy_ahora, "zona_hoy": zona_hoy, "situacion": situacion, "robots": filas, "trabajos": trabajos, "auditoria": aud, "avisos": avisos_foto,
        "resumen": {
            "con_sombra": con_sombra, "esperados": esperados, "vencidos": vencidos, "corrieron_hoy": corrieron,
            # «faltan hoy» y «solo a mano» dependen del día de la foto: solo se informan si la foto es de hoy
            "faltan_hoy": _ids(resumen_foto.get("faltan_hoy"), ids) if de_hoy else [], "solo_manual": _ids(resumen_foto.get("solo_manual"), ids),
            "sin_arrancar": _ids(resumen_foto.get("sin_arrancar"), ids), "sin_version": [f["id"] for f in filas if f["estado_latido"] == "no_aplica" or f["ejecutor_hoy"] != "sombra"],
        },
        "comandos": COMANDOS,
    }
    return datos, []
