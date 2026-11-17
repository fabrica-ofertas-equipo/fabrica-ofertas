"""Constructores de entradas SINTÉTICAS para pruebas y dorados de D2 (no son datos de mercado; URLs `.invalid`)."""
from __future__ import annotations


def ev(n: int, tipo: str = "ad") -> dict:
    return {"id": f"EV-{n:02d}", "url": f"https://ejemplo.invalid/{tipo}/{n}", "fecha": "2026-11-06"}


def conc(cid: str, mec: str, ang: str, edad: int, activo: bool = True, e: str = "EV-01") -> dict:
    return {"concepto_id": cid, "activo": activo, "antiguedad_dias": edad, "tipo_mecanismo": mec,
            "angulo_principal": ang, "evidencia_id": e}


def op(oid: str, tipo: str, conceptos: list, paises=("IT",), embudo: str = "0.5", truncado: bool = False,
       leidos: int = 3, primer: int = 120) -> dict:
    return {"operador_id": oid, "tipo_anunciante": tipo, "motivo_clustering": "página aislada = su propio operador",
            "paginas": [oid.replace("op-", "9")], "paises": list(paises), "embudo": embudo, "truncado": truncado,
            "anuncios_leidos": leidos, "primer_anuncio_observado_dias": primer, "conceptos": conceptos}


def base_entrada() -> dict:
    return {
        "schema_version": "1.0.0", "oferta_id": "OF-202611-01", "candidato_id": "CAND-01", "locale": "it-IT",
        "fecha_corte": "2026-11-06T12:00:00Z", "paises_consultados": ["IT"],
        "mu": {"tipo_mecanismo": "M3", "indistinguible_de_sostenido": False, "evidencia_id": None},
        "angulo_recomendado": "calendario-cuotas", "diferenciador_sustentado": True,
        "evidencias": [ev(i) for i in range(1, 9)],
        "mercado_resumen": {"anuncios_activos": 61, "edad_mediana_dias": 52},
        "operadores": [], "huecos": [], "sustituto_gratis": "diferenciado", "lectura_snapshots": "humano_muestreo",
        "evidencia_locale": {"e1_o_e2": 2},
        "voz": {"frases_total": 34, "frases_propias": 12, "frases_del_locale": 34,
                "fuentes": {"foro-a.invalid": 12, "foro-b.invalid": 11, "resenas-c.invalid": 11}},
        "confianza_datos": {"competidores_profundos": 5, "competidores_con_snapshot_leido": 4, "landings_analizadas": 4,
                            "consultas_distintas": 12, "segunda_pasada": True, "videos_total": 0, "videos_transcriptos": 0,
                            "relectura_realizada": False, "historial_dias": 7, "jaccard_replica": None},
        "riesgo": {"heredado": {"P": "verde", "C": "verde", "E": "verde", "N": "verde", "nivel": "verde", "subnivel": None},
                   "final": {"nivel": "verde", "subnivel": None}, "angulo_seguro_existe": True,
                   "reencuadre_verificable_x1": False, "x1_dictamen": "PASS"},
    }


_ANGS = [["flujo-mensual", "orden-de-deudas", "recordatorios"], ["tabla-de-pagos", "simulador-cuotas", "informe-de-credito"],
         ["calendario-visual", "presupuesto-familiar", "metodo-bolas-de-nieve"],
         ["checklist-de-vencimientos", "plan-anual", "tarjetas-y-prestamos"], ["agenda-de-pagos", "alertas-de-cuota", "resumen-trimestral"]]


def operadores_sostenidos(mecs: list[str], tipo: str = "producto_digital", paises=("IT",)) -> list[dict]:
    """Un operador sostenido por cada mecanismo de `mecs` (3 conceptos de >= 55 días, un país, landing con checkout)."""
    ops = []
    for i, m in enumerate(mecs):
        a = _ANGS[i % len(_ANGS)]
        ops.append(op(f"op-0{i + 1}", tipo, [conc(f"c{i + 1}1", m, a[0], 90), conc(f"c{i + 1}2", m, a[1], 70 if i % 2 == 0 else 90),
                                              conc(f"c{i + 1}3", m, a[2], 55)], paises=paises, primer=120 if i else 40))
    return ops


def hueco(presente=(), frases: int = 6, fuentes: int = 3) -> list[dict]:
    return [{"hueco_id": "h-01", "descripcion": "ningún sostenido unifica las cuotas de préstamos propios en un calendario",
             "presente_en": list(presente), "frases": frases, "fuentes": fuentes, "evidencia_id": "EV-02"}]


def entrada_go() -> dict:
    e = base_entrada()
    e["operadores"] = operadores_sostenidos(["M1", "M1", "M7", "M2"])
    e["huecos"] = hueco()
    return e
