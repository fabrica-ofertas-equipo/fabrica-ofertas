# Glosario mínimo

| Término | Significado |
|---|---|
| **A / S / H** | gate automático / semi (el humano audita por excepción) / humano obligatorio |
| **N0-N4** | nivel de autonomía **por etapa** (`empresa/autonomia.yaml`): N0 a mano, N1 Maker con skill y todo H, N2 Maker + QA con H en oferta/landing/activar/subir/M1 nuevo, N3 por excepción, N4 botón de punta a punta |
| **Gate efectivo** | el más estricto entre `gates.json` por el menor nivel y `limites.acciones_gate_humano` |
| **Oferta / familia** | concepto × idioma/clúster de mercados (`OF-AAAAMM-NN`); las del mismo concepto forman una familia (`FAM-AAAAMM-NN`) |
| **Candidato** | problema del banco de D1 con mecanismo único + entregable único, riesgo por promesa, contenido, encuadre y negocio (verde/amarillo/rojo) |
| **Macro-nicho** | salud, relaciones o dinero, por el deseo central del problema |
| **PAUSA** | `empresa/PAUSA`: kill switch; presencia = pausa |
| **Fail-closed** | sin dato o con duda, se bloquea (código 5 o 4) |
| **BLOQ / MAYOR / MENOR / MEJORA** | severidad de un hallazgo de QA |
| **Oferta validada** | Stripe, neta de reembolsos, cohorte madura, CPA ≤ objetivo (backbone 5.9) |
| **Techo vs plan** | el brief fija **techos** (`test_total_max`, `test_diario_max`); el plan real sale de `economia.gasto_test_plan` |
| **Sin asignar** | `OF-000000-00` / `FAM-000000-00` en un borrador: los asigna el motor |
| **Orden firmada** | `{accion, oferta_id, etapa?, hash_objetivo, ts, nonce, firma}` Ed25519 que genera `orq firmar` |
