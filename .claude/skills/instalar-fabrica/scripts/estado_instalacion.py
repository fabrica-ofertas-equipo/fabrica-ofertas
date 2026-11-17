"""Qué falta para que la fábrica quede instalada. Solo lee; nunca muestra el valor de una clave.

  python3 .claude/skills/instalar-fabrica/scripts/estado_instalacion.py [--json]

Lo que el script no puede ver (conectores de Claude, tareas programadas, sesión iniciada en el navegador integrado)
lo comprueba Claude con sus herramientas y lo anota en kit/estado-instalacion.json con `marcar`:
  python3 .claude/skills/instalar-fabrica/scripts/estado_instalacion.py marcar <paso> [--nota "…"]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
ESTADO = RAIZ / "kit" / "estado-instalacion.json"
MANUALES = {  # pasos que comprueba Claude con sus herramientas
    "conector-meta": "Conector de Meta Ads respondiendo (ads_get_ad_accounts devuelve la cuenta)",
    "cuenta-meta-activa": "Cuenta publicitaria activa y con medio de pago",
    "navegador-facebook": "Sesión de Facebook iniciada en el navegador integrado",
    "conector-impultienda": "Conector de Impultienda respondiendo (resumen_cuenta)",
    "navegador-impultienda": "Sesión de Impultienda iniciada en el navegador integrado",
    "impul-pay": "Medios de cobro activos en Impultienda",
    "conector-gmail": "Gmail conectado y correo de soporte reenviando a esa casilla",
    "terminos-propios": "Términos propios del radar agregados",
    "tareas": "Tareas programadas creadas",
    "celular": "App de Claude en el celular con avisos",
}


def _env() -> dict:
    out = {}
    p = RAIZ / ".env"
    if p.is_file():
        for ln in p.read_text(encoding="utf-8").splitlines():
            if "=" in ln and not ln.lstrip().startswith("#"):
                k, v = ln.split("=", 1)
                out[k.strip()] = bool(v.strip().strip('"').strip("'"))
    return out


def _version(cmd: list[str]) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return (r.stdout or r.stderr).strip().splitlines()[0] if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _puerto(p: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", p)) == 0


def chequeos() -> list[dict]:
    env = _env()
    venv_py = RAIZ / ".venv" / "bin" / "python"
    c = []

    def add(paso, ok, detalle, obligatorio=True):
        c.append({"paso": paso, "ok": bool(ok), "detalle": detalle, "obligatorio": obligatorio})

    for herramienta, cmd in (("homebrew", ["brew", "--version"]), ("git", ["git", "--version"]), ("gh", ["gh", "--version"]),
                             ("node", ["node", "--version"]), ("ffmpeg", ["ffmpeg", "-version"])):
        v = _version(cmd)
        add(herramienta, v, v or "falta instalar")
    add("google-chrome", Path("/Applications/Google Chrome.app").exists(), "para hacer los PDF y abrir el panel")
    add("python-venv", venv_py.is_file(), _version([str(venv_py), "--version"]) or "falta .venv (paso 2)")
    deps = _version([str(venv_py), "-c", "import yaml, jsonschema, requests; print('ok')"]) if venv_py.is_file() else None
    add("dependencias", deps == "ok", "PyYAML, jsonschema y requests" if deps == "ok" else "falta pip install -r requirements.txt")
    pers = RAIZ / "kit" / "personalizado.json"
    add("personalizado", pers.is_file(), "dominio, correo e id de instalación" if pers.is_file() else "falta el paso 3")
    if pers.is_file():
        add("cuenta-meta-en-kit", json.loads(pers.read_text(encoding="utf-8")).get("cuenta_meta"), "personalizar.py --cuenta-meta")
    conf = RAIZ / "empresa" / "instalacion.json"
    add("instalacion-json", conf.is_file(), "empresa/instalacion.json")
    for k, oblig, para in (("KIE_API_KEY", True, "imágenes y videos"), ("GEMINI_API_KEY", True, "voces e imágenes"),
                           ("ELEVENLABS_API_KEY", False, "efectos de sonido"), ("REGISTRO_TOKEN", True, "registro compartido de ofertas"),
                           ("META_ACCESS_TOKEN", False, "Meta en vivo cada 10 min en el panel")):
        add(f"env:{k}", env.get(k), f"{para} ({'cargada' if env.get(k) else 'vacía en .env'})", oblig)
    terr = RAIZ / ".claude/skills/buscar-ofertas/scripts/territorio.py"
    if terr.is_file() and venv_py.is_file():
        r = subprocess.run([str(venv_py), str(terr), "estado"], capture_output=True, text=True, cwd=RAIZ, timeout=30)
        add("registro-responde", "registro: responde" in r.stdout, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()[:120])
    add("panel", _puerto(8790), "http://127.0.0.1:8790 (scripts/kit/servicios.py panel)")
    hechos = json.loads(ESTADO.read_text(encoding="utf-8")).get("manuales", {}) if ESTADO.is_file() else {}
    for paso, desc in MANUALES.items():
        add(paso, paso in hechos, desc + (f" — {hechos[paso].get('nota')}" if paso in hechos and hechos[paso].get("nota") else ""))
    return c


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("accion", nargs="?", default="ver", choices=["ver", "marcar", "desmarcar"])
    ap.add_argument("paso", nargs="?")
    ap.add_argument("--nota")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.accion in ("marcar", "desmarcar"):
        if a.paso not in MANUALES:
            raise SystemExit(f"paso desconocido; opciones: {', '.join(MANUALES)}")
        d = json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.is_file() else {}
        m = d.setdefault("manuales", {})
        if a.accion == "marcar":
            m[a.paso] = {"cuando": dt.datetime.now().isoformat(timespec="minutes"), "nota": a.nota}
        else:
            m.pop(a.paso, None)
        ESTADO.parent.mkdir(parents=True, exist_ok=True)
        ESTADO.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{a.paso}: {'hecho' if a.accion == 'marcar' else 'pendiente'}")
        return 0
    c = chequeos()
    if a.json:
        print(json.dumps(c, ensure_ascii=False, indent=1))
    else:
        for x in c:
            marca = "✓" if x["ok"] else ("✗" if x["obligatorio"] else "·")
            print(f"{marca} {x['paso']:<24} {x['detalle']}")
        falta = [x["paso"] for x in c if not x["ok"] and x["obligatorio"]]
        print(f"\n{'LISTA: todo lo obligatorio está hecho.' if not falta else 'Falta: ' + ', '.join(falta)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
