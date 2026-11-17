# Cómo pulirla (para el dueño) y checklist de paso 0.1 → 1.0.0

> **v0.1 sin pulir (borrador generado desde la spec; no promover a 1.0.0 hasta cumplir el DoD: corrida manual real del dueño, retro de 30-45 min y DoD firmado por el dueño).**
> Método del dueño: a mano → pulir → skill → el agente la usa. Esta v0.1 es el «a mano» ya redactado: **no es criterio tuyo todavía**. Tu trabajo es correr cada paso con el Maker en la pestaña Code, corregir, y anotar por qué.

## 1. Preparación de una corrida a mano (≈ 15 min)
1. `.venv/bin/python -I .claude/skills/m1-mercados-localizacion/scripts/autoprueba.py` — debe dar todo `OK` (y `D09` como `L2`).
2. Elige **un país nuevo por iteración** (3 iteraciones máx., cada una con un país distinto; evita sobreajustar a un par de países). Máximo 2 h por iteración.
3. Pega este arranque en la sesión del Maker (`m1-maker`): «Ejecuta el SOP de la skill `m1-mercados-localizacion` en modo `<atlas|seleccion>` para `<país/locale>` y el candidato `<…>`. No leas nada fuera de las rutas de la skill, `docs/`, `departamentos/16-…`, `contratos/`, `empresa/` y `ofertas/<id>/`. Marca `[SUPUESTO]`/`[VERIFICAR]`. Primero las preguntas bloqueantes.»

## 2. Qué mirar en una corrida (preguntas de criterio)
- ¿La **cobertura de Polonia cambia según la fase** (y la de cualquier país con un método local clave)? ¿Salen las dos fases, el valor de desbloqueo, el hueco PayPal y la moneda?
- ¿**Cada celda de la ficha tiene fuente, fecha y confianza**? Abre 5 enlaces al azar: ¿dicen lo que la ficha dice?
- ¿**El puntaje se reproduce con el script**? (`puntaje.py reproducir` y `chequeos_l1.py` en 0 bloqueantes.)
- ¿La ficha dice **qué NO sabe**? ¿Hay algún lenguaje de favorito o de prior (aunque sea sutil: «el mejor», «sobre todo», «obviamente»)?
- ¿El ajuste de creadores está **solo informativo** (peso 0) y no desempata?
- ¿Un empate se presenta como empate? ¿La salida dice «señal de proceso» cuando no hay clics suficientes?
- ¿Las exclusiones R3 excluyen un **par (promesa, país)** y no un tema? ¿Cada etiqueta de promesa cita evidencia?
- ¿El resumen de 1 página del gate H se entiende sin abrir otros archivos (mercado elegido, 2 alternativas, qué se asume, qué falta)? **Tiempo tuyo por selección ≤ KPI de §3.5 de la spec.**
- Pregunta de oro: **«¿qué dato barato movería más el resultado?»**

## 3. Qué anotar en la bitácora del panel (`Pulido`)
Una línea por corrección: `n.º | archivo y sección | antes → después | categoría | tu motivo con tus palabras`. Categorías: **[error]** hecho o cálculo mal · **[regla]** criterio que quieres siempre · **[pref]** gusto tuyo · **[riesgo]** política/legal/dinero · **[contexto]** solo vale para este caso. Marca además: qué `[SUPUESTO]` aceptaste, cuáles cambiaste, qué decisión abierta (`preguntas-abiertas.md`) respondiste, cuánto tardaste y qué país probaste.
Luego la **retro de 30-45 min** (`docs/03` §2.3): reglas candidatas con evidencia, preferencias tuyas (no van a la skill), errores que un script habría detectado (checks L1 nuevos), ítems de rúbrica reescritos desde tus preguntas, ≥ 2 dorados nuevos y ≥ 10 sembrados.

## 4. Checklist de paso de 0.1 a 1.0.0 (DoD de la spec §10.4 + docs/03 §2.6; **no marcar sin evidencia reproducible**)
- [ ] **Atlas v1** con los 15 países de 08 §2.2 más RO y FR: 100 % de hojas con fuente + fecha + confianza (`vigencia.py` sin bloqueantes en cada ficha). *Hoy: no existe `empresa/mercados/`; RO y FR fuera de `rank.py`.*
- [ ] `puntaje.py reproducir` en `ok` (15 totales de 08 §2.2 ±1; sensibilidad de 08 §2.5; escenario `corregido`: CA 71 … IT 53, PL 51) con los mismos datos.
- [ ] **Eval de cobertura por fase correcto en PL e IT** con fichas **reales** (no las de ejemplo).
- [ ] **QA detecta ≥ 90 % de los bloqueantes sembrados con 0 falsos PASS**: L1 por `autoprueba.py` (hoy 12/12 de los medibles por script) **y** L2 (D09) en una corrida real del `m1-qa`; sembrados rotados.
- [ ] **Cero cadenas con país favorito** (autoprueba pasa; revisión humana del texto de las salidas).
- [ ] `mercado.json` válido con `validar_esquemas` en modo sellado (`chequeos_l1.py --modo sellado` en 0 bloqueantes).
- [ ] El dueño **aprueba 2 selecciones de práctica sin reescribir el razonamiento** (una de dinero, una de salud o relaciones; países distintos).
- [ ] **Pedidos a S-A listados y sin ediciones fuera de propiedad** (`dependencias.md` §1-§3 revisado; ninguna incoherencia abierta de I1-I14 resuelta por la skill; I1, I2, I7 e I14 ya están resueltas por S-A).
- [ ] ≥ 6 evals con vs. sin skill (Sonnet y Haiku; con skill > sin skill en cada uno), 3 corridas del mismo caso con decisión clave igual en ≥ 2 de 3 (`docs/03` §2.6 ítems 3-4).
- [ ] Prueba de inyección (texto hostil en una fuente de la ficha) pasa: el Maker lo trata como dato.
- [ ] Corrida en sombra (`docs/03` §2.7): ≥ 80 % de coincidencia de ítems de rúbrica (≤ 1 punto) en 2 sombras seguidas y 0 `[skill-falla]` BLOQUEANTE.
- [ ] Decididas (o explícitamente diferidas con firma) las **preguntas P1-P8** de `preguntas-abiertas.md`.
- [ ] Parámetros `grupos.mercados` integrados en `empresa/parametros.yaml` (o aceptado el fallback por escrito) y `scripts/mercados/` con tests del repo.
- [ ] CHANGELOG actualizado y tag `skill/m1-mercados-localizacion/v1.0.0` por PR aprobado por el dueño. Si fallan ítems no innegociables: `v0.9` con la deuda escrita.

## 5. Ascenso de nivel (spec §7)
N0-N1: dueño en Code con el Maker, todo se revisa (5 selecciones con ≤ 1 corrección para subir). N2: Maker + QA + X1, gate H en el primer lanzamiento de país o idioma y en toda exposición fiscal (≥ 10 selecciones, 0 fichas vencidas aceptadas, QA ≥ 90 % de sembrados). N3: S por excepción, **efectivo H mientras `limites.acciones_gate_humano` contenga `lanzamiento_pais_idioma_nuevo`**; H si cambia el régimen fiscal, entra un país con idioma legal obligatorio o se supera el tope de mercados. El veto de X1 por jurisdicción no se relaja con el nivel.
