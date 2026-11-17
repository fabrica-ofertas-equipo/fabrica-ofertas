# Glosario de términos de D6

| Término | Significa |
|---|---|
| **Oferta (`oferta_id`)** | Un concepto en un idioma y un clúster de mercados, con su marca, landing, dataset, campaña y P&L (`OF-AAAAMM-NN`). Una **familia** (`familia_id`) agrupa las ofertas hermanas de un mismo concepto |
| **Concepto** | Una hipótesis de ángulo (`concepto_id`, `angulo_id` de `oferta.angulos[]`, `nivel_conciencia`, `hipotesis`) con 1–2 hooks |
| **Ángulo** | Punto de vista que hace sentir «esto es para mí» en 3 s, sin atribuir condición al espectador |
| **Nivel de conciencia (N1–N5)** | N1 inconsciente del problema · N2 consciente del problema · N3 consciente de soluciones · N4 consciente del producto · N5 listo para comprar (no existe en el test) |
| **Hook** | Los primeros 0–3 s: acción visual + línea hablada + texto en pantalla; `hook_id` (`h1`, `h2`…) y `hook_tipo` del vocabulario cerrado |
| **Puente (on-ramp)** | Segundos ~3–15: continúa la premisa del hook; se reescribe al cambiar el hook |
| **Cuerpo** | Desarrollo + prueba + CTA, que no cambia al variar solo el hook |
| **`ad_name`** | `{concepto_id}_{img\|vid\|car}_{hook_id}_v{n}` (ASCII; es lo que lleva `utm_content`) |
| **Ficha de formato** | Estructura, ritmo, tipo de hook, ángulo y duración extraídos de una referencia; el activo se descarta |
| **`claim_id`** | Identificador de una afirmación permitida en `oferta.promesa.claims_permitidos` con su evidencia |
| **P, C, E, N** | Ejes de riesgo: Promesa, Contenido, Encuadre y categoría de Negocio; nivel = el máximo; **riesgo por pieza** = el de cada anuncio |
| **P2s** | Cifra reproducible del propio entregable con rótulo «ilustrativo» en el mismo cuadro o audio (amarillo) |
| **P2n** | Resultado futuro atribuido al lector, con o sin cifra o plazo (rojo) |
| **E2** | Atributo del espectador afirmado, implicado o preguntado (rojo) |
| **RHS** | Revisión humana de seguridad (una persona recorre la lista L3 de 22f §4.7; 30–60 min) |
| **QA-A / QA-B** | Dos pasadas de un mismo rol: A revisa el texto antes de gastar créditos (no cuenta ronda); B revisa las piezas (ronda 1 y 2) |
| **Hash de textos** | Hash de `matriz.json` + `copies.json` + `guiones/`; se congela en QA-A y B lo verifica |
| **Veto y sello de X1** | X1 bloquea y sella por hash el paquete; D7 lo verifica antes de armar y activar |
| **Ruta A / Ruta B** | A: HTML→PNG, 0 créditos, estáticos. B: Higgsfield, créditos, video (y fondos sin texto) |
| **Piloto** | 1 clip por concepto con video, aprobado antes del lote |
| **Semiasistido** | El Maker con Higgsfield corre en la sesión Code del dueño, con `ask` por generación; el runner desatendido no carga conectores |
| **Créditos** | Unidad de gasto de Higgsfield; topes `creditos_max_pieza`/`creditos_max_oferta` en `limites.yaml` |
| **C2PA** | Metadatos de procedencia de contenido; nunca se eliminan a propósito |
| **`meta_enhancements`** | Mejoras automáticas de Meta (texto y creatividad); ambas `false` |
| **Reserva** | Conceptos con guion y copy aprobados y sin assets, listos para D8 |
| **Pedido (`pedido_id`)** | Solicitud de D8/D9 (`motivo`: fatiga, ganador, escala, mercado, rechazo) con `variable_a_variar` y `cantidad` |
| **Escalera de variación** | Una variable por vez: hooks → ángulo vecino → formato → presentador → duración y CTA |
| **`[SUPUESTO]` · `[VERIFICAR]` · `[PENDIENTE]` · `[DUEÑO]` · `[HIPÓTESIS]` · `[CREADORES, A/B/C]`** | Etiquetas del backbone §5.8; ver `preguntas-abiertas.md` y `dependencias.md` |
| **Tanda** | Banco diario de 5-10 estáticos candidatos por idioma (Ruta A, 0 créditos) que termina en «por aprobar» (`modo-tanda.md`) |
| **Relevo** | El mismo anuncio con otra apertura cuando el original se cansa (`formatos-que-miden-bien.md` §2) |
| **Ganador traducido** | Un ganador propio llevado a otro idioma con traducción fiel, 5 capas de QA lingüístico y X1 por `locale` (hipótesis, no prior) |
| **`qc6`** | Control de calidad de 6 puntos de código: audio · idioma · texto · caras y manos · material ajeno · precios y promesas; estados `ok` · `revisar` · `falla` (`control-de-calidad-6-puntos.md`) |
| **Gancho (biblioteca)** | Primera línea de un anuncio guardada en `datos/ganchos.jsonl` con su fuente; sirve para no repetirse ni copiar (`biblioteca-ganchos.md`) |
| **Idea · forma · expresión (J13)** | La idea se hereda, la forma se transforma, la expresión (textos, nombres, imágenes) no se toca; ante la duda, se cambia (`inmersion-y-derechos.md`) |
| **Dossier de voz del cliente (J12)** | Resultado de la inmersión del mercado: jerga, quejas, deseos, creencias, objeciones y tono de un país |
| **Productor de formato** | Skill o script que fabrica la pieza de una fila de la matriz (`productores-de-formato.md`, `contrato-comun-de-formatos.md`) |
