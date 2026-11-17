"""Cliente mínimo de Kie.ai (Market API + subida de archivos).

Referencia leída de docs.kie.ai el 2026-11-06:
- createTask  POST https://api.kie.ai/api/v1/jobs/createTask   {model, input, callBackUrl?}
- recordInfo  GET  https://api.kie.ai/api/v1/jobs/recordInfo?taskId=...
  state: waiting | queuing | generating | success | fail ; resultJson es un string JSON {"resultUrls": [...]}
- créditos    GET  https://api.kie.ai/api/v1/chat/credit
- subida      POST https://kieai.redpandaai.co/api/file-stream-upload (multipart: file, uploadPath, fileName)
  -> data.downloadUrl (el archivo se borra a las 24 h: se vuelve a subir en cada corrida)
HTTP devuelve 200 aunque falle: siempre se mira body["code"].
"""
from __future__ import annotations

import datetime as _dt
import json
import mimetypes
import os
import threading
import time
from pathlib import Path

import requests

API = "https://api.kie.ai"
SUBIDA = "https://kieai.redpandaai.co"
ESTADOS_EN_CURSO = {"waiting", "queuing", "generating"}


class KieError(RuntimeError):
    pass


class Kie:
    def __init__(self, api_key: str | None = None, timeout: int = 60):
        self.key = api_key or os.environ.get("KIE_API_KEY", "")
        if not self.key:
            raise KieError("Falta KIE_API_KEY (ponela en sketch-ia/.env)")
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {self.key}"})
        self.timeout = timeout
        self._cache_subidas: dict[str, str] = {}
        self._candado = threading.Lock()

    # ── utilidades ──────────────────────────────────────────────────────────
    def _ok(self, r: requests.Response) -> dict:
        try:
            body = r.json()
        except ValueError as e:
            raise KieError(f"Respuesta no JSON ({r.status_code}): {r.text[:300]}") from e
        if body.get("code") not in (200, None) or (body.get("success") is False):
            raise KieError(f"Kie.ai {body.get('code')}: {body.get('msg') or body}")
        return body

    def creditos(self) -> float:
        return self._ok(self.s.get(f"{API}/api/v1/chat/credit", timeout=self.timeout))["data"]

    def subir(self, ruta: str | Path, carpeta: str = "sketch-ia") -> str:
        """Sube un archivo local y devuelve la URL pública temporal (24 h). Cachea por ruta+mtime."""
        p = Path(ruta)
        clave = f"{p.resolve()}:{p.stat().st_mtime_ns}"
        with self._candado:   # una sola subida por archivo aunque varios hilos lo pidan a la vez
            if clave in self._cache_subidas:
                return self._cache_subidas[clave]
            mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            for intento in range(4):
                try:
                    with p.open("rb") as fh:
                        r = self.s.post(
                            f"{SUBIDA}/api/file-stream-upload",
                            files={"file": (p.name, fh, mime)},
                            data={"uploadPath": carpeta, "fileName": f"{int(time.time())}-{p.name}"},
                            timeout=300,
                        )
                    break
                except (requests.ConnectionError, requests.Timeout):
                    if intento == 3:
                        raise
                    time.sleep(3 * (intento + 1))
            url = self._ok(r)["data"]["downloadUrl"]
            self._cache_subidas[clave] = url
            return url

    # ── tareas ──────────────────────────────────────────────────────────────
    def crear(self, modelo: str, entrada: dict, etiqueta: str = "", dur: float | None = None) -> str:
        cotizado = estimar_creditos(modelo, entrada, dur)
        registrar_previo(modelo, etiqueta, cotizado)          # D6: se anota ANTES de enviar
        r = self.s.post(f"{API}/api/v1/jobs/createTask", json={"model": modelo, "input": entrada}, timeout=self.timeout)
        tid = self._ok(r)["data"]["taskId"]
        registrar_evento({"fase": "enviado", "etiqueta": etiqueta, "modelo": modelo, "task_id": tid, "cotizado": cotizado})
        return tid

    def estado(self, task_id: str) -> dict:
        # consultar no cuesta: ante cortes de red se reintenta hasta 8 veces sin perder la tarea
        for intento in range(8):
            try:
                r = self.s.get(f"{API}/api/v1/jobs/recordInfo", params={"taskId": task_id}, timeout=self.timeout)
                return self._ok(r)["data"]
            except (requests.ConnectionError, requests.Timeout) as e:
                if intento == 7:
                    raise KieError(f"Sin conexión consultando {task_id}: {e}") from e
                time.sleep(3 * (intento + 1))

    def esperar(self, task_id: str, max_seg: int = 1800, cada: int = 6, etiqueta: str = "") -> dict:
        t0 = time.time()
        ultimo = None
        while True:
            d = self.estado(task_id)
            st = d.get("state")
            if st != ultimo:
                print(f"    · {etiqueta or task_id}: {st}", flush=True)
                ultimo = st
            if st == "success":
                res = d.get("resultJson") or "{}"
                d["resultado"] = json.loads(res) if isinstance(res, str) else res
                return d
            if st == "fail":
                raise KieError(f"{etiqueta or task_id} falló: {d.get('failCode')} {d.get('failMsg')}")
            if time.time() - t0 > max_seg:
                raise KieError(f"{etiqueta or task_id}: tiempo de espera agotado ({max_seg}s)")
            time.sleep(cada)

    def generar(self, modelo: str, entrada: dict, destino: str | Path, etiqueta: str = "", max_seg: int = 1800,
                dur: float | None = None) -> dict:
        """Crea la tarea, espera, descarga el primer resultado en `destino` y devuelve el registro."""
        tid = self.crear(modelo, entrada, etiqueta, dur)
        print(f"  → {etiqueta}: tarea {tid} ({modelo})", flush=True)
        return self.recuperar(tid, destino, etiqueta=etiqueta, max_seg=max_seg)

    def recuperar(self, tid: str, destino: str | Path, etiqueta: str = "", max_seg: int = 1800) -> dict:
        """Espera (o retoma) una tarea ya creada y descarga su primer resultado."""
        d = self.esperar(tid, max_seg=max_seg, etiqueta=etiqueta)
        urls = (d.get("resultado") or {}).get("resultUrls") or []
        if not urls:
            raise KieError(f"{etiqueta}: la tarea terminó sin resultUrls: {d.get('resultado')}")
        descargar(urls[0], destino)
        registrar_evento({"fase": "resultado", "etiqueta": etiqueta, "modelo": d.get("model"), "task_id": tid,
                          "creditos": d.get("creditsConsumed"), "archivo": str(destino)})
        print(f"    ✓ {Path(destino).name}  ({d.get('creditsConsumed', '?')} créditos)", flush=True)
        return d


def descargar(url: str, destino: str | Path) -> Path:
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        tmp = destino.with_suffix(destino.suffix + ".part")
        with tmp.open("wb") as fh:
            for trozo in r.iter_content(1 << 16):
                fh.write(trozo)
        tmp.replace(destino)
    return destino


def urls_resultado(d: dict) -> list[str]:
    """Saca las URLs de un recordInfo exitoso: resultJson.resultUrls (Market) o response.data[].audio_url (Suno)."""
    res = d.get("resultado") or {}
    urls = list(res.get("resultUrls") or [])
    for bloque in (d.get("response"), res.get("response"), res):
        if isinstance(bloque, dict) and isinstance(bloque.get("data"), list):
            urls += [x.get("audio_url") for x in bloque["data"] if isinstance(x, dict) and x.get("audio_url")]
    return list(dict.fromkeys(urls))


def suno(kie: Kie, tipo: str, entrada: dict, destino_base: Path, etiqueta: str) -> list[Path]:
    """tipo: 'generate' (música) o 'sounds' (efectos). Descarga todas las variantes: destino_base-1.mp3, -2.mp3…"""
    tid = kie.crear(f"ai-music-api/{tipo}", entrada, etiqueta)
    print(f"  → {etiqueta}: tarea {tid} (suno {tipo})", flush=True)
    d = kie.esperar(tid, max_seg=900, etiqueta=etiqueta)
    urls = urls_resultado(d)
    if not urls:
        raise KieError(f"{etiqueta}: sin audio en la respuesta: {str(d)[:600]}")
    salidas = []
    for i, u in enumerate(urls, 1):
        p = destino_base.parent / f"{destino_base.name}-{i}.mp3"
        descargar(u, p)
        salidas.append(p)
        print(f"    ✓ {p.name}", flush=True)
    registrar_evento({"fase": "resultado", "etiqueta": etiqueta, "modelo": f"ai-music-api/{tipo}", "task_id": tid,
                      "creditos": d.get("creditsConsumed"), "archivo": ";".join(str(x) for x in salidas)})
    return salidas



# ── registro de gasto (contrato de D6: cada generación se anota antes de enviarse) ──────────────
# Créditos Kie estimados por tarea (1 crédito ≈ 0,005 USD). Medidos en el sketch «La notificación» (2026-11-06);
# el valor real queda en `creditsConsumed` y se concilia en assets.json (creditos_reales).
ESTIMADOS = {
    "nano-banana-pro": 18, "nano-banana-2": 8, "gpt-image-2-image-to-image": 6,
    "kling/ai-avatar-pro": 22,          # por segundo de audio
    "infinitalk/from-audio": 3,         # por segundo
    "kling-3.0/video": 15.1,            # por segundo (std, sin sonido)
    "bytedance/seedance-2-5": 17,       # por segundo
    "ai-music-api/generate": 12, "ai-music-api/sounds": 12,
}


def estimar_creditos(modelo: str, entrada: dict, dur: float | None = None) -> int:
    base = ESTIMADOS.get(modelo, 20)
    if modelo in ("kling/ai-avatar-pro", "infinitalk/from-audio"):
        return int(round(base * float(dur or 2.0) + 0.5))
    if modelo in ("kling-3.0/video", "bytedance/seedance-2-5"):
        return int(round(base * float(entrada.get("duration", 3)) + 0.5))
    return int(round(base + 0.49))


def registrar_evento(ev: dict) -> None:
    ruta = os.environ.get("SKETCH_REGISTRO")
    if not ruta:
        return
    ev = {"ts": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **ev}
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a") as fh:
        fh.write(json.dumps(ev, ensure_ascii=False) + "\n")


def registrar_previo(modelo: str, etiqueta: str, cotizado: int) -> None:
    """Línea en el borrador 06-creativos/costos.jsonl (contratos/costos.schema.json) antes de cada envío."""
    ruta = os.environ.get("SKETCH_COSTOS_BORRADOR")
    if not ruta:
        return
    linea = {
        "schema_version": "1.0.0",
        "ts": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "oferta_id": os.environ.get("SKETCH_OFERTA_ID", "[SUPUESTO]"),
        "etapa": "D6",
        "ejecucion_id": os.environ.get("SKETCH_EJECUCION_ID", "[SUPUESTO]"),
        "origen": "creditos",
        "concepto": f"kie {modelo} {os.environ.get('SKETCH_AD_NAME', '')}/{etiqueta} cotizado={cotizado} job=pendiente",
        "creditos": cotizado,
        "monto": {"monto": 0, "moneda": os.environ.get("SKETCH_MONEDA", "USD")},
    }
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a") as fh:
        fh.write(json.dumps(linea, ensure_ascii=False) + "\n")
