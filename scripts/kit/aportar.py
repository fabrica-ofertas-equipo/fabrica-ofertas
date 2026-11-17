#!/usr/bin/env python3
"""Manda una mejora tuya al repositorio abierto de la fábrica, como pull request (lado de quien instaló).

    python3 scripts/kit/aportar.py --titulo "Adaptador de Hotmart" tienda/adaptadores/hotmart.py tienda/muestras/hotmart
    python3 scripts/kit/aportar.py --titulo "…" <archivos> --enviar      # sin --enviar solo muestra lo que mandaría

Solo viajan los archivos que nombrás, y solo de código, skills, pruebas o guías. Nunca .env, ofertas/, kit/personalizado.json
ni nada que tenga un valor de tu .env (si lo encuentra, frena). Usa gh: hace un fork del repositorio original, sube una rama
`aporte/<fecha>` y abre la pull request. El dueño del proyecto la revisa antes de sumarla.
Antes de --enviar, el agente le muestra a la persona qué se va a mandar y espera su «sí».
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PERMITIDO = re.compile(r"^(tienda|\.claude/skills|scripts|tests|dashboard|infra|docs|engine|landing|meta|postcompra|tracking)/")
PROHIBIDO = re.compile(r"(^|/)(\.env|ofertas/|kit/personalizado|.*\.(pem|key|db|sqlite3))")


def sh(*a: str, ok: bool = True) -> str:
    r = subprocess.run(list(a), cwd=RAIZ, capture_output=True, text=True)
    if ok and r.returncode != 0:
        raise SystemExit(f"falló «{' '.join(a[:3])}…»: {r.stderr.strip()[:400]}")
    return r.stdout


def archivos(rutas: list[str]) -> list[str]:
    out = []
    for r in rutas:
        p = (RAIZ / r).resolve()
        for f in ([p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file())):
            rel = f.relative_to(RAIZ).as_posix()
            if "__pycache__" in rel:
                continue
            if PROHIBIDO.search(rel) or not PERMITIDO.search(rel):
                raise SystemExit(f"no se puede aportar {rel}: solo código, skills, pruebas y guías")
            out.append(rel)
    return out


def secretos() -> list[str]:
    env = RAIZ / ".env"
    return [l.split("=", 1)[1].strip().strip('"') for l in (env.read_text(encoding="utf-8").splitlines() if env.is_file() else [])
            if "=" in l and not l.startswith("#") and len(l.split("=", 1)[1].strip()) >= 12]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rutas", nargs="+")
    ap.add_argument("--titulo", required=True)
    ap.add_argument("--detalle", default="")
    ap.add_argument("--enviar", action="store_true")
    a = ap.parse_args(argv)
    fs = archivos(a.rutas)
    vals = secretos()
    for f in fs:
        t = (RAIZ / f).read_text(encoding="utf-8", errors="ignore")
        if any(v in t for v in vals):
            raise SystemExit(f"FRENADO: {f} contiene un valor de tu .env")
    print("Se mandaría:\n" + "\n".join(f"  {f}" for f in fs))
    if not a.enviar:
        print("(prueba: agregá --enviar para mandarlo)")
        return 0
    origen = sh("git", "remote", "get-url", "origin").strip()
    repo = re.sub(r"^.*github\.com[:/]|\.git$", "", origen)
    rama = f"aporte/{dt.datetime.now():%Y%m%d-%H%M}"
    sh("gh", "repo", "fork", repo, "--remote", "--remote-name", "aporte", ok=False)
    base = sh("git", "rev-parse", "HEAD").strip()
    sh("git", "fetch", "-q", "origin", "main")
    sh("git", "worktree", "add", "-q", "-b", rama, f"/tmp/{rama.replace('/', '-')}", "origin/main")
    wt = Path(f"/tmp/{rama.replace('/', '-')}")
    try:
        for f in fs:
            (wt / f).parent.mkdir(parents=True, exist_ok=True)
            (wt / f).write_bytes((RAIZ / f).read_bytes())
        subprocess.run(["git", "add", *fs], cwd=wt, check=True)
        subprocess.run(["git", "commit", "-q", "-m", a.titulo], cwd=wt, check=True)
        subprocess.run(["git", "push", "-q", "aporte", rama], cwd=wt, check=True)
        subprocess.run(["gh", "pr", "create", "--repo", repo, "--head", f"{sh('gh', 'api', 'user', '-q', '.login').strip()}:{rama}",
                        "--title", a.titulo, "--body", (a.detalle or a.titulo) + f"\n\nBase local: {base[:8]}"], cwd=wt, check=True)
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=RAIZ)
    return 0


if __name__ == "__main__":
    sys.exit(main())
