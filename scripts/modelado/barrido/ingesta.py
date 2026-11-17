"""Ingesta del barrido por forma (B2): crudos de la Biblioteca → páginas, exportadores e integridad.

Qué hace (contrato: scripts/modelado/barrido/CONTRATO.md §2, §3 y §4):

- `ingestar_corrida`: lee todos los crudos de una corrida (`empresa/barrido/crudo/<corrida_id>/<qid>.json`),
  los valida con `comun.leer_crudo`, deduplica anuncios por `id` entre consultas, agrupa por `page_id` y
  produce el documento «Páginas». Un crudo inválido NO aborta la corrida: se excluye y queda en
  `advertencias` con su ruta; si no queda ningún crudo válido, `ErrorValidacion`.
- `detectar_exportador`: indicio de «probable exportador» (§17.2): cuenta publicitaria en la moneda de un
  país distinto de aquel donde anuncia. Qué monedas implican un país lo decide el parámetro
  `barrido_exportador_monedas_pais`, no el código (USD, moneda genérica, solo cuenta si el mapa la incluye).
- `escribir_paginas`: escribe `empresa/barrido/paginas/<corrida_id>.json` sin sobrescribir.
- `cobertura`: qué consultas del plan están listas, cuáles faltan, cuáles fallaron y cuáles quedaron
  truncadas; es lo que decide la siguiente pasada.

Reglas que no se negocian
-------------------------
- Medición por página (`medicion`): un país está medido por la propia página solo si hay una consulta por
  `page_ids` con ESE único page_id y ese país (fuente «pagina»; usa su `estimated_total_count`); si no, solo
  hay muestra de búsquedas por frase (fuente «muestra»), que nunca prueba que no haya más anuncios. Una consulta
  unipágina que devolvió 0 anuncios en un país mide la AUSENCIA (entrada con `anuncios_vistos` 0; `paises` sigue
  siendo solo presencia). Las consultas con 2+ page_ids no miden (un total para todo el lote es ambiguo).
  `completa` exige todo visto Y que la cifra no esté al tope de la consulta (el total del conector es una
  estimación: 50 de 50 es «parcial»). `estado`: «completa» = todos los países completos; «muestra» = ninguno
  medido por su página; «parcial» = lo demás. `muestra_truncada` = (estado != «completa»).
  `anuncios_activos_medidos` = max(anuncios distintos vistos, mayor cifra por país): cota inferior de anuncios
  DISTINTOS (nunca suma por país: un anuncio en 2 países contaría doble), así `medidos >= anuncios_activos_en_muestra
  >= conceptos_unicos`; es un PISO salvo en «completa». `edad_oferta_dias` sigue saliendo de `resumir_anuncios`
  sobre la unión; `edad_es_piso` avisa que podría haber anuncios ocultos más viejos. El truncado POR CONSULTA
  (límite alcanzado con más resultados) se conserva solo en `advertencias` y en `cobertura`.
- Solo anuncios ACTIVE: un crudo cuya consulta no sea `ad_active_status == ACTIVE` (INACTIVE o ALL, que las rutas
  B, C y D admiten) se excluye con advertencia: no cuenta como anuncios activos.
- La edad de la oferta es la de `puntaje_modelar.resumir_anuncios` (2.º anuncio más viejo; 1 solo anuncio → 0).
  Aquí no se recuenta nada a mano: los conteos y edades salen de esa función, sobre anuncios ya deduplicados.
  Las edades van como cadena decimal exacta (sin redondear, sin float).
- El exportador es un indicio con `motivo` en texto, jamás un hecho.
- Los títulos y nombres de página son dato NO confiable: se copian como texto, nunca se interpretan.
  Los títulos se conservan literales (el etiquetado exige que la evidencia exista tal cual).
- Contraste con el plan (revisión de seguridad M5): si existe un plan para la corrida, `ingestar_corrida` usa el
  más reciente (`plan.cargar_plan`) y RECHAZA la ingesta completa (ErrorValidacion, código 3) si hay un crudo
  cuyo qid no está en el plan o cuya consulta difiere de la planificada (frase, país, límite, estado o page_ids);
  nada de eso entra en las páginas. Único escape documentado: `permitir_fuera_de_plan=True` (esos crudos se
  ingieren y quedan en `advertencias`). Sin plan, se ingiere como siempre y se advierte que no hubo contraste.
  Un plan ilegible o inválido NUNCA equivale a «sin plan»: el error se propaga (falla cerrado).
- Ningún umbral está fijo aquí: `barrido_titulos_por_pagina_max` y `barrido_exportador_monedas_pais` llegan
  por `par_barrido`; si faltan o son raros, falla cerrado (ErrorLimite 5 / ErrorValidacion 3).
- Determinista: mismas entradas y mismo `ahora` → documento idéntico (orden fijo, sin reloj interno).
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from scripts.modelado import puntaje_modelar as pm
from scripts.modelado.barrido import comun
from scripts.modelado.barrido import plan as planes

ErrorLimite = comun.ErrorLimite
ErrorUso = comun.ErrorUso
ErrorValidacion = comun.ErrorValidacion

SCHEMA_VERSION = comun.VERSION_ESQUEMA

# Clave JSON del indicio de exportador. El contrato (§4) la escribe «señal» (con ñ); si se prefiere ASCII,
# este es el único lugar donde cambiarla.
CLAVE_SENAL = "señal"

# Largo máximo del texto de un error ajeno que se copia a `advertencias` (solo presentación, no decisión).
_MAX_MENSAJE = 300

_SUFIJO_ERROR = ".error.json"


# ---------------------------------------------------------------------------
# Utilidades pequeñas
# ---------------------------------------------------------------------------

def _raiz(raiz: Path | None) -> Path:
    return Path(raiz) if raiz is not None else comun.RAIZ


def ruta_paginas(corrida_id: str, raiz: Path | None = None) -> Path:
    """Ruta del documento «Páginas» de una corrida (`empresa/barrido/paginas/<corrida_id>.json`)."""
    _exigir_corrida(corrida_id)
    return comun.dir_barrido(raiz) / "paginas" / f"{corrida_id}.json"


def _exigir_corrida(corrida_id: Any) -> None:
    if not comun.corrida_id_valido(corrida_id):
        raise ErrorUso(f"corrida_id inválido: {_una_linea(repr(corrida_id))} (se espera AAAA-MM-DD-<letra>)")


def _una_linea(texto: Any) -> str:
    """Mensaje en una sola línea y acotado: puede incluir fragmentos de dato no confiable."""
    plano = " ".join(str(texto).split())
    return plano if len(plano) <= _MAX_MENSAJE else plano[: _MAX_MENSAJE - 1] + "…"


def _sin_raiz(texto: str, raiz: Path) -> str:
    """Quita el prefijo absoluto de la raíz de las rutas de un mensaje (el documento queda portable)."""
    return texto.replace(str(raiz) + "/", "")


def _dias_texto(valor: Decimal) -> str:
    """Decimal exacto → cadena sin notación científica (la misma cifra que da `resumir_anuncios`)."""
    return format(valor, "f")


# ---------------------------------------------------------------------------
# Parámetros
# ---------------------------------------------------------------------------

def _titulos_max(par_barrido: Mapping[str, Any]) -> int:
    if "barrido_titulos_por_pagina_max" not in par_barrido:
        raise ErrorLimite("falta el parámetro barrido_titulos_por_pagina_max (falla cerrado)")
    valor = par_barrido["barrido_titulos_por_pagina_max"]
    if isinstance(valor, Decimal) and valor == valor.to_integral_value():
        valor = int(valor)
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
        raise ErrorValidacion(
            f"barrido_titulos_por_pagina_max debe ser un entero ≥ 1, llegó {_una_linea(repr(valor))}")
    return valor


def _moneda(valor: Any, campo: str) -> str:
    texto = valor.strip().upper() if isinstance(valor, str) else ""
    if len(texto) != 3 or not (texto.isascii() and texto.isalpha()):
        raise ErrorValidacion(f"{campo}: se esperan 3 letras (ISO 4217), llegó {_una_linea(repr(valor))}")
    return texto


def _iso2(valor: Any, campo: str) -> str:
    texto = valor.strip().upper() if isinstance(valor, str) else ""
    if len(texto) != 2 or not (texto.isascii() and texto.isalpha()):
        raise ErrorValidacion(f"{campo}: se esperan 2 letras (ISO 3166-1 alfa-2), llegó {_una_linea(repr(valor))}")
    return texto


def _normalizar_mapa_monedas(mapa: Any) -> dict[str, tuple[str, ...]]:
    """Valida `barrido_exportador_monedas_pais` → {MONEDA: (PAIS, ...)}.

    Cada valor es un país ISO-2 o una lista de ellos (una moneda compartida por varios países, p. ej. EUR).
    """
    if mapa is None:
        raise ErrorLimite("falta el parámetro barrido_exportador_monedas_pais (falla cerrado)")
    if not isinstance(mapa, Mapping):
        raise ErrorValidacion("barrido_exportador_monedas_pais debe ser un mapa moneda → país(es)")
    salida: dict[str, tuple[str, ...]] = {}
    for moneda, paises in mapa.items():
        codigo = _moneda(moneda, "barrido_exportador_monedas_pais (clave)")
        if codigo in salida:
            raise ErrorValidacion(f"barrido_exportador_monedas_pais: moneda repetida {codigo}")
        lista = [paises] if isinstance(paises, str) else paises
        if not isinstance(lista, (list, tuple)) or not lista:
            raise ErrorValidacion(f"barrido_exportador_monedas_pais[{codigo}]: se espera un país ISO-2 o una lista")
        salida[codigo] = tuple(sorted({_iso2(p, f"barrido_exportador_monedas_pais[{codigo}]") for p in lista}))
    return salida


# ---------------------------------------------------------------------------
# Señal de exportador (§17.2)
# ---------------------------------------------------------------------------

def detectar_exportador(moneda: str, pais_anuncio: str, mapa: Mapping[str, Any]) -> dict[str, Any]:
    """¿La cuenta publicitaria está en la moneda de un país distinto del país donde anuncia?

    `mapa` = parámetro `barrido_exportador_monedas_pais` (moneda → país ISO-2, o lista de países).
    Solo las monedas que el mapa incluye cuentan; las demás (USD genérico, monedas desconocidas) no
    implican país y NO generan señal: lo decide el parámetro, no el código. Devuelve
    `{señal, moneda, pais_anuncio, motivo}`. Es un INDICIO, nunca un hecho: lo dice el `motivo`.

    Errores: ErrorValidacion si `moneda`/`pais_anuncio` no son códigos bien formados o el mapa es raro;
    ErrorLimite si el mapa es None (parámetro ausente).
    """
    cod_moneda = _moneda(moneda, "moneda")
    cod_pais = _iso2(pais_anuncio, "pais_anuncio")
    paises_moneda = _normalizar_mapa_monedas(mapa).get(cod_moneda)
    if paises_moneda is None:
        motivo = (f"la moneda {cod_moneda} no figura en el mapa de monedas con país: no implica país, "
                  "sin indicio de exportador")
        senal = False
    elif cod_pais in paises_moneda:
        motivo = (f"la moneda {cod_moneda} corresponde a {', '.join(paises_moneda)} y el anuncio corre en "
                  f"{cod_pais}: sin indicio de exportador")
        senal = False
    else:
        motivo = (f"cuenta publicitaria en {cod_moneda} (moneda de {', '.join(paises_moneda)}) que anuncia en "
                  f"{cod_pais}: probable exportador (indicio, no hecho)")
        senal = True
    return {CLAVE_SENAL: senal, "moneda": cod_moneda, "pais_anuncio": cod_pais, "motivo": motivo}


def _exportador_de_pagina(pares: Iterable[tuple[str, str]], mapa: Mapping[str, Any]) -> dict[str, Any]:
    """Resume los pares (moneda, país) con que se vio una página en un solo indicio determinista."""
    ordenados = sorted(set(pares), key=lambda par: (par[1], par[0]))
    evaluados = [detectar_exportador(moneda, pais, mapa) for moneda, pais in ordenados]
    con_senal = [e for e in evaluados if e[CLAVE_SENAL]]
    if con_senal:
        elegido = dict(con_senal[0])
        if len(con_senal) > 1:
            elegido["motivo"] += f" (y {len(con_senal) - 1} combinación(es) moneda × país más con el mismo indicio)"
        return elegido
    if len(evaluados) == 1:
        return evaluados[0]
    return {CLAVE_SENAL: False, "moneda": None, "pais_anuncio": None,
            "motivo": f"ninguna de las {len(evaluados)} combinaciones moneda × país indica exportador"}


# ---------------------------------------------------------------------------
# Lectura de crudos (compartida por la ingesta y la cobertura, para que coincidan)
# ---------------------------------------------------------------------------

def _truncada(doc: Mapping[str, Any]) -> bool:
    """La consulta llegó a su `limit` y el conector declara (o podría haber) más resultados."""
    recibidos = len(doc["ads"])
    total = doc["estimated_total_count"]
    return recibidos > 0 and recibidos >= doc["consulta"]["limit"] and (total is None or total > recibidos)


def _leer_crudos(corrida_id: str, raiz: Path, *, carpeta_opcional: bool = False
                 ) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Crudos de la corrida → (válidos por qid, mensajes de exclusión por nombre de archivo).

    Un crudo ilegible, que no pasa la validación o cuyo `corrida_id`/`qid` no coincide con su carpeta/nombre
    (`comun.leer_crudo`) se EXCLUYE y se explica; no aborta. Carpeta inexistente: ErrorUso (corrida desconocida),
    salvo `carpeta_opcional` (la cobertura de una corrida que aún no empezó).
    """
    if carpeta_opcional and not comun.dir_crudo(corrida_id, raiz).is_dir():
        return {}, {}
    validos: dict[str, dict[str, Any]] = {}
    excluidos: dict[str, str] = {}
    for ruta in comun.listar_crudos(corrida_id, raiz):
        try:
            validos[ruta.stem] = comun.leer_crudo(ruta)
        except (ErrorValidacion, ErrorUso) as exc:
            excluidos[ruta.stem] = f"crudo excluido: {_sin_raiz(_una_linea(exc), raiz)}"
    return validos, excluidos


def _deduplicar(validos: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Anuncios distintos por `id` entre todas las consultas válidas.

    Devuelve ({id: {page_id, ad, qids}}, avisos de conflicto). El mismo anuncio visto en varias consultas
    se cuenta una vez y recuerda en cuáles apareció. Si un `id` reaparece con otra página, otro inicio o
    otra moneda (incoherencia, posible error de transcripción), se conserva el primero (orden de `qid`),
    el reaparecido se IGNORA por completo y se avisa.
    """
    anuncios: dict[str, dict[str, Any]] = {}
    avisos: list[str] = []
    for qid in sorted(validos):
        for ad in validos[qid]["ads"]:
            firma = (ad["page_id"], ad["ad_delivery_start_time"], ad["currency"])
            previo = anuncios.get(ad["id"])
            if previo is None:
                anuncios[ad["id"]] = {"page_id": ad["page_id"], "firma": firma, "ad": ad, "qids": [qid]}
            elif previo["firma"] == firma:
                if qid not in previo["qids"]:
                    previo["qids"].append(qid)
            else:
                avisos.append(
                    f"el anuncio {ad['id']} aparece con datos distintos (página, inicio o moneda) en "
                    f"{previo['qids'][0]} y {qid}: se conserva el de {previo['qids'][0]} y se ignora el otro")
    return anuncios, avisos


# ---------------------------------------------------------------------------
# Ingesta
# ---------------------------------------------------------------------------

def _titulos(filas: Sequence[Mapping[str, Any]], maximo: int) -> list[str]:
    """Hasta `maximo` títulos únicos (por título normalizado, como los conceptos), literales y sin vacíos.

    Orden determinista: más repetidos primero; empate por título normalizado. De las variantes de un mismo
    título normalizado (mayúsculas, espacios) se conserva la menor en orden de texto.
    """
    variantes: dict[str, set[str]] = {}
    conteo: Counter[str] = Counter()
    for fila in filas:
        clave = pm._normalizar_titulo(fila["ad_creative_link_title"])  # misma normalización que los conceptos
        if not clave:
            continue
        variantes.setdefault(clave, set()).add(fila["ad_creative_link_title"])
        conteo[clave] += 1
    ordenadas = sorted(conteo, key=lambda clave: (-conteo[clave], clave))
    return [min(variantes[clave]) for clave in ordenadas[:maximo]]


def _nombre_pagina(anuncios: Sequence[Mapping[str, Any]]) -> str | None:
    """Nombre más frecuente (empate: el menor en orden de texto); None si ningún anuncio trae uno no vacío."""
    nombres = Counter(a["page_name"].strip() for a in anuncios if a["page_name"].strip())
    if not nombres:
        return None
    return sorted(nombres, key=lambda n: (-nombres[n], n))[0]


def _indexar_mediciones(validos: Mapping[str, Mapping[str, Any]], anuncios: Mapping[str, Mapping[str, Any]]
                        ) -> dict[str, Any]:
    """Índices para medir cada página por país (CONTRATO §4, `medicion`).

    - `muestra[(page_id, pais)]`: ids de anuncios de la página vistos en consultas por TÉRMINO (`page_ids` null).
    - `unipagina[(page_id, pais)]`: qids de consultas por `page_ids` con EXACTAMENTE ese page_id y ese país.
    - `ids_unipagina[(page_id, pais)][qid]`: ids de la página en esa consulta (solo los que no se ignoraron
      por conflicto de duplicados).
    - `paises_unipagina[page_id]`: países en que alguna consulta unipágina preguntó por esa página (con o sin
      anuncios: una consulta que devolvió 0 mide la AUSENCIA de la página en ese país).
    - Las consultas con 2+ page_ids NO miden (un solo `estimated_total_count` para todo el lote es ambiguo):
      quedan en `multi` para advertirlo.
    """
    indices: dict[str, Any] = {"muestra": {}, "unipagina": {}, "ids_unipagina": {}, "multi": [],
                               "otra_pagina": Counter(), "paises_unipagina": {}}
    for qid in sorted(validos):
        consulta = validos[qid]["consulta"]
        ids = consulta["page_ids"]
        if ids is None:
            continue
        if len(ids) == 1:
            indices["unipagina"].setdefault((ids[0], consulta["countries"][0]), []).append(qid)
            indices["paises_unipagina"].setdefault(ids[0], set()).add(consulta["countries"][0])
        else:
            indices["multi"].append(qid)
    for ad_id, registro in anuncios.items():
        for qid in registro["qids"]:
            consulta = validos[qid]["consulta"]
            pais = consulta["countries"][0]
            ids = consulta["page_ids"]
            if ids is None:
                indices["muestra"].setdefault((registro["page_id"], pais), set()).add(ad_id)
            elif len(ids) == 1:
                if ids[0] == registro["page_id"]:
                    indices["ids_unipagina"].setdefault((registro["page_id"], pais), {}).setdefault(qid, set()).add(ad_id)
                else:
                    indices["otra_pagina"][qid] += 1
    return indices


def _medir_pagina(page_id: str, paises: Sequence[str], validos: Mapping[str, Mapping[str, Any]],
                  indices: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """`medicion` de una página: por país, ¿se midió con su propia consulta por `page_ids` o solo por muestra?

    Países medidos = los de `paises` (presencia: se vieron anuncios) más los países en que una consulta unipágina
    preguntó por la página y no devolvió ninguno (AUSENCIA medida: `anuncios_vistos` 0 y `total_declarado` del
    conector; `paises` sigue siendo solo presencia).
    Por país: si hay una consulta con `page_ids == [page_id]` y ese país (si hay varias, la que más anuncios
    de la página ve; empate: la de mayor total declarado, luego el menor qid) → fuente «pagina»,
    `anuncios_vistos` = anuncios de la página en ese crudo, `total_declarado` = su `estimated_total_count`.
    `completa` = total declarado, todo visto Y la cifra no está al tope de la consulta (`anuncios_vistos < limit`
    o `total_declarado < limit`): el total del conector es una ESTIMACIÓN, y 50 de 50 podría ser 50 de 80.
    Si no hay consulta unipágina → fuente «muestra»: anuncios distintos de la página vistos en ese país en las
    consultas por término, `total_declarado` null, `completa` false (una frase nunca prueba que no haya más).
    `estado`: «completa» si todos los países son completa; «muestra» si ninguno se midió por su página;
    «parcial» en cualquier otro caso (alguno se midió por su página pero falta ver o medir algo).
    Devuelve (medicion, qids de consultas por page_ids cuyos anuncios no cuadran con las de término).
    """
    por_pais: dict[str, dict[str, Any]] = {}
    incoherentes: list[str] = []
    for pais in sorted(set(paises) | indices["paises_unipagina"].get(page_id, set())):
        clave = (page_id, pais)
        candidatas = indices["unipagina"].get(clave)
        vistos_por_termino = indices["muestra"].get(clave, set())
        if candidatas:
            ids_por_qid = indices["ids_unipagina"].get(clave, {})
            qid = sorted(candidatas, key=lambda q: (-len(ids_por_qid.get(q, ())),
                                                    -(validos[q]["estimated_total_count"] or 0), q))[0]
            ids = ids_por_qid.get(qid, set())
            total = validos[qid]["estimated_total_count"]
            limite = validos[qid]["consulta"]["limit"]
            vistos = len(ids)
            por_pais[pais] = {"fuente": "pagina", "anuncios_vistos": vistos, "total_declarado": total,
                              "completa": total is not None and vistos >= total
                                          and (vistos < limite or total < limite)}
            if vistos_por_termino - ids:
                incoherentes.append(qid)
        else:
            por_pais[pais] = {"fuente": "muestra", "anuncios_vistos": len(vistos_por_termino),
                              "total_declarado": None, "completa": False}
    if all(e["completa"] for e in por_pais.values()):
        estado = "completa"
    elif not any(e["fuente"] == "pagina" for e in por_pais.values()):
        estado = "muestra"
    else:
        estado = "parcial"
    return {"estado": estado, "por_pais": por_pais}, incoherentes


def _resumen_medicion(medicion: Mapping[str, Any], anuncios_union: int) -> dict[str, Any]:
    """Campos derivados de `medicion`: conteo medido, si es piso, `muestra_truncada` y `edad_es_piso`.

    `anuncios_activos_medidos` = max(anuncios distintos vistos (la unión), mayor cifra por país), donde la cifra
    de un país es su `total_declarado` (fuente «pagina» y no nulo) o sus `anuncios_vistos`. NO se suma por país:
    un mismo anuncio que corre en 2 países se contaría doble. Es una COTA INFERIOR de anuncios distintos, y así
    siempre `medidos >= anuncios_activos_en_muestra >= conceptos_unicos`.
    """
    entradas = list(medicion["por_pais"].values())
    por_pais = [e["total_declarado"] if e["fuente"] == "pagina" and e["total_declarado"] is not None
                else e["anuncios_vistos"] for e in entradas]
    no_completa = medicion["estado"] != "completa"
    oculta_mas = any(e["fuente"] == "pagina" and e["total_declarado"] is not None
                     and e["total_declarado"] > e["anuncios_vistos"] for e in entradas)
    return {"anuncios_activos_medidos": max([anuncios_union, *por_pais]),
            "anuncios_activos_medidos_es_piso": no_completa,
            "muestra_truncada": no_completa, "edad_es_piso": no_completa or oculta_mas}


def _contraste_con_plan(plan_doc: Mapping[str, Any], validos: Mapping[str, Mapping[str, Any]],
                        excluidos: Mapping[str, str], permitir: bool) -> list[str]:
    """Crudos que el plan no autoriza: ErrorValidacion salvo `permitir`, que los deja pasar con advertencia."""
    consultas = plan_doc["consultas"]
    en_plan = {c["qid"] for c in consultas}
    fuera = sorted((set(validos) | set(excluidos)) - en_plan)
    difieren = _contrastar(consultas, validos)
    if not fuera and not difieren:
        return []
    detalle: list[str] = []
    if fuera:
        detalle.append("fuera del plan: " + ", ".join(_una_linea(q) for q in fuera))
    if difieren:
        detalle.append("consulta distinta de la planificada: " + ", ".join(
            f"{q} ({', '.join(campos)})" for q, campos in difieren.items()))
    if not permitir:
        raise ErrorValidacion(
            f"corrida {plan_doc['corrida_id']}: la ingesta se rechaza porque hay crudos que el plan vigente "
            f"({len(consultas)} consultas) no autoriza; " + "; ".join(detalle) + ". Nada se ingiere. Retire o corrija "
            "esos archivos (o, bajo su responsabilidad, use permitir_fuera_de_plan=True)")
    avisos = [f"crudo fuera del plan {_una_linea(q)}: se ingiere por permitir_fuera_de_plan=True" for q in fuera
              if q in validos]
    avisos += [f"crudo {q} difiere de lo planificado en {', '.join(campos)}: se ingiere por permitir_fuera_de_plan=True"
               for q, campos in difieren.items()]
    return avisos


def ingestar_corrida(corrida_id: str, *, raiz: Path | None = None, ahora: datetime,
                     par_barrido: Mapping[str, Any], par_modelado: Mapping[str, Any],
                     permitir_fuera_de_plan: bool = False) -> dict[str, Any]:
    """Crudos de una corrida → documento «Páginas» (CONTRATO §4). No escribe nada.

    Entradas: `ahora` con zona horaria (reloj inyectado); `par_barrido` con `barrido_titulos_por_pagina_max`
    y `barrido_exportador_monedas_pais`; `par_modelado` se acepta (el mismo juego de parámetros que usan las
    demás etapas) pero la ingesta no aplica umbrales de tracción: eso es de `ranking`.
    Errores: ErrorUso (corrida inexistente o mal formada, `ahora` sin zona), ErrorLimite (falta un parámetro),
    ErrorValidacion (no hay ni un crudo válido, un parámetro raro, o crudos que el plan vigente no autoriza).
    Un crudo inválido NO es error: se excluye y se advierte con su ruta.

    Contraste con el plan: si existe plan para la corrida (el más reciente, `plan.cargar_plan`; necesita
    `modelado_max_consultas_por_corrida` y los `barrido_*` del plan en los parámetros), todo crudo cuyo qid no esté
    en el plan, o cuya consulta (frase, país, límite, estado, page_ids) difiera de la planificada, hace FALLAR la
    ingesta con ErrorValidacion (código 3) y no entra en ninguna página. Único escape documentado:
    `permitir_fuera_de_plan=True` (se ingieren y se listan en `advertencias`). Sin plan: ingesta normal + advertencia.
    """
    _exigir_corrida(corrida_id)
    if not isinstance(ahora, datetime) or ahora.tzinfo is None:
        raise ErrorUso("`ahora` debe ser un datetime con zona horaria UTC")
    if not isinstance(par_barrido, Mapping) or not isinstance(par_modelado, Mapping):
        raise ErrorUso("par_barrido y par_modelado deben ser mapas clave → valor ya tipado")
    maximo_titulos = _titulos_max(par_barrido)
    mapa_monedas = _normalizar_mapa_monedas(par_barrido.get("barrido_exportador_monedas_pais"))
    raiz_efectiva = _raiz(raiz)

    validos, excluidos = _leer_crudos(corrida_id, raiz_efectiva)
    if not validos:
        detalle = "; ".join(excluidos[k] for k in sorted(excluidos)) or "la corrida no tiene crudos"
        raise ErrorValidacion(f"corrida {corrida_id}: ningún crudo válido que ingerir ({detalle})")

    plan_vigente = _plan_vigente(corrida_id, par_barrido, par_modelado, raiz_efectiva)
    avisos_plan: list[str]
    if plan_vigente is None:
        avisos_plan = [f"sin plan para la corrida {corrida_id}: los crudos no se contrastan con lo planificado"]
    else:
        avisos_plan = _contraste_con_plan(plan_vigente, validos, excluidos, permitir_fuera_de_plan)

    # Solo cuentan anuncios ACTIVOS: una consulta INACTIVE/ALL (rutas B, C o D la admiten) no se ingiere.
    no_activos = sorted(q for q, doc in validos.items() if doc["consulta"]["ad_active_status"] != planes.ESTADO_ACTIVO)
    for qid in no_activos:
        excluidos[qid] = (f"crudo excluido: consulta.ad_active_status={validos[qid]['consulta']['ad_active_status']!r} "
                          f"(el barrido cuenta solo anuncios {planes.ESTADO_ACTIVO})")
        del validos[qid]
    if not validos:
        raise ErrorValidacion(f"corrida {corrida_id}: ningún crudo válido que ingerir ("
                              + "; ".join(excluidos[k] for k in sorted(excluidos)) + ")")
    advertencias: list[str] = [f"{k}: {excluidos[k]}" for k in sorted(excluidos)]
    advertencias.extend(avisos_plan)
    for qid in sorted(validos):
        advertencias.extend(f"consulta {qid}: {aviso}" for aviso in comun.advertencias_crudo(validos[qid]))

    anuncios, avisos_conflicto = _deduplicar(validos)
    advertencias.extend(avisos_conflicto)

    truncadas = {qid for qid, doc in validos.items() if _truncada(doc)}
    for qid in sorted(truncadas):
        doc = validos[qid]
        total = doc["estimated_total_count"]
        declarado = "total no declarado" if total is None else f"de {total} declarados"
        advertencias.append(
            f"consulta {qid} truncada: {len(doc['ads'])} anuncios recibidos ({declarado}); las páginas que solo "
            "se ven por esta muestra llevan un conteo que es un PISO, no el total")

    indices = _indexar_mediciones(validos, anuncios)
    for qid in indices["multi"]:
        advertencias.append(
            f"consulta {qid}: page_ids con {len(validos[qid]['consulta']['page_ids'])} páginas no mide por página "
            "(un solo estimated_total_count para todo el lote es ambiguo); sus anuncios sí cuentan en la muestra")
    for qid in sorted(indices["otra_pagina"]):
        advertencias.append(
            f"consulta {qid}: {indices['otra_pagina'][qid]} anuncio(s) de una página distinta de la consultada; "
            "no suman a la medición por página")

    por_pagina: dict[str, list[str]] = {}
    for ad_id, registro in anuncios.items():
        por_pagina.setdefault(registro["page_id"], []).append(ad_id)

    ahora_epoch = int(ahora.timestamp())
    paginas: list[dict[str, Any]] = []
    con_futuros: list[tuple[str, int]] = []
    de_un_anuncio = 0
    sin_titulo_util = 0
    incoherencias: list[tuple[str, str]] = []
    for page_id in sorted(por_pagina, key=lambda p: (int(p), p)):
        ads = [anuncios[i]["ad"] for i in por_pagina[page_id]]
        qids = sorted({q for i in por_pagina[page_id] for q in anuncios[i]["qids"]})
        resumen = pm.resumir_anuncios(
            [{"id": a["id"], "page_id": page_id, "ad_creative_link_title": a["ad_creative_link_title"],
              "ad_delivery_start_time": a["ad_delivery_start_time"]} for a in ads], ahora)
        pares = {(anuncios[i]["ad"]["currency"], validos[q]["consulta"]["countries"][0])
                 for i in por_pagina[page_id] for q in anuncios[i]["qids"]}
        futuros = sum(1 for a in ads if a["ad_delivery_start_time"] > ahora_epoch)
        if futuros:
            con_futuros.append((page_id, futuros))
        if resumen["anuncios_activos"] == 1:
            de_un_anuncio += 1
        titulos = _titulos(ads, maximo_titulos)
        if not titulos:
            sin_titulo_util += 1
        paises = sorted({validos[q]["consulta"]["countries"][0] for q in qids})
        medicion, incoherentes = _medir_pagina(page_id, paises, validos, indices)
        incoherencias.extend((page_id, qid) for qid in incoherentes)
        paginas.append({
            "page_id": page_id,
            "page_name": _nombre_pagina(ads),
            "paises": paises,
            "monedas": sorted({a["currency"] for a in ads}),
            "anuncios_activos_en_muestra": resumen["anuncios_activos"],
            "edad_oferta_dias": _dias_texto(resumen["edad_oferta_dias"]),
            "edad_max_dias": _dias_texto(resumen["edad_max_dias"]),
            "conceptos_unicos": resumen["conceptos_unicos"],
            "titulos": titulos,
            "qids": qids,
            "exportador": _exportador_de_pagina(pares, mapa_monedas),
            "medicion": medicion,
            **_resumen_medicion(medicion, resumen["anuncios_activos"]),
        })

    if not paginas:
        advertencias.append(f"ninguno de los {len(validos)} crudos válidos trae anuncios: no hay páginas")
    for page_id, n in con_futuros:
        advertencias.append(f"página {page_id}: {n} anuncio(s) con inicio posterior a `ahora` (edad fijada en 0)")
    if de_un_anuncio:
        advertencias.append(
            f"{de_un_anuncio} página(s) con un solo anuncio en la muestra: sin sobrevivientes, edad_oferta_dias = 0")
    if sin_titulo_util:
        advertencias.append(f"{sin_titulo_util} página(s) sin ningún título utilizable (todos vacíos)")
    for page_id, qid in incoherencias:
        advertencias.append(
            f"página {page_id}: hay anuncios vistos en consultas por término que no aparecen en su consulta {qid} "
            "por page_ids (¿terminaron entre una consulta y otra?); la medición usa la consulta por page_ids")
    if paginas:
        conteo = Counter(p["medicion"]["estado"] for p in paginas)
        advertencias.append(
            f"medición por página: completa={conteo['completa']}, parcial={conteo['parcial']}, "
            f"muestra={conteo['muestra']} de {len(paginas)} página(s)")
        n_truncadas = sum(1 for p in paginas if p["muestra_truncada"])
        if n_truncadas:
            advertencias.append(
                f"{n_truncadas} de {len(paginas)} página(s) con muestra_truncada=true (medición no completa): su "
                "anuncios_activos_medidos es un PISO, no el total de anuncios de la página")

    return {
        "schema_version": SCHEMA_VERSION,
        "corrida_id": corrida_id,
        "generado_en": comun.iso_z(ahora),
        "paginas": paginas,
        "advertencias": advertencias,
    }


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------

def escribir_paginas(doc: Mapping[str, Any], raiz: Path | None = None) -> Path:
    """Escribe el documento «Páginas» en `empresa/barrido/paginas/<corrida_id>.json` (atómico, sin sobrescribir).

    Errores: ErrorValidacion si el documento no tiene la forma esperada o lleva float/Decimal (lo rechaza
    `comun.escribir_json_nuevo` antes de tocar el disco); ErrorUso si el archivo ya existe. Devuelve la ruta.
    """
    if not isinstance(doc, Mapping) or not isinstance(doc.get("paginas"), list) \
            or not isinstance(doc.get("advertencias"), list):
        raise ErrorValidacion("doc: se esperaba el documento «Páginas» {corrida_id, generado_en, paginas, advertencias}")
    ruta = ruta_paginas(doc.get("corrida_id"), raiz)
    comun.escribir_json_nuevo(ruta, doc)
    return ruta


# ---------------------------------------------------------------------------
# Cobertura del plan
# ---------------------------------------------------------------------------

def _consultas_del_plan(plan: Any, corrida_id: str) -> list[Mapping[str, Any]]:
    if not isinstance(plan, Mapping) or not isinstance(plan.get("consultas"), list):
        raise ErrorValidacion("plan: se esperaba un objeto con la lista `consultas`")
    if plan.get("corrida_id") != corrida_id:
        raise ErrorValidacion(
            f"plan: corrida_id {_una_linea(repr(plan.get('corrida_id')))} no es el de la cobertura ({corrida_id})")
    vistos: set[str] = set()
    consultas: list[Mapping[str, Any]] = []
    for i, consulta in enumerate(plan["consultas"]):
        qid = consulta.get("qid") if isinstance(consulta, Mapping) else None
        if not comun.qid_valido(qid):
            raise ErrorValidacion(f"plan.consultas[{i}]: qid inválido {_una_linea(repr(qid))}")
        if qid in vistos:
            raise ErrorValidacion(f"plan.consultas[{i}]: qid repetido {qid}")
        vistos.add(qid)
        consultas.append(consulta)
    return consultas


def _difiere(planificada: Mapping[str, Any], doc: Mapping[str, Any]) -> list[str]:
    """Campos de la consulta ejecutada (crudo) que no coinciden con la planificada (solo los que el plan trae)."""
    ejecutada = doc["consulta"]
    campos: list[str] = []
    if "search_terms" in planificada and (
            None if planificada["search_terms"] is None else str(planificada["search_terms"]).strip()
    ) != (None if ejecutada["search_terms"] is None else ejecutada["search_terms"].strip()):
        campos.append("search_terms")
    if "countries" in planificada and (
            sorted(str(c).upper() for c in planificada["countries"]) != sorted(ejecutada["countries"])):
        campos.append("countries")
    if "limit" in planificada and planificada["limit"] != ejecutada["limit"]:
        campos.append("limit")
    if "ad_active_status" in planificada and planificada["ad_active_status"] != ejecutada["ad_active_status"]:
        campos.append("ad_active_status")
    if "page_ids" in planificada:
        def _ids(valor: Any) -> list[str] | None:
            return None if valor is None else sorted(str(v) for v in valor)
        if _ids(planificada["page_ids"]) != _ids(ejecutada["page_ids"]):
            campos.append("page_ids")
    return campos


def _contrastar(consultas: Sequence[Mapping[str, Any]], validos: Mapping[str, Mapping[str, Any]]
                ) -> dict[str, list[str]]:
    """{qid: campos que difieren} para las consultas del plan con crudo válido cuya ejecución cambió (orden del plan)."""
    diferencias: dict[str, list[str]] = {}
    for consulta in consultas:
        if consulta["qid"] in validos:
            campos = _difiere(consulta, validos[consulta["qid"]])
            if campos:
                diferencias[consulta["qid"]] = campos
    return diferencias


def _plan_vigente(corrida_id: str, par_barrido: Mapping[str, Any], par_modelado: Mapping[str, Any],
                  raiz: Path) -> dict[str, Any] | None:
    """El plan acumulado más reciente de la corrida (`plan.cargar_plan`) o None si NO hay ningún archivo de plan.

    Solo la ausencia total de archivos de plan es «sin plan»: un plan que existe pero no se puede leer o no valida
    propaga su error (ErrorUso / ErrorValidacion / ErrorLimite) en vez de degradarse a «sin contraste».
    """
    pasadas_max = par_barrido.get("barrido_pasadas_max")
    if pasadas_max is None:
        raise ErrorLimite("falta el parámetro barrido_pasadas_max (falla cerrado)")
    if isinstance(pasadas_max, bool) or not isinstance(pasadas_max, int) or pasadas_max < 1:
        raise ErrorValidacion(f"barrido_pasadas_max debe ser un entero ≥ 1, llegó {_una_linea(repr(pasadas_max))}")
    if not any(planes.ruta_plan(corrida_id, pasada, raiz).is_file() for pasada in range(1, pasadas_max + 1)):
        return None
    return planes.cargar_plan(corrida_id, {**par_barrido, **par_modelado}, raiz=raiz)


def cobertura(plan: Mapping[str, Any], corrida_id: str, *, raiz: Path | None = None) -> dict[str, Any]:
    """Estado de las consultas de un plan según lo que hay en disco. Decide la siguiente pasada.

    Para cada consulta del plan, en el orden del plan:
    - `consultas_ok`: tiene un crudo válido (gana aunque quede un `.error.json` viejo de un reintento).
    - `con_error`: no tiene crudo válido y hay un `<qid>.error.json`, o el crudo existe pero es inválido
      (estas quedan también en `invalidos`: conviene repetirlas).
    - `sin_crudo`: ni crudo ni error (la consulta no se ejecutó, o la carpeta de la corrida aún no existe).
    - `truncadas`: subconjunto de `consultas_ok` cuyo crudo llegó a su `limit` con más resultados declarados
      (o total no declarado): hay que particionarlas (pasada 2) o recorrerlas por `page_ids` (pasada 3).
    - `ads_total`: anuncios DISTINTOS (por id) en los crudos válidos del plan.
    Además: `fuera_de_plan` (crudos o errores de un qid que el plan no pidió), `difieren` (qids con crudo válido
    cuya consulta ejecutada difiere de la planificada; siguen en `consultas_ok`: aquí solo se informa, quien
    ingiere las rechaza) y `advertencias`. Todo sale de los archivos; nada se inventa.
    """
    _exigir_corrida(corrida_id)
    raiz_efectiva = _raiz(raiz)
    consultas = _consultas_del_plan(plan, corrida_id)
    qids_plan = [c["qid"] for c in consultas]

    validos, excluidos = _leer_crudos(corrida_id, raiz_efectiva, carpeta_opcional=True)
    directorio = comun.dir_crudo(corrida_id, raiz_efectiva)
    con_archivo_error = {p.name[: -len(_SUFIJO_ERROR)]
                         for p in (directorio.glob(f"*{_SUFIJO_ERROR}") if directorio.is_dir() else [])}

    ok: list[str] = []
    sin_crudo: list[str] = []
    con_error: list[str] = []
    invalidos: list[str] = []
    advertencias: list[str] = []
    for qid in qids_plan:
        if qid in validos:
            ok.append(qid)
            if qid in con_archivo_error:
                advertencias.append(
                    f"consulta {qid}: hay crudo válido y también un {qid}{_SUFIJO_ERROR} viejo; se usa el crudo")
        elif qid in excluidos:
            con_error.append(qid)
            invalidos.append(qid)
            advertencias.append(f"{qid}: {excluidos[qid]}")
        elif qid in con_archivo_error:
            con_error.append(qid)
        else:
            sin_crudo.append(qid)

    fuera = sorted((set(validos) | set(excluidos) | con_archivo_error) - set(qids_plan))
    advertencias.extend(f"consulta {qid}: hay archivos en la corrida que el plan no pidió" for qid in fuera)
    difieren = _contrastar(consultas, validos)
    advertencias.extend(f"consulta {qid}: lo ejecutado difiere de lo planificado en {', '.join(campos)}"
                        for qid, campos in difieren.items())

    anuncios, _ = _deduplicar({qid: validos[qid] for qid in ok})
    return {
        "consultas_ok": ok,
        "sin_crudo": sin_crudo,
        "con_error": con_error,
        "truncadas": [qid for qid in ok if _truncada(validos[qid])],
        "ads_total": len(anuncios),
        "invalidos": invalidos,
        "fuera_de_plan": fuera,
        "difieren": list(difieren),
        "advertencias": advertencias,
    }
