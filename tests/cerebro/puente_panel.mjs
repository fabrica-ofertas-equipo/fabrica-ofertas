// Puente de pruebas: calcula con el CÓDIGO REAL del panel (lib/cerebro.js y lib/tareas.js, tal cual) lo que el panel muestra de la lista única.
// Entrada (stdin): {"entradas": [<las líneas que devuelve GET /api/pulido>], "ahoraMs": 123}. Salida (stdout): un JSON con los ids de cada lista.
// Solo lectura: no escribe nada y no toca la red.
import { normalizarEntradas, clasificar, esAbierta, vencimiento } from '../../dashboard/web/lib/cerebro.js';
import { entradasPulido } from '../../dashboard/web/lib/tareas.js';

let crudo = '';
for await (const trozo of process.stdin) crudo += trozo;
const { entradas, ahoraMs } = JSON.parse(crudo);

const todas = normalizarEntradas(entradas);
const { pendientes, reglasPropuestas } = clasificar(todas);
const ids = (xs) => xs.map((e) => e.id);
const misTareas = entradasPulido({ entradas });      // «Mis tareas» (#/tareas) lee la lista con esta función

const salida = {
  p0: ids(todas.filter((e) => esAbierta(e) && e.prioridad === 'P0')),
  p1: ids(pendientes.filter((e) => esAbierta(e) && e.prioridad === 'P1')),
  abiertos_tareas: pendientes.filter(esAbierta).length,
  reglas: ids(reglasPropuestas.filter(esAbierta)),
  vencidos: ids(todas.filter((e) => vencimiento(e, ahoraMs).estado === 'vencido')),
  del_dueno: todas.filter((e) => esAbierta(e) && e.responsable === 'dueno').length,
  mis_tareas_mios: misTareas.filter((e) => e.estado !== 'resuelta' && e.responsable === 'dueno').length,
  mis_tareas_reglas: misTareas.filter((e) => e.tipo === 'regla_propuesta' && e.estado !== 'resuelta').length,
  total: todas.length,
};
process.stdout.write(JSON.stringify(salida));
