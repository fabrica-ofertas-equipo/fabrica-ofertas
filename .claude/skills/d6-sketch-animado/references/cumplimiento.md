# Cumplimiento: el sketch animado contra las reglas de D6 y X1

Cada regla de `d6-creativos/SKILL.md` §1 aplica completa. Esta tabla dice cómo se cumple en este formato y qué decide X1.

| Regla D6 | Riesgo en este formato | Cómo se cumple |
|---|---|---|
| 1 Inventar claims, cifras, testimonios | Que un personaje «cuente» lo que logró | La revelación solo dice lo que el producto ES; cada línea con hecho lleva `claims: [id]` de `claims_permitidos` |
| 2 Claims prohibidos | Que una objeción se responda con un sí («¿consigue trabajo?») | Se responde con lo que es el producto; QA busca cada `claims_prohibidos` y `claims_a_evitar` también parafraseados |
| 3 Ingresos, plazos de resultado | El detonante del formato original es plata (pagos, auto nuevo) | **Prohibido**: el detonante es un comportamiento (`formato.md` §4) |
| 4 Atributo del espectador | Que las preguntas apunten al que mira | Las objeciones se dicen **entre personajes** y se refieren al personaje, nunca a «vos/tú» que mira |
| 5 Antes/después, cuerpos, menores | Animaciones de transformación | Sin antes/después; sin menores en cuadro; sin cuerpos en foco |
| 6 Avatar/voz IA como cliente o con primera persona de experiencia | El protagonista es un personaje IA que usa el producto | **[DECIDE X1]** Se trata como **dramatización ficticia rotulada** («Ficción animada · generada con IA»): el protagonista describe el producto en tercera persona («Una guía con…»), no dice «me funcionó» ni da un resultado. Si X1 lo rechaza, el formato no se usa en esa oferta |
| 7 Copiar anuncios ajenos | Copiar el reel de referencia | Se toma la **ficha de formato** (estructura, ritmo, edición); guion, personajes, escenario y estilo son propios |
| 8 Clonar voces o rostros; música descargada | Voz «clonada» y caras parecidas a personas reales | Voces **preset** de Gemini por locale; personajes genéricos; música y efectos **generados** (Suno vía Kie, ElevenLabs) con licencia registrada |
| 9–14 Nivel, topes, Meta, QA propio, frases rechazadas, enhancements | — | Igual que D6; esta skill solo entrega el mp4 y las filas para el paquete |

**Divulgación de IA:** `politica_divulgacion_ia` decide. Con `declarar_siempre` o `declarar_si_corresponde`, la etiqueta va siempre (son personajes que parecen reales en movimiento). La etiqueta se dibuja dentro del video y no se quita C2PA.

**Gate humano:** primera pieza de este formato en cada oferta = revisión del dueño y de X1 antes de `listo_para_d7`.
