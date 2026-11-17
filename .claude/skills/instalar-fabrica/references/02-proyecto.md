# 2 · Proyecto

## Bajarlo (si la persona empezó desde el link)

1. GitHub: la persona necesita una cuenta y que el dueño del sistema la haya invitado al repositorio (le llega un correo de GitHub: aceptar la invitación).
2. Iniciar sesión en GitHub desde la terminal: es interactivo, lo hace la persona en su terminal con `gh auth login` (elegir GitHub.com → HTTPS → «Login with a web browser» y pegar el código que muestra). Comprobá con `gh auth status`.
3. Bajar el proyecto a una carpeta fija, por ejemplo `~/Fabrica`:
   `gh repo clone <dueño>/<repositorio> ~/Fabrica` (el nombre sale del link que te pasaron).
4. Desde acá trabajás dentro de `~/Fabrica`. Decile a la persona que, para el uso de todos los días, abra esa carpeta en la app de Claude (pestaña Code → elegir carpeta), así se cargan solas las skills de la fábrica.

## Entorno de Python

```
cd ~/Fabrica
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt requests
cp -n .env.example .env
```

`.env` es donde viven las claves; nunca se sube a GitHub (ya está en `.gitignore`).

## Prueba rápida

`.venv/bin/python -m pytest -q tests/scripts/test_descubrimiento_banco.py` y `node --test infra/workers/registro/test/*.test.mjs` tienen que pasar. Si algo falla por una dependencia, instalala y repetí; si falla otra cosa, avisale a la persona y al dueño del sistema con el error textual.

## Actualizar (cuando el dueño publique mejoras)

`cd ~/Fabrica && git stash && git pull && git stash pop` y después `python3 scripts/kit/personalizar.py …` con los mismos datos del paso 3 (lo nuevo llega con los marcadores sin reemplazar). Si `git stash pop` choca, no borres nada: mostrale a la persona qué archivos chocan y resolvelo con ella.
