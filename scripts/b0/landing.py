"""B0-11 (``landing``, dueño B4): ``landing.validar`` pasa el ejemplo y falla el 100 % de las 12
mutaciones sembradas (``tests/fixtures/contratos/mutaciones_landing/catalogo.json``, de CT: 8 base
``ML-01…08`` + 4 complementarias ``MC-01…04``).

Ejercita ``landing.validar.validar_sitio`` (real, B4) aplicando cada mutación con
``tests.contratos.aplicar_mutacion_landing`` (helper de solo lectura/aplicación sobre copias
temporales, de CT) a una copia de ``ofertas/_ejemplo``; nunca toca el ejemplo real.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


def _escenario() -> tuple[bool, str, list[str]]:
    from landing import validar as Val
    from tests.contratos import aplicar_mutacion_landing as A

    raiz = Path(__file__).resolve().parents[2]
    ejemplo = raiz / "ofertas" / "_ejemplo"

    problemas: list[str] = []
    hallazgos_base = Val.validar_sitio(ejemplo)
    if hallazgos_base:
        return False, f"la base (ofertas/_ejemplo) NO pasa limpia: {[str(h) for h in hallazgos_base[:3]]}", []

    with tempfile.TemporaryDirectory(prefix="b0-landing-") as tmp_str:
        tmp = Path(tmp_str)
        mutaciones = A.mutaciones(incluir_complementarias=True)
        for m in mutaciones:
            copia = A.copiar_ejemplo(tmp, m["id"])
            A.aplicar(m["id"], copia)
            hallazgos = Val.validar_sitio(copia)
            disparadas = Val.reglas(hallazgos)
            if m["regla_esperada"] not in disparadas:
                problemas.append(f"{m['id']} ({m['nombre']}): esperaba {m['regla_esperada']}, disparó {sorted(disparadas)}")
                continue
            permitidas = {m["regla_esperada"], *m["reglas_colaterales"]}
            inesperadas = disparadas - permitidas
            if inesperadas:
                problemas.append(f"{m['id']}: reglas inesperadas además de la propia: {sorted(inesperadas)}")

    if problemas:
        return False, f"{len(problemas)}/{len(mutaciones)} mutación(es) no se comportaron como se esperaba", problemas
    return True, f"base limpia + {len(mutaciones)}/{len(mutaciones)} mutaciones (8 base + 4 complementarias) disparan su regla, sin otras inesperadas", []


def evaluar_b0_11():
    from scripts.b0_e2e import _con_captura_de_error, _rojo, _verde

    def cuerpo():
        ok, motivo, detalle = _escenario()
        if not ok:
            return _rojo("B0-11", motivo if not detalle else f"{motivo}: {detalle[:3]}")
        return _verde("B0-11", motivo)

    return _con_captura_de_error("B0-11", cuerpo)
