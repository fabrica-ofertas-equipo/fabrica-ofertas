"""Memoria de barridos (B3): instantáneas inmutables, diff entre barridos y `entrantes_30d`.

Contrato: scripts/modelado/barrido/CONTRATO.md §4 (Memoria) y departamentos/02-descubrimiento.md §12.3 paso 6 y §17.3
pieza 6. Convierte el barrido en descubrimiento constante: guarda cada barrido, detecta páginas y temas nuevos o en
crecimiento y aporta la única medida que el barrido no puede dar solo: cuántos anunciantes entraron en los últimos
30 días (`hueco.entrantes_30d` de la ficha de `puntaje_modelar`).

Definiciones (las usan `guardar_instantanea`, `diff` y `entrantes_30d`; ningún otro módulo las reinterpreta)
------------------------------------------------------------------------------------------------------------
1. **Presencia.** Un par (`page_id`, país) está *presente* en una instantánea si la página figura con
   `anuncios_activos_en_muestra` ≥ 1 y el país está en su lista `paises`. El conteo de anuncios es de la
   *muestra* (el conector da ≤ 50 por llamada): si `muestra_truncada` es verdadero, es un PISO, no el total.
2. **Instantánea.** Foto inmutable de un barrido: por página, anuncios, edad de la oferta, edad del anuncio más
   viejo, países, truncamiento y tema (si hay etiqueta). Se guarda una sola vez por `corrida_id`, con un hash
   SHA-256 del contenido canónico (en el propio archivo y en `indice.jsonl`). Una instantánea cuyo hash no
   coincide está corrupta: lanza `ErrorValidacion` y NO se usa jamás (ni para el diff ni para `entrantes_30d`).
3. **Antigüedad** de una instantánea previa = `ahora` − su *instante*, en días exactos. El instante es
   `capturado_en` (campo opcional: el máximo de los `capturado_en` de los crudos, cuando el documento de páginas o
   el argumento `capturado_en` lo declaran) y, si no existe, `ts` (cuando se guardó). La ventana de `entrantes_30d`
   es el tiempo entre capturas, no entre guardados: una instantánea guardada días después de capturarse (`ts` >
   `capturado_en`; nunca al revés, se rechaza) parecería más joven de lo que es y se descartaría una base válida.
   Las instantáneas anteriores a este campo no lo tienen: siguen verificando con el mismo hash (el hash cubre
   exactamente las claves presentes) y se miden por `ts`.
4. **Base de `entrantes_30d`** (instantánea de referencia). Entre las previas (se excluye la propia corrida) con
   antigüedad ≥ `memoria_ventana_min_dias` (el borde, igual al mínimo, SÍ cumple) y, si el parámetro opcional
   `memoria_ventana_max_dias` existe, ≤ ese máximo, se elige la de antigüedad más cercana a 30 días
   (`DIAS_VENTANA_METRICA`: es la definición de la métrica `entrantes_30d`, no un umbral calibrable). Empate: la
   más antigua (cuenta más entrantes: sesgo conservador para H); luego, el menor `corrida_id`.
   **Si no existe ninguna, `entrantes_30d` es `None` (JAMÁS 0) y `diff` marca `estado: "sin_base"`.**
   0 solo significa «hay base y nadie entró».
5. **Entrante.** Una página de `actual` con anuncios activos que no estaba en la base, dentro de la ventana:
   a. *Nueva (alcance global, `pais=None`)*: la página NO figura activa en la base en ningún país y su anuncio
      más viejo visto (`edad_max_dias`) no es más antiguo que la base (empezó a anunciar después de ella). Si es
      más antigua, es *reaparecida* (ya existía y la muestra no la vio): no cuenta; se informa aparte.
   b. *Alcance de un mercado (`pais="MX"`)*: cuenta la *nueva* de arriba presente en ese país y también la
      *expansión*: página que en la base estaba activa pero no en ese país. Una página que «cambia de país»
      (estaba en ES y ahora está en MX) es entrante en MX, no lo es en ES ni en el alcance global, y `diff` la
      lista en `paginas_que_cambian_de_pais`.
   Un tema se cuenta por las páginas de `actual` con ese `tema_slug`; una oferta (página), como 1 o 0.
6. **Piso.** `diff` exporta `entrantes_30d_piso_por_pais` (bool por tema/oferta y país, `None` si el valor es
   `None`): verdadero si `actual` está truncado en ese alcance (el conteo es un PISO: puede haber más entrantes) o
   si la base lo estaba (puede incluir falsos entrantes). Un 0 con piso verdadero NO prueba que nadie entró y no
   debe leerse como hueco confirmado.
7. **Cobertura.** Si la instantánea declara `paises_consultados` y el mercado pedido no está ahí (en la base o en
   `actual`), no se sabe si nadie entró o si no se miró: `None`, no 0. Si no se declaró, se avisa en `advertencias`.
8. **Base de cambios** (para `paginas_*` y `temas_nuevos` de `diff`): la previa más reciente, sin mínimo de
   antigüedad, porque descubrir temas nuevos no necesita 30 días. Sin previa: `sin_base` y listas vacías (no se
   declara «nuevo» lo que no se puede comparar).

Reglas del repositorio: ningún umbral fijo (sale de `par`, los parámetros del barrido); falla cerrado (dato raro =
error claro); determinista (mismas entradas y mismo `ahora` → mismas salidas; sin reloj interno ni azar); sin
`float` en lo persistido (enteros y cadenas decimales); todo texto de la Biblioteca (nombres de página) es dato no
confiable: se sanea, jamás se interpreta. Solo biblioteca estándar. Sin red.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from scripts.modelado.barrido import comun

ErrorFabrica = comun.ErrorFabrica
ErrorLimite = comun.ErrorLimite
ErrorUso = comun.ErrorUso
ErrorValidacion = comun.ErrorValidacion


class _HashDistinto(ErrorValidacion):
    """El contenido de una instantánea no coincide con su hash: alterada o corrupta (sigue siendo ErrorValidacion)."""


def _rechazar_constante(nombre: str) -> Any:
    raise ValueError(f"constante no permitida: {nombre}")


__all__ = [
    "SCHEMA_VERSION", "NOMBRE_INDICE", "DIAS_VENTANA_METRICA", "CLAVE_VENTANA_MIN", "CLAVE_VENTANA_MAX",
    "construir_instantanea", "guardar_instantanea", "listar_instantaneas", "verificar_integridad",
    "cargar_instantanea", "cargar_previas", "diff", "entrantes_30d", "entrantes_detalle",
]

SCHEMA_VERSION = comun.VERSION_ESQUEMA
NOMBRE_INDICE = "indice.jsonl"

# Definición de la métrica `entrantes_30d` (la ventana va en su nombre: §12 de la spec y el campo de la ficha).
DIAS_VENTANA_METRICA = 30
CLAVE_VENTANA_MIN = "memoria_ventana_min_dias"   # obligatoria (CONTRATO §6); falta = ErrorLimite
CLAVE_VENTANA_MAX = "memoria_ventana_max_dias"   # opcional: sin ella, no hay tope de antigüedad y se avisa

_SEG_DIA = 86400

_RE_DIGITOS = re.compile(r"[0-9]+")
_RE_PAIS = re.compile(r"[A-Z]{2}")
_RE_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_RE_HASH = re.compile(r"sha256:[0-9a-f]{64}")

CAMPOS_INSTANTANEA = ("schema_version", "corrida_id", "ts", "generado_en", "n_paginas", "n_consultas",
                      "n_consultas_origen", "paises_consultados", "paginas", "hash")
CAMPOS_OPCIONALES_INSTANTANEA = ("capturado_en",)   # ausente en las instantáneas anteriores a este campo
CAMPOS_REGISTRO = ("page_id", "page_name", "paises", "anuncios_activos_en_muestra", "edad_oferta_dias",
                   "edad_max_dias", "muestra_truncada", "tema_slug")
CAMPOS_INDICE = ("corrida_id", "ts", "n_paginas", "n_consultas", "hash")
ORIGENES_N_CONSULTAS = ("declarado", "qids")


# ---------------------------------------------------------------------------
# Utilidades pequeñas (validación de tipos, sin float)
# ---------------------------------------------------------------------------

def _dir_memoria(raiz: Path | None) -> Path:
    return comun.dir_barrido(raiz) / "memoria"


def _exigir_corrida(corrida_id: Any) -> None:
    if not comun.corrida_id_valido(corrida_id):
        raise ErrorUso(f"corrida_id inválido {corrida_id!r}: se espera AAAA-MM-DD-<letra> (p. ej. 2026-11-06-a)")


def _exigir_ahora(ahora: Any) -> datetime:
    """`ahora` con zona (reloj inyectado), normalizado a UTC y a segundos (así `ts` es exacto al comparar)."""
    if not isinstance(ahora, datetime) or ahora.tzinfo is None or ahora.utcoffset() is None:
        raise ErrorUso("`ahora` debe ser un datetime con zona horaria (el reloj se inyecta; no hay reloj interno)")
    return ahora.astimezone(timezone.utc).replace(microsecond=0)


def _entero(valor: Any, campo: str, *, minimo: int = 0) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ErrorValidacion(f"{campo}: se esperaba un entero, llegó {type(valor).__name__}")
    if valor < minimo:
        raise ErrorValidacion(f"{campo}: {valor} es menor que {minimo}")
    return valor


def _decimal(valor: Any, campo: str) -> Decimal:
    """int, cadena decimal o Decimal → Decimal finito. Rechaza bool y float."""
    if isinstance(valor, bool) or isinstance(valor, float):
        raise ErrorValidacion(f"{campo}: use entero o cadena decimal, no {type(valor).__name__}")
    if isinstance(valor, (int, Decimal)):
        d = Decimal(valor)
    elif isinstance(valor, str):
        try:
            d = Decimal(valor.strip())
        except InvalidOperation as exc:
            raise ErrorValidacion(f"{campo}: «{valor}» no es un decimal") from exc
    else:
        raise ErrorValidacion(f"{campo}: se esperaba un número, llegó {type(valor).__name__}")
    if not d.is_finite():
        raise ErrorValidacion(f"{campo}: valor no finito")
    return d


def _texto_decimal(d: Decimal) -> str:
    """Decimal → cadena exacta y canónica (25, 25.0 y «25» dan «25»)."""
    return format(d.normalize(), "f")


def _dias_texto(segundos: int) -> str:
    """Segundos → días con 4 decimales (cadena; solo para mostrar: las comparaciones usan segundos exactos)."""
    d = (Decimal(segundos) / Decimal(_SEG_DIA)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)
    return format(d, "f")


def _texto_seguro(valor: Any, campo: str) -> str | None:
    """Nombre de página (dato no confiable): None se conserva; el resto se sanea (sustitutos sueltos → «?»,
    NFC, todo carácter de categoría Unicode C* → espacio, espacios colapsados). Nunca se interpreta.

    C* incluye los controles (Cc) y los de formato (Cf: bidi U+202E/U+2066…, joiners de ancho cero, BOM, guion
    blando), más uso privado (Co) y no asignados (Cn): ninguno puede disfrazar el orden de lectura del nombre
    (revisión de seguridad M4). Se aplica al construir una instantánea y al leerla; como el hash se calcula sobre
    el documento tal cual está guardado, esto no altera la verificación de las instantáneas ya escritas.
    """
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise ErrorValidacion(f"{campo}: se esperaba texto o null, llegó {type(valor).__name__}")
    texto = unicodedata.normalize("NFC", valor.encode("utf-8", "replace").decode("utf-8"))
    texto = "".join(" " if unicodedata.category(c)[0] == "C" else c for c in texto)
    return " ".join(texto.split())


def _id_pagina(valor: Any, campo: str) -> str:
    if isinstance(valor, bool):
        raise ErrorValidacion(f"{campo}: page_id inválido")
    if isinstance(valor, int):
        valor = str(valor) if valor >= 0 else ""
    if not isinstance(valor, str) or _RE_DIGITOS.fullmatch(valor) is None:
        raise ErrorValidacion(f"{campo}: page_id debe ser una cadena de dígitos, llegó {valor!r}")
    return valor


def _pais(valor: Any, campo: str) -> str:
    if not isinstance(valor, str) or _RE_PAIS.fullmatch(valor) is None:
        raise ErrorValidacion(f"{campo}: país ISO-2 en mayúsculas esperado, llegó {valor!r}")
    return valor


def _lista_paises(valor: Any, campo: str, *, vacia_ok: bool) -> list[str]:
    if not isinstance(valor, (list, tuple)) or (not valor and not vacia_ok):
        raise ErrorValidacion(f"{campo}: se esperaba una lista{'' if vacia_ok else ' no vacía'} de países ISO-2")
    paises = [_pais(p, f"{campo}[{i}]") for i, p in enumerate(valor)]
    if len(set(paises)) != len(paises):
        raise ErrorValidacion(f"{campo}: países repetidos")
    return sorted(paises)


def _slug(valor: Any, campo: str) -> str:
    """tema_slug: kebab ASCII con al menos una letra (un slug solo de dígitos se confundiría con un page_id)."""
    if not isinstance(valor, str) or _RE_SLUG.fullmatch(valor) is None or valor.isdigit():
        raise ErrorValidacion(f"{campo}: tema_slug debe ser kebab-case ASCII con al menos una letra, llegó {valor!r}")
    return valor


def _clave_pagina(page_id: str) -> int:
    return int(page_id)


# ---------------------------------------------------------------------------
# Hash canónico y validación de la instantánea
# ---------------------------------------------------------------------------

def _hash_contenido(doc_sin_hash: Mapping[str, Any]) -> str:
    """`sha256:<hex>` del JSON canónico (claves ordenadas, sin espacios, NFC), convención del repositorio."""
    try:
        texto = json.dumps(doc_sin_hash, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        return "sha256:" + hashlib.sha256(unicodedata.normalize("NFC", texto).encode("utf-8")).hexdigest()
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ErrorValidacion(f"instantánea no canonizable ({type(exc).__name__}): {exc}") from exc


def _sin_hash(doc: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in doc.items() if k != "hash"}


def _registro(rec: Any, ruta: str, *, estricto: bool, tema: str | None = None, tema_dado: bool = False) -> dict[str, Any]:
    """Valida y normaliza una página (formato de «Páginas» de B2, o el de la instantánea si `estricto`).

    `tema`/`tema_dado`: etiqueta externa que se impone al registro (kw `etiquetas` de `construir_instantanea`).
    """
    if not isinstance(rec, Mapping):
        raise ErrorValidacion(f"{ruta}: se esperaba un objeto")
    obligatorias = [c for c in CAMPOS_REGISTRO if c != "tema_slug"]
    faltan = [c for c in obligatorias if c not in rec]
    if faltan:
        raise ErrorValidacion(f"{ruta}: faltan campos {faltan}")
    if estricto:
        sobran = sorted(set(rec) - set(CAMPOS_REGISTRO))
        if sobran or "tema_slug" not in rec:
            raise ErrorValidacion(f"{ruta}: campos no reconocidos {sobran} o falta tema_slug")
    anuncios = _entero(rec["anuncios_activos_en_muestra"], f"{ruta}.anuncios_activos_en_muestra")
    edad = _decimal(rec["edad_oferta_dias"], f"{ruta}.edad_oferta_dias")
    edad_max = _decimal(rec["edad_max_dias"], f"{ruta}.edad_max_dias")
    if edad < 0 or edad_max < 0:
        raise ErrorValidacion(f"{ruta}: las edades no pueden ser negativas")
    if not isinstance(rec["muestra_truncada"], bool):
        raise ErrorValidacion(f"{ruta}.muestra_truncada: se esperaba un booleano")
    paises = _lista_paises(rec["paises"], f"{ruta}.paises", vacia_ok=False)
    if estricto and list(rec["paises"]) != paises:
        raise ErrorValidacion(f"{ruta}.paises: deben estar ordenados")
    if tema_dado:
        tema_slug = _slug(tema, f"{ruta}.tema_slug (etiquetas)")   # una etiqueta externa debe ser un slug: null no vale
    else:
        tema_slug = rec.get("tema_slug")
        if tema_slug is not None:
            tema_slug = _slug(tema_slug, f"{ruta}.tema_slug")
    return {
        "page_id": _id_pagina(rec["page_id"], f"{ruta}.page_id"),
        "page_name": _texto_seguro(rec["page_name"], f"{ruta}.page_name"),
        "paises": paises,
        "anuncios_activos_en_muestra": anuncios,
        "edad_oferta_dias": _texto_decimal(edad),
        "edad_max_dias": _texto_decimal(edad_max),
        "muestra_truncada": rec["muestra_truncada"],
        "tema_slug": tema_slug,
    }


def _foto(corrida_id: str, ts: datetime | None, registros: Sequence[Mapping[str, Any]],
          paises_consultados: Sequence[str] | None, hash_: str | None,
          capturado: datetime | None = None) -> dict[str, Any]:
    """Estructura interna de trabajo (índices de páginas y presencias).

    `instante` (base de toda antigüedad) = `capturado_en` si la instantánea lo trae, si no `ts`."""
    paginas = {r["page_id"]: r for r in registros}
    activas = {pid: r for pid, r in paginas.items() if r["anuncios_activos_en_muestra"] >= 1}
    presencias = {(pid, c) for pid, r in activas.items() for c in r["paises"]}
    return {"corrida_id": corrida_id, "ts": ts, "hash": hash_, "paginas": paginas, "activas": activas,
            "instante": capturado if capturado is not None else ts,
            "instante_origen": "capturado_en" if capturado is not None else "ts",
            "presencias": presencias,
            "paises_consultados": None if paises_consultados is None else frozenset(paises_consultados),
            "temas": {r["tema_slug"] for r in activas.values() if r["tema_slug"] is not None}}


def _foto_de_instantanea(doc: Any, origen: str, *, esperado: str | None = None) -> dict[str, Any]:
    """Valida una instantánea (estructura + hash propio) y la deja lista para usar. Corrupta = ErrorValidacion."""
    if not isinstance(doc, Mapping):
        raise ErrorValidacion(f"{origen}: la instantánea debe ser un objeto")
    faltan = [c for c in CAMPOS_INSTANTANEA if c not in doc]
    sobran = sorted(set(doc) - set(CAMPOS_INSTANTANEA) - set(CAMPOS_OPCIONALES_INSTANTANEA))
    if faltan or sobran:
        raise ErrorValidacion(f"{origen}: campos de la instantánea faltantes {faltan} o no reconocidos {sobran}")
    if doc["schema_version"] != SCHEMA_VERSION:
        raise ErrorValidacion(f"{origen}: schema_version {doc['schema_version']!r} no soportada (se espera {SCHEMA_VERSION})")
    corrida_id = doc["corrida_id"]
    if not comun.corrida_id_valido(corrida_id):
        raise ErrorValidacion(f"{origen}: corrida_id inválido {corrida_id!r}")
    if esperado is not None and corrida_id != esperado:
        raise ErrorValidacion(f"{origen}: el archivo dice corrida_id {corrida_id} y se esperaba {esperado}")
    ts = comun.parsear_z(doc["ts"])
    capturado = None
    if "capturado_en" in doc:
        capturado = comun.parsear_z(doc["capturado_en"])
        if capturado > ts:
            raise ErrorValidacion(f"{origen}: capturado_en ({doc['capturado_en']}) es posterior a ts ({doc['ts']}): "
                                  "no se puede guardar algo antes de capturarlo")
    if doc["generado_en"] is not None:
        comun.parsear_z(doc["generado_en"])
    paginas_doc = doc["paginas"]
    if not isinstance(paginas_doc, list):
        raise ErrorValidacion(f"{origen}.paginas: se esperaba una lista")
    registros = [_registro(r, f"{origen}.paginas[{i}]", estricto=True) for i, r in enumerate(paginas_doc)]
    ids = [r["page_id"] for r in registros]
    if len(set(ids)) != len(ids):
        raise ErrorValidacion(f"{origen}.paginas: page_id repetido")
    if ids != sorted(ids, key=_clave_pagina):
        raise ErrorValidacion(f"{origen}.paginas: deben estar ordenadas por page_id")
    if _entero(doc["n_paginas"], f"{origen}.n_paginas") != len(registros):
        raise ErrorValidacion(f"{origen}: n_paginas no coincide con la cantidad de páginas")
    _entero(doc["n_consultas"], f"{origen}.n_consultas")
    if doc["n_consultas_origen"] not in ORIGENES_N_CONSULTAS:
        raise ErrorValidacion(f"{origen}.n_consultas_origen: debe ser uno de {ORIGENES_N_CONSULTAS}")
    consultados = doc["paises_consultados"]
    if consultados is not None:
        consultados = _lista_paises(consultados, f"{origen}.paises_consultados", vacia_ok=False)
        if list(doc["paises_consultados"]) != consultados:
            raise ErrorValidacion(f"{origen}.paises_consultados: deben estar ordenados")
        fuera = sorted({c for r in registros for c in r["paises"]} - set(consultados))
        if fuera:
            raise ErrorValidacion(f"{origen}: páginas en países no consultados {fuera}")
    if not isinstance(doc["hash"], str) or _RE_HASH.fullmatch(doc["hash"]) is None:
        raise ErrorValidacion(f"{origen}.hash: formato inválido")
    calculado = _hash_contenido(_sin_hash(doc))
    if calculado != doc["hash"]:
        raise _HashDistinto(
            f"{origen}: el hash no coincide (guardado {doc['hash'][:19]}…, calculado {calculado[:19]}…): la instantánea "
            "fue alterada o está corrupta y NO se usa")
    return _foto(corrida_id, ts, registros, consultados, doc["hash"], capturado)


def _fuente_unica(kw: Any, doc: Mapping[str, Any], clave: str) -> Any:
    """Dato opcional que puede llegar por argumento o dentro del documento: si llega por ambos y difieren, error."""
    if kw is not None and doc.get(clave) is not None and doc[clave] != kw:
        raise ErrorValidacion(f"{clave}: el argumento ({kw!r}) contradice el documento de páginas ({doc[clave]!r})")
    return kw if kw is not None else doc.get(clave)


# ---------------------------------------------------------------------------
# Construcción, guardado y lectura
# ---------------------------------------------------------------------------

def construir_instantanea(paginas_doc: Any, corrida_id: str, *, ahora: datetime,
                          etiquetas: Mapping[str, str] | None = None, n_consultas: int | None = None,
                          paises_consultados: Sequence[str] | None = None,
                          capturado_en: str | datetime | None = None) -> dict[str, Any]:
    """Documento «Páginas» (B2) → instantánea (dict con hash). No escribe nada.

    - `ahora` (con zona) es el `ts` de la instantánea (cuándo se guarda).
    - `capturado_en`: instante de la captura (máximo de `capturado_en` de los crudos), por argumento o como campo
      `capturado_en` del documento de páginas (UTC con Z); si llega por ambos y difieren, error. Si está, es la base
      de toda antigüedad (ver «Definiciones» 3) y se guarda; si no, el campo se omite y la antigüedad se mide por
      `ts`. Debe ser ≤ `ahora`.
    - `etiquetas`: opcional {page_id: tema_slug}; se impone a las páginas listadas (las claves que no corresponden
      a ninguna página se ignoran). Sin ella se respeta el `tema_slug` que traiga cada página, o `null`.
    - `n_consultas`: consultas del plan (si no llega, ni el documento la trae, se deriva de la unión de `qids` de las
      páginas y se marca `n_consultas_origen: "qids"`: es un mínimo, porque una consulta sin resultados no aparece).
    - `paises_consultados`: países cubiertos por el barrido (del plan). Sin él, la cobertura queda desconocida.
    Errores: ErrorUso (corrida_id/ahora inválidos), ErrorValidacion (documento fuera de contrato).
    """
    _exigir_corrida(corrida_id)
    ts = _exigir_ahora(ahora)
    if not isinstance(paginas_doc, Mapping) or not isinstance(paginas_doc.get("paginas"), list):
        raise ErrorValidacion("paginas_doc: se esperaba el documento «Páginas» {corrida_id, generado_en, paginas, ...}")
    if paginas_doc.get("corrida_id") != corrida_id:
        raise ErrorValidacion(f"paginas_doc: corrida_id {paginas_doc.get('corrida_id')!r} no es {corrida_id}")
    generado = paginas_doc.get("generado_en")
    if generado is not None:
        comun.parsear_z(generado)
    if etiquetas is not None and not isinstance(etiquetas, Mapping):
        raise ErrorUso("etiquetas: se espera un mapa {page_id: tema_slug}")
    registros: list[dict[str, Any]] = []
    for i, rec in enumerate(paginas_doc["paginas"]):
        pid = _id_pagina(rec.get("page_id") if isinstance(rec, Mapping) else None, f"paginas[{i}].page_id")
        impuesta = etiquetas is not None and pid in etiquetas
        registros.append(_registro(rec, f"paginas[{i}]", estricto=False,
                                   tema=etiquetas[pid] if impuesta else None, tema_dado=impuesta))
    ids = [r["page_id"] for r in registros]
    if len(set(ids)) != len(ids):
        raise ErrorValidacion("paginas_doc: page_id repetido")
    registros.sort(key=lambda r: _clave_pagina(r["page_id"]))

    declarado = _fuente_unica(n_consultas, paginas_doc, "n_consultas")
    qids_union: set[str] = set()
    todas_con_qids = True
    for rec in paginas_doc["paginas"]:
        qids = rec.get("qids")
        if isinstance(qids, list) and all(isinstance(q, str) for q in qids):
            qids_union.update(qids)
        else:
            todas_con_qids = False
    if declarado is not None:
        total = _entero(declarado, "n_consultas")
        origen_n = "declarado"
        if todas_con_qids and total < len(qids_union):
            raise ErrorValidacion(f"n_consultas {total} es menor que las {len(qids_union)} consultas distintas "
                                  "que citan las páginas")
    elif todas_con_qids:
        total, origen_n = len(qids_union), "qids"
    else:
        raise ErrorValidacion("n_consultas: no llegó por argumento ni en el documento, y las páginas no traen `qids` "
                              "para derivarla (falla cerrado: no se inventa)")

    captura = capturado_en
    if isinstance(captura, datetime):
        captura = comun.iso_z(captura)
    captura = _fuente_unica(captura, paginas_doc, "capturado_en")
    if captura is not None and comun.parsear_z(captura) > ts:
        raise ErrorValidacion(f"capturado_en ({captura}) es posterior a `ahora` ({comun.iso_z(ts)})")

    consultados = _fuente_unica(None if paises_consultados is None else list(paises_consultados),
                                paginas_doc, "paises_consultados")
    if consultados is not None:
        consultados = _lista_paises(consultados, "paises_consultados", vacia_ok=False)
        fuera = sorted({c for r in registros for c in r["paises"]} - set(consultados))
        if fuera:
            raise ErrorValidacion(f"hay páginas en países que no figuran en paises_consultados: {fuera}")

    doc = {
        "schema_version": SCHEMA_VERSION,
        "corrida_id": corrida_id,
        "ts": comun.iso_z(ts),
        "generado_en": generado,
        "n_paginas": len(registros),
        "n_consultas": total,
        "n_consultas_origen": origen_n,
        "paises_consultados": consultados,
        "paginas": registros,
    }
    if captura is not None:
        doc["capturado_en"] = captura   # solo si se declaró: sin él, el documento es idéntico al formato anterior
    doc["hash"] = _hash_contenido(doc)
    return doc


def _leer_indice(ruta: Path) -> list[dict[str, Any]]:
    """Líneas de `indice.jsonl` validadas. Archivo ausente = []. Línea rota, campo raro o corrida repetida = ErrorValidacion."""
    if not ruta.exists():
        return []
    try:
        texto = ruta.read_bytes().decode("utf-8")
    except OSError as exc:
        raise ErrorUso(f"no se pudo leer {ruta}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise ErrorValidacion(f"{ruta}: no es UTF-8 válido ({exc})") from exc
    entradas: list[dict[str, Any]] = []
    vistas: set[str] = set()
    for n, linea in enumerate(texto.split("\n"), start=1):
        if not linea.strip():
            continue
        donde = f"{ruta} línea {n}"
        try:
            obj = json.loads(linea, parse_constant=_rechazar_constante)
        except ValueError as exc:
            raise ErrorValidacion(f"{donde}: JSON inválido ({exc})") from exc
        if not isinstance(obj, dict) or set(obj) != set(CAMPOS_INDICE):
            raise ErrorValidacion(f"{donde}: se esperaba un objeto con exactamente {list(CAMPOS_INDICE)}")
        if not comun.corrida_id_valido(obj["corrida_id"]):
            raise ErrorValidacion(f"{donde}: corrida_id inválido {obj['corrida_id']!r}")
        comun.parsear_z(obj["ts"])
        _entero(obj["n_paginas"], f"{donde}.n_paginas")
        _entero(obj["n_consultas"], f"{donde}.n_consultas")
        if not isinstance(obj["hash"], str) or _RE_HASH.fullmatch(obj["hash"]) is None:
            raise ErrorValidacion(f"{donde}: hash con formato inválido")
        if obj["corrida_id"] in vistas:
            raise ErrorValidacion(f"{donde}: corrida_id {obj['corrida_id']} repetido en el índice")
        vistas.add(obj["corrida_id"])
        entradas.append(obj)
    return entradas


def _orden_indice(e: Mapping[str, Any]) -> tuple[datetime, str]:
    return comun.parsear_z(e["ts"]), e["corrida_id"]


def guardar_instantanea(paginas_doc: Any, corrida_id: str, *, raiz: Path | None = None, ahora: datetime,
                        etiquetas: Mapping[str, str] | None = None, n_consultas: int | None = None,
                        paises_consultados: Sequence[str] | None = None,
                        capturado_en: str | datetime | None = None) -> Path:
    """Guarda la instantánea de un barrido en `empresa/barrido/memoria/<corrida_id>.json` y la anota en el índice.

    Inmutable: una corrida se guarda UNA vez. Si el archivo ya existe, o el índice ya registra la corrida, es
    ErrorUso y no se toca nada (el contenido guardado nunca se sobrescribe). El índice (`indice.jsonl`, una línea
    por corrida) lleva `corrida_id, ts, n_paginas, n_consultas, hash`. Un índice dañado también detiene el guardado
    (ErrorValidacion): no se anexa a un índice en el que no se puede confiar. Orden: primero el archivo (atómico, sin
    sobrescribir), luego el índice; si el proceso muere en medio, `verificar_integridad` lo ve como «archivo sin
    índice». Argumentos opcionales: ver `construir_instantanea`. Devuelve la ruta del archivo.
    """
    _exigir_corrida(corrida_id)
    doc = construir_instantanea(paginas_doc, corrida_id, ahora=ahora, etiquetas=etiquetas,
                                n_consultas=n_consultas, paises_consultados=paises_consultados,
                                capturado_en=capturado_en)
    carpeta = _dir_memoria(raiz)
    ruta = carpeta / f"{corrida_id}.json"
    indice = carpeta / NOMBRE_INDICE
    if ruta.exists():
        raise ErrorUso(f"la instantánea {corrida_id} ya existe ({ruta}): las instantáneas son inmutables")
    if any(e["corrida_id"] == corrida_id for e in _leer_indice(indice)):
        raise ErrorUso(f"el índice ya registra la corrida {corrida_id}: las instantáneas son inmutables "
                       "(revise con verificar_integridad)")
    comun.escribir_json_nuevo(ruta, doc)
    comun.anexar_jsonl(indice, {"corrida_id": corrida_id, "ts": doc["ts"], "n_paginas": doc["n_paginas"],
                                "n_consultas": doc["n_consultas"], "hash": doc["hash"]})
    return ruta


def listar_instantaneas(raiz: Path | None = None) -> list[dict[str, Any]]:
    """Entradas del índice, ordenadas por (`ts`, `corrida_id`): `[{corrida_id, ts, n_paginas, n_consultas, hash}]`.

    No abre los archivos (para eso, `cargar_instantanea` / `verificar_integridad`). Sin índice = lista vacía.
    Índice dañado = ErrorValidacion.
    """
    return sorted(_leer_indice(_dir_memoria(raiz) / NOMBRE_INDICE), key=_orden_indice)


def cargar_instantanea(corrida_id: str, raiz: Path | None = None) -> dict[str, Any]:
    """Lee UNA instantánea y la verifica: estructura, hash propio y coincidencia con el índice.

    ErrorUso si no existe; ErrorValidacion si está corrupta (hash distinto, estructura rota) o si el índice no la
    registra o la contradice. Una instantánea que no pasa estas pruebas no se devuelve nunca.
    """
    _exigir_corrida(corrida_id)
    carpeta = _dir_memoria(raiz)
    ruta = carpeta / f"{corrida_id}.json"
    if not ruta.is_file():
        raise ErrorUso(f"no existe la instantánea {corrida_id} ({ruta})")
    doc = comun.leer_json(ruta)
    _foto_de_instantanea(doc, str(ruta), esperado=corrida_id)
    entrada = next((e for e in _leer_indice(carpeta / NOMBRE_INDICE) if e["corrida_id"] == corrida_id), None)
    if entrada is None:
        raise ErrorValidacion(f"{ruta}: la corrida no figura en {NOMBRE_INDICE}: archivo sin índice, no se usa")
    for campo in CAMPOS_INDICE:
        if entrada[campo] != doc[campo]:
            raise ErrorValidacion(f"{ruta}: {campo} del archivo ({doc[campo]!r}) no coincide con el índice "
                                  f"({entrada[campo]!r}): no se usa")
    return doc


def cargar_previas(raiz: Path | None = None, *, excluir: str | None = None) -> list[dict[str, Any]]:
    """Todas las instantáneas del índice (menos `excluir`), verificadas y ordenadas por (`ts`, `corrida_id`).

    Falla cerrado: UNA instantánea corrupta detiene la carga (ErrorValidacion) en vez de omitirse en silencio;
    `verificar_integridad` dice cuál es.
    """
    return [cargar_instantanea(e["corrida_id"], raiz)
            for e in listar_instantaneas(raiz) if e["corrida_id"] != excluir]


def verificar_integridad(raiz: Path | None = None) -> list[dict[str, str]]:
    """Revisa la carpeta de memoria; devuelve los problemas (lista vacía = todo íntegro).

    Cada problema es `{tipo, corrida_id, detalle}` con `tipo` ∈ `indice_invalido` (el índice no se puede leer),
    `indice_sin_archivo`, `archivo_sin_indice`, `archivo_invalido` (ilegible o con estructura rota),
    `hash_distinto` (contenido ≠ hash propio o ≠ hash del índice) e `indice_inconsistente` (ts/n_paginas/n_consultas
    del índice ≠ archivo). Orden determinista. No modifica nada.
    """
    carpeta = _dir_memoria(raiz)
    problemas: list[dict[str, str]] = []

    def anotar(tipo: str, corrida_id: str, detalle: str) -> None:
        problemas.append({"tipo": tipo, "corrida_id": corrida_id, "detalle": detalle})

    try:
        entradas = {e["corrida_id"]: e for e in _leer_indice(carpeta / NOMBRE_INDICE)}
    except ErrorFabrica as exc:
        return [{"tipo": "indice_invalido", "corrida_id": "", "detalle": str(exc)}]
    archivos = {p.stem: p for p in carpeta.glob("*.json")} if carpeta.is_dir() else {}
    for corrida_id in sorted(entradas):
        entrada = entradas[corrida_id]
        ruta = carpeta / f"{corrida_id}.json"
        if not ruta.is_file():
            anotar("indice_sin_archivo", corrida_id, f"el índice registra {corrida_id} pero falta {ruta.name}")
            continue
        try:
            doc = comun.leer_json(ruta)
            _foto_de_instantanea(doc, ruta.name, esperado=corrida_id)
        except _HashDistinto as exc:
            anotar("hash_distinto", corrida_id, str(exc))
            continue
        except ErrorFabrica as exc:
            anotar("archivo_invalido", corrida_id, str(exc))
            continue
        if doc["hash"] != entrada["hash"]:
            anotar("hash_distinto", corrida_id,
                   f"el hash del archivo ({doc['hash'][:19]}…) no coincide con el del índice ({entrada['hash'][:19]}…)")
        for campo in ("ts", "n_paginas", "n_consultas"):
            if doc[campo] != entrada[campo]:
                anotar("indice_inconsistente", corrida_id,
                       f"{campo} del archivo ({doc[campo]!r}) no coincide con el índice ({entrada[campo]!r})")
    for nombre in sorted(set(archivos) - set(entradas)):
        anotar("archivo_sin_indice", nombre, f"{archivos[nombre].name} existe pero {NOMBRE_INDICE} no lo registra")
    return problemas


# ---------------------------------------------------------------------------
# Análisis: base de comparación, entrantes y diff
# ---------------------------------------------------------------------------

def _ventana(par: Any) -> tuple[Decimal, Decimal | None]:
    """(`memoria_ventana_min_dias`, `memoria_ventana_max_dias` o None) de los parámetros del barrido."""
    if not isinstance(par, Mapping):
        raise ErrorUso("par: se esperan los parámetros del barrido (el dict de comun.cargar_parametros_barrido)")
    if par.get(CLAVE_VENTANA_MIN) is None:
        raise ErrorLimite(f"falta el parámetro {CLAVE_VENTANA_MIN} (falla cerrado: sin él no se calcula entrantes_30d)")
    minimo = _decimal(par[CLAVE_VENTANA_MIN], CLAVE_VENTANA_MIN)
    if minimo <= 0:
        raise ErrorValidacion(f"{CLAVE_VENTANA_MIN}: debe ser > 0")
    maximo = None
    if par.get(CLAVE_VENTANA_MAX) is not None:
        maximo = _decimal(par[CLAVE_VENTANA_MAX], CLAVE_VENTANA_MAX)
        if maximo < minimo:
            raise ErrorValidacion(f"{CLAVE_VENTANA_MAX} ({maximo}) no puede ser menor que {CLAVE_VENTANA_MIN} ({minimo})")
    return minimo, maximo


def _segundos(ahora: datetime, ts: datetime) -> int:
    delta = ahora - ts
    return delta.days * _SEG_DIA + delta.seconds


def _foto_de_actual(actual: Any) -> dict[str, Any]:
    """`actual` puede ser una instantánea (con `hash`, se verifica) o el documento «Páginas» de B2 (sin etiquetas)."""
    if not isinstance(actual, Mapping):
        raise ErrorUso("actual: se espera una instantánea o el documento «Páginas»")
    if "hash" in actual:
        return _foto_de_instantanea(actual, "actual")
    corrida_id = actual.get("corrida_id")
    if not comun.corrida_id_valido(corrida_id) or not isinstance(actual.get("paginas"), list):
        raise ErrorValidacion("actual: se esperaba el documento «Páginas» con corrida_id válido y `paginas`")
    registros = [_registro(r, f"actual.paginas[{i}]", estricto=False) for i, r in enumerate(actual["paginas"])]
    ids = [r["page_id"] for r in registros]
    if len(set(ids)) != len(ids):
        raise ErrorValidacion("actual.paginas: page_id repetido")
    consultados = actual.get("paises_consultados")
    if consultados is not None:
        consultados = _lista_paises(consultados, "actual.paises_consultados", vacia_ok=False)
    return _foto(corrida_id, None, registros, consultados, None)


def _texto_pais_opcional(pais: Any) -> str | None:
    if pais is None:
        return None
    if not isinstance(pais, str) or _RE_PAIS.fullmatch(pais) is None:
        raise ErrorUso(f"pais: se espera un código ISO-2 en mayúsculas o None, llegó {pais!r}")
    return pais


class _Analisis:
    """Resuelve una vez las bases de comparación (previas verificadas) y calcula entrantes y cambios."""

    def __init__(self, actual: Any, previas: Any, ahora: datetime, par: Any) -> None:
        self.ahora = _exigir_ahora(ahora)
        self.minimo, self.maximo = _ventana(par)
        self.actual = _foto_de_actual(actual)
        self.previas = self._previas(previas)
        self.cambios = self.previas[-1] if self.previas else None
        self.base = self._elegir_base()
        self._por_tema: dict[str, list[dict[str, Any]]] = {}
        for pid in sorted(self.actual["activas"], key=_clave_pagina):
            rec = self.actual["activas"][pid]
            if rec["tema_slug"] is not None:
                self._por_tema.setdefault(rec["tema_slug"], []).append(rec)

    def _previas(self, previas: Any) -> list[dict[str, Any]]:
        if not isinstance(previas, (list, tuple)):
            raise ErrorUso("previas: se espera una lista de instantáneas (cargar_previas)")
        fotos: list[dict[str, Any]] = []
        vistas: set[str] = set()
        for i, doc in enumerate(previas):
            foto = _foto_de_instantanea(doc, f"previas[{i}]")  # corrupta = ErrorValidacion, NO se usa
            if foto["corrida_id"] in vistas:
                raise ErrorValidacion(f"previas[{i}]: la corrida {foto['corrida_id']} viene repetida")
            vistas.add(foto["corrida_id"])
            if foto["corrida_id"] == self.actual["corrida_id"]:
                continue  # la propia corrida no es «previa» de sí misma
            if foto["ts"] > self.ahora:
                raise ErrorValidacion(f"previas[{i}]: la instantánea {foto['corrida_id']} es posterior a `ahora` "
                                      f"({comun.iso_z(foto['ts'])} > {comun.iso_z(self.ahora)}): reloj inconsistente")
            fotos.append(foto)
        return sorted(fotos, key=lambda f: (f["instante"], f["ts"], f["corrida_id"]))

    def _elegir_base(self) -> dict[str, Any]:
        minimo_s = self.minimo * _SEG_DIA
        maximo_s = None if self.maximo is None else self.maximo * _SEG_DIA
        objetivo_s = DIAS_VENTANA_METRICA * _SEG_DIA
        candidatas = []
        recientes = vencidas = 0
        for f in self.previas:
            edad_s = _segundos(self.ahora, f["instante"])
            if edad_s < minimo_s:
                recientes += 1
            elif maximo_s is not None and edad_s > maximo_s:
                vencidas += 1
            else:
                candidatas.append((abs(edad_s - objetivo_s), -edad_s, f["corrida_id"], f, edad_s))
        base: dict[str, Any] = {"foto": None, "edad_s": None, "n_previas": len(self.previas),
                                "n_muy_recientes": recientes, "n_vencidas": vencidas}
        if candidatas:
            elegida = min(candidatas, key=lambda c: c[:3])
            base.update(estado="ok", motivo=None, foto=elegida[3], edad_s=elegida[4])
            return base
        total = len(self.previas)
        if total == 0:
            motivo = "primera_corrida"
        elif recientes == total:
            motivo = "base_demasiado_reciente"
        elif vencidas == total:
            motivo = "base_vencida"
        else:
            motivo = "sin_previa_en_ventana"
        base.update(estado="sin_base", motivo=motivo)
        return base

    # -- descriptores para la salida ------------------------------------------------------------------------

    def descriptor_base_entrantes(self) -> dict[str, Any]:
        b = self.base
        return {
            "estado": b["estado"], "motivo": b["motivo"],
            "corrida_id": None if b["foto"] is None else b["foto"]["corrida_id"],
            "antiguedad_dias": None if b["edad_s"] is None else _dias_texto(b["edad_s"]),
            "ventana_dias": str(DIAS_VENTANA_METRICA),
            "min_dias": _texto_decimal(self.minimo),
            "max_dias": None if self.maximo is None else _texto_decimal(self.maximo),
            "n_previas": b["n_previas"], "n_muy_recientes": b["n_muy_recientes"], "n_vencidas": b["n_vencidas"],
            "ventana_excedida": bool(b["edad_s"] is not None and b["edad_s"] > DIAS_VENTANA_METRICA * _SEG_DIA),
            "antiguedad_desde": None if b["foto"] is None else b["foto"]["instante_origen"],
        }

    def descriptor_base_cambios(self) -> dict[str, Any]:
        if self.cambios is None:
            return {"estado": "sin_base", "motivo": "primera_corrida", "corrida_id": None, "antiguedad_dias": None}
        return {"estado": "ok", "motivo": None, "corrida_id": self.cambios["corrida_id"],
                "antiguedad_dias": _dias_texto(_segundos(self.ahora, self.cambios["instante"])),
                "antiguedad_desde": self.cambios["instante_origen"]}

    # -- clasificación de entrantes -------------------------------------------------------------------------

    def _clase_pagina(self, rec: Mapping[str, Any]) -> str:
        """`conocida` (activa en la base), `nueva` (empezó después de la base) o `reaparecida` (ya existía)."""
        if rec["page_id"] in self.base["foto"]["activas"]:
            return "conocida"
        if Decimal(rec["edad_max_dias"]) * _SEG_DIA <= self.base["edad_s"]:
            return "nueva"
        return "reaparecida"

    def _clase_presencia(self, rec: Mapping[str, Any], pais: str) -> str:
        """`presente`, `expansion` (página conocida que llega a este país), `nueva` o `reaparecida`."""
        if (rec["page_id"], pais) in self.base["foto"]["presencias"]:
            return "presente"
        clase = self._clase_pagina(rec)
        return "expansion" if clase == "conocida" else clase

    def _resolver_clave(self, clave: Any) -> tuple[str, list[dict[str, Any]]]:
        if isinstance(clave, bool) or not isinstance(clave, (str, int)):
            raise ErrorUso(f"pagina_o_tema: se espera un page_id (dígitos) o un tema_slug, llegó {clave!r}")
        clave = str(clave)
        activas = self.actual["activas"]
        if _RE_DIGITOS.fullmatch(clave):
            if clave not in activas:
                raise ErrorUso(f"la página {clave} no está activa en la instantánea actual {self.actual['corrida_id']}")
            return "pagina", [activas[clave]]
        if _RE_SLUG.fullmatch(clave) is None:
            raise ErrorUso(f"pagina_o_tema {clave!r}: no es un page_id (dígitos) ni un tema_slug (kebab ASCII)")
        paginas = self._por_tema.get(clave)
        if not paginas:
            raise ErrorUso(f"el tema {clave!r} no existe en la instantánea actual {self.actual['corrida_id']}")
        return "tema", paginas

    def entrantes(self, clave: Any, pais: str | None) -> dict[str, Any]:
        _, paginas = self._resolver_clave(clave)
        detalle: dict[str, Any] = {"valor": None, "estado": self.base["estado"], "motivo": self.base["motivo"],
                                   "pais": pais, "piso": None, "base_truncada": None, "paginas": [],
                                   "reaparecidas": None, "advertencias": []}
        if self.base["estado"] != "ok":
            return detalle  # sin base: None, jamás 0
        base = self.base["foto"]
        if pais is not None:
            for nombre, foto in (("ahora", self.actual), ("en la base", base)):
                consultados = foto["paises_consultados"]
                if consultados is None:
                    detalle["advertencias"].append(
                        f"cobertura de países desconocida {nombre}: no se sabe si {pais} se consultó")
                elif pais not in consultados:
                    detalle.update(estado="sin_base", motivo=f"pais_no_consultado_{'ahora' if nombre == 'ahora' else 'en_base'}")
                    return detalle
        en_alcance = [r for r in paginas if pais is None or pais in r["paises"]]
        contadas: list[str] = []
        reaparecidas = 0
        for rec in en_alcance:
            clase = self._clase_pagina(rec) if pais is None else self._clase_presencia(rec, pais)
            if clase == "reaparecida":
                reaparecidas += 1
            elif clase == "nueva" or (pais is not None and clase == "expansion"):
                contadas.append(rec["page_id"])
        detalle.update(
            valor=len(contadas), paginas=contadas, reaparecidas=reaparecidas,
            piso=any(r["muestra_truncada"] for r in en_alcance),
            base_truncada=any(r["muestra_truncada"] for r in base["activas"].values()
                              if pais is None or pais in r["paises"]))
        if self.base["edad_s"] > DIAS_VENTANA_METRICA * _SEG_DIA:
            detalle["advertencias"].append(
                f"la base tiene {_dias_texto(self.base['edad_s'])} días (> {DIAS_VENTANA_METRICA}): "
                "el conteo cubre una ventana más larga que la métrica")
        return detalle

    # -- cambios --------------------------------------------------------------------------------------------

    def cambios_paginas(self) -> dict[str, Any]:
        salida: dict[str, Any] = {"paginas_nuevas": [], "paginas_que_crecen": [], "paginas_que_decrecen": [],
                                  "paginas_desaparecidas": [], "paginas_que_cambian_de_pais": []}
        if self.cambios is None:
            return salida
        antes, ahora_ = self.cambios["activas"], self.actual["activas"]
        for pid in sorted(ahora_, key=_clave_pagina):
            rec = ahora_[pid]
            if pid not in antes:
                if self.base["estado"] == "ok":
                    entrante: bool | None = self._clase_pagina(rec) == "nueva"
                else:
                    entrante = None
                salida["paginas_nuevas"].append({
                    "page_id": pid, "page_name": rec["page_name"], "paises": rec["paises"],
                    "anuncios_activos_en_muestra": rec["anuncios_activos_en_muestra"],
                    "tema_slug": rec["tema_slug"], "entrante": entrante})
                continue
            previo = antes[pid]
            delta = rec["anuncios_activos_en_muestra"] - previo["anuncios_activos_en_muestra"]
            if delta != 0:
                item = {"page_id": pid, "page_name": rec["page_name"],
                        "antes": previo["anuncios_activos_en_muestra"],
                        "despues": rec["anuncios_activos_en_muestra"], "delta": delta,
                        "piso": bool(rec["muestra_truncada"] or previo["muestra_truncada"])}
                salida["paginas_que_crecen" if delta > 0 else "paginas_que_decrecen"].append(item)
            if rec["paises"] != previo["paises"]:
                salida["paginas_que_cambian_de_pais"].append({
                    "page_id": pid, "page_name": rec["page_name"],
                    "paises_antes": previo["paises"], "paises_ahora": rec["paises"],
                    "paises_nuevos": sorted(set(rec["paises"]) - set(previo["paises"])),
                    "paises_perdidos": sorted(set(previo["paises"]) - set(rec["paises"]))})
        for pid in sorted(set(antes) - set(ahora_), key=_clave_pagina):
            previo = antes[pid]
            salida["paginas_desaparecidas"].append({
                "page_id": pid, "page_name": previo["page_name"], "paises": previo["paises"],
                "anuncios_activos_en_muestra": previo["anuncios_activos_en_muestra"]})
        salida["paginas_que_crecen"].sort(key=lambda i: (-i["delta"], _clave_pagina(i["page_id"])))
        salida["paginas_que_decrecen"].sort(key=lambda i: (i["delta"], _clave_pagina(i["page_id"])))
        return salida

    def temas(self) -> tuple[list[str], str]:
        if self.cambios is None:
            return [], "sin_base"
        if not self.actual["temas"]:
            return [], "sin_etiquetas"
        if not self.cambios["temas"]:
            return [], "base_sin_etiquetas"
        return sorted(self.actual["temas"] - self.cambios["temas"]), "ok"


def entrantes_detalle(pagina_o_tema: Any, actual: Any, previas: Any, *, ahora: datetime, par: Mapping[str, Any],
                      pais: str | None = None) -> dict[str, Any]:
    """Como `entrantes_30d`, pero con el desglose: `{valor, estado, motivo, pais, piso, base_truncada, paginas,
    reaparecidas, advertencias, base}`. `valor` es int o None; `estado` es «ok» o «sin_base» (con su `motivo`);
    `piso` indica que `actual` está truncado en el alcance (el conteo puede ser mayor); `base_truncada`, que la base
    lo estaba (pudo contar falsos entrantes); `paginas`, los page_id contados; `reaparecidas`, las excluidas por
    ser más viejas que la base."""
    analisis = _Analisis(actual, previas, ahora, par)
    detalle = analisis.entrantes(pagina_o_tema, _texto_pais_opcional(pais))
    detalle["base"] = analisis.descriptor_base_entrantes()
    return detalle


def entrantes_30d(pagina_o_tema: Any, actual: Any, previas: Any, *, ahora: datetime, par: Mapping[str, Any],
                  pais: str | None = None) -> int | None:
    """Anunciantes que entraron en la ventana de 30 días; `None` si no se puede medir (JAMÁS 0 sin base).

    - `pagina_o_tema`: un `page_id` (cadena de dígitos) o un `tema_slug`. Una página que no está activa en
      `actual`, o un tema que no existe, es ErrorUso (evita que un error de tecleo parezca «0 entrantes»).
    - `actual`: instantánea (`construir_instantanea`/`cargar_instantanea`) o el documento «Páginas» de B2.
    - `previas`: lista de instantáneas (`cargar_previas`). Cada una se verifica (hash) antes de usarse: una corrupta
      lanza ErrorValidacion. La propia corrida de `actual` se ignora.
    - `ahora`: reloj inyectado (con zona). `par`: parámetros del barrido (`memoria_ventana_min_dias`, obligatorio;
      `memoria_ventana_max_dias`, opcional).
    - `pais`: ISO-2 del mercado destino. Sin él, el alcance es global (páginas nuevas en el mapa). **Para llenar
      `mercados[].hueco.entrantes_30d` de una ficha, pasar el mercado destino.**
    Definición completa de «entrante», base y cobertura: bloque «Definiciones» al inicio del módulo.
    Devuelve int ≥ 0 si hay base válida; `None` si no hay instantánea previa con antigüedad ≥
    `memoria_ventana_min_dias` (primera corrida, previa demasiado reciente o vencida) o si el mercado no se consultó.
    """
    return entrantes_detalle(pagina_o_tema, actual, previas, ahora=ahora, par=par, pais=pais)["valor"]


def diff(actual: Any, previas: Any, *, par: Mapping[str, Any], ahora: datetime) -> dict[str, Any]:
    """Cambios del barrido `actual` frente a la memoria, más `entrantes_30d` por tema u oferta.

    Entradas: las mismas que `entrantes_30d`. Salida (todo texto, entero, bool o null; sin float):
    - `estado`: «ok» o «sin_base» (no hay base para `entrantes_30d`: todos los valores van `null`);
      `base_entrantes` y `base_cambios` explican cada base (corrida, antigüedad, motivo).
    - `paginas_nuevas`, `paginas_que_crecen`, `paginas_que_decrecen`, `paginas_desaparecidas`,
      `paginas_que_cambian_de_pais`, `temas_nuevos` (+ `temas_estado`), frente a la base de cambios (la previa
      más reciente). Sin previa: listas vacías. «Desaparecida» = no vista en la muestra actual (no prueba que dejó
      de anunciar); `piso` marca los cambios afectados por una muestra truncada.
    - `entrantes_30d`: {tema_slug | page_id (páginas sin tema): int | None} en alcance global;
      `entrantes_30d_por_pais`: lo mismo por mercado ({clave: {ISO2: int | None}}), que es lo que usa la ficha;
      `entrantes_30d_piso_por_pais`: {clave: {ISO2: bool | None}}, verdadero si ese conteo se midió sobre muestras
      truncadas (actual o base): es un piso/aproximación, no una cifra exacta (un 0 no prueba hueco). `None` si el
      valor es `None`.
    Determinista: no depende del orden de `previas`.
    """
    a = _Analisis(actual, previas, ahora, par)
    cambios = a.cambios_paginas()
    temas_nuevos, temas_estado = a.temas()
    activas = a.actual["activas"]
    temas = sorted(a.actual["temas"])
    sueltas = sorted((pid for pid, r in activas.items() if r["tema_slug"] is None), key=_clave_pagina)
    if a.actual["paises_consultados"] is not None:
        paises = sorted(a.actual["paises_consultados"])
    else:
        paises = sorted({c for r in activas.values() for c in r["paises"]})
    globales: dict[str, int | None] = {}
    por_pais: dict[str, dict[str, int | None]] = {}
    piso_por_pais: dict[str, dict[str, bool | None]] = {}
    for clave in temas + sueltas:
        globales[clave] = a.entrantes(clave, None)["valor"]
        detalles = {c: a.entrantes(clave, c) for c in paises}
        por_pais[clave] = {c: d["valor"] for c, d in detalles.items()}
        piso_por_pais[clave] = {c: None if d["valor"] is None else bool(d["piso"] or d["base_truncada"])
                                for c, d in detalles.items()}

    advertencias: list[str] = []
    if a.base["estado"] != "ok":
        advertencias.append(f"sin base para entrantes_30d ({a.base['motivo']}): todos los valores van null, nunca 0")
    elif a.base["edad_s"] > DIAS_VENTANA_METRICA * _SEG_DIA:
        advertencias.append(f"la base de entrantes tiene {_dias_texto(a.base['edad_s'])} días (> {DIAS_VENTANA_METRICA}): "
                            "el conteo cubre una ventana más larga que la métrica")
    if a.maximo is None:
        advertencias.append(f"{CLAVE_VENTANA_MAX} no está definido: no hay tope de antigüedad para la base de entrantes")
    if a.actual["paises_consultados"] is None:
        advertencias.append("la instantánea actual no declara paises_consultados: la cobertura por mercado es desconocida")
    if a.cambios is None:
        advertencias.append("primera corrida: sin instantánea previa no hay cambios que comparar")
    if cambios["paginas_desaparecidas"]:
        advertencias.append("«desaparecida» significa no vista en la muestra actual; no prueba que dejó de anunciar")
    if any(r["muestra_truncada"] for r in activas.values()):
        advertencias.append("hay páginas con muestra truncada: sus conteos son un PISO, no el total")
    if temas_estado in ("sin_etiquetas", "base_sin_etiquetas"):
        advertencias.append(f"temas_nuevos no se calcula ({temas_estado})")

    return {
        "schema_version": SCHEMA_VERSION,
        "corrida_id": a.actual["corrida_id"],
        "ahora": comun.iso_z(a.ahora),
        "estado": a.base["estado"],
        "base_entrantes": a.descriptor_base_entrantes(),
        "base_cambios": a.descriptor_base_cambios(),
        **cambios,
        "temas_nuevos": temas_nuevos,
        "temas_estado": temas_estado,
        "entrantes_30d": globales,
        "entrantes_30d_por_pais": por_pais,
        "entrantes_30d_piso_por_pais": piso_por_pais,
        "advertencias": advertencias,
    }
