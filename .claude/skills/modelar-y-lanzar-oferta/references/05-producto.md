# Fase 6 · Producto

Salida: el archivo que recibe el comprador, revisado pieza por pieza. Es la fase más larga y la que más créditos gasta; se arranca en cuanto está el desarme.

Lo de aquí tiene dos capas. El **método** vale para cualquier producto en PDF. El **productor** concreto (`ejemplo-mx/04-producto/scripts/`) hace hojas para colorear por números y solo se reutiliza si el producto nuevo es de ese tipo.

## 1. Qué se replica y qué es nuestro

Del referente se hereda la forma de la oferta: cuántas piezas, qué trae cada una, cuántos bonus y de qué tipo, formato de entrega. El contenido es nuestro de punta a punta: no se usa ni se rehace material del referente.

## 2. Catálogo

Antes de generar nada, la lista completa de piezas en `03-oferta/catalogo.md`, con criterio escrito:

- **Derechos.** Solo material propio o de dominio público. En México: obras de artistas fallecidos antes de 1952, reproducciones tomadas de Wikimedia Commons, y fuera los casos dudosos aunque fueran los más atractivos para el mercado. No es asesoría legal y se dice así.
- **Público.** Si el comprador es una familia con niños: sin desnudos, violencia ni alcohol. En México se sustituyeron tres obras por eso.
- **Sabor local.** Piezas que el mercado reconoce como suyas, salidas de la inmersión.
- **Formato del país.** Tamaño de hoja local, y pensar el costo de imprimir: si el comprador lo lleva a una papelería, que funcione en blanco y negro.

## 3. Datos y fuentes

Agentes en paralelo por bloques de unas 20 piezas. Cada uno entrega un JSON por bloque (`fichas-datos/bloque-*.json`) con: fuente de la imagen y su licencia, datos verificados con URL, y los textos de la pieza en la voz del mercado y para la edad del público. Límites de longitud por campo, para que la maqueta no se rompa.

Los servicios públicos limitan peticiones: `User-Agent` honesto, ritmo bajo, y anotar lo que no abrió.

## 4. Producir por rondas

Reglas del método, que salieron de cómo falló la primera noche:

- **Piloto primero.** Una sola pieza de principio a fin y enseñársela al dueño antes de lanzar cien.
- **Lo determinista, por código.** Lo que se puede calcular (numeración, leyenda, maqueta, índice) no se le pide a un generador de imágenes: así coincide siempre.
- **Cada ronda en su carpeta** (`planas-rN/`, `numeradas-rN/`). Nunca se borra una ronda; para cada pieza se usa la mejor que exista.
- **Tope de créditos por ronda** (`--tope`) y registro de cada envío. Si una tanda sale mal a los pocos minutos, se detiene y se corrige el prompt, no se deja terminar.
- **Modelo barato para la tanda, caro para los rehechos.** En México, 12 créditos por hoja el modelo base y 18 el superior.
- **Reintentar los fallos de servicio** (timeouts, errores 500) en una tanda aparte con menos hilos.

## 5. Revisión independiente

Quien genera no es quien aprueba. Tras cada ronda grande:

1. Armar láminas de comparación por pieza: original y cada candidato lado a lado (`candidatos.py laminas`).
2. Agentes revisores en lotes de 20-25, sin ver el razonamiento del generador, con criterios cerrados y veredicto `PASA / PASA_MENOR / REHACER`, más una instrucción corta de corrección para cada rehecho.
3. La ronda siguiente rehace solo lo marcado, con la instrucción de su revisor añadida al prompt.
4. Elegir el mejor candidato por pieza (`candidatos.py elegir seleccion.json`).

En México la primera revisión mandó rehacer 79 de 100. Sin ella el producto habría salido con caras sin rasgos, manchas negras y zonas imposibles de colorear. Criterios que se usaron: elementos inventados, pieza irreconocible, caras sin rasgos, manchas, demasiadas o muy pocas zonas, contenido no apto, texto colado, contornos perdidos.

Lo que no mejora con más rondas se resuelve cambiando el planteamiento: en México las obras con multitudes pasaron a «(detalle)» con un recorte central, y una pieza geométrica se dibujó por código.

Decir al final cuántas piezas quedaron en `PASA` y cuántas en `PASA_MENOR`, con la lista. No se entrega como perfecto lo que tiene defectos conocidos.

## 6. Armar el archivo

- HTML → PDF con Chrome sin pantalla (`armar_fichas.py`, `armar_kit.py`): portada, cómo usarlo, índice, piezas, bonus.
- **Peso.** Impultienda admite archivos grandes pero el comprador lo abre en el teléfono: en México el PDF pasó de 53 MB a 16.8 MB cuantizando las líneas a 1 bit con PyMuPDF.
- **Un PDF por bonus, además del archivo principal.** En la tienda cada bonus se carga como bono con su PDF y su portada vertical (`06-tienda-impultienda.md` §3.1). Meterlos solo dentro del archivo principal fue un error de las dos primeras corridas.
- Revisar el PDF final página por página en hojas de contacto: páginas en blanco, textos cortados, numeración.

## 7. Entorno

El `.venv` del repositorio no trae las librerías de imagen. Crear uno propio en `04-producto/.venv-fichas` con `numpy scipy pillow opencv-python-headless requests pymupdf`. Las llamadas a Kie usan el cliente `scripts/imagenes/ranuras_kie.py` con el `.venv` del repositorio; saldo con `ranuras_kie.py saldo`.

## 8. Productos de texto y maqueta (hojas de trabajo, guías, formatos)

Segunda corrida («Oferta B», 84 hojas y 4 guías): sin imágenes generadas y sin créditos.

1. Escribir primero una `ESPEC.md`: qué es el producto, áreas y códigos, la forma exacta de cada pieza en JSON, un catálogo cerrado de tipos de hoja con sus campos y límites de caracteres, reglas de contenido (originalidad, lo que queda fuera por seguridad, voz) e identidad visual.
2. Contenido: un agente por cada dos áreas escribe su JSON y lo valida contra los límites. Un agente aparte para los bonus.
3. Maqueta: un agente construye validador y generador HTML→PDF (una plantilla por tipo de hoja), lo prueba con datos al máximo y mira cada tipo en imagen.
4. Dos revisiones independientes en paralelo: contenido (seguridad, solidez, voz, supuestos, originalidad, repeticiones; devuelve cambios aplicables por ruta de campo) y visual (todas las páginas en imagen). Se aplican por programa y se regenera.
5. Si el referente tiene niveles, sacar un PDF por nivel y otro solo con los bonus.

Regla que salió de ahí: cada verbo de «escribe» o «anota» en una consigna necesita su renglón en la plantilla de ese tipo.

## Hecho cuando

- PDF final en `04-producto/entregables/`, con su peso y número de páginas anotados.
- `seleccion.json` con el candidato elegido por pieza y los veredictos de la última revisión.
- Lista de defectos conocidos dicha al dueño.
- Gasto en créditos dicho.
