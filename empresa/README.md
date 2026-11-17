# empresa
SOLO plantillas (*.ejemplo.*): estructura de los datos vivos de la empresa. Sin datos reales ni secretos.
Los datos reales viven en empresa/ en producción (backbone §4) y tienen su propia política: PAUSA, *.jsonl, estado.json y *.lock están en .gitignore; los demás archivos se versionan.
Rutas protegidas: limites.yaml y parametros.yaml solo los edita el dueño.
Si existe empresa/PAUSA, todo script con efecto externo se bloquea.
Probar: python3 -m unittest discover -s tests/infra -t .
