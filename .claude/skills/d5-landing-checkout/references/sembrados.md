# Defectos sembrados SD5-01…25 (Anexo A1 de la spec) y protocolo de siembra rotada

> v0.2 sin pulir (borrador generado desde la spec y revisado el 2026-11-07; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño).
> Datos legibles por máquina: `evals/sembrados/sembrados.json` (mutaciones y salida esperada del QA). B = bloqueante, M = mayor. «Regla del lint» = la que emite `scripts/lint_copy.py` o `scripts/contraste_paleta.py`; «ML/MC» = mutación equivalente de CT (`tests/fixtures/contratos/mutaciones_landing/`). **Pruebas:** `.venv/bin/python -m unittest discover -s .claude/skills/d5-landing-checkout/scripts -p "test_*.py"` siembra los 12 detectables en copy y paleta (11 y 1) sobre **dos idiomas y dos macro-nichos** (24 siembras) y exige que el lint dé la regla y la severidad esperadas.

| ID | Defecto | Sev. | Check | Se detecta con | Regla del lint | ML/MC | Mutación |
|---|---|---|---|---|---|---|---|
| SD5-01 | Precio de la landing 19 y de checkout.json 17 | B | C02 | lint copy+landing.validar | D5-COPY-IMPORTE | ML-04 | sí |
| SD5-02 | event_id del píxel distinto del de la API de Conversiones | B | C09 | código+L2-lectura | — | — | archivo |
| SD5-03 | Contador de escasez que se reinicia | B | C03 | lint copy | D5-COPY-URGENCIA | — | sí |
| SD5-04 | Webhook de Stripe sin verificación de firma | B | C07 | código | — | — | fixture |
| SD5-05 | Garantía de 30 días en la landing y de 14 en reembolsos | B | C02 | lint copy+landing.validar | D5-COPY-GARANTIA-DIAS | MC-02 | sí |
| SD5-06 | Píxel cargado antes del consentimiento | B | C10 | HTML | — | ML-06 | fixture |
| SD5-07 | adid perdido en la redirección www→apex | M | C06 | código | — | — | fixture |
| SD5-08 | Imagen hero de 2 MB | M | C04 | código | — | — | archivo |
| SD5-09 | Testimonio genérico con foto, sin compra_id | B | C03 | lint copy | D5-COPY-RESENA-SIN-COMPRA | — | sí |
| SD5-10 | CTA fijo que tapa el FAQ en 360 px | M | C05 | Playwright + capturas | — | — | fixture |
| SD5-11 | Entrega con pago en estado unpaid | B | C07 | código | — | — | fixture |
| SD5-12 | /gracias dispara Purchase pendiente | B | C09 | código | — | — | fixture |
| SD5-13 | Enlace de descarga permanente | B | C08 | código | — | — | fixture |
| SD5-14 | crear-sesion acepta el importe del navegador | B | C14 | código | — | — | fixture |
| SD5-15 | Bump premarcado | B | C03 | lint copy+landing.validar | D5-COPY-BUMP-PREMARCADO | MC-04 | sí |
| SD5-16 | brief.md o .env dentro de sitio/ | B | C01 | código | — | — | fixture |
| SD5-17 | Sello o comentario EJEMPLO en producción | B | C03 | lint copy+landing.validar | D5-COPY-EJEMPLO | ML-02 | sí |
| SD5-18 | Restos de Shopify (content_for_header, #shopify-section-*) o Google Fonts remotas | M | C01 | HTML | — | ML-03 | fixture |
| SD5-19 | Paleta igual a la de la base o contraste inferior a AA | M | C12 | contraste_paleta | D5-PALETA-BASE | — | sí |
| SD5-20 | Hero con pregunta o atributo dirigido al espectador | B | C15 | lint copy + R8 | D5-COPY-HERO-PREGUNTA | — | sí |
| SD5-21 | <title>, URL o content_name con términos sensibles | B | C16 | lint copy+landing.validar | D5-COPY-DATO-SENSIBLE | ML-05 | sí |
| SD5-22 | Texto visible distinto según agente o país | B | C17 | código | — | — | fixture |
| SD5-23 | Garantía atada a un resultado (o cifra de ahorro/ingreso) | B | C15 | lint copy | D5-COPY-GARANTIA-RESULTADO | — | sí |
| SD5-24 | «IVA incluido» con régimen fiscal diferido | M | C02 | lint copy | D5-COPY-IVA-INCLUIDO | — | sí |
| SD5-25 | Falta la casilla de renuncia (UE/UK) o /desistimiento | B | C11 | lint copy+landing.validar | D5-COPY-RENUNCIA | — | sí |

**Los 13 restantes** se prueban con un `fixture_l1` (resultados simulados de los checks de código o de HTML): el QA debe leerlo, **citar la evidencia** (`salida_qa_esperada.evidencia_que_debe_citar`) y devolver `FAIL` con el hallazgo (`check_id`, `patron_clave`, `severidad`) esperado. Cuando existan los Workers y Playwright se sustituye el fixture por la ejecución real.

## Protocolo de siembra rotada (calibración del QA)
1. **Cada corrida de calibración siembra al menos 12 de los 25 defectos, con al menos 8 bloqueantes**, y los elige por rotación: la corrida `k` toma los ids con `(número del id + k) mod 3 = 0` más los bloqueantes que falten para llegar a 8; no se repite el mismo subconjunto dos corridas seguidas.
2. **Rota también el contexto:** el dorado (macro-nicho × idioma: `dinero es-ES`, `relaciones pl-PL`, y `salud en-CA` cuando exista), el lugar donde se siembra (hero, FAQ, pie) y el bloque.
3. **El QA no ve** `sembrados.json` ni el protocolo; recibe el artefacto mutado, el contrato y la rúbrica. Un dorado sin mutar acompaña cada corrida: debe dar PASS.
4. **Criterio:** detectar ≥ 90 % de los bloqueantes sembrados, 0 falsos bloqueos sobre el dorado y 0 falsos verdes en `casos-frontera.yaml` (nota 25 §11; hoy `docs/_historial/hwr-semillas/`) para los lints de claims y encuadre; recalibrar cada vez que cambie la skill del QA.
5. **Registro:** resultado en `aprendizajes_para_skill[]` del informe; un bloqueante no detectado se convierte en un caso nuevo de este archivo (eval primero: docs/03 A9).

## Pendiente de la 0.2.0 (eval primero en la próxima pasada)
El catálogo SD5-01…25 no cubre aún los defectos que introducen el plano `referente` y los datos reales. Candidatos a SD5-26…: **demo o vista previa en un `sitio/` de producción** (`L1-DEMO`, BLOQUEANTE) · **fila de S16 sin fuente o sin fecha** (`D5-COPY-COMPARACION-SIN-FUENTE`, BLOQUEANTE) · **valoración o contador sin `prueba_social_real.json`** (`L1-PRUEBA-SOCIAL`) · **barra de lanzamiento sin `precio_programado`** (`L1-BARRA-LANZAMIENTO`) · **ranura `ilustrativa` aprobada y usada como muestra real en producción** (C03/R3) · **imagen con título o cifra alterada** (R3, revisión ciega) · **precio distinto del de D3** (SD5-01 ya cubre el importe) · **expresión del referente en el copy** (nombre de bonus, cifra, frase) · **revisor nativo exigido** (J11). Se agregan junto con un dorado `referente` (copy 0.2.0) y se actualizan `test_scripts.py` (catálogo de 25 → N) y el protocolo de rotación.
