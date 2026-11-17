# empresa/compliance/

Carpeta de datos de X1 (propietario único: **B6**, docs/06 §4.1 y R16: "`empresa/compliance/`
completa es de X1; O0 solo lee"). Nadie más escribe aquí.

- `sellos/<hash>.json`: un sello por `artefacto_sha256` sellado (`<hash>` = los 64 hex sin el
  prefijo `sha256:`), producido por `python -m compliance.sellar --live` (`compliance/sellar.py`).
  Contrato: `contratos/sello.schema.json`. Nunca se edita a mano ni se sobrescribe: un artefacto
  distinto tiene otro hash y por lo tanto otro archivo; un sello vencido se reemplaza re-sellando
  la etapa, no editando el `vigencia_hasta`.
- Antes de **usar** un sello (activar una campaña, publicar una landing), quien lo use llama a
  `python -m compliance.verificar` (`compliance/verificar.py`), que relee el archivo, revalida la
  firma y vuelve a hashear el artefacto (TOCTOU): un sello en disco no es automáticamente un sello
  vigente.

En modo prueba (`FABRICA_ENTORNO=prueba`, docs/06 §6.1), `scripts/b0_e2e.py` apunta `FABRICA_RAIZ` a
una carpeta temporal con su propia copia de esta carpeta: el `empresa/compliance/` real nunca se
toca por una corrida de B0.

- `terminos_sensibles/<locale>.yaml` (D-02b, B6b ola 2): léxico ADICIONAL que el Maker de X1 propone
  (él no puede editar `compliance/` ni resellar `reglas_sensibles.yaml`). `compliance.lint_claims`/
  `compliance.html_checks` lo suman automáticamente a las reglas base, sin poder debilitarlas (solo
  añade patrones nuevos; ver `compliance/README.md` Decisión 12). Ver el formato en
  `empresa/compliance/ejemplos/terminos_sensibles.es-ES.ejemplo.yaml` (ese archivo de ejemplo NO se
  lee en tiempo de ejecución; solo documenta la forma).
