"""``GET /api/robots``: el registro de robots (solo lectura; alimenta la pestaña «Registro» de ``#/robots``).

Devuelve ``empresa/robots.yaml`` tal como esté, saneado: sin escribir nada, sin lanzar por un archivo ausente o corrupto y con
topes de profundidad, de cantidad y de largo de texto (el contenido de los archivos es DATO no confiable; el cliente lo muestra
siempre como texto). El formato del archivo aún no está fijado por contrato (lo definirá el marco de robots): el cliente lo
normaliza con tolerancia, así que aquí no se interpreta, solo se acota. Si el archivo no existe, ``vacio: true``.

``GET /api/robots/sombra`` (solo lectura): la foto de los robots EN SOMBRA (``empresa/robots/estado.json``, que deja ``python -m scripts.robots.sombra … --escribir``), saneada
y con el vencimiento recalculado con la hora de ahora (``dashboard/robots_sombra.py``). Los robots en sombra miran y proponen; no son el sistema real. Si no hay foto,
``vacio: true`` con el comando para generarla. Es una ruta aparte para no tocar la forma de ``/api/robots``.
"""
from __future__ import annotations

from typing import Any

from dashboard.api_base import Ctx, Sobre
from dashboard.robots_sombra import COMANDOS, REL_ESTADO, leer_sombra

__all__ = ["robots", "sombra", "REL_ROBOTS"]

REL_ROBOTS = "empresa/robots.yaml"
_MAX_PROFUNDIDAD = 5
_MAX_ELEMENTOS = 200          # por lista o mapa
_MAX_TEXTO = 400


def _sanear(valor: Any, nivel: int = 0) -> Any:
    """Copia acotada de un valor YAML: escalares tal cual (texto recortado), listas y mapas con tope, sin objetos raros."""
    if isinstance(valor, bool) or valor is None:
        return valor
    if isinstance(valor, (int, float)):
        return valor
    if isinstance(valor, str):
        return valor[:_MAX_TEXTO]
    if nivel >= _MAX_PROFUNDIDAD:
        return None
    if isinstance(valor, (list, tuple)):
        return [_sanear(v, nivel + 1) for v in list(valor)[:_MAX_ELEMENTOS]]
    if isinstance(valor, dict):
        salida: dict[str, Any] = {}
        for k, v in list(valor.items())[:_MAX_ELEMENTOS]:
            salida[str(k)[:80]] = _sanear(v, nivel + 1)
        return salida
    return str(valor)[:_MAX_TEXTO]      # fechas YAML y demás: texto


def robots(ctx: Ctx) -> Sobre:
    """``{robots: …}`` con el contenido saneado de ``empresa/robots.yaml``; vacío (con aviso) si aún no existe."""
    lectura = ctx.empresa().yaml("robots.yaml")
    if lectura.estado == "ausente":
        return Sobre({}, [REL_ROBOTS], vacio=True,
                     avisos=["Todavía no existe el registro de robots. Lo va a definir el marco de robots (archivo empresa/robots.yaml; ver mapeo.md §10)."])
    avisos: list[str] = []
    if not lectura.ok:
        avisos.append(lectura.aviso or f"No se pudo entender el contenido del registro de robots ({REL_ROBOTS}).")
        return Sobre({}, [REL_ROBOTS], vacio=True, avisos=avisos)
    return Sobre(_sanear(lectura.dato), [REL_ROBOTS], vacio=False, avisos=avisos)


def sombra(ctx: Ctx) -> Sobre:
    """``{existe, generado_en, edad_min, de_hoy, situacion, robots[], trabajos[], resumen, auditoria, avisos, comandos}`` de los robots en sombra; vacío si aún no hay foto."""
    datos, avisos = leer_sombra(ctx)
    if datos is None:
        avisos = list(avisos) or [
            "Todavía no corrió ningún robot en sombra con la opción de guardar, así que no hay foto de su estado "
            f"({REL_ESTADO}). Se genera con el comando `{COMANDOS['escribir']}`; para probar sin guardar nada: `{COMANDOS['simular']}`."]
        return Sobre({"existe": False, "comandos": COMANDOS}, [REL_ESTADO], vacio=True, avisos=avisos)
    return Sobre(datos, [REL_ESTADO], vacio=False, avisos=avisos)
