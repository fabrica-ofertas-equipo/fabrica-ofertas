"""Deja el kit con los datos de esta instalación (lo corre la skill instalar-fabrica, paso 3).

  python3 scripts/kit/personalizar.py --id socia-1 --dominio midominio.com --correo soporte@midominio.com \
      [--cuenta-meta 1234567890] [--registro-url https://registro.dominio-del-dueno.com] [--seco]

Reemplaza los marcadores en todo el proyecto (guías, scripts y plantillas de tareas):
  <carpeta del proyecto> → la ruta real de esta carpeta
  soporte@tu-dominio.com → --correo        tu-dominio.com → --dominio
  TU_CUENTA_META         → --cuenta-meta (solo los números, sin «act_»); se puede pasar después
Y escribe empresa/instalacion.json con el id, una semilla nueva (orden propio del radar) y la URL del registro.
Se puede correr de nuevo: lo ya reemplazado no se toca, y la semilla no cambia si ya existe.
Nunca escribe claves: el token del registro y las API keys los pega la persona en .env.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
TEXTO = {".md", ".py", ".js", ".mjs", ".json", ".yaml", ".yml", ".toml", ".sh", ".txt", ".html", ".css", ".sql"}
SALTAR = {".git", ".venv", "node_modules", "__pycache__"}


def archivos():
    for p in RAIZ.rglob("*"):
        if p.is_file() and p.suffix.lower() in TEXTO and not (set(p.relative_to(RAIZ).parts) & SALTAR):
            if p.resolve() != Path(__file__).resolve():
                yield p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--id", required=True, help="id de la instalación que te dio el dueño del registro (p. ej. socia-1)")
    ap.add_argument("--dominio", required=True)
    ap.add_argument("--correo", required=True)
    ap.add_argument("--cuenta-meta")
    ap.add_argument("--registro-url")
    ap.add_argument("--seco", action="store_true")
    a = ap.parse_args(argv)
    if not re.fullmatch(r"[a-z0-9-]{3,40}", a.id):
        raise SystemExit("id inválido: minúsculas, números y guiones")
    if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", a.dominio):
        raise SystemExit("dominio inválido (ejemplo: midominio.com, sin https)")
    if "@" not in a.correo:
        raise SystemExit("correo inválido")
    if a.cuenta_meta and not re.fullmatch(r"\d{6,20}", a.cuenta_meta.removeprefix("act_")):
        raise SystemExit("cuenta de Meta inválida: solo los números")

    pares = [("<carpeta del proyecto>", str(RAIZ)), ("soporte@tu-dominio.com", a.correo), ("tu-dominio.com", a.dominio)]
    if a.cuenta_meta:
        pares.append(("TU_CUENTA_META", a.cuenta_meta.removeprefix("act_")))
    cambiados = 0
    for p in archivos():
        try:
            t = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        n = t
        for x, y in pares:
            n = n.replace(x, y)
        if n != t:
            cambiados += 1
            if not a.seco:
                p.write_text(n, encoding="utf-8")

    conf_p = RAIZ / "empresa" / "instalacion.json"
    conf = json.loads(conf_p.read_text(encoding="utf-8")) if conf_p.is_file() else {}
    conf.update({"id": a.id, "si_no_responde": "seguir" if a.id == "principal" else "esperar"})
    conf.setdefault("semilla", None if a.id == "principal" else secrets.token_hex(8))
    if a.registro_url:
        conf["registro_url"] = a.registro_url.rstrip("/")
    conf.setdefault("registro_url", None)
    if not a.seco:
        conf_p.parent.mkdir(parents=True, exist_ok=True)
        conf_p.write_text(json.dumps(conf, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        marca = RAIZ / "kit" / "personalizado.json"
        marca.parent.mkdir(parents=True, exist_ok=True)
        marca.write_text(json.dumps({"id": a.id, "dominio": a.dominio, "correo": a.correo, "cuenta_meta": bool(a.cuenta_meta)},
                                    ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    pend = [] if a.cuenta_meta else ["cuenta de Meta (volver a correr con --cuenta-meta cuando exista)"]
    print(f"{cambiados} archivos personalizados; instalación «{a.id}», semilla {'propia' if conf.get('semilla') else 'ninguna'}, "
          f"registro {conf.get('registro_url') or 'sin configurar'}." + (f" Pendiente: {', '.join(pend)}." if pend else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
