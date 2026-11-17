# Fábrica de ofertas

Sistema que busca ofertas digitales que ya venden en la Biblioteca de Anuncios de Meta, las modela (producto en PDF, tienda en Impultienda, landing y anuncios en video) y las lanza, vigila, escala y corta solo, con Claude.

## Cómo se instala

1. Instalá la app de escritorio de Claude en una Mac (con un plan pago) y abrí la pestaña **Code**.
2. Escribile a Claude:

   > Instalá la fábrica desde este repositorio: `<link de este repositorio>`

3. Claude te va guiando paso a paso: herramientas, cuentas (Meta, Impultienda, dominio, claves de IA), panel y tareas automáticas. Lo que requiere tus manos (contraseñas, tarjetas, datos personales, pegar claves) lo hacés vos; todo lo demás lo hace Claude y lo comprueba. Si cortás, decile «seguí con la instalación» y retoma donde quedó.

Antes de empezar pedile al dueño del sistema, por un canal privado: tu **id de instalación**, tu **token del registro** y la **dirección del registro**. Con eso tu fábrica no modela las mismas ofertas que las demás.

---

## Para Claude (si te pasaron el link de este repositorio)

Es un repositorio privado. Para instalar:

1. Seguí el paso 1 de `.claude/skills/instalar-fabrica/references/01-herramientas.md` (Homebrew, git y `gh`), con los comandos que exigen contraseña corridos por la persona en su terminal.
2. Pedile a la persona que corra `gh auth login` en su terminal (GitHub.com → HTTPS → navegador) y que haya aceptado la invitación al repositorio.
3. `gh repo clone <este repositorio> ~/Fabrica`.
4. Leé `~/Fabrica/.claude/skills/instalar-fabrica/SKILL.md` y seguilo desde el paso 1 (salteando lo ya hecho). Trabajá dentro de `~/Fabrica`.

## Qué hay adentro

- `.claude/skills/` — las skills: `buscar-ofertas` (radar y banco), `modelar-y-lanzar-oferta`, `escalar-oferta` (vigilancia, corte, escala, renovación), `backend-ofensivo` (upsells), `instalar-fabrica` y las de cada departamento.
- `REGLAS-DEL-METODO.md` — las reglas con las que opera todo (precios, cortes, presupuestos, escala).
- `dashboard/` — el panel (`http://127.0.0.1:8790`).
- `kit/tareas/` — las tareas automáticas que crea la instalación.
- `infra/workers/` — servicios en la nube (registro compartido y capa en vivo, opcional).
- `tienda/` — la capa de tienda: la fábrica vende con Impultienda, con una tienda propia con Stripe (`infra/workers/tienda-propia`) o con la plataforma que uses (skill `conectar-tienda`).

## Aportes

Si mejorás algo (un conector para tu plataforma, una corrección), mandalo con `python3 scripts/kit/aportar.py --titulo "…" <archivos>`: abre una pull request que revisa el dueño del proyecto.

## Licencia

[GNU AGPL v3](LICENSE). Podés usar, copiar y modificar la fábrica gratis. Si la ofrecés a otras personas como servicio (por ejemplo, en un servidor), tenés que publicar el código de tus cambios con la misma licencia.
