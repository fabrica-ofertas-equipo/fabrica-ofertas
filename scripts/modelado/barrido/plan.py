"""Plan de consultas del barrido por forma (D1 Modo D; spec departamentos/02-descubrimiento.md §15 y §17,
contrato scripts/modelado/barrido/CONTRATO.md §3 y §6).

Qué hace: arma la lista de consultas a `ads_library_search` que ejecutarán los agentes de barrido, la valida, la reparte
entre agentes y rellena el prompt de cada agente. No habla con la red ni con el conector: solo produce y valida planes.

  pasada 1  una consulta por (país × forma): frase `principal` de la forma, en el idioma del país.
  pasada 2  particiones: cuando una consulta de la pasada 1 supera `barrido_partir_si_total_supera` y su muestra llegó al
            límite (hay anuncios que no se ven), se repite con las variantes de frase de esa forma.
  pasada 3  consultas por `page_ids` (páginas con tracción en la muestra) × países de presencia: edad real y presencia.

Principios del repositorio:
  · La IA propone, el código dispone. Ningún número de umbral vive aquí: salen de `parametros_barrido.propuesta.yaml`
    y de `parametros_modelado.propuesta.yaml` (tope de consultas). Si falta uno, falla cerrado (ErrorLimite, código 5).
  · Ningún país es «el favorito»: el orden de los países sale de `barrido_paises_origen`.
  · Todo texto que venga de la Biblioteca es dato no confiable. Este módulo solo lee identificadores y conteos de ella.

Qid determinista (kebab-case ASCII): pasada 1 `<pais>-<forma>`; pasada 2 `<pais>-<forma>-v<k>`; pasada 3
`<pais>-pag-<huella>` (huella de los page_ids del lote). Un plan ampliado (pasadas 2 y 3) se escribe como plan acumulado en
`empresa/barrido/planes/<corrida_id>.pasada-<n>.json`: los artefactos nunca se sobrescriben.

Uso típico (coordinador):
    plan = generar_plan(corrida, paises=None, formas=None, par_barrido=pb, par_modelado=pm, ahora=ahora)
    escribir_plan(plan, {**pb, **pm})
    olas = repartir_en_olas(plan, par_barrido=pb)         # cada agente recibe instrucciones_agente(plan, sus_qids)
    # ... los agentes escriben empresa/barrido/crudo/<corrida>/<qid>.json ...
    res = resumenes_desde_crudos(validar_crudo(leer_json(r)) for r in listar_crudos(corrida))
    nuevas = siguiente_pasada(plan, res, par_barrido=pb, par_modelado=pm)
    plan2 = ampliar_plan(plan, nuevas, {**pb, **pm}, ahora=ahora)
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.modelado.barrido.comun import (
    LIMITE_MAX_CONECTOR,
    RAIZ,
    VERSION_ESQUEMA,
    ErrorLimite,
    ErrorUso,
    ErrorValidacion,
    corrida_id_valido,
    dir_barrido,
    escribir_json_nuevo,
    iso_z,
    leer_json,
    parsear_z,
    qid_valido,
)

# ---------------------------------------------------------------------------
# Constantes: vocabularios y hechos del contrato (NO son umbrales calibrables)
# ---------------------------------------------------------------------------

RUTA_BANCO: Path = Path(__file__).resolve().parent / "frases_forma.yaml"
RUTA_PLANTILLA: Path = Path(__file__).resolve().parent / "agente_barrido.md"

CLAVE_TOPE = "modelado_max_consultas_por_corrida"   # vive en parametros_modelado.propuesta.yaml
ESTADO_ACTIVO = "ACTIVE"                            # vocabulario de la Biblioteca: solo lo que corre hoy (spec §15.1)

PASADA_FORMA = 1        # identificadores de pasada (CONTRATO §3), no umbrales
PASADA_PARTICION = 2
PASADA_PAGINAS = 3
LARGO_HUELLA_QID = 8    # largo del sufijo hexadecimal del qid de la pasada 3: identificador, no umbral

CAMPOS_PLAN = ("schema_version", "corrida_id", "creado_en", "tope_consultas", "consultas")
CAMPOS_CONSULTA = ("qid", "search_terms", "countries", "idioma", "forma_id", "ad_active_status", "limit",
                   "page_ids", "pasada")
MARCA_INICIO = "<!-- PROMPT:INICIO -->"
MARCA_FIN = "<!-- PROMPT:FIN -->"
MARCADORES_PLANTILLA = ("CORRIDA_ID", "RAIZ", "TOTAL", "CONSULTAS")

_RE_PAIS = re.compile(r"[A-Z]{2}")
_RE_IDIOMA = re.compile(r"[a-z]{2}")
_RE_DIGITOS = re.compile(r"[0-9]+")
_RE_MARCADOR = re.compile(r"\{\{([A-Z_]+)\}\}")


# ---------------------------------------------------------------------------
# Parámetros (falla cerrado)
# ---------------------------------------------------------------------------

def _entero_param(par: Any, clave: str) -> int:
    """Entero ≥ 1 del mapa de parámetros. Falta o es nulo = ErrorLimite (5); tipo equivocado = ErrorValidacion (3)."""
    if not isinstance(par, Mapping) or par.get(clave) is None:
        raise ErrorLimite(f"falta el parámetro {clave} (falla cerrado: no se asume ningún valor; "
                          "ver scripts/modelado/barrido/parametros_barrido.propuesta.yaml)")
    valor = par[clave]
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ErrorValidacion(f"{clave}: se esperaba un entero, llegó {type(valor).__name__}")
    if valor < 1:
        raise ErrorLimite(f"{clave}: {valor} no es un valor utilizable (debe ser ≥ 1)")
    return valor


def _paises_param(par: Any, clave: str) -> list[str]:
    """Lista no vacía de países ISO-2 sin repetir. Falta = ErrorLimite; contenido raro = ErrorValidacion."""
    if not isinstance(par, Mapping) or par.get(clave) is None:
        raise ErrorLimite(f"falta el parámetro {clave} (falla cerrado: no se asume ningún valor; "
                          "ver scripts/modelado/barrido/parametros_barrido.propuesta.yaml)")
    valor = par[clave]
    if not isinstance(valor, (list, tuple)) or not valor:
        raise ErrorValidacion(f"{clave}: se esperaba una lista no vacía de países ISO-2")
    for p in valor:
        if not (isinstance(p, str) and _RE_PAIS.fullmatch(p)):
            raise ErrorValidacion(f"{clave}: país ISO-2 en mayúsculas esperado, llegó {p!r}")
    if len(set(valor)) != len(valor):
        raise ErrorValidacion(f"{clave}: países repetidos")
    return list(valor)


def _unir(par_barrido: Any, par_modelado: Any) -> dict[str, Any]:
    for nombre, par in (("par_barrido", par_barrido), ("par_modelado", par_modelado)):
        if not isinstance(par, Mapping):
            raise ErrorUso(f"{nombre}: se esperaba el dict que devuelven comun.cargar_parametros_*")
    return {**par_modelado, **par_barrido}


# ---------------------------------------------------------------------------
# Banco de frases por forma
# ---------------------------------------------------------------------------

def _frase(valor: Any, campo: str) -> str:
    """Frase de búsqueda: texto NFC, sin espacios en los bordes, sin saltos ni caracteres de control."""
    if not isinstance(valor, str):
        raise ErrorValidacion(f"{campo}: se esperaba texto, llegó {type(valor).__name__}")
    texto = unicodedata.normalize("NFC", valor).strip()
    if not texto:
        raise ErrorValidacion(f"{campo}: frase vacía")
    if any(unicodedata.category(c).startswith("C") for c in texto):
        raise ErrorValidacion(f"{campo}: la frase contiene caracteres de control o saltos de línea")
    return texto


def cargar_banco(ruta: Path | None = None) -> dict[str, Any]:
    """Carga y valida `frases_forma.yaml`.

    Devuelve `{"idiomas": {idioma: [paises]}, "pais_idioma": {pais: idioma},
    "formas": [{"id", "descripcion", "frases": {idioma: {"principal", "variantes": [...]}}}]}`.
    Errores: ErrorLimite si no se puede leer el archivo; ErrorValidacion si el contenido no cumple las reglas
    (país en dos idiomas, forma sin frase en algún idioma, frase repetida dentro de un idioma, id no kebab, ...).
    """
    import yaml  # PyYAML está en requirements.txt de la raíz

    ruta = Path(ruta) if ruta is not None else RUTA_BANCO
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ErrorLimite(f"no se pudo leer el banco de frases {ruta}: {exc} (falla cerrado)") from exc
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise ErrorValidacion(f"{ruta}: YAML inválido ({exc})") from exc
    if not isinstance(datos, dict):
        raise ErrorValidacion(f"{ruta}: se esperaba un mapa con «idiomas» y «formas»")
    if datos.get("schema_version") != VERSION_ESQUEMA:
        raise ErrorValidacion(f"{ruta}: schema_version debe ser «{VERSION_ESQUEMA}»")
    idiomas_crudo = datos.get("idiomas")
    if not isinstance(idiomas_crudo, dict) or not idiomas_crudo:
        raise ErrorValidacion(f"{ruta}: «idiomas» debe ser un mapa no vacío")
    idiomas: dict[str, list[str]] = {}
    pais_idioma: dict[str, str] = {}
    for idioma, ficha in idiomas_crudo.items():
        if not (isinstance(idioma, str) and _RE_IDIOMA.fullmatch(idioma)):
            raise ErrorValidacion(f"{ruta}: idioma inválido {idioma!r} (dos letras minúsculas)")
        paises = ficha.get("paises") if isinstance(ficha, dict) else None
        if not isinstance(paises, list) or not paises:
            raise ErrorValidacion(f"{ruta}: idiomas.{idioma}.paises debe ser una lista no vacía")
        for pais in paises:
            if not (isinstance(pais, str) and _RE_PAIS.fullmatch(pais)):
                raise ErrorValidacion(f"{ruta}: idiomas.{idioma}.paises: país ISO-2 esperado, llegó {pais!r} "
                                      "(entrecomille los códigos: en YAML «NO» se lee como falso)")
            if pais in pais_idioma:
                raise ErrorValidacion(f"{ruta}: el país {pais} está en dos idiomas ({pais_idioma[pais]} y {idioma})")
            pais_idioma[pais] = idioma
        idiomas[idioma] = list(paises)
    formas_crudo = datos.get("formas")
    if not isinstance(formas_crudo, list) or not formas_crudo:
        raise ErrorValidacion(f"{ruta}: «formas» debe ser una lista no vacía")
    formas: list[dict[str, Any]] = []
    ids: set[str] = set()
    vistas: dict[str, dict[str, str]] = {idioma: {} for idioma in idiomas}   # idioma -> {frase_casefold: dónde}
    for i, forma in enumerate(formas_crudo):
        cam = f"formas[{i}]"
        if not isinstance(forma, dict):
            raise ErrorValidacion(f"{ruta}: {cam} debe ser un mapa")
        fid = forma.get("id")
        if not (isinstance(fid, str) and qid_valido(fid)):
            raise ErrorValidacion(f"{ruta}: {cam}.id debe ser kebab-case ASCII, llegó {fid!r}")
        if fid in ids:
            raise ErrorValidacion(f"{ruta}: forma repetida «{fid}»")
        ids.add(fid)
        descripcion = forma.get("descripcion", "")
        if not isinstance(descripcion, str):
            raise ErrorValidacion(f"{ruta}: {cam}.descripcion debe ser texto")
        frases_crudo = forma.get("frases")
        if not isinstance(frases_crudo, dict) or set(frases_crudo) != set(idiomas):
            raise ErrorValidacion(f"{ruta}: {cam} ({fid}) debe tener frases en exactamente los idiomas {sorted(idiomas)}")
        frases: dict[str, dict[str, Any]] = {}
        for idioma in idiomas:
            f = frases_crudo[idioma]
            if not isinstance(f, dict) or set(f) != {"principal", "variantes"}:
                raise ErrorValidacion(f"{ruta}: {fid}.{idioma} debe tener exactamente «principal» y «variantes»")
            principal = _frase(f["principal"], f"{fid}.{idioma}.principal")
            if not isinstance(f["variantes"], list):
                raise ErrorValidacion(f"{ruta}: {fid}.{idioma}.variantes debe ser una lista")
            variantes = [_frase(v, f"{fid}.{idioma}.variantes[{k}]") for k, v in enumerate(f["variantes"])]
            for frase in [principal, *variantes]:
                clave = frase.casefold()
                if clave in vistas[idioma]:
                    raise ErrorValidacion(f"{ruta}: la frase «{frase}» ({idioma}) se repite en {fid} y en {vistas[idioma][clave]}")
                vistas[idioma][clave] = fid
            frases[idioma] = {"principal": principal, "variantes": variantes}
        formas.append({"id": fid, "descripcion": descripcion, "frases": frases})
    return {"idiomas": idiomas, "pais_idioma": pais_idioma, "formas": formas}


def _forma_por_id(banco: Mapping[str, Any], forma_id: str) -> Mapping[str, Any]:
    for forma in banco["formas"]:
        if forma["id"] == forma_id:
            return forma
    raise ErrorValidacion(f"la forma «{forma_id}» no está en el banco de frases")


# ---------------------------------------------------------------------------
# Construcción de consultas
# ---------------------------------------------------------------------------

def _consulta(qid: str, terminos: str | None, pais: str, idioma: str, forma_id: str | None, limite: int,
              page_ids: list[str] | None, pasada: int) -> dict[str, Any]:
    return {"qid": qid, "search_terms": terminos, "countries": [pais], "idioma": idioma, "forma_id": forma_id,
            "ad_active_status": ESTADO_ACTIVO, "limit": limite, "page_ids": page_ids, "pasada": pasada}


def _seleccionar_paises(paises: Any, origen: Sequence[str], banco: Mapping[str, Any]) -> list[str]:
    """Países pedidos, ordenados por su posición en `barrido_paises_origen` (los que no figuran, después, en el orden dado)."""
    if paises is None:
        return list(origen)
    if isinstance(paises, str) or not isinstance(paises, Iterable):
        raise ErrorUso("paises: se esperaba una lista de países ISO-2 (o None para usar barrido_paises_origen)")
    lista = list(paises)
    if not lista:
        raise ErrorUso("paises: lista vacía, el plan no tendría consultas")
    for p in lista:
        if not (isinstance(p, str) and _RE_PAIS.fullmatch(p)):
            raise ErrorUso(f"paises: país ISO-2 en mayúsculas esperado, llegó {p!r}")
        if p not in banco["pais_idioma"]:
            raise ErrorUso(f"paises: {p} no tiene idioma ni frases en frases_forma.yaml")
    if len(set(lista)) != len(lista):
        raise ErrorUso("paises: países repetidos")
    posicion = {p: i for i, p in enumerate(origen)}
    ordenados = sorted(enumerate(lista), key=lambda par: (posicion.get(par[1], len(origen)), par[0]))
    return [p for _, p in ordenados]


def _seleccionar_formas(formas: Any, banco: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Formas pedidas, siempre en el orden del banco (así el mismo conjunto da el mismo plan)."""
    if formas is None:
        return list(banco["formas"])
    if isinstance(formas, str) or not isinstance(formas, Iterable):
        raise ErrorUso("formas: se esperaba una lista de ids de forma (o None para todas)")
    pedidas = list(formas)
    if not pedidas:
        raise ErrorUso("formas: lista vacía, el plan no tendría consultas")
    conocidas = {f["id"] for f in banco["formas"]}
    desconocidas = [f for f in pedidas if f not in conocidas]
    if desconocidas:
        raise ErrorUso(f"formas: no existen en frases_forma.yaml: {desconocidas}")
    if len(set(pedidas)) != len(pedidas):
        raise ErrorUso("formas: ids repetidos")
    return [f for f in banco["formas"] if f["id"] in set(pedidas)]


def generar_plan(corrida_id: str, *, paises: Sequence[str] | None, formas: Sequence[str] | None,
                 par_barrido: Mapping[str, Any], par_modelado: Mapping[str, Any], ahora: datetime,
                 banco: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Pasada 1: una consulta por (país × forma), un país por consulta, frase `principal` en el idioma del país.

    `paises=None` usa todo `barrido_paises_origen`; `formas=None`, todas las del banco. El orden de las consultas es
    país (según `barrido_paises_origen`) y luego forma (según el banco): el mismo conjunto da siempre el mismo plan.
    Falla con ErrorLimite (código 5) si faltan parámetros o si el plan excede `modelado_max_consultas_por_corrida`;
    con ErrorUso (2) si un país o una forma no existe. El reloj es `ahora` (datetime con zona UTC).
    """
    if not corrida_id_valido(corrida_id):
        raise ErrorUso(f"corrida_id inválido {corrida_id!r}: se espera AAAA-MM-DD-<letra> (p. ej. 2026-11-06-a)")
    par = _unir(par_barrido, par_modelado)
    tope = _entero_param(par, CLAVE_TOPE)
    limite = _entero_param(par, "barrido_limite_por_consulta")
    origen = _paises_param(par, "barrido_paises_origen")
    banco = banco if banco is not None else cargar_banco()
    elegidos = _seleccionar_paises(paises, origen, banco)
    seleccion = _seleccionar_formas(formas, banco)
    total = len(elegidos) * len(seleccion)
    if total > tope:
        raise ErrorLimite(f"el plan tendría {total} consultas ({len(elegidos)} países × {len(seleccion)} formas) y el "
                          f"tope es {tope} ({CLAVE_TOPE}): reduzca países o formas, o apruebe otro tope")
    consultas = []
    for pais in elegidos:
        idioma = banco["pais_idioma"][pais]
        for forma in seleccion:
            consultas.append(_consulta(f"{pais.lower()}-{forma['id']}", forma["frases"][idioma]["principal"], pais,
                                       idioma, forma["id"], limite, None, PASADA_FORMA))
    doc = {"schema_version": VERSION_ESQUEMA, "corrida_id": corrida_id, "creado_en": iso_z(ahora),
           "tope_consultas": tope, "consultas": consultas}
    return validar_plan(doc, par)


# ---------------------------------------------------------------------------
# Validación y archivos
# ---------------------------------------------------------------------------

def _claves(valor: Any, campo: str, esperadas: Sequence[str]) -> Mapping[str, Any]:
    if not isinstance(valor, Mapping):
        raise ErrorValidacion(f"{campo}: se esperaba un objeto, llegó {type(valor).__name__}")
    faltan = [k for k in esperadas if k not in valor]
    sobran = sorted(str(k) for k in valor if k not in esperadas)
    if faltan:
        raise ErrorValidacion(f"{campo}: faltan campos {faltan}")
    if sobran:
        raise ErrorValidacion(f"{campo}: campos no reconocidos {sobran}")
    return valor


def _entero(valor: Any, campo: str, minimo: int) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ErrorValidacion(f"{campo}: se esperaba un entero, llegó {type(valor).__name__} {valor!r}")
    if valor < minimo:
        raise ErrorValidacion(f"{campo}: {valor} es menor que {minimo}")
    return valor


def _validar_consulta(c: Any, i: int, par: Mapping[str, Any], limite: int, pasadas_max: int) -> dict[str, Any]:
    cam = f"consultas[{i}]"
    _claves(c, cam, CAMPOS_CONSULTA)
    qid = c["qid"]
    if not qid_valido(qid):
        raise ErrorValidacion(f"{cam}.qid: se esperaba kebab-case ASCII, llegó {qid!r}")
    paises = c["countries"]
    if not isinstance(paises, list) or len(paises) != 1:
        raise ErrorValidacion(f"{cam}.countries: un país por consulta (lista con un ISO-2), llegó {paises!r}")
    pais = paises[0]
    if not (isinstance(pais, str) and _RE_PAIS.fullmatch(pais)):
        raise ErrorValidacion(f"{cam}.countries[0]: país ISO-2 en mayúsculas esperado, llegó {pais!r}")
    if not qid.startswith(f"{pais.lower()}-"):
        raise ErrorValidacion(f"{cam}.qid: «{qid}» debe empezar por «{pais.lower()}-» (el país de la consulta)")
    if not (isinstance(c["idioma"], str) and _RE_IDIOMA.fullmatch(c["idioma"])):
        raise ErrorValidacion(f"{cam}.idioma: dos letras minúsculas esperadas, llegó {c['idioma']!r}")
    if c["ad_active_status"] != ESTADO_ACTIVO:
        raise ErrorValidacion(f"{cam}.ad_active_status: el barrido solo mira anuncios «{ESTADO_ACTIVO}», llegó {c['ad_active_status']!r}")
    if _entero(c["limit"], f"{cam}.limit", 1) != limite:
        raise ErrorValidacion(f"{cam}.limit: {c['limit']} no coincide con barrido_limite_por_consulta ({limite})")
    pasada = _entero(c["pasada"], f"{cam}.pasada", PASADA_FORMA)
    if pasada > pasadas_max:
        raise ErrorValidacion(f"{cam}.pasada: {pasada} excede barrido_pasadas_max ({pasadas_max})")
    page_ids = c["page_ids"]
    terminos = c["search_terms"]
    forma_id = c["forma_id"]
    if pasada == PASADA_PAGINAS:
        if not isinstance(page_ids, list) or not page_ids:
            raise ErrorValidacion(f"{cam}.page_ids: la pasada {pasada} exige una lista no vacía de page_ids")
        for k, p in enumerate(page_ids):
            if not (isinstance(p, str) and _RE_DIGITOS.fullmatch(p)):
                raise ErrorValidacion(f"{cam}.page_ids[{k}]: cadena de dígitos esperada, llegó {p!r}")
        if len(set(page_ids)) != len(page_ids):
            raise ErrorValidacion(f"{cam}.page_ids: page_ids repetidos")
        maximo = _entero_param(par, "barrido_page_ids_por_consulta_max")
        if len(page_ids) > maximo:
            raise ErrorLimite(f"{cam}.page_ids: {len(page_ids)} page_ids exceden barrido_page_ids_por_consulta_max ({maximo})")
        if terminos is not None or forma_id is not None:
            raise ErrorValidacion(f"{cam}: la pasada {pasada} va por page_ids; search_terms y forma_id deben ser null")
    else:
        if page_ids is not None:
            raise ErrorValidacion(f"{cam}.page_ids: la pasada {pasada} no usa page_ids (deben ser null)")
        _frase(terminos, f"{cam}.search_terms")
        if not (isinstance(forma_id, str) and qid_valido(forma_id)):
            raise ErrorValidacion(f"{cam}.forma_id: kebab-case esperado, llegó {forma_id!r}")
    return {"qid": qid, "search_terms": terminos, "countries": [pais], "idioma": c["idioma"], "forma_id": forma_id,
            "ad_active_status": ESTADO_ACTIVO, "limit": limite,
            "page_ids": list(page_ids) if page_ids is not None else None, "pasada": pasada}


def validar_plan(doc: Any, par: Mapping[str, Any]) -> dict[str, Any]:
    """Valida un plan (CONTRATO §3) y devuelve una copia normalizada.

    `par` es el mapa de parámetros unido: `{**par_barrido, **par_modelado}` (usa `barrido_limite_por_consulta`,
    `barrido_pasadas_max`, `modelado_max_consultas_por_corrida` y, si hay pasada 3, `barrido_page_ids_por_consulta_max`).
    Reglas: campos exactos; `schema_version` "1.0.0"; `corrida_id` y `creado_en` válidos; qid kebab, único y que empieza
    por el país; un país por consulta; `limit` = parámetro; solo anuncios ACTIVE; pasada ≤ `barrido_pasadas_max`; pasadas 1-2 con
    frase y sin page_ids, pasada 3 con page_ids y sin frase; ninguna consulta repetida. **`len(consultas)` ≤ `tope_consultas`
    ≤ `modelado_max_consultas_por_corrida`: excederlo = ErrorLimite (código 5).**
    """
    limite = _entero_param(par, "barrido_limite_por_consulta")
    if limite > LIMITE_MAX_CONECTOR:
        raise ErrorLimite(f"barrido_limite_por_consulta: {limite} excede el máximo del conector ({LIMITE_MAX_CONECTOR})")
    pasadas_max = _entero_param(par, "barrido_pasadas_max")
    tope_param = _entero_param(par, CLAVE_TOPE)
    _claves(doc, "plan", CAMPOS_PLAN)
    if doc["schema_version"] != VERSION_ESQUEMA:
        raise ErrorValidacion(f"plan.schema_version: se esperaba «{VERSION_ESQUEMA}», llegó {doc['schema_version']!r}")
    if not corrida_id_valido(doc["corrida_id"]):
        raise ErrorValidacion(f"plan.corrida_id: se esperaba AAAA-MM-DD-<letra>, llegó {doc['corrida_id']!r}")
    parsear_z(doc["creado_en"])
    tope = _entero(doc["tope_consultas"], "plan.tope_consultas", 1)
    if tope > tope_param:
        raise ErrorLimite(f"plan.tope_consultas ({tope}) excede {CLAVE_TOPE} ({tope_param})")
    consultas = doc["consultas"]
    if not isinstance(consultas, list) or not consultas:
        raise ErrorValidacion("plan.consultas: se esperaba una lista no vacía")
    if len(consultas) > tope:
        raise ErrorLimite(f"el plan tiene {len(consultas)} consultas y el tope es {tope} ({CLAVE_TOPE}): "
                          "excederlo es un límite duro")
    normalizadas: list[dict[str, Any]] = []
    qids: set[str] = set()
    busquedas: set[tuple[Any, ...]] = set()
    for i, c in enumerate(consultas):
        ok = _validar_consulta(c, i, par, limite, pasadas_max)
        if ok["qid"] in qids:
            raise ErrorValidacion(f"consultas[{i}].qid: «{ok['qid']}» repetido")
        qids.add(ok["qid"])
        huella = (ok["countries"][0], (ok["search_terms"] or "").casefold(), tuple(ok["page_ids"] or ()))
        if huella in busquedas:
            raise ErrorValidacion(f"consultas[{i}]: repite la búsqueda de otra consulta (mismo país, frase y page_ids)")
        busquedas.add(huella)
        normalizadas.append(ok)
    return {"schema_version": VERSION_ESQUEMA, "corrida_id": doc["corrida_id"], "creado_en": doc["creado_en"],
            "tope_consultas": tope, "consultas": normalizadas}


def ruta_plan(corrida_id: str, pasada: int = PASADA_FORMA, raiz: Path | None = None) -> Path:
    """`empresa/barrido/planes/<corrida_id>.json` (pasada 1) o `<corrida_id>.pasada-<n>.json` (plan acumulado)."""
    if not corrida_id_valido(corrida_id):
        raise ErrorUso(f"corrida_id inválido {corrida_id!r}")
    nombre = f"{corrida_id}.json" if pasada == PASADA_FORMA else f"{corrida_id}.pasada-{pasada}.json"
    return dir_barrido(raiz) / "planes" / nombre


def escribir_plan(plan: Mapping[str, Any], par: Mapping[str, Any], *, raiz: Path | None = None) -> Path:
    """Valida y escribe el plan SIN sobrescribir (`comun.escribir_json_nuevo`; existente = ErrorUso).

    El archivo lleva el nombre de la pasada más alta que contiene (ver `ruta_plan`). Devuelve la ruta escrita.
    """
    doc = validar_plan(plan, par)
    ruta = ruta_plan(doc["corrida_id"], max(c["pasada"] for c in doc["consultas"]), raiz)
    escribir_json_nuevo(ruta, doc)
    return ruta


def cargar_plan(corrida_id: str, par: Mapping[str, Any], *, raiz: Path | None = None) -> dict[str, Any]:
    """Lee y valida el plan acumulado más reciente de la corrida (el de la pasada más alta que exista en disco)."""
    pasadas_max = _entero_param(par, "barrido_pasadas_max")
    for pasada in range(pasadas_max, 0, -1):
        ruta = ruta_plan(corrida_id, pasada, raiz)
        if ruta.is_file():
            doc = validar_plan(leer_json(ruta), par)
            if doc["corrida_id"] != corrida_id:
                raise ErrorValidacion(f"{ruta}: el corrida_id del contenido ({doc['corrida_id']}) no coincide con el nombre")
            return doc
    raise ErrorUso(f"no hay plan para la corrida {corrida_id} en {dir_barrido(raiz) / 'planes'}")


def ampliar_plan(plan: Mapping[str, Any], nuevas: Sequence[Mapping[str, Any]], par: Mapping[str, Any], *,
                 ahora: datetime) -> dict[str, Any]:
    """Plan acumulado = plan + consultas nuevas (de `siguiente_pasada`), con `creado_en` = `ahora`.

    Pasarse del tope o repetir una búsqueda/qid falla (ErrorLimite / ErrorValidacion): no se recorta en silencio.
    """
    base = validar_plan(plan, par)
    if not isinstance(nuevas, Sequence) or isinstance(nuevas, (str, bytes)):
        raise ErrorUso("nuevas: se esperaba la lista que devuelve siguiente_pasada")
    doc = copy.deepcopy(base)
    doc["creado_en"] = iso_z(ahora)
    doc["consultas"].extend(copy.deepcopy(list(nuevas)))
    return validar_plan(doc, par)


# ---------------------------------------------------------------------------
# Pasadas 2 y 3
# ---------------------------------------------------------------------------

def _digitos_id(valor: Any, campo: str) -> str:
    if isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0:
        valor = str(valor)
    if not (isinstance(valor, str) and _RE_DIGITOS.fullmatch(valor)):
        raise ErrorValidacion(f"{campo}: se esperaba un id de dígitos, llegó {valor!r}")
    return valor


def _indexar_consultas(resumenes: Any) -> dict[str, tuple[int | None, int]]:
    lista = resumenes.get("consultas") if isinstance(resumenes, Mapping) else None
    if not isinstance(lista, list):
        raise ErrorValidacion("resumenes: falta «consultas» (lista de {qid, estimated_total_count, n_anuncios})")
    indice: dict[str, tuple[int | None, int]] = {}
    for i, r in enumerate(lista):
        cam = f"resumenes.consultas[{i}]"
        _claves(r, cam, ("qid", "estimated_total_count", "n_anuncios"))
        if not qid_valido(r["qid"]):
            raise ErrorValidacion(f"{cam}.qid inválido {r['qid']!r}")
        if r["qid"] in indice:
            raise ErrorValidacion(f"{cam}.qid «{r['qid']}» repetido")
        total = r["estimated_total_count"]
        if total is not None:
            total = _entero(total, f"{cam}.estimated_total_count", 0)
        indice[r["qid"]] = (total, _entero(r["n_anuncios"], f"{cam}.n_anuncios", 0))
    return indice


def _indexar_paginas(resumenes: Any) -> list[tuple[str, int]]:
    lista = resumenes.get("paginas") if isinstance(resumenes, Mapping) else None
    if not isinstance(lista, list):
        raise ErrorValidacion("resumenes: falta «paginas» (lista de {page_id, anuncios_activos_en_muestra})")
    vistas: dict[str, int] = {}
    for i, r in enumerate(lista):
        cam = f"resumenes.paginas[{i}]"
        if not isinstance(r, Mapping) or "page_id" not in r or "anuncios_activos_en_muestra" not in r:
            raise ErrorValidacion(f"{cam}: faltan page_id o anuncios_activos_en_muestra")
        pid = _digitos_id(r["page_id"], f"{cam}.page_id")
        if pid in vistas:
            raise ErrorValidacion(f"{cam}.page_id «{pid}» repetido")
        vistas[pid] = _entero(r["anuncios_activos_en_muestra"], f"{cam}.anuncios_activos_en_muestra", 0)
    return list(vistas.items())


def resumenes_desde_crudos(crudos: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Arma `resumenes` para `siguiente_pasada` a partir de crudos YA validados (`comun.validar_crudo`).

    `consultas`: por qid, `estimated_total_count` y `n_anuncios`. `paginas`: por page_id, los anuncios distintos vistos en
    toda la corrida (`anuncios_activos_en_muestra`, un piso: la muestra son los 50 más recientes). Ordenado: determinista.
    """
    consultas: list[dict[str, Any]] = []
    anuncios_por_pagina: dict[str, set[str]] = {}
    for crudo in crudos:
        consultas.append({"qid": crudo["qid"], "estimated_total_count": crudo["estimated_total_count"],
                          "n_anuncios": len(crudo["ads"])})
        for ad in crudo["ads"]:
            anuncios_por_pagina.setdefault(_digitos_id(ad["page_id"], "ads.page_id"), set()).add(str(ad["id"]))
    consultas.sort(key=lambda r: r["qid"])
    paginas = [{"page_id": pid, "anuncios_activos_en_muestra": len(ids)}
               for pid, ids in sorted(anuncios_por_pagina.items())]
    return {"consultas": consultas, "paginas": paginas}


def _clave_frase(texto: str) -> str:
    return unicodedata.normalize("NFC", texto).strip().casefold()


def _forma_por_frase(banco: Mapping[str, Any], idioma: str, frase: Any) -> Mapping[str, Any] | None:
    """Forma del banco cuya frase principal o variante (en `idioma`) es `frase`; None si ninguna."""
    if not isinstance(frase, str):
        return None
    clave = _clave_frase(frase)
    for forma in banco["formas"]:
        f = forma["frases"].get(idioma)
        if f is not None and clave in {_clave_frase(x) for x in [f["principal"], *f["variantes"]]}:
            return forma
    return None


def _frases_para_partir(c: Mapping[str, Any], banco: Mapping[str, Any], informe: dict[str, Any]) -> list[str]:
    """Frases alternativas (todas las de la forma menos la que ya usa la consulta) para partir `c`.

    Forma del banco: las de esa forma. Forma desconocida (p. ej. un plan reconstruido con nombres hechos a mano): se anota en
    `informe["forma_desconocida"]` y se intenta reconocer la forma por la frase tal como está en la consulta; si tampoco así,
    no se parte y la consulta queda en `informe["sin_variantes"]`. Nunca aborta: una consulta rara no tumba a las demás."""
    forma = None
    try:
        forma = _forma_por_id(banco, c["forma_id"])
    except ErrorValidacion:
        informe["forma_desconocida"].append(c["qid"])
        forma = _forma_por_frase(banco, c["idioma"], c["search_terms"])
        if forma is not None:
            informe["rescatadas_por_frase"].append(c["qid"])
    try:
        if forma is None:
            raise ErrorValidacion(f"{c['qid']}: ninguna forma del banco reconoce esta consulta")
        if c["idioma"] not in forma["frases"]:
            raise ErrorValidacion(f"{c['qid']}: la forma «{forma['id']}» no tiene frases en «{c['idioma']}»")
    except ErrorValidacion:
        informe["sin_variantes"].append(c["qid"])
        return []
    f = forma["frases"][c["idioma"]]
    propia = _clave_frase(c["search_terms"])
    alternativas = [x for x in [f["principal"], *f["variantes"]] if _clave_frase(x) != propia]
    if not alternativas:
        informe["sin_variantes"].append(c["qid"])
    return alternativas


def _proponer_particiones(plan: Mapping[str, Any], resumenes: Any, par: Mapping[str, Any],
                          banco: Mapping[str, Any], informe: dict[str, Any]) -> list[dict[str, Any]]:
    umbral = _entero_param(par, "barrido_partir_si_total_supera")
    maximo = _entero_param(par, "barrido_variantes_por_particion_max")
    indice = _indexar_consultas(resumenes)
    qids = {c["qid"] for c in plan["consultas"]}
    busquedas = {(c["countries"][0], (c["search_terms"] or "").casefold()) for c in plan["consultas"]}
    desbordadas: list[tuple[int, Mapping[str, Any]]] = []
    for c in plan["consultas"]:
        if c["pasada"] != PASADA_FORMA:
            continue
        if c["qid"] not in indice:
            informe["sin_resumen"].append(c["qid"])
            continue
        total, n = indice[c["qid"]]
        if total is None:
            informe["sin_total"].append(c["qid"])
        elif total > umbral and n >= c["limit"]:
            desbordadas.append((total, c))
    desbordadas.sort(key=lambda t: (-t[0], t[1]["qid"]))     # primero las que más anuncios ocultan
    nuevas: list[dict[str, Any]] = []
    for _, c in desbordadas:
        variantes = _frases_para_partir(c, banco, informe)[:maximo]
        for k, frase in enumerate(variantes, start=1):
            qid = f"{c['qid']}-v{k}"
            clave = (c["countries"][0], frase.casefold())
            if qid in qids or clave in busquedas:
                informe["repetidas"] += 1
                continue
            qids.add(qid)
            busquedas.add(clave)
            nuevas.append(_consulta(qid, frase, c["countries"][0], c["idioma"], c["forma_id"], c["limit"], None,
                                    PASADA_PARTICION))
    return nuevas


def _proponer_paginas(plan: Mapping[str, Any], resumenes: Any, par: Mapping[str, Any],
                      banco: Mapping[str, Any], informe: dict[str, Any]) -> list[dict[str, Any]]:
    minimo = _entero_param(par, "barrido_pasada3_min_anuncios_muestra")
    max_paginas = _entero_param(par, "barrido_pasada3_paginas_max")
    por_consulta = _entero_param(par, "barrido_page_ids_por_consulta_max")
    limite = _entero_param(par, "barrido_limite_por_consulta")
    presencia = _paises_param(par, "barrido_paises_presencia")
    sin_idioma = [p for p in presencia if p not in banco["pais_idioma"]]
    if sin_idioma:
        raise ErrorValidacion(f"barrido_paises_presencia incluye países sin idioma en frases_forma.yaml: {sin_idioma}")
    elegibles = sorted(((pid, n) for pid, n in _indexar_paginas(resumenes) if n >= minimo),
                       key=lambda t: (-t[1], t[0]))[:max_paginas]            # más anuncios primero; empate por id
    qids = {c["qid"] for c in plan["consultas"]}
    nuevas: list[dict[str, Any]] = []
    for desde in range(0, len(elegibles), por_consulta):
        lote = [pid for pid, _ in elegibles[desde:desde + por_consulta]]
        huella = hashlib.sha1(",".join(sorted(lote)).encode("ascii")).hexdigest()[:LARGO_HUELLA_QID]
        for pais in presencia:
            qid = f"{pais.lower()}-pag-{huella}"
            if qid in qids:
                informe["repetidas"] += 1
                continue
            qids.add(qid)
            nuevas.append(_consulta(qid, None, pais, banco["pais_idioma"][pais], None, limite, list(lote),
                                    PASADA_PAGINAS))
    return nuevas


def siguiente_pasada(plan: Mapping[str, Any], resumenes: Mapping[str, Any], *, par_barrido: Mapping[str, Any],
                     par_modelado: Mapping[str, Any], banco: Mapping[str, Any] | None = None,
                     pasada: int | None = None, informe: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Consultas NUEVAS de la pasada siguiente (no modifica `plan`; ver `ampliar_plan`). Nunca pasa del tope.

    `resumenes` = `{"consultas": [{qid, estimated_total_count, n_anuncios}], "paginas": [{page_id,
    anuncios_activos_en_muestra}]}` (lo arma `resumenes_desde_crudos`; `paginas` también acepta la lista de la ingesta).
    Pasada 2 (por defecto tras la 1): consultas de la pasada 1 con `estimated_total_count` > `barrido_partir_si_total_supera`
    y muestra que llegó al límite, partidas en hasta `barrido_variantes_por_particion_max` variantes de frase.
    Pasada 3 (tras la 2; se puede pedir con `pasada=3` si la 2 no hizo falta): páginas con ≥
    `barrido_pasada3_min_anuncios_muestra` anuncios en la muestra, hasta `barrido_pasada3_paginas_max`, en lotes de
    `barrido_page_ids_por_consulta_max`, por cada país de `barrido_paises_presencia`.
    Si la pasada pedida excede `barrido_pasadas_max`, devuelve []. Se recorta al cupo que queda del tope de la corrida
    (`modelado_max_consultas_por_corrida` menos las consultas del plan), con prioridad por mayor ocultamiento / más anuncios.
    Un plan reconstruido puede traer `forma_id` que no están en el banco: esas consultas se anotan en
    `informe["forma_desconocida"]`, se intenta reconocer su forma por la frase (`rescatadas_por_frase`) y las que no se
    pueden partir quedan en `sin_variantes`; nunca se aborta por ellas.
    `informe` (opcional): se llena con pasada, candidatas, propuestas, omitidas_por_tope, sin_resumen, sin_total, repetidas,
    forma_desconocida, rescatadas_por_frase y sin_variantes.
    """
    par = _unir(par_barrido, par_modelado)
    plan = validar_plan(plan, par)
    banco = banco if banco is not None else cargar_banco()
    pasadas_max = _entero_param(par, "barrido_pasadas_max")
    ultima = max(c["pasada"] for c in plan["consultas"])
    destino = ultima + 1 if pasada is None else pasada
    if isinstance(destino, bool) or not isinstance(destino, int) or destino <= PASADA_FORMA:
        raise ErrorUso(f"pasada: debe ser {PASADA_PARTICION} o {PASADA_PAGINAS} (la pasada {PASADA_FORMA} la hace generar_plan)")
    estado: dict[str, Any] = {"pasada": destino, "candidatas": 0, "propuestas": 0, "omitidas_por_tope": 0,
                              "sin_resumen": [], "sin_total": [], "repetidas": 0,
                              "forma_desconocida": [], "rescatadas_por_frase": [], "sin_variantes": []}
    try:
        if destino > pasadas_max:
            return []
        if destino == PASADA_PARTICION:
            candidatas = _proponer_particiones(plan, resumenes, par, banco, estado)
        elif destino == PASADA_PAGINAS:
            candidatas = _proponer_paginas(plan, resumenes, par, banco, estado)
        else:
            raise ErrorUso(f"pasada {destino}: solo existen las pasadas {PASADA_FORMA} a {PASADA_PAGINAS}")
        cupo = max(plan["tope_consultas"] - len(plan["consultas"]), 0)
        propuestas = candidatas[:cupo]
        estado["candidatas"] = len(candidatas)
        estado["propuestas"] = len(propuestas)
        estado["omitidas_por_tope"] = len(candidatas) - len(propuestas)
        return propuestas
    finally:
        if informe is not None:
            informe.update(estado)


# ---------------------------------------------------------------------------
# Reparto entre agentes
# ---------------------------------------------------------------------------

def _qids_del_plan(plan: Mapping[str, Any], qids: Sequence[str] | None) -> list[str]:
    if not isinstance(plan, Mapping) or not isinstance(plan.get("consultas"), list):
        raise ErrorUso("plan: se esperaba el dict de un plan (con «consultas»)")
    todos = [c["qid"] for c in plan["consultas"]]
    if qids is None:
        return todos
    if isinstance(qids, str) or not isinstance(qids, Sequence):
        raise ErrorUso("qids: se esperaba una lista de qid")
    lista = list(qids)
    if len(set(lista)) != len(lista):
        raise ErrorUso("qids: qid repetidos")
    ajenos = [q for q in lista if q not in set(todos)]
    if ajenos:
        raise ErrorUso(f"qids: no están en el plan: {ajenos}")
    return lista


def _round_robin(lista: Sequence[str], k: int) -> list[list[str]]:
    grupos: list[list[str]] = [[] for _ in range(k)]
    for i, qid in enumerate(lista):
        grupos[i % k].append(qid)
    return grupos


def repartir_en_agentes(plan: Mapping[str, Any], n: int, *, par_barrido: Mapping[str, Any],
                        qids: Sequence[str] | None = None) -> list[list[str]]:
    """Reparte las consultas (todas o las `qids` dadas) entre `n` agentes: equilibrado (tamaños que difieren a lo sumo en
    uno), en orden alterno (cada agente mezcla países y formas) y con ≤ `barrido_consultas_por_agente_max` cada uno.

    Devuelve `min(n, #consultas)` listas. Si `n` agentes no alcanzan para respetar el máximo por agente, o `n` excede
    `barrido_agentes_paralelos_max`, falla con ErrorLimite (use `repartir_en_olas`): no se recorta ni se sobrecarga a nadie.
    """
    por_agente = _entero_param(par_barrido, "barrido_consultas_por_agente_max")
    paralelos = _entero_param(par_barrido, "barrido_agentes_paralelos_max")
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ErrorUso(f"n: se esperaba un entero ≥ 1 (agentes), llegó {n!r}")
    if n > paralelos:
        raise ErrorLimite(f"{n} agentes exceden barrido_agentes_paralelos_max ({paralelos}); use repartir_en_olas")
    lista = _qids_del_plan(plan, qids)
    if not lista:
        return []
    k = min(n, len(lista))
    necesarios = (len(lista) + por_agente - 1) // por_agente
    if k < necesarios:
        raise ErrorLimite(f"{len(lista)} consultas con ≤ {por_agente} por agente (barrido_consultas_por_agente_max) "
                          f"exigen al menos {necesarios} agentes y se pidieron {n}; use repartir_en_olas")
    return _round_robin(lista, k)


def repartir_en_olas(plan: Mapping[str, Any], *, par_barrido: Mapping[str, Any],
                     qids: Sequence[str] | None = None) -> list[list[list[str]]]:
    """Reparto completo: el mínimo de agentes que respeta `barrido_consultas_por_agente_max`, equilibrados, en olas de a
    lo sumo `barrido_agentes_paralelos_max` agentes simultáneos. `olas[i][j]` = qids del agente j de la ola i."""
    por_agente = _entero_param(par_barrido, "barrido_consultas_por_agente_max")
    paralelos = _entero_param(par_barrido, "barrido_agentes_paralelos_max")
    lista = _qids_del_plan(plan, qids)
    if not lista:
        return []
    agentes = _round_robin(lista, (len(lista) + por_agente - 1) // por_agente)
    return [agentes[desde:desde + paralelos] for desde in range(0, len(agentes), paralelos)]


# ---------------------------------------------------------------------------
# Prompt de un agente de barrido (plantilla: agente_barrido.md)
# ---------------------------------------------------------------------------

def cargar_plantilla(ruta: Path | None = None) -> str:
    """Texto del prompt entre `<!-- PROMPT:INICIO -->` y `<!-- PROMPT:FIN -->` de `agente_barrido.md`.

    Exige exactamente los marcadores `{{CORRIDA_ID}}`, `{{RAIZ}}`, `{{TOTAL}}` y `{{CONSULTAS}}` (ni uno más ni uno menos).
    """
    ruta = Path(ruta) if ruta is not None else RUTA_PLANTILLA
    try:
        texto = ruta.read_text(encoding="utf-8")
    except OSError as exc:
        raise ErrorUso(f"no se pudo leer la plantilla {ruta}: {exc}") from exc
    lineas = texto.splitlines()
    inicios = [i for i, l in enumerate(lineas) if l.strip() == MARCA_INICIO]
    fines = [i for i, l in enumerate(lineas) if l.strip() == MARCA_FIN]
    if len(inicios) != 1 or len(fines) != 1:
        raise ErrorValidacion(f"{ruta}: debe tener, cada una en su propia línea y una sola vez, {MARCA_INICIO} y {MARCA_FIN}")
    if fines[0] < inicios[0]:
        raise ErrorValidacion(f"{ruta}: {MARCA_FIN} aparece antes de {MARCA_INICIO}")
    cuerpo = "\n".join(lineas[inicios[0] + 1:fines[0]]).strip("\n")
    hallados = _RE_MARCADOR.findall(cuerpo)
    if sorted(set(hallados)) != sorted(MARCADORES_PLANTILLA):
        raise ErrorValidacion(f"{ruta}: los marcadores de la plantilla deben ser {list(MARCADORES_PLANTILLA)}, "
                              f"hay {sorted(set(hallados))}")
    return cuerpo


def _bloque_consulta(c: Mapping[str, Any], k: int, total: int, carpeta: Path) -> str:
    consulta = {"search_terms": c["search_terms"], "countries": list(c["countries"]),
                "ad_active_status": c["ad_active_status"], "limit": c["limit"], "page_ids": c["page_ids"]}
    return "\n".join([
        f"[{k}/{total}] qid: {c['qid']}",
        f"  archivo de salida: {carpeta / (c['qid'] + '.json')}",
        f"  archivo de error:  {carpeta / (c['qid'] + '.error.json')}",
        f"  consulta (úsala para llamar a la herramienta y cópiala igual en el campo «consulta» del crudo): "
        f"{json.dumps(consulta, ensure_ascii=False)}",
    ])


def _verificar_consulta_propia(c: Mapping[str, Any], banco: Mapping[str, Any], frase_del_plan_confiable: bool) -> None:
    """Falla (ErrorValidacion) si la consulta trae algo que no sea del sistema: el prompt de un agente solo puede llevar
    qid kebab, un país ISO-2, una frase DEL BANCO (o ninguna), dígitos de page_id y el límite. Nada que venga de la Biblioteca
    (ni de un crudo reconstruido) llega a un prompt ni, por tanto, a una línea de comandos."""
    qid = c.get("qid")
    if not qid_valido(qid):
        raise ErrorValidacion("consulta del plan con qid inválido: no se inserta en el prompt de un agente")
    paises = c.get("countries")
    if not (isinstance(paises, list) and len(paises) == 1 and isinstance(paises[0], str) and _RE_PAIS.fullmatch(paises[0])):
        raise ErrorValidacion(f"{qid}: país inválido, no se inserta en el prompt de un agente")
    if c.get("ad_active_status") != ESTADO_ACTIVO:
        raise ErrorValidacion(f"{qid}: ad_active_status inválido, no se inserta en el prompt de un agente")
    limite = c.get("limit")
    if isinstance(limite, bool) or not isinstance(limite, int) or limite < 1:
        raise ErrorValidacion(f"{qid}: limit inválido, no se inserta en el prompt de un agente")
    page_ids = c.get("page_ids")
    if page_ids is not None:
        if not (isinstance(page_ids, list) and page_ids and all(isinstance(p, str) and _RE_DIGITOS.fullmatch(p) for p in page_ids)):
            raise ErrorValidacion(f"{qid}: page_ids inválidos (solo cadenas de dígitos), no se insertan en el prompt")
        if c.get("search_terms") is not None:
            raise ErrorValidacion(f"{qid}: una consulta por page_ids no lleva frase, no se inserta en el prompt")
        return
    terminos = c.get("search_terms")
    if frase_del_plan_confiable:        # decisión explícita de quien orquesta (plan armado a mano): solo se exige una frase limpia
        _frase(terminos, f"{qid}.search_terms")
        return
    forma = _forma_por_id(banco, c.get("forma_id")) if isinstance(c.get("forma_id"), str) else None
    if forma is None or c.get("idioma") not in forma["frases"]:
        raise ErrorValidacion(f"{qid}: forma o idioma fuera del banco, no se inserta en el prompt de un agente")
    propias = {_clave_frase(f) for f in [forma["frases"][c["idioma"]]["principal"], *forma["frases"][c["idioma"]]["variantes"]]}
    if not (isinstance(terminos, str) and _clave_frase(terminos) in propias):
        raise ErrorValidacion(f"{qid}: la frase no es del banco de frases_forma.yaml (¿viene de un crudo?): "
                              "no se inserta en el prompt de un agente")


def instrucciones_agente(plan: Mapping[str, Any], qids: Sequence[str], *, raiz: Path | None = None,
                         plantilla: str | None = None, banco: Mapping[str, Any] | None = None,
                         frases_del_plan_confiables: bool = False) -> str:
    """Prompt completo para UN agente de barrido: la plantilla de `agente_barrido.md` con la corrida, la raíz absoluta
    del repositorio y la lista de sus consultas. Los valores se insertan en una sola pasada (un `{{...}}` dentro de un
    valor no se vuelve a expandir). Falla con ErrorUso si `qids` está vacío o alguna no pertenece al plan, y con
    ErrorValidacion si una consulta trae algo que no sea del sistema (frase fuera del banco, page_ids que no son dígitos):
    el prompt no lleva datos de la Biblioteca, que es lo que permite que el agente nunca vea texto ajeno en su línea de comandos.
    `frases_del_plan_confiables=True` (por defecto False) es la salida deliberada para un plan armado a mano o reconstruido
    cuyas frases no están en el banco: se exige solo que sean texto sin caracteres de control."""
    if not isinstance(plan, Mapping) or not corrida_id_valido(plan.get("corrida_id")):
        raise ErrorUso("plan: se esperaba el dict de un plan con corrida_id válido")
    lista = _qids_del_plan(plan, qids)
    if not lista:
        raise ErrorUso("qids: un agente sin consultas no tiene nada que ejecutar")
    por_qid = {c["qid"]: c for c in plan["consultas"]}
    banco = banco if banco is not None else cargar_banco()
    for q in lista:
        _verificar_consulta_propia(por_qid[q], banco, frases_del_plan_confiables)
    raiz_abs = (Path(raiz) if raiz is not None else RAIZ).resolve()
    carpeta = raiz_abs / "empresa" / "barrido" / "crudo" / plan["corrida_id"]
    texto = plantilla if plantilla is not None else cargar_plantilla()
    valores = {
        "CORRIDA_ID": plan["corrida_id"],
        "RAIZ": str(raiz_abs),
        "TOTAL": str(len(lista)),
        "CONSULTAS": "\n\n".join(_bloque_consulta(por_qid[q], k, len(lista), carpeta)
                                 for k, q in enumerate(lista, start=1)),
    }

    def sustituir(m: re.Match[str]) -> str:
        if m.group(1) not in valores:
            raise ErrorValidacion(f"plantilla: marcador desconocido {{{{{m.group(1)}}}}}")
        return valores[m.group(1)]

    return _RE_MARCADOR.sub(sustituir, texto)
