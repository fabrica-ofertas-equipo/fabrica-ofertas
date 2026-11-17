"""Veto por países del referente (2026-11-14, tras Oferta D en México con el original pautando ahí).

- elegir_mercado.py: un país con anuncios activos del referente sale del orden; sin países libres → código 3 (descartar),
  con países por medir → código 4.
- ordenar_candidatos.py: un candidato cuyo referente corre en todos los países lanzables queda fuera.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / ".claude" / "skills" / "modelar-y-lanzar-oferta" / "scripts"
ELEGIR = SCRIPTS / "elegir_mercado.py"


def _mod(nombre: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(nombre, SCRIPTS / f"{nombre}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _plantilla(tmp: Path) -> tuple[Path, list[str]]:
    out = subprocess.run([sys.executable, str(ELEGIR), "plantilla"], capture_output=True, text=True, check=True).stdout
    p = tmp / "mercados.json"
    p.write_text(out, encoding="utf-8")
    return p, [x["pais"] for x in json.loads(out)["paises"]]


def _ordenar(mercados: Path, medicion: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ELEGIR), "ordenar", str(mercados), "--inicio", "2026-12-01",
                           "--medicion", str(medicion)], capture_output=True, text=True)


def test_referente_en_todos_los_paises_descarta(tmp_path):
    mercados, paises = _plantilla(tmp_path)
    med = tmp_path / "med.json"
    med.write_text(json.dumps({"paises": {c: 100 for c in paises}}), encoding="utf-8")
    r = _ordenar(mercados, med)
    assert r.returncode == 3, r.stdout + r.stderr
    assert "DESCARTAR LA OFERTA" in r.stdout
    assert "Recomendado" not in r.stdout


def test_pais_del_referente_nunca_se_recomienda(tmp_path):
    mercados, paises = _plantilla(tmp_path)
    d = json.loads(mercados.read_text(encoding="utf-8"))
    for p in d["paises"]:
        if p["pais"] in ("MX", "DE"):
            p.update(competencia=3, consulta_competencia="frase", medido=True)
    mercados.write_text(json.dumps(d), encoding="utf-8")
    med = tmp_path / "med.json"
    med.write_text(json.dumps({"paises": {"MX": 127}, "sin_anuncios": ["DE"]}), encoding="utf-8")
    r = _ordenar(mercados, med)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Recomendado: DE" in r.stdout
    assert "MX (VETO" in r.stdout


def test_sin_libres_medidos_pero_faltan_paises(tmp_path):
    mercados, _ = _plantilla(tmp_path)
    med = tmp_path / "med.json"
    med.write_text(json.dumps({"paises": {"MX": 127, "US": 147}}), encoding="utf-8")
    r = _ordenar(mercados, med)
    assert r.returncode == 4, r.stdout + r.stderr
    assert "Recomendado" not in r.stdout


def test_candidato_con_referente_global_queda_fuera():
    oc = _mod("ordenar_candidatos")
    todos = {c: 90 for c in oc.LANZABLES}
    cands = [
        {"pagina": "Global", "anuncios": 150, "dias": 120, "funnel": "advertorial+tsl", "tema": "a",
         "referente_paises": {"paises": todos}},
        {"pagina": "Local", "anuncios": 40, "dias": 30, "funnel": "tsl", "tema": "b",
         "referente_paises": {"paises": {"GB": 47}, "sin_anuncios": [c for c in oc.LANZABLES if c != "GB"]}},
        {"pagina": "SinMedir", "anuncios": 40, "dias": 30, "funnel": "tsl", "tema": "c"},
    ]
    res = oc.ordenar(cands, [])
    elegibles = [f["pagina"] for f in res["elegibles"]]
    assert "Global" not in elegibles
    assert {"Local", "SinMedir"} <= set(elegibles)
    assert res["sin_mercado"] == 1
    sin_medir = next(f for f in res["elegibles"] if f["pagina"] == "SinMedir")
    assert sin_medir["medir_paises"] is True


def test_lista_ampliada_sin_sancionados_ni_duplicados():
    em = _mod("elegir_mercado")
    codigos = [p[0] for p in em.PAISES]
    assert len(codigos) == len(set(codigos)) >= 90
    fuera = set(" ".join(em.FUERA.values()).split())
    assert not (fuera & set(codigos))
    for sancionado in ("RU", "VE", "IR", "CU", "CN", "BJ"):
        assert sancionado not in codigos


def test_stripe_disponible_marca_requiere_stripe(tmp_path):
    mercados, _ = _plantilla(tmp_path)
    d = json.loads(mercados.read_text(encoding="utf-8"))
    for p in d["paises"]:
        if p["pais"] in ("PL", "CZ"):
            p.update(competencia=3, consulta_competencia="frase", medido=True, referente=0)
    mercados.write_text(json.dumps(d), encoding="utf-8")
    base = [sys.executable, str(ELEGIR), "ordenar", str(mercados), "--inicio", "2026-12-01"]
    con = subprocess.run(base, capture_output=True, text=True)
    sin = subprocess.run(base + ["--sin-stripe"], capture_output=True, text=True)
    fila = lambda out: next(l for l in out.splitlines() if l.startswith("|") and " PL " in l)
    assert "| 1.0 |" in fila(con.stdout)
    assert "| 0.4 |" in fila(sin.stdout)
    assert "Recomendado: PL" in con.stdout and "REQUIERE STRIPE" in con.stdout
    assert "REQUIERE STRIPE" not in sin.stdout
