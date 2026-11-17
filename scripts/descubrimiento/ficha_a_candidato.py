"""Puerta de entrada a `candidatos.json` (interfaces d1-v2 §3.8 y §3.8.1, 12 reglas).

Mapea una ficha `2.0.0` del Modo D (ya puntuada por `scripts.modelado.puntaje_modelar`) + el juicio del
Maker (macro, riesgo, mecanismo, entregable, evidencia -- lo que §3.8 marca "no lo da el Modo D") a UN
candidato de `candidatos.json` (esquema vigente **1.0.0**: construye contra ese esquema; los campos
nuevos de la MINOR 1.1.0 -- `subnivel`, `ejes_codigo`, `version_tabla`, `origen`, `sello_reglas`,
`modo_busqueda` -- viajan por candidato en un **sidecar** aparte (`<salida>.sidecar-1.1.0.json`, clave
`candidato_id`) que **no** se valida contra el esquema 1.0.0 y que CT debe aprobar (pedido §8.1 n.1 de
`docs/_historial/d1-v2-interfaces.md`); `sello_reglas` y `modo_busqueda` A NIVEL DOCUMENTO sí viajan en
`candidatos.json#parametros_usados` (ese campo es abierto en 1.0.0).

Orígenes de parámetros (defecto D1d n.2c: ningún archivo real junta `modelado_*` y `sim_dup_bloqueo`):
sin `--parametros`, el CLI resuelve cada uno por su hogar real bajo `--raiz`
(:func:`parametros_descubrimiento_reales`) -- `sim_dup_bloqueo` de `empresa/parametros.yaml` siempre;
`modelado_*` de ahí si ya están integrados, si no del respaldo
`scripts/modelado/parametros_modelado.propuesta.yaml`. `--parametros` sigue existiendo para pruebas y
diagnóstico con un único YAML fixture que los junta a mano.

La regla 5 (sin servicio/comunidad/en vivo) detecta **negación por ventana** sobre el texto libre
("sin comunidad" no veta; "incluye comunidad" sí) comparando formas compactadas (sin tildes, espacios
ni guiones) para resistir ofuscación simple; ante texto "mixto" (una mención negada y otra afirmada)
sigue vetando -- fail-closed. Si el juicio trae el campo estructurado opcional
`entregable_estructura.{servicio,comunidad_o_en_vivo}` en `true`, ese veredicto manda sobre el texto.

Las 12 reglas de §3.8.1, una función por regla (``_regla_N_...``), en orden; la primera que falla
decide el destino del par:

* ``estado_par = "pasa"``       -- las 12 reglas pasan: hay ``candidato`` listo para `candidatos.json`.
* ``estado_par = "incompleta"`` -- falta un dato (nunca se inventa): el par vuelve a
  ``pares_modelado[]`` del problema con su ``pendiente[]``; **no** se escribe nada.
* ``estado_par = "no_pasa"``    -- PM bajo el umbral, riesgo sobre `nivel_max_lanzable`, duplicado
  sobre el umbral o sin prueba de una frase (MU/EU): tampoco se escribe nada, pero no hay motivo
  canónico que registrar en `rechazos.jsonl` (regla 11).
* ``estado_par = "vetada"``     -- una puerta dura (G) está en ``true``. Si el motivo tiene nombre en
  `comunes#motivo_rechazo` (`dependencia_de_marca_personal`, `sustituto_gratis_dominante`,
  `fuera_de_macro_nicho`, `claim_de_salud_o_ingresos`, `requiere_servicio`,
  `requiere_comunidad_o_en_vivo`) se devuelve también para que el llamador lo anexe a
  `rechazos.jsonl` (§2.4); si no (p. ej. `practica_vetada` por clonar landing o testimonios
  inventados -- `linea_roja_de_contenido_o_negocio` **no existe todavía** en `comunes#motivo_rechazo`,
  pedido a CT §8.1 n.2), ``motivo`` queda en ``None`` y el par solo conserva su ``estado_par``
  (regla 11, último inciso).

Nunca escribe nada por sí sola: el CLI (`mapear`) es quien junta varios pares en un `candidatos.json`,
valida el documento ENTERO contra `contratos/candidatos.schema.json` (regla 10) y recién entonces
escribe, o no escribe nada si hay un solo error. Sin red, sin LLM, dry-run (solo lee); `--aplicar`
hace falta para anexar líneas a `rechazos.jsonl` y escribir `candidatos.json`.

Uso::

    python -m scripts.descubrimiento.ficha_a_candidato mapear pares.json --raiz . \\
        --oferta-id OF-202611-01 --corrida-id RUN-20261106-01 --locale es-MX --paises MX \\
        --salida candidatos.json [--modo-busqueda D] [--aplicar] [--json]
    # Pruebas/diagnóstico con un YAML fixture que junta modelado_* y sim_dup_bloqueo:
    python -m scripts.descubrimiento.ficha_a_candidato mapear pares.json --parametros P.yaml \\
        --oferta-id OF-202611-01 --corrida-id RUN-20261106-01 --locale es-MX --paises MX \\
        --salida candidatos.json [--aplicar] [--json]

Contrato de ``pares.json`` -- ``{"schema_version": "1.0.0", "pares": [ ... ]}``, cada elemento::

    {
      "ficha": { ... una "oferta" de scripts.modelado.puntaje_modelar, con exactamente
                 UN mercado (el destino de este candidato); "macro_nicho" SIEMPRE null aquí: lo fija
                 este módulo, nunca el barrido (regla 2) ... },
      "problema_id": "PRB-202611-0001",
      "nicho_id": "kit-de-arranque", "microsegmento": "plantillas-de-presupuesto",
      "juicio": {
        "prueba_una_frase": "de ... a ...", "problema": "...", "tesis": "...",
        "senal_id_e3": "<12 hex>" | null, "cita_e3": "..." (opcional),
        "ejes": {"P": "P1", "C": "C1", "E": "E0", "N": "N1"},
        "zona_gris": false, "hay_reencuadre": false,
        "practica_vetada_causa": "promesa_salud_o_ingresos" | "linea_roja_contenido_o_negocio" | null,
        "riesgo_fuentes": ["..."], "riesgo_categoria": "...", "riesgo_claims_a_evitar": ["..."],
        "riesgo_angulo_seguro": "...",
        "mecanismo": { ...campos de candidatos.schema.json#mecanismo... },
        "entregable": { ...campos de candidatos.schema.json#entregable... },
        "evidencia": [ {"id": "EV-01", "tipo": "E3", "locale": "es-MX", ...} ],
        "similitud_memoria": {"max": "0.10", "con": null},
        "precio_plausible": {"min": {...}, "max": {...}, "razon": "..."},
        "ventana_estacional": null, "hipotesis_para_d2": [], "que_la_mataria": [],
        "palabras_clave_voz_cliente": []
      }
    }

Códigos de salida (convenciones §8): 0 ok · 2 uso · 3 validación (incluye "0 candidatos pasaron" si se
pidió `--exigir-alguno`) · 5 falta `scripts.nivel_riesgo` o un parámetro crítico (falla cerrado).
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from datetime import datetime

from engine.comun import ahora_utc, anexar_jsonl, ejecutar_cli, escribir_atomico, iso_z, raiz as raiz_repositorio
from engine.errores import ErrorFabrica, ErrorLimite, ErrorUso, ErrorValidacion
from scripts import nivel_riesgo
from scripts.descubrimiento import macro as macro_mod
from scripts.modelado import puntaje_modelar as pm
from scripts.validar_esquemas import errores_de_esquema, json_canonico

# Motivos canónicos que YA existen en `comunes#motivo_rechazo` (contratos/comunes.schema.json).
# `linea_roja_de_contenido_o_negocio`, `duplicado_de_la_memoria`, `evidencia_insuficiente` e
# `inviable_sin_backend` son pedidos pendientes a CT (interfaces §7, §8.1 n.2); hasta que existan,
# un par que caería ahí queda `vetada`/`no_pasa` SIN motivo canónico (regla 11, último inciso).
MOTIVOS_CANONICOS_DISPONIBLES = (
    "sin_mecanismo", "multi_mecanismo", "requiere_servicio", "requiere_comunidad_o_en_vivo",
    "no_producible_o_sin_licencia", "sustituto_gratis_dominante", "claim_de_salud_o_ingresos",
    "dependencia_de_marca_personal", "mercado_demasiado_estrecho", "fuera_de_macro_nicho",
)
REDENCION_POR_MOTIVO: dict[str, str] = {
    "sin_mecanismo": "reformular", "multi_mecanismo": "dividir", "requiere_servicio": "descartar",
    "requiere_comunidad_o_en_vivo": "reformular", "no_producible_o_sin_licencia": "bajar_al_banco",
    "sustituto_gratis_dominante": "bajar_al_banco", "claim_de_salud_o_ingresos": "reformular",
    "dependencia_de_marca_personal": "descartar", "mercado_demasiado_estrecho": "bajar_al_banco",
    "fuera_de_macro_nicho": "reformular",
}
_RECHAZO_VIGENTE_DIAS = 90  # interfaces §7, tabla "Vigente" (todas las filas con redención a 90 días)

_FRASES_COMUNIDAD_O_VIVO = ("comunidad", "en vivo", "mentoria en vivo")
_FRASES_SERVICIO = ("suscripcion", "mensualidad", "servicio humano", "coaching 1 a 1",
                   "acompanamiento personalizado")
_FORMATOS_ENTREGABLE = (
    "guia_pdf", "plantilla", "biblioteca", "hoja_de_calculo", "checklist", "minicurso_video_corto", "pack",
)
_RX_NOMBRE_MECANISMO_PALABRAS = re.compile(r"\S+")

# Defecto D1d n.2b: la regla 5 vetaba por la palabra literal "comunidad" aunque estuviera negada
# ("sin comunidad"). Detección de negación por ventana (es/en/it/pl/ro/fr/de: sin, no incluye,
# without, no, senza, bez, fără, sans, ohne) comparando formas "compactadas" (sin tildes, espacios
# ni guiones) para resistir ofuscación simple ("co-munidad", "co munidad"). Si existe al menos una
# mención SIN negación inmediatamente antes (texto "mixto": una negada y otra afirmada), se trata
# como afirmada: fail-closed ante ambigüedad. Cuando el entregable trae un campo estructurado
# explícito (``juicio.entregable_estructura``, aditivo propio de D1, no del esquema 1.0.0) se usa
# ese veredicto en vez del texto -- "mejor, decide por campos estructurados cuando existan".
_NEGACIONES_COMPACTAS = ("sin", "noincluye", "noincluyen", "without", "no", "senza", "bez", "fara", "sans", "ohne")


def _normalizar_para_veto(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_acentos.casefold()


def _compactar(texto: str) -> str:
    """Solo letras y dígitos ASCII, sin tildes, espacios ni guiones (resistente a ofuscación simple)."""
    return re.sub(r"[^a-z0-9]", "", _normalizar_para_veto(texto))


def _hay_mencion_afirmada(texto: str, frase: str) -> bool:
    """¿Aparece ``frase`` en ``texto`` sin una negación pegada justo antes, en alguna mención?

    Compara las formas compactadas (``_compactar``). Si hay varias menciones y al menos una no está
    negada, es afirmada (fail-closed ante ambigüedad / texto "mixto").
    """
    compacto = _compactar(texto)
    buscado = _compactar(frase)
    if not buscado:
        return False
    desde = 0
    while True:
        pos = compacto.find(buscado, desde)
        if pos == -1:
            return False
        prefijo = compacto[:pos]
        if not any(neg and prefijo.endswith(neg) for neg in _NEGACIONES_COMPACTAS):
            return True
        desde = pos + 1

CERO = Decimal(0)
UNO = Decimal(1)


def _redondear_entero(valor: Decimal) -> int:
    return int(valor.to_integral_value(rounding=ROUND_HALF_EVEN))


# ---------------------------------------------------------------------------
# Resultado de evaluar un par
# ---------------------------------------------------------------------------
@dataclass
class ResultadoPar:
    """Salida de :func:`evaluar_par` para UN par oferta × mercado."""

    estado_par: str  # pasa | incompleta | no_pasa | vetada
    motivo: str | None = None  # motivo canónico, solo si corresponde registrar en rechazos.jsonl
    detalle: str = ""
    pendiente: list[str] = field(default_factory=list)
    candidato: dict[str, Any] | None = None

    @property
    def tiene_motivo_canonico(self) -> bool:
        return self.motivo is not None and self.motivo in MOTIVOS_CANONICOS_DISPONIBLES


def _incompleta(pendiente: Sequence[str]) -> ResultadoPar:
    return ResultadoPar("incompleta", pendiente=list(dict.fromkeys(pendiente)))


def _no_pasa(detalle: str) -> ResultadoPar:
    return ResultadoPar("no_pasa", detalle=detalle)


def _vetada(detalle: str, motivo: str | None = None) -> ResultadoPar:
    return ResultadoPar("vetada", motivo=motivo, detalle=detalle)


# ---------------------------------------------------------------------------
# Regla 1: estado = pasa (PM >= umbral) y pendientes = [] (ya lo calculó puntaje_modelar)
# ---------------------------------------------------------------------------
def _regla_1_estado_pasa(par_pm: Mapping[str, Any], *, practica_vetada_causa: str | None) -> ResultadoPar | None:
    """§3.8.1 regla 1. ``par_pm`` es la salida de ``puntaje_modelar.puntuar_par`` (o ``formatear``)."""
    if par_pm["vetos"]:
        veto = par_pm["vetos"][0]
        if veto == "marca_personal":
            return _vetada("puerta marca_personal = true", motivo="dependencia_de_marca_personal")
        if veto == "sustituto_gratis_cubre":
            return _vetada("puerta sustituto_gratis_cubre = true", motivo="sustituto_gratis_dominante")
        # practica_vetada: el motivo exacto depende de la causa que juzgó el Maker (interfaces §3.8).
        if practica_vetada_causa == "promesa_salud_o_ingresos":
            return _vetada("puerta practica_vetada = true (promesa de ingresos o salud)",
                           motivo="claim_de_salud_o_ingresos")
        return _vetada(
            "puerta practica_vetada = true (clonar landing, contenido de terceros, testimonios "
            "inventados o urgencia falsa); sin motivo canónico todavía (pedido a CT: "
            "linea_roja_de_contenido_o_negocio)")
    if par_pm["estado"] == "incompleta":
        return _incompleta(par_pm["pendientes"])
    if par_pm["estado"] == "no_pasa":
        return _no_pasa(f"PM {par_pm['PM']} bajo modelado_umbral_pasa")
    return None  # estado == "pasa": sigue a la regla 2


# ---------------------------------------------------------------------------
# Regla 2: macro por Q0-Q6 sobre la prueba de una frase del PRODUCTO PROPIO
# ---------------------------------------------------------------------------
def _regla_2_macro(juicio: Mapping[str, Any]) -> tuple[ResultadoPar | None, dict[str, Any] | None]:
    """§3.8.1 regla 2. Devuelve ``(fallo_o_None, clasificacion_macro)``. Nunca copia ``modelado.macro_etiqueta``."""
    frase = juicio.get("prueba_una_frase")
    r = macro_mod.clasificar(frase, senal_id_e3=juicio.get("senal_id_e3"), cita_e3=juicio.get("cita_e3"))
    if r["estado"] == "sin_prueba_frase":
        return _no_pasa("sin prueba de una frase «de [A] a [B]» reconocible (rechazo MU/EU, no de macro)"), None
    if r["estado"] == "fuera_de_macro_nicho":
        return _vetada(f"fuera de marco: motivo_macro={r['motivo_macro']}", motivo="fuera_de_macro_nicho"), None
    if r["estado"] == "incompleta":
        return _incompleta(["clasificacion_macro.senal_id_e3"]), None
    clasificacion = {
        "banderas": r["banderas"], "motivo_macro": None, "senal_id_e3": r["senal_id_e3"],
        "version_arbol": r["version_arbol"],
    }
    return None, {"macro_nicho": r["macro_nicho"], "macro_secundario": r["macro_secundario"], **clasificacion}


# ---------------------------------------------------------------------------
# Regla 3: nicho_id / microsegmento
# ---------------------------------------------------------------------------
_RX_KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _regla_3_nicho(nicho_id: Any, microsegmento: Any, *, hojas_validas: Sequence[tuple[str, str]] | None) -> ResultadoPar | None:
    """§3.8.1 regla 3. Sin un validador de `nichos.yaml` disponible, solo exige forma kebab (documentado)."""
    if not isinstance(nicho_id, str) or not _RX_KEBAB.fullmatch(nicho_id):
        return _incompleta(["nicho_id"])
    if not isinstance(microsegmento, str) or not _RX_KEBAB.fullmatch(microsegmento):
        return _incompleta(["microsegmento"])
    if hojas_validas is not None and (nicho_id, microsegmento) not in hojas_validas:
        return _incompleta(["nicho_id/microsegmento: hoja nueva, pendiente de aprobación del dueño"])
    return None


# ---------------------------------------------------------------------------
# Regla 4: riesgo completo por scripts.nivel_riesgo (falla cerrado si el módulo falla)
# ---------------------------------------------------------------------------
def _regla_4_riesgo(juicio: Mapping[str, Any], *, nivel_max_lanzable: Mapping[str, str] | None,
                    macro_nicho: str) -> tuple[ResultadoPar | None, dict[str, Any] | None]:
    """§3.8.1 regla 4. ``nivel_max_lanzable`` ausente => solo VERDE pasa (fail-closed, interfaces §5.1)."""
    ejes = juicio.get("ejes")
    extras = {
        "fuentes": juicio.get("riesgo_fuentes") or [], "categoria": juicio.get("riesgo_categoria") or "",
        "claims_a_evitar": juicio.get("riesgo_claims_a_evitar") or [],
        "angulo_seguro": juicio.get("riesgo_angulo_seguro") or "",
    }
    try:
        riesgo = nivel_riesgo.riesgo_de_candidato(
            ejes, zona_gris=bool(juicio.get("zona_gris")), hay_reencuadre=bool(juicio.get("hay_reencuadre")),
            **extras)
    except ErrorValidacion as exc:
        # "si el script no existe o falla, no hay candidato" (falla cerrado): este PAR no pasa, nunca
        # se asume un nivel. No es ErrorFabrica de la CLI: el resto del lote sigue evaluándose.
        return _no_pasa(f"riesgo no calculable: {exc.mensaje}"), None
    if riesgo["nivel"] == "rojo":
        detalle = f"riesgo ROJO (eje peor: {riesgo['ejes_codigo']})"
        if riesgo["ejes_codigo"]["P"] in ("P2n", "P3"):
            return _vetada(detalle, motivo="claim_de_salud_o_ingresos"), None
        return _vetada(detalle + "; sin motivo canónico todavía (pedido a CT: linea_roja_de_contenido_o_negocio)"), None
    tope = (nivel_max_lanzable or {}).get(macro_nicho)
    if not _nivel_dentro_del_tope(riesgo["nivel"], riesgo["subnivel"], tope):
        return _no_pasa(f"riesgo {riesgo['nivel']}/{riesgo['subnivel']} por encima de nivel_max_lanzable"
                        f"={tope!r} (ausente => solo verde)"), None
    return None, riesgo


_ORDEN_NIVEL_SUB: dict[tuple[str, str | None], int] = {
    ("verde", None): 0, ("amarillo", "A"): 1, ("amarillo", "B"): 2,
}


def _nivel_dentro_del_tope(nivel: str, subnivel: str | None, tope: str | None) -> bool:
    if tope is None:
        return nivel == "verde"  # sin la clave en limites.yaml: fail-closed, solo verde (interfaces §5.1)
    partes = tope.split("-", 1)
    tope_nivel, tope_sub = partes[0], (partes[1] if len(partes) > 1 else None)
    clave_tope = (tope_nivel, tope_sub.upper() if tope_sub else None)
    clave_actual = (nivel, subnivel)
    if clave_tope not in _ORDEN_NIVEL_SUB or clave_actual not in _ORDEN_NIVEL_SUB:
        return False
    return _ORDEN_NIVEL_SUB[clave_actual] <= _ORDEN_NIVEL_SUB[clave_tope]


# ---------------------------------------------------------------------------
# Regla 5: mecanismo (6 campos) y entregable (6 campos), sin servicio/comunidad/suscripción
# ---------------------------------------------------------------------------
def _regla_5_mecanismo_entregable(juicio: Mapping[str, Any], *, locale_destino: str) -> ResultadoPar | None:
    mecanismo = juicio.get("mecanismo")
    entregable = juicio.get("entregable")
    evidencia = juicio.get("evidencia") or []
    if not isinstance(mecanismo, Mapping):
        return _incompleta(["mecanismo"])
    nombre = mecanismo.get("nombre")
    if not isinstance(nombre, str):
        return _incompleta(["mecanismo.nombre"])
    n_palabras = len(_RX_NOMBRE_MECANISMO_PALABRAS.findall(nombre))
    if not (2 <= n_palabras <= 6):
        return _no_pasa(f"mecanismo.nombre: {n_palabras} palabras (se exige 2-6)")
    causa_raiz = mecanismo.get("causa_raiz") if isinstance(mecanismo.get("causa_raiz"), Mapping) else {}
    senales_causa = set(causa_raiz.get("senales") or [])
    if not senales_causa:
        return _incompleta(["mecanismo.causa_raiz.senales"])
    # `causa_raiz.senales` referencia `senal_id` (comunes#senal_id, 12 hex), NUNCA el `id` (EV-NN) de
    # `evidencia[]`; `senal_id` es un campo aditivo de la MINOR 1.1.0 (interfaces §3.7) que SÍ puede
    # viajar en `juicio.evidencia[]` (se limpia antes de escribir el `evidencia[]` del esquema 1.0.0).
    tiene_e3_destino = any(
        isinstance(e, Mapping) and e.get("senal_id") in senales_causa and e.get("tipo") == "E3"
        and e.get("locale") == locale_destino for e in evidencia
    )
    if not tiene_e3_destino:
        return _incompleta(["mecanismo.causa_raiz.senales (sin E3 del locale destino que la respalde)"])
    if not isinstance(entregable, Mapping):
        return _incompleta(["entregable"])
    faltan = [c for c in ("formato", "alcance", "estado_a_b", "tiempo_al_primer_resultado",
                          "producibilidad", "licencias") if not entregable.get(c)]
    if faltan:
        return _incompleta([f"entregable.{c}" for c in faltan])
    if entregable.get("formato") not in _FORMATOS_ENTREGABLE:
        return _no_pasa(f"entregable.formato {entregable.get('formato')!r} no está en {_FORMATOS_ENTREGABLE}")
    r = _regla_5b_sin_servicio_ni_comunidad(juicio, mecanismo, entregable)
    if r:
        return r
    if not entregable.get("licencias"):
        return _incompleta(["entregable.licencias"])
    return None


def _regla_5b_sin_servicio_ni_comunidad(juicio: Mapping[str, Any], mecanismo: Mapping[str, Any],
                                        entregable: Mapping[str, Any]) -> ResultadoPar | None:
    """Parte de la regla 5: veta si el entregable describe servicio, comunidad o "en vivo".

    Primero el campo estructurado (``juicio.entregable_estructura``) si lo trae el Maker; si no,
    detección de negación por ventana sobre el texto libre (``_hay_mencion_afirmada``).
    """
    estructura = juicio.get("entregable_estructura")
    estructura = estructura if isinstance(estructura, Mapping) else {}
    if estructura.get("comunidad_o_en_vivo") is True:
        return _vetada("entregable_estructura.comunidad_o_en_vivo = true (campo estructurado, §3.8.1 regla 5)",
                       motivo="requiere_comunidad_o_en_vivo")
    if estructura.get("servicio") is True:
        return _vetada("entregable_estructura.servicio = true (campo estructurado, §3.8.1 regla 5)",
                       motivo="requiere_servicio")
    texto_junto = " ".join(str(v) for v in (mecanismo.get("como_funciona"), entregable.get("alcance")))
    for frase in _FRASES_COMUNIDAD_O_VIVO:
        if _hay_mencion_afirmada(texto_junto, frase):
            return _vetada(f"entregable/mecanismo describe «{frase}» sin negarlo (sin servicio ni "
                           "comunidad, §3.8.1 regla 5)", motivo="requiere_comunidad_o_en_vivo")
    for frase in _FRASES_SERVICIO:
        if _hay_mencion_afirmada(texto_junto, frase):
            return _vetada(f"entregable/mecanismo describe «{frase}» sin negarlo (sin servicio ni "
                           "comunidad, §3.8.1 regla 5)", motivo="requiere_servicio")
    return None


# ---------------------------------------------------------------------------
# Regla 6: evidencia[] con >= 1 E3 del locale destino y >= 1 E2 (oferta), citas verificadas
# ---------------------------------------------------------------------------
def _regla_6_evidencia(evidencia: Any, *, locale_destino: str) -> ResultadoPar | None:
    if not isinstance(evidencia, list) or not evidencia:
        return _incompleta(["evidencia"])
    e3_destino = [e for e in evidencia if isinstance(e, Mapping) and e.get("tipo") == "E3" and e.get("locale") == locale_destino]
    e2_oferta = [e for e in evidencia if isinstance(e, Mapping) and e.get("tipo") == "E2"]
    if not e3_destino:
        return _incompleta(["evidencia (falta >= 1 E3 del locale destino)"])
    if not e2_oferta:
        return _incompleta(["evidencia (falta >= 1 E2 de la oferta fuente)"])
    if not all(e.get("cita_literal_verificada") is True for e in evidencia):
        return _no_pasa("evidencia con cita_literal_verificada != true no puede sostener un puntaje")
    return None


# ---------------------------------------------------------------------------
# Regla 7: similitud_memoria.max < sim_dup_bloqueo
# ---------------------------------------------------------------------------
def _regla_7_similitud(similitud_memoria: Any, *, sim_dup_bloqueo: Decimal) -> ResultadoPar | None:
    if not isinstance(similitud_memoria, Mapping) or similitud_memoria.get("max") is None:
        return _incompleta(["similitud_memoria"])
    try:
        sim = Decimal(str(similitud_memoria["max"]))
    except InvalidOperation:
        return _no_pasa("similitud_memoria.max ilegible")
    if sim >= sim_dup_bloqueo:
        return _no_pasa(f"similitud_memoria.max={sim} >= sim_dup_bloqueo={sim_dup_bloqueo} "
                        "(duplicado_de_la_memoria no es motivo canónico todavía, pedido a CT)")
    return None


# ---------------------------------------------------------------------------
# Regla 8: sensibilidad (siempre declarada; nunca se omite)
# ---------------------------------------------------------------------------
def _regla_8_sensibilidad(sensibilidad_pct: Any) -> tuple[ResultadoPar | None, int]:
    if not isinstance(sensibilidad_pct, int) or isinstance(sensibilidad_pct, bool) or not (0 <= sensibilidad_pct <= 100):
        return _incompleta(["sensibilidad.top3_estable_pct"]), 0
    return None, sensibilidad_pct


# ---------------------------------------------------------------------------
# Regla 9: pendiente[] vacío (notas abiertas del Maker sobre la ficha)
# ---------------------------------------------------------------------------
def _regla_9_pendiente_vacio(notas_pendientes: Any) -> ResultadoPar | None:
    lista = notas_pendientes or []
    if not isinstance(lista, list):
        return _no_pasa("ficha.pendiente debe ser una lista")
    if lista:
        return _incompleta([f"modelado.pendiente: {n}" for n in lista])
    return None


# ---------------------------------------------------------------------------
# Orquestación de un par (reglas 1-9; 10-12 son del CLI/QA)
# ---------------------------------------------------------------------------
def evaluar_par(par_pm: Mapping[str, Any], ficha_oferta: Mapping[str, Any], mercado: Mapping[str, Any],
                juicio: Mapping[str, Any], *, problema_id: str, nicho_id: Any, microsegmento: Any,
                sensibilidad_pct: int, nivel_max_lanzable: Mapping[str, str] | None = None,
                sim_dup_bloqueo: Decimal = Decimal("0.80"), hojas_validas: Sequence[tuple[str, str]] | None = None,
                modo_busqueda: str = "D", sello_reglas: str | None = None) -> ResultadoPar:
    """Corre las reglas 1-9 de §3.8.1 en orden y, si todas pasan, arma el ``candidato``.

    ``par_pm``: salida de ``puntaje_modelar.puntuar_par`` (sin formatear: valores ``Decimal``).
    ``ficha_oferta``/``mercado``: la oferta y el ÚNICO mercado ya validados por
    ``puntaje_modelar.validar_fichas`` (mismos objetos que produjeron ``par_pm``).
    """
    practica_vetada_causa = juicio.get("practica_vetada_causa")
    r = _regla_1_estado_pasa(par_pm, practica_vetada_causa=practica_vetada_causa)
    if r:
        return r

    r, clasificacion_macro = _regla_2_macro(juicio)
    if r:
        return r
    assert clasificacion_macro is not None
    macro_nicho = clasificacion_macro["macro_nicho"]

    r = _regla_3_nicho(nicho_id, microsegmento, hojas_validas=hojas_validas)
    if r:
        return r

    r, riesgo = _regla_4_riesgo(juicio, nivel_max_lanzable=nivel_max_lanzable, macro_nicho=macro_nicho)
    if r:
        return r
    assert riesgo is not None

    locale_destino = mercado["mercado"]  # ISO-2; el locale BCP-47 completo lo resuelve M1 (fuera de alcance D1c)
    r = _regla_5_mecanismo_entregable(juicio, locale_destino=locale_destino)
    if r:
        return r

    r = _regla_6_evidencia(juicio.get("evidencia"), locale_destino=locale_destino)
    if r:
        return r

    r = _regla_7_similitud(juicio.get("similitud_memoria"), sim_dup_bloqueo=sim_dup_bloqueo)
    if r:
        return r

    r, sensibilidad_declarada = _regla_8_sensibilidad(sensibilidad_pct)
    if r:
        return r

    r = _regla_9_pendiente_vacio(ficha_oferta.get("pendiente"))
    if r:
        return r

    candidato = _construir_candidato(
        par_pm=par_pm, ficha_oferta=ficha_oferta, mercado=mercado, juicio=juicio, problema_id=problema_id,
        nicho_id=nicho_id, microsegmento=microsegmento, macro_nicho=macro_nicho, riesgo=riesgo,
        sensibilidad_pct=sensibilidad_declarada, modo_busqueda=modo_busqueda, sello_reglas=sello_reglas)
    return ResultadoPar("pasa", candidato=candidato)


def _confianza_y_f(evidencia: Sequence[Mapping[str, Any]]) -> tuple[str, Decimal]:
    """``(confianza, f_confianza)`` de D1 §3.2 a partir de la evidencia del par."""
    fuentes = {e.get("id") for e in evidencia}
    tipos = {e.get("tipo") for e in evidencia}
    tiene_e1 = "E1" in tipos
    if len(fuentes) >= 3 and len(tipos) >= 2 and tiene_e1:
        return "alta", Decimal("1.0")
    if len(fuentes) >= 2 and len(tipos) >= 2:
        return "media", Decimal("0.9")
    return "baja", Decimal("0.75")


def _f_dup(sim: Decimal) -> Decimal:
    """``f_dup = 1 - 0.4 * clamp((sim - 0.5) / 0.3, 0, 1)`` (D1 §3.2)."""
    x = (sim - Decimal("0.5")) / Decimal("0.3")
    x = max(CERO, min(UNO, x))
    return UNO - Decimal("0.4") * x


def _construir_candidato(*, par_pm: Mapping[str, Any], ficha_oferta: Mapping[str, Any], mercado: Mapping[str, Any],
                         juicio: Mapping[str, Any], problema_id: str, nicho_id: str, microsegmento: str,
                         macro_nicho: str, riesgo: Mapping[str, Any], sensibilidad_pct: int,
                         modo_busqueda: str = "D", sello_reglas: str | None = None) -> dict[str, Any]:
    """Candidato con los 26 campos de `candidatos.schema.json` 1.0.0 (``candidato_id``/``rango`` los
    asigna el llamador tras ordenar todo el lote)."""
    evidencia_cruda = list(juicio.get("evidencia") or [])
    confianza, f_conf = _confianza_y_f(evidencia_cruda)
    _campos_evidencia_1_0_0 = ("id", "tipo", "url", "fecha_publicacion", "fecha_consulta", "cita",
                              "cita_literal_verificada", "hash_copia_crudo")
    # `locale` y `senal_id` son aditivos de la MINOR 1.1.0 (interfaces §3.7): se usan para las
    # reglas 5/6 (arriba) pero NO se escriben en `evidencia[]` del esquema 1.0.0 (additionalProperties
    # false); viajarían en `_evidencia_1_1_0` si CT aprueba la MINOR (pedido §8.1 n.1).
    evidencia = [{k: e[k] for k in _campos_evidencia_1_0_0 if k in e} for e in evidencia_cruda]
    sim = Decimal(str(juicio["similitud_memoria"]["max"]))
    score_base = _redondear_entero(par_pm["PM"])
    score_ajustado = max(0, min(100, _redondear_entero(Decimal(score_base) * f_conf * _f_dup(sim))))
    traccion = ficha_oferta["traccion"]
    demanda_pagada = {
        "n_anuncios": traccion["anuncios_activos"], "n_anunciantes": traccion["anunciantes_independientes_mismo_angulo"],
        "n_sostenidos": 0, "n_conceptos_unicos": traccion["conceptos_unicos"],
        "antiguedad_max_dias": int(traccion["edad_oferta_dias"]), "consultas_ids": [],
        "senal_rentabilidad": "no medible",
    }
    if juicio.get("hay_reencuadre"):
        reencuadre_aplicado = {
            "aplicado": True, "nivel_original": juicio.get("reencuadre_nivel_original") or "rojo",
            "descripcion": juicio.get("reencuadre_descripcion") or "reencuadre aplicado",
        }
    else:
        reencuadre_aplicado = {"aplicado": False}
    riesgo_1_0_0 = {
        "P": _color_de_eje(riesgo, "P"), "C": _color_de_eje(riesgo, "C"), "E": _color_de_eje(riesgo, "E"),
        "N": _color_de_eje(riesgo, "N"), "nivel": riesgo["nivel"], "reencuadre_aplicado": reencuadre_aplicado,
        "fuentes": riesgo.get("fuentes") or ["scripts/nivel_riesgo.py"], "categoria": riesgo.get("categoria") or "sin_categoria",
        "claims_a_evitar": riesgo.get("claims_a_evitar") or [], "angulo_seguro": riesgo.get("angulo_seguro") or "sin especificar",
    }
    return {
        "problema_id": problema_id, "macro_nicho": macro_nicho, "nicho_id": nicho_id, "microsegmento": microsegmento,
        "problema": juicio.get("problema") or juicio["prueba_una_frase"], "prueba_una_frase": juicio["prueba_una_frase"],
        "tesis": juicio.get("tesis") or juicio["prueba_una_frase"][:400],
        "mecanismo": juicio["mecanismo"], "entregable": juicio["entregable"],
        "precio_plausible": juicio["precio_plausible"],
        "puntajes": juicio.get("puntajes") or {}, "score_base": score_base, "score_ajustado": score_ajustado,
        "confianza": confianza, "evidencia": evidencia, "demanda_pagada": demanda_pagada, "riesgo": riesgo_1_0_0,
        "similitud_memoria": juicio["similitud_memoria"],
        "viabilidad_cpa": juicio.get("viabilidad_cpa") or {
            "ratio_pes": "1", "ratio_central": "1", "ratio_opt": "1", "supuestos": ["sin datos: ratio neutro"],
            "bandera": "amarilla"},
        "sensibilidad": {"top3_estable_pct": sensibilidad_pct},
        "ventana_estacional": juicio.get("ventana_estacional"),
        "hipotesis_para_d2": list(juicio.get("hipotesis_para_d2") or []),
        "que_la_mataria": list(juicio.get("que_la_mataria") or []),
        "palabras_clave_voz_cliente": list(juicio.get("palabras_clave_voz_cliente") or []),
        # Aditivos de la MINOR 1.1.0 (interfaces §3.7: `riesgo.{subnivel,ejes_codigo,version_tabla}`,
        # `origen`, y defecto D1d n.2a: `sello_reglas`/`modo_busqueda`), fuera del esquema 1.0.0
        # (additionalProperties:false por candidato; pedido a CT §8.1 n.1). El llamador (`mapear_candidatos`)
        # los extrae a un sidecar ANTES de validar el documento contra el esquema vigente.
        "_aditivos_1_1_0": {
            "riesgo": {"subnivel": riesgo["subnivel"], "ejes_codigo": riesgo["ejes_codigo"],
                      "version_tabla": riesgo["version_tabla"]},
            "origen": {"via": "oferta_primero", "modo_busqueda": modo_busqueda, "problema_id": problema_id},
            "sello_reglas": sello_reglas,
        },
    }


def _color_de_eje(riesgo: Mapping[str, Any], eje: str) -> str:
    return nivel_riesgo.COLOR[riesgo["ejes_codigo"][eje]]


# ---------------------------------------------------------------------------
# CLI: junta varios pares, ordena, valida el DOCUMENTO contra el esquema vigente (regla 10) y escribe
# ---------------------------------------------------------------------------
MODOS_BUSQUEDA_VALIDOS = ("A", "B", "C", "D", "mixto")

# Defecto D1d n.2c: ningún archivo real junta `modelado_*` y `sim_dup_bloqueo` en el mismo YAML.
# `sim_dup_bloqueo` SOLO tiene un hogar real: `empresa/parametros.yaml`. `modelado_*` vive ahí SI el
# dueño ya aprobó la integración (interfaces §9 n.6); hasta entonces, respaldo en
# `scripts/modelado/parametros_modelado.propuesta.yaml` (decisión de S-A). Nunca un valor literal.
RUTA_RESPALDO_MODELADO = Path(__file__).resolve().parents[1] / "modelado" / "parametros_modelado.propuesta.yaml"


def _cargar_parametros_descubrimiento(ruta: Path | None) -> dict[str, Any]:
    """Reusa el cargador de `puntaje_modelar` (mismas 36 claves `modelado_*` + sello) desde UN YAML.

    Para pruebas y diagnóstico con un único archivo fixture (``--parametros``); la resolución real por
    hogar (sin override) es :func:`parametros_descubrimiento_reales`.
    """
    return pm.cargar_parametros(ruta)


def parametros_descubrimiento_reales(raiz: Path) -> tuple[dict[str, Any], Decimal]:
    """``(modelado_*, sim_dup_bloqueo)`` leídos cada uno de SU hogar real (defecto D1d n.2c).

    ``sim_dup_bloqueo``: siempre de ``<raiz>/empresa/parametros.yaml`` (único hogar; sin respaldo).
    ``modelado_*``: de ``<raiz>/empresa/parametros.yaml`` si el dueño ya los integró ahí; si no, del
    respaldo :data:`RUTA_RESPALDO_MODELADO`. Si falta cualquiera de los dos orígenes: ``ErrorLimite``
    (5), falla cerrado, nunca un valor por defecto.
    """
    ruta_empresa = Path(raiz) / "empresa" / "parametros.yaml"
    sim_dup_bloqueo = _leer_sim_dup_bloqueo(ruta_empresa)
    try:
        modelado = pm.cargar_parametros(ruta_empresa)
    except pm.ErrorLimite:  # `puntaje_modelar` tiene su PROPIA jerarquía de errores, no engine.errores
        modelado = pm.cargar_parametros(RUTA_RESPALDO_MODELADO)
    return modelado, sim_dup_bloqueo


def _leer_sim_dup_bloqueo(ruta: Path) -> Decimal:
    """``grupos.descubrimiento.sim_dup_bloqueo.valor`` leído sin pasar por el validador de esquema completo.

    `engine.parametros.cargar_parametros` exige TODOS los grupos contra `parametros.schema.json`, que
    hoy (sin la MINOR 1.2.0 de `patternProperties`, interfaces §5.2) rechaza los `modelado_*` que
    conviven en el mismo `grupos.descubrimiento`. Mismo estilo de lectura que
    `puntaje_modelar.cargar_parametros`: falla cerrado (`ErrorLimite`) si falta.
    """
    import yaml

    try:
        datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ErrorLimite(f"no se pudo leer {ruta}: {exc}") from exc
    entrada = ((datos or {}).get("grupos") or {}).get("descubrimiento", {}).get("sim_dup_bloqueo")
    if not isinstance(entrada, Mapping) or "valor" not in entrada:
        raise ErrorLimite("falta descubrimiento.sim_dup_bloqueo en parametros.yaml")
    try:
        return Decimal(str(entrada["valor"]))
    except InvalidOperation as exc:
        raise ErrorValidacion("descubrimiento.sim_dup_bloqueo ilegible") from exc


def mapear_candidatos(doc_pares: Mapping[str, Any], parametros: Mapping[str, Any], *, oferta_id: str,
                      corrida_id: str, mercado_locale: str, mercado_paises: Sequence[str],
                      nivel_max_lanzable: Mapping[str, str] | None, sim_dup_bloqueo: Decimal,
                      ahora: Callable[[], datetime] = ahora_utc, modo_busqueda: str = "D") -> dict[str, Any]:
    """Procesa todos los pares de ``doc_pares`` y devuelve un resumen con el `candidatos.json` armado.

    ``doc_pares``: ``{"schema_version": "1.0.0", "pares": [...]}`` (contrato del docstring del módulo).
    ``parametros``: salida de ``puntaje_modelar.cargar_parametros`` (solo las 36 claves ``modelado_*``).
    ``sim_dup_bloqueo``: de ``empresa/parametros.yaml#grupos.descubrimiento.sim_dup_bloqueo`` (otro
    grupo de parámetros; el llamador lo lee con ``engine.parametros``, no con este módulo).
    Ningún candidato con ``riesgo.nivel = rojo`` entra (regla 4); la sensibilidad se calcula UNA sola
    vez para todo el lote (es propiedad del ranking, no de un par) y se copia a cada candidato que pasa.
    """
    if modo_busqueda not in MODOS_BUSQUEDA_VALIDOS:
        raise ErrorValidacion(f"modo_busqueda inválido: {modo_busqueda!r} (se espera uno de {MODOS_BUSQUEDA_VALIDOS})")
    if not isinstance(doc_pares, Mapping) or doc_pares.get("schema_version") != "1.0.0":
        raise ErrorValidacion("pares.json: se espera {schema_version: '1.0.0', pares: [...]}")
    pares_crudos = doc_pares.get("pares")
    if not isinstance(pares_crudos, list) or not pares_crudos:
        raise ErrorValidacion("pares.json: 'pares' debe ser una lista no vacía")

    sello_vigente = pm.sello_reglas(parametros)
    fichas_doc = {"schema_version": "2.0.0", "ofertas": [p["ficha"] for p in pares_crudos]}
    ofertas_validadas = pm.validar_fichas(fichas_doc, parametros)
    todos = [pm.puntuar_par(o, o["mercados"][0], parametros) for o in ofertas_validadas]
    sens = pm.sensibilidad(todos, parametros)
    sensibilidad_pct = 0 if sens["estado"] in ("insuficiente",) else (
        0 if sens["cobertura"] is None else _redondear_entero(Decimal(100) * sens["cobertura"]))

    resultados: list[ResultadoPar] = []
    for crudo, oferta_validada, par_pm in zip(pares_crudos, ofertas_validadas, todos):
        juicio = crudo.get("juicio") or {}
        r = evaluar_par(
            par_pm, oferta_validada, oferta_validada["mercados"][0], juicio, problema_id=crudo["problema_id"],
            nicho_id=crudo.get("nicho_id"), microsegmento=crudo.get("microsegmento"),
            sensibilidad_pct=sensibilidad_pct, nivel_max_lanzable=nivel_max_lanzable, sim_dup_bloqueo=sim_dup_bloqueo,
            modo_busqueda=modo_busqueda, sello_reglas=sello_vigente)
        resultados.append(r)

    pasan = [r for r in resultados if r.estado_par == "pasa"]
    pasan.sort(key=lambda r: -r.candidato["score_ajustado"])  # type: ignore[index]
    candidatos = []
    sidecar_1_1_0: dict[str, Any] = {}
    for i, r in enumerate(pasan, start=1):
        cand = dict(r.candidato)  # type: ignore[arg-type]
        cand["candidato_id"] = f"CAND-{i:02d}"
        cand["rango"] = i
        aditivos = cand.pop("_aditivos_1_1_0", None)
        if aditivos is not None:
            sidecar_1_1_0[cand["candidato_id"]] = aditivos
        candidatos.append(cand)

    documento = {
        "schema_version": "1.0.0", "oferta_id": oferta_id, "corrida_id": corrida_id,
        "fecha": iso_z(ahora()), "modo": "dirigido", "mercado": {"locale": mercado_locale, "paises": list(mercado_paises)},
        # Prefijo "pm_" (interfaces §3.7: cada familia de pesos lleva el prefijo de su modelo).
        "pesos": {f"pm_{k}": str(v * 100) for k, v in pm._pesos(parametros).items()},  # noqa: SLF001
        # `sello_reglas` y `modo_busqueda` (defecto D1d n.2a): el esquema 1.0.0 no los admite como
        # campos de cabecera (additionalProperties:false), pero `parametros_usados` SÍ es abierto
        # (additionalProperties:{}); viajan ahí hasta que CT apruebe la MINOR 1.1.0 (§3.7, cabecera).
        "parametros_usados": {"modelado_umbral_pasa": str(parametros["modelado_umbral_pasa"]),
                              "formula_version": pm.FORMULA_VERSION, "sello_reglas": sello_vigente,
                              "modo_busqueda": modo_busqueda},
        "consultas": [], "candidatos": candidatos, "descartados": [],
    }
    return {"documento": documento, "resultados": resultados, "sensibilidad": sens,
            "sensibilidad_pct": sensibilidad_pct, "sidecar_1_1_0": sidecar_1_1_0}


def rechazos_de(resultados: Sequence[ResultadoPar], pares_crudos: Sequence[Mapping[str, Any]], *,
                ahora: Callable[[], datetime] = ahora_utc) -> list[dict[str, Any]]:
    """Líneas para `rechazos.jsonl` (§2.4): solo los pares con motivo canónico (regla 11)."""
    lineas = []
    ts = iso_z(ahora())
    for r, crudo in zip(resultados, pares_crudos):
        if not r.tiene_motivo_canonico:
            continue
        lineas.append({
            "problema_id": crudo["problema_id"], "candidato_id": None, "nicho_id": crudo.get("nicho_id"),
            "locale": crudo["ficha"]["mercados"][0]["mercado"], "origen_descarte": "filtro_d1",
            "motivo": r.motivo, "redencion": REDENCION_POR_MOTIVO[r.motivo], "fecha": ts,
            "vigente_hasta": ts, "evidencia_ids": [], "detalle": r.detalle[:140],
        })
    return lineas


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.descubrimiento.ficha_a_candidato",
                                description="Puerta de entrada a candidatos.json (interfaces §3.8.1)")
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mapear")
    m.add_argument("pares", type=Path)
    m.add_argument("--raiz", type=Path,
                   help="raíz del repositorio; por defecto FABRICA_RAIZ o la ruta del archivo. Se usa "
                        "para resolver modelado_*/sim_dup_bloqueo por su hogar real si no se da --parametros")
    m.add_argument("--parametros", type=Path,
                   help="(diagnóstico/pruebas) UN YAML con modelado_* y sim_dup_bloqueo juntos; por "
                        "defecto (sin esto) se leen cada uno de su hogar real bajo --raiz")
    m.add_argument("--oferta-id", required=True)
    m.add_argument("--corrida-id", required=True)
    m.add_argument("--locale", required=True)
    m.add_argument("--paises", required=True, help="ISO-2 separados por coma")
    m.add_argument("--nivel-max-lanzable", help="JSON {macro_nicho: 'nivel-subnivel'}; ausente = solo verde")
    m.add_argument("--modo-busqueda", default="D", choices=MODOS_BUSQUEDA_VALIDOS,
                   help="cabecera 1.1.0 (interfaces §3.7); hoy solo 'D' está construido")
    m.add_argument("--salida", type=Path, required=True)
    m.add_argument("--rechazos", type=Path, help="ruta de rechazos.jsonl (se anexa con --aplicar)")
    m.add_argument("--sidecar", type=Path,
                   help="ruta del sidecar 1.1.0 (sello_reglas/riesgo ampliado/origen por candidato); "
                        "por defecto <salida>.sidecar-1.1.0.json")
    m.add_argument("--aplicar", action="store_true",
                   help="escribe --salida, --sidecar y anexa --rechazos; sin esto, solo informa")
    m.add_argument("--exigir-alguno", action="store_true", help="código 3 si ningún par llega a 'pasa'")
    m.add_argument("--json", action="store_true")
    return p


def _ruta_sidecar(a: argparse.Namespace) -> Path:
    if a.sidecar:
        return a.sidecar
    return a.salida.with_name(a.salida.stem + ".sidecar-1.1.0" + a.salida.suffix)


def _cuerpo_mapear(a: argparse.Namespace) -> int:
    doc_pares = pm.leer_json(a.pares)
    if a.parametros:
        parametros = _cargar_parametros_descubrimiento(a.parametros)
        sim_dup_bloqueo = _leer_sim_dup_bloqueo(a.parametros)
    else:
        parametros, sim_dup_bloqueo = parametros_descubrimiento_reales(a.raiz or raiz_repositorio())
    nivel_max_lanzable = json.loads(a.nivel_max_lanzable) if a.nivel_max_lanzable else None
    resultado = mapear_candidatos(
        doc_pares, parametros, oferta_id=a.oferta_id, corrida_id=a.corrida_id, mercado_locale=a.locale,
        mercado_paises=a.paises.split(","), nivel_max_lanzable=nivel_max_lanzable, sim_dup_bloqueo=sim_dup_bloqueo,
        modo_busqueda=a.modo_busqueda)
    documento = resultado["documento"]
    errores_esquema = errores_de_esquema("candidatos", documento) if documento["candidatos"] else []
    conteos = {"pasa": 0, "incompleta": 0, "no_pasa": 0, "vetada": 0}
    for r in resultado["resultados"]:
        conteos[r.estado_par] += 1
    rechazos = rechazos_de(resultado["resultados"], doc_pares["pares"])

    if errores_esquema:
        if not a.json:
            print(f"ERROR: el candidatos.json armado no cumple el esquema (regla 10): "
                  f"{len(errores_esquema)} error(es); no se escribe nada")
        raise ErrorValidacion(f"candidatos.json no valida contra el esquema 1.0.0: {len(errores_esquema)} error(es)")
    if a.exigir_alguno and conteos["pasa"] == 0:
        raise ErrorValidacion("ningún par llegó a 'pasa': no hay candidato que ofrecer")

    ruta_sidecar = _ruta_sidecar(a)
    if a.aplicar and conteos["pasa"] > 0:
        escribir_atomico(a.salida, json_canonico(documento))
        escribir_atomico(ruta_sidecar, json_canonico(
            {"schema_version": "1.1.0-sidecar", "candidatos": resultado["sidecar_1_1_0"]}))
        if a.rechazos:
            for linea in rechazos:
                anexar_jsonl(a.rechazos, linea)

    salida = {"conteos": conteos, "candidatos_pasan": conteos["pasa"], "rechazos_canonicos": len(rechazos),
              "escrito": bool(a.aplicar and conteos["pasa"] > 0), "ruta_salida": str(a.salida),
              "ruta_sidecar": str(ruta_sidecar)}
    if a.json:
        print(json.dumps(salida, ensure_ascii=False, sort_keys=True))
    else:
        print(f"pasa={conteos['pasa']} incompleta={conteos['incompleta']} no_pasa={conteos['no_pasa']} "
              f"vetada={conteos['vetada']} rechazos_canonicos={len(rechazos)} escrito={salida['escrito']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    def _principal() -> int:
        try:
            args = _parser().parse_args(argv)
        except SystemExit as exc:
            if exc.code in (0, None):
                return 0
            raise ErrorUso("argumentos inválidos (ver --help)") from None
        return {"mapear": _cuerpo_mapear}[args.cmd](args)

    return ejecutar_cli(_principal)


if __name__ == "__main__":
    raise SystemExit(main())
