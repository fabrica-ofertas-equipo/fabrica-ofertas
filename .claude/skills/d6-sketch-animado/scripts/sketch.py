#!/usr/bin/env python3
"""sketch-ia · fábrica de sketches animados con IA (formato reel vertical 9:16).

Uso (desde la raíz del proyecto; el lanzador es .claude/skills/d6-sketch-animado/scripts/sketch):
  ./sketch nuevo <carpeta>                   crea <carpeta>/guion.yaml desde templates/guion.yaml
  ./sketch costo <proyecto>                  estima el gasto en Kie.ai
  ./sketch creditos                          muestra los créditos que quedan en Kie.ai
  ./sketch animatic <proyecto>               voces del sistema + keyframes/placeholder → vídeo de tiempos (gratis)
  ./sketch audicion <proyecto> [--solo lucas] [--voces Puck,Charon] [--texto "..."]
                                             la primera línea de cada personaje con varias voces de Google
  ./sketch voces-google [--filtro "argentina male"]  busca en la biblioteca de voces de AI Studio
  ./sketch personajes <proyecto> [--variantes 3] [--solo lucas]
  ./sketch escenarios <proyecto>
  ./sketch keyframes <proyecto> [--solo p01,p02]
  ./sketch voces <proyecto>
  ./sketch efectos <proyecto>                genera los sfx con «generar:» (ElevenLabs Sound Effects)
  ./sketch animar <proyecto> [--solo p05]
  ./sketch montar <proyecto>
  ./sketch recuperar <proyecto>              descarga tareas ya pagadas que un corte de red dejó sin bajar
  ./sketch todo <proyecto>                   personajes → escenarios → keyframes → voces → animar → montar

<proyecto> es la carpeta del sketch con guion.yaml (p. ej. ofertas/<id>/06-creativos/sketch/<ad_name>).
Todo paso salta lo que ya existe; --forzar lo rehace.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sketchlib import pipeline as P  # noqa: E402
from sketchlib.util import RAIZ, cargar_env, raiz_repo  # noqa: E402


def resolver(nombre: str) -> Path:
    """Carpeta con guion.yaml: ruta directa o relativa a la raíz del proyecto."""
    for p in (Path(nombre), raiz_repo() / nombre):
        if (p / "guion.yaml").exists():
            return p
    raise SystemExit(f"No encuentro guion.yaml en {nombre}")


def main():
    cargar_env()
    ap = argparse.ArgumentParser(description="Fábrica de sketches animados con IA", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("paso", choices=["nuevo", "costo", "creditos", "voces-google", "audicion", "animatic", "personajes", "escenarios", "keyframes", "voces", "efectos", "animar", "montar", "recuperar", "todo"])
    ap.add_argument("proyecto", nargs="?")
    ap.add_argument("--forzar", action="store_true", help="rehace aunque el archivo exista")
    ap.add_argument("--solo", help="ids separados por coma (planos o personajes)")
    ap.add_argument("--variantes", type=int, default=1, help="personajes: cuántas opciones generar por personaje")
    ap.add_argument("--voces", help="audicion: voces a probar, separadas por coma")
    ap.add_argument("--texto", help="audicion: frase a decir (por defecto, la primera línea del personaje)")
    ap.add_argument("--filtro", default="argentina", help="voces-google: palabras a buscar (acento, género, edad…)")
    ap.add_argument("--sin-render", action="store_true", help="montar: solo escribe props y .srt")
    a = ap.parse_args()

    if a.paso == "creditos":
        from sketchlib.kie import Kie
        print(f"Créditos Kie.ai: {Kie().creditos()}  (1 crédito ≈ $0.005)")
        return
    if a.paso == "voces-google":
        from sketchlib.voces import listar_voces_google
        voces = listar_voces_google(a.filtro)
        for v in sorted(voces, key=lambda v: (v.get("gender", ""), v.get("pitch", ""))):
            print(f"  {v['id']:<24}{v.get('gender', ''):<8}{v.get('pitch', ''):<8}{v.get('description', '')[:100]}")
        print(f"{len(voces)} voces")
        return
    if a.paso == "nuevo":
        if not a.proyecto:
            raise SystemExit("Indicá la carpeta: ./sketch nuevo ofertas/<id>/06-creativos/sketch/<ad_name>")
        dest = Path(a.proyecto)
        if (dest / "guion.yaml").exists():
            raise SystemExit(f"Ya existe {dest / 'guion.yaml'}")
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy(RAIZ.parent / "templates" / "guion.yaml", dest / "guion.yaml")
        print(f"Creado {dest / 'guion.yaml'}")
        return
    if not a.proyecto:
        raise SystemExit("Falta el proyecto")
    pr = P.Proyecto(resolver(a.proyecto))
    print(f"[{a.paso}] {pr.g.get('titulo', pr.slug)}")

    if a.paso == "costo":
        P.costo(pr)
    elif a.paso == "audicion":
        P.audicion(pr, solo=a.solo, voces_lista=a.voces, texto=a.texto)
    elif a.paso == "animatic":
        P.voces(pr, forzar=a.forzar, solo=a.solo, animatic=True)
        P.montar(pr, animatic=True, sin_render=a.sin_render)
    elif a.paso == "personajes":
        P.personajes(pr, forzar=a.forzar, solo=a.solo, variantes=a.variantes)
    elif a.paso == "escenarios":
        P.escenarios(pr, forzar=a.forzar)
    elif a.paso == "keyframes":
        P.keyframes(pr, forzar=a.forzar, solo=a.solo)
    elif a.paso == "voces":
        P.voces(pr, forzar=a.forzar, solo=a.solo)
    elif a.paso == "recuperar":
        P.recuperar(pr)
    elif a.paso == "efectos":
        P.efectos(pr, forzar=a.forzar, solo=a.solo)
    elif a.paso == "animar":
        P.animar(pr, forzar=a.forzar, solo=a.solo)
    elif a.paso == "montar":
        P.montar(pr, sin_render=a.sin_render)
    elif a.paso == "todo":
        P.personajes(pr)
        P.escenarios(pr)
        P.keyframes(pr)
        P.voces(pr)
        P.efectos(pr)
        P.animar(pr)
        P.montar(pr)


if __name__ == "__main__":
    main()
