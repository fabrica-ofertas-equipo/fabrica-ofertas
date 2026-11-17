# Guía de estilo de imágenes — {oferta_id} · {locale}

> OBLIGATORIA antes de generar (§4.1 de la spec): se aprueba con QA-A previo al gasto, con 3 unidades piloto. Las imágenes de IA nunca son «foto real» de un resultado.

| Campo | Decisión |
|---|---|
| Marca visual | paleta {hex}, tipografías OFL {nombres, con `OFL.txt` verificado} |
| Aspecto | {ilustración plana / acuarela / fotografía de objeto sin personas…}; ratio {1:1, 3:4…} |
| Luz y fondo | {luz suave frontal, fondo liso…} |
| Semilla / modelo / plan | {modelo}, semilla {n} o `job_id` de la referencia; plan y términos de licencia: {…} |
| Prohibido | artistas, marcas, personajes o patrones ajenos; menores; personas con bata o uniforme profesional; texto dentro de la imagen; «antes/después»; resultados |
| Rótulo | «Imagen generada con IA» en el colofón; C2PA preservado |
| Plantilla de prompt | `Objeto: {…}. Estilo: {…}. Luz: {…}. Fondo: {…}. Sin texto, sin personas, sin logos.` |
| Verificación por imagen | visión sobre el 100 % (texto basura, proporciones imposibles, objeto que no corresponde al paso, estilo fuera de guía) + muestreo humano `producto.biblioteca_muestra_qa_pct` [propuesto]; un defecto → barrido de la clase |
| Presupuesto | cotización por pieza SIN generar (`get_cost`) en `cotizacion_creditos.json`; `cotizar_creditos.py` AUTORIZA o DENIEGA; piloto: guía + 3 unidades |
