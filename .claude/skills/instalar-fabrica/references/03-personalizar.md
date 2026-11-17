# 3 · Datos de esta instalación

Preguntale a la persona, en un solo mensaje:
1. El **id de instalación** que le dio el dueño del sistema (por ejemplo `socia-1`). Si todavía no lo tiene, usá uno provisorio con su nombre de pila en minúsculas y avisale que tiene que pedir el definitivo.
2. El **dominio** que va a usar (si no tiene, se compra en el paso 4; podés hacer este paso después).
3. El **correo de soporte** que va a aparecer en las tiendas y landings (lo normal: `soporte@<su dominio>`).
4. La **dirección del registro** que le pasó el dueño (por ejemplo `https://registro.algo.com`).

Después:
```
.venv/bin/python scripts/kit/personalizar.py --id <id> --dominio <dominio> --correo <correo> --registro-url <url>
```
La cuenta de Meta se agrega en el paso 5 con `--cuenta-meta`. El script reemplaza los marcadores (`tu-dominio.com`, `soporte@tu-dominio.com`, `TU_CUENTA_META`, `<carpeta del proyecto>`) en todo el proyecto y crea `empresa/instalacion.json` con una **semilla propia**: con ella el radar de esta instalación recorre las búsquedas en un orden distinto al de las otras fábricas.

Hecho cuando el estado marca ✓ en `personalizado` e `instalacion-json`.
