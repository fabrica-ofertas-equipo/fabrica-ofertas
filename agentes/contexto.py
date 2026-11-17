"""``agentes.contexto`` — qué ve el QA de una fuente externa no confiable (docs/09 §10, M12).

D1/D2 leen foros, competidores y la Biblioteca de Anuncios: ese texto es **dato**, nunca
instrucción. El QA no recibe ``crudo/**`` ni el texto completo de la fuente: recibe ``claims`` con
``evidencia.hash_copia_crudo`` y una cita de como mucho 200 caracteres, encerrada entre
``<<DATO_NO_CONFIABLE>> … <<FIN>>`` para que cualquier instrucción incrustada en la cita quede
marcada como dato y no como una orden del sistema. Si la propia fuente intenta falsificar el borde
de la cuarentena (escribiendo ``<<FIN>>`` dentro de su texto para "escapar"), esas marcas se quitan
antes de envolver la cita: la fuente no puede fabricar su propio cierre.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

__all__ = [
    "LARGO_CITA_MAX", "MARCA_FIN", "MARCA_INICIO", "TABLA_ETAPAS", "construir_claim", "construir_claims",
    "contexto_de_etapa", "contiene_ruta_crudo", "exigir_sin_crudo",
]

# Tabla por etapa (docs/06 §4.6: "contexto.py fija por etapa: lecturas, rutas escribibles, scripts
# permitidos, esquema de salida"). PRIMER BORRADOR [HIPÓTESIS]: cubre las etapas Maker<->QA del DAG
# (docs/06 §2); el dueño o quien integre con engine.orq la ajusta sin tocar el resto del runner
# (ver README, «Decisiones»). ``entradas``/``rutas_escribibles`` son PATRONES relativos a
# ``ofertas/<id>/``; el motor los resuelve con el ``oferta_id`` real antes de armar el ``EspecCorrida``.
TABLA_ETAPAS: dict[str, dict[str, Any]] = {
    "D1": {"entradas": ("00-brief.yaml",), "rutas_escribibles": ("D1/.staging/<run_id>/",),
          "scripts_permitidos": ("validar_esquemas.py",), "contrato_salida": "contratos/candidatos.schema.json"},
    "D2": {"entradas": ("D1/.staging/<run_id>/candidatos.json",), "rutas_escribibles": ("D2/.staging/<run_id>/",),
          "scripts_permitidos": ("validar_esquemas.py", "factibilidad.py"), "contrato_salida": "contratos/validacion.schema.json"},
    "D3": {"entradas": ("02-validacion/validacion.json", "03-oferta/economia.json"),
          "rutas_escribibles": ("D3/.staging/<run_id>/",), "scripts_permitidos": ("validar_esquemas.py", "factibilidad.py"),
          "contrato_salida": "contratos/oferta.schema.json"},
    "D4": {"entradas": ("03-oferta/oferta.json",), "rutas_escribibles": ("D4/.staging/<run_id>/",),
          "scripts_permitidos": ("validar_esquemas.py",), "contrato_salida": "contratos/producto.schema.json"},
    "D5": {"entradas": ("03-oferta/oferta.json", "04-producto/producto.json"),
          "rutas_escribibles": ("D5/.staging/<run_id>/",), "scripts_permitidos": ("validar_esquemas.py",),
          "contrato_salida": "contratos/tracking_plan.schema.json"},
    "D6": {"entradas": ("03-oferta/oferta.json",), "rutas_escribibles": ("D6/.staging/<run_id>/",),
          "scripts_permitidos": ("validar_esquemas.py",), "contrato_salida": "contratos/creativos.schema.json"},
    "D7": {"entradas": ("03-oferta/oferta.json", "06-creativos/creativos.json"),
          "rutas_escribibles": ("D7/.staging/<run_id>/",), "scripts_permitidos": ("validar_esquemas.py",),
          "contrato_salida": "contratos/campana.schema.json"},
    "X1": {"entradas": ("<etapa_objetivo>/<artefacto>.json",), "rutas_escribibles": (),
          "scripts_permitidos": ("validar_esquemas.py", "lint_claims.py"), "contrato_salida": "contratos/qa.schema.json"},
}


def contexto_de_etapa(etapa: str) -> dict[str, Any]:
    """Entradas/rutas escribibles/scripts/esquema de salida de ``etapa`` (copia; ``KeyError`` si no está en la tabla)."""
    return dict(TABLA_ETAPAS[etapa])

MARCA_INICIO = "<<DATO_NO_CONFIABLE>>"
MARCA_FIN = "<<FIN>>"
LARGO_CITA_MAX = 200

# Lo único de "evidencia" que puede llegar al QA: nunca el texto crudo ni su ruta en crudo/**.
_CAMPOS_EVIDENCIA_PERMITIDOS = ("hash_copia_crudo", "url", "fecha_captura", "fuente_id")


def _sanear_cita(texto: str) -> str:
    """Quita marcas de cuarentena literales del texto de origen y lo trunca a ``LARGO_CITA_MAX``."""
    limpio = str(texto).replace(MARCA_INICIO, "").replace(MARCA_FIN, "")
    return limpio[:LARGO_CITA_MAX]


def contiene_ruta_crudo(valor: Any) -> bool:
    """¿``valor`` (recorrido recursivamente si es mapa/lista) menciona una ruta bajo ``crudo/``?

    Red de seguridad para verificar, en pruebas o antes de armar el encargo del QA, que ningún
    campo apunta a datos crudos sin pasar por :func:`construir_claim`.
    """
    if isinstance(valor, str):
        return "crudo/" in valor
    if isinstance(valor, Mapping):
        return any(contiene_ruta_crudo(v) for v in valor.values())
    if isinstance(valor, (list, tuple)):
        return any(contiene_ruta_crudo(v) for v in valor)
    return False


def exigir_sin_crudo(entradas: Sequence[str]) -> None:
    """``ValueError`` si alguna ruta de ``entradas`` (las que recibe un QA) cae bajo ``crudo/``."""
    malas = [e for e in entradas if contiene_ruta_crudo(e)]
    if malas:
        raise ValueError(f"el QA no puede recibir rutas bajo crudo/**: {malas}")


def construir_claim(crudo: Mapping[str, Any]) -> dict[str, Any]:
    """Un ``claim`` seguro para el QA a partir de un hallazgo de D1/D2 sobre una fuente externa.

    ``crudo`` trae al menos ``cita`` (texto NO CONFIABLE) y ``evidencia.hash_copia_crudo``. El
    resultado nunca incluye el texto completo de la fuente, su ruta cruda, ni ningún campo de
    ``evidencia`` fuera de la lista blanca. ``ValueError`` si falta la cita o el hash de evidencia.
    """
    if not isinstance(crudo, Mapping):
        raise ValueError("construir_claim exige un mapa")
    cita = crudo.get("cita")
    if not isinstance(cita, str) or not cita.strip():
        raise ValueError("construir_claim exige una «cita» de texto no vacía")
    evidencia_cruda = crudo.get("evidencia") if isinstance(crudo.get("evidencia"), Mapping) else {}
    evidencia = {k: v for k, v in evidencia_cruda.items() if k in _CAMPOS_EVIDENCIA_PERMITIDOS}
    if not evidencia.get("hash_copia_crudo"):
        raise ValueError("construir_claim exige evidencia.hash_copia_crudo (nunca el texto crudo en sí)")
    claim_id = crudo.get("claim_id") or crudo.get("senal_id")
    if not claim_id:
        raise ValueError("construir_claim exige claim_id o senal_id")
    return {
        "claim_id": str(claim_id),
        "cita": f"{MARCA_INICIO} {_sanear_cita(cita)} {MARCA_FIN}",
        "evidencia": evidencia,
    }


def construir_claims(crudos: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Lista de :func:`construir_claim`, en el mismo orden que ``crudos``."""
    return [construir_claim(c) for c in crudos]
