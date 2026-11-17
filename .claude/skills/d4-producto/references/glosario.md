# Glosario de la skill D4

| Término | Significado |
|---|---|
| **EU / MU** | Entregable único / mecanismo único (backbone 5.11): un producto autocontenido y un «cómo» nombrable que se ve y se opera en él |
| **Matriz de promesas** | `producto.json#matriz_promesas`: cada promesa/bonus/bump → entregable → prueba ejecutable; y cada ítem → alguna promesa |
| **Maker / QA** | Dos procesos separados (`d4-maker`, `d4-qa`); el QA no ve el razonamiento del Maker ni `autoprueba.json` antes del cold run |
| **L1 / L2 / L3** | Checks deterministas / rúbrica de criterio 0-5 con evidencia citada / simulaciones (novato, comprador escéptico, revisor de políticas, lector vulnerable, auditor de vigencia) |
| **QA-A** | Checkpoint del QA **antes de gastar créditos** (guía de estilo + 3 piloto); no cuenta como ronda. Hoy dormido en D4 (sin Higgsfield); lo usa D6 |
| **Cold run** | Un novato (humano o agente de contexto limpio) sigue el producto solo con el producto y un caso |
| **Primer resultado** | Primer punto del método en que el comprador obtiene algo útil; su tiempo es `eu.tiempo_primer_resultado` |
| **T1-T4** | Niveles de fuente (oficial · profesional atribuida · editor con proceso · nunca) |
| **Snapshot** | Texto crudo de una fuente guardado con `sha256` en `respaldo/fuentes/` |
| **RHS** | Revisión humana de seguridad (30-60 min); no acredita exactitud clínica |
| **Ejes P, C, E, N** | Promesa, Contenido, Encuadre, Negocio (nota 25); D4 re-verifica **C** y solo puede subir el nivel |
| **Rojo / amarillo-a / amarillo-b / verde** | Niveles de riesgo del candidato; rojo no se produce; B exige H, ayuda verificada y revisión profesional o texto fiel |
| **`no_verificado_por_agente`** | Lo que un agente no puede comprobar (GUI, cuenta, pago, reloj humano): pasa al checklist del dueño |
| **Casos dorados** | Entradas con salida esperada de una calculadora, contra una implementación de referencia independiente |
| **Unidad / ficha** | Un elemento de una biblioteca de N (receta, patrón, tarjeta, prompt) como línea de JSONL |
| **Preproducción** | `preprod/<oferta_id>/` en R2 privado; D4 solo sube ahí |
| **Ruta A/B/C** | Alternativas de render PDF (Chrome sin pantalla / WeasyPrint / plantilla de hoja de cálculo o imprimir a PDF) y del novato cronometrado (humano / agentes / fórmula) |
| **`[PENDIENTE]`** | Falta construir o instalar algo; solo se lista en `dependencias.md` |
