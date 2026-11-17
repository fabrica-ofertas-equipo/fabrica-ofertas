"""Preflight de infraestructura: evalúa el catálogo de ``infra/plantillas/preflight-items.yaml`` y
escribe/firma ``empresa/infra/estado.json`` (``contratos/infra_estado.schema.json``).

Diseño (docs/07-puesta-en-marcha.md §10): **solo lectura** (ninguna sonda escribe en un servicio
externo); **falla cerrado** (una sonda no ejecutable —sin credencial, sin red, sin implementación en
este modo— es ROJO si el ítem es crítico y AMARILLO si no; nunca VERDE por ausencia); **sin límites no
hay VERDE** (``P-01``); **modo simulado por defecto** (sin credenciales se escribe ``modo: "simulado"``,
que los hooks y ``engine.guard`` rechazan para gastar o activar).

Qué hace esta entrega, honestamente: el CATÁLOGO completo (43 + ``R-06`` = 44 ítems) y el MOTOR de
agregación, firma y escritura están completos y probados. Las SONDAS reales solo están implementadas
para lo que se puede comprobar sin credenciales de terceros ni red real: ``K-01`` (``empresa/PAUSA``),
``P-01`` (``limites.yaml`` completo y sellado), ``R-06`` (centinela de persistencia local), ``C-09``
(estado del Worker ``watchdog`` vía un :class:`engine.transporte.Transporte` inyectado) y ``G-03``
(``gitleaks`` por subprocess, si el binario existe). El resto de los 43 ítems (Meta, Stripe, Cloudflare,
Railway, correo, legal) exige credenciales reales o servicios que no existen en este entorno de
construcción nocturna: quedan con su contrato (catálogo, firmas, esquema) y la sonda por defecto
«no ejecutable», listas para que quien tenga las credenciales inyecte su propia :data:`Sonda` sin
tocar el motor. Ver «Pedidos» del README.

Reglas de agregación del semáforo global (docs/07 §10.2, interpretación propia documentada en el
README bajo «Decisiones» porque el validador genérico de ``scripts.validar_esquemas`` usa una regla
más simple para los EJEMPLOS de contratos, no para el funcionamiento operativo de este módulo):
ROJO si algún ítem CRÍTICO quedó en ROJO; si no, AMARILLO si hay algún ítem que no sea VERDE
(AMARILLO, ROJO no crítico, PENDIENTE o PENDIENTE_EXTERNO); VERDE solo si TODOS están en VERDE.

CLI::

    python -m infra.preflight ejecutar --modo completo --salida empresa/infra/estado.json [--json]
    python -m infra.preflight ejecutar --modo ligero --salida empresa/infra/estado.json --anterior empresa/infra/estado.json
    python -m infra.preflight ejecutar --modo e2e_prueba --salida empresa/infra/estado.json

Salida (docs/07 §10.4, sin red ni credenciales reales en estas pruebas): 0 VERDE · 2 uso incorrecto ·
3 catálogo o datos inválidos · 4 AMARILLO o ROJO (no habilita gasto ni activación; el semáforo real
viaja en ``estado.json`` y en stdout).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from engine import comun, parametros
from engine.errores import ErrorFabrica, ErrorUso, ErrorValidacion
from engine.transporte import Transporte

__all__ = [
    "ESTADOS_ITEM", "MODOS", "ItemCatalogo", "ResultadoSonda", "cargar_catalogo", "construir_estado",
    "ejecutar", "escribir_estado", "main", "ruta_catalogo", "ruta_estado", "ruta_evidencia", "semaforo_global",
    "sonda_c09_watchdog", "sonda_centinela_r06", "sonda_gitleaks_g03", "sonda_k01_pausa", "sonda_p01_limites",
    "sondas_por_defecto",
]

MODOS = ("completo", "ligero", "e2e_prueba")
ESTADOS_ITEM = ("VERDE", "AMARILLO", "ROJO", "PENDIENTE", "PENDIENTE_EXTERNO")
SCHEMA_VERSION = "1.1.0"
VAR_CLAVE_PREFLIGHT = "PREFLIGHT_HMAC_KEY"  # misma variable que engine.guard._paso_infra verifica
PARAMETRO_VIGENCIA = "infra.hc_preflight_vigencia_horas"
VIGENCIA_MAXIMA_H = 6  # tope duro del backbone (§5.6); un parámetro nunca lo sube (igual que engine.guard)


# ----------------------------------------------------------------------------------------------
# Catálogo
# ----------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ItemCatalogo:
    """Un ítem del catálogo normativo (``infra/plantillas/preflight-items.yaml``)."""

    id: str
    bloque: str
    critico: bool
    ligero: bool
    comprueba: str
    verde: str = ""
    amarillo: str = ""
    rojo: str = ""
    condicion: str | None = None
    critico_desde: str | None = None


def ruta_catalogo(raiz: Path | None = None) -> Path:
    """Ruta de ``infra/plantillas/preflight-items.yaml`` (catálogo: siempre bajo el CÓDIGO, no ``FABRICA_RAIZ``)."""
    base = raiz if raiz is not None else Path(__file__).resolve().parents[1]
    return base / "infra" / "plantillas" / "preflight-items.yaml"


def cargar_catalogo(ruta: Path | None = None) -> list[ItemCatalogo]:
    """Carga y valida la forma del catálogo. ``ErrorValidacion`` (3) si falta, está vacío o repite un ``id``."""
    destino = ruta if ruta is not None else ruta_catalogo()
    try:
        datos = comun.cargar_yaml(destino)
    except FileNotFoundError as exc:
        raise ErrorValidacion(f"falta el catálogo de preflight: {destino}") from exc
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ErrorValidacion(f"catálogo de preflight ilegible: {exc}") from exc
    items = datos.get("items") if isinstance(datos, dict) else None
    if not isinstance(items, list) or not items:
        raise ErrorValidacion("preflight-items.yaml: se esperaba una lista «items» no vacía")
    vistos: set[str] = set()
    catalogo: list[ItemCatalogo] = []
    for crudo in items:
        if not isinstance(crudo, dict) or not crudo.get("id"):
            raise ErrorValidacion("preflight-items.yaml: ítem sin «id»")
        id_ = str(crudo["id"])
        if id_ in vistos:
            raise ErrorValidacion(f"preflight-items.yaml: id repetido {id_!r}")
        vistos.add(id_)
        catalogo.append(ItemCatalogo(
            id=id_, bloque=str(crudo.get("bloque", "")), critico=bool(crudo.get("critico", False)),
            ligero=bool(crudo.get("ligero", False)), comprueba=str(crudo.get("comprueba", "")),
            verde=str(crudo.get("verde", "")), amarillo=str(crudo.get("amarillo", "")), rojo=str(crudo.get("rojo", "")),
            condicion=crudo.get("condicion"), critico_desde=crudo.get("critico_desde"),
        ))
    return catalogo


# ----------------------------------------------------------------------------------------------
# Sondas (solo lectura, inyectables)
# ----------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ResultadoSonda:
    """Resultado de una sonda de un ítem: ``estado`` ∈ :data:`ESTADOS_ITEM`, mensaje breve y evidencia."""

    estado: str
    mensaje: str
    evidencia: Mapping[str, Any] = field(default_factory=dict)
    latencia_ms: int = 0


Sonda = Callable[[], ResultadoSonda]


def _no_ejecutable(item: ItemCatalogo) -> ResultadoSonda:
    """Regla de diseño (docs/07 §10.1-2): sin sonda, nunca VERDE. ROJO si es crítico, AMARILLO si no."""
    estado = "ROJO" if item.critico else "AMARILLO"
    return ResultadoSonda(estado, "sonda no ejecutable: sin credencial, red o implementación en este modo", {}, 0)


def sonda_k01_pausa(base: Path) -> ResultadoSonda:
    """``K-01``: ``empresa/PAUSA`` ausente y sin pausa conocida. Solo lee el archivo (sin red ni credenciales)."""
    from engine.guard import hay_pausa
    if hay_pausa(base):
        return ResultadoSonda("ROJO", "empresa/PAUSA presente", {"pausa": True})
    return ResultadoSonda("VERDE", "empresa/PAUSA ausente", {"pausa": False})


def sonda_p01_limites(base: Path, *, env: Mapping[str, str] | None = None, operacion: str = "gastar") -> ResultadoSonda:
    """``P-01``: ``limites.yaml`` completo, coherente y sellado para ``operacion`` (sin red)."""
    from engine import limites as limites_mod
    from engine.errores import ErrorLimite
    variables = os.environ if env is None else env
    try:
        lim = limites_mod.cargar_limites(base / "empresa" / "limites.yaml", env=variables)
        limites_mod.exigir_operacion(lim, operacion)
    except ErrorLimite as exc:
        faltan = list(exc.detalle.get("faltantes", []))
        return ResultadoSonda("ROJO", f"faltan o son incoherentes: {', '.join(faltan) or exc.mensaje}", {"faltantes": faltan})
    except ErrorFabrica as exc:
        return ResultadoSonda("ROJO", f"limites.yaml inválido: {exc.mensaje}", {})
    return ResultadoSonda("VERDE", "límites completos, coherentes y sellados", {"hash": lim.hash_calculado})


_RUTA_CENTINELA = ("empresa", "infra", "centinela_persistencia.json")


def sonda_centinela_r06(base: Path, *, ahora: Callable[[], datetime] = comun.ahora_utc,
                        antiguedad_minima_min: int = 1) -> ResultadoSonda:
    """``R-06``: ¿el almacén persiste tras un redeploy? Centinela local: escribe si falta, compara si existe.

    No puede demostrar una persistencia REAL entre redespliegues de Railway (eso exige el entorno real,
    ``[VERIFICAR]`` en infra, docs/06 §4.8): aquí solo se comprueba que un centinela escrito en una
    corrida anterior sigue legible y sin alterar. Primera corrida (sin centinela previo): ``PENDIENTE_EXTERNO``
    (nunca VERDE por ausencia). Con un centinela más viejo que ``antiguedad_minima_min``: ``VERDE``. Más
    nuevo (corrida repetida en la misma sesión, sin tiempo de por medio para un redeploy real): ``AMARILLO``.
    """
    ruta = base.joinpath(*_RUTA_CENTINELA)
    t = comun.instante(ahora)
    try:
        datos = comun.cargar_json(ruta)
        nonce = datos.get("nonce")
        escrito_en = comun.parsear_z(datos["escrito_en"])
    except FileNotFoundError:
        nuevo = {"nonce": comun.hash_bytes(comun.iso_z(t).encode("utf-8"))[: len("sha256:") + 16], "escrito_en": comun.iso_z(t)}
        comun.escribir_atomico(ruta, comun.json_canonico(nuevo))
        return ResultadoSonda("PENDIENTE_EXTERNO", "centinela recién creado: sin corrida previa que confirme persistencia", nuevo)
    except (OSError, ValueError, UnicodeDecodeError, KeyError, ErrorValidacion) as exc:
        return ResultadoSonda("ROJO", f"centinela de persistencia ilegible: {exc}", {})
    if not isinstance(nonce, str) or not nonce:
        return ResultadoSonda("ROJO", "centinela de persistencia sin nonce", {})
    if t - escrito_en < timedelta(minutes=antiguedad_minima_min):
        return ResultadoSonda("AMARILLO", "centinela demasiado reciente para confirmar persistencia entre corridas", {"nonce": nonce})
    return ResultadoSonda("VERDE", "centinela legible desde una corrida anterior", {"nonce": nonce})


def sonda_c09_watchdog(transporte: Transporte, url_base: str, *, timeout_s: int = 10) -> ResultadoSonda:
    """``C-09``: ``GET <url_base>/estado`` del Worker ``watchdog`` (``watchdog:visto`` reciente, variables obligatorias).

    El Worker responde 503 si ``GASTO_DIARIO_MAX_MINOR`` o ``CUENTA_TZ`` no están configuradas
    (docs/07 §9.2: «nunca se omite la barrera independiente del motor»); eso es ROJO, no «no ejecutable».
    """
    from engine.errores import ErrorExterno
    try:
        resp = transporte.solicitar("GET", url_base.rstrip("/") + "/estado", cabeceras={}, cuerpo=None, timeout_s=timeout_s)
    except ErrorExterno as exc:
        return ResultadoSonda("ROJO", f"watchdog inalcanzable: {exc.mensaje}", {})
    if resp.estado == 503:
        return ResultadoSonda("ROJO", "watchdog sin GASTO_DIARIO_MAX_MINOR o CUENTA_TZ configuradas", {"estado_http": 503})
    if not resp.ok:
        return ResultadoSonda("ROJO", f"watchdog respondió {resp.estado}", {"estado_http": resp.estado})
    try:
        cuerpo = resp.json()
    except ErrorExterno as exc:
        return ResultadoSonda("ROJO", f"respuesta de watchdog ilegible: {exc.mensaje}", {})
    visto_hace_min = cuerpo.get("visto_hace_min")
    if not isinstance(visto_hace_min, (int, float)) or isinstance(visto_hace_min, bool):
        return ResultadoSonda("ROJO", "watchdog sin visto_hace_min", {"cuerpo": cuerpo})
    if visto_hace_min > 10:
        return ResultadoSonda("ROJO", f"watchdog visto hace {visto_hace_min} min (> 10)", {"visto_hace_min": visto_hace_min})
    return ResultadoSonda("VERDE", f"watchdog visto hace {visto_hace_min} min", {"visto_hace_min": visto_hace_min})


def sonda_gitleaks_g03(*, raiz: Path | None = None,
                       ejecutar_proceso: Callable[[Sequence[str]], "subprocess.CompletedProcess[bytes]"] | None = None) -> ResultadoSonda:
    """``G-03``: ``gitleaks`` sobre el repositorio, si el binario existe (sin red; es análisis local)."""
    import shutil
    binario = shutil.which("gitleaks")
    if not binario:
        return ResultadoSonda("ROJO", "gitleaks no está instalado en este entorno", {})
    base = str(raiz) if raiz is not None else str(Path(__file__).resolve().parents[1])
    correr = ejecutar_proceso or (lambda orden: subprocess.run(orden, capture_output=True, timeout=120, check=False))
    try:
        resultado = correr([binario, "detect", "--no-git", "--source", base, "--report-format", "json"])
    except (OSError, subprocess.SubprocessError) as exc:
        return ResultadoSonda("ROJO", f"gitleaks no se pudo ejecutar: {exc}", {})
    if resultado.returncode == 0:
        return ResultadoSonda("VERDE", "0 hallazgos", {"returncode": 0})
    return ResultadoSonda("ROJO", "gitleaks encontró hallazgos", {"returncode": resultado.returncode})


# ----------------------------------------------------------------------------------------------
# Agregación y escritura de estado.json
# ----------------------------------------------------------------------------------------------
def semaforo_global(items: Sequence[Mapping[str, Any]]) -> str:
    """ROJO si algún ítem CRÍTICO es ROJO; si no, AMARILLO si hay algo que no sea VERDE; VERDE si todo lo es."""
    if any(i["critico"] and i["estado"] == "ROJO" for i in items):
        return "ROJO"
    if any(i["estado"] != "VERDE" for i in items):
        return "AMARILLO"
    return "VERDE"


def ruta_estado(raiz: Path) -> Path:
    return raiz / "empresa" / "infra" / "estado.json"


def ruta_evidencia(raiz: Path, generado_en: datetime) -> Path:
    """``empresa/infra/healthcheck/<AAAAMMDD-HHMM>.json`` (docs/06 N01)."""
    return raiz / "empresa" / "infra" / "healthcheck" / (generado_en.strftime("%Y%m%d-%H%M") + ".json")


def _vigencia_horas(base: Path) -> tuple[int, ResultadoSonda | None]:
    """Horas de vigencia (acotadas a :data:`VIGENCIA_MAXIMA_H`) y, si el parámetro falta, un ítem ROJO sintético."""
    try:
        par = parametros.cargar_parametros(base / "empresa" / "parametros.yaml")
        valor = par.valor(PARAMETRO_VIGENCIA)
    except ErrorFabrica as exc:
        return 0, ResultadoSonda("ROJO", f"{PARAMETRO_VIGENCIA} ilegible: {exc.mensaje}", {})
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
        return 0, ResultadoSonda("ROJO", f"{PARAMETRO_VIGENCIA} inválido: {valor!r}", {})
    return min(valor, VIGENCIA_MAXIMA_H), None


def construir_estado(modo: str, *, sondas: Mapping[str, Sonda] | None = None, catalogo: Sequence[ItemCatalogo] | None = None,
                     ahora: Callable[[], datetime] = comun.ahora_utc, raiz: Path | None = None, env: Mapping[str, str] | None = None,
                     infra_modo: str = "simulado", anterior: Mapping[str, Any] | None = None,
                     commit: str | None = None, hash_scripts: str | None = None) -> tuple[dict, dict]:
    """Ejecuta las sondas aplicables y devuelve ``(estado_sin_firma, evidencia_detallada)``.

    ``modo="ligero"`` solo corre los ítems ``ligero: true`` del catálogo y conserva los demás del
    ``anterior`` (su vigencia NO se extiende: conservan su ``medido_en``/``expira_en`` originales,
    docs/07 §10.3 «no extiende la vigencia de lo no remedido»). ``modo="e2e_prueba"`` corre como
    ``completo`` (la cadena sintética clic→sesión→webhook→correo→enlace→evento no está implementada
    en esta entrega; ver README «Decisiones»); no habilita nada por sí sola en ningún caso.
    """
    if modo not in MODOS:
        raise ErrorUso(f"--modo debe ser uno de {', '.join(MODOS)}")
    base = raiz if raiz is not None else comun.raiz(env or {})
    catalogo_items = list(catalogo) if catalogo is not None else cargar_catalogo()
    sondas = sondas or {}
    t = comun.instante(ahora)

    anteriores: dict[str, dict] = {}
    if anterior and isinstance(anterior.get("items"), list):
        anteriores = {i["id"]: dict(i) for i in anterior["items"] if isinstance(i, dict) and "id" in i}

    seleccion = catalogo_items if modo != "ligero" else [i for i in catalogo_items if i.ligero]
    items: list[dict] = []
    evidencia_detallada: dict[str, Any] = {}
    for item in catalogo_items:
        if item not in seleccion:
            previo = anteriores.get(item.id)
            if previo is not None:
                items.append(previo)
            continue
        sonda = sondas.get(item.id)
        try:
            r = sonda() if sonda is not None else _no_ejecutable(item)
        except ErrorFabrica as exc:
            r = ResultadoSonda("ROJO" if item.critico else "AMARILLO", f"sonda falló: {exc.mensaje}", {})
        except Exception as exc:  # noqa: BLE001 - una sonda rota nunca debe tumbar el preflight completo
            r = ResultadoSonda("ROJO" if item.critico else "AMARILLO", f"sonda con error inesperado: {exc}", {})
        if r.estado not in ESTADOS_ITEM:
            raise ErrorValidacion(f"sonda {item.id}: estado desconocido {r.estado!r}")
        evidencia_detallada[item.id] = {"mensaje": r.mensaje, "evidencia": dict(r.evidencia), "latencia_ms": r.latencia_ms}
        items.append({
            "id": item.id, "bloque": item.bloque, "critico": item.critico, "estado": r.estado,
            "mensaje": r.mensaje[:300], "evidencia_ruta": "", "medido_en": comun.iso_z(t),
            "expira_en": "", "latencia_ms": max(0, int(r.latencia_ms)),
        })

    vigencia_h, item_vigencia = _vigencia_horas(base)
    if item_vigencia is not None:
        items.append({
            "id": "P-00", "bloque": "control", "critico": True, "estado": item_vigencia.estado,
            "mensaje": item_vigencia.mensaje[:300], "evidencia_ruta": "", "medido_en": comun.iso_z(t),
            "expira_en": comun.iso_z(t), "latencia_ms": 0,
        })
    expira_en = comun.iso_z(t + timedelta(hours=vigencia_h)) if vigencia_h else comun.iso_z(t)
    evidencia_ruta_rel = f"empresa/infra/healthcheck/{t.strftime('%Y%m%d-%H%M')}.json"
    for i in items:
        if not i.get("evidencia_ruta"):
            i["evidencia_ruta"] = evidencia_ruta_rel
        if not i.get("expira_en"):
            i["expira_en"] = expira_en

    estado = {
        "schema_version": SCHEMA_VERSION,
        "modo": infra_modo,
        "semaforo": semaforo_global(items),
        "generado_en": comun.iso_z(t),
        "valido_hasta": comun.iso_z(t + timedelta(hours=vigencia_h)) if vigencia_h else comun.iso_z(t),
        "commit": commit or "0" * 40,
        "hash_scripts": hash_scripts or ("sha256:" + "0" * 64),
        "items": items,
    }
    return estado, {"modo_preflight": modo, "generado_en": comun.iso_z(t), "items": evidencia_detallada}


def escribir_estado(raiz: Path, estado: Mapping[str, Any], evidencia: Mapping[str, Any], *, clave: bytes) -> dict:
    """Firma (HMAC sobre el JSON canónico sin ``firma``) y escribe ``estado.json`` + la evidencia detallada."""
    firmado = dict(estado)
    firmado["firma"] = comun.firma_hmac(firmado, clave)
    comun.escribir_atomico(ruta_estado(raiz), comun.json_canonico(firmado))
    for ruta_rel in {i["evidencia_ruta"] for i in estado["items"]}:
        comun.escribir_atomico(raiz / ruta_rel, comun.json_canonico(evidencia))
    return firmado


def sondas_por_defecto(raiz: Path, env: Mapping[str, str]) -> dict[str, Sonda]:
    """Sondas REALES, sin credenciales de terceros ni red, que esta entrega sí implementa (ver cabecera del módulo).

    Un llamador puede sobreescribir cualquiera pasando su propia :data:`Sonda` en ``ejecutar``/``construir_estado``
    (el mapa explícito tiene prioridad). ``C-09`` no se incluye aquí: exige un :class:`Transporte` real hacia el
    Worker ``watchdog`` que esta función no puede construir sola sin arriesgar una llamada de red por omisión.
    """
    return {
        "K-01": lambda: sonda_k01_pausa(raiz),
        "P-01": lambda: sonda_p01_limites(raiz, env=env),
        "R-06": lambda: sonda_centinela_r06(raiz),
        "G-03": lambda: sonda_gitleaks_g03(raiz=raiz),
    }


def ejecutar(modo: str, *, raiz: Path, env: Mapping[str, str], sondas: Mapping[str, Sonda] | None = None,
            ahora: Callable[[], datetime] = comun.ahora_utc, infra_modo: str = "simulado",
            escribir: bool = True) -> dict:
    """Corre el preflight, firma y (si ``escribir``) guarda ``estado.json``. Devuelve el estado FIRMADO.

    Las sondas que esta entrega implementa de verdad (:func:`sondas_por_defecto`) se usan siempre que
    ``sondas`` no las sobreescriba explícitamente. ``ErrorUso`` (2) si falta ``PREFLIGHT_HMAC_KEY`` o el
    modo no existe.
    """
    clave = (env.get(VAR_CLAVE_PREFLIGHT) or "").encode("utf-8")
    if not clave:
        raise ErrorUso(f"falta {VAR_CLAVE_PREFLIGHT}: no se puede firmar estado.json")
    anterior = None
    if modo == "ligero" and ruta_estado(raiz).is_file():
        try:
            anterior = comun.cargar_json(ruta_estado(raiz))
        except (OSError, ValueError, UnicodeDecodeError):
            anterior = None
    sondas_finales = {**sondas_por_defecto(raiz, env), **(sondas or {})}
    estado, evidencia = construir_estado(modo, sondas=sondas_finales, ahora=ahora, raiz=raiz, env=env, infra_modo=infra_modo, anterior=anterior)
    if escribir:
        return escribir_estado(raiz, estado, evidencia, clave=clave)
    firmado = dict(estado)
    firmado["firma"] = comun.firma_hmac(firmado, clave)
    return firmado


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m infra.preflight", description="Preflight de infraestructura (solo lectura).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pe = sub.add_parser("ejecutar", help="corre el catálogo y escribe empresa/infra/estado.json")
    pe.add_argument("--modo", choices=MODOS, default="completo")
    pe.add_argument("--infra-modo", choices=("vivo", "prueba", "simulado"), default="simulado",
                    help="qué 'modo' declarar en estado.json; 'vivo' exige credenciales reales (fuera de este entorno)")
    pe.add_argument("--raiz", help="raíz alternativa (solo con FABRICA_ENTORNO distinto de produccion)")
    pe.add_argument("--ahora", help="instante UTC con Z (solo con FABRICA_ENTORNO distinto de produccion)")
    pe.add_argument("--no-escribir", action="store_true", help="calcula y muestra, pero no escribe estado.json")
    pe.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        if (args.raiz or args.ahora) and comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz y --ahora no existen con FABRICA_ENTORNO=produccion")
        raiz = Path(args.raiz).resolve() if args.raiz else comun.raiz(env)
        reloj = (lambda: comun.parsear_z(args.ahora)) if args.ahora else comun.ahora_utc
        estado = ejecutar(args.modo, raiz=raiz, env=env, ahora=reloj, infra_modo=args.infra_modo, escribir=not args.no_escribir)
        datos = {"semaforo": estado["semaforo"], "modo": estado["modo"], "items": len(estado["items"]),
                 "rojos": [i["id"] for i in estado["items"] if i["estado"] == "ROJO"],
                 "amarillos": [i["id"] for i in estado["items"] if i["estado"] == "AMARILLO"]}
        codigo = 0 if estado["semaforo"] == "VERDE" else 4
        if args.json:
            print(json.dumps({"ok": codigo == 0, "modo": "dry_run", "codigo": codigo, "datos": datos, "avisos": []},
                             sort_keys=True, ensure_ascii=False))
        else:
            print(f"PREFLIGHT {estado['semaforo']} ({len(estado['items'])} ítems): rojos={datos['rojos']} amarillos={datos['amarillos']}")
        return codigo

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
