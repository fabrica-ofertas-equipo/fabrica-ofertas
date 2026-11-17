# Barrido por forma de funnel

Movido aquí el 2026-11-13 desde `modelar-y-lanzar-oferta/references/01-elegir-oferta-y-mercado.md` (división de skills pedida por el dueño). Los scripts siguen en `.claude/skills/modelar-y-lanzar-oferta/scripts/` (caja de herramientas compartida): las rutas de abajo son relativas a esa carpeta.

## Barrido por forma de funnel

**Desde el 2026-11-13 el camino principal para encontrar ofertas es el radar (`05-radar.md`).** Este barrido queda como complemento: reposición a mano cuando el radar no alcanza y `clasificar` para encuadrar una landing.

El barrido por tema (`scripts/modelado/barrido/`) trae sobre todo páginas de venta simples. En la segunda corrida ningún quiz ni VSL de ese barrido pasaba el piso y se eligió un funnel simple; el dueño no lo dio por bueno como método. Desde el 2026-11-11 existe el barrido por forma de funnel: se busca por cómo es el funnel y no por qué vende. Probado una vez (resultado en `empresa/barrido/candidatos/2026-11-11-por-forma.md`).

Herramientas: `scripts/barrido_por_forma.py` (términos, clasificador, encuadre e informe), `scripts/terminos_forma_funnel.json` (frases en seis idiomas y señales de destino) y `taxonomia-funnels.md`.

### Paso 1 · Buscar

El conector `ads_library_search` no devuelve ni el texto del anuncio ni el URL de destino, y trae los más recientes primero: sirve para contar, no para encontrar funnels. La búsqueda se hace en la web de la Biblioteca con el navegador integrado, siempre con `country=ALL`, solo anuncios activos y con fecha tope de inicio de hace 10 días (así todo lo que aparece ya cumple la antigüedad mínima). `python3 $B terminos` imprime los URL listos. Solo lectura, sin iniciar sesión, pocas páginas y despacio; ante un bloqueo se para.

Tres maneras de buscar, de más a menos rendidora en la primera corrida:

| Manera | Ejemplo | Qué trajo |
|---|---|---|
| **Dominio de un constructor de quiz** como frase exacta | `"inlead.digital"` | Solo funnels de quiz, la mayoría de productos digitales baratos (Brasil y Latinoamérica). ~3.000 anuncios activos. La mejor fuente |
| **Frase de forma + palabra de producto digital** (búsqueda por palabras) | `quiz ebook`, `quiz PDF`, `quiz "acesso imediato"`, `quiz workbook` | Menos volumen, más limpio |
| **Frase de forma sola** (frase exacta) en cada idioma | «haz el test», «take the free quiz», «faça o quiz», «fai il test», «mach den Test», «faites le test», «mira el video hasta el final» | Mucho ruido: aplicaciones por suscripción, clínicas, seguros, tiendas. Sirve para descubrir operadores grandes que pautan en varios idiomas |

En cada página de resultados, leer por tarjeta: página, destino, «en circulación desde» y cuántos anuncios usan ese contenido; agrupar por página y destino (fragmento en `fragmentos-navegador.md` §6).

### Paso 2 · Medir la oferta, no la página

Buscar el **dominio de destino** como frase exacta, sin fecha tope y con `country=ALL`: el total que devuelve son los anuncios activos de ESA oferta en todas las páginas y países (un mismo operador suele repartirla en 4 a 8 páginas). La antigüedad es la de la tarjeta más vieja que se llegue a ver; como la Biblioteca ordena por impresiones, es un mínimo («al menos N días»). Las rutas de destino (`/es/`, `/de/`, `/br/`) dicen en qué idiomas pauta; los países exactos se cuentan con el conector (`page_ids` + `countries`, `limit: 1`).

Si el dominio lleva subdominio y la búsqueda da cero, repetir con el subdominio completo (`quiz.ejemplo.com`).

### Paso 3 · Clasificar

`python3 $B clasificar <URL>` para cada destino. Lo que salga con confianza baja (casi todo quiz, porque se dibuja con JavaScript) se recorre a mano en el navegador hasta ver qué hay después de las preguntas: ahí aparecen los híbridos. No se siguen pantallas donde continuar implica aceptar términos, ni se escriben datos personales; lo que quede detrás se anota como no observado. Mirar siempre en el pie si hay «política de suscripción».

Encuadrar cada uno en la taxonomía (`encuadrar --registrar` para lo visto a mano).

**Antes de dar por bueno el tipo, agrupar todos los anuncios del referente por destino** (lector de tarjetas, `fragmentos-navegador.md` §6). En la cuarta corrida el barrido trajo la página de un paquete (`tsl`), pero la mitad de los 205 anuncios iban a UN ebook con advertorial y ficha de 3 niveles: ese es el funnel que se modela, y el producto estrella es el que más anuncios recibe.

### Paso 4 · Ordenar e informar

Escribir los candidatos (formato de `ordenar_candidatos.py`, con `landing`, `mas_antiguo`, `paises`, `confianza`, `verificado_a_mano`, `evidencia`, `no_observado`) y correr:

```
python3 $B informe candidatos.json --salida-json empresa/barrido/candidatos/<fecha>-por-forma.json --salida-md empresa/barrido/candidatos/<fecha>-por-forma.md --busqueda busqueda.json
```

El informe lista elegibles, fuera, tipos encontrados (cuáles existían y cuáles son nuevos) y cuánto se buscó.

### Reglas

- No elegir hasta tener al menos 3 candidatos complejos (complejidad ≥ 0.60) que pasen el piso y se puedan producir. Si no aparecen, decirle al dueño cuánto se buscó y con qué términos, y recién entonces tomar el mejor puntaje disponible.
- Si se termina eligiendo un funnel simple, el informe dice «nuestro barrido no encontró», no «no hay».
- Lo que enseñó la primera corrida: **los funnels de quiz con más volumen (cientos o más de mil anuncios) son casi todos aplicaciones por suscripción** o programas de marca personal con promesa de salud, que este recorrido no produce. Sirven para modelar la estructura del quiz, no la oferta. Los quiz que venden un producto digital de pago único existen, con menos volumen (decenas de anuncios), y se encuentran sobre todo por el dominio del constructor.
- La web de la Biblioteca responde 403 al primer documento en `www.facebook.com` y enseguida carga bien en `web.facebook.com`. Usar `web.facebook.com` directamente. (El freno de `empresa/captura/freno.json` del 2026-11-06 anota justo un «HTTP 403 (Document)»: puede ser este mismo falso positivo. Solo una persona lo borra.)

