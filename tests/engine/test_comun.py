"""Pruebas de ``engine.comun``: raíz, entorno, tiempo UTC, archivos, hashes, firmas Ed25519 y datos sensibles."""
from __future__ import annotations

import contextlib
import io
import json
import os
import socket
import stat
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from engine import comun
from engine.errores import ErrorBloqueado, ErrorLimite, ErrorUso, ErrorValidacion
from scripts import validar_esquemas as ve
from tests.engine.apoyo import RAIZ_REPO, PruebaBase, par_de_claves


class PruebaRaizYEntorno(PruebaBase):
    """``raiz()`` y ``entorno()`` leen variables, nunca el directorio actual."""

    def test_raiz_usa_fabrica_raiz_resuelta(self) -> None:
        self.assertEqual(comun.raiz({"FABRICA_RAIZ": str(self.tmp)}), self.tmp.resolve())

    def test_raiz_inexistente_es_error_de_uso(self) -> None:
        with self.assertRaises(ErrorUso):
            comun.raiz({"FABRICA_RAIZ": str(self.tmp / "no-existe")})

    def test_raiz_sin_variable_es_la_del_repositorio_aunque_se_cambie_de_directorio(self) -> None:
        anterior = Path.cwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, anterior)
        self.assertEqual(comun.raiz({}), RAIZ_REPO)

    def test_entorno_por_defecto_es_desarrollo(self) -> None:
        self.assertEqual(comun.entorno({}), "desarrollo")
        self.assertEqual(comun.entorno({"FABRICA_ENTORNO": ""}), "desarrollo")

    def test_entornos_validos(self) -> None:
        for valor in ("desarrollo", "prueba", "produccion"):
            with self.subTest(valor=valor):
                self.assertEqual(comun.entorno({"FABRICA_ENTORNO": valor}), valor)

    def test_entorno_desconocido_no_se_asume(self) -> None:
        for valor in ("prod", "PRODUCCION", "live"):
            with self.subTest(valor=valor), self.assertRaises(ErrorUso):
                comun.entorno({"FABRICA_ENTORNO": valor})

    def test_sin_argumentos_lee_el_entorno_del_proceso(self) -> None:
        with mock.patch.dict(os.environ, {"FABRICA_ENTORNO": "prueba"}):
            self.assertEqual(comun.entorno(), "prueba")


class PruebaTiempo(PruebaBase):
    """Instantes UTC con ``Z``: sin ella o con desplazamiento se rechaza."""

    def test_ahora_utc_tiene_zona_y_segundos(self) -> None:
        d = comun.ahora_utc()
        self.assertEqual(d.utcoffset(), timedelta(0))
        self.assertEqual(d.microsecond, 0)

    def test_iso_z_convierte_a_utc_y_trunca(self) -> None:
        d = datetime(2026, 11, 6, 15, 30, 0, 999999, tzinfo=timezone(timedelta(hours=1)))
        self.assertEqual(comun.iso_z(d), "2026-11-06T14:30:00Z")

    def test_iso_z_rechaza_instante_sin_zona(self) -> None:
        with self.assertRaises(ErrorValidacion):
            comun.iso_z(datetime(2026, 11, 6, 14, 30, 0))

    def test_parsear_z_ida_y_vuelta(self) -> None:
        d = comun.parsear_z("2026-11-06T14:30:00Z")
        self.assertEqual(d, datetime(2026, 11, 6, 14, 30, 0, tzinfo=timezone.utc))
        self.assertEqual(comun.iso_z(d), "2026-11-06T14:30:00Z")

    def test_parsear_z_exige_la_z(self) -> None:
        invalidos = ["2026-11-06T14:30:00", "2026-11-06T14:30:00+00:00", "2026-11-06T14:30:00+01:00", "2026-11-06T14:30:00.5Z",
                     "2026-11-06 14:30:00Z", "2026-11-06T14:30Z", " 2026-11-06T14:30:00Z", "2026-11-06T14:30:00z", ""]
        for texto in invalidos:
            with self.subTest(texto=texto), self.assertRaises(ErrorValidacion):
                comun.parsear_z(texto)

    def test_parsear_z_rechaza_fechas_imposibles_y_tipos_incorrectos(self) -> None:
        for valor in ("2026-13-01T00:00:00Z", "2026-02-30T00:00:00Z", "2026-11-06T25:00:00Z", None, 20261106, b"2026-11-06T14:30:00Z"):
            with self.subTest(valor=valor), self.assertRaises(ErrorValidacion):
                comun.parsear_z(valor)  # type: ignore[arg-type]

    def test_instante_exige_reloj_con_zona(self) -> None:
        self.assertEqual(comun.instante(lambda: datetime(2026, 11, 6, tzinfo=timezone.utc)).tzinfo, timezone.utc)
        with self.assertRaises(ErrorValidacion):
            comun.instante(lambda: datetime(2026, 11, 6))
        with self.assertRaises(ErrorValidacion):
            comun.instante(lambda: "2026-11-06T00:00:00Z")  # type: ignore[arg-type,return-value]

    def test_dia_de_cuenta_con_corte_a_las_2330_utc_en_auckland_y_sao_paulo(self) -> None:
        corte = "2026-11-06T23:30:00Z"
        self.assertEqual(comun.dia_de_cuenta(corte, "Pacific/Auckland"), "2026-11-07")  # NZDT = UTC+13
        self.assertEqual(comun.dia_de_cuenta(corte, "America/Sao_Paulo"), "2026-11-06")  # UTC-3
        self.assertEqual(comun.dia_de_cuenta(corte, "UTC"), "2026-11-06")
        self.assertEqual(comun.dia_de_cuenta(comun.parsear_z("2026-11-07T02:30:00Z"), "America/Sao_Paulo"), "2026-11-06")
        self.assertEqual(comun.dia_de_cuenta("2026-11-07T03:00:00Z", "America/Sao_Paulo"), "2026-11-07")

    def test_dia_de_cuenta_respeta_dias_de_25_horas_por_cambio_de_horario(self) -> None:
        # Nueva York retrasa el reloj el 2026-11-01: ese día dura 25 h (04:00Z del 1 a 05:00Z del 2).
        self.assertEqual(comun.dia_de_cuenta("2026-11-01T03:59:59Z", "America/New_York"), "2026-10-31")
        self.assertEqual(comun.dia_de_cuenta("2026-11-01T04:00:00Z", "America/New_York"), "2026-11-01")
        self.assertEqual(comun.dia_de_cuenta("2026-11-02T04:59:59Z", "America/New_York"), "2026-11-01")
        self.assertEqual(comun.dia_de_cuenta("2026-11-02T05:00:00Z", "America/New_York"), "2026-11-02")

    def test_dia_de_cuenta_respeta_dias_de_23_horas_por_cambio_de_horario(self) -> None:
        # Nueva York adelanta el reloj el 2026-03-08: ese día dura 23 h (05:00Z del 8 a 04:00Z del 9).
        self.assertEqual(comun.dia_de_cuenta("2026-03-08T04:59:59Z", "America/New_York"), "2026-03-07")
        self.assertEqual(comun.dia_de_cuenta("2026-03-08T05:00:00Z", "America/New_York"), "2026-03-08")
        self.assertEqual(comun.dia_de_cuenta("2026-03-09T03:59:59Z", "America/New_York"), "2026-03-08")
        self.assertEqual(comun.dia_de_cuenta("2026-03-09T04:00:00Z", "America/New_York"), "2026-03-09")

    def test_dia_de_cuenta_rechaza_zona_o_instante_invalidos(self) -> None:
        for tz in ("Marte/Olimpo", "", None, "../etc/passwd"):
            with self.subTest(tz=tz), self.assertRaises(ErrorValidacion):
                comun.dia_de_cuenta("2026-11-06T00:00:00Z", tz)  # type: ignore[arg-type]
        with self.assertRaises(ErrorValidacion):
            comun.dia_de_cuenta(datetime(2026, 11, 6), "UTC")


class PruebaArchivos(PruebaBase):
    """Escritura atómica, append con bloqueo y lectura de JSONL."""

    def test_escribir_atomico_crea_carpetas_y_reemplaza_completo(self) -> None:
        destino = self.tmp / "a" / "b" / "estado.json"
        comun.escribir_atomico(destino, b"uno")
        self.assertEqual(destino.read_bytes(), b"uno")
        comun.escribir_atomico(destino, b"dos")
        self.assertEqual(destino.read_bytes(), b"dos")
        self.assertEqual([p.name for p in destino.parent.iterdir()], ["estado.json"], "no deben quedar temporales")

    def test_escribir_atomico_si_falla_deja_el_original_y_limpia(self) -> None:
        destino = self.tmp / "x.json"
        destino.write_bytes(b"original")
        with mock.patch("os.replace", side_effect=OSError("disco lleno")), self.assertRaises(OSError):
            comun.escribir_atomico(destino, b"nuevo")
        self.assertEqual(destino.read_bytes(), b"original")
        self.assertEqual([p.name for p in self.tmp.iterdir()], ["x.json"])

    def test_escribir_atomico_conserva_permisos_y_exige_bytes(self) -> None:
        destino = self.tmp / "p.txt"
        comun.escribir_atomico(destino, b"a")
        self.assertEqual(stat.S_IMODE(destino.stat().st_mode), 0o644)
        os.chmod(destino, 0o600)
        comun.escribir_atomico(destino, b"b")
        self.assertEqual(stat.S_IMODE(destino.stat().st_mode), 0o600)
        with self.assertRaises(ErrorValidacion):
            comun.escribir_atomico(destino, "texto")  # type: ignore[arg-type]

    def test_anexar_jsonl_escribe_json_canonico_una_linea_por_objeto(self) -> None:
        ruta = self.tmp / "e.jsonl"
        comun.anexar_jsonl(ruta, {"b": 2, "a": "ñ", "z": {"y": 1, "x": [1, 2]}})
        comun.anexar_jsonl(ruta, {"k": 1})
        self.assertEqual(ruta.read_text(encoding="utf-8"), '{"a":"ñ","b":2,"z":{"x":[1,2],"y":1}}\n{"k":1}\n')
        self.assertEqual(comun.leer_jsonl(ruta), [{"a": "ñ", "b": 2, "z": {"x": [1, 2], "y": 1}}, {"k": 1}])

    def test_anexar_jsonl_rechaza_flotantes_y_no_mapas(self) -> None:
        ruta = self.tmp / "e.jsonl"
        for malo in ({"monto": 1.5}, {"a": {"b": [1, 2.0]}}):
            with self.subTest(malo=malo), self.assertRaises(ErrorValidacion):
                comun.anexar_jsonl(ruta, malo)
        with self.assertRaises(ErrorValidacion):
            comun.anexar_jsonl(ruta, [1, 2])  # type: ignore[arg-type]
        with self.assertRaises(ErrorValidacion):
            comun.anexar_jsonl(ruta, {"a": {1, 2}})
        self.assertFalse(ruta.exists() and ruta.read_bytes())

    def test_anexar_tras_una_linea_truncada_no_las_pega(self) -> None:
        ruta = self.tmp / "t.jsonl"
        ruta.write_bytes(b'{"a":1}')  # sin salto de línea final: escritura anterior cortada
        comun.anexar_jsonl(ruta, {"b": 2})
        self.assertEqual(comun.leer_jsonl(ruta), [{"a": 1}, {"b": 2}])

    def test_anexar_concurrente_desde_hilos_no_mezcla_lineas(self) -> None:
        ruta = self.tmp / "c.jsonl"
        hilos = [threading.Thread(target=lambda n=n: [comun.anexar_jsonl(ruta, {"hilo": n, "i": i}) for i in range(20)]) for n in range(8)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        lineas = comun.leer_jsonl(ruta)
        self.assertEqual(len(lineas), 160)
        self.assertEqual(len({(x["hilo"], x["i"]) for x in lineas}), 160)

    def test_leer_jsonl_inexistente_es_lista_vacia_e_ignora_lineas_vacias(self) -> None:
        self.assertEqual(comun.leer_jsonl(self.tmp / "no.jsonl"), [])
        ruta = self.tmp / "v.jsonl"
        ruta.write_text('{"a":1}\n\n{"b":2}\n', encoding="utf-8")
        self.assertEqual(comun.leer_jsonl(ruta), [{"a": 1}, {"b": 2}])

    def test_leer_jsonl_rechaza_lineas_ilegibles_duplicadas_o_no_objeto(self) -> None:
        for contenido in ('{"a":1}\nno-es-json\n', '{"a":1,"a":2}\n', "[1,2]\n"):
            ruta = self.tmp / "m.jsonl"
            ruta.write_text(contenido, encoding="utf-8")
            with self.subTest(contenido=contenido), self.assertRaises(ErrorValidacion):
                comun.leer_jsonl(ruta)


class PruebaReexportaciones(PruebaBase):
    """Hashes y firma HMAC se re-exportan de ``scripts.validar_esquemas`` sin reimplementar."""

    def test_son_los_mismos_objetos(self) -> None:
        for nombre in ("json_canonico", "hash_objeto", "hash_archivo", "hash_directorio", "clave_idempotencia", "firma_hmac", "comparar_hash"):
            with self.subTest(nombre=nombre):
                self.assertIs(getattr(comun, nombre), getattr(ve, nombre))

    def test_el_json_canonico_sigue_la_referencia_de_las_convenciones(self) -> None:
        obj = {"b": [1, {"y": "ñ", "x": 2}], "a": None}
        esperado = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.assertEqual(comun.json_canonico(obj), esperado)
        self.assertTrue(comun.hash_objeto(obj).startswith("sha256:"))


class PruebaErroresDeEsquema(PruebaBase):
    """``comun.errores_de_esquema`` envuelve ``scripts.validar_esquemas.errores_de_esquema`` con tipo."""

    def test_esquema_conocido_delega_igual_que_antes(self) -> None:
        propios = [e.message for e in comun.errores_de_esquema("limites", {})]
        originales = [e.message for e in ve.errores_de_esquema("limites", {})]
        self.assertEqual(propios, originales)

    def test_esquema_desconocido_da_error_validacion_no_keyerror(self) -> None:
        # scripts.validar_esquemas.errores_de_esquema lanza un KeyError SIN TIPO si el nombre no es un
        # esquema conocido: la CLI terminaba con el código 1 (interno) en vez de uno de convenciones §8
        # (observación 4). ``comun.errores_de_esquema`` lo convierte en ErrorValidacion (3). Desde CT-2
        # los esquemas salen de contratos/ del código, no de FABRICA_RAIZ (CT2-40: el mensaje lo dice).
        with self.assertRaises(KeyError):
            ve.errores_de_esquema("esquema-que-no-existe", {})
        with self.assertRaises(ErrorValidacion) as cm:
            comun.errores_de_esquema("esquema-que-no-existe", {})
        self.assertIn("nunca de FABRICA_RAIZ", cm.exception.mensaje)
        self.assertIn("contratos", cm.exception.mensaje)
        self.assertNotIn("DIR_CONTRATOS", cm.exception.mensaje)    # el texto viejo, falso desde CT-2


class PruebaDinero(PruebaBase):
    """Importes enteros y monedas ISO 4217: la moneda se compara antes que el importe."""

    def test_exigir_importe(self) -> None:
        self.assertEqual(comun.exigir_importe(0), 0)
        self.assertEqual(comun.exigir_importe(5000), 5000)
        for malo in (True, False, 1.0, "5", None, -1):
            with self.subTest(malo=malo), self.assertRaises(ErrorValidacion):
                comun.exigir_importe(malo)

    def test_exigir_moneda(self) -> None:
        self.assertEqual(comun.exigir_moneda("EUR"), "EUR")
        for malo in ("eur", "EU", "EURO", "", None, 978, "USD\n"):
            with self.subTest(malo=malo), self.assertRaises(ErrorValidacion):
                comun.exigir_moneda(malo)  # "USD\n": antes ^[A-Z]{3}$ con .match() lo dejaba pasar (observación 5)

    def test_exigir_misma_moneda(self) -> None:
        comun.exigir_misma_moneda("USD", "USD")
        with self.assertRaises(ErrorValidacion):
            comun.exigir_misma_moneda("USD", "EUR", "tope")


class PruebaDatosSensibles(PruebaBase):
    """Los registros no llevan correos, IP, tarjetas ni credenciales."""

    def test_oculta_correo_ip_y_tarjeta_valida(self) -> None:
        texto = "cliente ana.perez+x@correo.example desde 203.0.113.7 y 2001:db8:85a3:0:0:8a2e:370:7334 pagó con 4111 1111 1111 1111"
        limpio = comun.ocultar_datos_sensibles(texto)
        for fragmento in ("ana.perez", "203.0.113.7", "2001:db8", "4111"):
            self.assertNotIn(fragmento, limpio)
        self.assertEqual(limpio.count("[correo]"), 1)
        self.assertEqual(limpio.count("[ip]"), 2)
        self.assertEqual(limpio.count("[tarjeta]"), 1)

    def test_no_toca_numeros_que_no_son_tarjeta_ni_versiones(self) -> None:
        texto = "pedido 1234567890123 versión 3.15.0 total 5000 EUR OF-202611-01"
        self.assertEqual(comun.ocultar_datos_sensibles(texto), texto)

    def test_oculta_prefijos_de_credenciales(self) -> None:
        # Los prefijos se arman por partes para no activar el escaneo de secretos del repositorio.
        secretos = ["s" + "k_live_abcdef123456", "r" + "k_test_abcdef123456", "whs" + "ec_abcdef123456", "E" + "AAGabcdef123456", "cf" + "ut_abcdef123456"]
        for secreto in secretos:
            with self.subTest(secreto=secreto[:4]):
                limpio = comun.enmascarar_secretos(f"token {secreto} fin")
                self.assertNotIn(secreto, limpio)
                self.assertIn("****", limpio)

    def test_no_enmascara_palabras_comunes(self) -> None:
        self.assertEqual(comun.enmascarar_secretos("task_runner y desk_top"), "task_runner y desk_top")


class PruebaFirmasEd25519(PruebaBase):
    """Firma y verificación con ``ssh-keygen -Y`` (local, sin red): solo la pública verifica."""

    def test_firma_y_verifica(self) -> None:
        par = par_de_claves()
        firma = comun.firmar_ed25519(b"contenido aprobado", par.privada)
        self.assertRegex(firma, r"^ed25519:[A-Za-z0-9+/=]{20,}$")
        self.assertTrue(comun.verificar_ed25519(b"contenido aprobado", firma, par.publica))

    def test_la_firma_es_determinista(self) -> None:
        par = par_de_claves()
        self.assertEqual(comun.firmar_ed25519(b"x", par.privada), comun.firmar_ed25519(b"x", par.privada))

    def test_datos_alterados_no_verifican(self) -> None:
        par = par_de_claves()
        firma = comun.firmar_ed25519(b"contenido aprobado", par.privada)
        self.assertFalse(comun.verificar_ed25519(b"contenido aprobadO", firma, par.publica))

    def test_otra_clave_no_verifica(self) -> None:
        par, otra = par_de_claves(), par_de_claves("otra")
        firma = comun.firmar_ed25519(b"datos", par.privada)
        self.assertFalse(comun.verificar_ed25519(b"datos", firma, otra.publica))

    def test_otro_namespace_no_verifica(self) -> None:
        par = par_de_claves()
        firma = comun.firmar_ed25519(b"datos", par.privada, namespace="otro-namespace")
        self.assertFalse(comun.verificar_ed25519(b"datos", firma, par.publica))
        self.assertTrue(comun.verificar_ed25519(b"datos", firma, par.publica, namespace="otro-namespace"))

    def test_firma_alterada_o_mal_formada_es_falsa_sin_lanzar(self) -> None:
        par = par_de_claves()
        firma = comun.firmar_ed25519(b"datos", par.privada)
        cuerpo = firma[len("ed25519:"):]
        alterada = "ed25519:" + cuerpo[:40] + ("A" if cuerpo[40] != "A" else "B") + cuerpo[41:]
        malas = [alterada, "ed25519:", "ed25519:abc", "ed25519:" + "A" * 40, "hmac-sha256:" + "ab" * 32, "", "ed25519:" + cuerpo[:-4], None, 5]
        for mala in malas:
            with self.subTest(mala=str(mala)[:30]):
                self.assertFalse(comun.verificar_ed25519(b"datos", mala, par.publica))  # type: ignore[arg-type]

    def test_clave_publica_con_comentario_vale_y_sin_clave_se_bloquea(self) -> None:
        par = par_de_claves()
        firma = comun.firmar_ed25519(b"datos", par.privada)
        self.assertTrue(comun.verificar_ed25519(b"datos", firma, par.publica + " dueno@equipo"))
        for mala in ("", "ssh-rsa AAAA", "ssh-ed25519 AAAA", "ssh-ed25519 " + "A" * 80, None, "ssh-ed25519 abc\nssh-ed25519 def"):
            with self.subTest(mala=str(mala)[:25]), self.assertRaises(ErrorBloqueado):
                comun.verificar_ed25519(b"datos", firma, mala)  # type: ignore[arg-type]

    def test_namespace_inseguro_se_rechaza_antes_de_ejecutar_nada(self) -> None:
        par = par_de_claves()
        firma = comun.firmar_ed25519(b"datos", par.privada)
        # "fabrica-ofertas\n": antes ^[A-Za-z0-9][A-Za-z0-9._-]*$ con .match() lo dejaba pasar (observación 5).
        for malo in ("-O", "", "a b", 'a"b', "a\nb", None, "fabrica-ofertas\n"):
            with self.subTest(namespace=malo):
                with self.assertRaises(ErrorValidacion):
                    comun.verificar_ed25519(b"datos", firma, par.publica, namespace=malo)  # type: ignore[arg-type]
                with self.assertRaises(ErrorValidacion):
                    comun.firmar_ed25519(b"datos", par.privada, namespace=malo)  # type: ignore[arg-type]

    def test_clave_privada_inexistente_bloquea(self) -> None:
        with self.assertRaises(ErrorBloqueado):
            comun.firmar_ed25519(b"datos", self.tmp / "no-existe")

    def test_sin_ssh_keygen_falla_cerrado(self) -> None:
        par = par_de_claves()
        firma = comun.firmar_ed25519(b"datos", par.privada)
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("ssh-keygen")):
            with self.assertRaises(ErrorBloqueado):
                comun.verificar_ed25519(b"datos", firma, par.publica)
            with self.assertRaises(ErrorBloqueado):
                comun.firmar_ed25519(b"datos", par.privada)

    def test_ruta_ssh_keygen_configurada_que_no_existe_falla_cerrado(self) -> None:
        # Antes ssh-keygen se resolvía SIEMPRE por PATH, sin forma de fijar una ruta absoluta
        # (observación 8). Una ruta configurada (parámetro o FABRICA_SSH_KEYGEN) que no sea un
        # ejecutable real debe bloquear, no caer de vuelta al PATH en silencio.
        par = par_de_claves()
        firma = comun.firmar_ed25519(b"datos", par.privada)
        falsa = self.tmp / "no-es-ssh-keygen"
        with self.assertRaises(ErrorBloqueado):
            comun.verificar_ed25519(b"datos", firma, par.publica, ruta_ssh_keygen=falsa)
        with self.assertRaises(ErrorBloqueado):
            comun.firmar_ed25519(b"datos", par.privada, ruta_ssh_keygen=falsa)
        with self.assertRaises(ErrorBloqueado):
            comun.verificar_ed25519(b"datos", firma, par.publica, env={"FABRICA_SSH_KEYGEN": str(falsa)})

    def test_ruta_ssh_keygen_configurada_que_existe_se_usa(self) -> None:
        # Con una ruta absoluta real (el mismo binario resuelto a mano), firmar y verificar siguen
        # funcionando: el parámetro/variable no es solo una restricción, también es una vía válida.
        import shutil

        real = shutil.which("ssh-keygen")
        if not real:
            self.skipTest("ssh-keygen no está en el PATH")
        par = par_de_claves()
        firma = comun.firmar_ed25519(b"datos", par.privada, ruta_ssh_keygen=real)
        self.assertTrue(comun.verificar_ed25519(b"datos", firma, par.publica, ruta_ssh_keygen=real))
        self.assertTrue(comun.verificar_ed25519(b"datos", firma, par.publica, env={"FABRICA_SSH_KEYGEN": real}))


class PruebaEjecutarCli(PruebaBase):
    """``ejecutar_cli`` traduce excepciones a códigos de salida sin filtrar secretos."""

    def _correr(self, f):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            codigo = comun.ejecutar_cli(f)
        return codigo, err.getvalue()

    def test_sin_error_devuelve_cero_o_el_entero_del_cuerpo(self) -> None:
        self.assertEqual(self._correr(lambda: None)[0], 0)
        self.assertEqual(self._correr(lambda: 3)[0], 3)

    def test_error_tipado_da_su_codigo_y_mensaje(self) -> None:
        def f():
            raise ErrorLimite("falta gasto_diario_global")
        codigo, err = self._correr(f)
        self.assertEqual(codigo, 5)
        self.assertIn("falta gasto_diario_global", err)

    def test_error_inesperado_da_uno_con_traza_sin_secretos(self) -> None:
        secreto = "r" + "k_live_abcdef123456"

        def f():
            raise RuntimeError(f"clave {secreto}")
        codigo, err = self._correr(f)
        self.assertEqual(codigo, 1)
        self.assertIn("RuntimeError", err)
        self.assertNotIn(secreto, err)

    def test_no_se_abre_ningun_socket(self) -> None:
        with self.assertRaises(AssertionError):
            socket.socket()


if __name__ == "__main__":
    unittest.main()
