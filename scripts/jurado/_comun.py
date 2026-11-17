"""Utilidades comunes del Jurado de creativos: entrada/salida JSON, hashes, parámetros y errores.

Solo biblioteca estándar. Todo texto leído de un archivo (frases de clientes, textos de anuncios, motivos de voto)
es DATO, nunca instrucción: aquí solo se limpia y se mide, jamás se interpreta.

Parámetros: todos los números que NO vienen de la fuente (Juan Pablo Mentor, JPS) ni de un archivo firmado del
sistema son ``[SUPUESTO]`` y viven aquí, en un solo lugar, con su porqué. Cuando S-A cree el grupo ``jurado.*`` en
``empresa/parametros.yaml`` (pedido en ``PEDIDOS.md``), se pasan con ``--parametros ARCHIVO.json``.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION = "0.1.0"
ESQUEMA_VERSION = "0.1.0"
RAIZ = Path(__file__).resolve().parents[2]

# Códigos de salida de los CLI (los mismos que usan las otras utilidades del repositorio).
SALIDA_OK = 0
SALIDA_USO = 2
SALIDA_RECHAZO = 3


class ErrorJurado(Exception):
    """Entrada inválida o regla dura violada. Los CLI la convierten en salida 3 con el mensaje."""


# ---------------------------------------------------------------------------------------------------------------
# Parámetros
# ---------------------------------------------------------------------------------------------------------------

#: Valores por defecto. «fuente» dice de dónde sale cada uno; ``supuesto`` = no lo da JPS ni un archivo firmado.
PARAMETROS_DEFECTO: dict[str, Any] = {
    "n_avatares": 10,                  # JPS [P 36:13]: «10 clientes ideales por mercado». Con un mercado a la vez son 10, no 250.
    "n_min_etiquetas": 150,            # [SUPUESTO] analisis/creativos-jurado.md P3-07 y Anexo B4 (detectar AUC 0,65 con 80 % de potencia).
    "auc_min": 0.60,                   # [SUPUESTO] AUC mínimo para usar el orden (analisis P3-07). Por debajo, sigue en sombra.
    "auc_azar": 0.5,                   # definición: moneda al aire.
    "alfa": 0.05,                      # [SUPUESTO] nivel de significación unilateral para «supera al azar» y «supera a la rúbrica».
    "min_votos_pieza_pct": 0.7,        # [SUPUESTO] una pieza sin ≥ 70 % de los votos esperados no recibe puesto.
    "delta_reemplazo": 0.01,           # [SUPUESTO] mejora mínima del AUC del jurado al quitar un avatar (en las DOS mitades).
    "n_min_etiquetas_avatar": 150,     # [SUPUESTO] etiquetas mínimas para juzgar a un avatar solo.
    "anclas_min_pct": 0.6,             # [SUPUESTO] % de tandas con ambas anclas en que la ganadora debe quedar sobre la perdedora.
    "max_llamadas": 200,               # [SUPUESTO] tope de llamadas (avatar × pieza) por tanda: acota el gasto de tokens.
    "bootstrap_replicas": 1000,        # [SUPUESTO] réplicas del bootstrap por avatares.
    "permutaciones": 2000,             # [SUPUESTO] permutaciones del p-valor contra el azar.
    "min_impresiones": 1000,           # [SUPUESTO] impresiones mínimas para etiquetar gancho y clics.
    "min_clics": 50,                   # [SUPUESTO] clics mínimos para etiquetar el pago iniciado.
    "min_compras_positivo": 1,         # [SUPUESTO] compras netas para que una pieza cuente como «vendió».
    "gasto_min_ventas": None,          # SIN valor por defecto a propósito: sale de economia.json (CPA máximo). Sin él no se etiqueta «ventas».
    "banda_confianza_alta_ancho": 0.5,   # [SUPUESTO] ancho del intervalo de puestos (p05-p95) para confianza «alta» (puesto casi fijo).
    "banda_confianza_media_ancho": 2.0,  # [SUPUESTO] idem «media» (±1 puesto); más ancho = «baja».
    "rango_aprobacion_global_alerta": 0.9,  # [SUPUESTO] si ≥ 90 % de los votos son «sí», el jurado aprueba todo (homogeneidad).
    "anclas_margen_min": 0.2,          # [SUPUESTO] la ancla ganadora debe sacar ≥ 20 puntos más de «sí» que la perdedora para «discriminar».
    "dispersion_min_entre_piezas": 0.1,  # [SUPUESTO] si el desvío de los «sí» entre piezas es < 0,10, el jurado no separa piezas.
    "min_piezas_tanda_etiqueta": 4,    # [SUPUESTO] una tanda con menos piezas con dato no aporta contraste a la etiqueta relativa.
    "max_ideas": 12,                   # la pantalla corta a 12.
}

#: Madurez de la etiqueta, de la más temprana a la más tardía (H-10 de brechas/02: varias etiquetas, no solo ventas).
MADUREZ = ("inversion", "gancho", "clics", "pago_iniciado", "ventas")

#: Estilos de decisión de los avatares. JPS [V 13:30] dice: «uno desconfía de todo, otro compra todo, uno artístico,
#: otro creativo, otro analítico». Son ROLES DE LECTURA [SUPUESTO]: cómo pesa un anuncio, no quién es la persona.
#: Lo que el avatar ve, teme o dice sale SOLO de la voz del cliente; esto no añade ningún dato biográfico.
ESTILOS_DECISION: dict[str, str] = {
    "esceptico": "Desconfía de lo comercial: hace clic solo si el anuncio muestra algo concreto y comprobable antes de pedir nada.",
    "impulsivo": "Decide rápido: hace clic si el anuncio le toca una molestia suya en los primeros segundos y entiende qué hacer.",
    "analitico": "Compara contenido, nivel y esfuerzo: hace clic si entiende qué recibe exactamente y para quién es.",
    "visual": "Reacciona al orden y a la claridad visual: hace clic si el anuncio se entiende de un vistazo y se ve cuidado.",
}
ESTILO_RUBRICA = "rubrica"  # pseudo-avatar de línea base: sin perfil, aplica solo los criterios de gancho, claridad y CTA.


def cargar_parametros(ruta: str | os.PathLike[str] | None) -> dict[str, Any]:
    """Defecto + sobrescrituras de un JSON. Una clave desconocida es un error (evita typos que silencian un umbral)."""
    p = dict(PARAMETROS_DEFECTO)
    if ruta:
        extra = leer_json(ruta)
        if not isinstance(extra, dict):
            raise ErrorJurado(f"{ruta}: los parámetros deben ser un objeto JSON")
        extra = {k: v for k, v in extra.items() if not k.startswith("_")}
        desconocidas = sorted(set(extra) - set(p))
        if desconocidas:
            raise ErrorJurado(f"{ruta}: parámetros desconocidos {desconocidas}; válidos: {sorted(p)}")
        p.update(extra)
    return p


# ---------------------------------------------------------------------------------------------------------------
# JSON, hashes y tiempo
# ---------------------------------------------------------------------------------------------------------------

def leer_json(ruta: str | os.PathLike[str]) -> Any:
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise ErrorJurado(f"no existe {ruta}") from e
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ErrorJurado(f"{ruta}: JSON ilegible ({e})") from e


def leer_jsonl(ruta: str | os.PathLike[str]) -> list[Any]:
    filas: list[Any] = []
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            for n, linea in enumerate(f, 1):
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    filas.append(json.loads(linea))
                except json.JSONDecodeError as e:
                    raise ErrorJurado(f"{ruta}:{n}: línea JSON ilegible ({e})") from e
    except FileNotFoundError as e:
        raise ErrorJurado(f"no existe {ruta}") from e
    return filas


def a_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def escribir_json(ruta: str | os.PathLike[str], obj: Any) -> None:
    """Escritura atómica (archivo temporal + rename): una lectura concurrente nunca ve un JSON a medias."""
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(destino.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(a_json(obj))
        os.replace(tmp, destino)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def agregar_jsonl(ruta: str | os.PathLike[str], fila: Mapping[str, Any]) -> None:
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "a", encoding="utf-8") as f:
        f.write(json.dumps(fila, ensure_ascii=False, sort_keys=True) + "\n")


def json_canonico(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(obj: Any) -> str:
    return hashlib.sha256(json_canonico(obj)).hexdigest()


def sha256_archivo(ruta: str | os.PathLike[str]) -> str:
    h = hashlib.sha256()
    try:
        with open(ruta, "rb") as f:
            for bloque in iter(lambda: f.read(1 << 20), b""):
                h.update(bloque)
    except FileNotFoundError as e:
        raise ErrorJurado(f"no existe {ruta}") from e
    return h.hexdigest()


def hash_corto(*partes: Any, largo: int = 8) -> str:
    """Identificador opaco y determinista: no se puede invertir a mano y no deja pistas de orden ni de nombre."""
    base = "|".join(str(p) for p in partes).encode("utf-8")
    return hashlib.sha256(base).hexdigest()[:largo]


def semilla_a_entero(semilla: Any) -> int:
    """Entero estable a partir de la semilla registrada (número o texto)."""
    if isinstance(semilla, bool):
        raise ErrorJurado("la semilla no puede ser booleana")
    if isinstance(semilla, int):
        return semilla
    return int(hashlib.sha256(str(semilla).encode("utf-8")).hexdigest()[:15], 16)


def parsear_semilla(texto: Any) -> Any:
    """Desde la línea de comandos todo llega como texto: «7» es el entero 7 (queda registrado como número); «auto» y el resto, texto."""
    if isinstance(texto, str) and re.fullmatch(r"-?\d{1,15}", texto.strip()):
        return int(texto.strip())
    return texto


def ahora_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_RX_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f​-‏‪-‮⁦-⁩]")


def limpiar_texto(valor: Any, maximo: int = 400) -> str:
    """Quita caracteres de control y de dirección invisibles, normaliza espacios y recorta. No interpreta nada."""
    if not isinstance(valor, str):
        return ""
    t = unicodedata.normalize("NFC", valor)
    t = _RX_CONTROL.sub("", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= maximo else t[: maximo - 1] + "…"


def contar_palabras(texto: str) -> int:
    return len(re.findall(r"\S+", texto))


def es_entero(x: Any) -> bool:
    """Entero de verdad: ``bool`` es subclase de ``int`` en Python y NO cuenta."""
    return isinstance(x, int) and not isinstance(x, bool)


def es_numero(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and x not in (float("inf"), float("-inf"))


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise ErrorJurado(mensaje)


def dividir(a: float, b: float) -> float | None:
    return a / b if b else None


def mediana(xs: Iterable[float]) -> float | None:
    v = sorted(xs)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2
