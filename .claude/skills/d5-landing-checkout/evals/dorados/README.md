# Dorados y bloqueos esperados

v0.1 sin pulir (borrador generado desde la spec; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño).

`dorados.json` lista los casos de la spec §10.5 (DG-01…DG-05 dorados; DG-06…DG-10 bloqueos o comportamientos esperados). Estados: **ejecutable** (lo prueba `scripts/test_scripts.py`), **parcial**, **especificado** (faltan artefactos que se construyen en la primera corrida manual).

- `DG-04` = `templates/{copy,paleta,assets}.ejemplo.json` sobre `ofertas/_ejemplo` (dinero, `es-ES`, bump).
- `DG-02` = `relaciones-pl-PL/` (relaciones, `pl-PL`, PLN): `oferta.min.json` sintética, `copy.json`, `paleta.json`, `assets.json`. **Textos en polaco sin revisor nativo** `[SUPUESTO]`.
- Cada dorado debe dar **PASS** del QA (puntaje ≥ `landing.umbral_qa`, críticos R1/R2/R5/R7 ≥ 3) y 0 BLOQUEANTE/MAYOR en `lint_copy.py` y `contraste_paleta.py`.
- Casos de otro nicho y de otro idioma (DG-01, DG-03, DG-05) evitan el sobreajuste al caso de `_ejemplo`; el nicho del video (edición de video) no entra salvo como eval negativo.

Ejecutar: `.venv/bin/python -m unittest discover -s .claude/skills/d5-landing-checkout/scripts -p "test_*.py"`.
