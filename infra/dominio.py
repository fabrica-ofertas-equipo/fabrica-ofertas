"""``infra.dominio``: verificación de un dominio en SOLO LECTURA (DNS/TXT, portfolio de Meta).

NUNCA compra un dominio ni escribe DNS (eso es un paso humano, N01b en
``infra/plantillas/alta-oferta.yaml``, pasos ``dominio-compra`` y ``meta-dominio-verificado``): este
módulo solo lee y dice qué falta. DNS se consulta por *DNS-over-HTTPS* (RFC 8484, formato JSON) a
través de un :class:`engine.transporte.Transporte` inyectable — NUNCA abre un socket propio — para
que las pruebas usen :class:`~engine.transporte.TransporteFixture` y un cliente real (fuera de esta
construcción nocturna) pueda usar ``infra.transporte_http.TransporteUrllib`` hacia un resolutor DoH.

Sin un transporte inyectado para una comprobación, esa comprobación queda ``pendiente`` (nunca
``verificado=True`` por omisión: la regla de siempre, docs/07 §10.1-2).

CLI::

    python -m infra.dominio verificar --dominio ejemplo.com --txt-esperado "meta-domain-verification=..." \
        --fixture-dns tests/fixtures/infra/dns.yaml [--business-id 123 --fixture-meta tests/fixtures/infra/meta.yaml] [--json]

Salida (convenciones §8): 0 todo lo comprobable está verificado · 2 uso · 4 falta algo (nunca gasta ni activa) · 6 el transporte inyectado falla.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from engine.errores import ErrorUso
from engine.transporte import Transporte, TransporteFixture

__all__ = [
    "ResultadoDominio", "consultar_txt", "dominio_verificado_en_meta", "main", "verificar",
]

_SERVIDOR_DOH_POR_DEFECTO = "https://cloudflare-dns.com/dns-query"
_TIPO_DNS_TXT = 16


def consultar_txt(transporte: Transporte, dominio: str, *, servidor: str = _SERVIDOR_DOH_POR_DEFECTO,
                  timeout_s: int = 10) -> list[str]:
    """Consulta los registros TXT de ``dominio`` por DNS-over-HTTPS (JSON, RFC 8484). Solo lectura.

    Devuelve los valores TXT (sin las comillas que DoH incluye en ``data``). Lista vacía si no hay
    ningún TXT. Propaga ``ErrorExterno`` si el transporte falla (red o tiempo agotado).
    """
    url = f"{servidor}?name={dominio}&type=TXT"
    resp = transporte.solicitar("GET", url, cabeceras={"Accept": "application/dns-json"}, cuerpo=None, timeout_s=timeout_s)
    cuerpo = resp.json()
    respuestas = cuerpo.get("Answer", []) if isinstance(cuerpo, dict) else []
    valores: list[str] = []
    for r in respuestas:
        if isinstance(r, Mapping) and r.get("type") == _TIPO_DNS_TXT and isinstance(r.get("data"), str):
            valores.append(r["data"].strip('"'))
    return valores


def dominio_verificado_en_meta(cliente: Any, business_id: str, dominio: str) -> bool | None:
    """¿``dominio`` figura ``verified`` en ``owned_domains`` del portfolio? Solo lectura (``GET``).

    ``None`` si el dominio no aparece en absoluto en la lista (ni verificado ni pendiente): no se
    puede distinguir "aún no se dio de alta" de "se dio de alta pero no se ve", así que se informa
    como desconocido en vez de asumir falso.
    """
    items = cliente.listar(f"{business_id}/owned_domains", campos=("id", "domain", "verification_status"))
    for item in items:
        if item.get("domain") == dominio:
            return str(item.get("verification_status", "")).lower() == "verified"
    return None


@dataclass(frozen=True)
class ResultadoDominio:
    dominio: str
    dns_txt: Mapping[str, Any]
    meta_portfolio: Mapping[str, Any]
    faltan: tuple[str, ...] = field(default_factory=tuple)

    @property
    def completo(self) -> bool:
        return not self.faltan


def verificar(dominio: str, *, transporte_dns: Transporte | None = None, txt_esperado: str | None = None,
             cliente_meta: Any | None = None, business_id: str | None = None,
             servidor_doh: str = _SERVIDOR_DOH_POR_DEFECTO) -> ResultadoDominio:
    """Verifica en solo lectura lo que se pueda con lo inyectado; lo demás queda ``pendiente``.

    NUNCA escribe DNS ni compra el dominio. ``faltan`` lista, en español, cada comprobación que no
    quedó satisfecha (incluidas las ``pendiente`` por falta de transporte inyectado: no son un
    "verde" silencioso).
    """
    if not isinstance(dominio, str) or not dominio.strip() or " " in dominio:
        raise ErrorUso("--dominio debe ser un nombre de dominio no vacío, sin espacios")

    faltan: list[str] = []

    if transporte_dns is None:
        dns_txt: dict[str, Any] = {"estado": "pendiente", "motivo": "sin transporte DNS inyectado en este entorno"}
        faltan.append("dns_txt: pendiente (sin transporte inyectado)")
    else:
        valores = consultar_txt(transporte_dns, dominio, servidor=servidor_doh)
        coincide = (txt_esperado in valores) if txt_esperado is not None else None
        dns_txt = {"estado": "ok" if valores else "ausente", "valores": valores, "coincide_esperado": coincide}
        if not valores:
            faltan.append("dns_txt: sin ningún registro TXT")
        elif txt_esperado is not None and not coincide:
            faltan.append("dns_txt: ninguno coincide con --txt-esperado")

    if cliente_meta is None or business_id is None:
        meta_portfolio: dict[str, Any] = {"estado": "pendiente", "motivo": "sin cliente de Meta o --business-id"}
        faltan.append("meta_portfolio: pendiente (sin cliente de Meta inyectado)")
    else:
        verificado = dominio_verificado_en_meta(cliente_meta, business_id, dominio)
        if verificado is None:
            meta_portfolio = {"estado": "pendiente", "motivo": "el dominio no aparece en owned_domains todavía"}
            faltan.append("meta_portfolio: el dominio no está dado de alta en el portfolio")
        else:
            meta_portfolio = {"estado": "verificado" if verificado else "no_verificado", "verificado": verificado}
            if not verificado:
                faltan.append("meta_portfolio: dado de alta pero no verificado")

    return ResultadoDominio(dominio=dominio, dns_txt=dns_txt, meta_portfolio=meta_portfolio, faltan=tuple(faltan))


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m infra.dominio", description="Verificación de dominio en solo lectura (DNS/TXT, portfolio de Meta).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pv = sub.add_parser("verificar")
    pv.add_argument("--dominio", required=True)
    pv.add_argument("--txt-esperado")
    pv.add_argument("--fixture-dns", help="ruta a reglas de TransporteFixture para la consulta DoH (sin esto: pendiente)")
    pv.add_argument("--business-id")
    pv.add_argument("--fixture-meta", help="ruta a reglas de TransporteFixture para owned_domains (sin esto: pendiente)")
    pv.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        transporte_dns = TransporteFixture.desde_archivo(Path(args.fixture_dns)) if args.fixture_dns else None
        cliente_meta = None
        if args.fixture_meta and args.business_id:
            from meta.cliente import ClienteMeta
            transporte_meta = TransporteFixture.desde_archivo(Path(args.fixture_meta))
            cliente_meta = ClienteMeta(transporte=transporte_meta, token="token-lectura-ficticio",
                                       app_secret="app-secret-ficticio", segundos_min_entre_ediciones=0,
                                       max_cambios_presupuesto_por_hora=100)
        resultado = verificar(args.dominio, transporte_dns=transporte_dns, txt_esperado=args.txt_esperado,
                              cliente_meta=cliente_meta, business_id=args.business_id)
        datos = {"dominio": resultado.dominio, "dns_txt": dict(resultado.dns_txt),
                 "meta_portfolio": dict(resultado.meta_portfolio), "faltan": list(resultado.faltan)}
        codigo = 0 if resultado.completo else 4
        if args.json:
            print(json.dumps({"ok": codigo == 0, "modo": "dry_run", "codigo": codigo, "datos": datos, "avisos": []},
                             sort_keys=True, ensure_ascii=False))
        else:
            print(json.dumps(datos, ensure_ascii=False, sort_keys=True))
        return codigo

    from engine import comun
    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
