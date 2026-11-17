# tests
Pruebas: una subcarpeta por componente de Python (tests/<componente>/test_*.py, unittest compatible con pytest).
Fixtures en tests/fixtures/<componente>/. Sin red ni credenciales. Pruebas de Node viven junto al código (<carpeta>/test/*.test.mjs).
Propietario: cada componente escribe solo en su subcarpeta.
Todo: bash scripts/test_all.sh
Una sola: .venv/bin/python -m unittest discover -s tests/<componente> -t .
