"""Consola de acciones de lista blanca (CONTRATO §6): carga de ``acciones.yaml`` y ejecutor de trabajos.

Seguridad (no negociable):

* El argv es FIJO en el YAML; solo se rellenan parámetros TIPADOS y validados (``corrida``, ``oferta``, ``entero``,
  ``eleccion``, ``bandera``). No existe ningún tipo de texto libre; ningún valor puede empezar por ``-``.
* El cargador RECHAZA toda acción cuyo argv fijo contenga ``--live``, activar, publicar, reembolsar, gastar, firmar,
  borrar, pausar/reanudar, ``meta.*`` o la escritura de ``PAUSA``/``freno``. ``riesgo`` ∈ {``lectura``, ``escribe_local``}.
* ``subprocess`` con lista de argumentos, ``shell=False``, ``cwd`` = raíz, entorno MÍNIMO (sin claves ni tokens),
  ``stdin`` cerrado, grupo de procesos propio, timeout y tope de salida (256 KB); un trabajo a la vez por acción.
"""
from __future__ import annotations

import codecs
import os
import re
import select
import shlex
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dashboard.api_base import RX_CORRIDA, RX_OFERTA, ahora_utc
from dashboard.archivos import Raiz, iso_z
from dashboard.seguridad import ErrorHttp

__all__ = ["Accion", "Ejecutor", "Job", "ListaBlanca", "TOPE_SALIDA", "cargar_lista_blanca"]

TOPE_SALIDA = 256 * 1024
TIMEOUT_DEFECTO_S = 120
TIMEOUT_MAX_S = 900
MAX_JOBS_SIMULTANEOS = 3
MAX_JOBS_GUARDADOS = 60
RIESGOS = ("lectura", "escribe_local")
TIPOS_PARAMETRO = ("corrida", "oferta", "entero", "eleccion", "bandera")
_RX_ID = re.compile(r"^[a-z][a-z0-9_]{1,47}$")
_RX_MARCADOR = re.compile(r"\{([a-z_][a-z0-9_]*)\}")
_RX_VALOR_ELECCION = re.compile(r"^[A-Za-z0-9_.][A-Za-z0-9_.-]{0,39}$")
# Lo que NUNCA puede aparecer en el argv fijo de una acción (contrato §6).
_RX_PROHIBIDO = re.compile(
    r"(?<![A-Za-z0-9])(live|activar|activate|activacion|publicar|publish|reembolsar|refund|gastar|spend|firmar|sign|"
    r"borrar|delete|remove|rm|kill|pausar|reanudar|upload|deploy|desplegar|sellar|ingresar|freno|pausa)(?![A-Za-z0-9])",
    re.IGNORECASE)
_RX_MODULO_META = re.compile(r"(^|\s)meta(\.|/|$)", re.IGNORECASE)
_ENTORNO_FIJO = {
    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1",
    "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C",
}
_ENTORNOS_VALIDOS = ("desarrollo", "prueba", "produccion")


@dataclass(frozen=True)
class Accion:
    """Una entrada de la lista blanca ya validada."""

    id: str
    titulo: str
    descripcion: str
    riesgo: str
    argv: tuple[str, ...]
    parametros: Mapping[str, Mapping[str, Any]]
    timeout_s: int
    requiere: tuple[str, ...] = ()
    proximamente: bool = False
    motivo: str | None = None

    def vista(self) -> str:
        """Comando para mostrar/copiar (con ``<parametro>`` donde va un valor y ``[--flag]`` para las banderas)."""
        piezas: list[str] = []
        for t in self.argv:
            if t == "{python}":
                piezas.append("python")
                continue
            m = _RX_MARCADOR.fullmatch(t)
            if m and m.group(1) in self.parametros and self.parametros[m.group(1)].get("tipo") == "bandera":
                piezas.append(f"[{self.parametros[m.group(1)].get('flag')}]")
                continue
            piezas.append(_RX_MARCADOR.sub(lambda mm: f"<{mm.group(1)}>", t))
        return " ".join(p if (p.startswith("[") or "<" in p) else shlex.quote(p) for p in piezas)


@dataclass
class ListaBlanca:
    """Acciones válidas por id y las rechazadas (con el motivo) para mostrarlas en la consola."""

    acciones: dict[str, Accion] = field(default_factory=dict)
    rechazadas: list[dict[str, Any]] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _validar(crudo: Any, raiz: Path) -> tuple[Accion | None, str, list[str]]:
    errores: list[str] = []
    if not isinstance(crudo, dict):
        return None, "?", ["una entrada de la lista no tiene el formato esperado"]
    aid = crudo.get("id")
    if not isinstance(aid, str) or not _RX_ID.fullmatch(aid):
        return None, str(aid)[:48], ["el nombre interno (id) no es válido: solo minúsculas, números y guion bajo, y tiene que empezar con una letra"]
    titulo, desc = crudo.get("titulo"), crudo.get("descripcion")
    if not isinstance(titulo, str) or not titulo.strip():
        errores.append("falta el título")
    if not isinstance(desc, str):
        errores.append("falta la descripción")
    riesgo = crudo.get("riesgo")
    if riesgo not in RIESGOS:
        errores.append(f"el riesgo tiene que ser uno de estos: {', '.join(RIESGOS)}")
    timeout = crudo.get("timeout_s", TIMEOUT_DEFECTO_S)
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= TIMEOUT_MAX_S:
        errores.append(f"el tiempo máximo (timeout_s) tiene que ser un número entero de segundos entre 1 y {TIMEOUT_MAX_S}")
    requiere = crudo.get("requiere") or []
    if not isinstance(requiere, list) or not all(isinstance(r, str) for r in requiere):
        errores.append("«requiere» tiene que ser una lista de rutas relativas")
        requiere = []
    proximamente = crudo.get("proximamente") is True
    motivo = crudo.get("motivo") if isinstance(crudo.get("motivo"), str) else None
    params_crudos = crudo.get("parametros") or {}
    parametros: dict[str, dict[str, Any]] = {}
    if not isinstance(params_crudos, dict):
        errores.append("«parametros» tiene que ser un mapa (nombre: definición)")
        params_crudos = {}
    for nombre, p in params_crudos.items():
        if not isinstance(nombre, str) or not re.fullmatch(r"[a-z_][a-z0-9_]*", nombre) or nombre == "python":
            errores.append(f"el nombre de dato {nombre!r} no es válido")
            continue
        if not isinstance(p, dict) or p.get("tipo") not in TIPOS_PARAMETRO:
            errores.append(f"dato «{nombre}»: el tipo tiene que ser uno de estos: {', '.join(TIPOS_PARAMETRO)} (no se permite texto libre)")
            continue
        p = dict(p)
        if p["tipo"] == "entero":
            if not all(isinstance(p.get(k), int) and not isinstance(p.get(k), bool) for k in ("minimo", "maximo")) \
                    or not 0 <= p["minimo"] <= p["maximo"]:
                errores.append(f"dato «{nombre}»: un número entero necesita «minimo» y «maximo» (desde 0, con minimo menor o igual que maximo)")
        if p["tipo"] == "eleccion":
            valores = p.get("valores")
            if not isinstance(valores, list) or not valores or not all(isinstance(v, str) and _RX_VALOR_ELECCION.fullmatch(v) for v in valores):
                errores.append(f"dato «{nombre}»: una elección necesita una lista de valores simples que no empiecen con «-»")
        if p["tipo"] == "bandera":
            flag = p.get("flag")
            if not isinstance(flag, str) or not re.fullmatch(r"--[a-z][a-z0-9-]*", flag) or _RX_PROHIBIDO.search(flag):
                errores.append(f"dato «{nombre}»: la opción (flag) no es válida o está prohibida")
        parametros[nombre] = p
    argv = crudo.get("argv")
    if proximamente and argv is None:
        argv = []
    if not isinstance(argv, list) or not all(isinstance(t, str) for t in argv):
        errores.append("«argv» (el comando) tiene que ser una lista de textos")
        argv = []
    usados: set[str] = set()
    for t in argv:
        for m in _RX_MARCADOR.finditer(t):
            nombre = m.group(1)
            if nombre != "python" and nombre not in parametros:
                errores.append(f"el comando usa {{{nombre}}} sin declararlo en «parametros»")
            usados.add(nombre)
        fijo = _RX_MARCADOR.sub("", t)
        if fijo and (_RX_PROHIBIDO.search(fijo) or _RX_MODULO_META.search(fijo)):
            errores.append(f"el comando contiene algo prohibido: {fijo[:40]!r}")
        if t != "{python}" and not _RX_MARCADOR.fullmatch(t):
            for m in _RX_MARCADOR.finditer(t):
                if m.group(1) == "python" or parametros.get(m.group(1), {}).get("tipo") == "bandera":
                    errores.append("{python} y las opciones (banderas) tienen que ocupar un elemento completo del comando")
    for nombre in parametros:
        if nombre not in usados:
            errores.append(f"el dato «{nombre}» no se usa en el comando")
    if argv and argv[0] != "{python}":
        errores.append("el comando tiene que empezar con {python}")
    if not argv and not proximamente:
        errores.append("falta el comando («argv»)")
    for r in requiere:
        if r.startswith("/") or ".." in r.split("/"):
            errores.append("«requiere» solo admite rutas relativas dentro del proyecto")
    if errores:
        return None, aid, errores
    faltan = [r for r in requiere if not (raiz / r).exists()]
    if faltan and not proximamente:
        proximamente = True
        motivo = motivo or f"Todavía no está disponible: falta {', '.join(faltan)}."
    return Accion(aid, titulo.strip(), desc, riesgo, tuple(argv), parametros, timeout, tuple(requiere), proximamente, motivo), aid, []


def cargar_lista_blanca(ruta_yaml: Path, raiz: Path) -> ListaBlanca:
    """Lee y valida ``acciones.yaml``. Una entrada inválida se rechaza sola (nunca se ejecuta) y queda listada."""
    lista = ListaBlanca()
    lec = Raiz(ruta_yaml.parent).yaml(ruta_yaml.name)
    if not lec.ok:
        lista.avisos.append(lec.aviso or f"No se encontró la lista de acciones permitidas ({ruta_yaml.name}): la consola no tiene nada para ejecutar.")
        return lista
    if not isinstance(lec.dato, dict) or not isinstance(lec.dato.get("acciones"), list):
        lista.avisos.append("La lista de acciones permitidas (acciones.yaml) está mal armada: le falta la sección «acciones» con la lista.")
        return lista
    for crudo in lec.dato["acciones"]:
        accion, aid, errores = _validar(crudo, raiz)
        if accion is None:
            lista.rechazadas.append({"id": aid, "motivos": errores})
        elif accion.id in lista.acciones:
            lista.rechazadas.append({"id": aid, "motivos": ["el nombre interno (id) está repetido"]})
        else:
            lista.acciones[accion.id] = accion
    return lista


# ----------------------------------------------------------------------------------------------
# Trabajos
# ----------------------------------------------------------------------------------------------
class Job:
    """Un trabajo en marcha o terminado. Salida acumulada con tope; lecturas incrementales por posición."""

    def __init__(self, job_id: str, accion: Accion, comando: str, inicio: str,
                 ocultar: tuple[tuple[str, str], ...] = ()) -> None:
        self.id = job_id
        self.accion = accion.id
        self.comando = comando
        self.inicio = inicio
        self.fin: str | None = None
        self.estado = "corriendo"      # corriendo | ok | error | timeout | tope_salida
        self.codigo: int | None = None
        self.truncado = False
        self._salida: list[str] = []
        self._largo = 0
        self._cerrojo = threading.Lock()
        # Rutas absolutas que nunca deben llegar al navegador (CONTRATO §7.4): la raíz del proyecto → «.», la carpeta personal → «~».
        # Se reemplazan al agregar. Una ruta puede partirse entre dos lecturas: se retiene el sufijo del texto que podría ser el comienzo
        # de una de ellas (y solo ese) hasta que llegue lo que sigue, para que el reemplazo lo haga siempre el patrón completo.
        self._ocultar = tuple(sorted(((a, b) for a, b in ocultar if a and len(a) > 1), key=lambda par: -len(par[0])))
        self._cola = ""

    def _limpiar(self, texto: str) -> str:
        for ruta, reemplazo in self._ocultar:
            texto = texto.replace(ruta, reemplazo)
        return texto

    def _sufijo_retenible(self, buf: str) -> int:
        """Largo del sufijo más largo de ``buf`` que es un comienzo propio de alguna ruta a ocultar."""
        mejor = 0
        for ruta, _ in self._ocultar:
            for k in range(min(len(ruta) - 1, len(buf)), mejor, -1):
                if buf.endswith(ruta[:k]):
                    mejor = k
                    break
        return mejor

    def agregar(self, texto: str, final: bool = False) -> bool:
        """Agrega salida (sin rutas absolutas); devuelve ``True`` si se alcanzó el tope (se descarta lo que sobra).

        ``final=True`` vacía la cola retenida (se usa al cerrar el trabajo).
        """
        with self._cerrojo:
            if self._ocultar:
                buf = self._cola + texto
                retener = 0 if final else self._sufijo_retenible(buf)
                texto, self._cola = self._limpiar(buf[:len(buf) - retener]), buf[len(buf) - retener:]
            libre = TOPE_SALIDA - self._largo
            if len(texto) > libre:
                texto = texto[:max(libre, 0)]
                self.truncado = True
            if texto:
                self._salida.append(texto)
                self._largo += len(texto)
            return self.truncado

    def terminar(self, estado: str, codigo: int | None, fin: str) -> None:
        with self._cerrojo:
            self.estado, self.codigo, self.fin = estado, codigo, fin

    def leer(self, desde: int) -> dict[str, Any]:
        with self._cerrojo:
            total = "".join(self._salida)
            desde = max(0, min(desde, len(total)))
            return {"job_id": self.id, "accion": self.accion, "comando": self.comando, "estado": self.estado,
                    "terminado": self.estado != "corriendo", "codigo": self.codigo, "inicio": self.inicio, "fin": self.fin,
                    "desde": desde, "siguiente": len(total), "salida": total[desde:], "truncado": self.truncado,
                    "tope_salida": TOPE_SALIDA}


class Ejecutor:
    """Valida argumentos, arma el argv y corre un trabajo por acción en un grupo de procesos propio."""

    def __init__(self, raiz: Path, lista: ListaBlanca, *, python: str | None = None, ahora: Callable[[], Any] | None = None,
                 auditar: Callable[[dict[str, Any]], None] | None = None, max_simultaneos: int = MAX_JOBS_SIMULTANEOS) -> None:
        self._raiz_dada = os.path.abspath(raiz)
        self.raiz = Path(os.path.realpath(raiz))
        self.lista = lista
        self.python = python or sys.executable
        self._ahora = ahora
        self._auditar = auditar
        self._max = max_simultaneos
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._procesos: dict[str, subprocess.Popen[bytes]] = {}
        self._en_curso: dict[str, str] = {}
        self._cerrojo = threading.Lock()
        self._cerrado = False

    # -- API ----------------------------------------------------------------------------------
    def describir(self) -> dict[str, Any]:
        """Datos de ``GET /api/acciones``."""
        filas = []
        for a in self.lista.acciones.values():
            en_curso = self._en_curso_de(a.id)
            filas.append({
                "id": a.id, "titulo": a.titulo, "descripcion": a.descripcion, "riesgo": a.riesgo,
                "comando": a.vista(), "timeout_s": a.timeout_s, "proximamente": a.proximamente,
                "disponible": not a.proximamente, "motivo": a.motivo,
                "parametros": [{"nombre": n, **p} for n, p in a.parametros.items()],
                "en_curso": en_curso,
            })
        return {"acciones": filas, "rechazadas": self.lista.rechazadas}

    def _en_curso_de(self, accion_id: str) -> str | None:
        with self._cerrojo:
            jid = self._en_curso.get(accion_id)
            job = self._jobs.get(jid) if jid else None
            return jid if job is not None and job.estado == "corriendo" else None

    def job(self, job_id: str) -> Job | None:
        with self._cerrojo:
            return self._jobs.get(job_id)

    def iniciar(self, accion_id: Any, args: Any) -> Job:
        """Valida y lanza. Errores: 404 acción fuera de lista, 400 argumentos inválidos, 409 ya en curso, 429 saturado."""
        if not isinstance(accion_id, str) or accion_id not in self.lista.acciones:
            raise ErrorHttp(404, "accion_no_permitida", "Esa acción no está entre las permitidas de la consola.")
        accion = self.lista.acciones[accion_id]
        if accion.proximamente:
            raise ErrorHttp(400, "accion_proximamente", accion.motivo or "Esa acción todavía no está disponible.")
        if args is None:
            args = {}
        if not isinstance(args, Mapping):
            raise ErrorHttp(400, "args_invalidos", "Los datos de la acción no tienen la forma esperada.")
        argv = self._armar(accion, args)
        ahora = self._ahora_iso()
        comando = accion.vista()
        job = Job(uuid.uuid4().hex[:16], accion, comando, ahora, ocultar=self._rutas_a_ocultar())
        with self._cerrojo:
            if self._cerrado:
                raise ErrorHttp(503, "panel_cerrando", "El panel se está cerrando. Ábrelo de nuevo y prueba otra vez.")
            previo = self._jobs.get(self._en_curso.get(accion.id, ""))
            if previo is not None and previo.estado == "corriendo":
                raise ErrorHttp(409, "accion_en_curso", "Esa acción ya se está ejecutando. Espera a que termine para lanzarla otra vez.", job_id=previo.id)
            if sum(1 for j in self._jobs.values() if j.estado == "corriendo") >= self._max:
                raise ErrorHttp(429, "demasiados_trabajos", "Ya hay varias acciones en marcha. Espera a que termine alguna y prueba de nuevo.")
            try:
                proc = subprocess.Popen(  # noqa: S603 - lista de argumentos, shell=False, argv fijo de la lista blanca
                    argv, shell=False, cwd=self.raiz, env=self._entorno(), stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
            except OSError as exc:
                raise ErrorHttp(500, "no_se_pudo_lanzar", "No se pudo iniciar la acción. Prueba de nuevo; si sigue pasando, avisa a quien mantiene el sistema.") from exc
            self._jobs[job.id] = job
            self._procesos[job.id] = proc
            self._en_curso[accion.id] = job.id
            while len(self._jobs) > MAX_JOBS_GUARDADOS:
                viejo = next((k for k, j in self._jobs.items() if j.estado != "corriendo"), None)
                if viejo is None:
                    break
                del self._jobs[viejo]
        hilo = threading.Thread(target=self._correr, args=(job, proc, accion.timeout_s), name=f"job-{job.id}", daemon=True)
        hilo.start()
        if self._auditar is not None:
            try:
                self._auditar({"ts": ahora, "evento": "accion", "accion": accion.id, "args": dict(args), "job_id": job.id})
            except Exception:  # noqa: BLE001 - la auditoría nunca debe impedir ni romper la acción
                pass
        return job

    def _rutas_a_ocultar(self) -> tuple[tuple[str, str], ...]:
        """(ruta absoluta, reemplazo): la raíz del proyecto (real y tal como se pasó) y la carpeta personal."""
        pares = [(str(self.raiz), ".")]
        if self._raiz_dada and self._raiz_dada != str(self.raiz):
            pares.append((self._raiz_dada, "."))
        try:
            casa = str(Path.home())
        except (RuntimeError, KeyError):
            casa = ""
        if casa and casa != "/":
            pares.append((casa, "~"))
        return tuple(pares)

    def cerrar(self) -> None:
        """Termina los trabajos en marcha (al apagar el panel)."""
        with self._cerrojo:
            self._cerrado = True
            procesos = list(self._procesos.values())
        for p in procesos:
            self._matar(p)

    # -- internos -----------------------------------------------------------------------------
    def _ahora_iso(self) -> str:
        return iso_z((self._ahora or ahora_utc)())

    def _entorno(self) -> dict[str, str]:
        env = dict(_ENTORNO_FIJO)
        env["FABRICA_RAIZ"] = str(self.raiz)
        entorno = os.environ.get("FABRICA_ENTORNO")
        if entorno in _ENTORNOS_VALIDOS:
            env["FABRICA_ENTORNO"] = entorno
        return env

    def _armar(self, accion: Accion, args: Mapping[str, Any]) -> list[str]:
        desconocidos = set(args) - set(accion.parametros)
        if desconocidos:
            raise ErrorHttp(400, "args_invalidos", f"Hay datos que esta acción no acepta: {', '.join(sorted(map(str, desconocidos)))}.")
        valores: dict[str, str | None] = {}
        for nombre, p in accion.parametros.items():
            presente = nombre in args and args[nombre] is not None
            if not presente:
                if "defecto" in p:
                    valores[nombre] = self._validar_valor(nombre, p, p["defecto"])
                    continue
                if p.get("requerido"):
                    raise ErrorHttp(400, "args_invalidos", f"Falta completar un dato obligatorio: {nombre}.")
                valores[nombre] = None
                continue
            valores[nombre] = self._validar_valor(nombre, p, args[nombre])
        salida: list[str] = []
        for t in accion.argv:
            if t == "{python}":
                salida.append(self.python)
                continue
            entero = _RX_MARCADOR.fullmatch(t)
            if entero is not None and accion.parametros[entero.group(1)]["tipo"] == "bandera":
                if valores.get(entero.group(1)) == "1":
                    salida.append(accion.parametros[entero.group(1)]["flag"])
                continue

            def _sustituir(m: re.Match[str]) -> str:
                valor = valores.get(m.group(1))
                if valor is None:
                    raise ErrorHttp(400, "args_invalidos", f"Falta completar un dato: {m.group(1)}.")
                return valor

            salida.append(_RX_MARCADOR.sub(_sustituir, t))
        return salida

    def _validar_valor(self, nombre: str, p: Mapping[str, Any], valor: Any) -> str:
        tipo = p["tipo"]
        malo = ErrorHttp(400, "args_invalidos", f"El dato «{nombre}» no es válido.")
        if tipo == "bandera":
            if not isinstance(valor, bool):
                raise malo
            return "1" if valor else "0"
        if tipo == "entero":
            if not isinstance(valor, int) or isinstance(valor, bool) or not p["minimo"] <= valor <= p["maximo"]:
                raise ErrorHttp(400, "args_invalidos", f"El dato «{nombre}» tiene que ser un número entero entre {p['minimo']} y {p['maximo']}.")
            return str(valor)
        if not isinstance(valor, str):
            raise malo
        if tipo == "corrida":
            if not RX_CORRIDA.fullmatch(valor):
                raise ErrorHttp(400, "args_invalidos", f"El dato «{nombre}» tiene que ser la fecha y una letra, por ejemplo 2026-11-06-a.")
            return valor
        if tipo == "oferta":
            if not RX_OFERTA.fullmatch(valor) or not (self.raiz / "ofertas" / valor).is_dir():
                raise ErrorHttp(400, "args_invalidos", f"El dato «{nombre}» tiene que ser el código de una oferta que exista.")
            return valor
        if tipo == "eleccion":
            if valor not in p["valores"]:
                raise ErrorHttp(400, "args_invalidos", f"El dato «{nombre}» tiene que ser uno de estos: {', '.join(p['valores'])}.")
            plantilla = p.get("requiere_directorio")
            if isinstance(plantilla, str) and not (self.raiz / plantilla.replace("{valor}", valor)).is_dir():
                raise ErrorHttp(400, "args_invalidos", f"No existe la carpeta necesaria para «{valor}» (dato «{nombre}»).")
            return valor
        raise malo

    def _matar(self, proc: subprocess.Popen[bytes]) -> None:
        for senal, espera in ((signal.SIGTERM, 2.0), (signal.SIGKILL, 2.0)):
            try:
                os.killpg(proc.pid, senal)
            except (ProcessLookupError, PermissionError):
                return
            try:
                proc.wait(timeout=espera)
                return
            except subprocess.TimeoutExpired:
                continue

    def _correr(self, job: Job, proc: subprocess.Popen[bytes], timeout_s: int) -> None:
        decodificador = codecs.getincrementaldecoder("utf-8")(errors="replace")
        limite = time.monotonic() + timeout_s
        motivo: str | None = None
        fd = proc.stdout.fileno() if proc.stdout is not None else -1
        try:
            while fd >= 0:
                if time.monotonic() >= limite:
                    motivo = "timeout"
                    self._matar(proc)
                    break
                listos, _, _ = select.select([fd], [], [], 0.2)
                if listos:
                    datos = os.read(fd, 8192)
                    if not datos:
                        break
                    if job.agregar(decodificador.decode(datos)):
                        motivo = "tope_salida"
                        self._matar(proc)
                        break
                elif proc.poll() is not None:
                    # El proceso principal terminó; si un nieto retiene la tubería no esperamos a que la cierre.
                    break
            if motivo is None and proc.poll() is None:
                try:
                    proc.wait(timeout=max(1.0, limite - time.monotonic()))
                except subprocess.TimeoutExpired:
                    motivo = "timeout"
                    self._matar(proc)
            job.agregar(decodificador.decode(b"", final=True), final=True)
        finally:
            try:
                codigo = proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._matar(proc)
                codigo = proc.poll()
            if proc.stdout is not None:
                try:
                    proc.stdout.close()
                except OSError:
                    pass
            estado = motivo or ("ok" if codigo == 0 else "error")
            job.terminar(estado, codigo, self._ahora_iso())
            with self._cerrojo:
                self._procesos.pop(job.id, None)
