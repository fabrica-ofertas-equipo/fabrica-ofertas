# Fase 2 · Elegir el mercado (la fase 1 es de buscar-ofertas)


**Fase 1 (elegir la oferta) ahora es de la skill `buscar-ofertas`** (división del 2026-11-13): radar de ofertas cada 2 horas (camino principal para encontrar), banco de candidatos, seguimiento diario y elección con `ordenar_candidatos.py`; el barrido por forma de funnel queda como complemento. Esa skill entrega el referente elegido con su `page_id`, landing, anuncios medidos ese día y tipo de funnel; desde ahí sigue esta guía con la fase 2. Las secciones §1.1-§1.3, §1.5 y §1.6 que se citan en otros archivos están en:

- §1.1-§1.3 → `.claude/skills/buscar-ofertas/references/01-elegir-del-banco.md`
- §1.5 → `.claude/skills/buscar-ofertas/references/02-barrido-por-forma.md`
- §1.6 → `.claude/skills/buscar-ofertas/references/03-banco-seguimiento-e-iteraciones.md`

## Fase 2 · Elegir el mercado

### 2.1 Criterio del dueño

Un país distinto al del referente donde esa oferta no se esté pautando. Se lanza al país entero, nunca a una ciudad o región.

**Veto, no peso (2026-11-14).** Oferta D salió a México con el original pautando ahí (170 anuncios al elegir, 127 el 14-nov): el referente corría en los 57 países de la lista de entonces (y en los 62 de afuera que se miraron), el «hueco» daba 0 en todos, dejaba de distinguir y México ganó por cobro; la corrida anotó «ningún país es hueco limpio» y siguió igual. Desde `elegir_mercado.py` v5, **un país con anuncios activos del referente (en cualquier idioma) sale del orden**. Si no queda ninguno libre, el script sale con código 3 y **la oferta se descarta**: se marca `descartada` en el banco y se vuelve a `buscar-ofertas` por la siguiente. Nunca se elige «el menos malo» ni se pasa como decisión del dueño. Con código 4 faltan países por medir: se miden y se vuelve a ordenar.

**No tirar siempre al mismo mercado (regla del dueño, 2026-11-12; endurecida el 2026-11-13).** Las dos primeras ofertas salieron a México sin comparar países: «si lo hiciste no sabes por qué y predeterminado, tiremos en otro mercado». En la cuarta corrida México volvió a ganar, pero solo porque se le puso cobro 1 de memoria y al resto 0,5 sin medir; con cobro igual habría quedado detrás de Alemania y EE. UU. El dueño preguntó con qué criterio. Desde entonces el país se elige con `scripts/elegir_mercado.py` v3 (13-nov). **No se descarta ningún país por idioma** (pedido del dueño: «no nos limitemos en ese sentido»): Impultienda arma la tienda en ~50 idiomas y Gemini escribe y locuta en todos.

1. `python3 .claude/skills/modelar-y-lanzar-oferta/scripts/elegir_mercado.py plantilla > ofertas/_borrador-<slug>/modelado/mercados.json`: 93 países donde se puede cobrar (v6, 14-nov; los que quedan fuera a propósito y por qué, en `FUERA` y en `elegir_mercado.py cobro`), ordenados por tamaño, cobro y poder de compra. Medir de arriba hacia abajo, primero 12-15; ampliar si el ganador sale frágil.
2. Medir por país (web de la Biblioteca con `country=XX`, o el conector):
   - `referente` (activos que llegan, en cualquier idioma). Lo más barato es medirlo en los 93 de una vez con `buscar-ofertas/scripts/paises_referente.py` (por mitades, ~10-20 consultas) y pasarlo con `--medicion`; los países con el referente quedan vetados y solo hace falta medir la competencia de los libres. Si se puede, `referente_inactivos` (si pautó ahí y se fue, el hueco vale menos);
   - `competencia` con **la misma frase del producto traducida** en cada país, anotada en `consulta_competencia`;
   - `medido: true`.
3. **Cobro**: no se escribe a mano. Sale de la tabla del script (`elegir_mercado.py cobro`; la columna «con Stripe» dice cuánto sube cada país con Stripe. Stripe está disponible (cuenta de EE. UU. del dueño): el orden ya lo cuenta, y si el ganador lo necesita el script dice «REQUIERE STRIPE» y se conecta solo en las tiendas de esa oferta, `06-tienda-impultienda.md` §2b; `--sin-stripe` da el orden solo con Impul Pay): «medido» = el medio está en Impul Pay (leído el 13-nov); «hábito» = juicio sobre cómo paga la gente ahí. Si gana un país con cobro «hábito», verificarlo en la vista previa del checkout (`preview_country=XX`, bajando hasta debajo de la tarjeta y con captura: los medios están dentro del cuadro de Whop y el texto de la página no los ve).
4. `... elegir_mercado.py ordenar modelado/mercados.json --inicio AAAA-MM-DD [--medicion m.json] > modelado/mercados.md`. Primero veta los países del referente (código 3 = descartar la oferta; 4 = medir lo que falta). Entre los libres, el puntaje suma hueco, tamaño, competencia, cobro y poder de compra, y ajusta:
   - repetir país: ×0,6 por cada vez en las últimas 4 ofertas, ×0,8 si ese país ya dio un test rentable (`ofertas/_funnels/libro-de-tests.json`);
   - repetir idioma: ×0,9 por cada vez de más.
   Al lado imprime el **CPA observado** por país en nuestros tests, el «r» económico de `scripts/mercados`, la **temporada** (Buen Fin, Black Friday, 11.11, Navidad) y la **sensibilidad** (quién gana sin cobro, sin castigo y sin competencia). Si las últimas 3 ofertas fueron a países repetidos, propone **el mejor país nunca probado** como exploración aunque no gane.
5. Decirle al dueño la tabla, por qué gana el primero, **qué supuesto lo sostiene**, si es frágil o empate, el aviso de temporada y la propuesta de exploración si sale. Anotar `pais_destino` e `idioma` en `ofertas/historial-modelado.json` al lanzar.
6. Sesgo a declarar: producir en español es más rápido. Si el apuro empuja a un país de habla hispana, decirlo en voz alta.
7. El precio del producto principal no depende del país: es la regla 19/27, máx(19 USD, precio del referente) (`06-tienda-impultienda.md` §3), con un precio redondo cercano en la moneda local. La columna «poder» solo informa si ese precio es compra de impulso ahí. (Obsoleto: «en países de poder bajo, el peldaño más bajo de la escalera»; el ticket de 17 ya no existe.)

Tercera corrida: el referente pautaba en español en todo el mundo y en Brasil 0 → Brasil, portugués (0.755 contra 0.439 del segundo). Cuarta corrida reprocesada con v3: México habría quedado último de los medidos (0,318, usado 2 de las últimas 3, en pleno Buen Fin) e Italia (0,679) y Alemania (0,660) arriba, en empate frágil.

### 2.1b Países donde Meta exige anunciante y pagador verificados (2026-11-14)

Singapur, Taiwán, Tailandia, Malasia, Australia e India: Meta no deja crear el conjunto sin la declaración regional (`SINGAPORE_UNIVERSAL`, etc.) con un anunciante y un pagador **verificados** (ayuda de Meta «About advertiser and payer transparency for ads»). La verificación es del dueño (documento o empresa, hasta 2 días hábiles) y el conector no tiene el campo. Oferta J quedó armada para Singapur por esto. Antes de elegir uno de estos países: comprobar que el portfolio ya tiene una entidad verificada (Business → Configuración → Autorizaciones y verificaciones); si no, decirlo al elegir y tomar el siguiente país. La Unión Europea solo pide el nombre (DSA), sin verificación.

### 2.2 Comprobaciones por cada país candidato

Candidatos: los que deja arriba `elegir_mercado.py` (cualquier idioma: no se limita a los países donde ya producimos). Para cada uno:

| Pregunta | Cómo se comprueba | Qué se busca |
|---|---|---|
| ¿El referente pauta ahí? | `ads_library_search` con `page_ids: [<page_id>]`, `countries: ["XX"]`, `ad_active_status: "ACTIVE"` | `estimated_total_count: 0` |
| ¿Alguien más vende lo mismo ahí? | `ads_library_search` con `search_terms` (dos o tres frases del producto en el idioma local), `countries: ["XX"]`, `ACTIVE`, `limit: 50` | Pocos o ningún anunciante con la misma idea. Anotar cuántos, a qué precio y a qué canal mandan (página, WhatsApp) |
| ¿El operador ya exporta? | Campo `exportador` del barrido; buscar otras páginas con la misma landing | Si ya opera en varios países, es más probable que llegue pronto a este |
| ¿Se puede cobrar? | En Impultienda, qué medios locales ofrece Impul Pay para ese país y en qué moneda | Tarjeta más los medios que el comprador local espera |
| ¿El idioma y la cultura dejan adaptar el producto? | Juicio; se confirma en la inmersión | Hay referentes culturales locales que sumar |
| ¿Cuánto cuesta anunciar ahí? | `scripts/mercados/rank.py --escenario corregido` si el país está entre los 15 puntuados | Orden económico y sus supuestos |

El conector devuelve como máximo 50 anuncios, los más recientes primero, sin texto completo ni gasto: sirve para contar y ver quién anuncia, no para medir tamaño de mercado. Decir ese límite al informar.

### 2.3 Lo que hay que resolver del país antes de seguir

Anotar en `estado.md`:
- Código de país, idioma y variante (p. ej. `es-MX`): el idioma de la tienda de Impultienda se elige al crearla y no se puede cambiar.
- Moneda y cómo se escribe el precio (en México «$» se lee como pesos: se escribe `$359 MXN`).
- Huso horario de referencia para programar el inicio («hora del centro de México»).
- Precio: regla 19/27 en USD (máx(19, precio del referente)) y su equivalente local redondo, fijado a mano (Brasil R$ 99, México MX$ 359).

### 2.4 Qué se le dice al dueño

Una tabla corta con los países mirados, el recuento de cada comprobación y la recomendación, y se sigue con el recomendado sin esperar respuesta. Si el referente pauta en todos los países, no hay recomendación: se descarta la oferta y se dice así («el original corre en los N países donde podemos lanzar»).

En México la única evidencia de hueco salió de rebote en la inmersión: ningún «colorear por números con obras de arte» local, y vendedores pequeños cerrando por WhatsApp a $45-$99 pesos. Esa comprobación ahora va aquí, antes de producir nada.

## Hecho cuando

- `estado.md` tiene: referente, `page_id`, landing, anuncios activos hoy con su fecha de inicio, país elegido con el recuento de cada comprobación, idioma, moneda, precio y huso.


