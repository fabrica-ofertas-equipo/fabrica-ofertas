# scripts
Comandos de operación y código determinista suelto: bootstrap.sh, test_all.sh, lint.sh, y CLI sin paquete propio.
Propietario: A0 (herramientas); subcarpetas youtube/ y mercados/ pertenecen a la investigación (no tocar).
Todo script con efecto externo: dry-run por defecto y --live con comprobaciones.
Uso: bash scripts/bootstrap.sh ; bash scripts/test_all.sh ; bash scripts/lint.sh
Probar: python3 -m unittest discover -s tests/scripts -t .
