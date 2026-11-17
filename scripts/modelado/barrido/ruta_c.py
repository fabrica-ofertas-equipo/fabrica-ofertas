"""Ruta C del barrido: cliente de la API oficial de la Biblioteca de Anuncios (`ads_archive`, Graph API).

Qué hace (CONTRATO §2 y §5):
  · `ClienteBiblioteca` consulta `https://graph.facebook.com/<versión>/ads_archive` con un `Transporte` INYECTABLE
    (clase con método `solicitar`), pagina por cursor con tope de páginas y pausa entre solicitudes (valores de
    `parametros_ruta_c.propuesta.yaml`, nunca fijos aquí) y se detiene ante token inválido, falta de acceso o límite de tasa.
  · `Frenos` (revisión de seguridad m4): ANTES de cada solicitud respeta `empresa/PAUSA` y el freno compartido
    `empresa/captura/freno.json` (si existe, no hace nada: código 4), anota la solicitud en
    `empresa/barrido/ruta_c/<corrida_id>.jsonl` y aplica el tope por corrida y el tope diario (UTC, suma de todas las
    corridas; parámetros, no números fijos). Un límite de tasa (613/429) es FRENO: sin reintento ni espera, escribe el
    freno compartido y corta; lo recibido hasta entonces se conserva.
  · El token sale SOLO de la variable de entorno `META_AD_LIBRARY_TOKEN` (`leer_token`, falla cerrado si falta). Viaja
    envuelto en `Secreto` (su repr no lo muestra) y nunca se escribe en archivos, mensajes de error ni logs. OJO: la API
    mete el `access_token` dentro de `paging.next` y a veces de `ad_snapshot_url`: aquí se descartan `next` (se pagina con
    el cursor `after`) y se limpia `ad_snapshot_url` apenas llega.
  · `convertir` pasa el resultado al formato crudo de CONTRATO §2 (`ruta: "C"`, fechas ISO a epoch en segundos,
    `ad_snapshot_url` reconstruida como `https://www.facebook.com/ads/library/?id=<id>` tras comprobar que el id de la URL
    de la API coincide). Lo que el contrato no tiene (texto del anuncio, alcance en la UE, plataformas, segmentación...)
    va a `<qid>.extra.json`, hermano del crudo, sin alterar el esquema del crudo.

Diferencias con el conector que el código NO esconde (fuente: referencia oficial de ArchivedAd, leída 2026-11-06):
  · `currency` solo está documentado para anuncios políticos: si la API no lo trae, el crudo usa «XXX» (código ISO 4217
    de «sin moneda», 3 letras para cumplir el contrato) y el extra marca `moneda_origen: "sin_dato"`. NO se inventa una
    moneda: sin moneda no hay señal de exportadores por moneda (PEDIDO en el informe).
  · La API no entrega `estimated_total_count`. Si la paginación termina (no hay `next`) el archivo declara su propio total;
    si se cortó por tope de páginas o por error, declara `null` y el extra dice `completo: false`.
  · El contrato exige `len(ads) <= limit <= 50`, pero la API pagina muchos más: el resultado se parte en archivos
    `<qid>-c01`, `<qid>-c02`... (un solo archivo `<qid>` si cabe en uno).
  · Fuera de la UE y el Reino Unido la API solo devuelve anuncios sobre temas sociales, elecciones o política: una consulta
    a un país fuera de `ruta_c_paises_cobertura` se rechaza (ErrorUso) en vez de volcar esos anuncios como si fueran ofertas.

Todo texto que viene de la Biblioteca (nombres, títulos, cuerpos) es dato NO confiable: aquí solo se copia y se valida.
Lo no comprobado contra la fuente oficial (formato exacto de errores, máximo de `limit`, límite de tasa, etc.) está
marcado [VERIFICAR] y se resuelve con la primera consulta real del dueño. Sin float en lo persistido. Solo biblioteca
estándar y PyYAML. Las pruebas no abren red: el transporte se inyecta.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

from scripts.modelado.barrido import comun
from scripts.modelado.barrido.comun import (
    ErrorBloqueado,
    ErrorFabrica,
    ErrorLimite,
    ErrorUso,
    ErrorValidacion,
)

__all__ = [
    "VARIABLE_TOKEN", "CLAVES_RUTA_C", "RUTA_PARAMETROS_RUTA_C", "MONEDA_SIN_DATO",
    "ErrorTokenInvalido", "ErrorAcceso", "ErrorTasa", "ErrorServicio", "ErrorRespuesta", "ErrorFreno", "ErrorTope",
    "Frenos",
    "Secreto", "leer_token", "ParametrosRutaC", "parametros_desde_mapa", "cargar_parametros_ruta_c",
    "Respuesta", "Transporte", "TransporteHTTP", "Resultado", "ClienteBiblioteca", "normalizar_consulta",
    "iso_a_epoch", "quitar_token_de_url", "Paquete", "convertir", "escribir", "barrer_consulta",
]

# ---------------------------------------------------------------------------
# Hechos de la API (vocabulario, no umbrales). Fuente: referencia oficial de ads_archive, leída 2026-11-06.
# ---------------------------------------------------------------------------

VARIABLE_TOKEN = "META_AD_LIBRARY_TOKEN"
HOST_API = "graph.facebook.com"
ENDPOINT = "ads_archive"
TIPO_ANUNCIO = "ALL"                    # `ad_type`: «ALL returns ads on all topics» (por defecto)
TERMINOS_MAX = 100                      # «The limit of your string is 100 characters or less»
PAGE_IDS_MAX = 10                       # `search_page_ids`: hasta diez Page IDs
TIPOS_BUSQUEDA = ("KEYWORD_UNORDERED", "KEYWORD_EXACT_PHRASE")
MONEDA_SIN_DATO = "XXX"                 # ISO 4217: «sin moneda»; la API no da `currency` en anuncios comerciales
URL_FICHA = "https://www.facebook.com/ads/library/?id={}"
USER_AGENT = "digital-products-barrido-ruta-c/1.0 (Ad Library API; uso interno)"
CODIGOS_TOKEN = frozenset({190, 102})   # 190 = «Invalid OAuth 2.0 Access Token» (documentado); 102 = sesión [VERIFICAR]
CODIGOS_TASA = frozenset({4, 17, 32, 341, 613})  # 613 = «exceeded the rate limit» (documentado); el resto [VERIFICAR]
CODIGOS_ACCESO = frozenset({10, 200})   # permiso denegado [VERIFICAR el código exacto de «identidad sin confirmar»]
CAMPOS_OBLIGATORIOS = ("id", "page_id", "page_name", "ad_delivery_start_time", "ad_snapshot_url",
                       "ad_creative_link_titles")

RUTA_PARAMETROS_RUTA_C: Path = Path(__file__).resolve().parent / "parametros_ruta_c.propuesta.yaml"
CLAVES_RUTA_C = (
    "ruta_c_version_api", "ruta_c_limite_pagina", "ruta_c_max_paginas", "ruta_c_pausa_ms", "ruta_c_tiempo_max_seg",
    "ruta_c_max_bytes_respuesta", "ruta_c_reintentos_tasa", "ruta_c_max_solicitudes_por_corrida",
    "ruta_c_max_solicitudes_por_dia", "ruta_c_anuncios_por_archivo",
    "ruta_c_tipo_busqueda", "ruta_c_campos", "ruta_c_paises_cobertura",
)

_RE_TOKEN = re.compile(r"[\x21-\x7e]{10,4096}")           # ASCII imprimible sin espacios
_RE_VERSION = re.compile(r"v[0-9]{1,3}\.[0-9]{1,2}")
_RE_CAMPO = re.compile(r"[a-z][a-z0-9_]{0,60}")
_RE_PAIS = re.compile(r"[A-Z]{2}")
_RE_MONEDA = re.compile(r"[A-Z]{3}")
_RE_DIGITOS = re.compile(r"[0-9]{1,30}")
_RE_ISO = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d{1,9})?\s*(Z|[+-]\d{2}(?::?\d{2})?)?)?")
_RE_TOKEN_EN_TEXTO = re.compile(r"(access_token=)[^&\s\"']+", re.IGNORECASE)
_RE_TOKEN_FB = re.compile(r"EAA[A-Za-z0-9]{40,}")


# ---------------------------------------------------------------------------
# Errores (se apoyan en los de comun: 3 validación, 4 bloqueado, 5 límite)
# ---------------------------------------------------------------------------

class _ConParcial(ErrorFabrica):
    """Base de los errores de la ruta C: lleva lo recibido antes de fallar y los archivos ya escritos."""

    parcial: "Resultado | None" = None
    archivos: tuple[Path, ...] = ()


class ErrorTokenInvalido(_ConParcial, ErrorBloqueado):
    """Meta rechazó el token (código 190: inválido, vencido o identidad sin confirmar). No se reintenta."""


class ErrorAcceso(_ConParcial, ErrorBloqueado):
    """Meta niega el permiso (identidad sin confirmar, app sin acceso a la API, HTTP 403). No se reintenta."""


class ErrorTasa(_ConParcial, ErrorBloqueado):
    """Límite de tasa agotado tras los reintentos permitidos: freno, no se insiste."""


class ErrorServicio(_ConParcial, ErrorBloqueado):
    """Fallo de red, tiempo agotado o error 5xx de Meta."""


class ErrorRespuesta(_ConParcial, ErrorValidacion):
    """La respuesta de la API no tiene la forma esperada (no es JSON, falta `data`, cursor inconsistente...)."""


class ErrorFreno(_ConParcial, ErrorBloqueado):
    """`empresa/PAUSA` o el freno compartido `empresa/captura/freno.json` están activos (código 4). No se hace nada."""


class ErrorTope(_ConParcial, ErrorLimite):
    """Tope por corrida o tope diario de solicitudes alcanzado (código 5): se retoma en otra corrida o mañana (UTC)."""


def _ver(valor: Any, largo: int = 80) -> str:
    texto = repr(valor)
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"


# ---------------------------------------------------------------------------
# Token: solo desde el entorno, envuelto, nunca en archivos ni mensajes
# ---------------------------------------------------------------------------

class Secreto:
    """Envuelve un secreto: `repr`/`str` no lo muestran; solo `revelar()` lo entrega (y solo al transporte)."""

    __slots__ = ("_valor",)

    def __init__(self, valor: str) -> None:
        self._valor = valor

    def revelar(self) -> str:
        return self._valor

    def __repr__(self) -> str:
        return "Secreto(***)"

    __str__ = __repr__

    def __reduce__(self):  # no se serializa por accidente (pickle/copy)
        raise TypeError("Secreto no se serializa")


def leer_token(entorno: Mapping[str, str] | None = None) -> Secreto:
    """Lee `META_AD_LIBRARY_TOKEN` del entorno (o de `entorno`, para pruebas). Falla cerrado (ErrorBloqueado, 4).

    El mensaje de error nunca incluye el valor, ni siquiera parcial.
    """
    entorno = os.environ if entorno is None else entorno
    crudo = entorno.get(VARIABLE_TOKEN)
    if crudo is None or not crudo.strip():
        raise ErrorBloqueado(
            f"falta la variable de entorno {VARIABLE_TOKEN}: sin token no se llama a la API "
            "(pasos del dueño en docs/_historial/barrido-ruta-c.md; nunca se guarda en archivos)")
    token = crudo.strip()
    if _RE_TOKEN.fullmatch(token) is None:
        raise ErrorBloqueado(
            f"{VARIABLE_TOKEN} tiene un formato inusable (se esperaban 10-4096 caracteres ASCII visibles, sin espacios): "
            "se rechaza sin mostrarlo")
    return Secreto(token)


def _sanear(texto: Any, token: Secreto | None = None, largo: int = 200) -> str:
    """Texto seguro para un mensaje: sin el token, sin `access_token=...`, sin controles y recortado."""
    s = str(texto)
    if token is not None and token.revelar():
        s = s.replace(token.revelar(), "***")
    s = _RE_TOKEN_EN_TEXTO.sub(r"\1***", s)
    s = _RE_TOKEN_FB.sub("***", s)
    s = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", s)
    return s if len(s) <= largo else s[: largo - 1] + "…"


def quitar_token_de_url(url: str) -> str:
    """La misma URL sin el parámetro `access_token` (la API lo incrusta en algunas `ad_snapshot_url`)."""
    partes = urlsplit(url)
    if not partes.query:
        return url
    pares = [(k, v) for k, v in parse_qsl(partes.query, keep_blank_values=True) if k.lower() != "access_token"]
    return urlunsplit((partes.scheme, partes.netloc, partes.path, urlencode(pares), partes.fragment))


# ---------------------------------------------------------------------------
# Parámetros (todos desde el YAML; falla cerrado)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParametrosRutaC:
    version_api: str
    limite_pagina: int
    max_paginas: int
    pausa_ms: int
    tiempo_max_seg: int
    max_bytes_respuesta: int
    reintentos_tasa: int
    max_solicitudes_por_corrida: int
    max_solicitudes_por_dia: int
    anuncios_por_archivo: int
    tipo_busqueda: str
    campos: tuple[str, ...]
    paises_cobertura: tuple[str, ...]


def _entero(clave: str, valor: Any, minimo: int, maximo: int | None = None) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ErrorValidacion(f"{clave}: se esperaba un entero, llegó {type(valor).__name__} {_ver(valor)}")
    if valor < minimo or (maximo is not None and valor > maximo):
        permitido = f"≥ {minimo}" if maximo is None else f"[{minimo}, {maximo}]"
        raise ErrorLimite(f"{clave}: {valor} fuera de lo permitido ({permitido})")
    return valor


def parametros_desde_mapa(mapa: Mapping[str, Any]) -> ParametrosRutaC:
    """Valida un mapa {clave: valor} con las claves de `CLAVES_RUTA_C` (p. ej. el que entrega `comun.cargar_parametros_barrido`
    cuando B1 integre estas claves). Falta una clave = ErrorLimite (5); tipo o contenido inválido = ErrorValidacion (3)."""
    faltan = [c for c in CLAVES_RUTA_C if c not in mapa or mapa[c] is None]
    if faltan:
        raise ErrorLimite(f"faltan parámetros de la ruta C: {', '.join(faltan)} (falla cerrado: no se asume ningún valor)")
    version = mapa["ruta_c_version_api"]
    if not (isinstance(version, str) and _RE_VERSION.fullmatch(version)):
        raise ErrorValidacion(f"ruta_c_version_api: se esperaba algo como «v27.0», llegó {_ver(version)}")
    tipo = mapa["ruta_c_tipo_busqueda"]
    if tipo not in TIPOS_BUSQUEDA:
        raise ErrorValidacion(f"ruta_c_tipo_busqueda: {_ver(tipo)} no está en {TIPOS_BUSQUEDA}")
    campos = mapa["ruta_c_campos"]
    if (not isinstance(campos, (list, tuple)) or not campos
            or not all(isinstance(c, str) and _RE_CAMPO.fullmatch(c) for c in campos)):
        raise ErrorValidacion("ruta_c_campos: se esperaba una lista no vacía de nombres de campo (minúsculas y _)")
    if len(set(campos)) != len(campos):
        raise ErrorValidacion("ruta_c_campos: campos repetidos")
    ausentes = [c for c in CAMPOS_OBLIGATORIOS if c not in campos]
    if ausentes:
        raise ErrorLimite(f"ruta_c_campos: faltan campos sin los que el conversor no puede armar el crudo: {', '.join(ausentes)}")
    paises = mapa["ruta_c_paises_cobertura"]
    if (not isinstance(paises, (list, tuple)) or not paises
            or not all(isinstance(p, str) and _RE_PAIS.fullmatch(p) for p in paises)):
        raise ErrorValidacion("ruta_c_paises_cobertura: se esperaba una lista no vacía de países ISO-2 en mayúsculas "
                              "(entrecomille los códigos: en YAML «NO» se lee como falso)")
    if len(set(paises)) != len(paises):
        raise ErrorValidacion("ruta_c_paises_cobertura: países repetidos")
    reintentos = _entero("ruta_c_reintentos_tasa", mapa["ruta_c_reintentos_tasa"], 0)
    if reintentos != 0:
        # Un límite de tasa es freno, no se reintenta ni se espera: no depende de que el YAML traiga o no un `rango`.
        raise ErrorLimite(f"ruta_c_reintentos_tasa: {reintentos}; solo se admite 0 (un límite de tasa 613/429 es freno)")
    por_corrida = _entero("ruta_c_max_solicitudes_por_corrida", mapa["ruta_c_max_solicitudes_por_corrida"], 1)
    por_dia = _entero("ruta_c_max_solicitudes_por_dia", mapa["ruta_c_max_solicitudes_por_dia"], 1)
    if por_corrida > por_dia:
        raise ErrorLimite(f"ruta_c_max_solicitudes_por_corrida ({por_corrida}) no puede superar el tope diario ({por_dia})")
    return ParametrosRutaC(
        version_api=version,
        limite_pagina=_entero("ruta_c_limite_pagina", mapa["ruta_c_limite_pagina"], 1),
        max_paginas=_entero("ruta_c_max_paginas", mapa["ruta_c_max_paginas"], 1),
        pausa_ms=_entero("ruta_c_pausa_ms", mapa["ruta_c_pausa_ms"], 0),
        tiempo_max_seg=_entero("ruta_c_tiempo_max_seg", mapa["ruta_c_tiempo_max_seg"], 1),
        max_bytes_respuesta=_entero("ruta_c_max_bytes_respuesta", mapa["ruta_c_max_bytes_respuesta"], 1024),
        reintentos_tasa=reintentos,
        max_solicitudes_por_corrida=por_corrida,
        max_solicitudes_por_dia=por_dia,
        anuncios_por_archivo=_entero("ruta_c_anuncios_por_archivo", mapa["ruta_c_anuncios_por_archivo"], 1,
                                     comun.LIMITE_MAX_CONECTOR),
        tipo_busqueda=tipo,
        campos=tuple(campos),
        paises_cobertura=tuple(paises),
    )


def _rango_ok(clave: str, valor: Any, rango: Any) -> None:
    if isinstance(valor, bool) or not isinstance(valor, int):
        return
    if rango is None:  # un límite numérico sin rango aprobado no se acepta (quitarlo no debe saltarse el control)
        raise ErrorLimite(f"{clave}: falta el «rango» aprobado de un límite numérico (falla cerrado)")
    if not (isinstance(rango, (list, tuple)) and len(rango) == 2 and all(isinstance(e, int) for e in rango)):
        raise ErrorValidacion(f"{clave}: «rango» debe ser [mínimo, máximo] con enteros")
    if not rango[0] <= valor <= rango[1]:
        raise ErrorLimite(f"{clave}: {valor} fuera del rango aprobado {list(rango)} (falla cerrado)")


def cargar_parametros_ruta_c(ruta: Path | None = None) -> ParametrosRutaC:
    """Lee `parametros_ruta_c.propuesta.yaml` (o `ruta`), comprueba el `rango` de cada valor y valida el conjunto."""
    import yaml  # PyYAML está en requirements.txt de la raíz

    ruta = Path(ruta) if ruta is not None else RUTA_PARAMETROS_RUTA_C
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ErrorLimite(f"no se pudo leer {ruta}: {exc} (falla cerrado: sin parámetros no se asume ningún valor)") from exc
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise ErrorValidacion(f"{ruta}: YAML inválido ({exc})") from exc
    if not isinstance(datos, dict):
        raise ErrorValidacion(f"{ruta}: se esperaba un mapa de parámetros")
    grupos = datos.get("grupos")
    origenes = [g for g in grupos.values() if isinstance(g, dict)] if isinstance(grupos, dict) else [datos]
    valores: dict[str, Any] = {}
    for grupo in origenes:
        for clave, entrada in grupo.items():
            if isinstance(entrada, dict) and "valor" in entrada:
                if clave in valores:
                    raise ErrorValidacion(f"{ruta}: parámetro repetido: {clave}")
                _rango_ok(str(clave), entrada["valor"], entrada.get("rango"))
                valores[str(clave)] = entrada["valor"]
    return parametros_desde_mapa(valores)


# ---------------------------------------------------------------------------
# Frenos, topes y registro (mismas reglas que las rutas B y D; parámetros, no números fijos)
# ---------------------------------------------------------------------------

@contextmanager
def _cerrojo(ruta: Path) -> Iterator[None]:
    """`flock` exclusivo breve: que comprobar el tope y anotar la solicitud sea una sola operación entre procesos."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(ruta, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)  # cerrar libera el bloqueo


class Frenos:
    """Todo lo que puede decir «no» ANTES de una solicitud a la API, y el registro de cada solicitud.

      · `empresa/PAUSA` y el freno compartido `empresa/captura/freno.json` (el que escribe la captura web): si existen,
        no se hace nada (ErrorFreno, código 4). Un freno ilegible cuenta como activo (falla cerrado). Solo una persona los borra.
      · Registro `empresa/barrido/ruta_c/<corrida_id>.jsonl`: una línea `solicitud` ANTES de enviar (así una solicitud que
        muere a medias cuenta igual) y una línea `resultado` después. Nunca lleva token, URL ni texto de anuncios.
      · Tope por corrida (líneas `solicitud` de ESTA corrida) y tope diario (UTC, todas las corridas); una línea ilegible
        cuenta como solicitud. Alcanzarlos es ErrorTope (código 5) y no se envía nada. Los valores salen de los parámetros.
      · `frenar(motivo)`: escribe el freno compartido (sin pisar uno existente). Lo usa el cliente ante un límite de tasa.
    """

    def __init__(self, *, raiz: Path | None, corrida_id: str, qid: str, parametros: ParametrosRutaC,
                 ahora: Callable[[], datetime] = comun.ahora_utc) -> None:
        self._raiz = Path(raiz) if raiz is not None else None
        self._corrida_id = corrida_id
        self._qid = qid
        self._p = parametros
        self._ahora = ahora
        self._pagina = 0

    @property
    def _empresa(self) -> Path:
        return (self._raiz if self._raiz is not None else comun.RAIZ) / "empresa"

    @property
    def carpeta_registro(self) -> Path:
        return comun.dir_barrido(self._raiz) / "ruta_c"

    @property
    def ruta_registro(self) -> Path:
        return self.carpeta_registro / f"{self._corrida_id}.jsonl"

    def verificar(self) -> None:
        """PAUSA o freno compartido activos = ErrorFreno. No crea ni modifica nada."""
        if os.path.lexists(self._empresa / "PAUSA"):
            raise ErrorFreno("existe empresa/PAUSA: la ruta C no hace nada hasta que una persona la borre")
        ruta = self._empresa / "captura" / "freno.json"
        if os.path.lexists(ruta):
            try:
                info = json.loads(ruta.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                info = None
            ts = info.get("ts") if isinstance(info, dict) else None
            motivo = info.get("motivo") if isinstance(info, dict) else None
            raise ErrorFreno(
                f"freno compartido activo desde {_sanear(ts or 'fecha desconocida', largo=40)} "
                f"({_sanear(motivo or 'motivo ilegible', largo=120)}): revise y borre {ruta} a mano; el sistema nunca lo levanta solo")

    def _contar(self, hoy: str) -> tuple[int, int]:
        """(solicitudes de esta corrida, solicitudes de hoy UTC en todas las corridas)."""
        de_corrida = de_hoy = 0
        try:
            archivos = sorted(self.carpeta_registro.glob("*.jsonl"))
            for archivo in archivos:
                propio = archivo.name == self.ruta_registro.name
                for linea in archivo.read_text(encoding="utf-8", errors="replace").splitlines():
                    if not linea.strip():
                        continue
                    try:
                        obj = json.loads(linea)
                    except ValueError:
                        obj = None
                    if isinstance(obj, dict) and obj.get("tipo") != "solicitud":
                        continue  # los resultados no gastan tope
                    ts = obj.get("ts") if isinstance(obj, dict) else None
                    if propio:
                        de_corrida += 1
                    if not isinstance(ts, str) or ts.startswith(hoy):  # sin fecha fiable: se cuenta como de hoy
                        de_hoy += 1
        except OSError as exc:
            raise ErrorFreno(f"no se pudo leer el registro de solicitudes ({type(exc).__name__}): sin él no se aplican "
                             "los topes y no se envía nada") from None
        return de_corrida, de_hoy

    def antes_de_solicitar(self, pagina: int) -> None:
        """Comprueba frenos y topes y anota la solicitud. Si algo dice no, no se envía nada."""
        self.verificar()
        hoy = comun.iso_z(self._ahora())[:10]
        with _cerrojo(self.carpeta_registro / ".cerrojo"):
            de_corrida, de_hoy = self._contar(hoy)
            if de_corrida >= self._p.max_solicitudes_por_corrida:
                raise ErrorTope(f"tope por corrida alcanzado: {de_corrida} solicitudes en {self._corrida_id} "
                                f"(ruta_c_max_solicitudes_por_corrida={self._p.max_solicitudes_por_corrida})")
            if de_hoy >= self._p.max_solicitudes_por_dia:
                raise ErrorTope(f"tope diario alcanzado: {de_hoy} solicitudes hoy (UTC) "
                                f"(ruta_c_max_solicitudes_por_dia={self._p.max_solicitudes_por_dia}); se retoma mañana")
            self._pagina = pagina
            comun.anexar_jsonl(self.ruta_registro, {
                "ts": comun.iso_z(self._ahora()), "tipo": "solicitud", "corrida_id": self._corrida_id,
                "qid": self._qid, "pagina": pagina})

    def despues_de_solicitar(self, estado: str) -> None:
        comun.anexar_jsonl(self.ruta_registro, {
            "ts": comun.iso_z(self._ahora()), "tipo": "resultado", "corrida_id": self._corrida_id,
            "qid": self._qid, "pagina": self._pagina, "estado": estado})

    def frenar(self, motivo: str) -> None:
        """Escribe el freno compartido (mismo formato que la captura web). Si ya hay uno, no lo pisa."""
        ruta = self._empresa / "captura" / "freno.json"
        doc = {"ts": comun.iso_z(self._ahora()), "ad_id": f"ruta_c:{self._qid}", "motivo": _sanear(motivo, largo=300)}
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            return
        except OSError as exc:
            raise ErrorFreno(f"no se pudo escribir el freno compartido ({type(exc).__name__})") from None
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(doc, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Transporte (inyectable)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Respuesta:
    estado: int
    cuerpo: bytes


class Transporte:
    """Interfaz del transporte: UNA solicitud GET por llamada. Las pruebas inyectan un doble; el real es `TransporteHTTP`.

    `parametros` incluye `access_token`: el transporte NO debe registrarlo ni incluirlo en mensajes de error.
    """

    def solicitar(self, url: str, parametros: Mapping[str, str], *, tiempo_max_seg: int, max_bytes: int) -> Respuesta:
        raise NotImplementedError


class _SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None  # una redirección es anómala en la Graph API: se informa, no se sigue


class TransporteHTTP(Transporte):
    """Transporte real con `urllib`: solo https a `graph.facebook.com`, sin redirecciones, con tiempo y bytes acotados.

    Ni la URL (lleva el token en la consulta) ni el cuerpo se incluyen jamás en un mensaje de error.
    """

    def __init__(self, abridor: Any = None) -> None:
        self._abridor = abridor  # solo para pruebas: objeto con `.open(request, timeout=...)`

    def solicitar(self, url: str, parametros: Mapping[str, str], *, tiempo_max_seg: int, max_bytes: int) -> Respuesta:
        partes = urlsplit(url)
        if (partes.scheme != "https" or partes.hostname != HOST_API or partes.port not in (None, 443)
                or partes.username or partes.password or partes.query or partes.fragment):
            raise ErrorUso(f"el transporte solo llama a https://{HOST_API}/..., sin consulta ni credenciales en la URL")
        peticion = urllib.request.Request(
            f"{url}?{urlencode(parametros)}", method="GET",
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        abridor = self._abridor or urllib.request.build_opener(_SinRedireccion)
        try:
            with abridor.open(peticion, timeout=tiempo_max_seg) as r:
                estado, cuerpo = int(r.status), r.read(max_bytes + 1)
        except urllib.error.HTTPError as exc:  # Graph responde 4xx/5xx con un JSON de error en el cuerpo
            try:
                estado, cuerpo = int(exc.code), exc.read(max_bytes + 1)
            except OSError:
                estado, cuerpo = int(exc.code), b""
            finally:
                exc.close()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ErrorServicio(f"fallo de red al llamar a la API ({type(exc).__name__})") from None
        if len(cuerpo) > max_bytes:
            raise ErrorRespuesta(f"la respuesta supera el tope de {max_bytes} bytes (ruta_c_max_bytes_respuesta)")
        return Respuesta(estado, cuerpo)


# ---------------------------------------------------------------------------
# Consulta y cliente
# ---------------------------------------------------------------------------

def _digitos(valor: Any, campo: str) -> str:
    if isinstance(valor, bool) or not isinstance(valor, (int, str)):
        raise ErrorUso(f"{campo}: se esperaba un id numérico, llegó {_ver(valor)}")
    texto = str(valor)
    if _RE_DIGITOS.fullmatch(texto) is None:
        raise ErrorUso(f"{campo}: se esperaba una cadena de dígitos, llegó {_ver(valor)}")
    return texto


def normalizar_consulta(consulta: Any, p: ParametrosRutaC) -> dict[str, Any]:
    """Valida una consulta con las claves de CONTRATO §2 (`search_terms`, `countries`, `ad_active_status`, `limit`,
    `page_ids`) y la devuelve normalizada. `limit` es opcional: tope de anuncios por archivo (nunca mayor que
    `ruta_c_anuncios_por_archivo`). Errores de uso = ErrorUso (2)."""
    if not isinstance(consulta, Mapping):
        raise ErrorUso("la consulta debe ser un mapa con search_terms, countries, ad_active_status[, limit, page_ids]")
    permitidas = {"search_terms", "countries", "ad_active_status", "limit", "page_ids"}
    sobran = sorted(set(consulta) - permitidas)
    if sobran:
        raise ErrorUso(f"claves desconocidas en la consulta: {', '.join(map(str, sobran))}")
    faltan = [k for k in ("search_terms", "countries", "ad_active_status") if k not in consulta]
    if faltan:
        raise ErrorUso(f"faltan claves en la consulta: {', '.join(faltan)}")
    paises = consulta["countries"]
    if not (isinstance(paises, (list, tuple)) and len(paises) == 1
            and isinstance(paises[0], str) and _RE_PAIS.fullmatch(paises[0])):
        raise ErrorUso(f"countries: se esperaba UN país ISO-2 en mayúsculas (un país por consulta), llegó {_ver(paises)}")
    pais = paises[0]
    if pais not in p.paises_cobertura:
        raise ErrorUso(
            f"{pais} está fuera de la cobertura comercial de la API (ruta_c_paises_cobertura): ahí `ads_archive` solo devuelve "
            "anuncios sobre temas sociales, elecciones o política, no ofertas. Use el conector o la ruta D para ese país")
    estado = consulta["ad_active_status"]
    if estado not in comun.ESTADOS_ANUNCIO:
        raise ErrorUso(f"ad_active_status: {_ver(estado)} no está en {comun.ESTADOS_ANUNCIO}")
    terminos = consulta["search_terms"]
    if terminos is not None and not isinstance(terminos, str):
        raise ErrorUso("search_terms: se esperaba texto o null")
    if terminos is not None and len(terminos) > TERMINOS_MAX:
        raise ErrorUso(f"search_terms: {len(terminos)} caracteres; la API admite {TERMINOS_MAX} o menos")
    ids = consulta.get("page_ids")
    if ids is not None:
        if not isinstance(ids, (list, tuple)) or not ids:
            raise ErrorUso("page_ids: se esperaba null o una lista no vacía")
        if len(ids) > PAGE_IDS_MAX:
            raise ErrorUso(f"page_ids: {len(ids)} ids; la API admite {PAGE_IDS_MAX} por consulta (parta la lista)")
        ids = [_digitos(i, f"page_ids[{n}]") for n, i in enumerate(ids)]
        if len(set(ids)) != len(ids):
            raise ErrorUso("page_ids: ids repetidos")
    if (terminos is None or not terminos.strip()) and ids is None:
        raise ErrorUso("search_terms vacío y sin page_ids: la consulta no buscaría nada")
    limite = p.anuncios_por_archivo
    if consulta.get("limit") is not None:
        limite = min(limite, _entero("limit", consulta["limit"], 1, comun.LIMITE_MAX_CONECTOR))
    return {"search_terms": terminos, "countries": [pais], "ad_active_status": estado, "limit": limite, "page_ids": ids}


@dataclass
class Resultado:
    """Lo recibido de la API para una consulta (anuncios tal como llegan, sin duplicados y sin token)."""

    consulta: dict[str, Any]
    anuncios: list[dict[str, Any]] = field(default_factory=list)
    paginas: int = 0
    completo: bool = True
    motivo_corte: str | None = None  # None | "tope_paginas" | "error_tasa" | "error_token" | "error_acceso" | ...
    duplicados: int = 0


def _rechazar_constante(nombre: str) -> Any:
    raise ValueError(f"constante JSON no permitida: {nombre}")


def _motivo(exc: BaseException) -> str:
    return {ErrorTasa: "error_tasa", ErrorTokenInvalido: "error_token", ErrorAcceso: "error_acceso",
            ErrorServicio: "error_servicio", ErrorRespuesta: "error_respuesta", ErrorFreno: "freno",
            ErrorTope: "tope"}.get(type(exc), "error")


_ESTADO_REGISTRO = {ErrorTokenInvalido: "token", ErrorAcceso: "acceso", ErrorServicio: "servicio",
                    ErrorRespuesta: "respuesta"}  # estado de la línea `resultado` del registro


class ClienteBiblioteca:
    """Cliente de `ads_archive`. Un objeto = un token + un transporte + parámetros. No guarda nada en disco."""

    def __init__(self, transporte: Transporte, token: Secreto, parametros: ParametrosRutaC, frenos: Any,
                 *, dormir: Callable[[float], None] = time.sleep) -> None:
        if not isinstance(token, Secreto):
            raise ErrorUso("el token debe venir de leer_token() (envuelto en Secreto)")
        self._transporte = transporte
        self._token = token
        self._p = parametros
        self._frenos = frenos  # `Frenos` (o un doble con sus tres métodos): obligatorio, no hay cliente sin frenos
        self._dormir = dormir
        self._url = f"https://{HOST_API}/{parametros.version_api}/{ENDPOINT}"

    def __repr__(self) -> str:
        return f"ClienteBiblioteca(version={self._p.version_api!r}, token=Secreto(***))"

    # -- una solicitud ------------------------------------------------------
    def _parametros_base(self, q: Mapping[str, Any]) -> dict[str, str]:
        base = {
            "ad_type": TIPO_ANUNCIO,
            "ad_reached_countries": json.dumps(q["countries"]),
            "ad_active_status": q["ad_active_status"],
            "search_type": self._p.tipo_busqueda,
            "fields": ",".join(self._p.campos),
            "limit": str(self._p.limite_pagina),
        }
        if q["search_terms"] is not None:
            base["search_terms"] = q["search_terms"]
        if q["page_ids"] is not None:
            base["search_page_ids"] = json.dumps([int(i) for i in q["page_ids"]])
        return base

    def _error_de_api(self, err: Mapping[str, Any], estado: int) -> ErrorFabrica:
        codigo = err.get("code")
        if isinstance(codigo, str) and codigo.isdigit():
            codigo = int(codigo)
        if isinstance(codigo, bool) or not isinstance(codigo, int):
            codigo = None
        detalle = f" (Meta dice: «{_sanear(err.get('message', ''), self._token)}»)" if err.get("message") else ""
        if codigo in CODIGOS_TOKEN:
            return ErrorTokenInvalido(
                f"Meta rechazó el token (código {codigo}): inválido, vencido o identidad sin confirmar en facebook.com/ID. "
                f"Genere uno nuevo y vuelva a exportar {VARIABLE_TOKEN}{detalle}")
        if codigo in CODIGOS_TASA or estado == 429:
            return ErrorTasa(f"límite de tasa de Meta (código {codigo}, HTTP {estado}){detalle}")
        if codigo in CODIGOS_ACCESO or estado == 403:
            return ErrorAcceso(
                f"Meta niega el acceso a la API (código {codigo}, HTTP {estado}): confirme la identidad en facebook.com/ID "
                f"y que la app pueda leer la Biblioteca de Anuncios{detalle}")
        if codigo == 100:
            return ErrorRespuesta(f"Meta rechazó un parámetro (código 100): revise ruta_c_campos y la consulta{detalle}")
        if estado >= 500 or codigo in (1, 2):
            return ErrorServicio(f"error del servicio de Meta (código {codigo}, HTTP {estado}){detalle}")
        return ErrorRespuesta(f"error de la API no previsto (código {codigo}, HTTP {estado}){detalle}")

    def _interpretar(self, resp: Respuesta) -> Mapping[str, Any]:
        doc: Any = None
        try:
            doc = json.loads(resp.cuerpo.decode("utf-8"), parse_float=str, parse_constant=_rechazar_constante)
        except (UnicodeDecodeError, ValueError):
            doc = None
        if isinstance(doc, dict) and isinstance(doc.get("error"), dict):
            raise self._error_de_api(doc["error"], resp.estado)
        if resp.estado == 429:
            raise ErrorTasa("límite de tasa de Meta (HTTP 429)")
        if resp.estado == 401:
            raise ErrorTokenInvalido(f"Meta rechazó el token (HTTP 401): genere uno nuevo y vuelva a exportar {VARIABLE_TOKEN}")
        if resp.estado == 403:
            raise ErrorAcceso("Meta niega el acceso a la API (HTTP 403): confirme la identidad en facebook.com/ID "
                              "y que la app pueda leer la Biblioteca de Anuncios")
        if resp.estado >= 500:
            raise ErrorServicio(f"error del servicio de Meta (HTTP {resp.estado})")
        if not 200 <= resp.estado < 300:
            raise ErrorRespuesta(f"respuesta inesperada de la API (HTTP {resp.estado})")
        if doc is None:
            raise ErrorRespuesta("la respuesta no es JSON válido")
        if not isinstance(doc, dict):
            raise ErrorRespuesta("la respuesta debería ser un objeto JSON")
        return doc

    def _pedir(self, base: Mapping[str, str], cursor: str | None, pagina: int) -> Mapping[str, Any]:
        parametros = dict(base)
        if cursor is not None:
            parametros["after"] = cursor
        parametros["access_token"] = self._token.revelar()
        self._frenos.antes_de_solicitar(pagina)  # PAUSA, freno compartido, topes y registro
        try:
            resp = self._transporte.solicitar(
                self._url, parametros, tiempo_max_seg=self._p.tiempo_max_seg, max_bytes=self._p.max_bytes_respuesta)
            doc = self._interpretar(resp)
        except ErrorTasa as exc:  # límite de tasa = FRENO: sin reintento ni espera; el freno compartido queda escrito
            self._frenos.despues_de_solicitar("tasa")
            self._frenos.frenar(str(exc))
            raise
        except _ConParcial as exc:
            self._frenos.despues_de_solicitar(_ESTADO_REGISTRO.get(type(exc), "error"))
            raise
        self._frenos.despues_de_solicitar("ok")
        return doc

    def _pagina(self, doc: Mapping[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
        datos = doc.get("data")
        if not isinstance(datos, list) or not all(isinstance(a, dict) for a in datos):
            raise ErrorRespuesta("la respuesta no trae `data` como lista de anuncios")
        paging = doc.get("paging")
        siguiente = None
        if isinstance(paging, Mapping) and paging.get("next"):
            cursores = paging.get("cursors")
            siguiente = cursores.get("after") if isinstance(cursores, Mapping) else None
            if not (isinstance(siguiente, str) and siguiente):
                raise ErrorRespuesta("hay página siguiente pero la respuesta no trae el cursor `after`")
        # `paging.next` se descarta a propósito: lleva el access_token en la URL.
        limpios = []
        for a in datos:
            a = dict(a)
            if isinstance(a.get("ad_snapshot_url"), str):
                a["ad_snapshot_url"] = quitar_token_de_url(a["ad_snapshot_url"])
            limpios.append(a)
        return limpios, siguiente

    # -- búsqueda paginada --------------------------------------------------
    def buscar(self, consulta: Mapping[str, Any]) -> Resultado:
        """Recorre las páginas de la consulta hasta que no haya `next` o se alcance `ruta_c_max_paginas`.

        Pausa `ruta_c_pausa_ms` entre solicitudes (no antes de la primera). Si una solicitud falla después de haber
        recibido anuncios, el error lleva `.parcial` (un `Resultado` con `completo=False`) para no perder lo pagado.
        """
        q = normalizar_consulta(consulta, self._p)
        base = self._parametros_base(q)
        res = Resultado(consulta=q)
        vistos: set[str] = set()
        cursores: set[str] = set()
        cursor: str | None = None
        while True:
            if res.paginas > 0:
                self._dormir(self._p.pausa_ms / 1000)
            try:
                doc = self._pedir(base, cursor, res.paginas + 1)
                datos, cursor = self._pagina(doc)
            except _ConParcial as exc:
                if res.paginas > 0 and exc.parcial is None:
                    res.completo, res.motivo_corte = False, _motivo(exc)
                    exc.parcial = res
                raise
            res.paginas += 1
            for a in datos:
                ident = a.get("id")
                if isinstance(ident, str) and ident in vistos:
                    res.duplicados += 1
                    continue
                if isinstance(ident, str):
                    vistos.add(ident)
                res.anuncios.append(a)
            if cursor is None:
                return res
            if cursor in cursores:
                error = ErrorRespuesta("la API repitió un cursor: se corta para no girar en círculo")
                res.completo, res.motivo_corte = False, "error_respuesta"
                error.parcial = res
                raise error
            cursores.add(cursor)
            if res.paginas >= self._p.max_paginas:
                res.completo, res.motivo_corte = False, "tope_paginas"
                return res


# ---------------------------------------------------------------------------
# Conversión al crudo de CONTRATO §2 (+ extra)
# ---------------------------------------------------------------------------

def iso_a_epoch(valor: Any, campo: str = "fecha") -> int:
    """Fecha ISO de la API (`2026-11-05`, `2026-11-05T10:00:00+0000`, `...Z`, `...+02:00`) a epoch en SEGUNDOS (UTC).

    Solo fecha = medianoche UTC; sin zona = UTC (la referencia dice que las horas de la API son UTC). Otra cosa = ErrorValidacion.
    """
    m = _RE_ISO.fullmatch(valor.strip()) if isinstance(valor, str) else None
    if m is None:
        raise ErrorValidacion(f"{campo}: fecha ISO esperada (AAAA-MM-DD[THH:MM:SS[Z|±hh[:mm]]]), llegó {_ver(valor)}")
    a, mes, d, h, mi, s, zona = m.groups()
    try:
        instante = datetime(int(a), int(mes), int(d), int(h or 0), int(mi or 0), int(s or 0), tzinfo=timezone.utc)
        if zona and zona != "Z":
            cifras = zona[1:].replace(":", "")
            hh, mm = int(cifras[:2]), int(cifras[2:4] or 0)
            if hh > 23 or mm > 59:
                raise ValueError("desfase horario fuera de rango")
            instante -= (1 if zona[0] == "+" else -1) * timedelta(hours=hh, minutes=mm)
    except (ValueError, OverflowError) as exc:
        raise ErrorValidacion(f"{campo}: fecha inexistente {_ver(valor)} ({exc})") from exc
    epoch = int(instante.timestamp())
    if not 1 <= epoch < comun.EPOCH_S_MAX_EXCLUSIVO:
        raise ErrorValidacion(f"{campo}: {_ver(valor)} cae fuera del rango de epoch en segundos")
    return epoch


def _lista_textos(a: Mapping[str, Any], clave: str) -> list[str] | None:
    valor = a.get(clave)
    if valor is None:
        return None
    if not isinstance(valor, list) or not all(isinstance(t, str) for t in valor):
        raise ErrorValidacion(f"{clave}: se esperaba una lista de textos, llegó {_ver(valor)}")
    return list(valor)


def _sin_float(valor: Any, camino: str) -> Any:
    if isinstance(valor, (float, Decimal)):
        raise ErrorValidacion(f"{camino}: número decimal no persistible")
    if isinstance(valor, list):
        return [_sin_float(v, f"{camino}[{i}]") for i, v in enumerate(valor)]
    if isinstance(valor, dict):
        return {str(k): _sin_float(v, f"{camino}.{k}") for k, v in valor.items()}
    return valor


def _convertir_anuncio(a: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Un anuncio de la API -> (anuncio del crudo, extra). ErrorValidacion con el campo exacto si algo falta o es raro."""
    ident = a.get("id")
    if isinstance(ident, int) and not isinstance(ident, bool):
        ident = str(ident)
    if not (isinstance(ident, str) and _RE_DIGITOS.fullmatch(ident)):
        raise ErrorValidacion(f"id: cadena de dígitos esperada, llegó {_ver(a.get('id'))}")
    pid = a.get("page_id")
    if isinstance(pid, int) and not isinstance(pid, bool):
        pid = str(pid)
    if not (isinstance(pid, str) and _RE_DIGITOS.fullmatch(pid)):
        raise ErrorValidacion(f"page_id: cadena de dígitos esperada, llegó {_ver(a.get('page_id'))}")
    nombre = a.get("page_name")
    if not isinstance(nombre, str):
        raise ErrorValidacion(f"page_name: texto esperado, llegó {_ver(nombre)}")
    url = a.get("ad_snapshot_url")
    if not isinstance(url, str):
        raise ErrorValidacion(f"ad_snapshot_url: texto esperado, llegó {_ver(url)}")
    try:
        ids_url = parse_qs(urlsplit(url).query).get("id", [])
    except ValueError as exc:
        raise ErrorValidacion(f"ad_snapshot_url: URL malformada ({exc})") from exc
    if ids_url != [ident]:
        raise ErrorValidacion(
            f"integridad: el id de ad_snapshot_url ({_ver(ids_url)}) no coincide con id={ident}")
    inicio_original = a.get("ad_delivery_start_time")
    inicio = iso_a_epoch(inicio_original, "ad_delivery_start_time")
    titulos = _lista_textos(a, "ad_creative_link_titles")
    # La API OMITE la lista cuando el anuncio no tiene título de enlace; el conector da «» en ese caso (contrato: puede ser «»).
    titulo = next((t for t in (titulos or []) if t != ""), "")
    moneda = a.get("currency")
    if moneda is None:
        moneda, origen_moneda = MONEDA_SIN_DATO, "sin_dato"
    elif isinstance(moneda, str) and _RE_MONEDA.fullmatch(moneda):
        origen_moneda = "api"
    else:
        raise ErrorValidacion(f"currency: 3 letras mayúsculas esperadas, llegó {_ver(moneda)}")
    crudo: dict[str, Any] = {
        "id": ident, "page_id": int(pid), "page_name": nombre, "ad_creative_link_title": titulo,
    }
    if a.get("ad_creation_time") is not None:
        crudo["ad_creation_time"] = iso_a_epoch(a["ad_creation_time"], "ad_creation_time")
    crudo.update({"ad_delivery_start_time": inicio, "currency": moneda, "ad_snapshot_url": URL_FICHA.format(ident)})

    fin = a.get("ad_delivery_stop_time")
    alcance = a.get("eu_total_reach")
    if alcance is not None:
        if isinstance(alcance, str) and _RE_DIGITOS.fullmatch(alcance):
            alcance = int(alcance)
        if isinstance(alcance, bool) or not isinstance(alcance, int) or alcance < 0:
            raise ErrorValidacion(f"eu_total_reach: entero ≥ 0 esperado, llegó {_ver(alcance)}")
    extra: dict[str, Any] = {
        "cuerpos": _lista_textos(a, "ad_creative_bodies"),
        "titulos": titulos,
        "descripciones": _lista_textos(a, "ad_creative_link_descriptions"),
        "captions": _lista_textos(a, "ad_creative_link_captions"),
        "inicio_original": inicio_original,
        "fin": iso_a_epoch(fin, "ad_delivery_stop_time") if fin else None,
        "plataformas": _lista_textos(a, "publisher_platforms"),
        "idiomas": _lista_textos(a, "languages"),
        "alcance_ue": alcance,
        "alcance_por_ubicacion": _sin_float(a.get("total_reach_by_location"), "total_reach_by_location"),
        "edades_objetivo": _lista_textos(a, "target_ages"),
        "genero_objetivo": a.get("target_gender") if isinstance(a.get("target_gender"), (str, list)) else None,
        "ubicaciones_objetivo": _sin_float(a.get("target_locations"), "target_locations"),
        "beneficiarios_pagadores": _sin_float(a.get("beneficiary_payers"), "beneficiary_payers"),
        "moneda_origen": origen_moneda,
    }
    return crudo, extra


@dataclass(frozen=True)
class Paquete:
    """Un archivo crudo ya validado y su extra, listos para escribir."""

    qid: str
    crudo: dict[str, Any]
    extra: dict[str, Any]


def convertir(resultado: Resultado, *, corrida_id: str, qid: str, capturado_en: str, parametros: ParametrosRutaC,
              descartar_invalidos: bool = False) -> list[Paquete]:
    """Convierte un `Resultado` en uno o más `Paquete` (crudo de CONTRATO §2 validado con `comun.validar_crudo` + extra).

    Un anuncio inválido (falta un campo, id y URL no coinciden...) es ErrorValidacion con su posición; con
    `descartar_invalidos=True` se omite y queda anotado en `paginacion.descartados` de cada extra (nunca se rellena
    con un valor inventado). Más de `consulta.limit` anuncios = varios archivos `<qid>-cNN`.
    """
    if not comun.corrida_id_valido(corrida_id):
        raise ErrorUso(f"corrida_id inválido {_ver(corrida_id)}")
    if not comun.qid_valido(qid):
        raise ErrorUso(f"qid inválido {_ver(qid)}: kebab-case ASCII")
    q = resultado.consulta
    tam = q["limit"]
    convertidos: list[tuple[dict[str, Any], dict[str, Any]]] = []
    descartados: list[dict[str, str]] = []
    for i, a in enumerate(resultado.anuncios):
        try:
            convertidos.append(_convertir_anuncio(a))
        except ErrorValidacion as exc:
            ident = a.get("id") if isinstance(a, Mapping) else None
            if not descartar_invalidos:
                raise ErrorValidacion(f"anuncio #{i} (id={_ver(ident)}): {exc}") from exc
            descartados.append({"id": str(ident), "motivo": _sanear(exc)})
    trozos = [convertidos[k:k + tam] for k in range(0, len(convertidos), tam)] or [[]]
    ancho = max(2, len(str(len(trozos))))
    paquetes: list[Paquete] = []
    for n, trozo in enumerate(trozos, start=1):
        qid_n = qid if len(trozos) == 1 else f"{qid}-c{n:0{ancho}d}"
        if not comun.qid_valido(qid_n):
            raise ErrorUso(f"qid derivado inválido {_ver(qid_n)}: acorte el qid")
        anuncios = [c for c, _ in trozo]
        # Resultado incompleto: el último archivo declara limit = len(ads) (y total null) para que la ingesta lo
        # reconozca como «llegó a su límite con más resultados» y marque el conteo como piso, no como total.
        limite_n = len(anuncios) if (not resultado.completo and n == len(trozos) and anuncios) else tam
        crudo = comun.validar_crudo({
            "schema_version": comun.VERSION_ESQUEMA, "corrida_id": corrida_id, "qid": qid_n,
            "consulta": {"search_terms": q["search_terms"], "countries": list(q["countries"]),
                         "ad_active_status": q["ad_active_status"], "limit": limite_n, "page_ids": q["page_ids"]},
            "capturado_en": capturado_en, "ruta": "C",
            # La API no da total. Si la paginación terminó, el archivo es un trozo completo de la consulta y declara
            # su propio total; si se cortó, null (el extra dice `completo: false`).
            "estimated_total_count": len(anuncios) if resultado.completo else None,
            "ads": anuncios,
        }, origen=f"ruta C {qid_n}")
        extra = {
            "schema_version": comun.VERSION_ESQUEMA, "corrida_id": corrida_id, "qid": qid_n, "qid_origen": qid,
            "ruta": "C", "fuente": ENDPOINT, "version_api": parametros.version_api, "capturado_en": capturado_en,
            "fragmento": {"numero": n, "de": len(trozos)},
            "consulta_api": {
                "ad_type": TIPO_ANUNCIO, "ad_reached_countries": list(q["countries"]),
                "ad_active_status": q["ad_active_status"], "search_terms": q["search_terms"],
                "search_page_ids": q["page_ids"], "search_type": parametros.tipo_busqueda,
                "campos": list(parametros.campos), "limite_pagina": parametros.limite_pagina,
            },
            "paginacion": {
                "paginas_leidas": resultado.paginas, "completo": resultado.completo,
                "motivo_corte": resultado.motivo_corte, "anuncios_recibidos": len(resultado.anuncios) + resultado.duplicados,
                "duplicados_omitidos": resultado.duplicados, "anuncios_convertidos_total": len(convertidos),
                "descartados": descartados,
            },
            "anuncios": {c["id"]: e for c, e in trozo},
        }
        paquetes.append(Paquete(qid_n, crudo, extra))
    return paquetes


# ---------------------------------------------------------------------------
# Escritura y orquestación
# ---------------------------------------------------------------------------

def _contiene(valor: Any, aguja: str) -> bool:
    """¿Algún texto (valor o clave) de `valor` contiene `aguja`? Recorre listas y mapas, sin serializar."""
    if isinstance(valor, str):
        return aguja in valor
    if isinstance(valor, Mapping):
        return any(_contiene(k, aguja) or _contiene(v, aguja) for k, v in valor.items())
    if isinstance(valor, (list, tuple)):
        return any(_contiene(v, aguja) for v in valor)
    return False


def _verificar_sin_secreto(doc: Any, token: Secreto | None, destino: str) -> None:
    """Falla cerrado si algún texto contiene el valor EXACTO del token. Solo el valor exacto: un anuncio ajeno con
    «access_token=abc» en su texto es un dato más y no debe hacer perder la consulta entera."""
    if token is not None and _contiene(doc, token.revelar()):
        raise ErrorValidacion(f"{destino}: el contenido incluye el valor del token de acceso; no se escribe (falla cerrado)")


def escribir(paquetes: Sequence[Paquete], *, corrida_id: str, raiz: Path | None = None,
             token: Secreto | None = None) -> list[Path]:
    """Escribe `<qid>.json` (crudo) y luego `<qid>.extra.json` por paquete, atómico y SIN sobrescribir (ErrorUso si existe).

    Comprueba ANTES de escribir que ningún destino exista y que ningún contenido lleve un token. Orden: crudo y después
    extra, así una interrupción deja a lo sumo un crudo sin extra (inofensivo), nunca un extra huérfano.
    """
    carpeta = comun.dir_crudo(corrida_id, raiz)
    destinos: list[tuple[Path, Any]] = []
    for p in paquetes:
        destinos.append((carpeta / f"{p.qid}.json", p.crudo))
        destinos.append((carpeta / f"{p.qid}.extra.json", p.extra))
    for ruta, doc in destinos:
        if os.path.lexists(ruta):
            raise ErrorUso(f"{ruta} ya existe: no se sobrescriben artefactos (use otro qid o corrida)")
        _verificar_sin_secreto(doc, token, ruta.name)
    escritos: list[Path] = []
    for p in paquetes:
        for ruta in (carpeta / f"{p.qid}.json", carpeta / f"{p.qid}.extra.json"):
            doc = p.crudo if ruta.name == f"{p.qid}.json" else p.extra
            comun.escribir_json_nuevo(ruta, doc)
            escritos.append(ruta)
    return escritos


def _exigir_raiz_oficial(raiz: Path | None) -> None:
    """Con FABRICA_ENTORNO=produccion no se acepta otra raíz: reiniciaría topes, registro y frenos (hallazgo M1)."""
    if raiz is None or (os.environ.get("FABRICA_ENTORNO") or "desarrollo").strip() != "produccion":
        return
    if Path(raiz).resolve() != Path(comun.RAIZ).resolve():
        raise ErrorUso("raiz= no existe con FABRICA_ENTORNO=produccion: topes, registro y frenos viven en la raíz del repositorio")


def barrer_consulta(consulta: Mapping[str, Any], *, corrida_id: str, qid: str, transporte: Transporte,
                    parametros: ParametrosRutaC, entorno: Mapping[str, str] | None = None, raiz: Path | None = None,
                    ahora: Callable[[], datetime] = comun.ahora_utc, dormir: Callable[[float], None] = time.sleep,
                    descartar_invalidos: bool = False) -> list[Path]:
    """Una consulta completa: token -> búsqueda paginada -> conversión -> archivos. Devuelve las rutas escritas.

    Falla cerrado ANTES de cualquier solicitud si existe `empresa/PAUSA` o el freno compartido, si falta el token,
    si el corrida_id/qid es inválido o la consulta no es válida. Si la API falla a mitad de camino y ya había anuncios, se escribe lo recibido (marcado `completo: false`)
    y se relanza el error con `.parcial` y `.archivos`: quien orquesta debe DETENER el resto de consultas (freno).
    Un límite de tasa además deja escrito el freno compartido, así que ninguna consulta siguiente (de ninguna ruta) corre.
    """
    if not comun.corrida_id_valido(corrida_id):
        raise ErrorUso(f"corrida_id inválido {_ver(corrida_id)}")
    if not comun.qid_valido(qid):
        raise ErrorUso(f"qid inválido {_ver(qid)}: kebab-case ASCII")
    _exigir_raiz_oficial(raiz)
    frenos = Frenos(raiz=raiz, corrida_id=corrida_id, qid=qid, parametros=parametros, ahora=ahora)
    frenos.verificar()  # PAUSA o freno compartido: no se hace nada, ni siquiera se pide el token
    token = leer_token(entorno)
    cliente = ClienteBiblioteca(transporte, token, parametros, frenos, dormir=dormir)
    capturado_en = comun.iso_z(ahora())
    try:
        resultado = cliente.buscar(consulta)
    except _ConParcial as exc:
        if exc.parcial is not None and exc.parcial.anuncios:
            paquetes = convertir(exc.parcial, corrida_id=corrida_id, qid=qid, capturado_en=capturado_en,
                                 parametros=parametros, descartar_invalidos=True)
            exc.archivos = tuple(escribir(paquetes, corrida_id=corrida_id, raiz=raiz, token=token))
        raise
    paquetes = convertir(resultado, corrida_id=corrida_id, qid=qid, capturado_en=capturado_en, parametros=parametros,
                         descartar_invalidos=descartar_invalidos)
    return escribir(paquetes, corrida_id=corrida_id, raiz=raiz, token=token)
