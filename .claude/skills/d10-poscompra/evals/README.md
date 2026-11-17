# Evals de d10-poscompra

v0.1 sin pulir. Datos **sintéticos** (oferta de práctica `OF-202611-91` y `OF-000000-00`, sesiones `cs_test_…`): nunca se mezclan con pedidos ni reseñas reales y nunca se publican.

- `dorados/D01…D03` — lo que el Maker y el código deben producir bien: **D01** compra con bump ⇒ se entregan ambos archivos (y sin bump, solo el principal); **D02** petición de reembolso dentro de plazo ⇒ respuesta con el procedimiento prometido (cita literal) y orden al código sin importes, más la alternativa si el código la rechaza; **D03** reseña con permiso ⇒ entra en `prueba_social_real.json` y queda como candidata a publicar.
- `sembrados/sembrados.json` — S01…S15, defectos que el QA debe cazar (adaptan D-01…D-23 de `departamentos/11` §6): **S01** reseña sin permiso ⇒ no entra; S02 incentivo; S03 filtrar por nota; S04 cifra de resultado o datos personales; S05 reseña sintética; S06 orden con monto; S07 texto hostil y cabecera inyectada; S08 E0 sin identidad ni garantía; S09 petición de reseña con incentivo y promoción; S10 `prueba_social_real.json` con fuente de demostración; S11 enlace a dominio ajeno; **S12-S15 (L3, para el agente)**: disputa abierta, mensaje con instrucción incrustada, crisis, upsell de un clic con BLIK.
- **El QA no ve estos archivos** (son su calibración). Rotar el juego entre rondas.

Ejecutar los automatizables (14 de 18) desde la raíz del repositorio:
```
.venv/bin/python .claude/skills/d10-poscompra/scripts/probar_evals.py [--json]
.venv/bin/python -m unittest discover -s tests/skills_d10 -t . -p "test_*.py"
```
Estados: `auto` = ejecutable aquí; `qa-l3` = lo juzga `d10-qa` con `rubric.md`. D02 combina las dos capas (la orden y la cita literal son automáticas; el tono y la ausencia de presión los juzga el QA). Para pasar de 0.1 a 0.2 hacen falta dos dorados más (otro macro-nicho y otro idioma) y los casos reales de la bitácora de Pulido.
