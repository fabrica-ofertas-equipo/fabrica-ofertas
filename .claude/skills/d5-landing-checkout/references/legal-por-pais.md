# Páginas legales y banner por jurisdicción (plantilla del sistema; sin abogado)

> v0.2 sin pulir (borrador generado desde la spec y revisado el 2026-11-07; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño).
> **Decisión 14 del dueño (2026-11-06, backbone):** las páginas legales y el banner los **genera el sistema desde plantilla**; el preflight **solo comprueba que existan y respondan 200**; X1 automatiza lo verificable (claims, avisos, sellos, líneas rojas) y el contador cubre lo fiscal. Ninguna tarea, gate ni checklist de D5 exige revisión de un abogado. Es un **riesgo residual aceptado por el dueño**: este archivo describe las obligaciones para que el generador y X1 las automaticen y el dueño las vea, **no** es asesoría legal. Todo lo marcado `[VERIFICAR]` viene de la spec (A3) o de las notas 05 y 22e y no se releyó hoy en la fuente oficial.

## 1. Las siete páginas base (+ una) y qué lleva cada una

| Ruta | Contenido mínimo | Datos que alimentan | Se comprueba |
|---|---|---|---|
| `/legal/vendedor` | razón social de la LLC, dirección, ID fiscal, correo de contacto; «marca sin cara, empresa no anónima» | datos de la LLC (D0) `[PENDIENTE: ruta; DD del dueño]` | L-01; existe, 200, sin `{{ }}`, datos completos |
| `/legal/terminos` | licencia de uso personal (sin reventa ni redistribución), entrega digital, alcance del producto | `producto`, `oferta` | existe, 200 |
| `/legal/privacidad` | qué datos se tratan (pedido y entrega), proveedores (Stripe, correo, Cloudflare), no se piden datos de salud, cómo pedir la baja | `mercado.consumo.ley_privacidad` | existe, 200 |
| `/legal/reembolsos` | garantía comercial de `{garantia_dias}` días, cómo pedirla; **separada** del derecho legal de desistimiento donde aplica | `oferta.garantia`, `mercado.consumo` | = `garantia_dias` (C11) |
| `/legal/cookies` | cookie propia de elección y, solo si se acepta, de marketing; cómo cambiar la elección | `tracking.consent_gating` | existe, enlazada desde el banner |
| `/legal/aviso` | contenido informativo; no es asesoramiento médico, financiero, fiscal ni de pareja; 18+; no garantiza resultados | `riesgo`, macro-nicho | existe; coherente con S14 |
| `/legal/entrega` | cómo y cuándo se entrega, vencimiento y límite del enlace, reenvío, soporte | `producto.entrega` | existe; coherente con S12 |
| `/desistimiento` | función de desistimiento en **dos pasos**, **sin login**, con acuse o código; solo si `mercado.consumo.boton_arrepentimiento` | página propia (decidido: `/desistimiento`, no dentro de reembolsos) que genera `landing.generar` si la ruta figura en `rutas.json`; la función `POST /api/desistimiento` es de D10 `[PENDIENTE: SB-17]` | existe y funciona (C11, SD5-25) |

Todas enlazadas desde el pie (S14) y desde `/comprar`; `<html lang>` = `locale`; la plantilla por idioma vive en `landing/textos.py` (es, en, it, pl); otro idioma cae a `en` con un aviso de `landing.generar` que **no bloquea por código**: lo exige el Maker y lo verifica el QA hasta que SB-17 añada la tabla (de, fr, ro según el primer mercado) y decida si bloquea.

## 2. Extras por jurisdicción (los automatiza X1 / C11; `[VERIFICAR]` salvo nota)

| Región | Qué añade o endurece |
|---|---|
| **UE** | información precontractual (Directiva 2011/83/UE, art. 6); botón de pedido con obligación de pago; **renuncia expresa a la entrega inmediata en casilla separada** (art. 16(m) `[VERIFICAR]`); función de desistimiento (art. 11a de la Directiva 2023/2673, desde 2026-06-19 `[VERIFICAR]`) |
| **Reino Unido** | Consumer Contracts Regulations 2013 y DMCC (reseñas, *drip pricing*) |
| **DE / AT** | Impressum (§ 5 DDG; ECG § 5); sin formato curso ni soporte (FernUSG) |
| **FR** | mentions légales y médiateur; contenido y documentación en francés (Toubon); renuncia en tres pasos |
| **PL** | regulamin; toda la documentación al consumidor en polaco (Ley del Idioma Polaco, art. 7a y 8) |
| **IT** | Codice del Consumo |
| **EE. UU.** | FTC (reseñas, urgencia, precios, endosos); sin obligación de desistimiento |
| **AR** | botón de arrepentimiento (Disp. 954/2025) |
| **Relaciones, duelo y ruptura** | ayuda del país (`empresa/compliance/ayuda_por_pais.yaml`, vigente ≤ `compliance.ayuda_max_antiguedad_dias` = 180 `[PENDIENTE: LT-49; formato provisional hasta que X1 lo entregue]`); en todo producto de conflicto de pareja o familia: «Si temes por tu seguridad, no uses este material» |

## 3. Banner de consentimiento (componente)
Aceptar, Rechazar y Personalizar con el **mismo peso visual**; marketing apagado por defecto; elección en cookie propia con **versión y fecha del texto**; mismo texto en todos los países (no hay geolocalización). Los textos salen de `copy.json#banner`. El registro de consentimientos viaja en `checkout.consentimientos` y D10 lo asienta en `empresa/datos/consentimientos.jsonl`.

## 4. Casillas en `/comprar`
`/comprar` es una página **estática** con UN `<form method="post" action="/api/sesion">` (decisión de arranque de pago, `docs/_historial/decision-arranque-de-pago.md`; operativo en `landing/PROCESO.md` §5). Casillas **nunca premarcadas**, separadas y con texto versionado: (1) `renuncia_desistimiento` (`required`) solo donde corresponda (UE/UK; el generador la exige según `checkout.compra.renuncia.requerido` y, mientras falte, según el locale) con `texto_version` y la hora UTC como evidencia (`renuncia_ts` en la metadata); (2) `bump` solo con `bump_modo = oferta_previa`. Los términos y la política de reembolsos se **enlazan** debajo del botón (Stripe recoge los términos; no es un campo del formulario). La casilla de renuncia no se combina con «comprar». `visitor_id` y los parámetros de anuncio no van en el HTML: los lleva el Worker desde las cookies `fab_vid` y `fab_attr`, que `consentimiento.js` escribe solo tras el consentimiento de marketing.

## 5. Criterio de «listo» del paso
Las siete páginas (+ `/desistimiento` si aplica) existen, responden 200, están enlazadas, no tienen marcadores sin rellenar, el reembolso coincide con la garantía y la garantía comercial no oculta el derecho legal. **No** se pide revisión legal humana (decisión 14). Riesgos residuales a nombrar en el informe: obligaciones omitidas por país, texto de renuncia, régimen fiscal diferido.
