"""``ClienteMeta``: cliente mínimo de la Marketing API sobre un :class:`engine.transporte.Transporte`.

Nunca abre una conexión por su cuenta (convenciones §4.1/§9): en pruebas y en ``modo=fixture``
recibe un :class:`~engine.transporte.TransporteFixture`; en vivo, el cliente HTTP real lo inyecta
quien construye el ``ClienteMeta`` (``meta.crear``, ``meta.activar``…). Responsabilidades propias
de este módulo (backbone §5, docs/06 §4.5):

* ``appsecret_proof`` en toda llamada (prueba de posesión del *app secret*, exigida por Meta cuando
  la app la tiene activada).
* Reintento con espera exponencial ante el error **613** (``"Calls to this api have exceeded the
  rate limit"``) hasta un tope técnico; cualquier otro error de Meta es ``ErrorExterno`` sin reintento
  (los reintentos son solo para fallas transitorias conocidas, convenciones §7).
* Ritmo de **ediciones** (``cambiar_estado``, ``cambiar_presupuesto``): al menos
  ``segundos_min_entre_ediciones`` entre dos ediciones del MISMO objeto y como máximo
  ``max_cambios_presupuesto_por_hora`` ediciones por objeto en la última hora. Estos dos números los
  pasa quien construye el cliente (normalmente los mismos valores de
  ``limites.segundos_min_entre_ediciones`` y ``limites.max_cambios_presupuesto_por_hora_por_conjunto``
  que ``engine.guard`` ya exige en el paso 5): es una segunda defensa local, no una reimplementación
  del tope de negocio (ese lo decide siempre ``engine.guard.comprobar_live``).

Las lecturas (``GET``) no pasan por el control de ritmo: solo las ediciones cuentan (crear un
objeto nuevo tampoco cuenta: el ritmo es sobre un ``object_id`` que ya existe).
"""
from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlencode

from engine import comun
from engine.errores import ErrorExterno, ErrorLimite, ErrorValidacion
from engine.transporte import Transporte

__all__ = ["ClienteMeta"]

_VERSION_POR_DEFECTO = "v21.0"
_BASE_URL_POR_DEFECTO = "https://graph.facebook.com"
_CODIGO_613 = 613  # "Calls to this api have exceeded the rate limit" (Graph API)
# Política técnica de reintento ante un error transitorio conocido (613): no es un tope de negocio
# (esos viven en limites.yaml); es análogo a engine.comun._TIMEOUT_SUBPROCESO_S.
_REINTENTOS_613_MAX = 5
_ESPERA_613_BASE_S = 1
_UNA_HORA = timedelta(hours=1)


def _dormir_real(segundos: float) -> None:
    time.sleep(segundos)


@dataclass
class ClienteMeta:
    """Cliente de la Marketing API sobre un ``Transporte`` inyectado (nunca abre red por su cuenta).

    ``segundos_min_entre_ediciones`` y ``max_cambios_presupuesto_por_hora`` son obligatorios: quien
    construye el cliente los trae de ``limites.yaml`` (fail-closed: sin ellos no se editan objetos).
    """

    transporte: Transporte
    token: str
    app_secret: str
    segundos_min_entre_ediciones: int
    max_cambios_presupuesto_por_hora: int
    version: str = _VERSION_POR_DEFECTO
    base_url: str = _BASE_URL_POR_DEFECTO
    ahora: Callable[[], datetime] = comun.ahora_utc
    dormir: Callable[[float], None] = _dormir_real
    reintentos_613_max: int = _REINTENTOS_613_MAX
    espera_613_base_s: float = _ESPERA_613_BASE_S
    _historial_ediciones: dict[str, list[datetime]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.transporte, Transporte):
            raise ErrorValidacion("ClienteMeta exige un Transporte inyectado")
        for nombre in ("token", "app_secret"):
            if not getattr(self, nombre) or not str(getattr(self, nombre)).strip():
                raise ErrorValidacion(f"ClienteMeta: falta {nombre}")
        for nombre in ("segundos_min_entre_ediciones", "max_cambios_presupuesto_por_hora"):
            v = getattr(self, nombre)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise ErrorValidacion(f"ClienteMeta: {nombre} debe ser un entero >= 0 (viene de limites.yaml)")

    # ------------------------------------------------------------------------------------------
    # Firma de la llamada
    # ------------------------------------------------------------------------------------------
    def _appsecret_proof(self) -> str:
        """HMAC-SHA256(clave=app_secret, mensaje=token) en hexadecimal (requerido por Meta con App Secret Proof)."""
        return hmac.new(self.app_secret.encode("utf-8"), self.token.encode("utf-8"), hashlib.sha256).hexdigest()

    def _url(self, ruta: str) -> str:
        if ruta.startswith("http://") or ruta.startswith("https://"):
            raise ErrorValidacion("ClienteMeta: la ruta debe ser relativa (sin esquema), no una URL absoluta")
        return f"{self.base_url}/{self.version}/{ruta.lstrip('/')}"

    def _parametros_firmados(self, extra: Mapping[str, Any] | None) -> dict[str, str]:
        base = {"access_token": self.token, "appsecret_proof": self._appsecret_proof()}
        for k, v in (extra or {}).items():
            base[k] = "true" if v is True else "false" if v is False else str(v)
        return base

    # ------------------------------------------------------------------------------------------
    # GET / POST con reintento ante 613
    # ------------------------------------------------------------------------------------------
    def _solicitar(self, metodo: str, ruta: str, *, parametros: Mapping[str, Any] | None = None,
                   cuerpo: Mapping[str, Any] | None = None) -> dict[str, Any]:
        intentos = 0
        while True:
            if metodo == "GET":
                url = self._url(ruta) + "?" + urlencode(sorted(self._parametros_firmados(parametros).items()))
                cabeceras: dict[str, str] = {}
                cuerpo_bytes = None
            else:
                url = self._url(ruta) + "?" + urlencode(sorted({"access_token": self.token, "appsecret_proof": self._appsecret_proof()}.items()))
                cabeceras = {"content-type": "application/x-www-form-urlencoded"}
                cuerpo_bytes = urlencode(sorted((cuerpo or {}).items())).encode("utf-8")
            respuesta = self.transporte.solicitar(metodo, url, cabeceras=cabeceras, cuerpo=cuerpo_bytes, timeout_s=30)
            cuerpo_json = respuesta.json() if respuesta.cuerpo else {}
            if respuesta.ok:
                return cuerpo_json
            error = cuerpo_json.get("error") if isinstance(cuerpo_json, dict) else None
            codigo = error.get("code") if isinstance(error, dict) else None
            if codigo == _CODIGO_613 and intentos < self.reintentos_613_max:
                self.dormir(self.espera_613_base_s * (2**intentos))
                intentos += 1
                continue
            mensaje = (error or {}).get("message", "error desconocido de la Marketing API") if isinstance(error, dict) else "respuesta sin JSON de error"
            raise ErrorExterno(f"Meta {metodo} {ruta}: {comun.ocultar_datos_sensibles(str(mensaje))} (estado {respuesta.estado})")

    # ------------------------------------------------------------------------------------------
    # Ritmo de ediciones (defensa local; el tope de negocio lo exige engine.guard)
    # ------------------------------------------------------------------------------------------
    def _comprobar_ritmo(self, object_id: str) -> None:
        ahora = comun.instante(self.ahora)
        historial = [t for t in self._historial_ediciones.get(object_id, []) if ahora - t < _UNA_HORA]
        if len(historial) + 1 > self.max_cambios_presupuesto_por_hora:
            raise ErrorLimite(f"ClienteMeta: {object_id} ya tuvo {len(historial)} ediciones en la última hora (máximo {self.max_cambios_presupuesto_por_hora})")
        if historial and ahora - max(historial) < timedelta(seconds=self.segundos_min_entre_ediciones):
            raise ErrorLimite(f"ClienteMeta: {object_id} se editó hace menos de {self.segundos_min_entre_ediciones} s")
        self._historial_ediciones[object_id] = historial + [ahora]

    # ------------------------------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------------------------------
    def leer(self, object_id: str, *, campos: Sequence[str]) -> dict[str, Any]:
        """``GET /{object_id}?fields=…`` (lectura pura; no cuenta en el ritmo de ediciones)."""
        return self._solicitar("GET", object_id, parametros={"fields": ",".join(campos)})

    def listar(self, ruta_padre: str, *, campos: Sequence[str], limite: int = 200) -> list[dict[str, Any]]:
        """``GET /{ruta_padre}?fields=…`` y devuelve ``data`` (sin paginar: alcanza para borradores de B0)."""
        cuerpo = self._solicitar("GET", ruta_padre, parametros={"fields": ",".join(campos), "limit": limite})
        datos = cuerpo.get("data", [])
        if not isinstance(datos, list):
            raise ErrorExterno(f"Meta GET {ruta_padre}: respuesta sin lista 'data'")
        return datos

    def buscar_por_prefijo(self, ruta_padre: str, prefijo: str, *, campos: Sequence[str] = ("id", "name")) -> dict[str, Any] | None:
        """El primer objeto de ``ruta_padre`` cuyo ``name`` empieza por ``prefijo`` (reutilización idempotente)."""
        campos = tuple(dict.fromkeys((*campos, "name")))
        for objeto in self.listar(ruta_padre, campos=campos):
            if str(objeto.get("name", "")).startswith(prefijo):
                return objeto
        return None

    def buscar_por_nombre_exacto(self, ruta_padre: str, nombre: str, *, campos: Sequence[str] = ("id", "name")) -> dict[str, Any] | None:
        """El objeto de ``ruta_padre`` cuyo ``name`` es EXACTAMENTE ``nombre`` (``startswith`` colisiona, p. ej. ``..._v1`` con ``..._v10``)."""
        campos = tuple(dict.fromkeys((*campos, "name")))
        for objeto in self.listar(ruta_padre, campos=campos):
            if str(objeto.get("name", "")) == nombre:
                return objeto
        return None

    def crear(self, ruta_padre: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        """``POST /{ruta_padre}`` con ``payload`` como formulario; devuelve ``{"id": …}``. No cuenta en el ritmo."""
        resultado = self._solicitar("POST", ruta_padre, cuerpo=payload)
        if "id" not in resultado:
            raise ErrorExterno(f"Meta POST {ruta_padre}: la respuesta no trae 'id'")
        return resultado

    def cambiar_estado(self, object_id: str, estado: str, *, forzar: bool = False) -> dict[str, Any]:
        """``POST /{object_id} {status: estado}``, bajo el control de ritmo (es una edición).

        ``forzar=True`` salta el control de ritmo: solo para una pausa de emergencia (rollback de una
        activación a medias, kill switch). Pausar nunca espera al ritmo (``contratos/gates.json``,
        ``accion:pausar``: "pausar nunca requiere esperar a un humano"; aquí, tampoco a 30 s de más).
        """
        if estado not in ("ACTIVE", "PAUSED"):
            raise ErrorValidacion(f"cambiar_estado: estado inválido {estado!r} (solo ACTIVE o PAUSED)")
        if not forzar:
            self._comprobar_ritmo(object_id)
        return self._solicitar("POST", object_id, cuerpo={"status": estado})

    def cambiar_presupuesto(self, object_id: str, campo: str, monto_unidad_meta: int) -> dict[str, Any]:
        """``POST /{object_id} {<campo>: monto_unidad_meta}`` (``monto_unidad_meta`` ya convertido con ``meta.monedas``)."""
        if campo not in ("daily_budget", "lifetime_budget", "spend_cap"):
            raise ErrorValidacion(f"cambiar_presupuesto: campo desconocido {campo!r}")
        monto = comun.exigir_importe(monto_unidad_meta, "monto_unidad_meta", minimo=1)
        self._comprobar_ritmo(object_id)
        return self._solicitar("POST", object_id, cuerpo={campo: monto})

    def insights(self, object_id: str, *, desde: str, hasta: str, campos: Sequence[str]) -> list[dict[str, Any]]:
        """``GET /{object_id}/insights`` para la ventana ``[desde, hasta]`` (fechas ``AAAA-MM-DD``)."""
        time_range = f'{{"since":"{desde}","until":"{hasta}"}}'
        cuerpo = self._solicitar("GET", f"{object_id}/insights", parametros={"fields": ",".join(campos), "time_range": time_range})
        datos = cuerpo.get("data", [])
        if not isinstance(datos, list):
            raise ErrorExterno(f"Meta GET {object_id}/insights: respuesta sin lista 'data'")
        return datos
