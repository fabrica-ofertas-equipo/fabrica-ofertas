# Banco de candidatos, seguimiento e iteraciones

Movido aquí el 2026-11-13 desde `modelar-y-lanzar-oferta/references/01-elegir-oferta-y-mercado.md` (división de skills pedida por el dueño). Los scripts siguen en `.claude/skills/modelar-y-lanzar-oferta/scripts/` (caja de herramientas compartida): las rutas de abajo son relativas a esa carpeta.

## Banco de candidatos, seguimiento e iteraciones

Pedido del dueño (2026-11-12): que no dependa de «el último barrido», que se mida cada día si las ofertas encontradas están escalando («hay más anuncios que ayer y anteriormente») y que, de las que escalan, se comparen tandas de anuncios para ver si están iterando un ángulo o formato, «como posible ad winner».

Todo con `scripts/banco_candidatos.py` (`K` abajo). Los datos viven en `empresa/barrido/banco/`: `ofertas.json` (estado de cada oferta: disponible, usada, descartada), `mediciones.jsonl` (una línea por oferta y día; solo se añade) y `creativos/<oferta>/<fecha>.json` (foto de sus anuncios).

### Banco: ¿alcanza o hay que barrer?

```
python3 $K importar empresa/barrido/candidatos/<corrida>-por-forma.json   # tras cada barrido; marca lo ya lanzado según el historial
python3 $K estado
python3 $K marcar <clave> --verificado            # tras recorrer el funnel a mano; también --estado usada|descartada, --producible si|no
```

`estado` separa: listos (complejos, verificados a mano, producibles y sobre el piso), complejos que falta verificar, y complejos bajo el piso. Con menos de 3 listos o un barrido de más de 7 días dice «HAY QUE BARRER». Antes de elegir, los listos se vuelven a medir ese día. Los umbrales (3, 7 días) son propuesta del asistente y están al principio del script.

### Seguimiento diario: ¿cuáles escalan?

1. `python3 $K seguimiento` imprime una búsqueda por oferta (su dominio de destino como frase exacta, todos los países, sin fecha tope).
2. Abrir cada una en la web de la Biblioteca y anotar el total (`fragmentos-navegador.md` §8 lo devuelve en una línea). Las ofertas alojadas en un constructor compartido (`inlead.digital`) no se pueden medir por dominio: se sigue el total de su página con el conector (`page_ids`, `limit: 1`), que incluye sus otras ofertas.
3. `python3 $K medir --archivo MEDICIONES.json` y `python3 $K tendencia`.

Cómo se lee `tendencia`: sube o baja si el cambio es de al menos 3 anuncios y 10 % (la Biblioteca redondea los totales grandes). **«ESCALANDO» exige tres días** medidos con el mismo método: más que ayer y más que las mediciones anteriores. Con dos días solo dice «sube (falta un tercer día)». Nunca se comparan cifras de métodos distintos (una muestra contra un total): quedan «sin base».

Son unas 20 búsquedas livianas, cinco minutos. Conviene hacerlo a la misma hora, y siempre el día en que se va a elegir.

### Iteraciones: ¿sobre qué video están sacando variantes?

**Se comparan los videos, no los textos.** Corrección del dueño (2026-11-12): «tiene que comparar los creativos en video, no los copys; los copys muchas veces van a ser iguales». En la primera prueba, 25 videos distintos de una oferta llevaban exactamente el mismo texto.

Para las que suben (y para el referente de una oferta nuestra en test):

1. Abrir en la Biblioteca la búsqueda por dominio de la oferta (o la página del anunciante) y leer las tarjetas (`fragmentos-navegador.md` §8) → `python3 $K creativos <clave> --archivo TARJETAS.json`. Da los días activo y cuántos anuncios repiten cada creativo.
2. En la misma pestaña, pegar `scripts/biblioteca_videos.js` y seguir su cabecera (`fragmentos-navegador.md` §9): saca huellas de fotogramas de cada video (unos 30 s para 40 videos), los compara y devuelve las familias → `python3 $K videos <clave> --archivo VIDEOS.json`.
3. Ver una hoja de contacto por familia (`__hoja`) y escribir en `VIDEOS.json` el formato en palabras (`formatos`, `formato_por_familia`, `lectura`).
4. `python3 $K iteraciones <clave>`.

Qué devuelve `iteraciones`:

- **Tandas de lanzamiento** que siguen vivas, con su ritmo y cuánto hace de la última.
- **Familias por video**, cada una con la relación entre sus miembros y una señal:
  - *Iterando*: variantes del mismo video lanzadas en tandas distintas. La relación más valiosa es **«mismo cuerpo, arranque distinto»**: encontraron un cuerpo que vende y le siguen probando ganchos. Es el candidato a ganador.
  - *Variantes lanzadas juntas*: prueba de arranques o de cortes (versión corta y larga) el mismo día.
  - *Repetido tal cual*: el mismo archivo de video en varios anuncios. Si además es viejo, lo están escalando.
  - *Único*: sin variantes ni copias; se listan los más viejos que siguen activos.
- El formato de cada familia en palabras, si se anotó tras ver la hoja de contacto.
- Por texto, solo como dato secundario (`--textos`).

Relaciones que distingue: idéntico (misma duración y mismos fotogramas), el mismo video con otro corte, mismo arranque con cuerpo distinto, mismo cuerpo con arranque distinto, mismo material con otro montaje.

Lo que NO hace: oír el audio. Dos videos de la misma persona en el mismo fondo con guiones distintos pueden salir parecidos, y un mismo guion grabado dos veces no se detecta. Para el plano por plano y lo que se dice, sigue haciendo falta ver enteros los videos de la muestra (`02-desarme-del-referente.md` §2), pero ahora la muestra se elige con criterio: un video por familia, empezando por las que iteran.

Primera corrida: `empresa/barrido/banco/seguimiento-2026-11-12.md`.

