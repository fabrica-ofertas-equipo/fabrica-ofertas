"""Hechos, reglas de alerta y semáforo «¿me puedo ausentar?» sobre raíces temporales (sin red, sin claves, sin tocar archivos reales)."""
from __future__ import annotations

import datetime as _dt
import json
import unittest

from scripts.alertas import hechos as H
from scripts.alertas.reglas import CATALOGO, REGLAS_PENDIENTES, REGLAS_PROPIAS, calcular_alertas, comando_firmar
from scripts.alertas.semaforo import calcular_semaforo
from scripts.validar_esquemas import errores_de_esquema, problemas_alertas, problemas_artefacto
from tests.alertas.ayudas import AHORA, Base, ITEMS_BUENOS, LIMITES_COMPLETOS, LIMITES_VACIOS, PARAMETROS, estado_infra, item


def por_id(alertas):
    return {a.fila["id"]: a for a in alertas}


class PruebaHechos(Base):
    def test_proyecto_vacio_no_lanza_y_todo_es_sin_dato(self) -> None:
        h = H.leer_hechos(self.ctx())
        self.assertIs(h["pausa"]["activa"], False)
        self.assertIsNone(h["freno_captura"])
        self.assertIs(h["preflight"]["existe"], False)
        self.assertIs(h["limites"]["legible"], False)
        self.assertEqual((h["canales"]["n"], h["planificador"]["existe"]), (0, False))
        self.assertEqual(h["ofertas"]["n_reales"], 0)
        self.assertIs(h["ventas"]["hay_datos"], False)
        self.assertEqual(h["ventas"]["fecha"], "2026-11-06", "por defecto, AYER: el último día cerrado")
        self.assertIsNone(h["umbrales"]["preflight_vigencia_h"], "sin parametros.yaml no hay umbral: fail-closed")

    def test_los_umbrales_salen_de_parametros_y_no_del_codigo(self) -> None:
        self.poner("empresa/parametros.yaml", PARAMETROS)
        h = H.leer_hechos(self.ctx())
        self.assertEqual(h["umbrales"], {"preflight_vigencia_h": 6, "latido_max_min": 30})
        self.poner("empresa/parametros.yaml", PARAMETROS.replace("{valor: 6,", "{valor: null,"))
        self.assertIsNone(H.leer_hechos(self.ctx())["umbrales"]["preflight_vigencia_h"])

    def test_archivos_corruptos_o_hostiles_no_tumban_las_demas_lecturas(self) -> None:
        self.poner("empresa/limites.yaml", "a: [sin cerrar\n  - {")
        self.poner("empresa/parametros.yaml", b"\xff\xfe\x00 no es yaml")
        self.poner("empresa/infra/estado.json", "{no es json")
        self.poner("empresa/panel/pulido.jsonl", "basura\n{\"id\": 5}\n[1,2]\n")
        self.poner("empresa/avisos.yaml", "canales: 5\n")
        self.poner("empresa/infra/latidos.json", "[1,2,3]")
        h = H.leer_hechos(self.ctx())
        self.assertIs(h["limites"]["legible"], False)
        self.assertIs(h["preflight"]["existe"], False)
        self.assertEqual(h["canales"]["n"], 0)
        self.assertEqual(h["pulido"]["abiertos"], [])

    def test_pausa_y_freno_se_leen_como_el_panel(self) -> None:
        self.poner("empresa/PAUSA", {"ts": "2026-11-07T01:00:00Z", "motivo": "x" * 900, "origen": "panel"})
        self.poner("empresa/captura/freno.json", {"ts": "2026-11-06T06:03:43Z", "motivo": "HTTP 403"})
        h = H.leer_hechos(self.ctx())
        self.assertIs(h["pausa"]["activa"], True)
        self.assertLessEqual(len(h["pausa"]["motivo"]), 300)
        self.assertEqual(h["freno_captura"]["motivo"], "HTTP 403")

    def test_limites_nulos_que_bloquean_y_sello(self) -> None:
        self.poner("empresa/limites.yaml", LIMITES_VACIOS)
        lim = H.leer_hechos(self.ctx())["limites"]
        self.assertEqual(sorted(lim["bloquean"]), ["capital_en_riesgo_total", "gasto_diario_global", "moneda_limites", "perdida_neta_acumulada_max"])
        self.assertNotIn("nivel_max_lanzable", lim["bloquean"], "null en las claves de riesgo 1.3.0 = solo verde, no es un dato faltante")
        self.assertNotIn("sello", lim["bloquean"], "el sello se cuenta aparte")
        self.assertIs(lim["sello"], False)
        self.poner("empresa/limites.yaml", LIMITES_COMPLETOS)
        lim = H.leer_hechos(self.ctx())["limites"]
        self.assertEqual((lim["n_bloquean"], lim["sello"], lim["cuentas_permitidas"]), (0, True, ["act_1234"]))

    def test_propuesta_de_limites_cambia_a_quien_le_toca(self) -> None:
        self.poner("empresa/limites.yaml", LIMITES_VACIOS)
        self.assertIs(H.leer_hechos(self.ctx())["limites"]["propuesta"], False)
        self.poner("empresa/propuestas/limites.propuesta.yaml", "grupos:\n  limites:\n    gasto_diario_global: 30000\n")
        self.assertIs(H.leer_hechos(self.ctx())["limites"]["propuesta"], True)

    def test_preflight_cuenta_items_edad_y_criticos_rojos(self) -> None:
        self.poner("empresa/parametros.yaml", PARAMETROS)
        self.poner("empresa/infra/estado.json", estado_infra("ROJO", items=[item("M-02", "ROJO"), item("S-01", "VERDE"), item("R-04", "ROJO", critico=False), item("K-01", "PENDIENTE")]))
        p = H.leer_hechos(self.ctx())["preflight"]
        self.assertEqual((p["conteo"]["ROJO"], p["conteo"]["VERDE"], p["conteo"]["PENDIENTE"]), (2, 1, 1))
        self.assertEqual(p["criticos_rojos"], ["M-02"])
        self.assertEqual(p["edad_h"], 1)

    def test_canales_cuentan_tipos_distintos_y_solo_los_probados(self) -> None:
        self.poner("empresa/avisos.yaml", "canales:\n  - {tipo: telegram, estado: probado}\n  - {tipo: Telegram}\n  - correo\n  - {tipo: ''}\n  - 5\n")
        c = H.leer_hechos(self.ctx())["canales"]
        self.assertEqual((c["tipos"], c["n"], c["n_probados"]), (["correo", "telegram"], 2, 1))
        self.poner("empresa/avisos.yaml", "canal: telegram\ncanal_respaldo: correo\n")
        self.assertEqual(H.leer_hechos(self.ctx())["canales"]["n"], 2)

    def test_latidos_vencidos_y_sin_fecha(self) -> None:
        self.poner("empresa/parametros.yaml", PARAMETROS)
        self.poner("empresa/infra/latidos.json", {"trabajos": [{"id": "a", "ultimo_latido": "2026-11-07T08:20:00Z"}, {"id": "b", "ultimo_latido": "2026-11-07T07:00:00Z"},
                                                            {"id": "c", "ultimo_latido": "no es fecha"}, {"id": "d", "ultimo_latido": "2026-11-07T08:00:00Z", "latido_max_min": 5}]})
        p = H.leer_hechos(self.ctx())["planificador"]
        self.assertEqual((p["n"], p["vencidos"], p["sin_latido"]), (4, 3, 1))
        self.assertEqual([t["vencido"] for t in p["trabajos"]], [False, True, True, True])

    def test_pendientes_del_dueno_se_pliegan_y_los_vencidos_se_marcan(self) -> None:
        filas = [
            {"id": "PUL-0001", "ts": "2026-11-01T00:00:00Z", "evento": "alta", "titulo": "Primero", "responsable": "dueno", "prioridad": "P1", "estado": "abierta", "vence": "2026-11-06"},
            {"id": "PUL-0002", "ts": "2026-11-01T00:00:00Z", "evento": "alta", "titulo": "Resuelto", "responsable": "dueno", "prioridad": "P0", "estado": "abierta"},
            {"id": "PUL-0002", "ts": "2026-11-02T00:00:00Z", "evento": "estado", "estado": "resuelta"},
            {"id": "PUL-0003", "ts": "2026-11-01T00:00:00Z", "evento": "alta", "titulo": "De la IA", "responsable": "ia", "prioridad": "P0", "estado": "abierta"},
            {"id": "PUL-0004", "ts": "2026-11-01T00:00:00Z", "evento": "alta", "titulo": "Sin fecha", "responsable": "dueno", "prioridad": "P0", "estado": "abierta", "vence": "2026-11-07"},
            {"id": "PUL-0005", "ts": "2026-11-01T00:00:00Z", "evento": "alta", "titulo": "Nota suelta", "estado": "abierta"},
        ]
        self.jsonl("empresa/panel/pulido.jsonl", filas)
        p = H.leer_hechos(self.ctx())["pulido"]
        self.assertEqual([x["id"] for x in p["abiertos"]], ["PUL-0004", "PUL-0001"], "solo del dueño y abiertos, P0 antes que P1")
        self.assertEqual({x["id"]: x["vencido"] for x in p["abiertos"]}, {"PUL-0001": True, "PUL-0004": False}, "una fecha sin hora vence al terminar ese día")

    def test_el_texto_de_los_archivos_es_dato_se_limpia(self) -> None:
        self.jsonl("empresa/panel/pulido.jsonl", [{"id": "PUL-0001", "evento": "alta", "titulo": "Mira https://malo.example/x?a=1 y www.otro.com ‮gnp.exe\x07 fin", "responsable": "dueno", "prioridad": "P0"}])
        t = H.leer_hechos(self.ctx())["pulido"]["abiertos"][0]["titulo"]
        self.assertNotIn("http", t)
        self.assertNotIn("www", t)
        self.assertNotIn("‮", t)
        self.assertNotIn("\x07", t)
        self.assertEqual(H.limpiar_texto("a" * 500, 50)[-1], "…")
        self.assertEqual(H.limpiar_texto(None), "")
        self.assertEqual(H.limpiar_texto(123), "")

    def test_ventas_solo_con_datos_reales_y_sin_inventar_ceros(self) -> None:
        self.oferta("OF-202611-91")
        self.assertEqual(H.leer_hechos(self.ctx())["ventas"]["hay_datos"], False)
        kpi = {"filas": [{"kpi_id": "gasto_meta", "valor": 2760, "unidad": "EUR_minor"}, {"kpi_id": "compras_stripe", "valor": 2, "unidad": "compras"},
                         {"kpi_id": "cpa", "valor": 1380, "unidad": "EUR_minor"}, {"kpi_id": "ctr_enlace", "valor": "1.60", "unidad": "porcentaje"}]}
        self.poner("ofertas/OF-202611-91/08-operacion/diario/2026-11-06/kpi_oferta_dia.json", kpi)
        v = H.leer_hechos(self.ctx())["ventas"]
        self.assertEqual((v["hay_datos"], v["compras"], v["gasto"]), (True, 2, [{"monto": 2760, "moneda": "EUR"}]))
        self.assertEqual(H.leer_hechos(self.ctx(), fecha_ventas="2026-11-05")["ventas"]["hay_datos"], False, "otro día, sin archivo: sin dato (no un 0)")

    def test_la_oferta_demo_no_cuenta_y_los_gates_son_de_ofertas_reales(self) -> None:
        self.oferta("_ejemplo", gate="D7")
        self.oferta("OF-202611-91", gate="D2")
        o = H.leer_hechos(self.ctx())["ofertas"]
        self.assertEqual((o["n_reales"], o["n_demo"]), (1, 1))
        self.assertEqual([(g["oferta_id"], g["etapa"]) for g in o["gates"]], [("OF-202611-91", "D2")])

    def test_hora_y_fecha_utilidades(self) -> None:
        self.assertIsNone(H.parsear_z("no"))
        self.assertIsNone(H.parsear_z(None))
        self.assertIsNone(H.parsear_z("2026-11-07T08:30:00Z" * 5))
        self.assertEqual(H.iso_z(H.parsear_z("2026-11-07T10:30:00+02:00")), "2026-11-07T08:30:00Z")
        self.assertEqual(H.horas_entre(H.parsear_z("2026-11-07T04:00:00Z"), AHORA), 4)
        self.assertEqual(H.horas_entre(H.parsear_z("2026-11-08T04:00:00Z"), AHORA), 0, "nunca negativo")
        self.assertIsNone(H.horas_entre(None, AHORA))


class PruebaReglas(Base):
    def test_proyecto_vacio_alertas_esperadas_y_todas_cumplen_el_esquema(self) -> None:
        al = por_id(calcular_alertas(H.leer_hechos(self.ctx())))
        self.assertEqual(sorted(al), ["F2-A16:chequeo", "F2-AUS-CANAL:empresa", "F2-AUS-CORREO:empresa", "F2-AUS-LIM:empresa", "F2-AUS-META:empresa", "F2-AUS-PLAN:planificador"])
        for a in al.values():
            self.assertEqual(list(errores_de_esquema("alertas", a.fila)), [], a.fila["id"])
            self.assertEqual(problemas_artefacto("alertas", a.fila), [])
            self.assertLessEqual(len(a.fila["accion_sugerida"]), 300)
            self.assertTrue(a.fila["accion_sugerida"].split(":")[0] in ("Te toca a ti", "Le toca al equipo técnico (S-B)", "Le toca al equipo de contratos y documentos (S-A)"), "dice a quién le toca")
        self.assertEqual(problemas_alertas([a.fila for a in al.values()]), [])
        self.assertEqual(al["F2-A16:chequeo"].fila["severidad"], "roja")
        self.assertEqual((al["F2-AUS-LIM:empresa"].fila["severidad"], al["F2-AUS-LIM:empresa"].extra["responsable"]), ("roja", "S-A"), "sin archivo de límites: fail-closed")
        self.assertIsNone(al["F2-AUS-META:empresa"].fila["oferta_id"])

    def test_ningun_valor_es_float_y_el_texto_no_copia_archivos(self) -> None:
        self.poner("empresa/PAUSA", {"motivo": "https://malo.example/<script>alert(1)</script>"})
        self.jsonl("empresa/panel/pulido.jsonl", [{"id": "PUL-0001", "evento": "alta", "titulo": "TITULO-SECRETO-ABC", "responsable": "dueno", "prioridad": "P0", "vence": "2026-01-01"}])
        for a in calcular_alertas(H.leer_hechos(self.ctx())):
            for k in ("valor", "umbral"):
                self.assertNotIsInstance(a.fila[k], float, a.fila["id"])
            self.assertNotIn("malo.example", a.fila["accion_sugerida"])
            self.assertNotIn("TITULO-SECRETO-ABC", a.fila["accion_sugerida"], "los títulos del archivo viajan aparte (extra), nunca en la acción del archivo de alertas")
        self.assertEqual(sorted(CATALOGO), sorted(REGLAS_PROPIAS))

    def test_pausa_y_freno(self) -> None:
        self.poner("empresa/PAUSA", {"ts": "2026-11-07T01:00:00Z", "motivo": "prueba"})
        self.poner("empresa/captura/freno.json", {"ts": "2026-11-06T06:03:43Z", "motivo": "HTTP 403"})
        al = por_id(calcular_alertas(H.leer_hechos(self.ctx())))
        self.assertEqual(al["F2-AUS-PAUSA:empresa"].fila["severidad"], "roja")
        self.assertEqual(al["F2-AUS-PAUSA:empresa"].extra["comando"], "rm empresa/PAUSA")
        self.assertEqual(al["F2-AUS-PAUSA:empresa"].extra["detalle"], "prueba")
        self.assertEqual(al["F2-AUS-FRENO:captura"].fila["severidad"], "amarilla")
        self.assertEqual(al["F2-AUS-FRENO:captura"].extra["responsable"], "dueno")

    def test_limites_vacios_dependen_de_quien_prepara_la_propuesta(self) -> None:
        self.poner("empresa/limites.yaml", LIMITES_VACIOS)
        al = por_id(calcular_alertas(H.leer_hechos(self.ctx())))
        self.assertEqual((al["F2-AUS-LIM:empresa"].fila["severidad"], al["F2-AUS-LIM:empresa"].extra["responsable"], al["F2-AUS-LIM:empresa"].fila["valor"]), ("roja", "S-B", 4),
                         "J4 sin fijar (300 por día y −3.000) es rojo y, sin propuesta, le toca al equipo técnico")
        self.assertEqual(al["F2-AUS-SELLO:empresa"].fila["severidad"], "amarilla", "primero se completa, después se firma")
        self.assertIn("300 USD por día", al["F2-AUS-LIM:empresa"].fila["accion_sugerida"])
        self.assertEqual(al["F2-AUS-LIM:empresa"].extra["medida"], "4 límites sin fijar")
        self.poner("empresa/propuestas/limites.propuesta.yaml", "grupos: {}\n")
        al = por_id(calcular_alertas(H.leer_hechos(self.ctx())))
        self.assertEqual(al["F2-AUS-LIM:empresa"].extra["responsable"], "dueno")

    def test_limites_completos_pero_sin_firma_es_rojo(self) -> None:
        self.poner("empresa/limites.yaml", LIMITES_COMPLETOS.replace("sello: {hash: \"sha256:aa\", firma: \"ed25519:bb\", clave_id: k1}", "sello: null"))
        al = por_id(calcular_alertas(H.leer_hechos(self.ctx())))
        self.assertNotIn("F2-AUS-LIM:empresa", al)
        self.assertEqual(al["F2-AUS-SELLO:empresa"].fila["severidad"], "roja")
        self.assertIn("engine.propuestas sellar", al["F2-AUS-SELLO:empresa"].extra["comando"])

    def test_limites_ilegibles_es_rojo_y_fail_closed(self) -> None:
        self.poner("empresa/limites.yaml", "{roto")
        a = por_id(calcular_alertas(H.leer_hechos(self.ctx())))["F2-AUS-LIM:empresa"]
        self.assertEqual((a.fila["severidad"], a.extra["responsable"]), ("roja", "S-A"))

    def test_chequeo_cada_caso(self) -> None:
        def sev(estado):
            self.poner("empresa/parametros.yaml", PARAMETROS)
            self.poner("empresa/infra/estado.json", estado)
            a = por_id(calcular_alertas(H.leer_hechos(self.ctx()))).get("F2-A16:chequeo")
            return None if a is None else (a.fila["severidad"], a.fila["valor"], a.fila["umbral"])
        self.assertEqual(sev(estado_infra("ROJO", items=[item("M-02", "ROJO"), item("S-01", "ROJO")])), ("roja", 2, 0))
        self.assertEqual(sev(estado_infra("AMARILLO"))[0], "amarilla")
        self.assertEqual(sev(estado_infra("VERDE", modo="prueba"))[0], "amarilla", "un chequeo de prueba no sirve para gastar")
        self.assertEqual(sev(estado_infra("VERDE", generado_en="2026-11-07T01:00:00Z")), ("amarilla", 7, 6), "vencido: 7 h > 6 h")
        self.assertIsNone(sev(estado_infra("VERDE", generado_en="2026-11-07T07:30:00Z")), "verde, real y reciente: sin alerta")

    def test_chequeo_sin_vigencia_en_parametros_no_se_da_por_bueno(self) -> None:
        self.poner("empresa/infra/estado.json", estado_infra("VERDE"))
        a = por_id(calcular_alertas(H.leer_hechos(self.ctx())))["F2-A16:chequeo"]
        self.assertEqual((a.fila["severidad"], a.fila["umbral"]), ("amarilla", None), "sin umbral fijado: gris, nunca verde")

    def test_canal_cero_uno_y_dos_sin_probar(self) -> None:
        def canal(yaml):
            if yaml is not None:
                self.poner("empresa/avisos.yaml", yaml)
            a = por_id(calcular_alertas(H.leer_hechos(self.ctx()))).get("F2-AUS-CANAL:empresa")
            return None if a is None else (a.fila["severidad"], a.fila["valor"], a.fila["umbral"], a.extra["responsable"])
        self.assertEqual(canal(None), ("roja", 0, 2, "dueno"))
        self.assertEqual(canal("canales: [telegram]\n"), ("amarilla", 1, 2, "dueno"))
        self.assertEqual(canal("canales: [telegram, correo]\n"), ("amarilla", 0, 2, "S-B"))
        self.assertIsNone(canal("canales:\n  - {tipo: telegram, estado: probado}\n  - {tipo: correo, probado: true}\n"))

    def test_planificador_y_latidos(self) -> None:
        self.poner("empresa/parametros.yaml", PARAMETROS)
        a = por_id(calcular_alertas(H.leer_hechos(self.ctx())))["F2-AUS-PLAN:planificador"]
        self.assertEqual((a.fila["severidad"], a.extra["responsable"]), ("amarilla", "dueno"))
        self.poner("empresa/infra/latidos.json", {"trabajos": [{"id": "a", "ultimo_latido": "2026-11-07T06:00:00Z"}, {"id": "b", "ultimo_latido": "2026-11-07T08:29:00Z"}]})
        al = por_id(calcular_alertas(H.leer_hechos(self.ctx())))
        self.assertNotIn("F2-AUS-PLAN:planificador", al)
        self.assertEqual((al["F2-A17:latidos"].fila["severidad"], al["F2-A17:latidos"].fila["valor"], al["F2-A17:latidos"].fila["umbral"]), ("roja", 150, 30), "valor = minutos del peor; umbral = latido_max_min")
        self.assertEqual(al["F2-A17:latidos"].extra["medida"], "1 de 2 sin señal; el peor, hace 150 min")

    def test_meta_correo_y_saldo_segun_el_chequeo(self) -> None:
        self.base_sana()
        self.assertEqual(sorted(por_id(calcular_alertas(H.leer_hechos(self.ctx())))), [], "todo en orden: ninguna alerta")
        self.poner("empresa/infra/estado.json", estado_infra("AMARILLO", items=[item("M-02", "ROJO"), item("M-03", "AMARILLO"), item("E-01", "ROJO")]))
        al = por_id(calcular_alertas(H.leer_hechos(self.ctx())))
        for k in ("F2-AUS-META:empresa", "F2-AUS-CORREO:empresa", "F2-AUS-SALDO:meta"):
            self.assertEqual(al[k].fila["severidad"], "amarilla", k)

    def test_con_ventas_en_curso_lo_que_falta_para_vender_es_rojo(self) -> None:
        self.base_sana()
        self.poner("empresa/infra/estado.json", estado_infra("VERDE", items=[item("M-02"), item("M-03", "ROJO")]))
        self.oferta("OF-202611-91", fase="en_test")
        al = por_id(calcular_alertas(H.leer_hechos(self.ctx())))
        self.assertEqual((al["F2-AUS-CORREO:empresa"].fila["severidad"], al["F2-AUS-SALDO:meta"].fila["severidad"]), ("roja", "roja"))

    def test_firmas_que_esperan_traen_su_comando_y_enlace(self) -> None:
        self.base_sana()
        self.oferta("OF-202611-91", gate="D2")
        self.oferta("_ejemplo", gate="D7")
        al = por_id(calcular_alertas(H.leer_hechos(self.ctx())))
        a = al["F2-AUS-GATE:OF-202611-91:D2"]
        self.assertNotIn("F2-AUS-GATE:_ejemplo:D7", al, "la demo no cuenta")
        self.assertEqual((a.fila["oferta_id"], a.fila["severidad"], a.fila["valor"], a.extra["enlace"]), ("OF-202611-91", "amarilla", 24, "#/oferta/OF-202611-91"))
        self.assertIn("--etapa D2", a.extra["comando"])
        self.assertIn("--oferta OF-202611-91", a.extra["comando"])
        self.assertIsNone(comando_firmar("OF-1; rm -rf /", "D2"))
        self.assertIsNone(comando_firmar("OF-202611-91", "D2 && x"))
        self.assertIsNone(comando_firmar("OF-202611-91", "d2"))

    def test_pendientes_vencidos_p0_rojo_y_otros_amarillo_sin_titulo_en_el_archivo(self) -> None:
        self.base_sana()
        self.jsonl("empresa/panel/pulido.jsonl", [
            {"id": "PUL-0001", "evento": "alta", "titulo": "Importante", "responsable": "dueno", "prioridad": "P0", "vence": "2026-11-01"},
            {"id": "PUL-0002", "evento": "alta", "titulo": "Menos", "responsable": "dueno", "prioridad": "P2", "vence": "2026-11-05T10:00:00Z"},
            {"id": "PUL-0003", "evento": "alta", "titulo": "Futuro", "responsable": "dueno", "prioridad": "P0", "vence": "2026-12-01"}])
        al = por_id(calcular_alertas(H.leer_hechos(self.ctx())))
        self.assertEqual(sorted(al), ["F2-AUS-VENCE:PUL-0001", "F2-AUS-VENCE:PUL-0002"])
        self.assertEqual((al["F2-AUS-VENCE:PUL-0001"].fila["severidad"], al["F2-AUS-VENCE:PUL-0001"].fila["valor"]), ("roja", 5), "cinco días completos después del fin del día de vencimiento")
        self.assertEqual(al["F2-AUS-VENCE:PUL-0002"].fila["severidad"], "amarilla")
        self.assertEqual(al["F2-AUS-VENCE:PUL-0001"].extra["detalle"], "Importante")
        self.assertNotIn("Importante", al["F2-AUS-VENCE:PUL-0001"].fila["accion_sugerida"])

    def test_determinista_y_las_pendientes_estan_documentadas(self) -> None:
        h = H.leer_hechos(self.ctx())
        self.assertEqual([a.fila for a in calcular_alertas(h)], [a.fila for a in calcular_alertas(h)])
        self.assertEqual([r["regla_id"] for r in REGLAS_PENDIENTES], [f"F2-A{n:02d}" for n in range(1, 16)], "F2-A01…A15 quedan como TODO con su dato requerido")
        for r in REGLAS_PENDIENTES:
            self.assertTrue(r["requiere"] and r["archivo"] and r["de"] in ("S-A", "S-B"), r["regla_id"])


class PruebaSemaforo(Base):
    def test_hoy_es_rojo_con_los_pasos_en_orden_y_a_quien_le_toca(self) -> None:
        self.poner("empresa/parametros.yaml", PARAMETROS)
        self.poner("empresa/limites.yaml", LIMITES_VACIOS)
        self.poner("empresa/captura/freno.json", {"ts": "2026-11-06T06:03:43Z", "motivo": "HTTP 403"})
        s = calcular_semaforo(H.leer_hechos(self.ctx()))
        self.assertEqual(s["nivel"], "rojo")
        self.assertEqual(s["titulo"], "Todavía no te puedes ausentar")
        self.assertEqual(s["conteos"], {"rojo": 4, "amarillo": 4, "verde": 2})
        self.assertEqual([p["id"] for p in s["pasos"]], ["limites", "chequeo", "canal", "planificador", "pausa", "meta", "correo", "saldo"], "primero lo rojo, y dentro de cada color el orden de importancia")
        self.assertEqual([p["paso"] for p in s["pasos"]], list(range(1, 9)))
        quien = {p["id"]: p["responsable"] for p in s["pasos"]}
        self.assertEqual(quien["limites"], "S-B")
        self.assertEqual(quien["canal"], "dueno")
        self.assertEqual(s["para_ti"], sum(1 for p in s["pasos"] if p["responsable"] == "dueno"))
        for p in s["comprobaciones"]:
            self.assertIn(p["nivel"], ("rojo", "amarillo", "verde"))
            self.assertTrue(p["estado"] and p["que_hacer"] and p["responsable_texto"] and p["enlace"].startswith("#/"), p["id"])

    def test_todo_en_orden_es_verde(self) -> None:
        self.base_sana()
        s = calcular_semaforo(H.leer_hechos(self.ctx()))
        self.assertEqual((s["nivel"], s["faltan"], s["pasos"]), ("verde", 0, []))
        self.assertEqual(s["titulo"], "Sí, te puedes ausentar")

    def test_solo_firmas_pendientes_es_amarillo_y_avisa_de_ofertas_sin_registro(self) -> None:
        self.base_sana()
        self.oferta("OF-202611-91", gate="D3")
        self.oferta("OF-202611-92", estado=False)
        s = calcular_semaforo(H.leer_hechos(self.ctx()))
        self.assertEqual((s["nivel"], [p["id"] for p in s["pasos"]]), ("amarillo", ["firmas"]))
        self.assertIn("1 oferta hecha a mano", s["pasos"][0]["nota"])
        self.assertIn("--etapa D3", s["pasos"][0]["comando"])

    def test_limites_firmados_distintos_de_lo_decidido_son_amarillo(self) -> None:
        self.base_sana()
        self.poner("empresa/limites.yaml", LIMITES_COMPLETOS.replace("gasto_diario_global: 30000", "gasto_diario_global: 50000"))
        s = calcular_semaforo(H.leer_hechos(self.ctx()))
        self.assertEqual({c["id"]: c["nivel"] for c in s["comprobaciones"]}["limites"], "amarillo")

    def test_pausa_puesta_es_rojo(self) -> None:
        self.base_sana()
        self.poner("empresa/PAUSA", {"motivo": "x"})
        s = calcular_semaforo(H.leer_hechos(self.ctx()))
        self.assertEqual((s["nivel"], s["pasos"][0]["id"], s["pasos"][0]["comando"]), ("rojo", "pausa", "rm empresa/PAUSA"))

    def test_chequeo_en_rojo_y_planificador_con_trabajos_caidos(self) -> None:
        self.base_sana()
        self.poner("empresa/infra/estado.json", estado_infra("ROJO", items=[item("M-02", "ROJO")]))
        self.poner("empresa/infra/latidos.json", {"trabajos": [{"id": "a", "ultimo_latido": "2026-11-07T01:00:00Z"}]})
        c = {x["id"]: x for x in calcular_semaforo(H.leer_hechos(self.ctx()))["comprobaciones"]}
        self.assertEqual((c["chequeo"]["nivel"], c["planificador"]["nivel"], c["planificador"]["responsable"]), ("rojo", "rojo", "S-B"))

    def test_dos_canales_sin_probar_es_amarillo_y_un_canal_tambien(self) -> None:
        self.base_sana()
        self.poner("empresa/avisos.yaml", "canales: [telegram, correo]\n")
        self.assertEqual({c["id"]: c["nivel"] for c in calcular_semaforo(H.leer_hechos(self.ctx()))["comprobaciones"]}["canal"], "amarillo")
        self.poner("empresa/avisos.yaml", "canales: [telegram]\n")
        self.assertEqual({c["id"]: c["nivel"] for c in calcular_semaforo(H.leer_hechos(self.ctx()))["comprobaciones"]}["canal"], "amarillo")

    def test_con_ventas_en_curso_lo_que_falta_para_vender_pasa_a_rojo(self) -> None:
        self.base_sana()
        self.poner("empresa/infra/estado.json", estado_infra("VERDE", items=[item("M-02"), item("M-03")]))     # sin E-01
        self.oferta("OF-202611-91", fase="escalando")
        s = calcular_semaforo(H.leer_hechos(self.ctx()))
        self.assertEqual({c["id"]: c["nivel"] for c in s["comprobaciones"]}["correo"], "rojo")
        self.assertEqual(s["nivel"], "rojo")

    def test_sin_dato_nunca_es_verde(self) -> None:
        s = calcular_semaforo(H.leer_hechos(self.ctx()))
        self.assertEqual([c["id"] for c in s["comprobaciones"] if c["nivel"] == "verde"], ["pausa", "firmas", "vigilancia"], "sin ningún archivo solo son verdes «sin PAUSA ni freno», «sin firmas» y «no hay ofertas vendiendo que vigilar»: lo demás es falta")

    def test_vigilancia_del_gasto_y_las_ventas(self) -> None:
        self.base_sana()
        graves = {"naranja": {"schema_version": "1.0.0", "id": "F1-A02:OF-202611-91", "ts": "2026-11-07T08:00:00Z", "severidad": "naranja", "regla_id": "F1-A02", "origen": "F1", "estado": "abierta", "accion_sugerida": "Pausar"}}
        sin_ventas = {c["id"]: c for c in calcular_semaforo(H.leer_hechos(self.ctx()))["comprobaciones"]}["vigilancia"]
        self.assertEqual(sin_ventas["nivel"], "verde", "sin ofertas vendiendo no hay gasto que vigilar")
        con_grave = {c["id"]: c for c in calcular_semaforo(H.leer_hechos(self.ctx()), [{**graves["naranja"], "oferta_id": None}])["comprobaciones"]}["vigilancia"]
        self.assertEqual((con_grave["nivel"], con_grave["responsable"], con_grave["enlace"]), ("rojo", "dueno", "#/avisos"))
        cerrada = {**graves["naranja"], "estado": "cerrada", "oferta_id": None}
        self.oferta("OF-202611-91", fase="en_test")
        sin_reglas = calcular_semaforo(H.leer_hechos(self.ctx()))
        v = {c["id"]: c for c in sin_reglas["comprobaciones"]}["vigilancia"]
        self.assertEqual((v["nivel"], v["responsable"]), ("amarillo", "S-B"), "ya hay ofertas vendiendo y nadie calcula las reglas de gasto y ventas")
        self.assertEqual(sin_reglas["nivel"], "amarillo")
        con_reglas = calcular_semaforo(H.leer_hechos(self.ctx()), [cerrada])
        self.assertEqual({c["id"]: c for c in con_reglas["comprobaciones"]}["vigilancia"]["nivel"], "verde", "las reglas corren (dejaron una línea, aunque esté cerrada) y no hay graves")
        self.assertEqual(con_reglas["nivel"], "verde")

    def test_el_semaforo_no_escribe_nada(self) -> None:
        antes = self.hash_arbol()
        calcular_semaforo(H.leer_hechos(self.ctx()))
        calcular_alertas(H.leer_hechos(self.ctx()))
        self.assertEqual(self.hash_arbol(), antes)
        self.assertEqual(json.loads(json.dumps(calcular_semaforo(H.leer_hechos(self.ctx())))), calcular_semaforo(H.leer_hechos(self.ctx())), "es JSON puro")


if __name__ == "__main__":
    unittest.main()
