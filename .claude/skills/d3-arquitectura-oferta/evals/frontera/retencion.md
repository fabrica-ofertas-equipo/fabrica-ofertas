# Conjunto de retención de D3: [PENDIENTE: lo sella el dueño]

**Estado: no existe.** Este archivo deja explícito qué falta; la skill no lo inventa ni lo reemplaza con la suite pública.

| Qué | Requisito (nota 25 §11; docs/03 §2.5) |
|---|---|
| Quién lo sella | **El dueño**, con el sha256 de los bytes del archivo. D3, D1, D6 y X1 **no lo ven** |
| Tamaño | ≥ 30 % de los casos de la suite pública, con **≥ 60 positivos** (esperado ROJO o fuera de macro) |
| Anotación | por **dos personas** (ejes, nivel, veredicto, deseo conservado) |
| Crecimiento | +15 casos nuevos por trimestre y **uno por cada rechazo real** de Meta o Stripe |
| Primer lote | los 30 casos `RT-*` (no deben usarse para ajustar lints ni reglas); hacen falta ≥ 30 más para llegar a 60 positivos |
| Forma | el mismo YAML que `casos-frontera.yaml` (`casos:` con los mismos campos) |
| Dónde vive | **[PENDIENTE: ruta definitiva]** fuera del alcance de los agentes (no en `.claude/`, no en `ofertas/`); el hash del sello se guarda en `empresa/` con la firma del dueño |
| Cómo se corre | `scripts/medir_frontera.py --conjunto retencion --retencion <archivo> --sello sha256:<hex>` (sin el sello o con uno distinto, no corre) |
| Criterio | 0 falsos negativos peligrosos, 0 falsos verdes, n y cota ≤ 5 % informados; concordancia por eje ≥ 0,90; sobre-bloqueo ≤ 0,15 |

**Mientras no exista:** el DoD (d) de D3 («0 falsos negativos peligrosos en los casos de frontera») se mide con `desarrollo` y `rt` y se declara **sin certificar**; `medir_frontera.py` lo dice (`NO CERTIFICA`). El dueño no debe leer un 0 en desarrollo como 0 en retención.
