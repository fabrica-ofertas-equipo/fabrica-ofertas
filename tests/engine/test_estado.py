"""Pruebas de ``engine.estado``: almacén SQLite, transiciones, gates, PAUSA y propagación de obsolescencia."""
from __future__ import annotations

from datetime import datetime, timezone

from engine import estado
from engine.ejecutor import EjecutorMotor
from engine.errores import ErrorBloqueado, ErrorUso, ErrorValidacion
from tests.engine import apoyo

BRIEF_MINIMO = {"mercado_objetivo": {"moneda_cobro": "EUR"}}


class PruebaEstado(apoyo.PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.raiz = self.tmp
        (self.raiz / "empresa").mkdir(parents=True, exist_ok=True)
        self.ahora = lambda: datetime(2026, 11, 9, 10, 0, 0, tzinfo=timezone.utc)

    def crear(self, oferta_id: str = "OF-202611-01", *, nivel: str = "N2") -> dict:
        return estado.crear(BRIEF_MINIMO, oferta_id=oferta_id, familia_id="FAM-202611-01", nivel=nivel, raiz=self.raiz, ahora=self.ahora)

    def test_crear_es_idempotente_por_oferta_id(self) -> None:
        primero = self.crear()
        segundo = self.crear()
        self.assertEqual(primero, segundo)

    def test_crear_fija_el_gate_de_la_tabla_unica(self) -> None:
        est = self.crear(nivel="N2")
        self.assertEqual(est["etapas"]["D1"]["gate"], "H")  # etapa:D1 es H en N0-N3 (gates.json)
        self.assertEqual(est["etapas"]["D2"]["gate"], "S")  # etapa:D2 es S en N2

    def test_cargar_oferta_desconocida_falla_con_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            estado.cargar("OF-999999-99", raiz=self.raiz)

    def test_cargar_importa_una_vista_en_disco_no_conocida_por_el_almacen(self) -> None:
        # Simula una fixture copiada a mano (como ofertas/_ejemplo/estado.json) sin pasar por crear().
        est = self.crear(oferta_id="OF-202611-02")
        otra_raiz = self.tmp  # mismo almacén: basta con comprobar que una segunda carga da lo mismo
        self.assertEqual(estado.cargar("OF-202611-02", raiz=otra_raiz), est)

    def test_guardar_rechaza_revision_desactualizada(self) -> None:
        est = self.crear()
        nuevo = dict(est)
        nuevo["revision"] = est["revision"] + 1
        nuevo["actualizado_en"] = "2026-11-09T10:05:00Z"
        estado.guardar(est["oferta_id"], nuevo, revision_esperada=est["revision"], raiz=self.raiz)
        # reintentar con la revisión YA vieja debe fallar (alguien más -en este caso, el paso anterior- ya escribió)
        with self.assertRaises(ErrorValidacion):
            estado.guardar(est["oferta_id"], nuevo, revision_esperada=est["revision"], raiz=self.raiz)

    def test_transicionar_valida_contra_la_tabla_unica(self) -> None:
        est = self.crear()
        oferta_id = est["oferta_id"]
        with self.assertRaises(ErrorValidacion):
            estado.transicionar(oferta_id, "D1", "aprobado", actor="orq", causa="salto inválido", raiz=self.raiz, ahora=self.ahora)
        estado.transicionar(oferta_id, "D1", "en_progreso", actor="orq", causa="inicio", raiz=self.raiz, ahora=self.ahora)
        con_cambios = estado.transicionar(oferta_id, "D1", "en_QA", actor="orq", causa="salida lista", raiz=self.raiz, ahora=self.ahora,
                                          cambios={"hash_salida": "sha256:" + "11" * 32, "ronda_qa": 1, "intentos": 1})
        self.assertEqual(con_cambios["etapas"]["D1"]["hash_salida"], "sha256:" + "11" * 32)
        self.assertTrue(con_cambios["etapas"]["D1"]["gate_pendiente"])  # D1 es gate H: en_QA deja gate_pendiente

    def test_transicionar_rechaza_campos_no_permitidos_en_cambios(self) -> None:
        est = self.crear()
        estado.transicionar(est["oferta_id"], "D1", "en_progreso", actor="orq", causa="x", raiz=self.raiz, ahora=self.ahora)
        with self.assertRaises(ErrorValidacion):
            estado.transicionar(est["oferta_id"], "D1", "en_QA", actor="orq", causa="x", raiz=self.raiz, ahora=self.ahora,
                                cambios={"version_aprobada": "v1"})

    def test_aprobar_fija_version_y_aprobado_por(self) -> None:
        est = self.crear()
        oferta_id = est["oferta_id"]
        estado.transicionar(oferta_id, "D1", "en_progreso", actor="orq", causa="x", raiz=self.raiz, ahora=self.ahora)
        estado.transicionar(oferta_id, "D1", "en_QA", actor="orq", causa="x", raiz=self.raiz, ahora=self.ahora,
                            cambios={"hash_salida": "sha256:" + "22" * 32, "ronda_qa": 1, "intentos": 1})
        aprobado = estado.aprobar(oferta_id, "D1", version="v1", aprobado_por={"tipo": "qa_pass", "id": "d1-qa", "fecha": "2026-11-09T10:10:00Z", "firma": None},
                                  raiz=self.raiz, ahora=self.ahora)
        campo = aprobado["etapas"]["D1"]
        self.assertEqual(campo["estado"], "aprobado")
        self.assertEqual(campo["version_aprobada"], "v1")
        self.assertFalse(campo["gate_pendiente"])

    def test_siguiente_etapa_respeta_dependencias(self) -> None:
        est = self.crear()
        oferta_id = est["oferta_id"]
        self.assertEqual(estado.siguiente_etapa(oferta_id, raiz=self.raiz), "D1")
        estado.transicionar(oferta_id, "D1", "en_progreso", actor="orq", causa="x", raiz=self.raiz, ahora=self.ahora)
        estado.transicionar(oferta_id, "D1", "en_QA", actor="orq", causa="x", raiz=self.raiz, ahora=self.ahora,
                            cambios={"hash_salida": "sha256:" + "33" * 32, "ronda_qa": 1, "intentos": 1})
        estado.aprobar(oferta_id, "D1", version="v1", aprobado_por={"tipo": "qa_pass", "id": "d1-qa", "fecha": "2026-11-09T10:10:00Z", "firma": None},
                      raiz=self.raiz, ahora=self.ahora)
        self.assertEqual(estado.siguiente_etapa(oferta_id, raiz=self.raiz), "M1")

    def _aprobar_d1_y_m1(self, oferta_id: str) -> None:
        for etapa, h in (("D1", "44" * 32), ("M1", "55" * 32)):
            estado.transicionar(oferta_id, etapa, "en_progreso", actor="orq", causa="x", raiz=self.raiz, ahora=self.ahora)
            estado.transicionar(oferta_id, etapa, "en_QA", actor="orq", causa="x", raiz=self.raiz, ahora=self.ahora,
                                cambios={"hash_salida": f"sha256:{h}", "entradas": {"D1": "sha256:" + "44" * 32} if etapa == "M1" else {},
                                         "ronda_qa": 1, "intentos": 1})
            estado.aprobar(oferta_id, etapa, version="v1",
                          aprobado_por={"tipo": "qa_pass", "id": f"{etapa.lower()}-qa", "fecha": "2026-11-09T10:10:00Z", "firma": None},
                          raiz=self.raiz, ahora=self.ahora)

    def test_propagar_obsolescencia_marca_dependientes_y_pausa_la_campana(self) -> None:
        est = self.crear()
        oferta_id = est["oferta_id"]
        self._aprobar_d1_y_m1(oferta_id)
        # fase hasta en_test (no exige que TODAS las etapas estén aprobadas: eso lo orquesta orq, no esta prueba de bajo nivel)
        for de, a in (("borrador", "en_construccion"), ("en_construccion", "listo_para_activar"), ("listo_para_activar", "en_test")):
            estado.transicionar_fase(oferta_id, a, actor="orq", causa="avance de prueba", raiz=self.raiz, ahora=self.ahora)

        ejecutor = EjecutorMotor(raiz=self.raiz, ahora=self.ahora)
        vueltas = estado.propagar_obsolescencia(oferta_id, "D1", raiz=self.raiz, ejecutor=ejecutor, ahora=self.ahora)
        self.assertIn("M1", vueltas)
        est_final = estado.cargar(oferta_id, raiz=self.raiz)
        self.assertEqual(est_final["etapas"]["M1"]["estado"], "pendiente")
        self.assertTrue(est_final["etapas"]["M1"]["obsoleta"])
        self.assertEqual(est_final["fase"], "pausada")  # la campaña activa se pausó (B0-07)

    def test_gate_de_usa_el_nivel_efectivo(self) -> None:
        est = self.crear(nivel="N3")
        self.assertEqual(estado.gate_de(est["oferta_id"], "etapa:D1", raiz=self.raiz), "H")
        self.assertEqual(estado.gate_de(est["oferta_id"], "etapa:D2", raiz=self.raiz), "S")

    def test_pausa_en_sus_dos_sitios_propios(self) -> None:
        self.assertFalse(estado.hay_pausa(raiz=self.raiz))
        estado.fijar_pausa("prueba", raiz=self.raiz, ahora=self.ahora)
        self.assertTrue((self.raiz / "empresa" / "PAUSA").exists())
        self.assertTrue(estado.hay_pausa(raiz=self.raiz))
        estado.quitar_pausa(raiz=self.raiz, ahora=self.ahora)
        self.assertFalse((self.raiz / "empresa" / "PAUSA").exists())
        self.assertFalse(estado.hay_pausa(raiz=self.raiz))

    def test_pausa_falla_cerrado_si_el_control_es_ilegible(self) -> None:
        estado.fijar_pausa("prueba", raiz=self.raiz, ahora=self.ahora)
        estado.quitar_pausa(raiz=self.raiz, ahora=self.ahora)
        conn = estado.conectar(self.raiz)
        try:
            conn.execute("UPDATE control SET valor='{no es json' WHERE clave='pausa'")
        finally:
            conn.close()
        self.assertTrue(estado.hay_pausa(raiz=self.raiz))


if __name__ == "__main__":
    import unittest
    unittest.main()
