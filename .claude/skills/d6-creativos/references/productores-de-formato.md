# Productores de formato (inventario) y su relación con D6

Un **productor de formato** es una skill o un script que, dada una fila de la matriz de D6, fabrica la **pieza** (`assets/<ad_name>.<ext>`). D6 decide el qué (matriz, ángulo, hook, copy, claims, riesgo, paquete); el productor decide el cómo. El contrato mínimo que todos deberían cumplir está en `contrato-comun-de-formatos.md` (entrada = brief + copy; salida = pieza + fragmento de `paquete.json`). Revisado el 2026-11-07 (B1-21).

## 1. Dentro del repo

| Productor | Formato | Ruta | Estado | Entrada | Salida | ¿Cumple el contrato común? |
|---|---|---|---|---|---|---|
| **Ruta A de `d6-creativos`** (`scripts/render_estatico.py`) | `imagen`, `carrusel`, `demo-pantalla` (captura) | A, 0 créditos | **Funciona y está probado** (`scripts/test_d6.py`, `tests/creativos/`) | `copies.json` + `matriz.json` + marca de D5 (`paleta.json`, WOFF2) | `assets/<ad_name>.png` + `assets/src/<ad_name>.html` | Sí en el fondo: la fila de `paquete.json` la arma el Maker (`templates/paquete.json`) |
| **`d6-sketch-animado`** (`.claude/skills/d6-sketch-animado/`) | `video` · sub-formato «sketch animado» | C: Kie.ai + Gemini TTS + ElevenLabs + Remotion, semiasistida en la sesión del dueño | v0.1 experimental; **0 corridas reales, 0 pruebas, 0 evals** (`brechas/01` B1-18); solo ofertas verdes fuera de salud y relaciones | `.claude/skills/d6-sketch-animado/scripts/brief_desde_oferta.py` produce `brief-sketch.json` desde la oferta y una fila de la matriz con `subformato: sketch-animado` en `notas` | `assets/<ad_name>.mp4` + fila de `assets.json` + `licencias.json` + `trabajo/gasto.jsonl` | **Parcial:** cumple entrada (brief derivado de la oferta) y salida de pieza, registro previo de créditos y etiqueta de IA; **falta** el fragmento de `paquete.json` y la salida `--json` |
| Ruta B (Higgsfield) de `d6-creativos` | `video` (clips, voz, subtítulos por script) y fondos | B, créditos | Escrita, **nunca corrida**; solo existe en la sesión interactiva del dueño | matriz + guion congelado + cotización aprobada | `assets/<ad_name>.mp4` | Sí en el fondo, con las reglas de `costos-y-rutas.md` |

## 2. Fuera del repo (`~/.claude/skills/`, del dueño; los agentes desatendidos NO las leen)

Son de la marca **tuotroproyecto / el dueño** (dropshipping en Mercado Libre Argentina, voz rioplatense) y **ninguna aparece referenciada por D6 ni por los departamentos**. Se listan para que se sepa qué existe y qué falta si se quisiera reutilizar un formato para ofertas digitales; no se llaman desde D6.

| Skill | Formato (según su descripción) | Salida típica | Para ofertas digitales hoy |
|---|---|---|---|
| `sketch-estilo-pixar` | Sketch animado 3D estilizado, diálogo ping-pong, lip-sync, subtítulos de 1-3 palabras (Kie.ai, Gemini TTS, Remotion) | mp4 vertical en `entrega/` | Origen de `d6-sketch-animado`, que ya lo adaptó con las reglas duras de D6 |
| `reel-3d-tuotroproyecto` | Reel 3D explicativo con maniquíes e interfaces de Mercado Libre/WhatsApp/Instagram; incluye variantes «retro 8-bit», «CS» y «FIFA» | mp4 vertical | No sirve tal cual: marca, voz, personajes e interfaces de tuotroproyecto |
| `reel-estilo-fleta` | Edición de brutos grabados con iPhone al estilo Fletá (subtítulos palabra a palabra, motion graphics, SFX, música) | mp4 + `.srt` | Requiere brutos con rostro del creador (no entra en salud y relaciones); sin caras generadas |
| `videos-estilo-cs`, `videos-estilo-fifa`, `videos-retro-mario` | Reels con estética de shooter 2000s, partido de fútbol en consola y plataformas 8-bit | mp4 vertical | Marca tuotroproyecto; los personajes y el humor argentino no se trasladan sin reescribir |
| `editor-video`, `planificador-video` | Edición y plan de edición de videos de YouTube con CapCut | kit por capas | Herramientas de edición del creador, no productores de piezas de anuncio |
| `ideador-guiones` | Ideación de guiones (26 estructuras, historial, banco) | guion | No es un productor; su historial/banco no cubre «ofertas digitales» y varias estructuras chocan con D6 (`biblioteca-ganchos.md`) |

**Lectura:** hoy el único productor que cumple lo que D6 necesita sin intervención es la Ruta A. Los demás son semiasistidos, de otra marca o están sin probar; construir cualquiera como «productor de formato» de D6 exige (1) cumplir el contrato común, (2) vivir dentro del repo (los agentes del runner no ven `~/.claude`), (3) las claves en el motor y no en el agente (B1-18) y (4) las reglas duras de la SKILL §1 íntegras (sin testimonios, sin avatares como cliente, sin rostros en salud y relaciones, sin clips ni música descargados, cotización previa).
