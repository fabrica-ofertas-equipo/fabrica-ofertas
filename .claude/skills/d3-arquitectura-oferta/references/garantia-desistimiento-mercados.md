# Garantía y desistimiento por mercado

Fuentes: `departamentos/04-oferta.md` §3.2, `docs/_investigacion/05-legal.md` §2 (resumen por jurisdicción; casi todo `[VERIFICAR]`), nota 25 §5.3. **Sin abogado** (decisión 14): D3 describe obligaciones y riesgos para que X1 las automatice y el dueño las vea; ninguna tarea queda a la espera de un profesional legal. El contador cubre lo fiscal.

## 1. Garantía comercial (`oferta.garantia`)
- `tipo = reembolso_incondicional`; **nunca de resultado** («reconciliación o reembolso», «ahorrás o te devolvemos»: RE-14). `reembolso_condicionado` existe en el enum pero D3 no lo usa (S7, R5).
- `dias ≥ max(landing.garantia_dias_min, limites.politica_reembolso_dias, mínimo legal del mercado, brief.reembolso_dias)`. Hoy `landing.garantia_dias_min` = 14 `[HIPÓTESIS]`; `limites.politica_reembolso_dias` está en `null` (el dueño no lo fijó: la oferta queda sin gasto autorizado, no se detiene). Los 7 días de los ejemplos de los creadores **no son un defecto a copiar**. 14 días es el piso recomendado; 30 es una **variante de conversión** opcional por oferta (pregunta abierta n.º 3), no un requisito.
- `texto_visible`: claro, corto, sin condiciones, sin ocultar el derecho legal («Si no te sirve, te devolvemos el importe durante 14 días. Sin preguntas.»). Tradúcelo/localízalo en el idioma de la oferta.
- **Redacción y el lint de X1** (medido con `reglas_sensibles.yaml` 1.1.0, 2026-11-06): la regla `garantias_absolutas` marca ROJO fórmulas de reembolso incondicional legítimas como «te devolvemos el dinero», «ti rimborsiamo» y «zwrot pieniędzy». Mientras X1 no las distinga, usa formas que pasan: «puedes pedir el reembolso», «puoi chiedere il rimborso», «zwrot płatności», «te devolvemos el importe». Es un falso positivo pedido a X1 (`dependencias.md` A2), no una razón para condicionar la garantía.
- Es una **decisión de negocio del dueño** (costo = reembolsos por abuso; beneficio = cumplimiento casi universal y menos disputas): la tasa esperada de reembolso del motor (`economia.tasa_reembolso_bp`) ya la pondera.

## 2. UE y Reino Unido: la garantía NO es el desistimiento
- El **derecho legal de desistimiento (14 días)** es otro derecho. En contenido digital se pierde solo con **consentimiento expreso** a la entrega inmediata y **reconocimiento de la pérdida**, en **casillas separadas y sin premarcar** (art. 16(m) de la Directiva 2011/83/UE `[VERIFICAR]`; UK: Consumer Contracts Regulations 2013 `[VERIFICAR]`). La garantía comercial **no lo sustituye ni lo oculta** (S22).
- Desde **2026-06-19** debe haber una **función de desistimiento en línea** de dos pasos, visible durante todo el plazo (Directiva (UE) 2023/2673 `[VERIFICAR]`: EUR-Lex no respondió en la lectura; fuente secundaria).
- **D3 declara, D5/X1 implementan** (L1-14, X1-J07): en `oferta.md` §F escribe que la garantía comercial de N días no sustituye el desistimiento legal, que el checkout necesita las casillas y la función, y `mercado.consumo.boton_arrepentimiento` = el valor de M1. Ninguna promesa del texto puede contradecirlos.

## 3. Resumen por jurisdicción (nota 05 §2.2; `[VERIFICAR]` salvo donde se indica)
| Mercado | Derecho de arrepentimiento / desistimiento | Excluible en contenido digital |
|---|---|---|
| UE (IT, ES, FR, DE, PL…) | 14 días; función en línea desde 2026-06-19 | Sí, con consentimiento expreso y reconocimiento separados |
| Reino Unido | 14 días (cancelación) | Sí, con consentimiento y reconocimiento |
| EE. UU. | no hay derecho general; la FTC exige cumplir lo prometido (la garantía es un compromiso) | n/a |
| Argentina | 10 días + botón de arrepentimiento (Disp. 954/2025) | no apoyarse en la excepción |
| Brasil | 7 días (CDC art. 49); zona gris en bienes digitales | asumir que aplica; **excluido de v1** (idioma, LGPD, impuestos) |
| Chile | 10 días (90 si falta la confirmación escrita) | conflicto de fuentes: tratar como «aplica» |
| Colombia | 5 días hábiles (retracto) | sin excepción digital explícita |
| México | retractación; plazo con fuentes en conflicto | exclusión posible, sin confirmar |
La política **14 días incondicionales para todos** cubre la mayoría de los mínimos de la tabla. El **mínimo legal del mercado** que usa D3 es `mercado.consumo.desistimiento_dias`; si M1 no lo trae, usa el de esta tabla con `[VERIFICAR]` en `supuestos[]`.

## 4. Precio, IVA y ancla
Precio local **con IVA incluido** (`tax_behavior: inclusive`) para el consumidor de UE/UK/LatAm (S21: precio sin IVA = MAYOR). Precio total y moneda visibles; ninguna comisión ni cargo oculto. Precio tachado o «valor real» solo con **historial real** (Ómnibus UE: el más bajo de 30 días `[VERIFICAR]`); una oferta nueva no lo tiene: `precio.anclaje = null` (S13).

## 5. Qué hace D3 y qué NO
Hace: declarar la garantía, el mínimo legal y el desistimiento para D5/X1 (oferta.md §F); comprobar `garantia.dias` contra los pisos (L1-05). No hace: diseñar las casillas ni el botón (D5), decidir el régimen fiscal ni el tipo de IVA del PDF (contador; hoy `fiscal.regimen = diferido`), ni redactar términos legales.
