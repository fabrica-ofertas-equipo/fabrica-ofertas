# Formato «sketch animado»: estructura y edición medidas

Fuente: reel de referencia analizado plano a plano el 2026-11-06 (64 s, 43 planos, separación de pistas con Demucs, cámara medida con OpenCV y voces con Whisper) y el piloto «La notificación». Se copia el **formato**, no la obra: ni personajes, ni nombres, ni estilo de un estudio, ni líneas (D6 regla 7).

## 1. Estructura (beats)

| Tiempo | Beat | Qué pasa | Función |
|---|---|---|---|
| 0–5 s | **Gancho in medias res** | El protagonista entra a una escena tensa; nadie explica | retención: hay que quedarse para entender |
| 5–12 s | **Detonante** | Alguien vio algo raro (un comportamiento, no un resultado) | plantea la pregunta |
| 12–30 s | **Interrogatorio** | Ráfaga de hipótesis equivocadas = **objeciones** de la oferta, cada una con su «No.» seco | descarta objeciones sin defenderse |
| 30–33 s | **Silencio y revelación visual** | Se corta la música, aparece el producto (laptop, libro, cuaderno) y todos se inclinan | cambio de ritmo |
| 33–45 s | **Revelación** | Qué ES el producto, en 3 frases secas con `[claim]` | la oferta |
| 45–52 s | **Remate** | Giro cómico sobre el personaje cómico, en silencio | se comparte y se vuelve a ver |
| 52–57 s | **Cierre** | Producto + claim + garantía (o «Comenta PALABRA» si D7 lo soporta) | conversión |

Historia de 45–57 s; ~40–45 planos por minuto; **un plano por línea**; las réplicas de una palabra («No.») duran 0,4–0,6 s.

## 2. Edición (medida)

- **Cortes:** 42 de 43 son secos. Sin fundidos ni transiciones de plantilla.
- **Cámara (`camara:`):** 60 % de planos fijos; `push-lento` (+5 %) en líneas tensas; `push-fuerte` (+20 %) una sola vez, en la explicación clave; `pull` (alejamiento rápido del 7 %) en gritos cómicos.
- **Ritmo de voces:** pausa base de 0,18 s (la referencia tiene 0,28 s de mediana) y 0,5–0,6 s antes de los golpes. **Sin J-cuts:** con lip-sync, que la voz siguiente entre antes del corte se lee como desincronización.
- **Música:** está siempre presente, **~6 dB bajo la voz** (no es un fondo tímido), y va **por secciones**: suspenso → corte en la revelación → asombro → corte en el remate → cierre. Hace ducking: sube en los huecos sin diálogo.
- **Efectos:** foley en cada acción (puerta, silla, objeto, celular) y efectos de tensión (golpe grave, drone que crece, brillo en la revelación, tic de reloj). Sin efectos de dibujos animados.
- **Subtítulos:** blancos, sans 600, 46 px, 1–3 palabras, `y = 1150`, 180 px de margen lateral (zona segura de D6 `specs-formatos.md`: 14 % arriba, 35 % abajo, 180 px por lado); la etiqueta IA va en `y = 280`. Cada uno aparece cuando Whisper detecta su primera palabra.
- **Look:** contraste +7 %, saturación +6 %, viñeta suave que se cierra en los cortes de música.
- **Mezcla:** −17 ± 1 LUFS, pico ≤ −1 dBFS.

## 3. Reparto por papeles (genérico; se rediseña por oferta)

| Papel | Qué hace | Ejemplo |
|---|---|---|
| **protagonista** | calmo; trae el producto y lo **describe** | quien está usando el método |
| **autoridad** | interroga, seca | padre, madre, jefa, suegro |
| **fiscal** | sospecha; dice la mayoría de las objeciones | hermana, compañera, tía |
| **cómico** | desgano; se come el remate | cuñado, primo, compañero vago |

El escenario sale del `cliente_ideal` y del `locale`:

| Cliente ideal | Escenario |
|---|---|
| adultos | almuerzo familiar |
| jóvenes | piso compartido, facultad |
| profesionales | oficina, reunión |
| padres | grupo del colegio |
| parejas | cena con los suegros |

Comida, objetos, nombres y modismos son del país (paella en es-ES, asado o ravioles en es-AR, pasta en it-IT). Cada personaje tiene **una** ropa fija y **una** voz preset de su país.

## 4. Detonantes y remates que cumplen (sin resultados)

| Macro-nicho | Detonante (comportamiento, no resultado) | Producto revelado |
|---|---|---|
| dinero verde (CV, trabajo) | la oyeron ensayando sola en la cocina | guía + plantilla + guion de 30 s |
| dinero verde (finanzas personales) | ordena tickets en carpetas de colores | planilla de presupuesto |
| habilidades | se encierra a «practicar» con auriculares | curso, ejercicios, tiempo de uso |
| productividad | apaga el celular en la cena | método + plantilla de planificación |

**Remate:** alguien pide que se lo pasen al personaje cómico, el cómico protesta y la autoridad lo remata con un dato de su vida (no del espectador), en silencio.

## 5. Planos difíciles (lecciones)

- **Gesto hacia otro personaje** (señalar, retar): contraplano por encima del hombro, con el destinatario de espaldas en primer término (`elenco: solo`). Así el gesto tiene destino y el lip-sync mueve una sola boca.
- **Planos generales:** todo el elenco va como referencia; si no, el modelo inventa extras.
- **Planos cerrados:** sin la imagen del set (si no, copia su encuadre) y con «resto de la familia fuera de cuadro».
