// _diseno.js — galería de componentes del sistema de diseño (SOLO DESARROLLO: `#/_diseno`, sin datos reales). No figura en el menú.
// Sirve para ver todas las piezas comunes juntas, en claro/oscuro, cómodo/compacto y con el modo técnico encendido o apagado.
// Parámetros del hash (solo para esta pantalla): ?seccion=tokens|iconos|controles|datos|guias|estados  ?tema=claro|oscuro  ?densidad=compacta  ?tecnico=1  ?abrir=termino|fuente

import { NOMBRES_ICONOS } from '../lib/iconos.js';

export const meta = { ruta: '_diseno', titulo: 'Galería de componentes', grupo: 'Desarrollo', icono: 'chispa' };

const SECCIONES = ['tokens', 'iconos', 'controles', 'datos', 'guias', 'estados'];

const SUPERFICIES = [
  ['--bg', 'Fondo de la app (nivel 0)'], ['--sup', 'Tarjeta (nivel 1)'], ['--sup-2', 'Hundido / hover (nivel 2)'], ['--sup-3', 'Pista, pulsado (nivel 3)'], ['--elev', 'Elevada: popover, modal'],
  ['--borde', 'Borde fino'], ['--borde-fuerte', 'Borde de énfasis'], ['--borde-input', 'Borde de campos (≥ 3:1)'],
];
const TEXTOS = [['--txt', 'Texto'], ['--txt-2', 'Texto secundario'], ['--txt-3', 'Texto terciario / metadatos']];
const ACENTO = [['--acento', 'Acento (único)'], ['--acento-fuerte', 'Acento fuerte'], ['--acento-bg', 'Acento tenue'], ['--foco', 'Anillo de foco']];
const ESTADOS = [
  ['bien', '--punto-ok', '--ok', '--ok-bg'], ['aviso', '--punto-aviso', '--aviso', '--aviso-bg'], ['grave', '--punto-grave', '--grave', '--grave-bg'],
  ['crítico', '--punto-error', '--error', '--error-bg'],
];
const SERIES = ['--serie-1', '--serie-2', '--serie-3', '--serie-4', '--serie-5', '--serie-6', '--serie-7', '--serie-8'];

export async function render(ctx) {
  const { ui, params } = ctx;
  const { el, fmt } = ui;

  // parámetros de desarrollo: permiten fotografiar cada combinación sin tocar el estado a mano
  const parche = {};
  if (params.tema === 'claro' || params.tema === 'oscuro' || params.tema === 'auto') parche.tema = params.tema;
  if (params.densidad === 'compacta' || params.densidad === 'comoda') parche.densidad = params.densidad;
  if (params.tecnico === '1' || params.tecnico === '0') parche.modoTecnico = params.tecnico === '1';
  if (Object.keys(parche).length) ctx.estado.fijar(parche);

  const quiere = (nombre) => !params.seccion || params.seccion === 'todo' || params.seccion === nombre;
  const muestra = (variable, texto) => el('div', { class: 'muestra' }, el('div', { class: 'muestra__color', style: { background: `var(${variable})` } }), el('code', null, variable), el('span', null, texto));
  const bloque = (titulo, ...cuerpo) => ui.seccion(titulo, el('div', { class: 'galeria__bloque' }, ...cuerpo));

  // ─────────── tokens ───────────
  const tokens = () => [
    bloque('Superficies y bordes', el('div', { class: 'galeria__muestras' }, SUPERFICIES.map(([v, t]) => muestra(v, t)))),
    bloque('Texto y acento único', el('div', { class: 'galeria__muestras' }, [...TEXTOS, ...ACENTO].map(([v, t]) => muestra(v, t))),
      el('p', { class: 'texto-tenue' }, 'El acento se reserva para lo interactivo y la selección. Nada decorativo lo usa.')),
    bloque('Estados: bien · aviso · grave · crítico (siempre icono + etiqueta)',
      el('div', { class: 'galeria__muestras' }, ESTADOS.flatMap(([n, punto, texto, fondo]) => [muestra(punto, `${n}: marca`), muestra(texto, `${n}: texto`), muestra(fondo, `${n}: fondo`)])),
      el('div', { class: 'galeria__fila' },
        ui.chip('Bien', 'bien'), ui.chip('Aviso', 'aviso'), ui.chip('Grave', 'grave'), ui.chip('Crítico', 'critico'), ui.chip('Espera tu firma', 'acento'), ui.chip('Informativo', 'info'), ui.chip('Neutro', 'neutro'),
        ui.chip('Sin icono', 'ok', { icono: false }))),
    bloque('Categorías de gráficos (orden fijo, nunca cíclico)', el('div', { class: 'galeria__muestras' }, SERIES.map((v, i) => muestra(v, `Serie ${i + 1}`))),
      el('p', { class: 'texto-tenue' }, 'El texto nunca lleva el color de la serie; se usa rotulado directo y vista de tabla.')),
    bloque('Escala tipográfica (raíz de 14 px)', el('div', { class: 'escala-tipo' }, [
      ['32 px · 2xl', '2.286rem', 650], ['24 px · título de página', '1.714rem', 650], ['20 px · xl', '1.43rem', 650], ['16 px · título de sección', '1.143rem', 650],
      ['14 px · texto base', '1rem', 400], ['13 px · secundario', '.929rem', 400], ['12 px · metadatos', '.857rem', 400],
    ].map(([etq, tam, peso]) => el('div', null, el('small', null, etq), el('span', { style: { fontSize: tam, fontWeight: String(peso) } }, 'Lo que pasa y qué espera de ti'))))),
  ];

  // ─────────── iconos ───────────
  const iconos = () => [
    bloque('Iconos propios (trazo 1,75 px, currentColor) a 28 px',
      el('div', { class: 'galeria__muestras' }, NOMBRES_ICONOS.map((n) => el('div', { class: 'muestra' }, el('span', { class: 'muestra__icono' }, ui.icono(n, { tamano: 28 })), el('code', null, n))))),
    bloque('A los tamaños de uso (12, 14, 16, 18, 22 px) en los estados reservados',
      el('div', { class: 'galeria__fila' }, [12, 14, 16, 18, 22].flatMap((t) => ['ok', 'alerta', 'rombo-alerta', 'octogono', 'info', 'usuario'].map((n) => ui.icono(n, { tamano: t }))))),
  ];

  // ─────────── controles ───────────
  const controles = () => [
    bloque('Botones',
      el('div', { class: 'galeria__fila' },
        el('button', { type: 'button', class: 'btn btn--primario' }, ui.icono('check', { tamano: 15 }), 'Primario'),
        el('button', { type: 'button', class: 'btn' }, 'Secundario'),
        el('button', { type: 'button', class: 'btn btn--fantasma' }, 'Fantasma'),
        el('button', { type: 'button', class: 'btn btn--peligro' }, ui.icono('pausa', { tamano: 15 }), 'Peligro'),
        el('button', { type: 'button', class: 'btn btn--peligro-suave' }, 'Peligro suave'),
        el('button', { type: 'button', class: 'btn', disabled: true }, 'Deshabilitado'),
        el('button', { type: 'button', class: 'btn btn--chico' }, 'Chico'),
        el('button', { type: 'button', class: 'btn btn--icono', 'aria-label': 'Copiar' }, ui.icono('copiar')),
        el('a', { class: 'btn', href: '#/_diseno' }, 'Enlace con aspecto de botón')),
      el('div', { class: 'galeria__fila' },
        ui.interruptor({ etiqueta: 'Detalle técnico', activo: true }), ui.interruptor({ etiqueta: 'Apagado', activo: false }),
        ui.segmentado({ etiqueta: 'Densidad', valor: 'comoda', opciones: [{ valor: 'comoda', etiqueta: 'Cómoda', icono: 'menu' }, { valor: 'compacta', etiqueta: 'Compacta', icono: 'densidad' }] }),
        ui.kbd('Ctrl/⌘', 'K'), ui.kbd('g', 'r'), ui.kbd('?'))),
    bloque('Campos',
      el('div', { class: 'filtros' },
        el('label', { class: 'filtros__campo' }, 'Texto', el('input', { class: 'campo', type: 'text', placeholder: 'Escribe algo…' })),
        el('label', { class: 'filtros__campo' }, 'Selector', el('select', { class: 'campo' }, el('option', null, 'Todas las ofertas'), el('option', null, 'OF-DEMO-01'))),
        el('label', { class: 'filtros__campo' }, 'Búsqueda', el('input', { class: 'campo', type: 'search', placeholder: 'Filtrar…' })),
        el('label', { class: 'filtros__campo' }, 'Con foco (pulsa Tab)', el('input', { class: 'campo', type: 'text', value: 'Foco visible con anillo' }))),
      el('label', { class: 'etiqueta-campo' }, 'Área de texto', el('textarea', { class: 'campo', rows: '2', placeholder: 'Motivo…' }))),
    bloque('Chips de estado con icono',
      el('div', { class: 'galeria__fila' }, ['aprobado', 'en_QA', 'en_progreso', 'pendiente', 'bloqueado', 'escalado', 'obsoleta', 'vigente', 'vencido', 'espera_firma'].map((e) => ui.estadoIcono(e)))),
    bloque('Pestañas (flechas, Inicio y Fin)', ui.tabs([
      { id: 'a', titulo: 'Resumen', render: () => el('p', null, 'Contenido de la primera pestaña.') },
      { id: 'b', titulo: 'Detalle', render: () => el('p', null, 'Contenido de la segunda pestaña.') },
      { id: 'c', titulo: 'Historial', render: () => el('p', null, 'Contenido de la tercera pestaña.') },
    ])),
    bloque('Pestañas que no caben: degradado en el borde con más pestañas (estrecha la ventana o desplaza)',
      el('div', { style: { maxWidth: '420px' } }, ui.barraPestanas({ etiqueta: 'Muchas secciones', activo: 'a', items: ['Resumen', 'Etapas', 'Archivos', 'Cumplimiento', 'Historial', 'Ajustes'].map((t, i) => ({ id: String.fromCharCode(97 + i), titulo: t, contador: i === 1 ? 11 : undefined })) }))),
    bloque('Avisos y ventanas',
      el('div', { class: 'galeria__fila' },
        el('button', { type: 'button', class: 'btn', onclick: () => ui.toast('Copiado al portapapeles', 'ok') }, 'Toast OK'),
        el('button', { type: 'button', class: 'btn', onclick: () => ui.toast('Algo necesita atención', 'aviso') }, 'Toast aviso'),
        el('button', { type: 'button', class: 'btn', onclick: () => ui.toast('No se pudo completar', 'error') }, 'Toast error'),
        el('button', { type: 'button', class: 'btn', onclick: () => ui.modal({ titulo: 'Ventana modal', cuerpo: el('p', null, 'Foco atrapado, Esc cierra y devuelve el foco.'), acciones: [{ texto: 'Cancelar' }, { texto: 'Aceptar', tono: 'primario' }] }) }, 'Abrir modal'))),
  ];

  // ─────────── datos ───────────
  const filas = [
    { id: 'OF-DEMO-01', fase: 'en_test', gasto: { monto: 124050, moneda: 'EUR' }, compras: 31, cpa: { monto: 4001, moneda: 'EUR' }, act: '2026-11-06T13:10:00Z' },
    { id: 'OF-DEMO-02', fase: 'en_construccion', gasto: { monto: 0, moneda: 'EUR' }, compras: 0, cpa: null, act: '2026-11-05T09:30:00Z' },
    { id: 'OF-DEMO-03', fase: 'validada', gasto: { monto: 981200, moneda: 'EUR' }, compras: 412, cpa: { monto: 2381, moneda: 'EUR' }, act: '2026-11-06T14:02:00Z' },
    { id: 'OF-DEMO-04', fase: 'fallida', gasto: { monto: 55300, moneda: 'USD' }, compras: 3, cpa: { monto: 18433, moneda: 'USD' }, act: '2026-10-28T08:00:00Z' },
  ];
  const datos = () => [
    bloque('Métricas: número grande, etiqueta humana, contexto, tendencia y mini-serie',
      el('div', { class: 'rejilla-tarjetas' },
        ui.metrica({ etiqueta: 'Gasto de hoy', valor: fmt.dinero(124050, 'EUR'), contexto: 'de 300,00 € de tope', tono: 'ok', tendencia: { valor: '+12 %', sentido: 'sube', bueno: false }, serie: [3, 5, 4, 6, 8, 7, 9], ayuda: 'tope' }),
        ui.metrica({ etiqueta: 'Ayuda con texto directo', valor: 7, contexto: 'sin clave de glosario', ayuda: 'Cuántas veces se repitió la prueba. Texto corto directo: no hace falta una clave por métrica.' }),
        ui.metrica({ etiqueta: 'Compras netas', valor: 31, contexto: 'últimos 7 días', tendencia: { valor: '+4', sentido: 'sube', bueno: true }, serie: [1, 2, 2, 4, 5, 4, 7], ayuda: 'compras_netas' }),
        ui.metrica({ etiqueta: 'Coste por compra', valor: fmt.dinero(4001, 'EUR'), contexto: 'equilibrio 42,00 €', tono: 'aviso', tendencia: { valor: '−3 %', sentido: 'baja', bueno: true }, ayuda: 'cpa_equilibrio' }),
        ui.metrica({ etiqueta: 'Reembolsos', valor: fmt.pct(1250), contexto: 'sobre el umbral del 10 %', tono: 'critico', ayuda: 'ratio_reembolsos' }),
        ui.metrica({ etiqueta: 'Esperan tu firma', valor: 2, contexto: 'Oferta y página de venta', tono: 'acento', ruta: 'ofertas' }),
        ui.metrica({ etiqueta: 'Sin dato todavía', valor: null, contexto: 'No hay lecturas aún' }),
        ui.tarjeta({ titulo: 'Tarjeta heredada', valor: '12', detalle: 'se ve igual que una métrica', tono: 'info' }))),
    bloque('Tabla: cabecera fija, cifras tabulares a la derecha, filtro y orden (usa el interruptor de densidad)',
      ui.tabla({
        etiqueta: 'Ofertas de ejemplo', filtro: true, ordenInicial: { clave: 'id', dir: 'asc' },
        columnas: [
          { clave: 'id', titulo: 'Oferta' },
          { clave: 'fase', titulo: 'Fase', formato: (v) => ui.estadoIcono(v) },
          { clave: 'gasto', titulo: 'Gasto', alinear: 'der' },
          { clave: 'compras', titulo: 'Compras', alinear: 'der', numerico: true },
          { clave: 'cpa', titulo: 'CPA', alinear: 'der' },
          { clave: 'act', titulo: 'Actualizada', formato: (v) => ui.tiempo(v, { ahora: Date.parse('2026-11-06T15:00:00Z') }) },
        ],
        filas, alClick: () => ui.toast('Fila elegida', 'info'),
      })),
    bloque('Clave/valor, barra apilada y mini-serie',
      el('div', { class: 'rejilla-2' },
        ui.kv([['Oferta', 'OF-DEMO-01'], ['Mercado', 'España · es-ES'], ['Nivel', ui.termino('nivel_n2', { texto: 'N2' })], ['Creada', ui.tiempo('2026-11-05T09:30:00Z', { ahora: Date.parse('2026-11-06T15:00:00Z') })], ['Sin dato', null]]),
        el('div', { class: 'pila' },
          ui.barraApilada([{ valor: 5, tono: 'ok', titulo: 'aprobadas' }, { valor: 2, tono: 'info', titulo: 'en curso' }, { valor: 1, tono: 'aviso', titulo: 'escaladas' }, { valor: 2, tono: 'neutro', titulo: 'pendientes' }], { etiqueta: 'Etapas por estado' }),
          el('div', { class: 'fila-flex' }, ui.sparkline([1, 3, 2, 5, 4, 6, 8], { ancho: 160, alto: 40, etiqueta: 'Ventas' }), el('span', { class: 'texto-tenue' }, 'Línea de 2 px con el último punto marcado')))),
    ),
    bloque('Visor de JSON y texto',
      ui.visorJson({ oferta_id: 'OF-DEMO-01', etapas: { D1: 'aprobado', D2: 'en_QA' }, gates_pendientes: ['D3'], nota: null }, { colapsado: false }),
      ui.visorTexto('# Título\n\nTexto plano: nunca se interpreta como HTML <b>ni</b> Markdown.', { tipo: 'md' })),
  ];

  // ─────────── guías ───────────
  const etapasDemo = [
    { id: 'D1', nombre: 'Descubrir', codigo: 'D1', estado: 'aprobado' }, { id: 'M1', nombre: 'Mercado', codigo: 'M1', estado: 'aprobado' }, { id: 'D2', nombre: 'Validar', codigo: 'D2', estado: 'aprobado' },
    { id: 'D3', nombre: 'Oferta', codigo: 'D3', estado: 'espera_firma', seleccionada: true, aviso: 'El QA dejó 2 notas para revisar' }, { id: 'D4', nombre: 'Producto', codigo: 'D4', estado: 'en_progreso' },
    { id: 'D5', nombre: 'Página de venta y pago', codigo: 'D5', estado: 'pendiente' }, { id: 'D6', nombre: 'Anuncios', codigo: 'D6', estado: 'bloqueado' }, { id: 'D7', nombre: 'Campaña', codigo: 'D7', estado: 'pendiente' },
    { id: 'D8', nombre: 'Operación', codigo: 'D8', estado: 'pendiente' }, { id: 'D9', nombre: 'Escalado', codigo: 'D9', estado: 'obsoleta' }, { id: 'D10', nombre: 'Después de la venta', codigo: 'D10', estado: 'escalado' },
  ];
  const guias = () => [
    ui.encabezadoPagina({
      titulo: 'Cabecera de página (ejemplo)', descripcion: 'Una frase que explica para qué sirve la pantalla, con migas arriba, la acción principal a la derecha y pestañas pegadas debajo.',
      migas: [{ texto: 'Operar' }, { texto: 'Ofertas', ruta: 'ofertas' }, { texto: 'OF-DEMO-01' }],
      acciones: [el('button', { type: 'button', class: 'btn' }, ui.icono('refrescar', { tamano: 15 }), 'Actualizar'), el('button', { type: 'button', class: 'btn btn--primario' }, 'Ver cómo firmar')],
      pestanas: ui.tabs([{ id: 'p1', titulo: 'Resumen', render: () => el('span') }, { id: 'p2', titulo: 'Etapas', render: () => el('span') }, { id: 'p3', titulo: 'Archivos', render: () => el('span') }]),
    }),
    ui.atencion({
      items: [
        { tono: 'info', titulo: 'El barrido de ayer terminó', detalle: '13 fichas nuevas listas para revisar.', accion: { texto: 'Ver fichas', ruta: 'descubrimiento' } },
        { tono: 'critico', titulo: 'El freno de captura está activo', detalle: 'La fuente cambió sus términos. Solo una persona puede levantarlo.', accion: { texto: 'Revisar freno', ruta: 'sistema' } },
        { tono: 'aviso', titulo: 'Los límites de gasto siguen sin fijar', detalle: 'Mientras no los definas, el sistema no puede gastar.', accion: { texto: 'Abrir límites', ruta: 'parametros' } },
        { tono: 'grave', titulo: 'La oferta OF-DEMO-04 superó el umbral de reembolsos', detalle: '12,5 % frente a un máximo del 10 %.', accion: { texto: 'Ver la oferta', ruta: 'oferta/OF-DEMO-04' } },
      ],
    }),
    ui.atencion({ items: [] }),
    bloque('Pipeline de oferta (pasos): flechas, Inicio y Fin; la etapa que espera tu firma, destacada',
      ui.pasos({ etapas: etapasDemo, onElegir: (id) => ui.toast(`Etapa ${id}`, 'info'), etiqueta: 'Etapas de OF-DEMO-01' })),
    bloque('Pipeline dentro de una tarjeta estrecha: se compacta solo (opción `compacto`: auto · true · false)',
      el('div', { style: { maxWidth: '560px' } }, ui.pasos({ etapas: etapasDemo, etiqueta: 'Etapas (compacto automático)' })),
      el('div', { style: { maxWidth: '560px' } }, ui.pasos({ etapas: etapasDemo.slice(0, 5), compacto: true, etiqueta: 'Etapas (compacto forzado)' }))),
    bloque('Términos con definición (pasa el cursor o enfoca con Tab) y ayuda «?»',
      el('p', null, 'Una oferta espera tu firma (', ui.termino('gate_h', { texto: 'gate H' }), ') cuando la ', ui.termino('preflight'), ' pasó y el ', ui.termino('sello_x1'), ' está vigente. Mira la ', ui.termino('traccion'), ' antes de decidir. ',
        ui.termino('termino_que_no_existe', { texto: 'Un término sin definición' }), '.'),
      el('div', { class: 'fila-flex' }, el('span', null, 'Tasa de reembolsos'), ui.ayuda('ratio_reembolsos'), el('span', { class: 'texto-tenue' }, '·'), el('span', null, 'Origen de estos datos'), ui.fuente(['ofertas/_ejemplo/estado.json', 'empresa/registro.jsonl'], { leido: new Date(Date.now() - 3000).toISOString() }))),
    bloque('Comando (cerrado por defecto, con Copiar visible) y detalle técnico (sigue el modo técnico)',
      ui.comando('.venv/bin/python -m engine.orq firmar --oferta OF-DEMO-01 --etapa D3', { nota: 'Lo firmas tú: el panel nunca firma por ti.' }),
      ui.comando('.venv/bin/python -m dashboard --puerto 8765', { titulo: 'Arrancar el panel', abierto: true }),
      ui.detalleTecnico('Rutas, huellas y JSON', () => el('div', { class: 'pila' },
        ui.kv([['Ruta', el('code', null, 'ofertas/OF-DEMO-01/estado.json')], ['Huella', el('code', null, 'sha256:9f2c…e41a')]]),
        ui.visorJson({ hash_config: 'sha256:9f2c…e41a', etapas: { D1: 'aprobado' } })))),
  ];

  // ─────────── estados ───────────
  const estados = () => [
    ui.vacioConPasos({
      titulo: 'Todavía no hay candidatos', explicacion: 'El barrido de descubrimiento aún no corrió, así que no hay fichas que revisar. Estos son los pasos para llenarlo.',
      icono: 'lupa',
      pasos: [{ texto: 'Comprueba en qué estado está el barrido.', comando: '.venv/bin/python -m scripts.modelado.barrido estado' }, { texto: 'Pídele al asistente que lance una corrida nueva y vuelve aquí.' }],
    }),
    ui.vacio('Sin filas que mostrar.', { pista: 'Cuando el motor registre eventos aparecerán aquí.', comando: '.venv/bin/python -m engine.registro ver', fuente: ['empresa/registro.jsonl'], icono: 'lista' }),
    bloque('Estado vacío con pasos en una columna estrecha (se adapta a su contenedor)',
      el('div', { class: 'rejilla-3' },
        ui.vacioConPasos({ titulo: 'Sin campañas', explicacion: 'Aún no hay campañas armadas para esta oferta.', icono: 'megafono', pasos: [{ texto: 'Genera el expediente.', comando: '.venv/bin/python -m engine.orq campana --oferta X' }] }),
        ui.vacioConPasos({ titulo: 'Compacto forzado', explicacion: 'Misma pieza con `compacto: true`.', icono: 'archivo', compacto: true, pasos: [{ texto: 'Un paso sin comando.' }] }))),
    bloque('Esqueletos de carga', ui.esqueleto('tarjetas', 4), ui.esqueleto('tabla', 4), ui.esqueleto('texto', 4)),
    bloque('Esqueleto de página completa', ui.esqueleto('pagina')),
    ui.errorBox({ codigo: 'sin_conexion', mensaje: 'No se pudo leer el estado del sistema.' }, { reintentar: () => ui.toast('Reintentando…', 'info') }),
  ];

  const mapa = { tokens, iconos, controles, datos, guias, estados };
  const activas = SECCIONES.filter(quiere);
  const nodo = el('div', { class: 'pagina' },
    ui.encabezadoPagina({
      titulo: 'Galería de componentes', descripcion: 'Solo desarrollo: todas las piezas del sistema de diseño con datos de ejemplo. Cambia tema, densidad y modo técnico en la barra superior.',
      acciones: SECCIONES.map((s) => el('a', { class: ['btn btn--chico', params.seccion === s && 'btn--primario'], href: `#/_diseno?seccion=${s}` }, s)),
    }),
    el('div', { class: 'galeria' }, activas.flatMap((s) => mapa[s]())),
    ui.fuenteInfo({ fuente: ['(ejemplos sin datos reales)'], generado_en: new Date().toISOString() }));

  if (params.abrir) {
    setTimeout(() => {
      const objetivo = params.abrir === 'fuente' ? nodo.querySelector('.fuente-btn') : nodo.querySelector('.termino');
      if (objetivo && typeof objetivo.focus === 'function') { objetivo.focus(); if (params.abrir === 'fuente') objetivo.click(); }
    }, 120);
  }
  return nodo;
}
