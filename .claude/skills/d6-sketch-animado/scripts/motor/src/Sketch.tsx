import React from 'react';
import {
  AbsoluteFill,
  Audio,
  CalculateMetadataFunction,
  continueRender,
  delayRender,
  Easing,
  Img,
  interpolate,
  OffthreadVideo,
  Sequence,
  staticFile,
  useCurrentFrame,
} from 'remotion';

// Montaje del formato «sketch animado» (skill d6-sketch-animado). Las props las escribe `sketch montar`.
// Formato medido en la referencia: cortes secos cada 1–2 s, 60 % de planos fijos, empujes en líneas tensas,
// subtítulo blanco de 1–3 palabras, música por secciones con cortes cómicos y cierre con CTA «Comentá PALABRA».
// Sin marca propia: colores y fuentes llegan en `marca` (copia de 05-landing/paleta.json de la oferta).

type Plano = {id: string; ini: number; dur: number; tipo: 'video' | 'imagen' | 'vacio'; src?: string; inicio?: number; nota: string; zoom?: number; camara?: string};
type Pista = {src: string; ini: number; vol: number; fin?: number};
type Sub = {ini: number; fin: number; texto: string};
type Item = {etiqueta: string; titulo: string; detalle?: string};
type Cierre = {ini: number; dur: number; etiqueta?: string; antes?: string; palabra: string; despues?: string; extra?: string; items?: Item[]};
type Marca = {
  fondo?: string; // fondo del cierre
  texto?: string; // texto del cierre
  primario?: string; // etiquetas y línea secundaria
  acento?: string; // fondo de la palabra del CTA
  acento_texto?: string; // texto sobre el acento
  fuente_titulos?: string; // familia CSS
  fuente_texto?: string;
  fuentes?: {familia: string; src: string; peso?: string}[];
};
type Musica = {src: string; ini: number; dur: number; inicio: number; vol: number; sinVoz: number; fundido: number};

export type SketchProps = {
  fps: number;
  frames: number;
  planos: Plano[];
  audios: Pista[];
  sfx: Pista[];
  subtitulos: Sub[];
  musica: {src: string; vol: number; sinVoz?: number; cierre?: number} | null;
  musicas?: Musica[];
  ambiente: {src: string; vol: number} | null;
  cierre: Cierre | null;
  cortesMusica?: {ini: number; fin: number}[];
  estiloSub: {y: number; tam: number};
  marca?: Marca;
  etiquetaIA?: string | null;
  animatic: boolean;
};

export const calcularSketch: CalculateMetadataFunction<SketchProps> = ({props}) => ({
  durationInFrames: Math.max(1, props.frames),
  fps: props.fps || 30,
});

const MUEVE = Easing.bezier(0.76, 0, 0.24, 1);
const ENTRA = Easing.bezier(0.19, 1, 0.22, 1);
const SANS = (f?: string) => `${f ? `"${f}", ` : ''}"Helvetica Neue", Arial, sans-serif`;

// Carga de las fuentes de la oferta (WOFF2 de D5): el render espera a que estén.
const Fuentes: React.FC<{fuentes: Marca['fuentes']}> = ({fuentes}) => {
  const [h] = React.useState(() => (fuentes && fuentes.length ? delayRender('fuentes de la oferta') : null));
  React.useEffect(() => {
    if (h === null || !fuentes) return;
    Promise.all(fuentes.map((f) => new FontFace(f.familia, `url(${staticFile(f.src)})`, {weight: f.peso ?? '100 900'}).load()))
      .then((cargadas) => cargadas.forEach((c) => document.fonts.add(c)))
      .catch((e) => console.error('No cargaron las fuentes', e))
      .finally(() => continueRender(h));
  }, [h, fuentes]);
  return null;
};

// ─── Plano: corte seco; cámara por plano ───────────────────────────────────────────
const PlanoVista: React.FC<{p: Plano; animatic: boolean}> = ({p, animatic}) => {
  const f = useCurrentFrame();
  const z = p.zoom ?? 1;
  const lin = Math.min(1, f / Math.max(1, p.dur));
  let escala = 1 + 0.03 * Math.min(1, f / 240); // «fijo»: respiración mínima
  if (p.camara === 'push') escala = interpolate(lin, [0, 1], [1, 1.045], {easing: MUEVE});
  if (p.camara === 'push-lento') escala = 1 + 0.05 * lin;
  if (p.camara === 'push-fuerte') escala = interpolate(lin, [0, 1], [1, 1.2], {easing: MUEVE});
  if (p.camara === 'pull') escala = interpolate(f, [0, 8], [1.07, 1], {extrapolateRight: 'clamp', easing: ENTRA});
  const estilo: React.CSSProperties = {width: '100%', height: '100%', objectFit: 'cover', transformOrigin: '50% 38%', transform: `scale(${z * escala})`};
  return (
    <AbsoluteFill style={{background: '#000', overflow: 'hidden'}}>
      {p.tipo === 'video' && p.src ? <OffthreadVideo src={staticFile(p.src)} startFrom={p.inicio ?? 0} muted style={estilo} /> : null}
      {p.tipo === 'imagen' && p.src ? <Img src={staticFile(p.src)} style={estilo} /> : null}
      {p.tipo === 'vacio' ? (
        <AbsoluteFill style={{background: '#111', alignItems: 'center', justifyContent: 'center', padding: 64}}>
          <div style={{fontFamily: 'Menlo, monospace', color: '#999', fontSize: 34, textAlign: 'center', lineHeight: 1.4}}>{p.nota}</div>
        </AbsoluteFill>
      ) : null}
      {animatic ? (
        <div style={{position: 'absolute', top: 120, left: 64, fontFamily: 'Menlo, monospace', fontSize: 26, color: '#fff', background: 'rgba(0,0,0,.6)', padding: '6px 12px', borderRadius: 6}}>{p.nota}</div>
      ) : null}
    </AbsoluteFill>
  );
};

// ─── Subtítulos: blancos, finos, 1–3 palabras, dentro de la zona segura de Instagram/Meta ──
const Subtitulos: React.FC<{subs: Sub[]; y: number; tam: number; fuente?: string}> = ({subs, y, tam, fuente}) => {
  const f = useCurrentFrame();
  const s = subs.find((x) => x.ini <= f && f < x.fin);
  if (!s) return null;
  return (
    <div style={{position: 'absolute', left: 180, right: 180, top: y, display: 'flex', justifyContent: 'center'}}>
      <div style={{fontFamily: SANS(fuente), fontWeight: 600, fontSize: tam, letterSpacing: '-0.01em', lineHeight: 1.18, color: '#FFFFFF', textAlign: 'center', textShadow: '0 1px 2px rgba(0,0,0,.6), 0 0 14px rgba(0,0,0,.35)'}}>
        {s.texto}
      </div>
    </div>
  );
};

// ─── Etiqueta de IA visible (limites.politica_divulgacion_ia) ─────────────────────────
const EtiquetaIA: React.FC<{texto: string; fuente?: string}> = ({texto, fuente}) => (
  <div style={{position: 'absolute', top: 280, left: 0, right: 0, display: 'flex', justifyContent: 'center'}}>
    <div style={{fontFamily: SANS(fuente), fontWeight: 500, fontSize: 24, color: 'rgba(255,255,255,.92)', background: 'rgba(0,0,0,.38)', padding: '6px 14px', borderRadius: 999}}>{texto}</div>
  </div>
);

// ─── Viñeta: suave siempre; se cierra en los cortes de música (suspenso) ───────────────
const Vineta: React.FC<{cortes: {ini: number; fin: number}[]; hasta: number}> = ({cortes, hasta}) => {
  const f = useCurrentFrame();
  if (f >= hasta) return null;
  let extra = 0;
  for (const c of cortes) extra = Math.max(extra, Math.min(1, Math.max(0, (f - c.ini) / 10)) * Math.min(1, Math.max(0, (c.fin + 6 - f) / 6)));
  return <AbsoluteFill style={{pointerEvents: 'none', background: `radial-gradient(ellipse 75% 62% at 50% 44%, rgba(0,0,0,0) ${58 - 12 * extra}%, rgba(8,6,4,${0.38 + 0.27 * extra}) 100%)`}} />;
};

// ─── Cierre: «Comentá PALABRA» con la marca de la oferta ─────────────────────────────
const CierreVista: React.FC<{c: Cierre; m: Marca}> = ({c, m}) => {
  const f = useCurrentFrame();
  const p = (ini: number) => interpolate(f, [ini, ini + 12], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ENTRA});
  const sube = (x: number, d = 24): React.CSSProperties => ({opacity: x, transform: `translateY(${(1 - x) * d}px)`});
  const fondo = m.fondo ?? '#F5F3EE', texto = m.texto ?? '#141414', primario = m.primario ?? '#1F4ED8';
  const acento = m.acento ?? primario, acentoTxt = m.acento_texto ?? '#FFFFFF';
  return (
    <AbsoluteFill style={{background: fondo, alignItems: 'center', fontFamily: SANS(m.fuente_texto)}}>
      <div style={{position: 'absolute', top: 300, left: 64, right: 64, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 26}}>
        {c.etiqueta ? <div style={{fontSize: 24, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: primario, ...sube(p(0), 12)}}>{c.etiqueta}</div> : null}
        {c.antes ? <div style={{fontFamily: SANS(m.fuente_titulos), fontSize: 72, fontWeight: 600, letterSpacing: '-0.04em', color: texto, marginTop: 30, ...sube(p(6))}}>{c.antes}</div> : null}
        <div style={{fontFamily: SANS(m.fuente_titulos), fontSize: Math.min(180, Math.floor(1500 / Math.max(6, c.palabra.length))), fontWeight: 700, textAlign: 'center', lineHeight: 1, letterSpacing: '-0.05em', color: acentoTxt, background: acento, padding: '18px 40px 28px', borderRadius: 22, ...sube(p(12), 30)}}>{c.palabra}</div>
        {c.despues ? (
          <div style={{fontSize: 52, fontWeight: 600, letterSpacing: '-0.03em', color: texto, textAlign: 'center', marginTop: 10, ...sube(p(22))}}>
            {c.despues}
            {c.extra ? <div style={{color: primario, fontSize: 40, marginTop: 8}}>{c.extra}</div> : null}
          </div>
        ) : null}
        <div style={{display: 'flex', flexDirection: 'column', gap: 18, width: '100%', marginTop: 30}}>
          {(c.items ?? []).map((it, k) => (
            <div key={k} style={{display: 'flex', flexDirection: 'column', gap: 4, background: '#FFFFFF', borderRadius: 14, boxShadow: '0 20px 40px -24px rgba(0,0,0,.35)', padding: '22px 28px', ...sube(p(34 + k * 10))}}>
              <div style={{fontSize: 20, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: primario}}>{it.etiqueta}</div>
              <div style={{fontSize: 40, fontWeight: 600, color: texto}}>{it.titulo}</div>
              {it.detalle ? <div style={{fontSize: 26, color: '#666'}}>{it.detalle}</div> : null}
            </div>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ─── Mezcla: la música baja bajo la voz y sube en los huecos; se corta en los planos «musica: corta» ──
const volumenBase = (f: number, m: {vol: number; sinVoz?: number}, audios: Pista[]) => {
  const alto = m.sinVoz ?? m.vol;
  let d = Infinity;
  for (const a of audios) {
    const fin = a.fin ?? a.ini;
    if (f >= a.ini && f < fin) return m.vol;
    d = Math.min(d, Math.abs(f - a.ini), Math.abs(f - fin));
  }
  return m.vol + (alto - m.vol) * Math.min(1, Math.max(0, (d - 2) / 12));
};
const volumenCama = (f: number, m: {vol: number; sinVoz?: number}, audios: Pista[], cortes: {ini: number; fin: number}[]) => {
  for (const c of cortes) if (f >= c.ini && f < c.fin) return 0;
  const tras = cortes.find((c) => f >= c.fin && f < c.fin + 4);
  const antes = cortes.find((c) => f >= c.ini - 2 && f < c.ini);
  return Math.min(tras ? (f - tras.fin + 1) / 4 : 1, antes ? (antes.ini - f) / 3 : 1) * volumenBase(f, m, audios);
};

export const Sketch: React.FC<SketchProps> = (props) => {
  const {planos, audios, sfx, subtitulos, musica, ambiente, cierre, estiloSub, animatic} = props;
  const m = props.marca ?? {};
  const cortes = props.cortesMusica ?? [];
  const finHistoria = cierre ? cierre.ini : props.frames;
  return (
    <AbsoluteFill style={{background: '#000'}}>
      <Fuentes fuentes={m.fuentes} />
      <AbsoluteFill style={{filter: animatic ? undefined : 'contrast(1.07) saturate(1.06) brightness(0.98) sepia(0.04)'}}>
        {planos.map((p) => (
          <Sequence key={p.id} from={p.ini} durationInFrames={p.dur}>
            <PlanoVista p={p} animatic={animatic} />
          </Sequence>
        ))}
      </AbsoluteFill>
      {animatic ? null : <Vineta cortes={cortes} hasta={finHistoria} />}
      <Subtitulos subs={subtitulos} y={estiloSub.y} tam={estiloSub.tam} fuente={m.fuente_texto} />
      {props.etiquetaIA ? (
        <Sequence from={0} durationInFrames={finHistoria} layout="none">
          <EtiquetaIA texto={props.etiquetaIA} fuente={m.fuente_texto} />
        </Sequence>
      ) : null}
      {cierre ? (
        <Sequence from={cierre.ini} durationInFrames={cierre.dur}>
          <CierreVista c={cierre} m={m} />
          {props.etiquetaIA ? <EtiquetaIA texto={props.etiquetaIA} fuente={m.fuente_texto} /> : null}
        </Sequence>
      ) : null}
      {audios.map((a, k) => (
        <Sequence key={`a${k}`} from={a.ini} layout="none">
          <Audio src={staticFile(a.src)} volume={a.vol} />
        </Sequence>
      ))}
      {sfx.map((a, k) => (
        <Sequence key={`s${k}`} from={a.ini} layout="none">
          <Audio src={staticFile(a.src)} volume={a.vol} />
        </Sequence>
      ))}
      {(props.musicas ?? []).map((mu, k) => (
        <Sequence key={`m${k}`} from={mu.ini} durationInFrames={mu.dur} layout="none">
          <Audio
            src={staticFile(mu.src)}
            startFrom={mu.inicio}
            volume={(f) => {
              const entra = Math.min(1, (f + 1) / Math.max(1, mu.fundido));
              const sale = Math.min(1, (mu.dur - f) / Math.max(1, mu.fundido * 2));
              return Math.min(entra, sale) * volumenCama(mu.ini + f, mu, audios, cortes);
            }}
          />
        </Sequence>
      ))}
      {musica ? <Audio src={staticFile(musica.src)} volume={(f) => volumenCama(f, musica, audios, cortes)} loop /> : null}
      {ambiente ? <Audio src={staticFile(ambiente.src)} volume={ambiente.vol} loop /> : null}
    </AbsoluteFill>
  );
};

export const SKETCH_DEMO: SketchProps = {
  fps: 30,
  frames: 150,
  planos: [{id: 'p01', ini: 0, dur: 60, tipo: 'vacio', nota: 'p01 · plano de ejemplo'}],
  audios: [],
  sfx: [],
  subtitulos: [{ini: 10, fin: 55, texto: '¿Qué es eso?'}],
  musica: null,
  ambiente: null,
  cierre: {ini: 60, dur: 90, antes: 'Comentá', palabra: 'GUIA', despues: 'y te mando el acceso'},
  estiloSub: {y: 1150, tam: 46},
  etiquetaIA: 'Ficción animada · generada con IA',
  animatic: true,
};
