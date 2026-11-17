"""``cerrar``: fase final de la oferta y post-mortem mínimo (N17 «O0 Cierre», docs/06 §2 y §5).

Lee ``08-operacion/veredicto_oferta.json`` (lo escribe ``engine.d8.veredicto``, de otra sesión) y:

1. mueve ``fase`` a ``validada``, ``fallida`` o ``inconclusa`` según ``veredicto.estado`` (vía
   ``engine.estado.transicionar_fase``); ``PROMETEDORA`` no es una fase (docs/06 D-11): la oferta
   sigue ``en_test`` y esta función se niega a cerrar (``ErrorBloqueado``);
2. escribe ``08-operacion/postmortem.json`` (obligatorio, incl. ``retraso_clic_compra``);
3. con ``VALIDADA``, deja una nota para D9 (``09-escalado/propuesta-d9.md``) SIN ejecutar nada (D9
   queda fuera de este alcance).

Genérico a propósito (B0, modo prueba): sin un Maker de cierre todavía (docs/06 §7.3), el
post-mortem que se genera aquí es un borrador mínimo y determinista a partir de la evidencia del
veredicto; el dueño lo revisa y lo completa a mano. «La fase final no se reescribe» (docs/06 §5):
llamar de nuevo sobre una oferta ya cerrada es un no-op que devuelve el post-mortem existente.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from engine import comun, estado
from engine.errores import ErrorBloqueado, ErrorValidacion

__all__ = ["cerrar_oferta"]

# veredicto_oferta.estado -> fase final de estado.json (docs/contratos.md §3; PROMETEDORA no es una fase, docs/06 D-11)
_FASE_FINAL = {"VALIDADA": "validada", "FALLIDA": "fallida", "INCONCLUSA": "inconclusa"}
# Causa principal genérica por veredicto (kebab-case): un Maker de cierre la afina con evidencia real.
_CAUSA_PRINCIPAL = {
    "VALIDADA": "cpa-bajo-el-objetivo", "FALLIDA": "cpa-sobre-el-equilibrio", "INCONCLUSA": "datos-insuficientes-al-tope",
}
_NIVEL_EVIDENCIA_GENERICO = "hipotesis"  # generado por código, sin diagnóstico humano todavía (fail-closed y honesto)


def _retraso_clic_compra_generico() -> dict:
    """Sin un cruce Stripe↔evento de clic disponible en este alcance: ``no_medible`` (fail-closed, nunca se inventa una cifra)."""
    return {"n_compras": 0, "mediana_h": None, "p90_h": None, "fuente": "no_medible"}


def _postmortem_generico(oferta_id: str, veredicto_doc: Mapping[str, Any], *, veredicto_sha256: str,
                         generado_en: str) -> dict:
    estado_v = veredicto_doc["estado"]
    return {
        "schema_version": "1.0.0",
        "oferta_id": oferta_id,
        "generado_en": generado_en,
        # Ningún valor del enumerado (maker|qa|humano) describe «generado por código determinista sin
        # Maker todavía»; "maker" es el menos inexacto (un borrador que el dueño revisa), nunca "humano"
        # (nadie lo escribió a mano). Documentado en el README del componente («Decisiones»).
        "origen_version": "maker",
        "veredicto": estado_v,
        "veredicto_sha256": veredicto_sha256,
        "causa_principal": _CAUSA_PRINCIPAL[estado_v],
        "causas": [{
            "codigo": _CAUSA_PRINCIPAL[estado_v],
            "descripcion": f"Veredicto {estado_v} calculado por engine.d8 sobre la evidencia de Stripe (ver regla en veredicto_oferta.json).",
            "nivel_evidencia": _NIVEL_EVIDENCIA_GENERICO,
        }],
        "aprendizajes": [],
        "parametros_a_calibrar": [],
        "retraso_clic_compra": _retraso_clic_compra_generico(),
    }


def _leer_json_si_existe(ruta: Path) -> dict | None:
    try:
        return comun.cargar_json(ruta)
    except FileNotFoundError:
        return None


def cerrar_oferta(oferta_id: str, *, raiz: Path | None = None, ahora: Callable[[], datetime] = comun.ahora_utc,
                  actor: str = "motor") -> dict:
    """Cierra ``oferta_id``: fase final + post-mortem (y, si ``VALIDADA``, nota para D9).

    Idempotente: si la fase ya es la final correspondiente al veredicto vigente, no la reescribe
    (devuelve el post-mortem ya existente, ``reutilizado=True``). Errores: ``ErrorBloqueado`` (4) si
    falta ``veredicto_oferta.json`` o el veredicto es ``PROMETEDORA`` (la oferta sigue ``en_test``, no
    se cierra); ``ErrorValidacion`` (3) si el veredicto o el post-mortem generado no cumplen su esquema.
    """
    base = raiz or comun.raiz()
    ruta_veredicto = base / "ofertas" / oferta_id / "08-operacion" / "veredicto_oferta.json"
    try:
        veredicto_doc = comun.cargar_json(ruta_veredicto)
    except FileNotFoundError as exc:
        raise ErrorBloqueado("sin 08-operacion/veredicto_oferta.json no se puede cerrar la oferta (lo escribe engine.d8.veredicto)") from exc
    errores = comun.errores_de_esquema("veredicto_oferta", veredicto_doc)
    if errores:
        raise ErrorValidacion(f"veredicto_oferta.json inválido: {comun.resumir_errores_esquema(errores)}")
    estado_v = veredicto_doc["estado"]
    fase_final = _FASE_FINAL.get(estado_v)
    if fase_final is None:
        raise ErrorBloqueado(f"veredicto {estado_v}: la oferta sigue en_test (PROMETEDORA no es una fase, docs/06 D-11); nada que cerrar todavía")

    ruta_postmortem = base / "ofertas" / oferta_id / "08-operacion" / "postmortem.json"
    est = estado.cargar(oferta_id, raiz=raiz)
    if est["fase"] == fase_final:
        existente = _leer_json_si_existe(ruta_postmortem)
        if existente is not None:
            return {"oferta_id": oferta_id, "fase": fase_final, "reutilizado": True, "postmortem": existente}

    estado.transicionar_fase(oferta_id, fase_final, actor=actor, causa=f"veredicto {estado_v}", raiz=raiz, ahora=ahora)
    generado_en = comun.iso_z(comun.instante(ahora))
    post = _postmortem_generico(oferta_id, veredicto_doc, veredicto_sha256=comun.hash_archivo(ruta_veredicto), generado_en=generado_en)
    errores_post = comun.errores_de_esquema("postmortem", post)
    if errores_post:
        raise ErrorValidacion(f"post-mortem generado no cumple su esquema: {comun.resumir_errores_esquema(errores_post)}")
    comun.escribir_atomico(ruta_postmortem, comun.json_canonico(post))
    if estado_v == "VALIDADA":
        _escribir_nota_d9(base, oferta_id, generado_en)
    return {"oferta_id": oferta_id, "fase": fase_final, "reutilizado": False, "postmortem": post}


def _escribir_nota_d9(base: Path, oferta_id: str, generado_en: str) -> None:
    """Nota para D9 (sin ejecutar nada: D9/escalado queda fuera de este alcance, ``plan.json`` sigue diferido
    y sin esquema propio, docs/contratos.md §1)."""
    ruta = base / "ofertas" / oferta_id / "09-escalado" / "propuesta-d9.md"
    texto = (
        f"# Propuesta para D9 — {oferta_id}\n\n"
        f"Generada por `engine.cerrar` el {generado_en}.\n\n"
        "La oferta quedó `VALIDADA` (ver `08-operacion/veredicto_oferta.json` y `postmortem.json`). "
        "D9 (escalado) está fuera del alcance de este motor; esta nota es solo un registro de que hay "
        "una propuesta pendiente de revisar, sin ejecutar ningún aumento de presupuesto ni clon.\n"
    )
    comun.escribir_atomico(ruta, texto.encode("utf-8"))
