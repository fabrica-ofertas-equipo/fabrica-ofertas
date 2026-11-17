# Exposición por país × macro-nicho (EXPO, R3, R4)

> Fuente: `departamentos/16` §4.1 (R3, R4, EXPO) y Anexo D; `docs/_investigacion/25-marco-salud-relaciones-dinero.md` §8.1 y §11; `22e`. **Manda X1**: `empresa/compliance/{paises,matriz_pais_nivel,ayuda_por_pais}.yaml` **no existen todavía** `[PENDIENTE: lo construye X1]`. Mientras tanto M1 usa la SEMILLA de `scripts/semilla_exposicion.json` y marca `[SUPUESTO]` en `matriz_ref.estado`; cuando exista, manda X1 (MQ-12, con el hash citado) y la semilla se descarta.
> Criterio del dueño (decisión 13): **el riesgo se evalúa por promesa, contenido, encuadre y modelo de negocio, nunca por tema.** Una «cura» es rojo; una guía de reinserción laboral para madres es válida; «ganar dinero con manualidades» es válido si no promete ingresos. Aquí se excluyen **pares (promesa/contenido, país)**, jamás el tema entero.
> Sin abogado (decisión 14): ningún paso pide revisión legal humana; lo verificable lo automatizan X1 y sus lints J03-J05; lo fiscal es del contador. El **gate H del dueño** (una vez por país × macro × nivel) registra el riesgo residual aceptado.

## 1. Exposición y nivel máximo sin gate
V (bajo) · A (medio) · A+ (medio-alto) · R (alto). Nivel máximo sin gate: V → hasta amarillo-b con ayuda verificada · A → amarillo-a (B con gate H, ayuda y revisión) · A+ → amarillo-a (se rige por la matriz de X1 y los lints J03-J05; el overlay de mercado **solo sube niveles y no reemplaza los lints**) · R → verde, y solo producto de hogar sin cifra de ahorro, instrumento ni ingreso.
Observación abierta (PEDIDO, no resuelta aquí): la spec 16 deja A+ en amarillo-a sin gate; la nota 25 §8.1 exige gate H del dueño por país × macro × nivel para A+. `puntaje.py` marca la bandera `gate_h_exposicion` en ambos casos: coincide con las dos lecturas.

## 2. Semilla (resumen; el dato máquina está en `scripts/semilla_exposicion.json`)
La tabla país × macro (`exposicion`) y las condiciones que M1 pasa a R3/R4 salen del Anexo D de la spec: PL (sin cripto en dinero; sin bata ni estética clínica, UOKiK; ayuda 800 70 2222), IT (J05 en dinero; «senza dieta» y plazos = patrón AGCM; ruptura y duelo con Telefono Amico), RO (sin ayuda de crisis verificada ⇒ R4 en emocional), FR (Toubon y menciones legales `[VERIFICAR]`), ES (salud: sin términos del RD 1907/1996 art. 4; verificación financiera de Meta = parada), DE (sin formato «curso», sin ayuda fiscal personalizada StBerG §5, HWG en salud), GB/IE (IVA/registro desde la primera venta en UK; J05), US (FTC; inversión roja en anuncios), AU (dinero solo de hogar), CA (sin hipotecas LM-11). **NZ y PT no están evaluados**: heredan por analogía `[SUPUESTO]` y llevan gate H por «no evaluado».

## 3. Cómo se aplica (SOP paso 3)
1. **Etiqueta** la promesa/contenido FINAL del candidato (después del reencuadre) con las etiquetas de la semilla (`formato_curso`, `ayuda_fiscal_personalizada`, `eficacia_salud`, `termino_rd1907_art4`, `instrumento_financiero`, `ingresos`, `inversion`, `cripto`, `estetica_clinica`, `producto_hogar`, `requiere_ayuda_emocional`…), **citando la evidencia** de cada etiqueta (frase del anuncio/landing/nombre o línea del contenido). Una etiqueta sin evidencia no cuenta; una etiqueta omitida es el defecto que el QA caza leyendo la promesa (sembrado D09: salud en DE con promesa de eficacia puesta como verde).
2. Corre `puntaje.py excluir`: R3 cruza etiquetas × `restricciones[]` del país; R4 cruza `ayuda_verificada`.
3. EXPO = **peor caso** entre `macro_nicho` y las banderas S·R·D del candidato (nota 25 §8.1: J01 lee por bandera, no por macro primario). `macro_secundario` y `riesgo.banderas` **no existen aún** en `candidatos` 1.0.0: hasta entonces usa `categoria` + `macro_nicho` y marca `[SUPUESTO]`.
4. País sin fila de matriz ⇒ R3 («pregunta bloqueante a X1»), nunca un EXPO inventado.

## 4. Frontera (calibración)
Los casos de `docs/_historial/hwr-semillas/casos-frontera.yaml` con `mercado_gate` deben dar **el mismo veredicto país × nivel** que la proyección de la matriz (0 divergencias). Hoy no se puede correr: depende de `matriz_pais_nivel.yaml` (X1). Un LLM nunca baja un nivel que el lint subió; el overlay solo sube.
