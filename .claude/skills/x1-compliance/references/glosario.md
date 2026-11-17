# Glosario de X1

| Término | Significado |
|---|---|
| **Veto** | un ROJO de X1 bloquea cualquier etapa; ningún nivel de autonomía lo relaja; solo se levanta corrigiendo el artefacto |
| **Dictamen** | un `qa` con `etapa = X1` y `etapa_objetivo`; por `oferta_id` y `locale`; vale solo con **sello** |
| **Sello** | archivo `empresa/compliance/sellos/<artefacto_sha256>.json` emitido por **`compliance.sellar`** (código) con firma Ed25519 de una clave que el agente no tiene; lo verifican los hooks de D5 y D7 antes de publicar o activar. Cambiar el artefacto o `reglas_version`, o vencer, lo invalida |
| **ROJO / AMARILLO / VERDE** | semáforo del hallazgo; en el esquema, minúsculas `rojo/amarillo/verde` |
| **A / B** (amarillo) | A: un eje amarillo; B: dos o más |
| **P · C · E · N** | ejes de riesgo: Promesa, Contenido, Encuadre, Negocio (`criterio-riesgo.md`) |
| **Bandera S · R · D** | el deseo central toca salud, relaciones o dinero (las tres se registran; hay un primario y a lo sumo un secundario) |
| **Reencuadre** | cambio que conserva el deseo y baja el nivel a ≤ amarillo (RE-01…15); cambiar solo sinónimos es elusión (LM-08) |
| **Línea roja** | promesa, contenido o modelo de negocio excluido (LP/LC/LM-nn); no es un tema |
| **Espectador ajeno** | prueba de E: la frase debe ser verdadera y neutra para cualquiera |
| **L1 / L2 / L3** | checks deterministas / rúbrica con evidencia / simulaciones |
| **RHS** | revisión humana de seguridad (una persona, 30-60 min, primer lanzamiento de cada hoja × idioma) |
| **Gate H** | aprobación humana con firma del dueño; registra el riesgo residual aceptado (decisión 14) |
| **Riesgo residual aceptado** | decisión 14: sin revisión legal humana; X1 automatiza lo verificable; lo fiscal, el contador |
| **Hoja** | unidad hoja × idioma de la taxonomía (nota 25); un rechazo de producto o contenido congela la hoja, uno de pieza el ángulo |
| **Falso verde** | un caso rojo clasificado verde (peligroso); requisito: 0 sobre ≥ 60 positivos de retención, con n y cota |
| **Sobre-bloqueo** | un legítimo clasificado un nivel por encima; requisito: ≤ 15 % |
| **Retención** | conjunto de casos sellado por hash, anotado por dos personas e invisible a Makers y linters |
| **Hallazgo** | `check_id`, `patron_clave` (kebab), `severidad` (BLOQUEANTE/MAYOR/MENOR/MEJORA), cita literal, corrección segura |
| **VC-01…16** | checks del sello de recolección de D1 |
| **Descriptor** | texto que aparece en el extracto de la tarjeta; estático y neutro, igual al declarado a Stripe |
| **MoR / Managed Payments** | comerciante registrado: Stripe cobra y liquida impuestos (+ tarifa; exige producto 100 % automatizado) |
| **DSA** | beneficiario y pagador obligatorios en anuncios dirigidos a la UE |
| **T1-T4** | jerarquía de fuentes de un hecho (T1 reguladores oficiales; eficacia T2 atribuida; T3 contexto; T4 nunca como hecho) |
