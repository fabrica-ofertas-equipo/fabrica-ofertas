// Arnés de SOLO LECTURA para tests/datos/test_contrato_workers.py (B3). Ejecuta el firmador REAL del
// Worker `tracking/workers/eventos` (de B2; este archivo NO lo modifica) con un `transporte` inyectado
// que captura la petición en vez de abrir un socket, y devuelve por stdout lo que ese Worker firma y
// envía a `POST /ingesta/evento`. Entrada por stdin: {"secreto","ahora","cuerpo"} (JSON).
import { manejarEvento } from "../../../tracking/workers/eventos/src/manejador.mjs";

function leerStdin() {
  return new Promise((resolve, reject) => {
    let datos = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (c) => { datos += c; });
    process.stdin.on("end", () => resolve(datos));
    process.stdin.on("error", reject);
  });
}

async function main() {
  const entrada = JSON.parse(await leerStdin());
  const capturado = { cabeceras: null, cuerpo: null, url: null };
  const transporte = {
    async solicitar(_metodo, url, opciones) {
      capturado.url = url;
      capturado.cabeceras = opciones.cabeceras;
      capturado.cuerpo = opciones.cuerpo;
      return { estado: 202, cuerpo: "{}" };
    },
  };
  const env = { ingestSecret: entrada.secreto, ingestaEventoUrl: "http://local/ingesta/evento" };
  const ahora = () => new Date(entrada.ahora);
  const resultado = await manejarEvento({ cuerpo: entrada.cuerpo, env, ahora, transporte });
  process.stdout.write(JSON.stringify({ resultado, capturado }));
}

main().catch((e) => {
  process.stderr.write(String((e && e.stack) || e));
  process.exit(1);
});
