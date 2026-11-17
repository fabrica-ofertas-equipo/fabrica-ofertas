// dom_falso.mjs — DOM mínimo para probar el render de las páginas de P5 con `node --test` (sin navegador ni dependencias).
// Solo implementa lo que usan ui.js y las páginas: createElement/NS/TextNode, hijos, atributos, clase, dataset, style, eventos, textContent.
// NO interpreta HTML: es la prueba de que nada pasa por innerHTML (no existe en este DOM; si alguien lo usara, la prueba fallaría).

class Texto {
  constructor(t) { this.nodeType = 3; this.texto = String(t); this.parentNode = null; }
  get textContent() { return this.texto; }
}

class Elemento {
  constructor(tag, ns = null) {
    this.nodeType = 1; this.tagName = String(tag).toUpperCase(); this.localName = String(tag); this.namespaceURI = ns;
    this.hijos = []; this.atributos = new Map(); this.dataset = {}; this.eventos = {}; this.parentNode = null;
    this.hidden = false; this.className = ''; this.value = ''; this.checked = false; this.estiloMapa = {};
    const yo = this;
    this.style = { cssText: '', setProperty(k, v) { yo.estiloMapa[k] = v; } };
  }
  get firstChild() { return this.hijos[0] || null; }
  get children() { return this.hijos.filter((h) => h.nodeType === 1); }
  get childNodes() { return this.hijos; }
  get isConnected() { return true; }
  appendChild(n) { if (n.parentNode) n.parentNode.removeChild(n); n.parentNode = this; this.hijos.push(n); return n; }
  insertBefore(n, ref) {
    if (n.parentNode) n.parentNode.removeChild(n);
    const i = ref ? this.hijos.indexOf(ref) : -1;
    n.parentNode = this;
    if (i === -1) this.hijos.push(n); else this.hijos.splice(i, 0, n);
    return n;
  }
  removeChild(n) { const i = this.hijos.indexOf(n); if (i !== -1) this.hijos.splice(i, 1); n.parentNode = null; return n; }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  setAttribute(k, v) { this.atributos.set(k, String(v)); if (k === 'class') this.className = String(v); }
  getAttribute(k) { return this.atributos.has(k) ? this.atributos.get(k) : null; }
  removeAttribute(k) { this.atributos.delete(k); }
  addEventListener(t, f) { (this.eventos[t] = this.eventos[t] || []).push(f); }
  dispararEvento(t, ev = {}) { for (const f of this.eventos[t] || []) f({ target: this, ...ev, preventDefault() {} }); }
  focus() {} select() {}
  get textContent() { return this.hijos.map((h) => h.textContent).join(''); }
  set textContent(v) { this.hijos = []; if (v !== '' && v !== null && v !== undefined) this.appendChild(new Texto(v)); }
  get classList() {
    const yo = this;
    return {
      contains: (c) => yo.className.split(/\s+/).includes(c),
      add: (c) => { if (!yo.className.split(/\s+/).includes(c)) yo.className = `${yo.className} ${c}`.trim(); },
      remove: (c) => { yo.className = yo.className.split(/\s+/).filter((x) => x && x !== c).join(' '); },
      toggle: (c, f) => { const t = f === undefined ? !yo.className.split(/\s+/).includes(c) : f; if (t) yo.classList.add(c); else yo.classList.remove(c); },
    };
  }
  querySelector(sel) { return todos(this, (n) => coincideSelector(n, sel))[0] || null; }
  querySelectorAll(sel) { return todos(this, (n) => coincideSelector(n, sel)); }
}

function coincideSelector(n, sel) {
  if (n.nodeType !== 1) return false;
  return String(sel).split(',').some((s) => {
    const t = s.trim();
    if (t.startsWith('.')) return n.className.split(/\s+/).includes(t.slice(1));
    return n.localName === t;
  });
}

/** Todos los descendientes (incluido el propio nodo) que cumplan `pred`. */
export function todos(raiz, pred) {
  const salida = [];
  const visitar = (n) => { if (n.nodeType === 1 && pred(n)) salida.push(n); if (n.hijos) n.hijos.forEach(visitar); };
  visitar(raiz);
  return salida;
}
export const porClase = (raiz, clase) => todos(raiz, (n) => n.className.split(/\s+/).includes(clase));
export const porTag = (raiz, tag) => todos(raiz, (n) => n.localName === tag);
export const texto = (nodo) => nodo.textContent;

/** Instala `document` falso en globalThis y devuelve `restaurar()`. `defaultView` es null: instalarEstilos() no hace nada. */
export function instalarDomFalso() {
  const previo = globalThis.document;
  const doc = {
    createElement: (t) => new Elemento(t), createElementNS: (ns, t) => new Elemento(t, ns), createTextNode: (t) => new Texto(t),
    body: new Elemento('body'), activeElement: null, defaultView: null, addEventListener() {}, removeEventListener() {},
    querySelector: () => null, execCommand: () => false,
  };
  globalThis.document = doc;
  return () => { if (previo === undefined) delete globalThis.document; else globalThis.document = previo; };
}
