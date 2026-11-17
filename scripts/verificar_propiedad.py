"""``scripts.verificar_propiedad`` (I1, ola 2): guarda de propiedad de archivos.

Dada una lista de rutas cambiadas (o una raíz y un ancla de tiempo) y el identificador de un
componente (``--dueno B1``…``B10``, ``CT``, ``I1``), verifica que CADA ruta cae dentro de la carpeta
que la tabla de propiedad de docs/06 §2 y del plan §2 «Propiedad de archivos» asigna a ese
componente. Falla (código 3, ``ErrorValidacion``) si alguna ruta pertenece a OTRO componente
(``dueño_de(ruta) not in (None, dueno)``).

**Sin ``git``** (regla de la noche): las rutas llegan por argumento (lo que pasaría un hook o un CI
que sí tiene el diff) o, con ``--ancla RUTA``, se descubren recorriendo el árbol desde
``engine.comun.raiz()`` y quedándose con los archivos cuyo ``mtime`` es posterior al de ``ancla``
(excluyendo carpetas que nunca son código de un componente: ``.git``, ``__pycache__``, ``.venv``,
``node_modules``, ``.pytest_cache``).

**Decisión de diseño (honesta, documentada en el informe de la sesión — «Decisiones»):** una ruta que
no cae en NINGÚN patrón de la tabla (p. ej. ``README.md``, ``pyproject.toml``, ``docs/06-*.md``,
``departamentos/**``, la mayoría de ``empresa/**``/``ofertas/**`` -- datos de una oferta real, no
código de un componente) se considera **común** y NUNCA es una violación, aunque se pase
``--dueno``: este guarda existe para atrapar a un componente escribiendo en la carpeta de OTRO
componente, no para prohibir archivos de raíz o documentación compartida. Si en el futuro se quiere
que un árbol sin dueño también bloquee, agregar su patrón a :data:`TABLA_PROPIEDAD` (fail-closed
deliberado: hoy, ambigüedad = no bloquea, para no generar falsos positivos masivos la primera noche).
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from engine import comun
from engine.errores import ErrorFabrica, ErrorUso, ErrorValidacion

__all__ = ["TABLA_PROPIEDAD", "Violacion", "dueno_de", "rutas_desde_ancla", "verificar", "main"]

# Carpetas que nunca son código de un componente (bookkeeping, artefactos de proceso, cachés).
_IGNORABLES = (".git", "__pycache__", ".pytest_cache", ".venv", "node_modules", ".mypy_cache")

# ----------------------------------------------------------------------------------------------
# Tabla de propiedad: (patrón glob relativo a la raíz del repo, dueño). Primer patrón que haga
# match gana (algunos patrones de B8/CT son más específicos que el patrón ancho de otro dueño y
# van ANTES en la lista a propósito: p. ej. "infra/workers/fulfill/**" (B7) antes de "infra/**" (B8)).
# Fuente: docs/06-bases-del-testeo.md §2 y §4.1, y el plan de construcción §2 «Propiedad de archivos».
# ----------------------------------------------------------------------------------------------
TABLA_PROPIEDAD: tuple[tuple[str, str], ...] = (
    # CT (contratos) — antes que I1/B1 porque ofertas/_ejemplo y validar_esquemas son más específicos.
    ("contratos/*", "CT"), ("contratos/**", "CT"), ("scripts/validar_esquemas.py", "CT"),
    ("docs/contratos.md", "CT"), ("ofertas/_ejemplo/*", "CT"), ("ofertas/_ejemplo/**", "CT"),

    # I1 (integración, ola 2) — antes que B1 porque scripts/b0_e2e.py y scripts/b0/** son míos.
    ("tests/integracion/*", "I1"), ("tests/integracion/**", "I1"),
    ("scripts/b0_e2e.py", "I1"), ("scripts/b0/*", "I1"), ("scripts/b0/**", "I1"),
    ("scripts/verificar_propiedad.py", "I1"), ("scripts/lint_estatico.py", "I1"),
    ("tests/fixtures/engine/escenarios/*", "I1"), ("tests/fixtures/engine/escenarios/**", "I1"),
    ("tests/fixtures/meta/reales/*", "I1"), ("tests/fixtures/meta/reales/**", "I1"),
    ("tests/fixtures/datos/reales/*", "I1"), ("tests/fixtures/datos/reales/**", "I1"),
    ("tests/fixtures/b0/*", "I1"), ("tests/fixtures/b0/**", "I1"),

    # B1 (motor): núcleo + economía + registro de salida de D4/D2 (envoltorios de una línea).
    ("engine/*", "B1"), ("engine/**", "B1"), ("decision/entradas.py", "B1"),
    ("scripts/factibilidad.py", "B1"), ("scripts/producto/*", "B1"), ("scripts/producto/**", "B1"),
    ("scripts/validacion/veredicto_d2.py", "B1"), ("empresa/propuestas/parametros-b0.yaml", "B1"),
    ("tests/engine/*", "B1"), ("tests/engine/**", "B1"),
    ("tests/fixtures/engine/*", "B1"), ("tests/fixtures/engine/**", "B1"),
    # decision/{estadistica,presupuesto,reglas,simulacion}.py: cambian solo vía B1 (con revisión de R1).
    ("decision/estadistica.py", "B1"), ("decision/presupuesto.py", "B1"),
    ("decision/reglas.py", "B1"), ("decision/simulacion.py", "B1"),

    # B2 (tracking, Workers JS)
    ("tracking/workers/crear-sesion/*", "B2"), ("tracking/workers/crear-sesion/**", "B2"),
    ("tracking/workers/webhook-stripe/*", "B2"), ("tracking/workers/webhook-stripe/**", "B2"),
    ("tracking/workers/capi/*", "B2"), ("tracking/workers/capi/**", "B2"),
    ("tracking/workers/eventos/*", "B2"), ("tracking/workers/eventos/**", "B2"),
    ("tracking/workers/_lib/*", "B2"), ("tracking/workers/_lib/**", "B2"),

    # B3 (datos)
    ("datos/*", "B3"), ("datos/**", "B3"), ("tests/datos/*", "B3"), ("tests/datos/**", "B3"),
    ("tests/fixtures/datos/*", "B3"), ("tests/fixtures/datos/**", "B3"),

    # B4 (landing)
    ("landing/*", "B4"), ("landing/**", "B4"), ("tests/landing/*", "B4"), ("tests/landing/**", "B4"),
    ("tests/fixtures/landing/*", "B4"), ("tests/fixtures/landing/**", "B4"),

    # B5 (meta)
    ("meta/*", "B5"), ("meta/**", "B5"), ("scripts/meta_crear.py", "B5"), ("scripts/meta_activar.py", "B5"),
    ("scripts/pausar.py", "B5"), ("scripts/subir_presupuesto.py", "B5"),
    ("tests/meta/*", "B5"), ("tests/meta/**", "B5"), ("tests/fixtures/meta/*", "B5"), ("tests/fixtures/meta/**", "B5"),

    # B6 (compliance)
    ("compliance/*", "B6"), ("compliance/**", "B6"), ("scripts/lint_claims.py", "B6"),
    ("empresa/compliance/*", "B6"), ("empresa/compliance/**", "B6"),
    ("tests/compliance/*", "B6"), ("tests/compliance/**", "B6"),
    ("tests/fixtures/compliance/*", "B6"), ("tests/fixtures/compliance/**", "B6"),

    # B7 (postcompra + fulfill) — más específico que infra/** (B8): va ANTES.
    ("infra/workers/fulfill/*", "B7"), ("infra/workers/fulfill/**", "B7"),
    ("postcompra/*", "B7"), ("postcompra/**", "B7"),
    ("tests/postcompra/*", "B7"), ("tests/postcompra/**", "B7"),
    ("tests/fixtures/postcompra/*", "B7"), ("tests/fixtures/postcompra/**", "B7"),

    # B8 (infra, salvo fulfill)
    ("infra/*", "B8"), ("infra/**", "B8"), ("scripts/preflight.py", "B8"),
    (".github/*", "B8"), (".github/**", "B8"), ("infra/plantillas/*", "B8"), ("infra/plantillas/**", "B8"),
    (".env.example", "B8"), ("tests/infra/*", "B8"), ("tests/infra/**", "B8"),
    ("tests/fixtures/infra/*", "B8"), ("tests/fixtures/infra/**", "B8"),

    # B9 (agentes)
    ("agentes/*", "B9"), ("agentes/**", "B9"), (".claude/agents/_plantillas/*", "B9"),
    (".claude/agents/_plantillas/**", "B9"), (".claude/settings.json", "B9"),
    ("tests/agentes/*", "B9"), ("tests/agentes/**", "B9"),

    # B10 (dashboard)
    ("dashboard/*", "B10"), ("dashboard/**", "B10"),
    ("tests/dashboard/*", "B10"), ("tests/dashboard/**", "B10"),
    ("tests/fixtures/dashboard/*", "B10"), ("tests/fixtures/dashboard/**", "B10"),

    # RB (runbook, adelantado a la ola 0c)
    ("docs/10-runbook-testeo.md", "RB"),
)

# Intocable para TODOS (ninguna sesión de construcción lo posee; lo edita el dueño o Modo D).
INTOCABLES: tuple[str, ...] = (
    "scripts/modelado/*", "scripts/modelado/**", "departamentos/02-descubrimiento.md",
    "tests/scripts/test_puntaje_modelar.py", "tests/fixtures/modelado/*", "tests/fixtures/modelado/**",
)


@dataclass(frozen=True)
class Violacion:
    ruta: str
    dueno_esperado: str
    dueno_declarado: str


def _normalizar(ruta: str | Path, raiz: Path) -> str:
    """Ruta relativa a ``raiz`` con separadores ``/`` (para que los patrones de :data:`TABLA_PROPIEDAD`,
    escritos con ``/``, funcionen igual en cualquier sistema operativo)."""
    p = Path(ruta)
    rel = p.relative_to(raiz) if p.is_absolute() else p
    return rel.as_posix()


def dueno_de(ruta: str | Path, *, raiz: Path | None = None) -> str | None:
    """Dueño del PRIMER patrón de :data:`TABLA_PROPIEDAD` que haga match con ``ruta``; ``None`` si
    ninguno (ruta «común», ver docstring del módulo)."""
    rel = _normalizar(ruta, raiz or comun.raiz())
    for patron, dueno in TABLA_PROPIEDAD:
        if fnmatch.fnmatch(rel, patron):
            return dueno
    return None


def es_intocable(ruta: str | Path, *, raiz: Path | None = None) -> bool:
    rel = _normalizar(ruta, raiz or comun.raiz())
    return any(fnmatch.fnmatch(rel, patron) for patron in INTOCABLES)


def _es_ignorable(rel: Path) -> bool:
    return any(parte in _IGNORABLES for parte in rel.parts)


def rutas_desde_ancla(ancla: Path, *, raiz: Path | None = None) -> list[str]:
    """Todos los archivos bajo ``raiz`` con ``mtime`` estrictamente posterior al de ``ancla``
    (nunca usa ``git``: pensado para una sesión sin historial, o para un hook que compara contra un
    archivo-marca escrito al empezar). Excluye carpetas ignorables (ver :data:`_IGNORABLES`)."""
    base = raiz or comun.raiz()
    if not ancla.is_file():
        raise ErrorUso(f"--ancla no existe o no es un archivo: {ancla}")
    corte = ancla.stat().st_mtime
    encontradas: list[str] = []
    for ruta in base.rglob("*"):
        if not ruta.is_file() or ruta.is_symlink():
            continue
        rel = ruta.relative_to(base)
        if _es_ignorable(rel):
            continue
        try:
            if ruta.stat().st_mtime > corte:
                encontradas.append(rel.as_posix())
        except OSError:
            continue
    return sorted(encontradas)


def verificar(rutas: Sequence[str], *, dueno: str, raiz: Path | None = None) -> list[Violacion]:
    """Violaciones de ``rutas`` contra ``dueno`` (vacío = todo en orden). No lanza por sí sola; el CLI
    decide el código de salida (``main``) y ``ErrorValidacion`` (3) es lo que usa un llamador programático."""
    base = raiz or comun.raiz()
    violaciones: list[Violacion] = []
    for ruta in rutas:
        esperado = dueno_de(ruta, raiz=base)
        if esperado is not None and esperado != dueno:
            violaciones.append(Violacion(ruta=_normalizar(ruta, base), dueno_esperado=esperado, dueno_declarado=dueno))
    return violaciones


def _parsear_argumentos(argv: Sequence[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="python -m scripts.verificar_propiedad",
        description="Falla (3) si alguna ruta no cae en la carpeta del dueño declarado (docs/06 §2).",
    )
    ap.add_argument("rutas", nargs="*", help="rutas cambiadas a verificar (relativas o absolutas)")
    ap.add_argument("--dueno", required=True, help="id del componente que corre la verificación (B1..B10, CT, I1, RB)")
    ap.add_argument("--ancla", help="en vez de listar rutas, descubrirlas por mtime posterior al de este archivo")
    ap.add_argument("--raiz", help="raíz del repo (por defecto engine.comun.raiz())")
    ap.add_argument("--json", action="store_true")
    return ap.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    def _principal() -> int:
        args = _parsear_argumentos(argv)
        raiz = Path(args.raiz).resolve() if args.raiz else comun.raiz()
        if args.ancla and args.rutas:
            raise ErrorUso("--ancla y una lista de rutas son excluyentes: usa uno de los dos")
        if args.ancla:
            rutas = rutas_desde_ancla(Path(args.ancla), raiz=raiz)
        elif args.rutas:
            rutas = list(args.rutas)
        else:
            raise ErrorUso("hace falta --ancla o al menos una ruta")
        violaciones = verificar(rutas, dueno=args.dueno, raiz=raiz)
        if args.json:
            datos = {"dueno": args.dueno, "rutas_verificadas": len(rutas),
                    "violaciones": [v.__dict__ for v in violaciones]}
            print(json.dumps({"ok": not violaciones, "modo": "dry_run", "codigo": 0 if not violaciones else 3,
                              "datos": datos, "avisos": [f"{v.ruta}: es de {v.dueno_esperado}" for v in violaciones]},
                             sort_keys=True, ensure_ascii=False, separators=(",", ":")))
        elif violaciones:
            for v in violaciones:
                print(f"FUERA DE PROPIEDAD: {v.ruta} es de {v.dueno_esperado}, no de {v.dueno_declarado}", file=sys.stderr)
        else:
            print(f"{len(rutas)} ruta(s) verificada(s) contra {args.dueno}: todas en orden")
        if violaciones:
            raise ErrorValidacion(f"{len(violaciones)} ruta(s) fuera de la propiedad de {args.dueno}")
        return 0

    return comun.ejecutar_cli(_principal)


if __name__ == "__main__":
    sys.exit(main())
