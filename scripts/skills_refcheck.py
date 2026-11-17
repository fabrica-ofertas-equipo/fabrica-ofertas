#!/usr/bin/env python3
"""``skills_refcheck.py`` - comprobación de referencias de rutas en skills y agentes (solo lectura).

Recorre ``.claude/skills/**/*.md`` y ``.claude/agents/*.md``, extrae las rutas del repositorio que aparecen
entre acentos graves, comillas dobles, comillas angulares o enlaces de Markdown (rutas con ``/`` que parecen
archivos) y comprueba que existen. Genera un informe Markdown con las referencias rotas por archivo.

Qué cuenta como referencia
--------------------------
Un candidato es una cadena con ``/`` cuyo último segmento lleva extensión (``references/x.md``,
``.claude/skills/d8-optimizacion/scripts/proponer.py``). Se admiten ``archivo.py:12``, ``archivo.md#ancla``,
``--bandera=ruta`` y la expansión simple de llaves (``scripts/{a,b}.py``).

Cómo se resuelve (la primera que exista)
----------------------------------------
1. desde la raíz del repositorio; 2. desde la carpeta del archivo que la cita; 3. desde la carpeta de su skill
(``references/x.md`` dentro de ``.claude/skills/<slug>/``); 4. desde ``.claude/skills/`` (``d6-creativos/references/x.md``)
y desde ``.claude/``; 5. en un agente, desde las skills que precarga (campo ``skills``) y la skill de su prefijo;
6. **por sufijo**: rutas abreviadas cuyo primer segmento no es ``references``, ``scripts``, ``templates``, ``evals`` ni ``datos``
(``barrido/ruta_b.py``, ``04-producto/producto.json``, ``analisis/x.md``) se dan por buenas si algún archivo del repositorio
termina en esa ruta. Una ruta relativa a la skill que no existe (``references/x.md``) nunca se salva por sufijo.

Qué se ignora (no cuenta como rota)
-----------------------------------
* plantillas con ``<...>``, ``{id}``, ``$VAR``, ``...``, ``AAAA``, ``OF-AAAAMM-NN`` y similares, URLs y dominios;
* patrones con ``*``/``?`` (``ofertas/*/estado.json``): se comprueban con ``glob`` solo si salen del repo versionado;
  si no, quedan como patrón;
* líneas con el marcador ``refcheck:ignore`` o con ``[EJEMPLO`` (ejemplos marcados).

Dos categorías aparte, listadas pero sin contar como rotas
----------------------------------------------------------
* **pendiente declarado**: la línea dice que el archivo todavía no existe (``[PENDIENTE``, ``no existe``, ``aún no``...);
* **dato de ejecución**: rutas bajo ``ofertas/``, ``empresa/``, ``runs/`` o ``logs/`` que no están en el repositorio porque
  las produce el sistema al correr (o las crea el dueño).

Uso (desde la raíz; solo lectura; sin red)::

    .venv/bin/python scripts/skills_refcheck.py                       # imprime el resumen
    .venv/bin/python scripts/skills_refcheck.py --informe docs/_historial/mentor-sistema/brechas/ref-check.md
    .venv/bin/python scripts/skills_refcheck.py --json                 # salida JSON

Código de salida: 0 sin referencias rotas; 1 con referencias rotas; 2 uso incorrecto.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

ROTA = "rota"
PENDIENTE = "pendiente"
EJECUCION = "ejecucion"

# Primer segmento de una ruta relativa a la propia skill: no se resuelve por sufijo (un error ahí es un error de verdad).
RELATIVAS_A_LA_SKILL = ("references", "scripts", "templates", "evals", "datos", "rubric.md", "SKILL.md")
CARPETAS_IGNORADAS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
# Carpetas de una oferta (``ofertas/<id>/NN-etapa/...``): una ruta que empieza así es relativa a la oferta.
RX_CARPETA_DE_OFERTA = re.compile(
    r"^(\d{2}-[a-z]+|modelado|qa|infra|crudo|entregables|respaldo|evidencia|inmersion|diario|cierre|ranuras|trabajo|\.staging|staging)/"
)

# Prefijos de datos que produce el sistema al correr: si no están en el repositorio no son una referencia rota.
PREFIJOS_EJECUCION = ("ofertas/", "empresa/", "runs/", "logs/")

RX_ACENTO = re.compile(r"`([^`\n]+)`")
RX_COMILLAS = re.compile(r'"([^"\n]{3,200})"')
RX_ANGULARES = re.compile(r"«([^»\n]{3,200})»")
RX_ENLACE = re.compile(r"\]\(([^)\s]+)\)")
RX_EXT = re.compile(r"\.[A-Za-z][A-Za-z0-9]{0,5}$")
RX_DOMINIO = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")
RX_MARCA_PENDIENTE = re.compile(
    r"PENDIENTE|no existe|no existen|a[uú]n no|todav[ií]a no|hoy no |sin construir|por construir|por crear|a crear|se crea"
    r"|no est[aá] (construid|instalad)|nada de esto existe|\[SIN DATO|sin esquema|hasta que exist|cuando exist"
    r"|borrad[oa]|eliminad[oa]|retirad[oa]|ya no existe|\bPedido:",
    re.IGNORECASE,
)
RX_MARCA_EJEMPLO = re.compile(r"refcheck:ignore|\[EJEMPLO", re.IGNORECASE)
RX_PLANTILLA = re.compile(
    r"[<>{}$…]|\.\.\.|AAAA|OF-[A-Z]{2,}|OF-0{6}-0{2}|OF-…|NN\b|\bXX+\b|\bxxx+\b|CORRIDA|%0\d+d|\bRUTA\b|\bARCHIVO\b", re.IGNORECASE
)
# Archivos que son, por naturaleza, el registro de lo que aún no existe: sus rutas ausentes no son un error de enlace.
ARCHIVOS_REGISTRO = {"PEDIDOS.md", "pedidos.md", "PENDIENTES.md", "preguntas-abiertas.md"}
# ``dependencias.md`` también lista lo que falta, pero allí una ruta relativa a la skill (``references/x.md``) sí se exige.
ARCHIVOS_DEPENDENCIAS = {"dependencias.md"}


@dataclass(frozen=True)
class Referencia:
    archivo: str          # ruta relativa a la raíz del archivo que cita
    linea: int
    ruta: str             # la ruta tal como se cita (ya limpia)
    estado: str           # ROTA | PENDIENTE | EJECUCION
    contexto: str = ""    # la línea (recortada)


@dataclass
class Resultado:
    revisados: int = 0
    candidatos: int = 0
    ok: int = 0
    ignorados: int = 0
    rotas: list[Referencia] = field(default_factory=list)
    pendientes: list[Referencia] = field(default_factory=list)
    ejecucion: list[Referencia] = field(default_factory=list)


# ---------------------------------------------------------------------------------------------------- extracción
def _expandir_llaves(token: str) -> list[str]:
    """``a/{b,c}.py`` -> ``[a/b.py, a/c.py]`` (un nivel; si la llave no lleva coma se deja tal cual)."""
    m = re.search(r"\{([^{}]*,[^{}]*)\}", token)
    if not m:
        return [token]
    salida: list[str] = []
    for opcion in m.group(1).split(","):
        salida.extend(_expandir_llaves(token[: m.start()] + opcion.strip() + token[m.end():]))
    return salida


def _limpiar(token: str) -> str:
    t = token.strip().strip("()[]\"'`,;:!?«»")
    if "=" in t and not t.startswith(("http", "/")):
        t = t.split("=", 1)[1].strip("\"'`")
    t = re.sub(r"#[A-Za-z0-9_\-]+$", "", t)               # ancla
    t = re.sub(r":\d+(-\d+)?$", "", t)                    # :12 o :12-30
    t = re.sub(r"[.…]+$", "", t) if t.endswith("..") else t
    return t.rstrip(".,;:)")


def _parece_archivo(t: str) -> bool:
    if "/" not in t or t.endswith("/") or t.startswith(("http:", "https:", "file:", "/", "./../", "www.", "~", "-", "@", "#")):
        return False
    ultimo = t.rsplit("/", 1)[1]
    if not RX_EXT.search(ultimo) or re.fullmatch(r"v?\d+(\.\d+)+", ultimo):
        return False
    primero = t.split("/", 1)[0]
    if RX_DOMINIO.match(primero) and not (RAIZ / primero).exists():  # un dominio, no una carpeta del repo
        return False
    return True


def _candidatos_de_texto(texto: str) -> list[str]:
    """Rutas que parecen archivos dentro de un fragmento (un acento grave, unas comillas, un enlace)."""
    salida: list[str] = []
    # ``empresa/{a.yaml, b.yaml}``: se normalizan los espacios dentro de las llaves antes de partir por espacios.
    texto = re.sub(r"\{([^{}]*)\}", lambda m: "{" + re.sub(r"\s*,\s*", ",", m.group(1).strip()) + "}", texto)
    for trozo in re.split(r"\s+", texto.strip()):
        if not trozo:
            continue
        for sub in re.split(r"[|]", trozo):
            for exp in _expandir_llaves(sub):
                # a/b.py,c/d.md (sin llaves) -> partir por coma si cada parte parece ruta
                partes = exp.split(",") if exp.count("/") > 1 and "," in exp and "{" not in exp else [exp]
                for p in partes:
                    c = _limpiar(p)
                    if c:
                        salida.append(c)
    return [c for c in salida if _parece_archivo(c)]


def extraer(texto: str) -> list[tuple[int, str, str]]:
    """``[(linea, ruta, contexto)]`` de un documento. Mantiene el orden y quita duplicados por línea."""
    vistos: set[tuple[int, str]] = set()
    salida: list[tuple[int, str, str]] = []
    for n, linea in enumerate(texto.splitlines(), 1):
        fragmentos: list[str] = []
        for rx in (RX_ACENTO, RX_COMILLAS, RX_ANGULARES, RX_ENLACE):
            fragmentos.extend(m.group(1) for m in rx.finditer(linea))
        for frag in fragmentos:
            for ruta in _candidatos_de_texto(frag):
                if (n, ruta) not in vistos:
                    vistos.add((n, ruta))
                    salida.append((n, ruta, linea.strip()))
    return salida


# ---------------------------------------------------------------------------------------------------- resolución
def _frontmatter_skills(texto: str) -> list[str]:
    m = re.match(r"^---\n(.*?)\n---\n", texto, re.S)
    if not m:
        return []
    r = re.search(r"^skills:\s*\[([^\]]*)\]", m.group(1), re.M)
    return [s.strip() for s in r.group(1).split(",") if s.strip()] if r else []


def bases_de(archivo: Path, texto: str, raiz: Path) -> list[Path]:
    """Carpetas contra las que se prueba una ruta relativa, en orden."""
    bases = [raiz, archivo.parent, raiz / ".claude" / "skills", raiz / ".claude"]
    skills_dir = raiz / ".claude" / "skills"
    try:
        rel = archivo.relative_to(skills_dir)
        bases.insert(2, skills_dir / rel.parts[0])
    except ValueError:
        if archivo.parent.name == "agents" and archivo.parent.parent.name == ".claude":
            precargadas = _frontmatter_skills(texto)
            prefijo = archivo.stem.rsplit("-", 1)[0]
            if skills_dir.is_dir():
                for d in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
                    if d.name in precargadas or d.name == prefijo or d.name.startswith(prefijo + "-"):
                        bases.insert(2, d)
    return bases


class IndiceDeArchivos:
    """Todos los archivos del repositorio por nombre, para resolver rutas abreviadas por sufijo."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.por_nombre: dict[str, list[str]] = {}
        for actual, carpetas, archivos in os.walk(raiz):
            carpetas[:] = [c for c in carpetas if c not in CARPETAS_IGNORADAS]
            rel = Path(actual).relative_to(raiz).as_posix()
            for a in archivos:
                self.por_nombre.setdefault(a, []).append(a if rel == "." else f"{rel}/{a}")

    def coincide_por_sufijo(self, ruta: str) -> bool:
        nombre = ruta.rsplit("/", 1)[1]
        return any(c == ruta or c.endswith("/" + ruta) for c in self.por_nombre.get(nombre, ()))


def _existe(ruta: str, bases: list[Path]) -> bool:
    if any(c in ruta for c in "*?"):
        return any(glob.glob(str(b / ruta)) for b in bases)
    return any((b / ruta).exists() for b in bases)


def _marca_cerca(rx: re.Pattern[str], linea: str, ruta: str, ventana: int = 130) -> bool:
    """¿Hay un marcador cerca de la ruta (misma frase), no en cualquier parte de una línea larga o de una fila de tabla?"""
    i = linea.find(ruta)
    if i < 0:
        i = linea.find(ruta.rsplit("/", 1)[-1])
    if i < 0:
        return bool(rx.search(linea))
    return bool(rx.search(linea[max(0, i - ventana): i + len(ruta) + ventana]))


def clasificar(ruta: str, linea: str, bases: list[Path], indice: IndiceDeArchivos | None = None,
              archivo: Path | None = None) -> str | None:
    """``None`` si existe o se ignora; ``ROTA``, ``PENDIENTE`` o ``EJECUCION`` si no."""
    if RX_MARCA_EJEMPLO.search(linea) or RX_PLANTILLA.search(ruta):
        return None
    if _existe(ruta, bases):
        return None
    if "*" in ruta or "?" in ruta:
        return None  # patrón sin coincidencias: dato de ejecución o ejemplo genérico, no una ruta concreta
    primero = ruta.split("/", 1)[0]
    if indice is not None and primero not in RELATIVAS_A_LA_SKILL and indice.coincide_por_sufijo(ruta):
        return None
    if ruta.startswith(PREFIJOS_EJECUCION) or RX_CARPETA_DE_OFERTA.match(ruta):
        return EJECUCION
    en_registro = archivo is not None and (
        archivo.name in ARCHIVOS_REGISTRO or (archivo.name in ARCHIVOS_DEPENDENCIAS and primero not in RELATIVAS_A_LA_SKILL)
    )
    casilla_sin_marcar = bool(re.match(r"\s*[-*] \[ \]", linea))  # '- [ ] ...': lista de lo que falta
    if _marca_cerca(RX_MARCA_PENDIENTE, linea, ruta) or casilla_sin_marcar or en_registro:
        return PENDIENTE
    return ROTA


def revisar(raiz: Path = RAIZ) -> Resultado:
    res = Resultado()
    indice = IndiceDeArchivos(raiz)
    archivos = sorted((raiz / ".claude" / "skills").rglob("*.md")) + sorted((raiz / ".claude" / "agents").glob("*.md"))
    for archivo in archivos:
        if CARPETAS_IGNORADAS.intersection(archivo.parts):  # node_modules y demás código vendido no es documentación nuestra
            continue
        res.revisados += 1
        texto = archivo.read_text(encoding="utf-8", errors="replace")
        bases = bases_de(archivo, texto, raiz)
        rel = str(archivo.relative_to(raiz))
        for linea, ruta, contexto in extraer(texto):
            res.candidatos += 1
            estado = clasificar(ruta, contexto, bases, indice, archivo)
            if estado is None:
                if RX_MARCA_EJEMPLO.search(contexto) or RX_PLANTILLA.search(ruta) or "*" in ruta or "?" in ruta:
                    res.ignorados += 1
                else:
                    res.ok += 1
                continue
            ref = Referencia(rel, linea, ruta, estado, contexto[:160])
            {ROTA: res.rotas, PENDIENTE: res.pendientes, EJECUCION: res.ejecucion}[estado].append(ref)
    return res


# ---------------------------------------------------------------------------------------------------- informe
def _por_archivo(refs: list[Referencia]) -> dict[str, list[Referencia]]:
    d: dict[str, list[Referencia]] = {}
    for r in refs:
        d.setdefault(r.archivo, []).append(r)
    return d


def _tabla(refs: list[Referencia], con_contexto: bool = False) -> list[str]:
    lineas: list[str] = []
    for archivo, items in _por_archivo(refs).items():
        lineas.append(f"### `{archivo}`")
        for r in items:
            extra = f" — «{r.contexto[:110].replace('|', '/')}»" if con_contexto else ""
            lineas.append(f"- L{r.linea}: `{r.ruta}`{extra}")
        lineas.append("")
    return lineas


DUENOS_POR_PREFIJO = (
    ("contratos/", "S-A (contratos)"), ("departamentos/", "S-A"), ("docs/", "S-A"), ("empresa/", "dueño / S-A (parámetros y datos)"),
    ("engine/", "S-B (motor)"), ("decision/", "S-B"), ("infra/", "S-B"), ("meta/", "S-B"), ("agentes/", "S-B"),
    ("scripts/", "S-B (código) o S-C si es un script de skill"), (".claude/settings", "S-B (runner)"),
)


def _dueno_probable(ruta: str) -> str:
    for prefijo, dueno in DUENOS_POR_PREFIJO:
        if ruta.startswith(prefijo):
            return dueno
    return "S-C (skills y agentes)"


def _resumen_pendientes(pendientes: list[Referencia]) -> list[str]:
    """Tabla de rutas ausentes (una fila por ruta) con cuántos archivos las citan y quién las construiría."""
    if not pendientes:
        return ["Ninguno.", ""]
    citas: dict[str, set[str]] = {}
    for r in pendientes:
        citas.setdefault(r.ruta, set()).add(r.archivo)
    L = ["| Ruta ausente | Archivos que la citan | Dueño probable |", "|---|---|---|"]
    for ruta in sorted(citas):
        L.append(f"| `{ruta}` | {len(citas[ruta])} | {_dueno_probable(ruta)} |")
    return L + [""]


def informe_markdown(res: Resultado, fecha: str, notas: list[str] | None = None) -> str:
    L = [
        "# Comprobación de referencias de skills y agentes",
        "",
        f"Generado el {fecha} por `scripts/skills_refcheck.py` (solo lectura; stdlib; sin red). "
        "Recorre `.claude/skills/**/*.md` y `.claude/agents/*.md`, extrae las rutas del repositorio entre acentos graves, "
        "comillas o enlaces (con `/` y extensión) y comprueba que existen. Reglas y límites en la cabecera del script.",
        "",
        "## Resumen",
        "",
        "| Medida | Cantidad |",
        "|---|---|",
        f"| Archivos revisados | {res.revisados} |",
        f"| Rutas candidatas | {res.candidatos} |",
        f"| Existen | {res.ok} |",
        f"| Ignoradas (plantillas, patrones, ejemplos marcados) | {res.ignorados} |",
        f"| **Rotas** | **{len(res.rotas)}** |",
        f"| Pendiente declarado (la línea dice que aún no existe) | {len(res.pendientes)} |",
        f"| Dato de ejecución (`ofertas/`, `empresa/`, `runs/`, `logs/` que aún no están en el repo) | {len(res.ejecucion)} |",
        "",
    ]
    if notas:
        L += ["## Notas del barrido", ""] + [f"- {n}" for n in notas] + [""]
    L += ["## Referencias rotas por archivo", ""]
    if res.rotas:
        L += _tabla(res.rotas, con_contexto=True)
    else:
        L += ["Ninguna.", ""]
    L += ["## Destinos ausentes declarados pendientes, por dueño probable", ""]
    L += _resumen_pendientes(res.pendientes)
    L += ["## Pendientes declarados (no cuentan como rotas)", ""]
    L += _tabla(res.pendientes) if res.pendientes else ["Ninguno.", ""]
    L += ["## Datos de ejecución que no están en el repositorio (no cuentan como rotas)", ""]
    L += _tabla(res.ejecucion) if res.ejecucion else ["Ninguno.", ""]
    return "\n".join(L).rstrip("\n") + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Comprueba que existen las rutas citadas en skills y agentes (solo lectura).")
    ap.add_argument("--raiz", default=str(RAIZ), help="raíz del repositorio (por defecto, la de este script)")
    ap.add_argument("--informe", help="escribe el informe Markdown en esta ruta")
    ap.add_argument("--fecha", default="", help="fecha del informe (AAAA-MM-DD); por defecto, hoy")
    ap.add_argument("--json", action="store_true", help="imprime el resultado como JSON")
    ap.add_argument("--nota", action="append", default=[], help="nota para el informe (repetible)")
    a = ap.parse_args(argv)
    raiz = Path(a.raiz).resolve()
    if not (raiz / ".claude").is_dir():
        print(f"ERROR: {raiz} no parece la raíz del repositorio (falta .claude/)", file=sys.stderr)
        return 2
    res = revisar(raiz)
    if a.fecha:
        fecha = a.fecha
    else:
        import datetime
        fecha = datetime.date.today().isoformat()
    if a.informe:
        destino = Path(a.informe)
        destino = destino if destino.is_absolute() else raiz / destino
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(informe_markdown(res, fecha, a.nota), encoding="utf-8")
    if a.json:
        print(json.dumps({
            "revisados": res.revisados, "candidatos": res.candidatos, "ok": res.ok, "ignorados": res.ignorados,
            "rotas": [r.__dict__ for r in res.rotas],
            "pendientes": [r.__dict__ for r in res.pendientes],
            "ejecucion": [r.__dict__ for r in res.ejecucion],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"archivos={res.revisados} candidatas={res.candidatos} ok={res.ok} ignoradas={res.ignorados} "
              f"rotas={len(res.rotas)} pendientes={len(res.pendientes)} ejecucion={len(res.ejecucion)}")
        for archivo, items in _por_archivo(res.rotas).items():
            print(f"  {archivo}")
            for r in items:
                print(f"    L{r.linea}: {r.ruta}")
    return 1 if res.rotas else 0


if __name__ == "__main__":
    sys.exit(main())
