# Evals de x1-compliance (v0.1 sin pulir)

Todo se corre desde la raíz del repositorio con `.venv/bin/python`. El corredor **mide; no decide, no sella y no ajusta ningún linter**.

| Carpeta | Qué es | Cómo se corre | Criterio |
|---|---|---|---|
| `dorados/minimos-10-5.json` | Los 14 evals mínimos de la spec §10.5 (E01…E14), con entrada y salida esperada | a mano con el Maker y el QA (ver `references/como-pulirla.md`); `correr_evals.py estructura` valida el formato | cada caso da su `esperado` |
| `dorados/legitimos-deben-pasar.json` | 17 legítimos que un filtro por tema bloquearía (L01…L17; 3 amarillo-a) | igual; `correr_evals.py codigo` cuenta los falsos positivos del linter real | **sobre-bloqueo ≤ 15 %** |
| `casos-frontera/` | La suite central de 230 casos (`docs/_historial/hwr-semillas/casos-frontera.yaml`): deben pasar los legítimos y bloquearse (o reformularse) los peligrosos | `correr_evals.py suite-entrada` → clasificador ciego → `correr_evals.py suite` | **falsos verdes sobre rojos = 0**, sobre-bloqueo ≤ 15 %, concordancia por eje ≥ 90 % |
| `sembrados/` | 33 defectos sembrados (X1-S01…S18 + S19…S33) con fixtures HTML/TXT | el QA los revisa a ciegas; `correr_evals.py codigo` dice cuáles ve ya el código | QA detecta ≥ 90 % de los ★ y 100 % de los L1 |
| `adversarial/corpus.json` | 96 frases (86 rojas, 10 controles verdes): voseo, tuteo, neutro/jerga, it, pl, texto en imagen y audio | el QA clasifica sin ver `esperado` | 0 falsos verdes; la spec pide ≥ 30 por categoría e idioma: [PENDIENTE] |
| `retencion/` | Conjunto de retención | lo sella el dueño | [PENDIENTE: lo sella el dueño] |
| `salud/series.json` | 21 series simuladas de la regla de salud | `scripts/regla_salud.py --series evals/salud/series.json` | todas coinciden |

Pruebas de los scripts: `.venv/bin/python -m unittest discover -s .claude/skills/x1-compliance/scripts -p "test_*.py"` (20 pruebas: 17 originales + 3 de convenciones).

**Lo que el corredor `codigo` mide hoy (2026-11-06, tras el trabajo de S-B B6b; brechas del CÓDIGO, no de la skill; detalle y pedidos en `references/dependencias.md`):** el linter trae reglas de es-ES, es-AR, es-MX, en-US, it-IT, pl-PL, ro-RO, fr-FR y de-DE (y la categoría relaciones; las cinco últimas con `revision_nativa: false`, `[HIPÓTESIS]`): **0 frases sin reglas de locale** y **0/10 falsos positivos** sobre los controles verdes («comida sana» ya no da ROJO). Del corpus adversarial ve **79 de 86 rojos** (7 falsos verdes del código: ingresos 1, nombre-de-estado 2, peso-plazo 1, prueba-social 3); de los 14 sembrados con fixture detecta **7** y deja **7 BRECHA** que debe cazar el QA (L1-HWR-P01, D01, P04a, N01, C03, J03 y L1-S10; afiliado financiero, tasa histórica, reseña con cifra y slug sensible son brechas declaradas por S-B). `html_checks` ya ve «Quedan N» fijo y «EJEMPLO»/`lorem` (también en comentarios). Por eso el sello exige además QA PASS: el QA (L2/L3) sigue siendo la segunda red.

**Reglas de uso:** (1) ningún Maker ni linter ve `retencion/` ni los casos RT-* para ajustar nada; (2) los textos it/pl/ro/fr/de son del autor y no pasaron por revisor nativo: `[VERIFICAR]`; (3) cada rechazo real de Meta o Stripe se agrega como caso nuevo (por claim, no por oferta); (4) rotar macro-nicho e idioma de los sembrados en cada corrida para que no se memoricen.
