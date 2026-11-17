"""Crea la carpeta de trabajo de una oferta nueva con el código de la corrida de México listo para adaptar.

Uso (desde la raíz del repositorio): python3 .claude/skills/modelar-y-lanzar-oferta/scripts/nueva_oferta.py <slug> [--seco]
  <slug>  nombre de carpeta en minúsculas con guiones, p. ej. br-patrones-crochet → ofertas/_borrador-br-patrones-crochet/

Copia SOLO código (scripts de producto, landing y creativos). Los datos de ejemplo (guiones, desarme, copy, anuncios)
se quedan en la skill, en ejemplo-mx/, para consultarlos: en una oferta nueva se escriben desde cero.
No pisa nada: si la carpeta ya existe, se detiene.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
RAIZ = SKILL.parents[2]  # .claude/skills/<skill> → raíz del repositorio
EJEMPLO = SKILL / "ejemplo-mx"

CARPETAS = [
    "modelado", "02-validacion/inmersion", "03-oferta", "04-producto/scripts", "04-producto/entregables",
    "05-landing/assets", "05-landing/publicar", "06-creativos/scripts", "06-creativos/audio", "06-creativos/clips",
    "06-creativos/keyframes", "06-creativos/videos", "07-campana", "marca/posts",
]
CODIGO = [  # (origen dentro de ejemplo-mx, se copia a la misma ruta de la oferta)
    "04-producto/scripts", "05-landing/assets", "06-creativos/scripts",
]
ESTADO = """# Estado de la oferta {slug}

Marcar cada fase al terminarla, con fecha y la evidencia (archivo, URL o ID). Detalle de cada fase: references/ de la skill.

- [ ] 0. Arranque: sesión de Impultienda abierta por el dueño, cuenta de Meta activa y con pago, créditos de Kie
- [ ] 1. Oferta elegida con la skill buscar-ofertas (referente, page_id, anuncios activos, antigüedad)
- [ ] 2. Mercado elegido con elegir_mercado.py v3 (país entero; comprobado que el referente no pauta ahí)
- [ ] 3. Desarme del referente (modelado/desarme.md: landing bloque por bloque, anuncios plano por plano, checkout)
- [ ] 4. Inmersión y guía de voz (02-validacion/inmersion/)
- [ ] 5. Marca: nombre, fan page, píxel
- [ ] 6. Producto: PDF final revisado
- [ ] 7. Tienda: producto, precio 19/27 (máx(19 USD, referente)), checkout, píxel (dataset_id de ads_get_datasets), imagen de producto
- [ ] 8. Landing publicada y medida contra el referente en móvil
- [ ] 9. Creativos: misma mezcla y duraciones que el referente; galería para el dueño
- [ ] 10. Campaña creada: CBO de 3 tickets del producto principal (el completo si hay niveles), inicio a las 00:00 del día siguiente (hora del mercado), anuncios en pausa, sin errores
- [ ] 11. control_previo.py (escalar-oferta) → mirar la hora otra vez → activar sola → verificar (rechazados: se apelan, no se reemplazan; sin ningún anuncio no rechazado esa campaña no sale)
- [ ] 12. Pendientes del dueño comunicados (compra de prueba, voces, token CAPI)

## Datos

- Referente:
- Mercado:
- Marca:
- Tienda:
- Página / píxel / cuenta / campaña / conjunto:
- Gasto en créditos:
"""


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    seco = "--seco" in sys.argv
    if len(args) != 1 or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", args[0]):
        print(__doc__)
        return 2
    slug = args[0]
    dest = RAIZ / "ofertas" / f"_borrador-{slug}"
    if dest.exists():
        print(f"Ya existe {dest}: no se toca nada.")
        return 1
    plan = [f"crear {dest.relative_to(RAIZ)}/{c}" for c in CARPETAS]
    copias = []
    for rel in CODIGO:
        for f in sorted((EJEMPLO / rel).iterdir()):
            if f.is_file():
                copias.append((f, dest / rel / f.name))
    plan += [f"copiar {o.relative_to(SKILL)} → {d.relative_to(RAIZ)}" for o, d in copias]
    plan.append(f"copiar ejemplo-mx/05-landing/landing.plantilla.html → {dest.relative_to(RAIZ)}/05-landing/landing.plantilla.html")
    plan.append(f"escribir {dest.relative_to(RAIZ)}/estado.md")
    if seco:
        print("\n".join(plan))
        return 0
    for c in CARPETAS:
        (dest / c).mkdir(parents=True, exist_ok=True)
    for o, d in copias:
        shutil.copy2(o, d)
    shutil.copy2(EJEMPLO / "05-landing/landing.plantilla.html", dest / "05-landing/landing.plantilla.html")
    (dest / "estado.md").write_text(ESTADO.format(slug=slug), encoding="utf-8")
    print(f"Lista: {dest.relative_to(RAIZ)} ({len(copias) + 2} archivos). Siguiente: adaptar lo marcado en ejemplo-mx/LEEME.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
