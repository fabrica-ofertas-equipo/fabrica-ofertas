"""Ayudas compartidas por las pruebas del núcleo del motor (y reutilizables por I1 para B0).

* :class:`PruebaBase`: bloquea ``socket.socket`` en ``setUp`` (ninguna prueba abre un socket) y da una
  carpeta temporal por prueba.
* :func:`par_de_claves`: genera UNA vez por proceso un par Ed25519 de prueba con ``ssh-keygen`` (local,
  sin red) en una carpeta temporal que se borra al salir. Nunca hay claves en el repositorio.
* :func:`crear_empresa`: copia ``tests/fixtures/engine/empresa_prueba/`` a una raíz temporal y deja
  todo listo para que ``comprobar_live`` pase los 7 pasos: límites firmados con la clave de prueba, ancla
  del hash, ``estado.json`` re-firmado (HMAC de prueba) en el modo pedido, variables de entorno ficticias.
  Cada prueba rompe UNA cosa a la vez a partir de este estado verde.
"""
from __future__ import annotations

import atexit
import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from unittest import mock

import yaml

from engine import comun
from scripts.validar_esquemas import CLAVE_DE_PRUEBA, cargar_json, cargar_yaml, firma_hmac, sello_de_limites

RAIZ_REPO = Path(__file__).resolve().parents[2]
FIXTURES = RAIZ_REPO / "tests" / "fixtures" / "engine"
EMPRESA_PRUEBA = FIXTURES / "empresa_prueba"
GENERADO_EN = "2026-11-09T06:00:00Z"  # instante de estado.json en la fixture
AHORA_BASE = datetime(2026, 11, 9, 7, 0, 0, tzinfo=timezone.utc)  # una hora después de GENERADO_EN
OFERTA = "OF-202611-01"
HASH_CONFIG = "sha256:" + "ab" * 32  # hash_objetivo de ejemplo para órdenes firmadas
ELIMINAR = object()  # valor para quitar una clave en ``reescribir_estado``


class PruebaBase(unittest.TestCase):
    """Base de las pruebas del motor: socket bloqueado y carpeta temporal propia."""

    def setUp(self) -> None:
        super().setUp()
        parche = mock.patch("socket.socket", side_effect=AssertionError("prueba sin red: socket.socket está bloqueado"))
        parche.start()
        self.addCleanup(parche.stop)
        self.tmp = Path(tempfile.mkdtemp(prefix="fabrica-prueba-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)


@dataclass(frozen=True)
class ParClaves:
    """Par Ed25519 de prueba: ruta de la privada y texto de la pública (``ssh-ed25519 AAAA…``)."""

    privada: Path
    publica: str


_DIR_CLAVES: Path | None = None
_PARES: dict[str, ParClaves] = {}


def par_de_claves(nombre: str = "dueno") -> ParClaves:
    """Par Ed25519 de prueba (uno por ``nombre`` y proceso). Salta la prueba si ``ssh-keygen`` no existe."""
    global _DIR_CLAVES
    if nombre in _PARES:
        return _PARES[nombre]
    if _DIR_CLAVES is None:
        _DIR_CLAVES = Path(tempfile.mkdtemp(prefix="fabrica-claves-"))
        atexit.register(shutil.rmtree, _DIR_CLAVES, True)
    ruta = _DIR_CLAVES / nombre
    try:
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "clave-de-prueba", "-f", str(ruta)],
                       check=True, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise unittest.SkipTest(f"ssh-keygen no disponible: {exc}") from exc
    par = ParClaves(ruta, Path(str(ruta) + ".pub").read_text(encoding="utf-8").strip())
    _PARES[nombre] = par
    return par


@dataclass
class EmpresaPrueba:
    """Una raíz temporal lista para el guard. ``env`` es el entorno INYECTADO (no se toca ``os.environ``)."""

    raiz: Path
    env: dict[str, str]
    ahora: datetime
    claves: ParClaves
    hash_limites: str
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def reloj(self) -> Callable[[], datetime]:
        """Reloj inyectable fijo en ``ahora``."""
        return lambda: self.ahora

    def ruta(self, *partes: str) -> Path:
        """Ruta bajo ``<raiz>/empresa``."""
        return self.raiz.joinpath("empresa", *partes)

    def reescribir_estado(self, **cambios: Any) -> None:
        """Modifica ``estado.json`` con ``cambios`` de primer nivel (``ELIMINAR`` quita la clave) y lo RE-FIRMA (HMAC de prueba)."""
        ruta = self.ruta("infra", "estado.json")
        estado = cargar_json(ruta)
        estado.pop("firma", None)
        for clave, valor in cambios.items():
            if valor is ELIMINAR:
                estado.pop(clave, None)
            else:
                estado[clave] = valor
        estado["firma"] = firma_hmac(estado, CLAVE_DE_PRUEBA)
        ruta.write_text(json.dumps(estado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def reescribir_parametros(self, clave: str, valor: Any) -> None:
        """Cambia el ``valor`` de ``grupo.clave`` en ``parametros.yaml`` de esta raíz."""
        ruta = self.ruta("parametros.yaml")
        datos = cargar_yaml(ruta)
        grupo, nombre = clave.split(".")
        datos["grupos"][grupo][nombre]["valor"] = valor
        ruta.write_text(yaml.safe_dump(datos, sort_keys=False, allow_unicode=True), encoding="utf-8")

    def reescribir_limites(self, modificar: Callable[[dict], None], *, firmar: bool = True, anclar: bool = True) -> None:
        """Modifica ``limites.yaml``, recalcula el sello, lo firma con la clave de prueba y actualiza el ancla."""
        ruta = self.ruta("limites.yaml")
        lim = cargar_yaml(ruta)
        modificar(lim)
        lim["sello"] = {"hash": sello_de_limites(lim), "firmado_por": "dueno-de-prueba", "firmado_en": "2026-11-06T12:00:00Z"}
        if firmar:
            lim["sello"]["firma"] = comun.firmar_ed25519(lim["sello"]["hash"].encode("utf-8"), self.claves.privada)
        ruta.write_text(yaml.safe_dump(lim, sort_keys=False, allow_unicode=True), encoding="utf-8")
        self.hash_limites = lim["sello"]["hash"]
        if anclar:
            self.env["LIMITES_HASH_ANCLA"] = self.hash_limites

    def firmar_orden(self, accion: str, *, oferta_id: str | None = OFERTA, hash_objetivo: str = HASH_CONFIG,
                     ts: str = "2026-11-09T06:30:00Z", nonce: str = "nonce-0001", alterar: bool = False) -> dict:
        """Escribe ``empresa/ordenes/<nonce>.json`` firmada con la clave de prueba (``alterar`` rompe la firma)."""
        orden: dict[str, Any] = {"accion": accion, "oferta_id": oferta_id, "hash_objetivo": hash_objetivo, "ts": ts, "nonce": nonce}
        orden["firma"] = comun.firmar_ed25519(comun.json_canonico(orden), self.claves.privada)
        if alterar:
            orden["hash_objetivo"] = "sha256:" + "cd" * 32
        destino = self.ruta("ordenes")
        destino.mkdir(parents=True, exist_ok=True)
        (destino / f"{nonce}.json").write_text(json.dumps(orden, indent=2) + "\n", encoding="utf-8")
        return orden


def crear_empresa(destino: Path, *, modo_infra: str = "vivo", entorno: str = "produccion",
                  ahora: datetime = AHORA_BASE, generado_en: str = GENERADO_EN) -> EmpresaPrueba:
    """Copia la fixture a ``destino/empresa`` y la deja en estado verde para ``comprobar_live``."""
    claves = par_de_claves()
    shutil.copytree(EMPRESA_PRUEBA, destino / "empresa")
    emp = EmpresaPrueba(raiz=destino, env={}, ahora=ahora, claves=claves, hash_limites="")
    emp.env = {
        "FABRICA_ENTORNO": entorno,
        "FABRICA_RAIZ": str(destino),
        "PREFLIGHT_HMAC_KEY": CLAVE_DE_PRUEBA.decode("utf-8"),
        "FABRICA_FIRMA_PUBLICA": claves.publica,
        "META_TOKEN_OPERADOR": "ficticio-operador",
        "META_AD_ACCOUNT_ID": "act_100000000000001",
        "META_APP_SECRET": "ficticio-app",
        "STRIPE_RK_REEMBOLSO": "ficticio-reembolso",
        "CORREO_API_KEY": "ficticio-correo",
    }
    emp.reescribir_limites(lambda lim: None)
    valido_hasta = comun.iso_z(comun.parsear_z(generado_en) + timedelta(hours=6))
    emp.reescribir_estado(modo=modo_infra, generado_en=generado_en, valido_hasta=valido_hasta)
    return emp


def copia_profunda(x: Any) -> Any:
    """Atajo para que las pruebas muten copias de fixtures sin tocar el original."""
    return copy.deepcopy(x)
