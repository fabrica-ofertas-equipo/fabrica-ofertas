# Radar de ofertas: el super buscador siempre prendido

Pedido del dueño (2026-11-13): «quiero armar un SUPER BUSCADOR DE OFERTAS», buscando «al mismo tiempo en todos los mercados del mundo en sus idiomas y en inglés», siempre prendido, para dar con joyas. «A nivel resultados, olvidate del riesgo.»

## Qué cambia respecto del barrido por forma

| Antes (barrido por forma, 11-nov) | Ahora (radar) |
|---|---|
| Frases sobre la forma del funnel («haz el test») | **Señales de venta de producto digital**: dónde se cobra (Hotmart, Kiwify, Digistore24, ClickBank, Systeme.io…) y cómo se entrega («descarga inmediata», «pago único», «acceso de por vida») |
| 6 idiomas, todos los países juntos | **93 mercados** (57 hasta el 14-nov), cada uno con su país puesto, en su idioma y en inglés (46 idiomas) |
| Una corrida y a mano | **Cola de 711 búsquedas** que corre sola cada 4 horas, 24 horas; el mundo entero cada ~8 días y vuelve a empezar |
| Si se puede producir, al final | Se filtra temprano: primero lo que se vende como producto digital; la forma del funnel se clasifica después |
| Puntaje: complejidad, antigüedad, anuncios | Además **joya**: hueco de mercado (validada en pocos países) y aceleración |

Catálogo: `scripts/radar_terminos.json`. Motor: `scripts/radar.py`. Lector de tarjetas: `scripts/radar_lector.js`. Datos: `empresa/barrido/radar/`.

## El recorrido de una oferta en el radar

```
hallazgo → nuevo → a_medir → medida → a_verificar → verificada → exportada (al banco)
                                  ↘ descartada (bajo el piso, no producible)
```

- **a_medir:** ≥ 5 anuncios vistos y ≥ 10 días, **o** un anuncio activo hace ≥ 30 días (evergreen). En plataformas compartidas cada producto se ve con una tarjeta por búsqueda: el evergreen es la señal.
- **medida:** se cuenta el total de la oferta en todos los países. Dominio propio → el dominio como frase exacta. Plataforma compartida → el **código del producto** (`M107497977L`), probado el 13-nov. El número de `pagina_url` NO sirve para medir (no es el de la Biblioteca).
- **a_verificar:** ≥ 15 anuncios y ≥ 10 días (el piso del dueño).
- **verificada:** se abrió la landing en el navegador y se decidió si se puede producir (pago único, entregable como archivo, sin marca personal ni cara, sin promesa de salud o de ingresos garantizados, sin suscripción). Se anota el funnel (`barrido_por_forma.py clasificar`; los quiz se recorren a mano).
  - **«Sin cara» se comprueba en los anuncios, no solo en la landing (14-nov).** Antes de marcar `--producible si`, abrir la página del anunciante en la Biblioteca y mirar la hoja de contacto de 3 videos de tandas distintas, y el video de la landing. BossaColor pasó como «sin cara del vendedor» y sus 9 creativos y la VSL eran el creador a cámara con su propio metraje: se descubrió al desarmarla, ya elegida, y la vuelta de lanzamiento se quedó sin candidato.
  - Un curso cuyo producto es video o audio de una persona (adiestrador, profesor de idiomas) no es «entregable como archivo» aunque sea pago único: se marca `no` y se deja en la nota qué haría falta.
- **exportada:** pasa al banco con `radar.py exportar` + `banco_candidatos.py importar`, con su `hueco` para el puntaje de la elección.

## Cada vuelta (tarea «radar-ofertas», cada 4 horas)

`R=.claude/skills/buscar-ofertas/scripts/radar.py`

**Orden fijo: verificar → medir → buscar** (14-nov: el radar buscaba primero y se quedaba sin vuelta para lo demás; había 509 ofertas sin medir y 4 sin verificar mientras el lanzamiento esperaba candidatos). Lo encontrado sin medir no sirve. El dueño: «el sistema siempre tiene que tener preparadas ofertas… si no encontramos, sigue buscando».

0. `python3 $R estado`. Con bloqueo vigente de la Biblioteca no se mide ni se busca (un bloqueo no se esquiva: se espera), pero se verifica igual: verificar abre los destinos, no la Biblioteca. Después `python3 $R plan --json`: cuántas verificar, medir y buscar en esta vuelta (números en `ofertas/_funnels/reglas.json → radar`). Con el banco bajo la reserva (`lanzamiento.banco_objetivo_listos`, 3) el modo es **reposición** y se mide más; con ≥ 300 sin medir hay **atasco** y se busca menos.
1. **Verificar:** las primeras `verificar` de `a_verificar`. Abrir el destino, recorrerlo sin dar datos personales, y `python3 $R verificar <clave> --producible si|no --funnel <tipo> --producto "…" --tema <tema> --nota "…" --landing <url final>`. Antes de dar el tipo por bueno, mirar a qué destino van la mayoría de sus anuncios (`02-barrido-por-forma.md`, paso 3). Una app que se puede pasar a un pack de archivos o a PDF cuenta como producible (ReferenteG, Adesiva Pro). Exportar e importar enseguida (paso 4).
1b. **Ofertas hermanas (S05):** cuando una verificación da `--producible si`, abrir la página del anunciante en la Biblioteca (clic en su nombre en una tarjeta) y leer sus tarjetas con `radar_lector.js`: cada destino distinto que no esté en el radar entra con `python3 $R agregar <destino> --pagina "<página>" --origen hermana-de:<clave>`. Un operador que ya tiene una joya suele tener otras validadas.
2. **Medir:** las primeras `medir` de `a_medir` (mayor joya). Abrir `url_medir`, leer el total y la tarjeta más vieja, y `python3 $R medir <clave> --total N --dias D`. Si el código no da resultados, medir por la página del anunciante (`--page-id`). Lo que pase a `a_verificar` se verifica en la misma vuelta.
3. **Buscar:** `python3 $R cola siguiente --n <busquedas> --json` (como mucho 3 por país) con su URL. Para cada una:
   - abrir la URL en el navegador integrado (`web.facebook.com`);
   - una rueda real del ratón y 3-5 `window.scrollTo(0, document.body.scrollHeight)` con 2,5 s entre cada uno;
   - pegar `scripts/radar_lector.js` y guardar lo que devuelve en el scratchpad;
   - `python3 $R registrar <id> --archivo <json>`;
   - si la página pide iniciar sesión, muestra un desafío o responde con un error repetido: `python3 $R bloqueo --busqueda <id> --motivo "…"` y dejar de buscar. Un bloqueo no se esquiva: se espera.
4. **Pasar al banco:** si hay verificadas y producibles, `python3 $R exportar` y el `banco_candidatos.py importar` que imprime.
5. **Navegador rechazado:** si un sitio queda rechazado («declined») o no abre, la vuelta no se corta: se sigue con lo que no usa ese sitio y se avisa urgente con `avisos.py avisar permiso-navegador-<sitio>` para que el dueño lo permita siempre (el 14-nov la vuelta murió en silencio por esto).
6. **API de Europa:** si existe `META_AD_LIBRARY_TOKEN`, `python3 $R api --lote 20`. Sin token, se saltea sin avisar cada vez.

Mensaje final: una línea: búsquedas hechas, ofertas nuevas, medidas, verificadas, exportadas y la mejor joya del momento.

## La API oficial (ruta C) para la UE y el Reino Unido

- El cliente ya existía (`scripts/modelado/barrido/ruta_c.py`, con frenos, registro y el token protegido). El radar lo usa con `radar.py api`.
- Trae, por anuncio: texto, dominio del enlace, fecha de inicio y **alcance en la UE**. Sirve para 28 países y sus idiomas, en bloque y sin navegador.
- Falta el token del dueño: confirmar identidad en facebook.com/ID, crear una app en developers.facebook.com y generar un token de acceso. El dueño lo pega en `.env` como `META_AD_LIBRARY_TOKEN`; el agente nunca lo escribe ni lo lee en voz alta.
- Los topes de solicitudes están en `scripts/modelado/barrido/parametros_ruta_c.propuesta.yaml` (hipótesis hasta la primera corrida real).

## Cómo se mejora el radar

- Cada búsqueda guarda cuántas ofertas nuevas trajo; la cola prioriza las que más rinden y deja para después las que no traen nada.
- Una plataforma, constructor o frase nueva se agrega a `radar_terminos.json` y se corre `radar.py cola generar` (conserva las estadísticas).
- Lo que se aprende va al `CHANGELOG.md` de la skill.

## Latido y avisos (escenarios S39 y S40, 13-nov)

Al terminar cada vuelta, haya salido bien o no: `python3 .claude/skills/escalar-oferta/scripts/avisos.py latido radar-ofertas ok|error --detalle "…"`. Si imprime `AVISAR` (tercera falla seguida), notificación urgente al dueño. Todo aviso pasa antes por `avisos.py avisar <clave> --mensaje "…" [--urgente]` y solo se manda si imprime `ENVIAR`. Si PushNotification responde «not sent» (p. ej. «Remote Control inactive»), correr `python3 .claude/skills/escalar-oferta/scripts/avisos.py no-llego <clave> --motivo "…"`: el aviso vuelve a salir en la próxima vuelta y el panel lo muestra como no entregado.
