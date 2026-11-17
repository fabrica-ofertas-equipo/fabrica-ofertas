# Escala por campaña con el AOV de la tienda (dueño, 16-nov)

> **Desde el 17-nov, todo en NETO y con rango** (`docs/ruido-y-confianza-2026-11-17.md`). Donde abajo dice «AOV», se usa el valor NETO por comprador del sistema: 7/14 días o la historia, sin cruzar el último cambio del embudo. Los umbrales equivalen así:
>
> | Antes (bruto) | Ahora (neto) |
> |---|---|
> | 1,8 | **1,65** |
> | 1,5 | **1,4** |
> | 3 | **2,75** |
>
> Cambian dos cosas:
> - El ROAS de la campaña se acerca a sus 3 días anteriores (50/30/20), como si fueran 3 compras previas. Si no vendió, se acerca a la oferta en 7 días; si tampoco, al empate.
> - **Para subir, además, el piso del rango (80 %) tiene que ser ≥ 1.**
>
> El motivo de cada decisión muestra el ROAS visto, el estimado y el rango.

Reemplaza la regla de `07-escala-simetrica.md` (que queda como historia y por la simulación). Análisis completo de lo que hizo el dueño a mano y por qué cambió: `docs/criterio-de-escala-2026-11-16.md`.

## 1. La regla, en palabras del dueño

> «Estoy surfeando lo que tiene buen CPA y mantiene también ROAS, ROAS comparado con el AOV de la tienda, y siempre trato de escalar por arriba de 1,8 porque tiene brecha para escalar todavía, pero a ojo.»

- **Cada campaña activa se decide sola** (principal, pocket, variaciones, réplicas). Antes la escala miraba una por oferta.
- **ROAS con AOV** = compras que Meta le atribuye a esa campaña × AOV de la tienda ÷ gasto, todo **desde el último cambio de presupuesto de esa campaña**, lo haya hecho el sistema o el dueño. El AOV es bruto ÷ compradores, con bump y upsells (lo calcula el panel, `dashboard/negocio.py`). Si la oferta tiene menos de 5 compradores, se usa el AOV de la madre (réplicas) o el ticket del completo.
- Ni el valor de compra de Meta (se queda corto) ni el ROAS de la tienda entera (mezcla campañas: daba «ROAS 6,2 con 0 compras»).

| Desde el último cambio de la campaña | Qué se hace |
|---|---|
| ROAS con AOV ≥ 1,8, ≥ 2 compras, ≥ 3 h, presupuesto < 500 USD/día | **Surfeo**: +20 % con 2-3 compras, +30 % con 4-7, +40 % con 8 o más; +10 si el ROAS es ≥ 3 (tope +50 %) |
| Lo mismo con 500 USD/día o más | +30 % cada 24 h |
| ROAS con AOV < 1,5, ≥ 3 h y (≥ 2 compras o ≥ 1,5 tickets gastados) | **−30 %**, nunca bajo el presupuesto inicial |
| Entre 1,5 y 1,8, o falta tiempo o compras | Nada |
| Iba a subir pero en las últimas 6 h (de 9 a 21 en el mercado) gastó < 40 % de lo que le tocaba | **NO_GASTA**: no se sube, no cambiaría nada (creativos o subasta) |
| Iba a subir pero faltan < 2 h para la medianoche del mercado | **TARDE**: se decide en la primera vuelta del día |
| Oferta en el día 1 de test | **EN_TEST**: no se toca |
| Oferta congelada por R16 | **CONGELADA**: no se toca |

La dosis por compras es la traducción del «a ojo» del dueño: con poca muestra se sube poco, con mucha se sube más. Todos los números en `ofertas/_funnels/reglas.json` → `escala.por_campana`.

## 2. De dónde salen los datos (sin pedirle nada a Meta)

- `scripts/nube_sync.py` (cada 5 min, sin Claude) trae de la nube el acumulado de hoy y el presupuesto de **todas** las campañas del libro y llama a `scripts/fotos_campanas.py`: guarda una foto en `ofertas/_funnels/fotos_campanas.jsonl` y cada cambio de presupuesto o de estado en `ofertas/_funnels/presupuesto_eventos.jsonl`, con **autor** («sistema» si la escala lo había decidido o la vigilancia lo anotó; «a_mano» si no).
- `escalar_presupuesto.py --auto` arma la lectura sola: último cambio de cada campaña (de los eventos), gasto, compras y valor desde ese cambio (historial diario del libro + fotos), ritmo de las últimas 6 h, AOV, fase, congelamiento y hora del mercado.
- Los cambios del dueño en el Administrador quedan registrados solos (autor «a_mano») y **reinician el reloj** de esa campaña: la escala decide con lo que pasó después de su cambio y nunca lo revierte.

## 3. En la vigilancia (paso 7)

`python3 .claude/skills/escalar-oferta/scripts/escalar_presupuesto.py --auto --registrar` → por cada campaña con SURFEAR, SUBIR_24H o BAJAR, cambiar el presupuesto diario **en el Administrador de anuncios** (nunca con `ads_update_entity`, `08-cambios-en-meta-sin-pausa.md`), comprobar por API y anotar en `presupuesto_cambios` del libro con `"campana": "<id>"`. NO_GASTA: un aviso al dueño por campaña y por día (`avisos.py avisar no-gasta-<campaña>`). El resto: nada.

## 4. Lo que se ve en el panel

En la ficha de cada oferta (Negocio → oferta): «Campañas en Meta» (campaña → conjunto → anuncio, con ROAS con AOV y la última decisión de la escala) y «Línea de tiempo del presupuesto» (cada suba, bajada, pausa y decisión, con quién la hizo y por qué).

## 5. Campañas que aparecen o se apagan (dueño, 16-nov: «que sea dinámico… cuando se lanza una campaña nueva, que el sistema la detecte y entienda dónde agregarla»)

- `nube_sync.py` (cada 5 min) compara las campañas de la cuenta con las del libro (`fotos_campanas.asignar_campanas`):
  - **Nueva**: si el nombre es «MERCADO | oferta | …» (como las nombra el sistema) y el mercado coincide con un test del libro, se agrega a `ficha.campanas` de ese test con su rol según el nombre (pocket, variaciones, renovación, escala, réplica; si no, principal u «otra»), estado, presupuesto y `detectada`. Desde esa vuelta entra en la escala, en las fotos, en los anuncios y en el panel, y su arranque aparece en la línea de tiempo.
  - **Mismo nombre en otro mercado**: no se mezcla (es otra oferta o una réplica sin test); queda en `campanas_sin_oferta.json` si está activa, junto con las activas que no siguen la convención de nombres.
  - **Ya conocida**: se ponen al día el estado (con `apagada_desde` al apagarse; la nota que acompaña al estado no se pisa) y el presupuesto.
- **Para que una campaña nueva se asigne sola, su nombre tiene que empezar con «MERCADO | Nombre de la oferta |»**, como las que crea el sistema.
- Panel: las campañas apagadas no ocupan lugar; quedan en un grupo «N campañas apagadas (ocultas)» al final de la tabla, que se abre con un clic; en la línea de tiempo solo aparecen si tuvieron un cambio dentro de la ventana.

## 6. Día nuevo = ventana nueva (dueño, 16-nov)

- A las 00:00 del mercado **el presupuesto queda como terminó** (no se vuelve al inicial: con reseteo diario la escala se limita a lo que se sube en un día).
- Lo que se reinicia es la cuenta: desde la medianoche del mercado (zona de `control_previo.ZONA`) la escala mira solo lo de hoy. Si la campaña arranca gastando sin vender, la bajada −30 % salta con la muestra de siempre (≥ 3 h y ≥ 1,5 tickets, o 2 compras, ROAS con AOV < 1,5): es el «tirón» del dueño. El primer surfeo del día también necesita 3 h y 2 compras de hoy.
- Lo que hacen Bilbao, Trimb y Bonardo, y por qué se eligió esto: `docs/investigacion/2026-11-16-escala-dia-siguiente/LEEME.md`.
- `reglas.json` → `escala.por_campana.ventana_desde_medianoche_mercado`.
