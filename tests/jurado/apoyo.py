"""Apoyo de las pruebas del Jurado de creativos: fixtures sintéticas, sin red y sin LLM. Todo se genera en cada prueba."""
from __future__ import annotations

import random
import statistics
from pathlib import Path
from typing import Any

from scripts.jurado import _comun as c
from scripts.jurado import agregar, avatares, paquetes

AHORA = "2026-11-08T07:00:00Z"


def voz_fixture(n_temas: int = 12, frases_por_tema: int = 2, fuentes: int = 3, lexico: bool = True) -> dict:
    """voz_cliente.json sintético con la forma real: frases con id, texto, fuente, tema y categoría."""
    frases = []
    for t in range(n_temas):
        for k in range(frases_por_tema):
            frases.append({
                "frase_id": f"f-{t:02d}{k}", "texto_literal": f"Zdanie testowe {t}-{k}", "locale": "pl-PL", "pais": "PL",
                "fuente_url": f"https://ejemplo.test/hilo/{(t + k) % fuentes}", "fecha": "2026-11-06",
                "categoria": "objecion" if t % 3 == 0 else "dolor", "tema": f"tema-{t}", "origen": "d2",
            })
    if lexico:
        frases.append({"frase_id": "f-lex", "texto_literal": "Kup teraz słownictwo", "locale": "pl-PL", "pais": "PL",
                       "fuente_url": "https://tienda.test/x", "fecha": "2026-11-06", "categoria": "lexico_de_compra", "tema": "lexico-solo", "origen": "d2"})
    return {"schema_version": "0.1.0-borrador", "oferta_id": "OF-TEST-01", "locale": "pl-PL", "fecha": "2026-11-07", "frases": frases,
            "lexico": ["słówka", "mapy myśli"]}


def panel_fixture(n: int = 6, baseline: bool = True, semilla: Any = 7, **kw) -> dict:
    voz = voz_fixture(**kw)
    return avatares.generar_panel(voz, "0" * 64, "voz.json", n, semilla, incluir_baseline=baseline, oferta_id="OF-TEST-01", ahora=AHORA)


def piezas_fixture(n: int = 5, con_precondiciones: bool = True) -> dict:
    piezas = []
    for i in range(n):
        p = {"ad_name": f"c{i:02d}-angulo{i}_img_h{i}_v1", "tipo": "texto", "texto_visible": f"Tekst reklamy numer {i}", "id_origen": f"G-{i:04d}"}
        if con_precondiciones:
            p["precondiciones"] = {"qa_a": "PASS", "lint": "PASS_CON_NOTAS"}
        piezas.append(p)
    return {"oferta_id": "OF-TEST-01", "locale": "pl-PL", "tanda_id": "t1", "piezas": piezas}


def anclas_fixture(origen: str = "medida") -> dict:
    ev = {"fuente": "OF-ANTERIOR/08-operacion", "metrica": "ctr_enlace", "valor": 0.031} if origen == "medida" else {"nota": "control escrito a mano para la prueba"}
    return {"locale": "pl-PL", "anclas": [
        {"ancla_id": "ancla-buena", "veredicto_conocido": "ganadora", "origen_resultado": origen, "tipo": "texto", "texto_visible": "Dobra reklama kontrolna", "evidencia": ev},
        {"ancla_id": "ancla-mala", "veredicto_conocido": "perdedora", "origen_resultado": origen, "tipo": "texto", "texto_visible": "Zła reklama kontrolna", "evidencia": ev},
    ]}


def armar_tanda(directorio: Path, semilla: Any = 11, n_avatares: int = 4, n_piezas: int = 5, baseline: bool = True, **kw) -> tuple[dict, dict, Path]:
    panel = panel_fixture(n_avatares, baseline)
    manifiesto = paquetes.armar(panel, piezas_fixture(n_piezas), anclas_fixture(), semilla, directorio, tanda_id="t1", ahora=AHORA, **kw)
    return panel, manifiesto, directorio


def voto_valido(llamada: dict, voto: bool = True, general: int = 7, **extra) -> dict:
    v = {"paquete_id": llamada["paquete_id"], "avatar_id": llamada["avatar_id"], "pieza_id": llamada["pieza_id"], "voto": voto,
         "motivo": "Me llama la atención porque habla de mi problema.", "puntaje_gancho": general, "puntaje_claridad": general,
         "puntaje_cta": None, "puntaje_general": general, "idea": None, "alerta_ceguera": None}
    v.update(extra)
    return v


def votos_de_tanda(manifiesto: dict, llave: dict, decide) -> list[tuple[str, dict]]:
    """Un voto por llamada; ``decide(llamada, nombre_pieza_o_ancla) -> (voto, general)``."""
    salida = []
    for o in manifiesto["orden_llamadas"]:
        pid = o["pieza_id"]
        nombre = llave["piezas"][pid]["ad_name"] if pid in llave["piezas"] else llave["anclas"][pid]["ancla_id"]
        voto, general = decide(o, nombre)
        salida.append((Path(o["archivo"]).stem + ".json", voto_valido(o, voto, general)))
    return salida


# ---------------------------------------------------------------------------------------------------------------
# Fixtures de calibración
# ---------------------------------------------------------------------------------------------------------------

def jurado_sellado(oferta: str, tanda: str, filas: list[dict], sellado_en: str, votos: list[dict] | None = None, rubrica: dict | None = None,
                   anclas_discriminan: bool = True, anclas_medidas: int = 1, demostracion: bool = False, locale: str = "pl-PL") -> dict:
    """Un jurado.json mínimo y sellado, con lo que lee ``calibrar``. ``filas``: {ad_name, share_si, puntaje_medio}."""
    piezas = [{"ad_name": f["ad_name"], "share_si": f["share_si"], "score": round(f["share_si"] + 0.001 * f["puntaje_medio"] / 10, 6),
               "puntaje_medio": f["puntaje_medio"]} for f in filas]
    doc = {
        "schema_version": c.ESQUEMA_VERSION, "tipo": "jurado_creativos", "demostracion": demostracion, "oferta_id": oferta, "locale": locale,
        "tanda_id": tanda, "sellado_en": sellado_en, "generado_en": sellado_en, "modo": "sombra", "aplica_orden": False,
        "piezas": piezas, "votos": votos or [], "orden": [], "precision": None,
        "baseline_rubrica": [{"ad_name": a, "score": s, "n_items": 3} for a, s in (rubrica or {}).items()],
        "anclas": {"share_si_ganadoras": 0.9 if anclas_discriminan else 0.2, "share_si_perdedoras": 0.1 if anclas_discriminan else 0.6,
                   "discrimina": anclas_discriminan, "medidas": anclas_medidas},
    }
    doc["sello"] = agregar.sellar(doc)
    return doc


def escenario_calibracion(habilidad: str, tandas: int = 30, por_tanda: int = 10, semilla: int = 3, rubrica: str = "ruidosa",
                          avatar_malo: bool = False, ruido_avatar: float = 0.0) -> tuple[list[dict], list[dict]]:
    """(jurados, métricas). ``habilidad``: 'perfecto' | 'aleatorio' | 'invertido'. Calidad real = CTR; etiqueta = por encima de la mediana de la tanda.

    ``rubrica``: 'ruidosa' (peor que el jurado perfecto), 'igual' (idéntica al jurado) o 'ninguna'.
    """
    rng = random.Random(semilla)
    jurados, metricas = [], []
    avatares_ids = [f"av-pl-PL-{i:02d}" for i in range(1, 11)]
    for t in range(tandas):
        perm = list(range(por_tanda))
        rng.shuffle(perm)
        puesto = {i: perm[i] for i in range(por_tanda)}  # 0 = peor pieza de la tanda, por_tanda-1 = la mejor (en TODAS las métricas)
        efecto_dia = rng.uniform(0.8, 1.2)  # el día y el presupuesto mueven todas las piezas por igual: la etiqueta relativa lo cancela
        filas, votos, rub = [], [], {}
        for i in range(por_tanda):
            ad = f"o1-t{t:02d}-a{i:02d}"
            frac = puesto[i] / (por_tanda - 1)
            ctr = (0.005 + 0.03 * frac) * efecto_dia
            clics = ctr * 100000
            metricas.append({"oferta_id": "OF-CAL", "ad_name": ad, "fecha_lectura": "2026-11-20", "gasto": (10 + 10 * frac) * efecto_dia, "impresiones": 100000,
                             "clics_enlace": clics, "vistas_3s": 20000 * (1 + frac) * efecto_dia, "pagos_iniciados": clics * (0.05 + 0.05 * frac), "compras": 0})
            if habilidad == "perfecto":
                nivel = puesto[i] / (por_tanda - 1)
            elif habilidad == "invertido":
                nivel = 1 - puesto[i] / (por_tanda - 1)
            else:
                nivel = rng.random()
            vs = []
            for k, aid in enumerate(avatares_ids):
                n_av = nivel
                if avatar_malo and k == 0:
                    n_av = 1 - nivel
                if ruido_avatar:
                    n_av = min(1.0, max(0.0, n_av + rng.gauss(0, ruido_avatar)))
                vs.append({"ad_name": ad, "avatar_id": aid, "voto": n_av > 0.5 or (n_av == 0.5), "puntaje_general": int(round(10 * n_av))})
            votos += vs
            share = sum(1 for v in vs if v["voto"]) / len(vs)
            if habilidad == "perfecto" and not avatar_malo and not ruido_avatar:
                share = (puesto[i] + 1) / por_tanda  # jurado sin empates: ordena exactamente por CTR
            pm = statistics.fmean(v["puntaje_general"] for v in vs)
            filas.append({"ad_name": ad, "share_si": round(share, 4), "puntaje_medio": pm})
            if rubrica == "ruidosa":
                rub[ad] = round(puesto[i] / (por_tanda - 1) * 4 + rng.uniform(-4, 4), 3)
            elif rubrica == "igual":
                rub[ad] = share * 10 + 0.001 * pm
        jurados.append(jurado_sellado("OF-CAL", f"t{t:02d}", filas, "2026-11-10T07:00:00Z", votos, rub if rubrica != "ninguna" else None))
    return jurados, metricas
