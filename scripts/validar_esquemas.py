"""Validador de contratos de datos y de reglas cruzadas entre artefactos.

Qué hace
--------
1. Carga todos los esquemas ``contratos/*.schema.json`` por ``$id`` con un registro de
   referencias (``jsonschema`` + ``referencing``) y comprueba que sean esquemas válidos.
2. Valida los ejemplos de ``contratos/ejemplos/``: los ``*.valido.*`` deben pasar y los
   ``*.invalido*.*`` deben fallar con el motivo declarado en su archivo hermano ``.motivo.txt``.
3. Valida las REGLAS CRUZADAS de una oferta completa (``ofertas/<id>/``): mismo
   ``oferta_id`` y ``familia_id``; hashes que coinciden con el contenido; rutas citadas que
   existen; nombres de Meta (backbone 5.2); parámetros de URL (5.3); presupuesto dentro de
   ``limites``; gate y nivel coherentes con ``autonomia`` y ``contratos/gates.json``;
   ``macro_nicho`` permitido; ``riesgo.nivel`` coherente con los ejes; economía recalculada.
4. Comprueba la regla de diseño FAIL-CLOSED de ``limites.yaml``: si una clave necesaria
   está en ``null`` (o falta el sello del dueño) ningún script gasta ni activa
   (:func:`evaluar_limites`).

CLI (códigos de salida de docs/convenciones-de-codigo.md, sección 8)::

    python -m scripts.validar_esquemas                       # esquemas + ejemplos + ofertas/_ejemplo
    python -m scripts.validar_esquemas esquemas
    python -m scripts.validar_esquemas ejemplos
    python -m scripts.validar_esquemas oferta ofertas/_ejemplo [--limites ruta.yaml]
    python -m scripts.validar_esquemas limites empresa/limites.yaml --operacion gastar
    python -m scripts.validar_esquemas parametros empresa/parametros.yaml --operacion runner_vivo   # ParametroFaltante => 5

Ola 0b-1 (esquemas 1.1.0): firmas (``tipo_firma``, ``problemas_firma``, ``payload_firma``; Ed25519 obligatoria en producción, su
verificación criptográfica es de ``engine.guard``), coherencia de los artefactos nuevos (``problemas_artefacto``, ``problemas_ledger``),
``coherencia_parametros`` / ``parametros_faltantes`` para los grupos opcionales, ``regla_brief``, ``regla_mercado``,
``regla_artefactos_nuevos`` y el candado alternativo del ``spend_cap``. Las firmas públicas anteriores no cambian.
CT-3 B1: ``regla_catalogo`` (X48: catálogo firmado frente a ``checkout.json`` e ``ids_meta.json``; clave ``CATALOGO_HMAC``) y ``problemas_alertas`` (X49).

Salida: 0 correcto · 2 uso incorrecto · 3 validación (esquema o regla cruzada) ·
5 dato de límites faltante (fail-closed). Sin red, sin efectos externos.
"""
from __future__ import annotations

import argparse
import copy
import datetime as _dt
import hashlib
import hmac
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import parse_qsl, urlsplit

import yaml
from jsonschema import Draft202012Validator, validators as _jv
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

# Raíz del CÓDIGO: la carpeta que contiene este archivo. Los ESQUEMAS (``contratos/``) y los ejemplos son código: se resuelven SIEMPRE
# desde aquí y nunca desde ``FABRICA_RAIZ`` (con una raíz de datos sin ``contratos/`` el validador y ``engine.guard`` fallan cerrados
# con 4/5 en lugar de ``KeyError: esquema desconocido``).
RAIZ_CODIGO = Path(__file__).resolve().parents[1]
DIR_CONTRATOS = RAIZ_CODIGO / "contratos"
DIR_EJEMPLOS = DIR_CONTRATOS / "ejemplos"


def raiz_datos() -> Path:
    """Raíz de los DATOS (``empresa/``, ``ofertas/``): ``FABRICA_RAIZ`` leída en CADA llamada (no solo al importar) o la raíz del código."""
    return Path(os.path.abspath(os.environ.get("FABRICA_RAIZ") or RAIZ_CODIGO))   # absoluta (una raíz relativa no se antepone dos veces)


def es_ejemplo_del_repositorio(dir_oferta: Path | str) -> bool:
    """``True`` solo para ``<raíz de datos>/ofertas/_ejemplo`` (límites ficticios y clave de prueba pública), no para cualquier carpeta con ese nombre."""
    return Path(dir_oferta).resolve() == (raiz_datos() / "ofertas" / "_ejemplo").resolve()


def __getattr__(nombre: str) -> Any:
    """``RAIZ`` (nombre público histórico) = ``raiz_datos()`` evaluada al acceder; ``from scripts.validar_esquemas import RAIZ`` sigue valiendo."""
    if nombre == "RAIZ":
        return raiz_datos()
    raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")

# Códigos de salida (convenciones, sección 8).
SALIDA_OK, SALIDA_USO, SALIDA_VALIDACION, SALIDA_LIMITE = 0, 2, 3, 5

# Etapas con carpeta propia dentro de ofertas/<id>/ y archivos que sellan su salida.
CARPETA_ETAPA = {
    "M1": ".", "D1": "01-descubrimiento", "D2": "02-validacion", "D3": "03-oferta", "D4": "04-producto",
    "D5": "05-landing", "D6": "06-creativos", "D7": "07-campana", "D8": "08-operacion",
    "D9": "09-escalado", "D10": "10-postcompra",
}
ARCHIVOS_SELLADOS = {
    "M1": ["mercado.json"],
    "D1": ["01-descubrimiento/candidatos.json"],
    "D2": ["02-validacion/validacion.json"],
    "D3": ["03-oferta/oferta.json", "03-oferta/economia.json"],
    "D4": ["04-producto/producto.json"],
    "D5": ["05-landing/assets.json", "05-landing/checkout.json", "05-landing/tracking.json", "05-landing/rutas.json"],
    "D6": ["06-creativos/paquete.json"],
    "D7": ["07-campana/campana.json"],
}
# Carpetas que además sellan la salida de una etapa (se hashean con ``hash_directorio``): la aprobación de D5 cubre el sitio servido.
# Lista aparte de ``ARCHIVOS_SELLADOS`` para que quien recorre esos archivos (p. ej. compliance.lint_claims) no tropiece con carpetas.
DIRECTORIOS_SELLADOS = {
    "D5": ["05-landing/sitio"],
}
# Dependencias de aprobación (entradas de cada etapa; backbone 3). M1 se apoya en D1 y D2 en D1+M1.
DEPENDENCIAS = {
    "D1": [], "M1": ["D1"], "D2": ["D1", "M1"], "D3": ["D2"], "D4": ["D3"], "D5": ["D3", "D4"],
    "D6": ["D3", "D5"], "D7": ["D5", "D6"], "D8": ["D7"], "D9": ["D8"], "D10": ["D4", "D5"],
}
# Esquema que corresponde a cada archivo de una oferta (ruta relativa -> nombre de esquema).
ESQUEMA_DE_ARCHIVO = {
    "00-brief.yaml": "brief", "estado.json": "estado", "mercado.json": "mercado",
    "01-descubrimiento/candidatos.json": "candidatos", "02-validacion/validacion.json": "validacion",
    "03-oferta/oferta.json": "oferta", "03-oferta/economia.json": "economia", "04-producto/producto.json": "producto",
    "05-landing/assets.json": "assets", "05-landing/checkout.json": "checkout", "05-landing/tracking.json": "tracking_plan",
    "06-creativos/paquete.json": "creativos", "07-campana/campana.json": "campana",
    "08-operacion/veredicto_oferta.json": "veredicto_oferta", "10-postcompra/senal_pausa.json": "senal_pausa",
    "07-campana/ids_meta.json": "ids_meta", "07-campana/preflight.json": "preflight", "07-campana/aprobacion.json": "aprobacion",
    "07-campana/traspaso.json": "traspaso", "08-operacion/postmortem.json": "postmortem",
    "05-landing/catalogo.json": "catalogo",   # CT-3 B-01: lo emite landing.catalogo tras D5; no es archivo sellado
}
# Artefactos que solo existen tras crear/activar/operar (no los lleva una oferta en borrador como ofertas/_ejemplo).
ARCHIVOS_POSTERIORES_AL_BORRADOR = frozenset({"07-campana/ids_meta.json", "07-campana/preflight.json", "07-campana/aprobacion.json",
                                              "07-campana/traspaso.json", "08-operacion/postmortem.json", "08-operacion/decisiones.jsonl",
                                              "05-landing/catalogo.json"})
ESQUEMA_DE_JSONL = {
    "08-operacion/ordenes_presupuesto.jsonl": "orden_presupuesto", "08-operacion/decisiones.jsonl": "decision", "10-postcompra/entregas.jsonl": "entrega",
    "10-postcompra/reembolsos.jsonl": "reembolso",
}
NIVELES = ["N0", "N1", "N2", "N3", "N4"]
MACRO_NICHOS = {"salud", "relaciones", "dinero"}
ORDEN_RIESGO = {"verde": 0, "amarillo": 1, "rojo": 2}
# Lint mínimo de claims (el lint completo es de X1: scripts/lint_claims.py). Solo atrapa lo obvio.
CLAIMS_PROHIBIDOS = [
    r"\bcura(r|s|rte|mos)?\b", r"\bsana(r|rte)\b", r"\badelgaz", r"\bbajar de peso\b", r"\bganar dinero\b",
    r"\bingresos? (garantizados?|pasivos?)\b", r"\bhazte rica?\b", r"\bresultados? garantizados?\b",
    r"\bgarantizamos (que )?(consegu|encontr)", r"\b\d+\s?(€|eur|euros|usd|\$)\s?(al|por|/)\s?(mes|dia|día|semana)\b",
    r"\bconseguir[áa]s (un )?(trabajo|empleo)\b", r"\bdiagnostic", r"\btratamiento\b",
]


# ----------------------------------------------------------------------------------------------
# Resultado de validación
# ----------------------------------------------------------------------------------------------
@dataclass
class Hallazgo:
    """Un problema detectado: ``nivel`` es ERROR o AVISO; ``codigo`` identifica la regla."""
    nivel: str
    codigo: str
    ruta: str
    mensaje: str
    salida: int = SALIDA_VALIDACION

    def __str__(self) -> str:
        return f"[{self.nivel}] {self.codigo} {self.ruta}: {self.mensaje}"


@dataclass
class Informe:
    """Acumula hallazgos y calcula el código de salida."""
    titulo: str
    hallazgos: list[Hallazgo] = field(default_factory=list)
    verificados: int = 0

    def error(self, codigo: str, ruta: str, mensaje: str, salida: int = SALIDA_VALIDACION) -> None:
        self.hallazgos.append(Hallazgo("ERROR", codigo, str(ruta), mensaje, salida))

    def aviso(self, codigo: str, ruta: str, mensaje: str) -> None:
        self.hallazgos.append(Hallazgo("AVISO", codigo, str(ruta), mensaje))

    def extender(self, otro: "Informe") -> None:
        self.hallazgos.extend(otro.hallazgos)
        self.verificados += otro.verificados

    @property
    def errores(self) -> list[Hallazgo]:
        return [h for h in self.hallazgos if h.nivel == "ERROR"]

    @property
    def codigo_salida(self) -> int:
        errs = self.errores
        if not errs:
            return SALIDA_OK
        if any(h.salida == SALIDA_LIMITE for h in errs) and all(h.salida == SALIDA_LIMITE for h in errs):
            return SALIDA_LIMITE
        return SALIDA_VALIDACION

    def texto(self) -> str:
        lineas = [f"== {self.titulo}"]
        lineas += [str(h) for h in self.hallazgos]
        estado = "OK" if not self.errores else f"{len(self.errores)} error(es)"
        lineas.append(f"-> {estado}; {self.verificados} verificación(es), {len(self.hallazgos) - len(self.errores)} aviso(s)")
        return "\n".join(lineas)


# ----------------------------------------------------------------------------------------------
# Carga de datos, JSON canónico y hashes (convenciones, sección 5)
# ----------------------------------------------------------------------------------------------
class _CargadorYaml(yaml.SafeLoader):
    """Cargador seguro que NO convierte fechas ni instantes a objetos ``datetime``."""


_CargadorYaml.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _mapa_sin_duplicados(cargador: yaml.SafeLoader, nodo: yaml.MappingNode, profundo: bool = False) -> dict:
    """Constructor YAML que rechaza claves repetidas (la última no gana en silencio; crítica m01)."""
    claves = set()
    for k_nodo, _ in nodo.value:
        k = cargador.construct_object(k_nodo, deep=True)
        if k in claves:
            raise ValueError(f"clave duplicada en YAML: {k!r}")
        claves.add(k)
    return yaml.SafeLoader.construct_mapping(cargador, nodo, deep=profundo)


_CargadorYaml.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapa_sin_duplicados)


def _pares_sin_duplicados(pares: list[tuple[str, Any]]) -> dict:
    """``object_pairs_hook`` de JSON: rechaza claves repetidas (un Worker JS leería lo mismo distinto)."""
    d: dict = {}
    for k, v in pares:
        if k in d:
            raise ValueError(f"clave duplicada en JSON: {k!r}")
        d[k] = v
    return d


def cargar_yaml(ruta: Path | str) -> Any:
    """Lee un YAML como datos puros (fechas como texto). Falla con ``yaml.YAMLError`` si es inválido."""
    with open(ruta, encoding="utf-8") as f:
        return yaml.load(f, Loader=_CargadorYaml)  # noqa: S506 - cargador seguro derivado de SafeLoader


def cargar_json(ruta: Path | str) -> Any:
    """Lee un JSON UTF-8."""
    with open(ruta, encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=_pares_sin_duplicados)


def cargar_datos(ruta: Path | str) -> Any:
    """Lee JSON o YAML según la extensión."""
    ruta = Path(ruta)
    return cargar_yaml(ruta) if ruta.suffix in (".yaml", ".yml") else cargar_json(ruta)


def cargar_jsonl(ruta: Path | str) -> list[Any]:
    """Lee un JSONL (una línea JSON por evento); ignora líneas vacías."""
    with open(ruta, encoding="utf-8") as f:
        return [json.loads(l, object_pairs_hook=_pares_sin_duplicados) for l in f if l.strip()]


def json_canonico(obj: Any) -> bytes:
    """JSON canónico: UTF-8, claves ordenadas, sin espacios, sin NaN (convenciones 5)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def normalizar_texto(texto: str) -> str:
    """Unicode NFC y saltos de línea ``\\n`` antes de hashear texto."""
    return unicodedata.normalize("NFC", texto.replace("\r\n", "\n").replace("\r", "\n"))


def hash_bytes(datos: bytes) -> str:
    """``sha256:<hex>`` de unos bytes."""
    return "sha256:" + hashlib.sha256(datos).hexdigest()


def hash_objeto(obj: Any, excluir: Iterable[str] = ()) -> str:
    """Hash del JSON canónico de ``obj`` sin las claves de primer nivel de ``excluir`` (sellos)."""
    if isinstance(obj, dict) and excluir:
        obj = {k: v for k, v in obj.items() if k not in set(excluir)}
    return hash_bytes(json_canonico(obj))


EXT_TEXTO = {".md", ".txt", ".html", ".css", ".js", ".mjs", ".jsonl", ".csv", ".svg"}


def _es_servido(ruta: Path) -> bool:
    """``True`` si la ruta cuelga de ``05-landing/sitio/`` (el par consecutivo, no cualquier carpeta llamada «sitio» del clon)."""
    p = ruta.parts
    return any(p[i] == "05-landing" and p[i + 1] == "sitio" for i in range(len(p) - 1))


def hash_archivo(ruta: Path | str, *, servido: bool | None = None) -> str:
    """Hash de contenido: JSON/YAML por su forma canónica, texto normalizado NFC, el resto por bytes.

    Lo SERVIDO (``.html/.js/.mjs/.css/.svg`` de ``05-landing/sitio/``) se hashea por bytes, sin normalizar (m01). ``servido`` lo fuerza
    (``hash_directorio`` lo pasa en ``True``); por defecto se deduce del par ``05-landing/sitio`` de la ruta, no de un ``sitio`` suelto.
    """
    ruta = Path(ruta)
    if (servido if servido is not None else _es_servido(ruta)) and ruta.suffix in (".html", ".js", ".mjs", ".css", ".svg"):
        return hash_bytes(ruta.read_bytes())
    if ruta.suffix == ".json":
        return hash_objeto(cargar_json(ruta))
    if ruta.suffix in (".yaml", ".yml"):
        return hash_objeto(cargar_yaml(ruta))
    if ruta.suffix in EXT_TEXTO:
        return hash_bytes(normalizar_texto(ruta.read_text(encoding="utf-8")).encode("utf-8"))
    return hash_bytes(ruta.read_bytes())


CAMPOS_BRIEF_ASIGNADOS = ("hash", "aprobado_por", "oferta_id", "familia_id", "creado_en")


def hash_contenido_brief(brief: dict) -> str:
    """Hash del CONTENIDO del brief, sin los campos que asigna el motor tras recibirlo.

    ``orq crear`` busca este hash para devolver el mismo ``oferta_id`` ante el mismo contenido
    (idempotencia; crítica MA-09). El ``hash`` completo del brief (el que firma el dueño) sigue
    excluyendo solo ``hash`` y ``aprobado_por``.
    """
    return hash_objeto(brief, excluir=CAMPOS_BRIEF_ASIGNADOS)


def hash_ruta(ruta: Path | str) -> str:
    """Hash de un archivo (``hash_archivo``) o de una carpeta (``hash_directorio``)."""
    ruta = Path(ruta)
    return hash_directorio(ruta) if ruta.is_dir() else hash_archivo(ruta)


def hash_directorio(carpeta: Path | str) -> str:
    """Hash de una carpeta: JSON canónico del mapa ``ruta relativa -> hash_archivo`` (orden estable).

    Los ``.html/.js/.mjs/.css/.svg`` de la carpeta se hashean por bytes (se sirven tal cual): el hash de ``sitio/`` es el mismo en el clon,
    en una copia de despliegue o en el historial de ``landing.desplegar``, viva donde viva.
    """
    carpeta = Path(carpeta)
    mapa = {str(p.relative_to(carpeta).as_posix()): hash_archivo(p, servido=True) for p in sorted(carpeta.rglob("*")) if p.is_file()}
    return hash_objeto(mapa)


def hash_salida_etapa(dir_oferta: Path, etapa: str) -> str | None:
    """Hash de salida de una etapa: sobre el mapa de sus archivos sellados; ``None`` si falta alguno."""
    mapa = {}
    for rel in ARCHIVOS_SELLADOS.get(etapa, []):
        p = dir_oferta / rel
        if not p.is_file():
            return None
        mapa[rel] = hash_archivo(p)
    for rel in DIRECTORIOS_SELLADOS.get(etapa, []):
        p = dir_oferta / rel
        if not p.is_dir():
            return None
        mapa[rel] = hash_directorio(p)
    return hash_objeto(mapa) if mapa else None


def clave_idempotencia(operacion: str, oferta_id: str, parametros: Any) -> str:
    """Clave de idempotencia determinista (convenciones 7)."""
    return hash_objeto({"operacion": operacion, "oferta_id": oferta_id, "parametros": parametros})


def firma_hmac(contenido: Any, clave: bytes) -> str:
    """Firma ``hmac-sha256:<hex>`` del JSON canónico del contenido (clave fuera del alcance de los agentes)."""
    return "hmac-sha256:" + hmac.new(clave, json_canonico(contenido), hashlib.sha256).hexdigest()


def comparar_hash(a: str, b: str) -> bool:
    """Comparación de hashes en tiempo constante."""
    return hmac.compare_digest(a.encode(), b.encode())


def buscar_floats(obj: Any, ruta: str = "") -> list[str]:
    """Rutas de valores ``float`` dentro de ``obj`` (prohibidos para dinero y tasas)."""
    if isinstance(obj, float):
        return [ruta or "/"]
    if isinstance(obj, dict):
        return [r for k, v in obj.items() for r in buscar_floats(v, f"{ruta}/{k}")]
    if isinstance(obj, list):
        return [r for i, v in enumerate(obj) for r in buscar_floats(v, f"{ruta}/{i}")]
    return []


def dec(valor: Any) -> "Decimal":
    """Convierte entero o cadena decimal a ``Decimal`` (nunca float)."""
    from decimal import Decimal
    if isinstance(valor, float):
        raise ValueError("float prohibido")
    return Decimal(str(valor))


def entero_redondeado(numerador: int, denominador: int, modo: str = "half_even") -> int:
    """Redondeo explícito de ``numerador/denominador`` (enteros, denominador > 0)."""
    from decimal import ROUND_CEILING, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
    m = {"half_even": ROUND_HALF_EVEN, "half_up": ROUND_HALF_UP, "techo": ROUND_CEILING}[modo]
    return int((Decimal(numerador) / Decimal(denominador)).quantize(Decimal(1), rounding=m))


# ----------------------------------------------------------------------------------------------
# Esquemas
# ----------------------------------------------------------------------------------------------
def _patron_ecma(patron: str) -> "re.Pattern[str]":
    """Compila un ``pattern`` de JSON Schema (ECMA-262) para ``re``: ``$`` fuera de una clase se vuelve ``\\Z``.

    En Python ``$`` casa también antes de un ``\\n`` final y en ECMAScript no (CT1-01). Se conserva la semántica de ``search``
    (los patrones sin ancla, como los de ``if`` de ``schema_version``, siguen siendo parciales); un ``fullmatch`` los rompería.
    """
    salida, en_clase, i = [], False, 0
    while i < len(patron):
        ch = patron[i]
        if ch == "\\" and i + 1 < len(patron):
            salida.append(patron[i:i + 2])
            i += 2
            continue
        if en_clase:
            en_clase = ch != "]"
        elif ch == "[":
            en_clase = True
        elif ch == "$":
            ch = "\\Z"
        salida.append(ch)
        i += 1
    return re.compile("".join(salida))


_PATRONES: dict[str, "re.Pattern[str]"] = {}


def _patron_completo(validador: Any, patron: str, instancia: Any, esquema: Any):  # noqa: ANN202
    """``pattern`` con ``$`` estricto (CT1-01): `"123\\n"` no cumple `^[0-9]+$`."""
    if validador.is_type(instancia, "string"):
        if patron not in _PATRONES:
            _PATRONES[patron] = _patron_ecma(patron)
        if not _PATRONES[patron].search(instancia):
            yield ValidationError(f"{instancia!r} does not match {patron!r}")


Validador = _jv.extend(Draft202012Validator, {"pattern": _patron_completo})


def cargar_esquemas(dir_contratos: Path | None = None) -> tuple[Registry, dict[str, dict]]:
    """Carga ``*.schema.json`` y arma el registro de referencias por ``$id``.

    Devuelve ``(registro, esquemas)`` con ``esquemas`` indexado por nombre corto (``oferta``).
    Lanza ``ValueError`` si hay ``$id`` duplicados y ``jsonschema.SchemaError`` si un esquema es inválido.
    """
    dir_contratos = dir_contratos or DIR_CONTRATOS
    registro = Registry()
    esquemas: dict[str, dict] = {}
    ids: set[str] = set()
    for p in sorted(dir_contratos.glob("*.schema.json")):
        doc = cargar_json(p)
        Draft202012Validator.check_schema(doc)
        if doc["$id"] in ids:
            raise ValueError(f"$id duplicado: {doc['$id']}")
        ids.add(doc["$id"])
        esquemas[p.name[: -len(".schema.json")]] = doc
        registro = registro.with_resource(doc["$id"], Resource.from_contents(doc, default_specification=DRAFT202012))
    return registro, esquemas


_CACHE: dict[str, tuple[Registry, dict]] = {}


def _esquemas() -> tuple[Registry, dict]:
    clave = str(DIR_CONTRATOS)
    if clave not in _CACHE:
        _CACHE[clave] = cargar_esquemas()
    return _CACHE[clave]


def errores_de_esquema(nombre: str, instancia: Any) -> list[Any]:
    """Errores de ``jsonschema`` al validar ``instancia`` contra el esquema ``nombre``."""
    registro, esquemas = _esquemas()
    if nombre not in esquemas:
        raise KeyError(f"esquema desconocido: {nombre}")
    v = Validador(esquemas[nombre], registry=registro)
    return sorted(v.iter_errors(instancia), key=lambda e: list(map(str, e.absolute_path)))


def ruta_json(error: Any) -> str:
    """Puntero JSON (``/a/0/b``) de un error de ``jsonschema``."""
    return "".join(f"/{p}" for p in error.absolute_path)


def validar_contra_esquema(nombre: str, instancia: Any, origen: str, informe: Informe) -> bool:
    """Valida ``instancia`` y agrega errores al informe; además prohíbe ``float``. Devuelve si pasó."""
    informe.verificados += 1
    ok = True
    for e in errores_de_esquema(nombre, instancia):
        ok = False
        informe.error("ESQUEMA", f"{origen}{ruta_json(e)}", f"{e.validator}: {e.message[:240]}")
    for r in buscar_floats(instancia):
        ok = False
        informe.error("FLOAT", f"{origen}{r}", "float prohibido: usar enteros (unidad menor) o cadenas decimales")
    return ok


# ----------------------------------------------------------------------------------------------
# Ejemplos válidos e inválidos
# ----------------------------------------------------------------------------------------------
def leer_motivo(ruta: Path) -> dict[str, str]:
    """Lee ``<ejemplo>.motivo.txt``: líneas ``clave=valor`` (``validador``, ``ruta``, ``contiene``, ``texto``)."""
    datos: dict[str, str] = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if "=" in linea and not linea.lstrip().startswith("#"):
            k, v = linea.split("=", 1)
            datos[k.strip()] = v.strip()
    return datos


def coincide_motivo(errores: list[Any], motivo: dict[str, str]) -> bool:
    """¿Algún error coincide con el motivo esperado (validador, ruta exacta y fragmento del mensaje)?"""
    for e in errores:
        if "validador" in motivo and e.validator != motivo["validador"]:
            continue
        if "ruta" in motivo and ruta_json(e) != motivo["ruta"]:
            continue
        if "contiene" in motivo and motivo["contiene"] not in e.message:
            continue
        return True
    return False


def reglas_de_artefacto(nombre: str, datos: Any, informe: Informe, origen: str) -> None:
    """Reglas propias de artefactos de empresa (P&L, semáforo de infra, KPI) aplicadas a ejemplos válidos."""
    if nombre == "pnl":
        for ruta, b in [("consolidado", datos["consolidado"])] + [(f"por_oferta/{k}", x["bloque"]) for k, x in enumerate(datos["por_oferta"])]:
            esperado = pnl_resultado(b["lineas"], datos["moneda_base"])
            if b["resultado_operativo"] != esperado:
                informe.error("PNL_FORMULA", f"{origen}/{ruta}", f"resultado_operativo {b['resultado_operativo']} != {esperado}")
        suma = sum(x["bloque"]["lineas"]["gasto_meta"]["monto"] for x in datos["por_oferta"])
        if suma > datos["consolidado"]["lineas"]["gasto_meta"]["monto"]:
            informe.error("PNL_FORMULA", origen, "el gasto de Meta por oferta supera el consolidado")
    if nombre == "infra_estado" and not semaforo_coherente(datos):
        informe.error("INFRA_SEMAFORO", origen, "el semáforo no es el peor de sus ítems")
    if nombre in ("aprobacion", "preflight", "sello", "orden_firmada", "decision", "conciliacion", "tipo_cambio", "traspaso", "postmortem", "catalogo", "alertas"):
        for cod, msg in problemas_artefacto(nombre, datos, clave=CLAVE_DE_PRUEBA, entorno="prueba"):
            informe.error(cod, origen, msg)
    if nombre == "ledger":
        for cod, msg in problemas_ledger([datos]):
            informe.error(cod, origen, msg)


def pnl_resultado(lineas: dict, moneda: str) -> dict:
    """resultado_operativo = ingresos - impuestos - reembolsos - comisiones - tarifas_disputa - disputas_perdidas - gasto_meta - costo_ia - otros_costos."""
    g = lambda k: lineas[k]["monto"]
    res = g("ingresos_brutos") - sum(g(k) for k in ("impuestos", "reembolsos", "comisiones", "tarifas_disputa", "disputas_perdidas", "gasto_meta", "costo_ia", "otros_costos"))
    return {"monto": res, "moneda": moneda}


def validar_ejemplos(dir_ejemplos: Path | None = None) -> Informe:
    """Los ``*.valido.*`` deben pasar; los ``*.invalido*.*`` deben fallar con el motivo de su ``.motivo.txt``."""
    dir_ejemplos = dir_ejemplos or DIR_EJEMPLOS
    inf = Informe("Ejemplos de contratos")
    _, esquemas = _esquemas()
    vistos: dict[str, dict[str, int]] = {n: {"valido": 0, "invalido": 0} for n in esquemas if n not in ("comunes",)}
    for p in sorted(dir_ejemplos.iterdir()):
        if p.suffix not in (".json", ".yaml") or ".motivo" in p.name:
            continue
        m = re.match(r"^(?P<nombre>[a-z_]+)\.(?P<tipo>valido|invalido)(?:-[a-z0-9_-]+)?\.(json|yaml)$", p.name)
        if not m:
            inf.error("EJEMPLO_NOMBRE", p.name, "nombre esperado: <esquema>.valido.json | <esquema>.invalido-<motivo>.json")
            continue
        nombre, tipo = m["nombre"], m["tipo"]
        if nombre not in esquemas:
            inf.error("EJEMPLO_ESQUEMA", p.name, f"no existe el esquema {nombre}")
            continue
        datos = cargar_datos(p)
        errs = errores_de_esquema(nombre, datos)
        errs_f = buscar_floats(datos)
        inf.verificados += 1
        if tipo == "valido":
            vistos[nombre]["valido"] += 1
            for e in errs:
                inf.error("EJEMPLO_VALIDO_FALLA", f"{p.name}{ruta_json(e)}", f"{e.validator}: {e.message[:200]}")
            for r in errs_f:
                inf.error("FLOAT", f"{p.name}{r}", "float en ejemplo válido")
            if not errs:
                reglas_de_artefacto(nombre, datos, inf, p.name)
        else:
            vistos[nombre]["invalido"] += 1
            mot = p.parent / (p.stem + ".motivo.txt")
            if not mot.exists():
                inf.error("EJEMPLO_SIN_MOTIVO", p.name, f"falta {mot.name}")
            elif not errs and not errs_f:
                inf.error("EJEMPLO_INVALIDO_PASA", p.name, "el ejemplo inválido pasó la validación")
            elif not coincide_motivo(errs, leer_motivo(mot)) and not (errs_f and leer_motivo(mot).get("validador") == "float"):
                inf.error("EJEMPLO_MOTIVO", p.name, f"falló, pero no con el motivo esperado {leer_motivo(mot)}; errores: "
                          + "; ".join(f"{e.validator}@{ruta_json(e)}" for e in errs[:4]))
    for nombre, c in vistos.items():
        if c["valido"] == 0 or c["invalido"] == 0:
            inf.error("EJEMPLO_FALTA", nombre, f"faltan ejemplos (válidos={c['valido']}, inválidos={c['invalido']})")
    return inf


# ----------------------------------------------------------------------------------------------
# Límites: fail-closed
# ----------------------------------------------------------------------------------------------
CLAVES_CRITICAS: dict[str, list[str]] = {
    "gastar": ["moneda_limites", "capital_en_riesgo_total", "gasto_diario_global", "gasto_diario_por_oferta", "gasto_total_test_por_oferta",
               "perdida_max_test_por_oferta", "perdida_neta_acumulada_max", "ofertas_en_test_simultaneas_max",
               "limite_gasto_cuenta_meta", "cuentas_permitidas", "paises_permitidos", "locales_permitidos"],
    "aumentar_presupuesto": ["gasto_diario_global", "gasto_diario_por_oferta", "aumento_presupuesto_max_pct_por_paso",
                             "horas_min_entre_aumentos", "limite_gasto_cuenta_meta"],
    "escalar": ["gasto_diario_global", "gasto_diario_por_oferta", "aumento_presupuesto_max_pct_por_paso",
                "horas_min_entre_aumentos", "stop_loss_escala", "dias_cobertura_caja", "perdida_neta_acumulada_max",
                "limite_gasto_cuenta_meta"],
    "reembolsar_auto": ["reembolso_auto_max", "reembolsos_auto_max_por_dia"],
    "descubrir": ["fuentes_permitidas", "max_busquedas_por_barrido", "max_barridos_por_semana", "max_costo_por_barrido",
                  "max_consultas_biblioteca"],  # CT-3 A-06 (LT-15); max_capturas_web_por_dia entra con CT-4
    "generar_creativos": ["creditos_max_pieza", "creditos_max_oferta", "max_budget_por_corrida_agente"],
    "enviar_correo": ["correos_max_por_dia", "correos_max_por_semana"],
}
CLAVES_CRITICAS["activar"] = CLAVES_CRITICAS["gastar"] + ["precio_neto_minimo", "politica_divulgacion_ia",
                                                           "ratio_disputas_pausa", "politica_reembolso_dias"]


@dataclass
class ResultadoLimites:
    """Resultado de :func:`evaluar_limites`: ``ok`` solo si se puede operar; ``faltantes`` explica por qué no."""
    ok: bool
    faltantes: list[str]
    motivo: str = ""

    def __bool__(self) -> bool:
        return self.ok


def sello_de_limites(limites: dict) -> str:
    """Hash que debe llevar ``sello.hash``: JSON canónico del contenido sin el campo ``sello``."""
    return hash_objeto(limites, excluir=("sello",))


# Importes de limites.yaml (enteros >= 0 en la unidad menor de ``moneda_limites``).
TOPES_IMPORTE = ("capital_en_riesgo_total", "gasto_diario_global", "gasto_diario_por_oferta", "gasto_total_test_por_oferta",
                 "perdida_max_test_por_oferta", "perdida_neta_acumulada_max", "limite_gasto_cuenta_meta", "stop_loss_escala",
                 "precio_neto_minimo", "reembolso_auto_max", "autoaprobar_hasta")
# Gates H que el archivo no puede quitar (el esquema solo restringe el enum; B02).
ACCIONES_GATE_MINIMAS = {"activar_campana", "reactivar_tras_pausa", "subir_presupuesto_sobre_tope", "cambiar_limites",
                         "cambiar_entidad_stripe", "lanzamiento_pais_idioma_nuevo"}
FACTOR_META_MIN = "1.75"  # hecho de plataforma (investigación 04, HC-26; [VERIFICAR] en la fuente oficial de Meta)
# Monedas con offset 1 en la API de Meta (https://developers.facebook.com/docs/marketing-api/currencies, leída 2026-11-06).
# Hasta que exista ``meta/monedas.py`` probado, ``moneda_limites`` no puede ser una de ellas (M06).
MONEDAS_META_OFFSET_1 = frozenset({"CLP", "COP", "CRC", "HUF", "ISK", "IDR", "JPY", "KRW", "PYG", "TWD", "VND"})


def coherencia_limites(l: dict) -> list[str]:
    """Incoherencias entre valores YA presentes de un limites.yaml (lista vacía = coherente).

    Los ``null`` se ignoran aquí (los cubre el fail-closed de :func:`evaluar_limites`); lo que existe
    debe ser entero >= 0 (no ``bool``/``str``) y respetar el orden entre topes (crítica B02).
    """
    err: list[str] = []
    v: dict[str, int | None] = {}
    for k in TOPES_IMPORTE:
        x = l.get(k)
        if x is None:
            v[k] = None
        elif isinstance(x, bool) or not isinstance(x, int) or x < 0:
            err.append(f"{k}: debe ser entero >= 0 (es {x!r})")
            v[k] = None
        else:
            v[k] = x
    m = l.get("moneda_limites")
    if m is not None:
        if not (isinstance(m, str) and len(m) == 3 and m.isupper()):
            err.append("moneda_limites: debe ser ISO 4217 en mayúsculas")
        elif m in MONEDAS_META_OFFSET_1:
            err.append(f"moneda_limites {m}: offset 1 en Meta; no admitida hasta que meta/monedas.py esté probado (M06)")
    f = l.get("factor_techo_teorico_diario")
    if f is not None:
        try:
            if dec(f) < dec(FACTOR_META_MIN):
                err.append(f"factor_techo_teorico_diario < {FACTOR_META_MIN}: subestima el gasto máximo de Meta")
        except (ValueError, ArithmeticError):
            err.append("factor_techo_teorico_diario ilegible")

    def le(a: str, b: str) -> None:
        if v.get(a) is not None and v.get(b) is not None and v[a] > v[b]:  # type: ignore[operator]
            err.append(f"{a} > {b}")

    le("gasto_diario_por_oferta", "gasto_diario_global")
    le("perdida_max_test_por_oferta", "gasto_total_test_por_oferta")
    le("gasto_total_test_por_oferta", "limite_gasto_cuenta_meta")
    le("limite_gasto_cuenta_meta", "capital_en_riesgo_total")
    le("perdida_neta_acumulada_max", "capital_en_riesgo_total")
    n = l.get("ofertas_en_test_simultaneas_max")
    if n is not None and (isinstance(n, bool) or not isinstance(n, int) or n < 1):
        err.append(f"ofertas_en_test_simultaneas_max: debe ser entero >= 1 (es {n!r})")
    elif isinstance(n, int) and v["gasto_diario_por_oferta"] and v["gasto_diario_global"]:
        if n * v["gasto_diario_por_oferta"] > v["gasto_diario_global"]:  # type: ignore[operator]
            err.append("ofertas_en_test_simultaneas_max x gasto_diario_por_oferta > gasto_diario_global")
    gate = l.get("acciones_gate_humano")
    if gate is not None and not ACCIONES_GATE_MINIMAS <= set(gate):
        err.append("acciones_gate_humano no contiene el mínimo obligatorio")
    # CT-3 A-04: la cuota de amarillo-b es parte de la de amarillo (nota 25 §10.1: 30 / 10). null = sin cuota (solo verde): se ignora.
    ca, cb = l.get("cuota_gasto_amarillo_max_pct"), l.get("cuota_gasto_amarillo_b_max_pct")
    for k, x in (("cuota_gasto_amarillo_max_pct", ca), ("cuota_gasto_amarillo_b_max_pct", cb)):
        if x is not None and (isinstance(x, bool) or not isinstance(x, int) or not 0 <= x <= 100):
            err.append(f"{k}: debe ser entero 0-100 (es {x!r})")
    if all(isinstance(x, int) and not isinstance(x, bool) for x in (ca, cb)) and cb > ca:
        err.append("cuota_gasto_amarillo_b_max_pct > cuota_gasto_amarillo_max_pct: amarillo-b es parte de amarillo")
    return err


NIVEL_PARA_ACTIVAR_SIN_H = "N3"  # desde N3 contratos/gates.json pone S (no H) en activar_campana y lanzamiento_pais_idioma_nuevo
ETAPA_DE_GATE_ACTIVAR = {"activar_campana": "D7", "lanzamiento_pais_idioma_nuevo": "M1"}


def coherencia_gate_activar(limites: dict | None, autonomia: dict | None) -> list[str]:
    """AVISOS (nunca errores) ``GATE_ACTIVAR_H``: el gate H de ``activar_campana``/``lanzamiento_pais_idioma_nuevo`` no se levanta con el nivel (CT-3 A-05, C-04).

    ``gates.json`` pone S en N3/N4 para esas dos acciones, pero ``limites.acciones_gate_humano`` las trae siempre (mínimo del esquema, del validador y de
    ``engine.guard``: no se pueden quitar, ni con firma). Gate efectivo = el más estricto de las cuatro fuentes. Si alguna etapa vinculada (D7 para
    activar, M1 para el primer lanzamiento en país/idioma nuevo) está en >= N3 en ``autonomia``, el botón NO activará solo: lista un mensaje por acción.
    Quitar ese H es la decisión estructural D-02 del dueño.
    """
    if not isinstance(autonomia, dict):
        return []
    lista = set((limites or {}).get("acciones_gate_humano") or []) | ACCIONES_GATE_MINIMAS  # las mínimas rigen aunque el archivo no las traiga
    por_etapa = autonomia.get("nivel_por_etapa") or {}
    msgs = []
    for accion, etapa in ETAPA_DE_GATE_ACTIVAR.items():
        nivel = (por_etapa.get(etapa) or {}).get("nivel")
        if accion in lista and nivel in NIVELES and NIVELES.index(nivel) >= NIVELES.index(NIVEL_PARA_ACTIVAR_SIN_H):
            msgs.append(f"{etapa} en {nivel}: accion:{accion} sigue en gate H (mínimo de limites.acciones_gate_humano; no se quita ni con firma) aunque gates.json dice S; "
                        "el botón no activará solo (decisión D-02 del dueño)")
    return msgs


def coherencia_limites_parametros(limites: dict, parametros: dict | None) -> list[str]:
    """``ratio_disputas_pausa`` (fracción, pausa dura) no puede ser menor que la alerta ``salud_operativa.disputas_alerta_pct`` / 100 (CT1-25)."""
    r = limites.get("ratio_disputas_pausa")
    alerta = _param_valor(parametros, "salud_operativa", "disputas_alerta_pct")
    if r is None or alerta is None:
        return []
    try:
        if dec(r) < dec(alerta) / 100:
            return [f"ratio_disputas_pausa {r} < salud_operativa.disputas_alerta_pct/100 ({dec(alerta) / 100}): la pausa dura saltaría antes que la alerta"]
    except (ValueError, ArithmeticError):
        return ["ratio_disputas_pausa o disputas_alerta_pct ilegible"]
    return []


def evaluar_limites(limites: dict | None, operacion: str = "gastar", *, entorno: str | None = None,
                    ancla_hash: str | None = None, verificador: Callable[[bytes, str], bool] | None = None) -> ResultadoLimites:
    """Regla FAIL-CLOSED: ¿se puede ejecutar ``operacion`` con estos límites?

    Entradas: ``limites`` ya cargado (``None`` o no-dict = no cargado) y la operación (clave de
    ``CLAVES_CRITICAS``). Devuelve ``ResultadoLimites``. NO lanza: la persona que llama traduce un
    resultado falso al código de salida 5 (``ErrorLimite``). Una clave crítica en ``null``, una lista
    exigida vacía, ``macro_nichos_permitidos`` distinto del marco fijo, un sello ausente o que no
    coincide con el contenido, o valores incoherentes entre sí (:func:`coherencia_limites`), bloquean TODO.

    ``entorno`` (por defecto ``FABRICA_ENTORNO``): con ``produccion`` se exige además ``sello.firma``
    Ed25519 de formato SSHSIG (un HMAC o una cadena con otra forma bloquea: CT1-05). La firma criptográfica la
    verifica ``engine.limites.verificar_firma_sello`` con la clave PÚBLICA; si se pasa ``verificador(bytes, firma)``
    (hook, sin importar ``engine``) se aplica aquí a los bytes UTF-8 de ``sello.hash``. Un hash sin clave lo recalcula
    quien escribe el archivo (B01). ``ancla_hash`` es el
    hash vigente guardado FUERA del volumen (variable ``LIMITES_HASH_ANCLA``): si se pasa y difiere, bloquea.
    """
    if not isinstance(limites, dict):
        return ResultadoLimites(False, ["<archivo>"], "limites.yaml no cargado")
    if operacion not in CLAVES_CRITICAS:
        return ResultadoLimites(False, [operacion], f"operación desconocida: {operacion}")
    faltantes = []
    for k in CLAVES_CRITICAS[operacion]:
        v = limites.get(k)
        if v is None or (isinstance(v, (list, dict)) and not v):
            faltantes.append(k)
    if set(limites.get("macro_nichos_permitidos") or []) != MACRO_NICHOS:
        faltantes.append("macro_nichos_permitidos")
    sello = limites.get("sello")
    if not isinstance(sello, dict) or "hash" not in sello:
        faltantes.append("sello")
    else:
        calculado = sello_de_limites(limites)
        if not comparar_hash(sello["hash"], calculado):
            faltantes.append("sello(no coincide con el contenido)")
        if ancla_hash is not None and not comparar_hash(ancla_hash, calculado):
            faltantes.append("sello(no coincide con LIMITES_HASH_ANCLA)")
        entorno = entorno if entorno is not None else os.environ.get("FABRICA_ENTORNO", "")
        if entorno == "produccion":
            if tipo_firma(sello.get("firma")) != "ed25519":
                faltantes.append("sello.firma(Ed25519 SSHSIG obligatoria en producción: ausente, mal formada o HMAC)")
            elif verificador is not None and not _verifica(verificador, str(sello["hash"]).encode("utf-8"), sello["firma"]):
                faltantes.append("sello.firma(no verifica con la clave pública)")
    if faltantes:
        return ResultadoLimites(False, faltantes, "faltan datos de límites del dueño: " + ", ".join(faltantes))
    inc = coherencia_limites(limites)
    if inc:
        return ResultadoLimites(False, ["coherencia"], "límites incoherentes: " + "; ".join(inc))
    return ResultadoLimites(True, [])


def validar_limites_archivo(ruta: Path, operacion: str = "gastar") -> Informe:
    """Valida ``limites.yaml`` contra su esquema y aplica la regla fail-closed (salida 5 si no se puede operar)."""
    inf = Informe(f"Límites {ruta} (operación: {operacion})")
    if not Path(ruta).is_file():   # fail-closed: sin límites no se gasta ni se activa (salida 5, nunca un traceback)
        inf.error("LIMITES_AUSENTE", str(ruta), "falta limites.yaml: sin límites no se gasta ni se activa", SALIDA_LIMITE)
        return inf
    datos = cargar_yaml(ruta)
    validar_contra_esquema("limites", datos, str(ruta), inf)
    res = evaluar_limites(datos, operacion)
    inf.verificados += 1
    if not res:
        inf.error("LIMITES_FALTAN", str(ruta), res.motivo, SALIDA_LIMITE)
    return inf


# ----------------------------------------------------------------------------------------------
# Autonomía, gates, estados
# ----------------------------------------------------------------------------------------------
TRANSICIONES = {
    ("pendiente", "en_progreso"), ("en_progreso", "en_QA"), ("en_progreso", "bloqueado"), ("en_QA", "aprobado"),
    ("en_QA", "en_progreso"), ("en_QA", "escalado"), ("bloqueado", "en_progreso"), ("escalado", "en_progreso"),
    ("escalado", "aprobado"), ("aprobado", "pendiente"),
}


# Ciclo de vida de la oferta (campo ``fase`` de estado.json). ``pausada`` solo se reanuda con gate H.
# ``fallida -> en_construccion`` (reabrir con evidencia nueva) exige gate H firmado y origen_version=humano (M14);
# ``retirada`` es la única fase final.
FASES_TRANSICIONES = {
    ("borrador", "en_construccion"), ("en_construccion", "listo_para_activar"), ("listo_para_activar", "en_test"),
    ("en_test", "validada"), ("en_test", "fallida"), ("en_test", "inconclusa"), ("inconclusa", "en_test"),
    ("validada", "escalando"), ("en_test", "pausada"), ("escalando", "pausada"), ("pausada", "en_test"), ("pausada", "escalando"),
    ("listo_para_activar", "en_construccion"), ("fallida", "retirada"), ("fallida", "en_construccion"), ("inconclusa", "retirada"), ("validada", "retirada"),
    ("escalando", "retirada"), ("pausada", "retirada"), ("en_construccion", "retirada"), ("listo_para_activar", "retirada"),
}


def transicion_fase_valida(de: str, a: str) -> bool:
    """¿Es válido el paso de fase de la oferta? (reactivar desde ``pausada`` exige además gate H)."""
    return (de, a) in FASES_TRANSICIONES


def transicion_valida(de: str, a: str) -> bool:
    """¿Es válida la transición de estado de etapa? (O0 sección 4; solo la hace el motor)."""
    return (de, a) in TRANSICIONES


def cargar_gates() -> dict:
    """Carga la tabla única ``contratos/gates.json``."""
    return cargar_json(DIR_CONTRATOS / "gates.json")


def gate_esperado(clave: str, nivel: str, gates: dict | None = None) -> str:
    """Gate de la tabla única para ``etapa:D3`` o ``accion:activar_campana`` en un nivel (A, S, H o NA)."""
    gates = gates or cargar_gates()
    return gates["entradas"][clave]["gate"][nivel]


def nivel_efectivo(etapa: str, estado: dict, autonomia: dict | None) -> str:
    """Nivel con el que opera una etapa de una oferta: el MENOR entre el de la oferta, la etapa y autonomia.yaml."""
    cands = [estado["nivel"], estado["etapas"][etapa].get("nivel", estado["nivel"])]
    if autonomia and etapa in autonomia.get("nivel_por_etapa", {}):
        cands.append(autonomia["nivel_por_etapa"][etapa]["nivel"])
    return min(cands, key=NIVELES.index)


def infra_verde(estado: dict, ahora: Callable[[], _dt.datetime], max_horas: int, *, exigir_modo: str | None = "vivo",
                tolerancia_futuro_s: int = 120) -> tuple[bool, str]:
    """¿Puede gastar/activar según ``empresa/infra/estado.json``?

    Exige: ``modo`` vivo (D-07; ``exigir_modo=None`` solo para pruebas con reloj), semáforo VERDE e ítems
    TODOS VERDE (un ítem ROJO escondido bajo un semáforo VERDE no pasa), ``generado_en`` no en el futuro
    (más de ``tolerancia_futuro_s``), edad <= ``min(max_horas, 6)`` y ``valido_hasta`` vigente. La firma del
    archivo la verifica ``engine.guard`` ANTES de llamar acá (crítica B03).
    """
    if exigir_modo is not None and estado.get("modo") != exigir_modo:
        return False, f"modo {estado.get('modo')!r} != {exigir_modo!r}"
    items = estado.get("items") or [{"estado": "ROJO"}]
    if estado.get("semaforo") != "VERDE" or any(i.get("estado") != "VERDE" for i in items):
        return False, "semáforo o ítems no VERDE"
    max_horas = min(max_horas, 6)  # el tope de 6 h es del backbone: no lo sube un parámetro
    gen = _dt.datetime.strptime(estado["generado_en"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)
    t = ahora()
    if gen - t > _dt.timedelta(seconds=tolerancia_futuro_s):
        return False, "generado_en en el futuro"
    if t - gen > _dt.timedelta(hours=max_horas):
        return False, f"estado de hace {t - gen} (> {max_horas} h)"
    if t > _dt.datetime.strptime(estado["valido_hasta"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc):
        return False, "estado vencido (valido_hasta)"
    return True, "ok"


def semaforo_coherente(estado: dict) -> bool:
    """El semáforo global es el peor de sus ítems (VERDE solo si todos VERDE)."""
    estados = [i["estado"] for i in estado["items"]]
    if "ROJO" in estados:
        return estado["semaforo"] == "ROJO"
    if all(e == "VERDE" for e in estados):
        return estado["semaforo"] == "VERDE"
    return estado["semaforo"] in ("AMARILLO", "ROJO")


# ----------------------------------------------------------------------------------------------
# Reglas cruzadas de una oferta
# ----------------------------------------------------------------------------------------------
@dataclass
class Contexto:
    """Datos cargados de una oferta y de la empresa para las reglas cruzadas."""
    dir: Path
    datos: dict[str, Any]            # ruta relativa -> contenido
    limites: dict | None
    parametros: dict | None
    autonomia: dict | None
    gates: dict
    informe: Informe
    clave_firma: bytes | None = None
    verificador: Callable[[bytes, str], bool] | None = None
    clave_catalogo: bytes | None = None   # CATALOGO_HMAC (distinta de FABRICA_FIRMA_CLAVE); sin ella solo se comprueba el formato de la firma

    def get(self, rel: str) -> Any:
        return self.datos.get(rel)

    def param(self, grupo: str, clave: str, defecto: Any = None) -> Any:
        try:
            return self.parametros["grupos"][grupo][clave]["valor"]
        except (TypeError, KeyError):
            return defecto


def _rx(r: str) -> "re.Pattern[str]":
    return re.compile(r, re.IGNORECASE)


def ejemplo_permitido() -> bool:
    """``ofertas/_ejemplo`` (límites ficticios, clave de prueba pública) solo se valida fuera de producción (M18)."""
    return os.environ.get("FABRICA_ENTORNO") != "produccion"


def regla_ids(c: Contexto) -> None:
    """X01: ``oferta_id`` y ``familia_id`` iguales en todos los artefactos y con el nombre de la carpeta."""
    inf = c.informe
    brief = c.get("00-brief.yaml")
    oid = brief["oferta_id"] if brief else c.dir.name
    fid = brief["familia_id"] if brief else None
    if not (c.dir.name == "_ejemplo" and ejemplo_permitido()) and c.dir.name != oid:
        inf.error("X01_ID", c.dir.name, f"la carpeta no coincide con oferta_id {oid}")
    for rel, d in c.datos.items():
        objs = d if isinstance(d, list) else [d]
        for k, o in enumerate(objs):
            if not isinstance(o, dict):
                continue
            suf = f"[{k}]" if isinstance(d, list) else ""
            if "oferta_id" in o and o["oferta_id"] not in (None, oid):
                inf.error("X01_ID", rel + suf, f"oferta_id {o['oferta_id']} != {oid}")
            if "familia_id" in o and o["familia_id"] != fid:
                inf.error("X01_ID", rel + suf, f"familia_id {o['familia_id']} != {fid}")
    prod = c.get("04-producto/producto.json")
    if prod and prod["producto_id"] != "PROD-" + oid:
        inf.error("X01_ID", "04-producto/producto.json", f"producto_id debe ser PROD-{oid}")
    inf.verificados += 1


def regla_hashes(c: Contexto) -> None:
    """X02/X03/X04: hashes de brief, de salida de etapa, de campaña y de QA coinciden con el contenido."""
    inf, d = c.informe, c.dir
    brief = c.get("00-brief.yaml")
    if brief:
        esperado = hash_objeto(brief, excluir=("hash", "aprobado_por"))
        if not comparar_hash(brief["hash"], esperado):
            inf.error("X04_HASH_BRIEF", "00-brief.yaml", f"hash del brief {brief['hash']} != calculado {esperado}")
        if c.clave_firma and brief["aprobado_por"].get("firma"):
            f = firma_hmac({"hash": brief["hash"], "aprobador": brief["aprobado_por"]["id"], "fecha": brief["aprobado_por"]["fecha"]}, c.clave_firma)
            if not comparar_hash(f, brief["aprobado_por"]["firma"]):
                inf.error("X04_FIRMA_BRIEF", "00-brief.yaml", "la firma HMAC del brief no verifica")
    est0 = c.get("estado.json")
    if est0 and c.clave_firma:
        for etapa, e in est0["etapas"].items():
            ap = e["aprobado_por"]
            if ap and ap.get("firma"):
                f = firma_hmac({"oferta_id": est0["oferta_id"], "etapa": etapa, "hash_salida": e["hash_salida"], "aprobador": ap["id"], "fecha": ap["fecha"]}, c.clave_firma)
                if not comparar_hash(f, ap["firma"]):
                    inf.error("X02_FIRMA_ETAPA", f"estado.json/{etapa}", "la firma HMAC de la aprobación no verifica contra hash_salida")
    elif est0 and not c.clave_firma:
        if os.environ.get("FABRICA_ENTORNO") == "produccion":
            inf.error("X02_FIRMA_ETAPA", "estado.json", "firmas no verificadas en producción (falta la clave de verificación): falla cerrado (B01)")
        else:
            inf.aviso("X02_FIRMA_ETAPA", "estado.json", "firmas HMAC no verificadas (falta FABRICA_FIRMA_CLAVE)")
    cand0 = c.get("01-descubrimiento/candidatos.json")
    if cand0:
        for x in cand0["candidatos"]:
            for ev in x["evidencia"]:
                crudo = d / "01-descubrimiento" / "crudo" / f"{ev['id']}.txt"
                if crudo.is_file() and not comparar_hash(ev["hash_copia_crudo"], hash_archivo(crudo)):
                    inf.error("X05_HASH_CRUDO", "01-descubrimiento/candidatos.json", f"{ev['id']}: hash_copia_crudo no coincide con el texto crudo")
    camp = c.get("07-campana/campana.json")
    if camp:
        esperado = hash_objeto(camp, excluir=("hash_config",))
        if not comparar_hash(camp["hash_config"], esperado):
            inf.error("X02_HASH_CAMPANA", "07-campana/campana.json", f"hash_config {camp['hash_config']} != calculado {esperado}")
    est = c.get("estado.json")
    if est:
        for etapa, e in est["etapas"].items():
            if e["hash_salida"] is not None:
                real = hash_salida_etapa(d, etapa)
                if real is None:
                    inf.error("X02_HASH_ETAPA", f"estado.json/{etapa}", "hash_salida declarado pero faltan archivos de la etapa")
                elif not comparar_hash(e["hash_salida"], real):
                    inf.error("X02_HASH_ETAPA", f"estado.json/{etapa}", f"hash_salida {e['hash_salida']} != calculado {real}")
            elif e["estado"] == "aprobado":
                inf.error("X02_HASH_ETAPA", f"estado.json/{etapa}", "etapa aprobada sin hash_salida")
    for rel, q in c.datos.items():
        if rel.startswith("qa/"):
            ref = d / q["artefacto_ref"]
            if not ref.exists():
                inf.error("X07_RUTA", rel, f"artefacto_ref no existe: {q['artefacto_ref']}")
            elif not comparar_hash(q["artefacto_sha256"], hash_ruta(ref)):
                inf.error("X03_HASH_QA", rel, f"artefacto_sha256 no coincide con {q['artefacto_ref']}")
            for r, h in q["entradas"].items():
                p = d / r
                if p.exists() and not comparar_hash(h, hash_ruta(p)):
                    inf.error("X03_HASH_QA", rel, f"hash de entrada {r} no coincide")
    inf.verificados += 1


def regla_estado(c: Contexto) -> None:
    """X11/X24: gate y nivel coherentes con autonomia y la tabla de gates; dependencias y cadena de hashes."""
    inf = c.informe
    est, brief = c.get("estado.json"), c.get("00-brief.yaml")
    if not est:
        return
    if brief and NIVELES.index(est["nivel"]) > NIVELES.index(brief["nivel_autonomia"]):
        inf.error("X11_NIVEL", "estado.json", f"nivel {est['nivel']} supera el nivel del brief {brief['nivel_autonomia']}")
    if c.autonomia:
        for etapa, e in est["etapas"].items():
            techo = c.autonomia["nivel_por_etapa"].get(etapa, {}).get("nivel")
            if techo and NIVELES.index(e["nivel"]) > NIVELES.index(techo):
                inf.error("X11_NIVEL", f"estado.json/{etapa}", f"nivel {e['nivel']} supera autonomia.yaml ({techo})")
    for etapa, e in est["etapas"].items():
        nivel = nivel_efectivo(etapa, est, c.autonomia)
        if e["nivel"] != nivel:
            inf.error("X11_NIVEL", f"estado.json/{etapa}", f"nivel {e['nivel']} != nivel efectivo {nivel}")
        clave = f"etapa:{etapa}"
        if clave in c.gates["entradas"]:
            esp = gate_esperado(clave, nivel, c.gates)
            if e["gate"] != esp:
                inf.error("X11_GATE", f"estado.json/{etapa}", f"gate {e['gate']} != tabla de gates ({esp}) para {nivel}")
        ap = e["aprobado_por"]
        if e["estado"] == "aprobado":
            if e["gate"] == "H" and (not ap or ap["tipo"] != "humano" or not ap.get("firma")):
                inf.error("X11_GATE", f"estado.json/{etapa}", "gate H aprobado sin firma de humano")
            if e["gate"] in ("S", "A") and not ap:
                inf.error("X11_GATE", f"estado.json/{etapa}", "etapa aprobada sin aprobado_por")
            if e["version_aprobada"] is None:
                inf.error("X11_ESTADO", f"estado.json/{etapa}", "aprobado sin version_aprobada")
            for dep in DEPENDENCIAS.get(etapa, []):
                if est["etapas"][dep]["estado"] != "aprobado":
                    inf.error("X24_DEP", f"estado.json/{etapa}", f"aprobada pero su entrada {dep} no está aprobada")
                elif e["entradas"].get(dep) != est["etapas"][dep]["hash_salida"]:
                    inf.error("X24_DEP", f"estado.json/{etapa}", f"entradas[{dep}] no coincide con hash_salida de {dep} (obsoleta)")
        if e["estado"] == "en_QA" and not e["gate_pendiente"] and e["gate"] == "H":
            inf.aviso("X11_ESTADO", f"estado.json/{etapa}", "en_QA con gate H sin gate_pendiente")
        if e["gate_pendiente"] and e["estado"] != "en_QA":
            inf.error("X11_ESTADO", f"estado.json/{etapa}", "gate_pendiente solo es un indicador dentro de en_QA")
        if e["estado"] == "bloqueado" and not e["bloqueo"]:
            inf.error("X11_ESTADO", f"estado.json/{etapa}", "bloqueado sin motivo")
        if e["obsoleta"] and e["estado"] == "aprobado":
            inf.error("X11_ESTADO", f"estado.json/{etapa}", "una etapa obsoleta debe volver a pendiente")
    ce = est.get("candidato_elegido")
    cand = c.get("01-descubrimiento/candidatos.json")
    if ce and cand and ce["candidato_id"] not in {x["candidato_id"] for x in cand["candidatos"]}:
        inf.error("X12_CAND", "estado.json", "candidato_elegido no figura en candidatos.json")
    inf.verificados += 1


def regla_nichos_y_riesgo(c: Contexto) -> None:
    """X12/X13: macro_nicho permitido y consistente; riesgo.nivel = máximo de los ejes; sin rojos."""
    inf = c.informe
    permitidos = set((c.limites or {}).get("macro_nichos_permitidos") or MACRO_NICHOS)
    prohibidos = set((c.limites or {}).get("subnichos_prohibidos") or [])
    cand = c.get("01-descubrimiento/candidatos.json")
    oferta = c.get("03-oferta/oferta.json")
    val = c.get("02-validacion/validacion.json")
    brief = c.get("00-brief.yaml")

    def revisar_riesgo(r: dict, ruta: str) -> None:
        maximo = max((r[e] for e in "PCEN"), key=ORDEN_RIESGO.get)
        if r["nivel"] != maximo:
            inf.error("X13_RIESGO", ruta, f"riesgo.nivel={r['nivel']} pero el máximo de los ejes P,C,E,N es {maximo}")
        ra = r["reencuadre_aplicado"]
        if ra["aplicado"] and ORDEN_RIESGO[ra["nivel_original"]] <= ORDEN_RIESGO[r["nivel"]]:
            inf.error("X13_RIESGO", ruta, "reencuadre_aplicado: nivel_original debe ser mayor que el nivel resultante")
        if not ra["aplicado"] and ra.get("nivel_original"):
            inf.error("X13_RIESGO", ruta, "nivel_original sin reencuadre aplicado")

    if brief:
        extra = set(brief["nichos"]["permitidos"]) - permitidos
        if extra:
            inf.error("X12_NICHO", "00-brief.yaml", f"nichos del brief fuera de los permitidos por limites: {sorted(extra)}")
        if not set(brief["nichos"]["subnichos_prohibidos"]) >= prohibidos:
            inf.error("X12_NICHO", "00-brief.yaml", "el brief no puede quitar subnichos prohibidos por limites")
    elegido = None
    if cand:
        for k, x in enumerate(cand["candidatos"]):
            ruta = f"01-descubrimiento/candidatos.json/candidatos/{k}"
            if x["macro_nicho"] not in MACRO_NICHOS or x["macro_nicho"] not in permitidos:
                inf.error("X12_NICHO", ruta, f"macro_nicho {x['macro_nicho']} fuera de {sorted(permitidos)}")
            if x["nicho_id"] in prohibidos or x["microsegmento"] in prohibidos:
                inf.error("X12_NICHO", ruta, "sub-nicho prohibido por limites.subnichos_prohibidos")
            revisar_riesgo(x["riesgo"], ruta + "/riesgo")
            if x["riesgo"]["nivel"] == "rojo":
                inf.error("X13_RIESGO", ruta, "candidato ROJO no puede avanzar: reencuadrar o descartar (decisión 13)")
            if x["mecanismo"]["nombre"].count(" ") > 5:
                inf.error("X12_MU", ruta, "el nombre del mecanismo debe tener 2 a 6 palabras")
        est = c.get("estado.json")
        if est and est.get("candidato_elegido"):
            elegido = next((x for x in cand["candidatos"] if x["candidato_id"] == est["candidato_elegido"]["candidato_id"]), None)
    if oferta:
        if oferta["macro_nicho"] not in MACRO_NICHOS or oferta["macro_nicho"] not in permitidos:
            inf.error("X12_NICHO", "03-oferta/oferta.json", f"macro_nicho {oferta['macro_nicho']} no permitido")
        revisar_riesgo(oferta["riesgo"], "03-oferta/oferta.json/riesgo")
        niv = oferta["riesgo"]["nivel"]
        if niv == "rojo":
            inf.error("X13_RIESGO", "03-oferta/oferta.json", "oferta ROJA: no puede avanzar")
        if niv == "amarillo" and not oferta["requiere_gate_humano_legal"]:
            inf.error("X13_RIESGO", "03-oferta/oferta.json", "riesgo amarillo exige requiere_gate_humano_legal=true")
        if elegido:
            if oferta["macro_nicho"] != elegido["macro_nicho"]:
                inf.error("X12_NICHO", "03-oferta/oferta.json", "macro_nicho distinto del candidato elegido")
            if ORDEN_RIESGO[niv] > ORDEN_RIESGO[elegido["riesgo"]["nivel"]]:
                inf.error("X13_RIESGO", "03-oferta/oferta.json", "la oferta no puede tener más riesgo que el candidato elegido")
            if oferta["candidato_ref"]["candidato_id"] != elegido["candidato_id"] or oferta["candidato_ref"]["problema_id"] != elegido["problema_id"]:
                inf.error("X12_CAND", "03-oferta/oferta.json", "candidato_ref no coincide con el candidato elegido")
    if val:
        revisar_riesgo(val["riesgo_politica"], "02-validacion/validacion.json/riesgo_politica")
        if val["macro_nicho"] not in permitidos:
            inf.error("X12_NICHO", "02-validacion/validacion.json", "macro_nicho no permitido")
    inf.verificados += 1


def regla_economia(c: Contexto) -> None:
    """X14: recalcula la economía de D3 con ``engine.factibilidad.calcular`` (única fórmula, D-01) y compara con lo declarado."""
    from engine import factibilidad as fact   # perezoso: engine.comun importa este módulo; aquí solo hace falta engine.errores
    from engine.errores import ErrorFabrica

    inf = c.informe
    eco, oferta = c.get("03-oferta/economia.json"), c.get("03-oferta/oferta.json")
    if not eco:
        return
    e = eco["entradas_usadas"]
    mon = e["moneda"]
    precio, bump = e["precio"]["monto"], e["precio_bump"]["monto"]
    ruta = "03-oferta/economia.json"
    dias, plan = eco["dias_test"], eco["gasto_test_plan"]["monto"]
    if plan % dias:
        inf.error("X14_ECONOMIA", ruta + "/gasto_test_plan", f"gasto_test_plan {plan} debe ser gasto diario × dias_test ({dias}): no es múltiplo")
        return
    entradas = {**e, "gasto_diario": plan // dias, "dias_test": dias, "k": eco["criterios_corte"]["k"], "n_dec": eco["criterios_corte"]["n_dec"],
                "evento_optimizacion_inicial": eco["evento_optimizacion_inicial"], "validada": eco["criterios_corte"]["validada"],
                "costos_fijos_oferta": e.get("costos_fijos_oferta", {"monto": 0, "moneda": mon})}
    min_fact = c.param("economia", "razon_min_factible")
    try:
        calc = fact.calcular(entradas, c.parametros, c.limites, estricto=False)
    except ErrorFabrica as exc:
        inf.error("X14_ECONOMIA", ruta, f"engine.factibilidad.calcular no pudo recalcular: {exc.mensaje}")
        return
    for k in ("aov", "mc", "cpa_be", "cpa_obj", "presupuesto_test_min"):
        if eco[k]["monto"] != calc[k]["monto"]:
            inf.error("X14_ECONOMIA", f"{ruta}/{k}", f"declarado {eco[k]['monto']} != recalculado {calc[k]['monto']}")
    for k, v in calc["cpa_real"].items():
        if eco["cpa_real"][k]["monto"] != v["monto"]:
            inf.error("X14_ECONOMIA", f"{ruta}/cpa_real/{k}", f"declarado {eco['cpa_real'][k]['monto']} != recalculado {v['monto']}")
    for k in ("razon", "razon_obj", "roas_be"):
        if eco[k] != calc[k]:
            inf.error("X14_ECONOMIA", f"{ruta}/{k}", f"declarada {eco[k]} != recalculada {calc[k]}")
    if "tasa_iva_bp" in e:
        _regla_economia_d02(c, eco, e, calc)
    if plan < calc["presupuesto_test_min"]["monto"]:
        inf.error("X14_ECONOMIA", ruta, "gasto_test_plan inferior a presupuesto_test_min")
    if eco["cpa_be"]["monto"] != eco["mc"]["monto"] or not 0 < eco["mc"]["monto"] <= eco["aov"]["monto"]:
        inf.error("X14_ECONOMIA", ruta + "/mc", "mc debe cumplir 0 < mc <= aov y cpa_be = mc")
    if not 0 < eco["cpa_obj"]["monto"] <= eco["cpa_be"]["monto"]:
        inf.error("X14_ECONOMIA", ruta + "/cpa_obj", "cpa_obj debe cumplir 0 < cpa_obj <= cpa_be")
    if calc["veredicto"] is None:
        inf.aviso("X14_VEREDICTO", ruta, "sin razon_min_factible (parametros.economia) no se verifica el veredicto")
    elif eco["veredicto"] != calc["veredicto"]:
        # igualdad EXACTA con lo que calcula engine.factibilidad (razón sin redondear; la razón impresa a 2 decimales es informativa)
        inf.error("X14_ECONOMIA", ruta + "/veredicto",
                  f"declarado {eco['veredicto']} != recalculado {calc['veredicto']} (razón {calc['razon']}, mínimo {min_fact})")
    if eco["perdida_max_test"] != calc["perdida_max_test"]:
        inf.error("X14_ECONOMIA", ruta + "/perdida_max_test",
                  f"declarada {eco['perdida_max_test']} != gasto_test_plan + costos_fijos_oferta = {calc['perdida_max_test']}")
    if eco["entradas_usadas"]["moneda"] != eco["aov"]["moneda"]:
        inf.error("X14_ECONOMIA", ruta, "monedas mezcladas")
    if oferta:
        if oferta["precio"]["lista"]["monto"] != precio or oferta["precio"]["lista"]["moneda"] != mon:
            inf.error("X14_ECONOMIA", ruta, "precio/moneda distintos de oferta.precio.lista")
        if oferta["bump"] and oferta["bump"]["precio"]["monto"] != bump:
            inf.error("X14_ECONOMIA", ruta, "precio_bump distinto de oferta.bump.precio")
        if oferta["moneda"] != mon:
            inf.error("X14_ECONOMIA", "03-oferta/oferta.json", "oferta.moneda distinta de la economía")
    if eco["gasto_test_plan"]["monto"] > eco["perdida_max_test"]["monto"]:
        inf.error("X14_ECONOMIA", ruta, "gasto_test_plan supera perdida_max_test")
    if c.limites and c.limites.get("perdida_max_test_por_oferta") is not None:
        if c.limites["moneda_limites"] == mon and eco["perdida_max_test"]["monto"] > c.limites["perdida_max_test_por_oferta"]:
            inf.error("X10_LIMITES", ruta, "perdida_max_test supera limites.perdida_max_test_por_oferta")
    inf.verificados += 1


def _regla_economia_d02(c: Contexto, eco: dict, e: dict, calc: dict) -> None:
    """X14 sobre los campos D-02: derivados del escenario central y de las tarifas (los calcula ``engine.factibilidad``); monedas y origen de tarifas coherentes."""
    from fractions import Fraction
    inf, ruta = c.informe, "03-oferta/economia.json"
    mon = e["moneda"]
    if Fraction(dec(eco["conv_central"])) != Fraction(dec(calc["conv_central"])):
        inf.error("X14_ECONOMIA", ruta + "/conv_central", f"{eco['conv_central']} != clic_compra_bp/10000 del escenario central")
    cpc = Fraction(dec(calc["cpc_esperado"]["monto"]))
    if eco["cpc_esperado"]["moneda"] != mon or abs(Fraction(dec(eco["cpc_esperado"]["monto"])) - cpc) > Fraction(1, 1000):
        inf.error("X14_ECONOMIA", ruta + "/cpc_esperado", f"{eco['cpc_esperado']} != cpm/(1000 x ctr) = {calc['cpc_esperado']['monto']} del escenario central")
    visto = calc["cpa_be_visto"]["monto"]
    if eco["cpa_be_visto"]["monto"] != visto or eco["cpa_be_visto"]["moneda"] != mon:
        inf.error("X14_ECONOMIA", ruta + "/cpa_be_visto", f"declarado {eco['cpa_be_visto']['monto']} != cpa_be x 10000 / (10000 + tarifa_meta_bp) = {visto}")
    if eco["resultado_esperado_central"]["monto"] != calc["resultado_esperado_central"]["monto"]:
        inf.error("X14_ECONOMIA", ruta + "/resultado_esperado_central",
                  f"declarado {eco['resultado_esperado_central']['monto']} != recalculado {calc['resultado_esperado_central']['monto']}")
    for nombre, din in (("stripe_tax.fijo", e["stripe_tax"]["fijo"]), ("resultado_esperado_central", eco["resultado_esperado_central"])):
        if din["moneda"] != mon:
            inf.error("X14_ECONOMIA", ruta, f"{nombre} en {din['moneda']} y la economía en {mon}: monedas mezcladas")
    if e["tarifas_origen"] == "supuesto" and "[SUPUESTO]" not in e["tarifas_fuente"]:
        inf.error("X14_TARIFAS", ruta, "tarifas_origen=supuesto exige que tarifas_fuente lleve la marca [SUPUESTO]")
    if e["tarifas_origen"] == "tarifas_json_f1" and "[SUPUESTO]" in e["tarifas_fuente"]:
        inf.error("X14_TARIFAS", ruta, "tarifas_origen=tarifas_json_f1 pero tarifas_fuente sigue marcada [SUPUESTO]")
    conocidas = {k for ks in CLAVES_CRITICAS.values() for k in ks}
    for k in eco["limites_pendientes"]:
        if k not in conocidas:
            inf.error("X14_LIMITES_PENDIENTES", ruta, f"limites_pendientes: {k} no es una clave crítica de limites.yaml")
    if c.limites:
        declaradas, reales = set(eco["limites_pendientes"]), set(calc["limites_pendientes"])
        if declaradas - reales:   # afirma «pendiente» algo que YA tiene valor: la economía miente
            inf.error("X14_LIMITES_PENDIENTES", ruta, f"limites_pendientes lista {sorted(declaradas - reales)}, que ya tienen valor en limites.yaml "
                      "(al sellar o cambiar limites.yaml hay que regenerar economia.json)")
        if reales - declaradas:   # instantánea vieja: el guard sigue bloqueando el gasto; no invalida la economía
            inf.aviso("X14_LIMITES_PENDIENTES", ruta, f"limites.yaml aún tiene null {sorted(reales - declaradas)} que economia.json no lista")
    else:
        inf.aviso("X14_LIMITES_PENDIENTES", ruta, "sin limites.yaml cargado no se verifica limites_pendientes")


def regla_tiempos(c: Contexto) -> None:
    """X15: el tiempo prometido nace en D3 (única fuente); D4 lo mide sin cambiarlo."""
    inf = c.informe
    oferta, prod = c.get("03-oferta/oferta.json"), c.get("04-producto/producto.json")
    if not (oferta and prod):
        return
    prom = oferta["promesa"]["tiempo_prometido_min"]
    if prod["tiempos"]["prometido_min"] != prom:
        inf.error("X15_TIEMPO", "04-producto/producto.json", f"tiempos.prometido_min {prod['tiempos']['prometido_min']} != oferta.promesa.tiempo_prometido_min {prom}")
    f_dis = c.param("economia", "tiempo_diseno_max_factor", "1.10")
    if oferta["vehiculo"]["tiempo_consumo_min"] * 100 > prom * int(dec(f_dis) * 100):
        inf.error("X15_TIEMPO", "03-oferta/oferta.json", f"tiempo_consumo_min {oferta['vehiculo']['tiempo_consumo_min']} > {f_dis} x prometido")
    t = prod["tiempos"]
    # Base estimada: la fórmula de D4 exige total <= prometido; medido en frío: <= cold_run_tolerancia x prometido.
    f_med = "1.0" if t["base"] == "estimado" else c.param("producto", "cold_run_tolerancia", "1.25")
    if t["total_min"] * 100 > prom * int(dec(f_med) * 100):
        inf.error("X15_TIEMPO", "04-producto/producto.json", f"total_min {t['total_min']} > {f_med} x prometido ({t['base']})")
    if t["lectura_min"] + t["ejecucion_min"] != t["total_min"]:
        inf.error("X15_TIEMPO", "04-producto/producto.json", "total_min != lectura_min + ejecucion_min")
    lm = c.param("producto", "lectura_max_pct_prometido")
    if lm is not None and t["lectura_min"] * 100 > prom * int(lm):
        inf.error("X15_TIEMPO", "04-producto/producto.json", f"lectura_min supera {lm} % del tiempo prometido")
    inf.verificados += 1


def regla_rutas_y_assets(c: Contexto) -> None:
    """X05/X06/X07: archivos citados existen y sus hashes coinciden; precio y destino alineados con la oferta."""
    inf, d = c.informe, c.dir
    prod = c.get("04-producto/producto.json")
    if prod:
        base = d / "04-producto"
        for it in prod["items"]:
            p = base / it["archivo"] if not it["archivo"].startswith("04-producto/") else d / it["archivo"]
            if not p.is_file():
                inf.error("X07_RUTA", "04-producto/producto.json", f"item {it['id']}: no existe {it['archivo']}")
            elif not comparar_hash(it["sha256"], hash_archivo(p)):
                inf.error("X05_HASH_ITEM", "04-producto/producto.json", f"item {it['id']}: sha256 no coincide con {it['archivo']}")
        oferta = c.get("03-oferta/oferta.json")
        if oferta and prod["items"] and not any(i["en_paquete"] for i in prod["items"]):
            inf.error("X05_ITEM", "04-producto/producto.json", "ningún ítem en paquete")
        if oferta and prod["entrega"]["vence_dias"] != c.param("entrega", "enlace_vence_dias", prod["entrega"]["vence_dias"]):
            inf.aviso("X05_ENTREGA", "04-producto/producto.json", "vence_dias distinto de parametros.entrega.enlace_vence_dias")
    assets = c.get("05-landing/assets.json")
    if assets:
        for s in assets["slots"]:
            if s["archivo"]:
                p = d / "05-landing" / s["archivo"]
                if not p.is_file():
                    inf.error("X07_RUTA", "05-landing/assets.json", f"slot {s['slot_id']}: no existe {s['archivo']}")
                elif not comparar_hash(s["sha256"], hash_archivo(p)):
                    inf.error("X05_HASH_ITEM", "05-landing/assets.json", f"slot {s['slot_id']}: sha256 no coincide")
            if s["tipo"] == "captura_producto" and s["origen"] not in (None, "producto_muestra"):
                inf.error("X05_ITEM", "05-landing/assets.json", f"slot {s['slot_id']}: una captura de producto debe ser de una muestra real")
    paq = c.get("06-creativos/paquete.json")
    if paq:
        for a in paq["anuncios"]:
            for k, asset in enumerate(a["assets"]):
                p = d / "06-creativos" / asset["archivo"]
                if not p.is_file():
                    inf.error("X07_RUTA", "06-creativos/paquete.json", f"{a['ad_name']}: no existe {asset['archivo']}")
                elif not comparar_hash(asset["sha256"], hash_archivo(p)):
                    inf.error("X06_HASH_ASSET", "06-creativos/paquete.json", f"{a['ad_name']}: sha256 no coincide con {asset['archivo']}")
            if a["lint_x1"] == "FAIL":
                inf.error("X06_X1", "06-creativos/paquete.json", f"{a['ad_name']}: lint X1 en FAIL no puede estar en el paquete")
        sitio = d / "05-landing" / "sitio"
        if sitio.is_dir() and not comparar_hash(paq["destino"]["landing_hash"], hash_directorio(sitio)):
            inf.error("X06_HASH_LANDING", "06-creativos/paquete.json", "destino.landing_hash no coincide con 05-landing/sitio/")
        oferta = c.get("03-oferta/oferta.json")
        if oferta:
            if paq["destino"]["precio"] != oferta["precio"]["lista"]:
                inf.error("X06_PRECIO", "06-creativos/paquete.json", "destino.precio distinto de oferta.precio.lista")
            angs = {a["angulo_id"] for a in oferta["angulos"]}
            for cc in paq["conceptos"]:
                if cc["angulo_id"] not in angs:
                    inf.error("X06_ANGULO", "06-creativos/paquete.json", f"concepto {cc['concepto_id']}: angulo_id {cc['angulo_id']} no existe en la oferta")
            claims = {x["claim_id"] for x in oferta["promesa"]["claims_permitidos"]}
            for a in paq["anuncios"]:
                for cl in a["claim_ids"]:
                    if cl not in claims:
                        inf.error("X06_CLAIM", "06-creativos/paquete.json", f"{a['ad_name']}: claim_id {cl} no permitido por la oferta")
        for ref in (paq["qa_ref"], paq["x1_ref"]):
            if not ((d / ref).exists() or (raiz_datos() / ref).exists()):
                inf.error("X07_RUTA", "06-creativos/paquete.json", f"no existe {ref}")
        x1d = c.get(paq["x1_ref"])
        if x1d and (x1d["veredicto"] == "FAIL" or x1d.get("etapa_objetivo") != "D6"):
            inf.error("X06_X1", "06-creativos/paquete.json", "x1_ref no es un dictamen PASS de D6")
        conceptos = {x["concepto_id"] for x in paq["conceptos"]}
        for a in paq["anuncios"]:
            if a["concepto_id"] not in conceptos:
                inf.error("X06_CONCEPTO", "06-creativos/paquete.json", f"{a['ad_name']}: concepto desconocido")
            if not a["ad_name"].startswith(a["concepto_id"] + "_"):
                inf.error("X08_NOMBRE", "06-creativos/paquete.json", f"{a['ad_name']} no empieza por el concepto_id")
    inf.verificados += 1


def regla_checkout_tracking(c: Contexto) -> None:
    """X16/X17: checkout y tracking alineados con la oferta; eventos con las reglas de ``event_id`` del backbone 5.3."""
    inf = c.informe
    oferta, co, tr = c.get("03-oferta/oferta.json"), c.get("05-landing/checkout.json"), c.get("05-landing/tracking.json")
    if oferta and co:
        if co["precio"]["monto"] != oferta["precio"]["lista"]["monto"] or co["moneda"] != oferta["moneda"] or co["precio"]["moneda"] != oferta["moneda"]:
            inf.error("X16_CHECKOUT", "05-landing/checkout.json", "precio/moneda distintos de la oferta (el precio sale del catálogo del servidor)")
        if co["garantia_dias"] != oferta["garantia"]["dias"]:
            inf.error("X16_CHECKOUT", "05-landing/checkout.json", "garantia_dias distinta de la oferta")
        gmin = c.param("landing", "garantia_dias_min")
        if gmin is not None and co["garantia_dias"] < gmin:
            inf.error("X16_CHECKOUT", "05-landing/checkout.json", f"garantia_dias < parametros.landing.garantia_dias_min ({gmin})")
        if (oferta["bump"] is None) != (co["bump"] is None) or (oferta["bump"] and co["bump"]["precio"]["monto"] != oferta["bump"]["precio"]["monto"]):
            inf.error("X16_CHECKOUT", "05-landing/checkout.json", "bump distinto del de la oferta")
        host = oferta["marca"]["dominio"]
        for campo in ("success_url", "return_url"):
            h = urlsplit(co[campo]).hostname or ""
            if not (h == host or h.endswith("." + host)):
                inf.error("X16_CHECKOUT", "05-landing/checkout.json", f"{campo} no apunta al dominio de la marca ({host})")
        if co["price_ids"]["live"] is not None and co["price_ids"]["live"] == co["price_ids"]["test"]:
            inf.error("X16_CHECKOUT", "05-landing/checkout.json", "price_id live igual al de test")
    if tr:
        regla = {"Purchase": "purchase_<checkout_session_id>", "InitiateCheckout": "ic_<visitor_id>_<ts>"}
        for ev in tr["eventos"]:
            if ev["nombre"] in regla and ev["event_id_regla"] != regla[ev["nombre"]]:
                inf.error("X17_TRACKING", "05-landing/tracking.json", f"{ev['nombre']}: event_id_regla debe ser {regla[ev['nombre']]}")
            if ev["nombre"] == "Purchase" and ev["canal"] != "ambos":
                inf.error("X17_TRACKING", "05-landing/tracking.json", "Purchase debe enviarse por píxel y API de Conversiones (deduplicación)")
        if oferta and tr["dominio_verificado"] != oferta["marca"]["dominio"]:
            inf.error("X17_TRACKING", "05-landing/tracking.json", "dominio_verificado distinto del dominio de la marca")
        if _tiene_salud(tr, oferta):
            inf.error("X17_TRACKING", "05-landing/tracking.json", "datos de salud en el nombre/ruta de eventos o dominio (el píxel no puede recibir datos de salud)")
        rutas = cargar_json(c.dir / "05-landing" / "rutas.json") if (c.dir / "05-landing" / "rutas.json").is_file() else {}
        sens = _terminos_sensibles(" ".join([tr["dominio_verificado"], *(rutas or {}).keys()]))
        if sens:
            inf.error("X17_SENSIBLE", "05-landing/tracking.json", f"dominio o rutas con términos de salud/finanzas ({sens}); usar URLs y nombres neutros (Términos de las Herramientas de Empresa de Meta §1.h)")
        for ev in tr["eventos"]:
            extra = set(ev["parametros_permitidos"]) - PARAMETROS_EVENTO_PERMITIDOS
            if extra:
                inf.error("X17_SENSIBLE", "05-landing/tracking.json", f"{ev['nombre']}: parámetros fuera de la lista cerrada {sorted(extra)}")
        emq = c.param("landing", "emq_min_purchase")
        if emq is not None and dec(tr["emq_objetivo"]) < dec(emq):
            inf.error("X17_TRACKING", "05-landing/tracking.json", f"emq_objetivo < parametros.landing.emq_min_purchase ({emq})")
    inf.verificados += 1


def regla_catalogo(c: Contexto) -> None:
    """X48: el catálogo firmado (``05-landing/catalogo.json``) coincide con ``checkout.json`` y con ``07-campana/ids_meta.json``.

    Es lo que fija B0-09: el Worker solo acepta ``adid``/``asid``/``cid`` del catálogo, así que el catálogo no puede ir por delante ni
    por detrás de los ids reales, ni cobrar un precio que el checkout no declara. La firma se verifica con ``clave_catalogo``.
    """
    inf, cat = c.informe, c.get("05-landing/catalogo.json")
    if not cat:
        return
    rel = "05-landing/catalogo.json"
    for cod, msg in problemas_artefacto("catalogo", cat, clave=c.clave_catalogo, verificador=c.verificador):
        inf.error(cod, rel, msg)
    if c.clave_catalogo is None and tipo_firma(cat["firma"]) == "hmac":
        inf.aviso("X40_FIRMA", rel, "firma HMAC sin clave (CATALOGO_HMAC): solo se comprobó el formato, no la firma")
    co = c.get("05-landing/checkout.json")
    if co:
        for campo in ("oferta_id", "version", "moneda"):
            if cat[campo] != co[campo]:
                inf.error("X48_CATALOGO", rel, f"{campo} {cat[campo]} != checkout.{campo} ({co[campo]})")
        validos = {x for x in (co["price_ids"]["test"], co["price_ids"]["live"]) if x}
        if cat["price_ids"]["principal"] not in validos:
            inf.error("X48_CATALOGO", rel, "price_ids.principal no es checkout.price_ids.test ni .live: el precio sale solo del checkout")
        bump = (co.get("bump") or {}).get("price_id")
        if cat["price_ids"].get("bump") != bump:
            inf.error("X48_CATALOGO", rel, f"price_ids.bump ({cat['price_ids'].get('bump')}) != checkout.bump.price_id ({bump})")
        for campo in ("success_url", "return_url"):
            if campo in cat and cat[campo] != co[campo]:
                inf.error("X48_CATALOGO", rel, f"{campo} distinta de checkout.{campo}")
    ids, im = c.get("07-campana/ids_meta.json"), cat["ids_meta"]
    if ids:
        if im["campaign_id"] != ids["campaign_id"] or set(im["adset_ids"]) != set(ids["adset_ids"]) or set(im["ad_ids"]) != set(ids["ad_ids"]):
            inf.error("X48_CATALOGO", rel, "ids_meta distinto de 07-campana/ids_meta.json (el Worker aceptaría ids que ya no existen o rechazaría los vigentes)")
    elif im["campaign_id"] is not None:
        inf.error("X48_CATALOGO", rel, "ids_meta con ids pero no existe 07-campana/ids_meta.json: el catálogo firmaría ids que nadie creó")
    inf.verificados += 1


# Lista cerrada de parámetros de evento (M10): nada que revele una condición de salud o financiera.
PARAMETROS_EVENTO_PERMITIDOS = {"fbp", "fbc", "value", "currency", "content_ids", "content_type", "num_items", "event_id"}
# Mínimo de términos sensibles (es/en/it/pl/de/fr). La lista completa por locale es de X1/B6 (``compliance/reglas_sensibles.yaml``).
TERMINOS_SENSIBLES = (
    r"salud", r"diagnost", r"enfermedad", r"medic", r"health", r"patolog", r"ansiedad", r"insomni", r"depres", r"diabet", r"anxiety", r"sleep",
    r"deuda", r"prestamo", r"préstamo", r"credito", r"crédito", r"debt", r"loan", r"mortgage", r"hipoteca", r"invers",
    r"salute", r"ansia", r"debito", r"zdrow", r"dlug", r"dług", r"kredyt", r"gesundheit", r"schulden", r"sant[eé]", r"dette",
)


def _terminos_sensibles(texto: str) -> list[str]:
    t = unicodedata.normalize("NFC", texto).lower()
    return sorted({m for m in TERMINOS_SENSIBLES if re.search(m, t)})


def _tiene_salud(tr: dict, oferta: dict | None) -> bool:
    texto = " ".join([tr["dominio_verificado"]] + [e["nombre"] for e in tr["eventos"]] + [p for e in tr["eventos"] for p in e["parametros_permitidos"]]).lower()
    return bool(re.search(r"salud|diagnost|enfermedad|medic|health|patolog", texto))


def _query(url: str) -> dict[str, str]:
    return dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))


def regla_campana(c: Contexto) -> None:
    """X08/X09/X10: nombres de Meta (5.2), parámetros de URL (5.3), presupuesto dentro de límites y economía alineada."""
    inf = c.informe
    camp = c.get("07-campana/campana.json")
    if not camp:
        return
    oid = camp["oferta_id"]
    n = camp["nombres"]
    # Nombres (patrones en el esquema; aquí coherencias).
    if not n["campana"].startswith(oid + "_" + camp["fase"] + "_"):
        inf.error("X08_NOMBRE", "07-campana/campana.json", "el nombre de campaña debe empezar por {oferta_id}_{fase}_")
    if n["campana"].split("_")[3] != camp["estructura"]:
        inf.error("X08_NOMBRE", "07-campana/campana.json", "la estructura del nombre no coincide con camp.estructura")
    if not n["conjunto"].endswith("_" + camp["idioma"]):
        inf.error("X08_NOMBRE", "07-campana/campana.json", "el idioma del nombre del conjunto no coincide con camp.idioma")
    for texto in [n["campana"], n["conjunto"], *n["anuncios"], camp["url"]["plantilla"]]:
        if "|" in texto:
            inf.error("X08_NOMBRE", "07-campana/campana.json", f"'|' prohibido en nombres y URLs de Meta (usar '_' o %7C en macros): {texto[:60]}")
    nombres_anuncios = [a["ad_name"] for a in camp["anuncios"]]
    if sorted(nombres_anuncios) != sorted(n["anuncios"]) or len(set(nombres_anuncios)) != len(nombres_anuncios):
        inf.error("X08_NOMBRE", "07-campana/campana.json", "nombres.anuncios no coincide con anuncios[].ad_name (o hay duplicados)")
    paq = c.get("06-creativos/paquete.json")
    if paq:
        por_nombre = {a["ad_name"]: a for a in paq["anuncios"]}
        for a in camp["anuncios"]:
            pa = por_nombre.get(a["ad_name"])
            if not pa:
                inf.error("X08_NOMBRE", "07-campana/campana.json", f"{a['ad_name']} no está en el paquete de D6")
            elif a["asset_sha256"] != pa["assets"][0]["sha256"]:
                inf.error("X06_HASH_ASSET", "07-campana/campana.json", f"{a['ad_name']}: asset_sha256 distinto del paquete")
    # Parámetros de URL (5.3).
    q = _query(camp["url"]["plantilla"].replace("{{", "%7B%7B").replace("}}", "%7D%7D"))
    q = {k: v.replace("%7B%7B", "{{").replace("%7D%7D", "}}") for k, v in q.items()}
    exigidos = {"utm_source": "meta", "utm_medium": "paid", "utm_campaign": "{{campaign.name}}", "utm_content": "{{ad.name}}",
                "utm_term": "{{adset.name}}", "oferta_id": oid, "cid": "{{campaign.id}}", "asid": "{{adset.id}}", "adid": "{{ad.id}}"}
    for k, v in exigidos.items():
        if q.get(k) != v:
            inf.error("X09_URL", "07-campana/campana.json", f"parámetro de URL {k} debe ser {v!r}, es {q.get(k)!r}")
    res = _query(camp["url"]["ejemplo_resuelto"])
    for k in exigidos:
        if k not in res or "{{" in res.get(k, ""):
            inf.error("X09_URL", "07-campana/campana.json", f"ejemplo_resuelto: {k} ausente o sin resolver")
    if res.get("oferta_id") != oid:
        inf.error("X09_URL", "07-campana/campana.json", "ejemplo_resuelto con otro oferta_id")
    if paq and not camp["url"]["plantilla"].startswith(paq["destino"]["url_base"]):
        inf.error("X09_URL", "07-campana/campana.json", "la URL no parte de destino.url_base del paquete")
    # Economía alineada.
    eco = c.get("03-oferta/economia.json")
    p = camp["presupuesto"]
    exp = EXPONENTE_ISO4217.get(p["moneda"])
    if exp is None or p["decimales"] != exp:
        inf.error("X10_MONEDA", "07-campana/campana.json",
                  f"presupuesto.decimales {p['decimales']} != exponente ISO 4217 de {p['moneda']} ({exp if exp is not None else 'moneda sin exponente registrado: fail-closed'}): meta.monedas escalaría mal el gasto (M06)")
    cand = p.get("candado_alternativo")
    techo_perdida = p["spend_cap"] if p["spend_cap"] is not None else (cand["lifetime_budget"] if cand else None)
    if eco:
        ce = camp["economia"]
        for k, kk in (("cpa_equilibrio", "cpa_be"), ("cpa_objetivo", "cpa_obj")):
            if ce[k] != eco[kk]["monto"]:
                inf.error("X14_ECONOMIA", "07-campana/campana.json", f"economia.{k} != economia.json.{kk}")
        if ce["k_corte"] != eco["criterios_corte"]["k"] or p["moneda"] != eco["aov"]["moneda"]:
            inf.error("X14_ECONOMIA", "07-campana/campana.json", "k_corte o moneda distintos de economia.json")
        if p["total_test"] > eco["perdida_max_test"]["monto"]:
            inf.error("X10_LIMITES", "07-campana/campana.json", "total_test supera economia.perdida_max_test")
    if p["total_test"] != p["diario"] * p["dias"]:
        inf.error("X10_LIMITES", "07-campana/campana.json", "total_test != diario x dias")
    if camp["economia"]["n_anuncios"] != len(camp["anuncios"]):
        inf.error("X10_LIMITES", "07-campana/campana.json", "economia.n_anuncios != len(anuncios)")
    # Presupuesto dentro de límites (fail-closed).
    lim = c.limites
    factor = dec((lim or {}).get("factor_techo_teorico_diario") or "1.75")
    esperado_max = entero_redondeado(p["diario"] * int(factor * 100), 100, "techo")
    if p["max_teorico_diario"] != esperado_max:
        inf.error("X10_LIMITES", "07-campana/campana.json", f"max_teorico_diario {p['max_teorico_diario']} != techo(factor {factor} x diario) = {esperado_max}")
    ctrl = evaluar_limites(lim, "activar")
    if camp["estado"] == "borrador":
        if not ctrl:
            inf.aviso("X10_LIMITES", "07-campana/campana.json", "borrador: límites incompletos o sin sello; la campaña NO podrá activarse: " + ctrl.motivo)
    elif not ctrl:
        inf.error("X10_LIMITES", "07-campana/campana.json", f"estado {camp['estado']} con límites no válidos (fail-closed): {ctrl.motivo}", SALIDA_LIMITE)
    if lim and lim.get("gasto_diario_por_oferta") is not None:
        if lim.get("moneda_limites") != p["moneda"]:
            inf.error("X10_LIMITES", "07-campana/campana.json", f"moneda del presupuesto {p['moneda']} != moneda_limites {lim.get('moneda_limites')} (requiere tipo de cambio registrado)")
        else:
            # El máximo de pérdida publicitaria posible es el ``spend_cap`` (o, si es null, el ``lifetime_budget`` del
            # candado alternativo), no ``total_test`` (B05).
            valores = {**p, "spend_cap": techo_perdida}
            topes = [("max_teorico_diario", "gasto_diario_por_oferta"), ("total_test", "gasto_total_test_por_oferta"), ("spend_cap", "limite_gasto_cuenta_meta"),
                     ("spend_cap", "gasto_total_test_por_oferta"), ("spend_cap", "perdida_max_test_por_oferta")]
            for k, kl in topes:
                if lim.get(kl) is not None and valores[k] is not None and valores[k] > lim[kl]:
                    inf.error("X10_LIMITES", "07-campana/campana.json", f"presupuesto.{k} {valores[k]} supera limites.{kl} {lim[kl]}")
            if lim.get("perdida_max_test_por_oferta") is not None and p["total_test"] > lim["perdida_max_test_por_oferta"]:
                inf.error("X10_LIMITES", "07-campana/campana.json", "total_test supera limites.perdida_max_test_por_oferta")
            if lim.get("gasto_diario_global") is not None and p["max_teorico_diario"] > lim["gasto_diario_global"]:
                inf.error("X10_LIMITES", "07-campana/campana.json", "max_teorico_diario supera limites.gasto_diario_global")
        if lim.get("paises_permitidos") and not set(camp["paises"]) <= set(lim["paises_permitidos"]):
            inf.error("X10_LIMITES", "07-campana/campana.json", "países de la campaña fuera de limites.paises_permitidos")
        if lim.get("locales_permitidos") and camp["idioma"] not in lim["locales_permitidos"]:
            inf.error("X10_LIMITES", "07-campana/campana.json", "idioma fuera de limites.locales_permitidos")
        brief = c.get("00-brief.yaml")
        if brief and lim.get("cuentas_permitidas") and brief["cuenta_meta_id"] not in lim["cuentas_permitidas"]:
            inf.error("X10_LIMITES", "00-brief.yaml", "cuenta_meta_id fuera de limites.cuentas_permitidas")
    if techo_perdida is None:
        inf.error("X30_PRESUPUESTO", "07-campana/campana.json", "sin spend_cap ni candado_alternativo: la campaña no tendría tope de gasto")
    elif techo_perdida <= 0:
        inf.error("X30_PRESUPUESTO", "07-campana/campana.json", "spend_cap debe ser > 0 (0 = sin tope en Meta)")
    dmax = c.param("veredicto", "dias_max")
    if dmax is not None and p["dias"] > dmax:
        inf.error("X30_PRESUPUESTO", "07-campana/campana.json", f"presupuesto.dias {p['dias']} > veredicto.dias_max {dmax} (el gasto posterior no entra al veredicto)")
    cats = camp.get("special_ad_categories")
    if cats:
        aud = camp["audiencia"]
        if aud.get("intereses"):
            inf.error("X31_CATEGORIA_ESPECIAL", "07-campana/campana.json", "special_ad_categories no vacío: la audiencia no puede llevar intereses")
        if aud["edad_min"] != 18 or aud["edad_max"] != 65:
            inf.error("X31_CATEGORIA_ESPECIAL", "07-campana/campana.json", "special_ad_categories no vacío: edad fija 18-65")
        ofe = c.get("03-oferta/oferta.json")
        if ofe and not ofe.get("requiere_gate_humano_legal"):
            inf.error("X31_CATEGORIA_ESPECIAL", "03-oferta/oferta.json", "special_ad_categories no vacío exige requiere_gate_humano_legal=true")
    spend_cap_f = c.param("campana", "spend_cap_factor")
    calculado = entero_redondeado(p["total_test"] * int(dec(spend_cap_f) * 100), 100, "half_up") if spend_cap_f is not None else None
    if calculado is not None and p["spend_cap"] is not None and p["spend_cap"] != calculado:
        inf.error("X10_LIMITES", "07-campana/campana.json", f"spend_cap != {spend_cap_f} x total_test")
    _regla_spend_cap(c, camp, calculado)
    brief = c.get("00-brief.yaml")
    if brief:
        bp = brief["presupuesto"]
        if bp["test_total_max"]["moneda"] == p["moneda"] and p["total_test"] > bp["test_total_max"]["monto"]:
            inf.error("X10_LIMITES", "07-campana/campana.json", "total_test supera brief.presupuesto.test_total_max (el brief solo restringe)")
        if bp["test_diario_max"]["moneda"] == p["moneda"] and p["diario"] > bp["test_diario_max"]["monto"]:
            inf.error("X10_LIMITES", "07-campana/campana.json", "diario supera brief.presupuesto.test_diario_max")
    if camp["audiencia"]["edad_min"] > camp["audiencia"]["edad_max"]:
        inf.error("X10_LIMITES", "07-campana/campana.json", "edad_min > edad_max")
    inf.verificados += 1


# ----------------------------------------------------------------------------------------------
# Ola 0b-1 (esquemas 1.1.0): firmas, spend_cap nullable, brief, mercado, economía D-02,
# parámetros opcionales y los once artefactos nuevos. Todo puro y sin red.
# ----------------------------------------------------------------------------------------------
# SSHSIG de `ssh-keygen -Y sign` (engine.comun.firmar_ed25519): el base64 empieza por U1NIU0lH (= «SSHSIG»); una real mide ~248 caracteres.
RX_ED25519 = re.compile(r"ed25519:U1NIU0lH[A-Za-z0-9+/]{210,340}={0,2}")
RX_HMAC = re.compile(r"hmac-sha256:[0-9a-f]{64}")
# Tarifas de LLC de EE. UU. [SUPUESTO] hasta que exista tarifas.json de F1 con fecha dentro de
# finanzas.tarifas_antiguedad_max_dias (30). https://stripe.com/pricing, nota 03 4.1, leída 2026-11-05.
TARIFAS_LLC_US_SUPUESTO = {
    "origen": "supuesto", "fuente": "[SUPUESTO] LLC de EE. UU.: 2,9 % + 0,30 USD tarjeta doméstica, +1,5 % internacional, +1 % conversión, disputa 15 USD "
                                     "(https://stripe.com/pricing; docs/_investigacion/03-stripe.md 4.1, leída 2026-11-05)",
    "comision_pct_bp": 290, "comision_fija": {"monto": 30, "moneda": "USD"}, "recargos_bp": 150, "conversion_bp": 100,
    "tarifa_disputa": {"monto": 1500, "moneda": "USD"},
}
SELLO_ESTADOS_VERDES = ("VERDE", "NO_APLICA")


def tipo_firma(firma: Any) -> str | None:
    """``"ed25519"``, ``"hmac"`` o ``None`` según el FORMATO de la firma (no la verifica)."""
    if not isinstance(firma, str):
        return None
    if RX_ED25519.fullmatch(firma):
        return "ed25519"
    if RX_HMAC.fullmatch(firma):
        return "hmac"
    return None


def _en_produccion(entorno: str | None) -> bool:
    return (entorno if entorno is not None else os.environ.get("FABRICA_ENTORNO", "")) == "produccion"


def payload_firma_v1(nombre: str, d: dict) -> dict:
    """Payload ANTERIOR a CT1-06 (la firma de ``aprobacion`` no cubría nivel, gate, tipo ni creado_en). Solo para migrar firmas viejas."""
    if nombre == "aprobacion":
        ap = d["aprobado_por"]
        base = {"oferta_id": d["oferta_id"], "hash_objetivo": d["hash_objetivo"], "object_ids": sorted(d["object_ids"]),
                "vigencia_hasta": d["vigencia_hasta"], "aprobador": ap["id"], "fecha": ap["fecha"]}
        base.update({k: d[k] for k in ("etapa", "accion") if k in d})
        return base
    return payload_firma(nombre, d)


def payload_firma(nombre: str, d: dict) -> dict:
    """Contenido que se firma para ``aprobacion``, ``sello``, ``orden_firmada`` y ``catalogo`` (el resto no se firma aquí).

    ``aprobacion`` (CT1-06) cubre TODO salvo la firma: versión, gate, nivel, tipo de aprobador, ``creado_en`` y vigencia,
    de modo que degradar un H a S o cambiar el tipo invalida la firma.
    """
    if nombre == "aprobacion":
        ap = d["aprobado_por"]
        base = {k: d[k] for k in ("schema_version", "oferta_id", "gate", "nivel", "hash_objetivo", "creado_en", "vigencia_hasta")}
        base.update({"object_ids": sorted(d["object_ids"]), "aprobador": ap["id"], "tipo_aprobador": ap["tipo"], "fecha": ap["fecha"]})
        base.update({k: d[k] for k in ("etapa", "accion") if k in d})
        return base
    if nombre in ("sello", "orden_firmada", "catalogo"):   # catalogo (CT-3 B-01): igual que landing.catalogo, que firma el cuerpo sin `firma`
        return {k: v for k, v in d.items() if k != "firma"}
    raise KeyError(f"{nombre} no tiene payload de firma")


def firmar_hmac_de_prueba(nombre: str, d: dict, clave: bytes = None) -> str:  # type: ignore[assignment]
    """Firma HMAC de PRUEBA (solo ofertas/_ejemplo y tests); la firma real es Ed25519 en el equipo del dueño."""
    return firma_hmac(payload_firma(nombre, d), clave or CLAVE_DE_PRUEBA)


def _verifica(verificador: Callable[[bytes, str], bool], datos: bytes, firma: str) -> bool:
    """Aplica el hook de verificación; cualquier excepción cuenta como «no verifica» (fail-closed)."""
    try:
        return bool(verificador(datos, firma))
    except Exception:  # noqa: BLE001 - un verificador roto nunca aprueba
        return False


def problemas_firma(firma: Any, payload: dict | None, clave: bytes | None, *, entorno: str | None = None, obligatoria: bool = True,
                    verificador: Callable[[bytes, str], bool] | None = None) -> list[tuple[str, str]]:
    """Problemas de una firma: formato, Ed25519 obligatoria en producción y verificación.

    HMAC: se verifica si hay ``clave``. Ed25519: con ``verificador(json_canonico(payload), firma)`` (hook que inyecta
    ``engine.guard`` con la clave PÚBLICA; este módulo no importa ``engine``) se verifica; SIN verificador, en producción
    es ``X40_FIRMA`` (fail-closed: una cadena con forma de SSHSIG no es una aprobación) y fuera de producción solo se
    exige el formato (CT1-04/05).
    """
    if firma is None:
        return [("X40_FIRMA", "firma ausente")] if obligatoria else []
    t = tipo_firma(firma)
    if t is None:
        return [("X40_FIRMA", "firma mal formada (ed25519:<base64> o hmac-sha256:<64 hex>)")]
    if _en_produccion(entorno) and t != "ed25519":
        return [("X40_FIRMA", "en producción la firma humana, el sello y la orden son Ed25519; HMAC solo para pruebas y servicio a servicio")]
    if t == "hmac" and clave is not None and payload is not None and not comparar_hash(firma, firma_hmac(payload, clave)):
        return [("X40_FIRMA", "la firma HMAC no verifica contra su contenido")]
    if t == "ed25519":
        if verificador is not None:
            if payload is None or not _verifica(verificador, json_canonico(payload), firma):
                return [("X40_FIRMA", "la firma Ed25519 no verifica con la clave pública contra su contenido")]
        elif _en_produccion(entorno):
            return [("X40_FIRMA", "firma Ed25519 no verificable: falta el verificador con la clave pública (fail-closed en producción)")]
    return []


def decision_id_esperado(oferta_id: str, objeto_id: str, lectura_ts: str) -> str:
    """``decision_id`` = hash canónico de (oferta, objeto, lectura): repetir la lectura no duplica la acción (docs/06 N13)."""
    return hash_objeto({"oferta_id": oferta_id, "objeto_id": objeto_id, "lectura_ts": lectura_ts})


def tipo_cambio_id_esperado(par: str, fecha: str) -> str:
    """``TC-<BASE><COTIZADA>-<AAAAMMDD>`` para un par ``BASE/COTIZADA`` y una fecha ``AAAA-MM-DD``."""
    return "TC-" + par.replace("/", "") + "-" + fecha.replace("-", "")


def _t(s: str) -> _dt.datetime:
    return _dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)


def _param_valor(parametros: dict | None, grupo: str, clave: str) -> Any:
    try:
        return parametros["grupos"][grupo][clave]["valor"]  # type: ignore[index]
    except (TypeError, KeyError):
        return None


def hash_contenido_tipo_cambio(tc: dict) -> str:
    """``tipo_cambio.hash_contenido`` = ``hash_objeto({par, fecha, tasa, fuente, obtenido_en})`` (CT1-33)."""
    return hash_objeto({k: tc[k] for k in ("par", "fecha", "tasa", "fuente", "obtenido_en")})


def _d(s: str) -> _dt.date:
    """Fecha ``AAAA-MM-DD`` real (lanza ``ValueError`` con ``2026-02-31``)."""
    return _dt.date.fromisoformat(s)


# Exponente ISO 4217 (unidad menor = 10^-e) de las monedas operables. Fuente: lista oficial SIX/ISO 4217 (list-one.xml,
# publicada 2026-09-17, leída 2026-11-06): https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml
# Moneda fuera de la tabla = error (fail-closed): se agrega aquí con su exponente verificado, nunca por inferencia.
EXPONENTE_ISO4217 = {**{m: 2 for m in (
    "EUR", "USD", "GBP", "CAD", "AUD", "MXN", "BRL", "COP", "CHF", "SEK", "NOK", "DKK", "PLN", "CZK", "NZD", "SGD", "HUF", "IDR", "TWD", "CRC",
    "AED", "ARS", "HKD", "INR", "MYR", "NGN", "PEN", "PHP", "RON", "TRY", "ZAR")},
    **{m: 0 for m in ("CLP", "JPY", "KRW", "ISK", "PYG", "VND")}}
SENTIDO_DE_TIPO = {"pedido": {"entrada"}, "gasto": {"salida"}, "reembolso": {"salida"}, "disputa": {"salida"}, "comision": {"salida"},
                   "impuesto": {"salida"}, "costo": {"salida"}, "ajuste": {"entrada", "salida"}}


def problemas_artefacto(nombre: str, d: dict, *, clave: bytes | None = None, entorno: str | None = None, gates: dict | None = None,
                        verificador: Callable[[bytes, str], bool] | None = None, nivel_exigido: str | None = None,
                        parametros: dict | None = None) -> list[tuple[str, str]]:
    """Coherencia INTERNA de un artefacto nuevo (sin mirar otros archivos): lista de ``(código, mensaje)``.

    Un dato hostil NO lanza: fecha u hora inexistente => ``X47_TIEMPO`` (CT1-02). ``verificador``: hook de Ed25519 (ver
    :func:`problemas_firma`). ``nivel_exigido`` (solo ``aprobacion``): nivel EFECTIVO que fija quien conoce el estado de la oferta
    (:func:`nivel_efectivo`); una aprobación nunca decide por sí sola su propio nivel (CT1-27).
    """
    try:
        return _problemas_artefacto(nombre, d, clave=clave, entorno=entorno, gates=gates, verificador=verificador, nivel_exigido=nivel_exigido, parametros=parametros)
    except ValueError as exc:
        return [("X47_TIEMPO", f"fecha u hora inexistente: {exc}")]


def _problemas_artefacto(nombre: str, d: dict, *, clave: bytes | None, entorno: str | None, gates: dict | None,
                         verificador: Callable[[bytes, str], bool] | None, nivel_exigido: str | None, parametros: dict | None) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if nombre == "aprobacion":
        ap = d["aprobado_por"]
        if _t(d["vigencia_hasta"]) <= _t(d["creado_en"]):
            out.append(("X40_VIGENCIA", "vigencia_hasta debe ser posterior a creado_en"))
        gates = gates or cargar_gates()
        k = f"etapa:{d['etapa']}" if "etapa" in d else f"accion:{d.get('accion')}"
        esp_ef = None
        if nivel_exigido is not None:
            if NIVELES.index(d["nivel"]) > NIVELES.index(nivel_exigido):
                out.append(("X40_NIVEL", f"nivel declarado {d['nivel']} supera el nivel efectivo {nivel_exigido} (mínimo de oferta, etapa y autonomia.yaml)"))
            if k in gates["entradas"]:
                esp_ef = gate_esperado(k, nivel_exigido, gates)
        if d["gate"] == "H" or ap.get("firma") is not None or esp_ef == "H":
            out += problemas_firma(ap.get("firma"), payload_firma("aprobacion", d), clave, entorno=entorno, verificador=verificador)
        if esp_ef == "H":
            if d["gate"] != "H":
                out.append(("X40_GATE", f"gate {d['gate']} pero la tabla exige H para {k} con el nivel efectivo {nivel_exigido}"))
            if ap["tipo"] != "humano":
                out.append(("X40_FIRMA", f"gate H efectivo ({k} en {nivel_exigido}) exige aprobación humana firmada, no {ap['tipo']}"))
        if k not in gates["entradas"]:
            out.append(("X40_ACCION", f"{k} no existe en contratos/gates.json"))
        else:
            esp = gate_esperado(k, d["nivel"], gates)
            if esp == "NA":
                out.append(("X40_GATE", f"{k} no está permitida en {d['nivel']}"))
            elif d["gate"] != esp:
                out.append(("X40_GATE", f"gate {d['gate']} != tabla de gates ({esp}) para {k} en {d['nivel']}"))
        if d.get("accion") == "activar_campana" and not d["object_ids"]:
            out.append(("X40_OBJETOS", "activar_campana exige los object_ids exactos aprobados"))
    elif nombre == "preflight":
        estados = [v["estado"] for v in d["checks"].values()]
        peor = "ROJO" if "ROJO" in estados else ("AMARILLO" if "AMARILLO" in estados else "VERDE")
        if d["semaforo"] != peor:
            out.append(("X41_PREFLIGHT", f"semaforo {d['semaforo']} != peor de los checks ({peor})"))
        if _t(d["valido_hasta"]) <= _t(d["generado_en"]):
            out.append(("X41_PREFLIGHT", "valido_hasta debe ser posterior a generado_en"))
    elif nombre == "sello":
        if _t(d["vigencia_hasta"]) <= _t(d["emitido_en"]):
            out.append(("X40_VIGENCIA", "vigencia_hasta debe ser posterior a emitido_en"))
        if d["object_ids"] and d["etapa_objetivo"] != "D7":
            out.append(("X40_OBJETOS", "solo el sello de D7 lleva object_ids"))
        if d["etapa_objetivo"] == "D7" and not d["object_ids"]:
            out.append(("X40_OBJETOS", "el sello de D7 debe llevar los object_ids exactos"))
        if not re.fullmatch(rf"qa/x1-{d['etapa_objetivo'].lower()}-v[1-9][0-9]*\.json", d["dictamen_ref"]):
            out.append(("X40_DICTAMEN", f"dictamen_ref debe ser el dictamen de X1 de la etapa objetivo (qa/x1-{d['etapa_objetivo'].lower()}-v<n>.json)"))
        out += problemas_firma(d["firma"], payload_firma("sello", d), clave, entorno=entorno, verificador=verificador)
    elif nombre == "orden_firmada":
        gates = gates or cargar_gates()
        if d["accion"] != "aprobar_etapa" and f"accion:{d['accion']}" not in gates["entradas"]:
            out.append(("X40_ACCION", f"accion {d['accion']} no existe en contratos/gates.json (ni es aprobar_etapa)"))
        if d["accion"] == "activar_campana" and not d.get("object_ids"):
            out.append(("X40_OBJETOS", "activar_campana exige los object_ids"))
        if d.get("object_ids") and d["accion"] != "activar_campana":
            out.append(("X40_OBJETOS", "object_ids solo para activar_campana"))
        out += problemas_firma(d["firma"], payload_firma("orden_firmada", d), clave, entorno=entorno, verificador=verificador)
    elif nombre == "decision":
        if d["decision_id"] != decision_id_esperado(d["oferta_id"], d["objeto_id"], d["lectura_ts"]):
            out.append(("X43_DECISION", "decision_id no es hash(oferta_id, objeto_id, lectura_ts)"))
        if _t(d["ts"]) < _t(d["lectura_ts"]):
            out.append(("X43_DECISION", "ts anterior a lectura_ts"))
        if d["objeto_tipo"] == "oferta" and d["objeto_id"] != d["oferta_id"]:
            out.append(("X43_DECISION", "objeto_tipo oferta exige objeto_id = oferta_id"))
        if d["accion"] in ("BLOQUEADO", "SEGUIR") and d["ejecutada"]:
            out.append(("X43_DECISION", f"{d['accion']} no tiene acción que ejecutar: ejecutada debe ser false"))
        g = gates or cargar_gates()
        clave_gate = "accion:pausar" if d["accion"] == "MATAR" else ("etapa:D8" if d["accion"] in ("BLOQUEADO", "SEGUIR", "INCONCLUSO") else None)
        if clave_gate:
            esp = gate_esperado(clave_gate, d["nivel"], g)
            if d["gate"] != esp:
                out.append(("X43_GATE", f"gate {d['gate']} != tabla de gates ({esp}) para {clave_gate} en {d['nivel']}"))
            elif d["accion"] == "MATAR" and esp == "H" and d["ejecutada"]:
                out.append(("X43_GATE", f"MATAR ejecutada con gate H en {d['nivel']}: pausar exige aprobación humana"))
    elif nombre == "conciliacion":
        for k in ("stripe_vs_ledger", "gasto_meta_vs_ledger"):
            c = d[k]
            if not (c["izquierda"]["moneda"] == c["derecha"]["moneda"] == c["diferencia"]["moneda"] == d["moneda"]):
                out.append(("X44_CONCILIACION", f"{k}: monedas distintas de {d['moneda']}"))
            elif c["diferencia"]["monto"] != c["izquierda"]["monto"] - c["derecha"]["monto"]:
                out.append(("X44_CONCILIACION", f"{k}: diferencia != izquierda - derecha"))
        cuadra = all(d[k]["diferencia"]["monto"] == 0 for k in ("stripe_vs_ledger", "gasto_meta_vs_ledger"))
        if d["estado"] == "CONCILIADO" and not cuadra:
            out.append(("X44_CONCILIACION", "estado CONCILIADO exige diferencias 0"))
        if d["estado"] == "DESCUADRE" and cuadra:
            out.append(("X44_CONCILIACION", "estado DESCUADRE con todas las diferencias en 0: sería CONCILIADO"))
        if d["cifras_tachadas"] == (d["estado"] == "CONCILIADO"):
            out.append(("X44_CONCILIACION", "cifras_tachadas debe ser verdadero si y solo si estado != CONCILIADO"))
        if _d(d["periodo"]["desde"]) > _d(d["periodo"]["hasta"]):
            out.append(("X44_CONCILIACION", "periodo.desde posterior a periodo.hasta"))
        minimo_bp = 1  # sin parámetros: al menos algo de cobertura; con parametros, testeo.cobertura_adid_min_pct (B0-15)
        pm = _param_valor(parametros, "testeo", "cobertura_adid_min_pct")
        if pm is not None:
            minimo_bp = max(1, int(dec(pm) * 100))
        if d["estado"] == "CONCILIADO" and d["cobertura_adid_bp"] < minimo_bp:
            out.append(("X44_CONCILIACION", f"CONCILIADO con cobertura_adid_bp {d['cobertura_adid_bp']} < {minimo_bp} (testeo.cobertura_adid_min_pct; B0-15)"))
        cm = d["compras"]
        if cm["stripe"] == 0 and cm["razon_meta_stripe"] is not None:
            out.append(("X44_CONCILIACION", "razon_meta_stripe debe ser null cuando compras.stripe es 0"))
        elif cm["stripe"] > 0:
            esperada = str((Decimal(cm["meta"]) / Decimal(cm["stripe"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))
            if cm["razon_meta_stripe"] != esperada:
                out.append(("X44_CONCILIACION", f"razon_meta_stripe {cm['razon_meta_stripe']} != meta/stripe = {esperada} (2 decimales, half-even)"))
    elif nombre == "tipo_cambio":
        base, cot = d["par"].split("/")
        if base == cot:
            out.append(("X45_TIPO_CAMBIO", "par con la misma moneda en ambos lados"))
        if d["tipo_cambio_id"] != tipo_cambio_id_esperado(d["par"], d["fecha"]):
            out.append(("X45_TIPO_CAMBIO", f"tipo_cambio_id != {tipo_cambio_id_esperado(d['par'], d['fecha'])}"))
        if dec(d["tasa"]) <= 0:
            out.append(("X45_TIPO_CAMBIO", "tasa debe ser > 0"))
        if _t(d["obtenido_en"]).date() < _d(d["fecha"]):
            out.append(("X45_TIPO_CAMBIO", "obtenido_en anterior a la fecha de la tasa"))
        if d["hash_contenido"] != hash_contenido_tipo_cambio(d):
            out.append(("X45_TIPO_CAMBIO", "hash_contenido != hash_objeto({par, fecha, tasa, fuente, obtenido_en})"))
    elif nombre == "traspaso":
        if d["gasto"]["real"]["moneda"] != d["gasto"]["esperado"]["moneda"]:
            out.append(("X42_TRASPASO", "gasto real y esperado en monedas distintas"))
        if d["rechazos_7d"] < sum(1 for a in d["anuncios"] if a["rechazado"]):
            out.append(("X42_TRASPASO", "rechazos_7d menor que los anuncios rechazados de esta lectura"))
        if len({a["ad_id"] for a in d["anuncios"]}) != len(d["anuncios"]):
            out.append(("X42_TRASPASO", "ad_id repetido"))
        if d["lanzamiento_estable"] and (d["campana"]["effective_status"] != "ACTIVE" or any(a["rechazado"] for a in d["anuncios"])):
            out.append(("X42_TRASPASO", "lanzamiento_estable exige campaña ACTIVE y ningún anuncio rechazado"))
        for a in d["anuncios"]:
            if a["rechazado"] != (a["effective_status"] == "DISAPPROVED"):
                out.append(("X42_TRASPASO", f"anuncio {a['ad_id']}: rechazado={a['rechazado']} contradice effective_status={a['effective_status']}"))
        if d["lanzamiento_estable"] and not any(a["effective_status"] == "ACTIVE" for a in d["anuncios"]):
            out.append(("X42_TRASPASO", "lanzamiento_estable sin ningún anuncio ACTIVE"))
    elif nombre == "ids_meta":
        todos = [d["campaign_id"], *d["adset_ids"], *d["ad_ids"], *d["creative_ids"]]
        if len(todos) != len(set(todos)):
            out.append(("X41_IDS", "un mismo id de Meta aparece como campaña, conjunto, anuncio o creativo a la vez"))
    elif nombre == "catalogo":
        ids = d["ids_meta"]
        todos = [i for i in (ids["campaign_id"], *ids["adset_ids"], *ids["ad_ids"]) if i is not None]
        if len(todos) != len(set(todos)):
            out.append(("X48_CATALOGO", "un mismo id de Meta aparece como campaña, conjunto o anuncio a la vez"))
        if d["price_ids"].get("bump") == d["price_ids"]["principal"]:
            out.append(("X48_CATALOGO", "el price_id del bump es el del producto principal"))
        if tipo_firma(d["firma"]) == "ed25519" and verificador is None and _en_produccion(entorno):
            out.append(("X40_FIRMA", "firma Ed25519 del catálogo no verificable: falta el verificador con la clave pública (fail-closed en producción)"))
        else:   # entorno="servicio": el catálogo es servicio a servicio, la HMAC (CATALOGO_HMAC) vale también en producción
            out += problemas_firma(d["firma"], payload_firma("catalogo", d), clave, entorno="servicio", verificador=verificador)
    elif nombre == "alertas":
        if not d["regla_id"].startswith(d["origen"] + "-"):
            out.append(("X49_ALERTAS", f"regla_id {d['regla_id']} no corresponde al origen {d['origen']} (prefijo {d['origen']}-)"))
        v, u = d["valor"], d["umbral"]
        if isinstance(v, dict) and isinstance(u, dict) and v["moneda"] != u["moneda"]:
            out.append(("X49_ALERTAS", "valor y umbral en monedas distintas"))
        elif v is not None and u is not None and isinstance(v, dict) != isinstance(u, dict):
            out.append(("X49_ALERTAS", "valor y umbral de tipos incomparables (dinero frente a número)"))
    elif nombre == "postmortem":
        r = d["retraso_clic_compra"]
        if r["p90_h"] is not None and r["mediana_h"] is not None and r["p90_h"] < r["mediana_h"]:
            out.append(("X46_POSTMORTEM", "p90_h menor que mediana_h"))
        if d["causa_principal"] not in {x["codigo"] for x in d["causas"]}:
            out.append(("X46_POSTMORTEM", "causa_principal no figura en causas[]"))
    return out


def problemas_ledger(lineas: list[dict], tipos_cambio: list[dict] | None = None) -> list[tuple[str, str]]:
    """Coherencia del ledger: clave natural única y con el prefijo de su fuente; sentido acorde al tipo; ``fecha`` = día de ``ts``;
    ``importe_base`` solo con un tipo de cambio registrado que corresponda al par y a la aritmética (CT1-19/20/21). No lanza."""
    try:
        return _problemas_ledger(lineas, tipos_cambio)
    except ValueError as exc:
        return [("X47_TIEMPO", f"fecha u hora inexistente: {exc}")]


def convertir_importe(monto: int, moneda_origen: str, moneda_base: str, tasa: str) -> int:
    """``monto`` (unidad menor de ``moneda_origen``) x ``tasa`` (BASE/COTIZADA) a la unidad menor de ``moneda_base``, half-even, sin float.

    ``tasa`` es unidades de ``moneda_base`` por una de ``moneda_origen``. Moneda fuera de :data:`EXPONENTE_ISO4217` = ``KeyError`` (fail-closed).
    """
    from fractions import Fraction
    eo, eb = EXPONENTE_ISO4217[moneda_origen], EXPONENTE_ISO4217[moneda_base]
    f = Fraction(monto) * Fraction(dec(tasa)) * Fraction(10) ** eb / Fraction(10) ** eo
    return entero_redondeado(f.numerator, f.denominator, "half_even")


def _problemas_ledger(lineas: list[dict], tipos_cambio: list[dict] | None) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    vistos: set[str] = set()
    por_id = {t["tipo_cambio_id"]: t for t in tipos_cambio} if tipos_cambio is not None else None
    for k, l in enumerate(lineas):
        if l["clave_natural"] in vistos:
            out.append(("X44_LEDGER", f"[{k}] clave_natural repetida: el ledger es upsert, no append de duplicados"))
        vistos.add(l["clave_natural"])
        if not l["clave_natural"].startswith(l["fuente"] + ":"):
            out.append(("X44_LEDGER", f"[{k}] clave_natural no empieza por la fuente {l['fuente']}:"))
        if l["sentido"] not in SENTIDO_DE_TIPO[l["tipo"]]:
            out.append(("X44_LEDGER", f"[{k}] tipo {l['tipo']} no admite sentido {l['sentido']}"))
        _d(l["fecha"])
        if l["fecha"] != _t(l["ts"]).date().isoformat():
            out.append(("X44_LEDGER", f"[{k}] fecha {l['fecha']} != día UTC de ts {l['ts']}"))
        if "importe_base" in l and l["importe_base"]["moneda"] == l["importe"]["moneda"]:
            out.append(("X44_LEDGER", f"[{k}] importe_base en la misma moneda que el importe: no hay conversión"))
        if por_id is None or "tipo_cambio_id" not in l:
            continue
        tc = por_id.get(l["tipo_cambio_id"])
        if tc is None:
            out.append(("X44_LEDGER", f"[{k}] tipo_cambio_id {l['tipo_cambio_id']} no está registrado"))
            continue
        if "importe_base" not in l:
            continue
        mo, mb = l["importe"]["moneda"], l["importe_base"]["moneda"]
        if mo == mb:
            continue
        if tc["par"] != f"{mo}/{mb}":
            out.append(("X44_LEDGER", f"[{k}] tipo de cambio {tc['par']} no corresponde a la conversión {mo}->{mb}"))
        elif tc["fecha"] > l["fecha"]:
            out.append(("X44_LEDGER", f"[{k}] tipo de cambio de {tc['fecha']} posterior a la fecha {l['fecha']} del hecho"))
        else:
            try:
                esp = convertir_importe(l["importe"]["monto"], mo, mb, tc["tasa"])
            except KeyError as exc:
                out.append(("X44_LEDGER", f"[{k}] moneda {exc} sin exponente ISO 4217 registrado: no se convierte (fail-closed)"))
            else:
                if l["importe_base"]["monto"] != esp:
                    out.append(("X44_LEDGER", f"[{k}] importe_base {l['importe_base']['monto']} != importe x tasa = {esp}"))
    return out


def problemas_alertas(lineas: list[dict]) -> list[tuple[str, str]]:
    """Coherencia de un ``alertas.jsonl`` completo: una línea = el estado vigente de una alerta, así que el ``id`` no se repite."""
    out: list[tuple[str, str]] = []
    vistos: set[str] = set()
    for k, a in enumerate(lineas):
        if a["id"] in vistos:
            out.append(("X49_ALERTAS", f"línea {k}: id {a['id']} repetido (una alerta = regla x objeto x ventana, deduplicada)"))
        vistos.add(a["id"])
    return out


def problemas_ordenes(lineas: list[dict]) -> list[tuple[str, str]]:
    """Export de órdenes firmadas: un ``nonce`` se consume UNA vez, comparado sin mayúsculas (APFS/NTFS) (CT1-09)."""
    out: list[tuple[str, str]] = []
    vistos: set[str] = set()
    for k, o in enumerate(lineas):
        n = o["nonce"].casefold()
        if n in vistos:
            out.append(("X40_NONCE", f"[{k}] nonce repetido (sin distinguir mayúsculas): una orden firmada se consume una sola vez"))
        vistos.add(n)
    return out


def problemas_uso_sello(sello: dict, *, artefacto_sha256: str, object_ids: Iterable[str] = (), ahora: _dt.datetime,
                        tolerancia_s: int = 120) -> list[tuple[str, str]]:
    """Comprobación JUSTO ANTES de usar un sello (TOCTOU, CT1-07): re-hash del artefacto, vigencia y objetos exactos.

    Pura: la llaman ``meta.activar`` y ``landing.desplegar`` con el hash recalculado en ese instante. ``ahora`` es UTC con tzinfo.
    """
    out: list[tuple[str, str]] = []
    if not comparar_hash(sello["artefacto_sha256"], artefacto_sha256):
        out.append(("X40_SELLO", "el artefacto cambió después del sello (re-hash justo antes de usar)"))
    if ahora > _t(sello["vigencia_hasta"]):
        out.append(("X40_VIGENCIA", "sello vencido"))
    if ahora < _t(sello["emitido_en"]) - _dt.timedelta(seconds=tolerancia_s):
        out.append(("X40_VIGENCIA", "sello con emitido_en en el futuro"))
    if set(sello["object_ids"]) != set(object_ids):
        out.append(("X40_OBJETOS", "object_ids del sello distintos de los que se van a activar (igualdad exacta)"))
    return out


# --- parámetros opcionales de la 1.1.0 --------------------------------------------------------
DUPLICADAS_HEREDADAS = frozenset({"umbral_qa", "umbral_pass_qa"})  # ya repetidas en la plantilla 1.0.0 (departamentos distintos); hallazgo abierto
OPERACION_PARAMETROS: dict[str, list[str]] = {
    "decidir_d8": ["estadistica." + k for k in (
        "prior_conv_fuerza_clics", "prior_cpc_fuerza_clics", "alfa_descarte", "k_min_matar", "k_min_fallida", "nodos_cpc", "dias_con_compras_min", "dias_madurez_compra")],
    "runner_vivo": ["agentes." + k for k in (
        "claude_version_min", "modelo", "esfuerzo", "tiempo_s_max", "turnos_max", "holgura_pct", "reintentos_transitorios_max", "backoff_base_s",
        "reintentos_validacion_max", "gracia_s", "pausa_poll_s", "bucle_repeticion_max", "bucle_sin_progreso_turnos", "estado_max_edad_h",
        "bash_timeout_defecto_ms", "bash_timeout_max_ms", "hook_timeout_s")],
    "ingesta": ["ingesta.tolerancia_seg", "ingesta.cuerpo_max_bytes"],
    "watchdog": ["watchdog.latido_cada_min", "watchdog.latido_max_min", "watchdog.ciclo_max_min"],
    "crear_sesion": ["landing.max_sesiones_por_visitante", "ingesta.cuerpo_max_bytes"],
    "preparar_campana": ["campana.spend_cap_minimo_meta", "campana.spend_cap_factor"],
}


def claves_de_parametros() -> dict[str, set[str]]:
    """``{grupo: {claves}}`` que admite ``parametros.schema.json`` (incluye los grupos opcionales aunque la plantilla no los traiga)."""
    grupos = _esquemas()[1]["parametros"]["properties"]["grupos"]["properties"]
    return {g: set(d["properties"]) for g, d in grupos.items()}


def parametros_faltantes(parametros: dict | None, requeridos: Iterable[str]) -> list[str]:
    """Claves ``grupo.clave`` requeridas que faltan o valen ``null`` (grupo ausente incluido): el motor las traduce a ``ParametroFaltante`` (exit 5)."""
    grupos = (parametros or {}).get("grupos") or {}
    falta = []
    for k in requeridos:
        g, _, c = k.partition(".")
        v = (grupos.get(g) or {}).get(c)
        if not isinstance(v, dict) or v.get("valor") is None:
            falta.append(k)
    return falta


def claves_duplicadas(parametros: dict) -> dict[str, list[str]]:
    """Claves que aparecen en más de un grupo, salvo las heredadas de la plantilla 1.0.0 (``DUPLICADAS_HEREDADAS``)."""
    donde: dict[str, list[str]] = {}
    for g, claves in ((parametros or {}).get("grupos") or {}).items():
        for k in claves:
            donde.setdefault(k, []).append(g)
    return {k: gs for k, gs in donde.items() if len(gs) > 1 and k not in DUPLICADAS_HEREDADAS}


def coherencia_parametros(parametros: dict) -> list[str]:
    """Incoherencias entre parámetros (los grupos opcionales solo se miran si están presentes)."""
    err: list[str] = []
    for k, gs in claves_duplicadas(parametros).items():
        err.append(f"clave {k} repetida en los grupos {gs}: cada clave tiene UN solo hogar")
    gr = parametros.get("grupos") or {}

    def v(g: str, k: str) -> Any:
        x = (gr.get(g) or {}).get(k)
        return x.get("valor") if isinstance(x, dict) else None

    est = gr.get("estadistica")
    if est:
        def en(k: str, lo: str, hi: str, incl_hi: bool = False) -> None:
            x = v("estadistica", k)
            if x is None:
                return
            try:
                d = dec(x)
            except (ValueError, ArithmeticError):
                err.append(f"estadistica.{k}: ilegible")
                return
            if not (dec(lo) < d < dec(hi) or (incl_hi and d == dec(hi))):
                err.append(f"estadistica.{k}={x} fuera de ({lo}, {hi})")
        en("alfa_descarte", "0", "0.5"); en("mercados_alfa", "0", "0.5"); en("potencia", "0.5", "1"); en("confianza_precision", "0.5", "1")
        en("mercados_p_diferencia", "0.5", "1"); en("control_fraccion", "0", "1"); en("control_fraccion_presupuesto", "0", "1")
        en("meta_fraccion_min_purchase", "0", "1", True); en("precision_relativa", "0", "1")
        a, b = v("estadistica", "k_min_matar"), v("estadistica", "k_min_fallida")
        if a is not None and dec(a) <= 0:
            err.append("estadistica.k_min_matar debe ser > 0")
        if a is not None and b is not None and dec(b) < dec(a):
            err.append("estadistica.k_min_fallida < k_min_matar")
        dm, dmin = v("estadistica", "dias_madurez_compra"), v("veredicto", "dias_min")
        if dm is not None and dmin is not None and dm >= dmin:
            err.append(f"estadistica.dias_madurez_compra ({dm}) >= veredicto.dias_min ({dmin}): no quedaría evidencia")
    ag = gr.get("agentes")
    if ag:
        edad, vig = v("agentes", "estado_max_edad_h"), v("infra", "hc_preflight_vigencia_horas")
        if edad is not None and edad > min(vig if vig is not None else 6, 6):
            err.append("agentes.estado_max_edad_h > min(infra.hc_preflight_vigencia_horas, 6) (D-17)")
        d_, m_ = v("agentes", "bash_timeout_defecto_ms"), v("agentes", "bash_timeout_max_ms")
        if d_ is not None and m_ is not None and d_ > m_:
            err.append("agentes.bash_timeout_defecto_ms > bash_timeout_max_ms")
    wd = gr.get("watchdog")
    if wd:
        cada, mx, ciclo = v("watchdog", "latido_cada_min"), v("watchdog", "latido_max_min"), v("watchdog", "ciclo_max_min")
        if cada is not None and mx is not None and mx <= cada:
            err.append("watchdog.latido_max_min debe ser mayor que latido_cada_min")
        lect = v("optimizacion", "lectura_horas")
        if ciclo is not None and lect is not None and ciclo <= lect * 60:
            err.append("watchdog.ciclo_max_min debe superar optimizacion.lectura_horas x 60: pausaría entre ciclos sanos")
    return err


# --- reglas cruzadas nuevas -------------------------------------------------------------------
def _regla_spend_cap(c: "Contexto", camp: dict, calculado: int | None) -> None:
    """X10_SPEND_CAP: ``spend_cap`` nulo solo con candado alternativo y porque el calculado queda bajo el mínimo de Meta."""
    inf, p, ruta = c.informe, camp["presupuesto"], "07-campana/campana.json"
    cap, minimo, cand = p["spend_cap"], p["spend_cap_minimo_meta"], p["candado_alternativo"]
    if (cap is None) != (cand is not None):
        inf.error("X10_SPEND_CAP", ruta, "spend_cap null <=> candado_alternativo presente")
    par_min = c.param("campana", "spend_cap_minimo_meta")
    if isinstance(par_min, dict) and par_min.get("moneda") == p["moneda"] and minimo is not None and minimo != par_min["monto"]:
        inf.error("X10_SPEND_CAP", ruta, f"spend_cap_minimo_meta {minimo} != parametros.campana.spend_cap_minimo_meta {par_min['monto']}")
    if minimo is None:
        if camp["estado"] == "borrador":
            inf.aviso("X10_SPEND_CAP", ruta, "borrador sin spend_cap_minimo_meta convertido (tipo_cambio registrado): P20 del preflight lo exige [VERIFICAR]")
        else:
            inf.error("X10_SPEND_CAP", ruta, f"estado {camp['estado']} sin spend_cap_minimo_meta: no se puede comprobar el mínimo de Meta")
    else:
        if cap is not None and cap < minimo:
            inf.error("X10_SPEND_CAP", ruta, f"spend_cap {cap} < mínimo de Meta {minimo}: Meta lo rechaza; usar candado_alternativo")
        if cap is None and calculado is not None and calculado >= minimo:
            inf.error("X10_SPEND_CAP", ruta, "candado_alternativo innecesario: el spend_cap calculado alcanza el mínimo de Meta")
    if cand:
        lb = cand["lifetime_budget"]
        if lb < p["total_test"]:
            inf.error("X10_SPEND_CAP", ruta, "lifetime_budget del candado < total_test: cortaría el test antes de tiempo")
        if calculado is not None and lb > calculado:
            inf.error("X10_SPEND_CAP", ruta, f"lifetime_budget {lb} > {calculado} (factor x total_test): el candado no acota la pérdida")


def regla_brief(c: Contexto) -> None:
    """X10_BRIEF / X10_MONEDA: techos del brief coherentes con limites, economía, oferta y mercado (plan <= techo)."""
    inf = c.informe
    brief = c.get("00-brief.yaml")
    if not brief:
        return
    bp, lim = brief["presupuesto"], c.limites
    monedas = {bp[k]["moneda"] for k in ("test_total_max", "test_diario_max", "ia_max")}
    if len(monedas) != 1:
        inf.error("X10_MONEDA", "00-brief.yaml", f"presupuesto en monedas distintas: {sorted(monedas)}")
    mon = bp["test_total_max"]["moneda"]
    if bp["test_diario_max"]["monto"] > bp["test_total_max"]["monto"]:
        inf.error("X10_BRIEF", "00-brief.yaml", "test_diario_max > test_total_max")
    if lim and lim.get("moneda_limites") is not None:
        if lim["moneda_limites"] != mon:
            inf.error("X10_MONEDA", "00-brief.yaml", f"moneda del brief {mon} != moneda_limites {lim['moneda_limites']} (requiere tipo de cambio registrado)")
        else:
            for k, kl in (("test_total_max", "gasto_total_test_por_oferta"), ("test_diario_max", "gasto_diario_por_oferta")):
                if lim.get(kl) is not None and bp[k]["monto"] > lim[kl]:
                    inf.error("X10_BRIEF", "00-brief.yaml", f"{k} {bp[k]['monto']} supera limites.{kl} {lim[kl]} (el brief solo restringe)")
    eco, camp, est, of, merc = (c.get("03-oferta/economia.json"), c.get("07-campana/campana.json"), c.get("estado.json"),
                                c.get("03-oferta/oferta.json"), c.get("mercado.json"))
    if eco:
        if eco["gasto_test_plan"]["moneda"] != mon:
            inf.error("X10_MONEDA", "03-oferta/economia.json", f"gasto_test_plan en {eco['gasto_test_plan']['moneda']} y el techo del brief en {mon}")
        elif eco["gasto_test_plan"]["monto"] > bp["test_total_max"]["monto"]:
            inf.error("X10_BRIEF", "03-oferta/economia.json", "gasto_test_plan supera brief.presupuesto.test_total_max (plan <= techo)")
    if camp and camp["presupuesto"]["moneda"] != mon:
        inf.error("X10_MONEDA", "07-campana/campana.json", f"moneda {camp['presupuesto']['moneda']} != moneda del brief {mon}")
    if est and est["costo_ia"]["moneda"] == bp["ia_max"]["moneda"] and est["costo_ia"]["monto"] > bp["ia_max"]["monto"]:
        inf.error("X10_BRIEF", "estado.json", "costo_ia supera brief.presupuesto.ia_max")
    mo, pr = brief["mercado_objetivo"], brief["precio_rango"]
    if pr["min"]["moneda"] != mo["moneda_cobro"] or pr["max"]["moneda"] != mo["moneda_cobro"]:
        inf.error("X10_MONEDA", "00-brief.yaml", "precio_rango en una moneda distinta de mercado_objetivo.moneda_cobro")
    if pr["min"]["monto"] > pr["max"]["monto"]:
        inf.error("X10_BRIEF", "00-brief.yaml", "precio_rango.min > max")
    if of and of["moneda"] == mo["moneda_cobro"] and not pr["min"]["monto"] <= of["precio"]["lista"]["monto"] <= pr["max"]["monto"]:
        inf.error("X10_BRIEF", "03-oferta/oferta.json", "precio de lista fuera de brief.precio_rango")
    if merc and (merc["locale"] != mo["locale"] or merc["moneda_cobro"] != mo["moneda_cobro"] or set(merc["paises_segmentacion"]) != set(mo["paises_segmentacion"])):
        inf.error("X30_MERCADO", "mercado.json", "locale, moneda_cobro o países distintos de brief.mercado_objetivo")
    inf.verificados += 1


def regla_mercado(c: Contexto) -> None:
    """X32: exposición fiscal firmada con régimen diferido (MA-06) y revisor nativo donde el idioma es obligación legal (C0.3)."""
    inf = c.informe
    merc = c.get("mercado.json")
    if not merc:
        return
    f, rl = merc["fiscal"], merc["revision_linguistica"]
    ex = f["exposicion_aceptada"]
    if f["regimen"] == "diferido":
        if ex is None:
            inf.error("X32_FISCAL", "mercado.json", "régimen diferido sin exposicion_aceptada firmada por el dueño: no se lanza ahí")
        else:
            if not set(merc["paises_segmentacion"]) <= set(ex["paises"]):
                inf.error("X32_FISCAL", "mercado.json", "exposicion_aceptada no cubre todos los paises_segmentacion")
            payload = {"oferta_id": merc["oferta_id"], "paises": ex["paises"], "aprobador": ex["firmada_por"]["id"], "fecha": ex["firmada_por"]["fecha"]}
            for cod, msg in problemas_firma(ex["firmada_por"].get("firma"), payload, c.clave_firma, verificador=c.verificador):
                inf.error("X32_FISCAL", "mercado.json", "exposicion_aceptada: " + msg)
    if rl["obligacion_legal_idioma"] and not rl["revisor_nativo"]:
        inf.error("X32_REVISOR", "mercado.json", "el idioma es obligación legal y no hay revisor nativo: X1 emite ROJO (nota 16 C0.3)")
    inf.verificados += 1


ETAPA_DE_ACCION = {"activar_campana": "D7", "publicar_landing": "D5", "aprobar_oferta": "D3", "elegir_candidato": "D1",
                   "reactivar_tras_pausa": "D8", "aumentar_presupuesto_d8": "D8", "subir_presupuesto_d9": "D9"}


def _nivel_exigido_aprobacion(ap: dict, est: dict, autonomia: dict | None) -> str:
    """Nivel EFECTIVO de una aprobación: el menor entre oferta, etapa y autonomia.yaml (CT1-27); nunca el que ella declara."""
    etapa = ap.get("etapa") or ETAPA_DE_ACCION.get(ap.get("accion", ""))
    try:
        return nivel_efectivo(etapa, est, autonomia) if etapa else est["nivel"]
    except KeyError:
        return est["nivel"]


def regla_artefactos_nuevos(c: Contexto) -> None:
    """X40-X46: aprobación, ids_meta, preflight, traspaso, post-mortem y decisiones frente a la campaña y el estado."""
    inf, camp = c.informe, c.get("07-campana/campana.json")
    est = c.get("estado.json")
    for nombre, rel in (("aprobacion", "07-campana/aprobacion.json"), ("preflight", "07-campana/preflight.json"),
                        ("traspaso", "07-campana/traspaso.json"), ("postmortem", "08-operacion/postmortem.json"),
                        ("ids_meta", "07-campana/ids_meta.json")):
        d = c.get(rel)
        if d:
            exigido = None
            if nombre == "aprobacion" and est:
                exigido = _nivel_exigido_aprobacion(d, est, c.autonomia)
            for cod, msg in problemas_artefacto(nombre, d, clave=c.clave_firma, gates=c.gates, verificador=c.verificador, nivel_exigido=exigido):
                inf.error(cod, rel, msg)
    ap0 = c.get("07-campana/aprobacion.json")
    if ap0 and c.clave_firma is None and tipo_firma(ap0["aprobado_por"].get("firma")) == "hmac":
        inf.aviso("X40_FIRMA", "07-campana/aprobacion.json", "firma HMAC sin clave (FABRICA_FIRMA_CLAVE): solo se comprobó el formato, no la firma")
    vig_ap = c.param("campana", "preflight_vigencia_h")
    if ap0 and vig_ap is not None and _t(ap0["vigencia_hasta"]) - _t(ap0["creado_en"]) > _dt.timedelta(hours=vig_ap):
        inf.error("X40_VIGENCIA", "07-campana/aprobacion.json", f"vigencia de la aprobación mayor que campana.preflight_vigencia_h ({vig_ap} h)")
    decs = c.get("08-operacion/decisiones.jsonl") or []
    for k, d in enumerate(decs):
        for cod, msg in problemas_artefacto("decision", d, gates=c.gates):
            inf.error(cod, f"08-operacion/decisiones.jsonl[{k}]", msg)
    vistos_dec: set[str] = set()
    for k, d in enumerate(decs):
        if d["decision_id"] in vistos_dec:
            inf.error("X43_DECISION", f"08-operacion/decisiones.jsonl[{k}]", "decision_id repetido: repetir la lectura no duplica la acción")
        vistos_dec.add(d["decision_id"])
        if d["oferta_id"] != c.dir.name and c.get("00-brief.yaml") and d["oferta_id"] != c.get("00-brief.yaml")["oferta_id"]:
            inf.error("X43_DECISION", f"08-operacion/decisiones.jsonl[{k}]", "oferta_id distinto del de la oferta")
    ids, ap, pf, tr, pm = (c.get("07-campana/ids_meta.json"), c.get("07-campana/aprobacion.json"), c.get("07-campana/preflight.json"),
                           c.get("07-campana/traspaso.json"), c.get("08-operacion/postmortem.json"))
    brief = c.get("00-brief.yaml")
    if ids:
        if brief and brief["cuenta_meta_id"] != ids["ad_account_id"]:
            inf.error("X41_IDS", "07-campana/ids_meta.json", "ad_account_id distinto de brief.cuenta_meta_id")
        if camp:
            if ids["hash_config"] != camp["hash_config"]:
                inf.error("X41_IDS", "07-campana/ids_meta.json", "hash_config distinto del de campana.json (deriva de configuración)")
            if len(ids["ad_ids"]) != len(camp["anuncios"]) or len(ids["creative_ids"]) != len(camp["anuncios"]):
                inf.error("X41_IDS", "07-campana/ids_meta.json", "ad_ids/creative_ids no coinciden con el número de anuncios de campana.json")
            cm = camp.get("ids_meta")
            if cm and (cm["campaign_id"] != ids["campaign_id"] or set(cm["adset_ids"]) != set(ids["adset_ids"]) or set(cm["ad_ids"]) != set(ids["ad_ids"])
                       or cm["ad_account_id"] != ids["ad_account_id"]):
                inf.error("X41_IDS", "07-campana/ids_meta.json", "difiere de campana.ids_meta: activar compara igualdad exacta")
            if camp["estado"] in ("activa", "pausada", "cerrada", "aprobada") and not cm:
                inf.error("X41_IDS", "07-campana/campana.json", "hay ids_meta.json pero campana.ids_meta es null")
    if ap and camp:
        if ap.get("accion") == "activar_campana":
            if ap["hash_objetivo"] != camp["hash_config"]:
                inf.error("X40_HASH", "07-campana/aprobacion.json", "hash_objetivo distinto de campana.hash_config: aprobación de otra configuración")
            if ids and set(ap["object_ids"]) != {ids["campaign_id"], *ids["adset_ids"], *ids["ad_ids"]}:
                inf.error("X40_OBJETOS", "07-campana/aprobacion.json", "object_ids distintos de ids_meta.json (igualdad exacta; un extra o una falta no activa)")
        if camp["estado"] in ("aprobada", "activa", "pausada") and ap.get("accion") != "activar_campana":
            inf.error("X40_HASH", "07-campana/aprobacion.json", "campaña aprobada/activa sin aprobación de activar_campana")
    elif camp and camp["estado"] in ("aprobada", "activa", "pausada") and not ap:
        inf.error("X40_HASH", "07-campana/aprobacion.json", f"campaña {camp['estado']} sin aprobacion.json")
    if pf and camp:
        if pf["hash_config"] != camp["hash_config"]:
            inf.error("X41_PREFLIGHT", "07-campana/preflight.json", "hash_config distinto del de campana.json: preflight de otra configuración")
        vig = c.param("campana", "preflight_vigencia_h")
        if vig is not None and _t(pf["valido_hasta"]) - _t(pf["generado_en"]) > _dt.timedelta(hours=vig):
            inf.error("X41_PREFLIGHT", "07-campana/preflight.json", f"vigencia mayor que campana.preflight_vigencia_h ({vig} h)")
        if camp["special_ad_categories"] and "P25" not in pf["checks"]:
            inf.error("X41_PREFLIGHT", "07-campana/preflight.json", "special_ad_categories no vacío exige P25 (coincidencia con el dictamen de X1)")
    if camp and camp["estado"] in ("preflight_ok", "aprobada", "activa", "pausada") and (not pf or pf["semaforo"] == "ROJO"):
        inf.error("X41_PREFLIGHT", "07-campana/preflight.json", f"campaña {camp['estado']} sin preflight.json o con semáforo ROJO")
    if tr:
        if ids and not {a["ad_id"] for a in tr["anuncios"]} <= set(ids["ad_ids"]):
            inf.error("X42_TRASPASO", "07-campana/traspaso.json", "anuncios fuera de ids_meta.json")
        if ids and tr["campana"]["campaign_id"] != ids["campaign_id"]:
            inf.error("X42_TRASPASO", "07-campana/traspaso.json", "campaign_id distinto de ids_meta.json")
        if camp and tr["gasto"]["real"]["moneda"] != camp["presupuesto"]["moneda"]:
            inf.error("X42_TRASPASO", "07-campana/traspaso.json", "gasto en otra moneda que la campaña")
    if pm:
        v = c.get("08-operacion/veredicto_oferta.json")
        if v and pm["veredicto"] != v["estado"]:
            inf.error("X46_POSTMORTEM", "08-operacion/postmortem.json", "veredicto distinto de veredicto_oferta.estado")
        if v and (c.dir / "08-operacion/veredicto_oferta.json").is_file() and not comparar_hash(pm["veredicto_sha256"], hash_archivo(c.dir / "08-operacion/veredicto_oferta.json")):
            inf.error("X46_POSTMORTEM", "08-operacion/postmortem.json", "veredicto_sha256 no coincide con veredicto_oferta.json")
        for k, x in enumerate(pm["parametros_a_calibrar"]):
            g, _, cl = x["parametro"].partition(".")
            if cl not in (claves_de_parametros().get(g) or ()):
                inf.error("X46_POSTMORTEM", f"08-operacion/postmortem.json/parametros_a_calibrar/{k}", f"{x['parametro']} no existe en parametros.schema")
    inf.verificados += 1


def validar_artefactos_de_empresa(emp: Path, informe: Informe, clave: bytes | None = None, parametros: dict | None = None,
                                  verificador: Callable[[bytes, str], bool] | None = None) -> None:
    """Ledger, conciliación, tipos de cambio, órdenes y sellos de X1 de ``empresa/`` si existen (cada uno contra su esquema y su coherencia).

    ``parametros``: por defecto ``emp/parametros.yaml`` o, si no está, el de la raíz del proyecto (vigencia de sellos, cobertura de adid).
    """
    if parametros is None:
        for cand in (emp / "parametros.yaml", raiz_datos() / "empresa" / "parametros.yaml"):
            if cand.is_file():
                parametros = cargar_yaml(cand)
                break
    tcs = None
    p = emp / "finanzas" / "tipos_cambio.jsonl"
    if p.is_file():
        tcs = cargar_jsonl(p)
        tasas: dict[str, str] = {}
        for k, l in enumerate(tcs):
            if validar_contra_esquema("tipo_cambio", l, f"empresa/finanzas/tipos_cambio.jsonl[{k}]", informe):
                for cod, msg in problemas_artefacto("tipo_cambio", l):
                    informe.error(cod, f"empresa/finanzas/tipos_cambio.jsonl[{k}]", msg)
                if l["tipo_cambio_id"] in tasas and tasas[l["tipo_cambio_id"]] != l["tasa"]:
                    informe.error("X45_TIPO_CAMBIO", f"empresa/finanzas/tipos_cambio.jsonl[{k}]", f"{l['tipo_cambio_id']} repetido con otra tasa: las conversiones no serían reproducibles")
                tasas.setdefault(l["tipo_cambio_id"], l["tasa"])
    p = emp / "finanzas" / "ledger.jsonl"
    if p.is_file():
        lineas = cargar_jsonl(p)
        if all(validar_contra_esquema("ledger", l, f"empresa/finanzas/ledger.jsonl[{k}]", informe) for k, l in enumerate(lineas)):
            for cod, msg in problemas_ledger(lineas, tcs):
                informe.error(cod, "empresa/finanzas/ledger.jsonl", msg)
    p = emp / "finanzas" / "conciliacion.json"
    if p.is_file():
        d = cargar_json(p)
        if validar_contra_esquema("conciliacion", d, "empresa/finanzas/conciliacion.json", informe):
            for cod, msg in problemas_artefacto("conciliacion", d, parametros=parametros):
                informe.error(cod, "empresa/finanzas/conciliacion.json", msg)
    p = emp / "datos" / "alertas.jsonl"   # el panel (GET /finanzas) lee solo esta ruta; finanzas/alertas.jsonl (F1) no tiene lector
    if p.is_file():
        alertas = []
        for k, a in enumerate(cargar_jsonl(p)):
            if validar_contra_esquema("alertas", a, f"empresa/datos/alertas.jsonl[{k}]", informe):
                alertas.append(a)
                for cod, msg in problemas_artefacto("alertas", a):
                    informe.error(cod, f"empresa/datos/alertas.jsonl[{k}]", msg)
        for cod, msg in problemas_alertas(alertas):
            informe.error(cod, "empresa/datos/alertas.jsonl", msg)
    p = emp / "ordenes_firmadas.jsonl"
    if p.is_file():
        ordenes = cargar_jsonl(p)
        buenas = []
        for k, o in enumerate(ordenes):
            if validar_contra_esquema("orden_firmada", o, f"empresa/ordenes_firmadas.jsonl[{k}]", informe):
                buenas.append(o)
                for cod, msg in problemas_artefacto("orden_firmada", o, clave=clave, verificador=verificador):
                    informe.error(cod, f"empresa/ordenes_firmadas.jsonl[{k}]", msg)
        for cod, msg in problemas_ordenes(buenas):
            informe.error(cod, "empresa/ordenes_firmadas.jsonl", msg)
    vig_dias = _param_valor(parametros, "compliance", "vigencia_dictamen_dias")
    for p in sorted((emp / "compliance" / "sellos").glob("*.json")) if (emp / "compliance" / "sellos").is_dir() else []:
        d = cargar_json(p)
        rel = f"empresa/compliance/sellos/{p.name}"
        if validar_contra_esquema("sello", d, rel, informe):
            if p.stem != d["artefacto_sha256"].split(":", 1)[1]:
                informe.error("X40_SELLO", rel, "el nombre del archivo debe ser el hash (sin prefijo) de artefacto_sha256")
            for cod, msg in problemas_artefacto("sello", d, clave=clave, verificador=verificador):
                informe.error(cod, rel, msg)
            try:
                if vig_dias is None:
                    informe.aviso("X40_VIGENCIA", rel, "sin parametros.compliance.vigencia_dictamen_dias no se acota la vigencia del sello")
                elif _t(d["vigencia_hasta"]) - _t(d["emitido_en"]) > _dt.timedelta(days=int(dec(vig_dias))):
                    informe.error("X40_VIGENCIA", rel, f"vigencia del sello mayor que compliance.vigencia_dictamen_dias ({vig_dias} d)")
            except ValueError:
                pass  # ya informado como X47_TIEMPO por problemas_artefacto


UE_UK = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT",
         "RO", "SK", "SI", "ES", "SE", "GB", "IS", "LI", "NO"}
# Estado de campaña admitido por cada fase de la oferta (docs/06 sección 5). Las fases no listadas no se restringen.
CAMPANA_POR_FASE = {
    "borrador": {"borrador", "preflight_ok", "aprobada"}, "en_construccion": {"borrador", "preflight_ok", "aprobada"},
    "listo_para_activar": {"aprobada"}, "en_test": {"activa", "pausada"},
}


def regla_coherencia_global(c: Contexto) -> None:
    """X30: fase, campaña, mercado, moneda, dominio y consentimiento coherentes entre artefactos (crítica M04)."""
    inf = c.informe
    est, camp, oferta = c.get("estado.json"), c.get("07-campana/campana.json"), c.get("03-oferta/oferta.json")
    merc, co, tr, paq = c.get("mercado.json"), c.get("05-landing/checkout.json"), c.get("05-landing/tracking.json"), c.get("06-creativos/paquete.json")
    if est and camp:
        fase, ce = est["fase"], camp["estado"]
        if fase in CAMPANA_POR_FASE and ce not in CAMPANA_POR_FASE[fase]:
            inf.error("X30_FASE", "estado.json", f"fase {fase} incoherente con campana.estado {ce}")
        if ce in ("activa", "pausada", "cerrada") and not (camp.get("ids_meta") or {}):
            inf.error("X30_FASE", "07-campana/campana.json", "estado activa/pausada/cerrada sin ids_meta")
        if fase in ("listo_para_activar", "en_test"):
            if co and co["price_ids"]["live"] is None:
                inf.error("X30_FASE", "05-landing/checkout.json", "fase que cobra con price_ids.live nulo")
            pend = [e for e in ("D1", "D2", "D3", "D4", "D5", "D6", "D7") if est["etapas"][e]["estado"] != "aprobado"]
            if pend:
                inf.error("X30_FASE", "estado.json", f"fase {fase} con etapas sin aprobar: {pend}")
        if fase == "validada" and not c.get("08-operacion/veredicto_oferta.json"):
            inf.error("X30_FASE", "estado.json", "fase validada sin veredicto_oferta.json")
    if merc and oferta and merc["moneda_cobro"] != oferta["moneda"]:
        inf.error("X30_MONEDA", "mercado.json", "moneda_cobro != oferta.moneda")
    if merc and camp:
        if merc["locale"] != camp["idioma"]:
            inf.error("X30_MERCADO", "mercado.json", "locale != campana.idioma")
        if not set(camp["paises"]) <= set(merc["paises_segmentacion"]):
            inf.error("X30_MERCADO", "mercado.json", "campana.paises fuera de mercado.paises_segmentacion")
    if oferta and camp:
        host = oferta["marca"]["dominio"]
        for nombre, url in (("campana.url.plantilla", camp["url"]["plantilla"]), ("campana.url.ejemplo_resuelto", camp["url"]["ejemplo_resuelto"])):
            if urlsplit(url).hostname != host:
                inf.error("X30_DOMINIO", "07-campana/campana.json", f"{nombre} apunta a otro dominio que oferta.marca.dominio ({host})")
    if oferta and paq and urlsplit(paq["destino"]["url_base"]).hostname != oferta["marca"]["dominio"]:
        inf.error("X30_DOMINIO", "06-creativos/paquete.json", "destino.url_base fuera del dominio de la marca")
    if tr and camp and set(camp["paises"]) & UE_UK and not tr["consent_gating"]["requerido_ue_uk"]:
        inf.error("X30_CONSENT", "05-landing/tracking.json", "campaña a la UE/UK con consent_gating.requerido_ue_uk=false")
    for m in coherencia_gate_activar(c.limites, c.autonomia):
        inf.aviso("GATE_ACTIVAR_H", "estado.json", m)
    inf.verificados += 1


def regla_operacion(c: Contexto) -> None:
    """X20/X21/X22: órdenes de presupuesto (único escritor, topes, gate), veredicto y señal de pausa."""
    inf, lim = c.informe, c.limites
    for k, o in enumerate(c.get("08-operacion/ordenes_presupuesto.jsonl") or []):
        ruta = f"08-operacion/ordenes_presupuesto.jsonl[{k}]"
        if o["emisor"] == "D8" and o["plan_ref"]:
            inf.error("X21_ORDEN", ruta, "D8 no puede emitir órdenes con un plan de D9 vigente (único escritor: D9 si hay plan activo)")
        if o["emisor"] == "D9" and not o["plan_ref"]:
            inf.error("X21_ORDEN", ruta, "D9 solo emite órdenes respaldadas por un plan (plan_ref)")
        antes, despues = o["antes"]["monto"], o["despues"]["monto"]
        if (o["accion"] == "aumentar") != (despues > antes) or (o["accion"] == "reducir") != (despues < antes):
            inf.error("X21_ORDEN", ruta, "accion incoherente con antes/despues")
        if antes:
            delta = entero_redondeado((despues - antes) * 10000, antes, "half_even")
            if delta != int(dec(o["delta_pct"]) * 100):
                inf.error("X21_ORDEN", ruta, f"delta_pct {o['delta_pct']} != recalculado {delta / 100}")
        clave_gate = "accion:aumentar_presupuesto_d8" if o["emisor"] == "D8" else "accion:subir_presupuesto_d9"
        if o["accion"] == "aumentar":
            esp = gate_esperado(clave_gate, o["gate"]["nivel"], c.gates)
            if o["gate"]["accion_gate"] != clave_gate or o["gate"]["gate"] != esp:
                inf.error("X11_GATE", ruta, f"gate de la orden {o['gate']} != tabla ({clave_gate}={esp})")
            if esp == "NA":
                inf.error("X11_GATE", ruta, f"{o['emisor']} no puede aumentar presupuesto en {o['gate']['nivel']}")
            if esp == "H" and (not o["aprobado_por"] or o["aprobado_por"]["tipo"] != "humano") and o["estado"] in ("aprobada", "ejecutada"):
                inf.error("X11_GATE", ruta, "orden con gate H ejecutada sin aprobación humana")
            res = evaluar_limites(lim, "aumentar_presupuesto")
            if o["estado"] in ("aprobada", "ejecutada") and not res:
                inf.error("X10_LIMITES", ruta, "aumento sin límites válidos (fail-closed): " + res.motivo, SALIDA_LIMITE)
            if res and lim:
                if o["delta_pct"] and dec(o["delta_pct"]) > dec(lim["aumento_presupuesto_max_pct_por_paso"]):
                    inf.error("X10_LIMITES", ruta, "aumento mayor que limites.aumento_presupuesto_max_pct_por_paso")
                if o["horas_desde_ultimo_aumento"] is not None and o["horas_desde_ultimo_aumento"] < lim["horas_min_entre_aumentos"]:
                    inf.error("X10_LIMITES", ruta, "aumento antes de limites.horas_min_entre_aumentos")
                f = dec(lim["factor_techo_teorico_diario"])
                if o["despues"]["moneda"] != lim.get("moneda_limites"):
                    inf.error("X10_LIMITES", ruta, "moneda de la orden != moneda_limites (convertir con tipo de cambio registrado)")
                elif despues * f > lim["gasto_diario_por_oferta"]:
                    inf.error("X10_LIMITES", ruta, "factor x nuevo presupuesto supera limites.gasto_diario_por_oferta")
        exp_key = clave_idempotencia("orden_presupuesto", o["oferta_id"], {"orden_id": o["orden_id"], "accion": o["accion"], "despues": despues})
        if o["idempotency_key"] != exp_key:
            inf.error("X21_ORDEN", ruta, "idempotency_key no es la determinista de (operación, oferta, parámetros)")
    v = c.get("08-operacion/veredicto_oferta.json")
    if v:
        ev = v["evidencia"]
        if ev["compras_netas"] != ev["compras_brutas"] - ev["reembolsos"]:
            inf.error("X20_VEREDICTO", "08-operacion/veredicto_oferta.json", "compras_netas != brutas - reembolsos")
        extra = c.param("veredicto", "madurez_dias_extra")
        if extra is not None and ev["madurez_dias"] != ev["garantia_dias"] + extra:
            inf.error("X20_VEREDICTO", "08-operacion/veredicto_oferta.json", "madurez_dias != garantía + madurez_dias_extra (backbone 5.9)")
        if v["estado"] == "VALIDADA":
            cmin, dmin = c.param("veredicto", "compras_min"), c.param("veredicto", "dias_min")
            if cmin is not None and ev["compras_netas"] < cmin:
                inf.error("X20_VEREDICTO", "08-operacion/veredicto_oferta.json", "VALIDADA con menos compras netas que veredicto.compras_min")
            if dmin is not None and ev["dias_con_datos"] < dmin:
                inf.error("X20_VEREDICTO", "08-operacion/veredicto_oferta.json", "VALIDADA con menos días que veredicto.dias_min")
            if ev["cpa_neto"] is not None and ev["cpa_neto"]["moneda"] != ev["cpa_objetivo"]["moneda"]:
                inf.error("X20_VEREDICTO", "08-operacion/veredicto_oferta.json", "cpa_neto y cpa_objetivo en monedas distintas")
            elif ev["cpa_neto"] is None or ev["cpa_neto"]["monto"] > ev["cpa_objetivo"]["monto"]:
                inf.error("X20_VEREDICTO", "08-operacion/veredicto_oferta.json", "VALIDADA exige CPA <= CPA objetivo")
        eco = c.get("03-oferta/economia.json")
        if eco and ev["cpa_objetivo"]["monto"] != eco["cpa_obj"]["monto"]:
            inf.error("X20_VEREDICTO", "08-operacion/veredicto_oferta.json", "cpa_objetivo distinto de economia.json")
        oferta = c.get("03-oferta/oferta.json")
        if oferta and ev["garantia_dias"] != oferta["garantia"]["dias"]:
            inf.error("X20_VEREDICTO", "08-operacion/veredicto_oferta.json", "garantia_dias distinto de la oferta")
        res_g = gate_esperado("etapa:D8", c.get("estado.json")["nivel"] if c.get("estado.json") else "N0", c.gates)
        if v["gate"] != res_g and v["estado"] != "VALIDADA":
            inf.aviso("X11_GATE", "08-operacion/veredicto_oferta.json", f"gate {v['gate']} distinto de la tabla para D8 ({res_g})")
    s = c.get("10-postcompra/senal_pausa.json")
    if s:
        u = s["umbrales_usados"]
        if c.param("salud_operativa", "disputas_alerta_pct") is not None and dec(u["disputas_alerta_pct"]) != dec(c.param("salud_operativa", "disputas_alerta_pct")):
            inf.error("X22_SENAL", "10-postcompra/senal_pausa.json", "disputas_alerta_pct distinto de parametros.salud_operativa")
        if lim and lim.get("ratio_disputas_pausa") is not None and dec(u["ratio_disputas_pausa"]) != dec(lim["ratio_disputas_pausa"]):
            inf.error("X22_SENAL", "10-postcompra/senal_pausa.json", "ratio_disputas_pausa distinto de limites")
        if s["emitida"] and s["accion_solicitada"] == "ninguna":
            inf.error("X22_SENAL", "10-postcompra/senal_pausa.json", "señal emitida sin acción solicitada")
        if not s["emitida"] and (s["accion_solicitada"] != "ninguna" or s["nivel"] != "verde" and s["motivo"] == "ninguno"):
            inf.error("X22_SENAL", "10-postcompra/senal_pausa.json", "señal no emitida pero con acción o nivel incoherente")
        if s["emitida"] and s["consumida_por"] is None:
            inf.aviso("X22_SENAL", "10-postcompra/senal_pausa.json", "señal emitida aún no consumida por D8")
    for k, e in enumerate(c.get("10-postcompra/entregas.jsonl") or []):
        prod = c.get("04-producto/producto.json")
        if prod and e["producto_sha256"] not in {i["sha256"] for i in prod["items"]}:
            inf.error("X05_HASH_ITEM", f"10-postcompra/entregas.jsonl[{k}]", "producto_sha256 no corresponde a ningún ítem del producto")
    for k, r in enumerate(c.get("10-postcompra/reembolsos.jsonl") or []):
        oferta = c.get("03-oferta/oferta.json")
        if oferta and r["dentro_garantia"] != (r["dias_desde_compra"] <= oferta["garantia"]["dias"]):
            inf.error("X20_REEMBOLSO", f"10-postcompra/reembolsos.jsonl[{k}]", "dentro_garantia incoherente con dias_desde_compra y la garantía")
        if lim and lim.get("reembolso_auto_max") is not None and r["ejecutor"] == "script":
            if r["monto"]["moneda"] != lim.get("moneda_limites"):
                inf.error("X10_LIMITES", f"10-postcompra/reembolsos.jsonl[{k}]", "moneda del reembolso != moneda_limites (convertir con tipo de cambio registrado; B04)")
            elif r["monto"]["monto"] > lim["reembolso_auto_max"]:
                inf.error("X10_LIMITES", f"10-postcompra/reembolsos.jsonl[{k}]", "reembolso automático mayor que limites.reembolso_auto_max")
    inf.verificados += 1


def regla_qa(c: Contexto) -> None:
    """X18: coherencia de cada QA (puntaje, umbral, severidades abiertas, veto de X1, nombre de archivo)."""
    inf = c.informe
    for rel, q in c.datos.items():
        if not rel.startswith("qa/"):
            continue
        nombre = Path(rel).stem
        esperado = f"{q['etapa'].lower()}-{q['version']}"
        if q["etapa"] == "X1":
            if not q.get("etapa_objetivo"):
                inf.error("X18_QA", rel, "un dictamen de X1 exige etapa_objetivo")
            esperado = f"x1-{(q.get('etapa_objetivo') or 'xx').lower()}-{q['version']}"
        if nombre != esperado:
            inf.error("X18_QA", rel, f"el nombre debe ser {esperado}.json (reconciliación R09/R15)")
        abiertos = [h for h in q["hallazgos"] if h["estado"] in ("abierto", "devuelto_al_maker")]
        bloq = [h for h in abiertos if h["severidad"] == "BLOQUEANTE"]
        mayor = [h for h in abiertos if h["severidad"] == "MAYOR"]
        items = [it["puntaje"] for it in q["items"]]
        media = sum(items) / len(items)
        if abs(media - float(q["puntaje_global"])) > 0.05:
            inf.error("X18_QA", rel, f"puntaje_global {q['puntaje_global']} != media de ítems {media:.2f}")
        if q["veredicto"] in ("PASS", "PASS_CON_NOTAS"):
            if bloq or mayor:
                inf.error("X18_QA", rel, "PASS con BLOQUEANTES o MAYORES abiertos")
            if dec(q["puntaje_global"]) < dec(q["umbral"]):
                inf.error("X18_QA", rel, "PASS con puntaje por debajo del umbral")
        if q["veredicto"] == "FAIL" and not (bloq or mayor or dec(q["puntaje_global"]) < dec(q["umbral"])):
            inf.error("X18_QA", rel, "FAIL sin BLOQUEANTE/MAYOR abierto ni puntaje bajo el umbral")
        if q["ronda"] == 2 and (bloq or mayor) and q["veredicto"] != "ESCALAR":
            inf.error("X18_QA", rel, "ronda 2 con BLOQUEANTE/MAYOR debe escalar al humano")
        if any(it["puntaje"] < 3 for it in q["items"]) and q["veredicto"] == "PASS":
            inf.aviso("X18_QA", rel, "PASS con un ítem por debajo de 3")
        if q["x1"] and q["x1"]["veredicto"] == "FAIL" and q["veredicto"] != "FAIL":
            inf.error("X18_QA", rel, "un FAIL de compliance (X1) bloquea la etapa: el veredicto no puede ser menor")
        if q["x1"]:
            if not (c.dir / q["x1"]["dictamen_ref"]).exists():
                inf.error("X07_RUTA", rel, f"no existe {q['x1']['dictamen_ref']}")
            elif (c.get(q["x1"]["dictamen_ref"]) or {}).get("artefacto_ref") not in (None, q["artefacto_ref"]):
                inf.error("X03_HASH_QA", rel, "el dictamen de X1 cubre otro artefacto_ref que el QA")
            elif not comparar_hash(q["x1"]["artefacto_sha256"], q["artefacto_sha256"]):
                inf.error("X03_HASH_QA", rel, "el sello de X1 no cubre el mismo artefacto que el QA")
    _regla_qa_categoria_especial(c)
    inf.verificados += 1


def problemas_categoria_especial(dictamen: dict, special_ad_categories: list[str] | None) -> list[tuple[str, str]]:
    """X50 (CT-3 B-03, LT-11): el dictamen de X1 y ``campana.special_ad_categories`` dicen lo mismo (conjunto; error en ambos sentidos).

    Cierra el defecto de que ``meta.preflight._p25`` sea ``NO_APLICA`` con ``[]`` y un producto financiero pase: si X1 exigió una categoría
    la campaña debe declararla, y si la campaña declara una que X1 no exigió el dictamen está desactualizado. Un dictamen 1.0.0 (o
    1.1.0 sin el campo) NO se compara (el campo es opcional): solo el dictamen de X1 sobre D7 con ``schema_version`` >= 1.1.0 está
    obligado a traerlo. ``special_ad_categories=None`` (no hay campaña todavía) solo comprueba la presencia. Función pura y reutilizable
    por quien emita P25 (``meta.preflight``).
    """
    out: list[tuple[str, str]] = []
    if dictamen.get("etapa") != "X1":
        return out
    cat = dictamen.get("categoria_especial_requerida")
    if cat is None:
        v = dictamen.get("schema_version")
        if dictamen.get("etapa_objetivo") == "D7" and isinstance(v, str) and _semver_tupla(v) >= (1, 1, 0):
            out.append(("X50_QA_CATEGORIA", "el dictamen de X1 sobre D7 (qa >= 1.1.0) debe traer categoria_especial_requerida ([] si ninguna): sin el campo P25 no puede detectar un producto financiero con special_ad_categories vacío"))
        return out
    if special_ad_categories is None:
        return out
    a, b = set(cat), set(special_ad_categories)
    if a - b:
        out.append(("X50_QA_CATEGORIA", f"X1 exige {sorted(a - b)} y campana.special_ad_categories no las declara: la campaña saldría sin la categoría especial (incumple la política de Meta)"))
    if b - a:
        out.append(("X50_QA_CATEGORIA", f"campana.special_ad_categories declara {sorted(b - a)} que el dictamen de X1 no exigió: dictamen desactualizado o categoría sin revisar"))
    return out


def _semver_tupla(v: str) -> tuple[int, int, int]:
    try:
        a, b, c = v.split(".")
        return int(a), int(b), int(c)
    except ValueError:
        return (0, 0, 0)


def _regla_qa_categoria_especial(c: Contexto) -> None:
    """X50 sobre el dictamen VIGENTE (versión más alta) de cada ``etapa_objetivo``; los anteriores no se comparan (los reemplaza el nuevo)."""
    vigentes: dict[str, tuple[int, str, dict]] = {}
    for rel, q in c.datos.items():
        if not rel.startswith("qa/") or q.get("etapa") != "X1":
            continue
        m = re.fullmatch(r"v([1-9][0-9]*)", str(q.get("version")))
        n = int(m.group(1)) if m else 0
        obj = str(q.get("etapa_objetivo"))
        if obj not in vigentes or n > vigentes[obj][0]:
            vigentes[obj] = (n, rel, q)
    camp = c.get("07-campana/campana.json")
    cats = camp.get("special_ad_categories") if camp else None
    for _, rel, q in vigentes.values():
        for cod, msg in problemas_categoria_especial(q, cats):
            c.informe.error(cod, rel, msg)


def regla_claims(c: Contexto) -> None:
    """X19: lint mínimo de claims de salud o de ingresos en la oferta y los creativos (el lint completo es de X1)."""
    inf = c.informe
    textos: list[tuple[str, str]] = []
    o = c.get("03-oferta/oferta.json")
    if o:
        p = o["promesa"]
        textos += [("oferta.promesa.titulo", p["titulo"]), ("oferta.promesa.subtitulo", p["subtitulo"])]
        textos += [(f"oferta.claims_permitidos/{x['claim_id']}", x["texto"]) for x in p["claims_permitidos"]]
        textos += [("oferta.garantia", o["garantia"]["texto_visible"])]
    paq = c.get("06-creativos/paquete.json")
    if paq:
        for a in paq["anuncios"]:
            cp = a["copy"]
            textos += [(f"{a['ad_name']}/{k}", cp[k]) for k in ("texto_principal", "titular", "descripcion")]
    for ruta, t in textos:
        for r in CLAIMS_PROHIBIDOS:
            if _rx(r).search(t):
                inf.error("X19_CLAIM", ruta, f"claim prohibido (salud/ingresos/resultado garantizado): /{r}/ en «{t[:80]}»")
    inf.verificados += 1


def cadena_registro_valida(lineas: list[dict]) -> list[str]:
    """Errores de la cadena de hashes de ``registro.jsonl``: cada ``hash`` es el de su línea y enlaza con la previa."""
    errores, prev = [], None
    for k, l in enumerate(lineas):
        if l["hash_previo"] != prev:
            errores.append(f"línea {k}: hash_previo no enlaza con la línea anterior")
        if not comparar_hash(l["hash"], hash_objeto(l, excluir=("hash",))):
            errores.append(f"línea {k}: hash no coincide con el contenido")
        prev = l["hash"]
    return errores


def regla_empresa(c: Contexto) -> None:
    """X25: cadena de hashes del registro; costos con oferta_id de la oferta y en la moneda de los límites."""
    inf = c.informe
    for m in cadena_registro_valida(c.get("_empresa/registro.jsonl") or []):
        inf.error("X25_REGISTRO", "_empresa/registro.jsonl", m)
    for k, l in enumerate(c.get("_empresa/registro.jsonl") or []):
        if l["modo"] == "dry_run" and l["resultado"]["estado"] not in ("ok", "dry_run", "bloqueado", "error"):
            inf.error("X25_REGISTRO", f"_empresa/registro.jsonl[{k}]", "resultado incoherente con el modo")
    inf.verificados += 1


def regla_floats_y_consistencia_basica(c: Contexto) -> None:
    """X26: ningún float en ningún artefacto de la oferta."""
    for rel, d in c.datos.items():
        for r in buscar_floats(d):
            c.informe.error("FLOAT", f"{rel}{r}", "float prohibido")
    c.informe.verificados += 1


REGLAS: list[Callable[[Contexto], None]] = [
    regla_ids, regla_hashes, regla_estado, regla_nichos_y_riesgo, regla_economia, regla_tiempos,
    regla_rutas_y_assets, regla_checkout_tracking, regla_catalogo, regla_campana, regla_brief, regla_mercado, regla_artefactos_nuevos,
    regla_coherencia_global, regla_operacion, regla_qa, regla_claims,
    regla_empresa, regla_floats_y_consistencia_basica,
]


def cargar_oferta(dir_oferta: Path, informe: Informe) -> dict[str, Any]:
    """Carga y valida contra esquema todos los artefactos presentes de una oferta."""
    datos: dict[str, Any] = {}
    for rel, esquema in ESQUEMA_DE_ARCHIVO.items():
        p = dir_oferta / rel
        if p.is_file():
            datos[rel] = cargar_datos(p)
            validar_contra_esquema(esquema, datos[rel], rel, informe)
    for rel, esquema in ESQUEMA_DE_JSONL.items():
        p = dir_oferta / rel
        if p.is_file():
            lineas = cargar_jsonl(p)
            datos[rel] = lineas
            for k, l in enumerate(lineas):
                validar_contra_esquema(esquema, l, f"{rel}[{k}]", informe)
    for p in sorted((dir_oferta / "08-operacion" / "diario").glob("*/kpi_oferta_dia.json")) if (dir_oferta / "08-operacion" / "diario").is_dir() else []:
        rel = str(p.relative_to(dir_oferta).as_posix())
        datos[rel] = cargar_json(p)
        validar_contra_esquema("kpi", datos[rel], rel, informe)
    for rel, esquema in (("_empresa/registro.jsonl", "registro"), ("_empresa/costos.jsonl", "costos")):
        p = dir_oferta / rel
        if p.is_file():
            datos[rel] = cargar_jsonl(p)
            for k, l in enumerate(datos[rel]):
                validar_contra_esquema(esquema, l, f"{rel}[{k}]", informe)
    qa_dir = dir_oferta / "qa"
    if qa_dir.is_dir():
        for p in sorted(qa_dir.glob("*.json")):
            rel = f"qa/{p.name}"
            datos[rel] = cargar_json(p)
            validar_contra_esquema("qa", datos[rel], rel, informe)
    return datos


def validar_oferta(dir_oferta: Path | str, limites: dict | None = None, parametros: dict | None = None,
                   autonomia: dict | None = None, clave_firma: bytes | None = None,
                   verificador: Callable[[bytes, str], bool] | None = None, clave_catalogo: bytes | None = None) -> Informe:
    """Valida una oferta completa: esquemas de cada artefacto y reglas cruzadas.

    ``limites``/``parametros``/``autonomia`` se cargan de ``empresa/`` si no se pasan. Si ``limites`` no
    está cargado o tiene claves nulas, un borrador solo recibe AVISO, pero cualquier estado que gaste
    (campaña distinta de ``borrador``) recibe ERROR con código de salida 5 (fail-closed).
    """
    dir_oferta = Path(dir_oferta)
    inf = Informe(f"Oferta {dir_oferta}")
    if not dir_oferta.is_dir():
        inf.error("OFERTA", str(dir_oferta), "la carpeta no existe")
        return inf
    emp = raiz_datos() / "empresa"
    limites = limites if limites is not None else (cargar_yaml(emp / "limites.yaml") if (emp / "limites.yaml").exists() else None)
    parametros = parametros if parametros is not None else (cargar_yaml(emp / "parametros.yaml") if (emp / "parametros.yaml").exists() else None)
    autonomia = autonomia if autonomia is not None else (cargar_yaml(emp / "autonomia.yaml") if (emp / "autonomia.yaml").exists() else None)
    if parametros is not None:
        validar_contra_esquema("parametros", parametros, "parametros", inf)
        for m in coherencia_parametros(parametros):
            inf.error("PARAM_COHERENCIA", "parametros", m)
        if limites is not None:
            for m in coherencia_limites_parametros(limites, parametros):
                inf.error("LIMITES_COHERENCIA", "limites", m)
    datos = cargar_oferta(dir_oferta, inf)
    if inf.errores:
        return inf  # sin esquema válido las reglas cruzadas no son confiables
    ctx = Contexto(dir_oferta, datos, limites, parametros, autonomia, cargar_gates(), inf, clave_firma, verificador,
                   clave_catalogo if clave_catalogo is not None else _clave_catalogo_env())
    for regla in REGLAS:
        try:
            regla(ctx)
        except (KeyError, TypeError, ValueError, IndexError) as exc:  # un artefacto faltante o malformado no tumba el informe
            inf.error("REGLA_FALLA", regla.__name__, f"{type(exc).__name__}: {exc}")
    return inf


def validar_cartera_de_empresa(emp: Path | None = None) -> Informe:
    """Valida las plantillas de ``empresa/`` (parametros, autonomia, limites) contra sus esquemas."""
    emp = emp or raiz_datos() / "empresa"
    inf = Informe("Plantillas de empresa/")
    for nombre in ("parametros", "autonomia", "limites"):
        p = emp / f"{nombre}.yaml"
        if p.exists():
            validar_contra_esquema(nombre, cargar_yaml(p), f"empresa/{nombre}.yaml", inf)
        else:
            inf.error("EMPRESA", f"empresa/{nombre}.yaml", "no existe")
    gates = cargar_gates()
    validar_contra_esquema("gates", gates, "contratos/gates.json", inf)
    par = emp / "parametros.yaml"
    if par.exists():
        for m in coherencia_parametros(cargar_yaml(par)):
            inf.error("PARAM_COHERENCIA", "empresa/parametros.yaml", m)
    lim_p, aut_p = emp / "limites.yaml", emp / "autonomia.yaml"
    if lim_p.exists() and aut_p.exists():
        for m in coherencia_gate_activar(cargar_yaml(lim_p), cargar_yaml(aut_p)):
            inf.aviso("GATE_ACTIVAR_H", "empresa/autonomia.yaml", m)
    validar_artefactos_de_empresa(emp, inf, parametros=cargar_yaml(par) if par.exists() else None)
    return inf


def validar_esquemas_cargables() -> Informe:
    """Carga todos los esquemas y comprueba metaesquema, ``$id`` único, ``$ref`` resolubles y descripciones."""
    inf = Informe("Esquemas")
    try:
        registro, esquemas = cargar_esquemas()
    except Exception as exc:  # noqa: BLE001 - se reporta como error de validación
        inf.error("ESQUEMA_CARGA", "contratos/", f"{type(exc).__name__}: {exc}")
        return inf
    for nombre, doc in esquemas.items():
        inf.verificados += 1
        if not doc["$id"].endswith(f"/{nombre}.schema.json") or "/v1/" not in doc["$id"]:
            inf.error("ESQUEMA_ID", nombre, f"$id inesperado: {doc['$id']}")
        if not doc.get("title") or not doc.get("description"):
            inf.error("ESQUEMA_DOC", nombre, "faltan title o description")
        for ref in _refs(doc):
            base = ref.split("#")[0]
            if base and not any(d["$id"].endswith("/" + base) for d in esquemas.values()):
                inf.error("ESQUEMA_REF", nombre, f"$ref a un esquema inexistente: {ref}")
        # Toda ``$ref`` debe resolver (se prueba con una instancia vacía).
        try:
            list(Validador(doc, registry=registro).iter_errors({}))
        except Exception as exc:  # noqa: BLE001
            inf.error("ESQUEMA_REF", nombre, f"referencia no resoluble: {type(exc).__name__}: {exc}")
    return inf


def _refs(nodo: Any) -> list[str]:
    if isinstance(nodo, dict):
        return ([nodo["$ref"]] if isinstance(nodo.get("$ref"), str) else []) + [r for v in nodo.values() for r in _refs(v)]
    if isinstance(nodo, list):
        return [r for v in nodo for r in _refs(v)]
    return []


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def limites_de_prueba() -> dict:
    """Límites FICTICIOS completos y sellados, solo para validar ``ofertas/_ejemplo`` (nunca son límites reales)."""
    ruta = DIR_EJEMPLOS / "limites.valido.yaml"
    return cargar_yaml(ruta)


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada. Devuelve el código de salida (0, 2, 3 o 5)."""
    ap = argparse.ArgumentParser(prog="python -m scripts.validar_esquemas", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("esquemas", help="carga y valida todos los esquemas")
    sub.add_parser("ejemplos", help="valida ejemplos válidos e inválidos")
    po = sub.add_parser("oferta", help="valida una oferta completa con reglas cruzadas")
    po.add_argument("dir")
    po.add_argument("--limites", help="limites.yaml a usar (por defecto empresa/limites.yaml; ofertas/_ejemplo usa límites de prueba)")
    pl = sub.add_parser("limites", help="comprueba limites.yaml (fail-closed)")
    pl.add_argument("archivo", nargs="?", default=str(raiz_datos() / "empresa" / "limites.yaml"))
    pl.add_argument("--operacion", default="gastar", choices=sorted(CLAVES_CRITICAS))
    pp = sub.add_parser("parametros", help="comprueba que parametros.yaml trae lo que exige una operación (fail-closed, salida 5)")
    pp.add_argument("archivo", nargs="?", default=str(raiz_datos() / "empresa" / "parametros.yaml"))
    pp.add_argument("--operacion", required=True, choices=sorted(OPERACION_PARAMETROS))
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return SALIDA_USO if e.code not in (0, None) else SALIDA_OK
    informes: list[Informe] = []
    if args.cmd in (None, "esquemas"):
        informes.append(validar_esquemas_cargables())
    if args.cmd in (None, "ejemplos"):
        informes.append(validar_ejemplos())
        informes.append(validar_cartera_de_empresa())
    if args.cmd in (None, "oferta"):
        dir_o = Path(args.dir) if args.cmd == "oferta" else raiz_datos() / "ofertas" / "_ejemplo"
        if not dir_o.is_absolute():   # un argumento relativo es relativo a la raíz de datos (absoluta: nunca se duplica el prefijo)
            dir_o = raiz_datos() / dir_o
        es_ejemplo = es_ejemplo_del_repositorio(dir_o)
        if es_ejemplo and not ejemplo_permitido():
            print("ERROR: ofertas/_ejemplo no se valida con FABRICA_ENTORNO=produccion (usa límites ficticios y una clave de prueba pública)")
            return SALIDA_VALIDACION
        lim = None
        if args.cmd == "oferta" and args.limites:
            lim = cargar_yaml(args.limites)
        elif es_ejemplo:
            lim = limites_de_prueba()
        aut = cargar_yaml(DIR_EJEMPLOS / "autonomia.valido.yaml") if es_ejemplo else None
        clave = _clave_firma_env() or (CLAVE_DE_PRUEBA if es_ejemplo else None)
        informes.append(validar_oferta(dir_o, limites=lim, autonomia=aut, clave_firma=clave))
    if args.cmd == "limites":
        informes.append(validar_limites_archivo(Path(args.archivo), args.operacion))
    if args.cmd == "parametros":
        inf = Informe(f"Parámetros {args.archivo} (operación: {args.operacion})")
        if not Path(args.archivo).is_file():   # fail-closed: sin parámetros no se opera
            inf.error("PARAMETRO_FALTANTE", args.archivo, "ParametroFaltante: falta parametros.yaml: sin parámetros no se opera", SALIDA_LIMITE)
            print(inf.texto())
            return SALIDA_LIMITE
        datos = cargar_yaml(args.archivo)
        validar_contra_esquema("parametros", datos, args.archivo, inf)
        falta = parametros_faltantes(datos, OPERACION_PARAMETROS[args.operacion])
        inf.verificados += 1
        if falta:
            inf.error("PARAMETRO_FALTANTE", args.archivo, "ParametroFaltante: " + ", ".join(falta), SALIDA_LIMITE)
        informes.append(inf)
    codigos = []
    for inf in informes:
        print(inf.texto())
        codigos.append(inf.codigo_salida)
    if SALIDA_VALIDACION in codigos:
        return SALIDA_VALIDACION
    return SALIDA_LIMITE if SALIDA_LIMITE in codigos else SALIDA_OK


CLAVE_DE_PRUEBA = b"clave-de-prueba-no-real"  # solo para firmar/verificar ofertas/_ejemplo; nunca una clave real


def _clave_catalogo_env() -> bytes | None:
    """Clave HMAC del catálogo firmado (la misma variable que usa ``landing.catalogo`` y el secreto del Worker)."""
    clave = os.environ.get("CATALOGO_HMAC")
    return clave.encode() if clave else None


def _clave_firma_env() -> bytes | None:
    clave = os.environ.get("FABRICA_FIRMA_CLAVE")
    return clave.encode() if clave else None


if __name__ == "__main__":
    sys.exit(main())
