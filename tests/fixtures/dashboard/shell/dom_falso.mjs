// dom_falso.mjs — DOM mínimo en memoria para probar `ui.js` y las páginas con `node --test` (sin navegador, sin dependencias).
// Es deliberadamente estricto: `innerHTML`, `outerHTML` e `insertAdjacentHTML` LANZAN, para demostrar que ningún código los usa.
// Uso:  const { instalar, texto, buscar, buscarTodos } = await import('.../dom_falso.mjs'); const doc = instalar();

const NS_HTML = 'http://www.w3.org/1999/xhtml';

class Nodo {
  constructor(tipo) { this.nodeType = tipo; this.parentNode = null; this.childNodes = []; }
  get firstChild() { return this.childNodes[0] || null; }
  get lastChild() { return this.childNodes[this.childNodes.length - 1] || null; }
  get children() { return this.childNodes.filter((n) => n.nodeType === 1); }
  appendChild(n) {
    if (n.nodeType === 11) { for (const h of [...n.childNodes]) this.appendChild(h); return n; }
    if (n.parentNode) n.parentNode.removeChild(n);
    n.parentNode = this; this.childNodes.push(n); return n;
  }
  append(...ns) { for (const n of ns) this.appendChild(typeof n === 'string' ? new Texto(n) : n); }
  insertBefore(n, ref) {
    if (ref === null || ref === undefined) return this.appendChild(n);
    if (n.parentNode) n.parentNode.removeChild(n);
    const i = this.childNodes.indexOf(ref);
    if (i === -1) throw new Error('insertBefore: referencia ajena');
    n.parentNode = this; this.childNodes.splice(i, 0, n); return n;
  }
  removeChild(n) {
    const i = this.childNodes.indexOf(n);
    if (i === -1) throw new Error('removeChild: no es hijo');
    this.childNodes.splice(i, 1); n.parentNode = null; return n;
  }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  contains(n) { for (let x = n; x; x = x.parentNode) if (x === this) return true; return false; }
  get isConnected() { let x = this; while (x.parentNode) x = x.parentNode; return x === globalThis.document?.documentElement || x === globalThis.document; }
  get textContent() { return this.childNodes.map((n) => n.textContent).join(''); }
  set textContent(v) { this.childNodes.forEach((n) => { n.parentNode = null; }); this.childNodes = []; if (v !== '' && v !== null && v !== undefined) this.appendChild(new Texto(String(v))); }
}

class Texto extends Nodo {
  constructor(data) { super(3); this.data = String(data); }
  get textContent() { return this.data; }
  set textContent(v) { this.data = String(v); }
}

function parsearCompuesto(s) {
  const c = { tag: null, clases: [], attrs: [], noAttrs: [], id: null };
  let resto = s;
  const mt = /^(?:[a-zA-Z][a-zA-Z0-9-]*|\*)/.exec(resto);
  if (mt) { c.tag = mt[0] === '*' ? null : mt[0].toUpperCase(); resto = resto.slice(mt[0].length); }
  while (resto) {
    let m;
    if ((m = /^#([\w-]+)/.exec(resto))) c.id = m[1];
    else if ((m = /^\.([\w-]+)/.exec(resto))) c.clases.push(m[1]);
    else if ((m = /^:not\(\[([\w-]+)(?:="([^"]*)")?\]\)/.exec(resto))) c.noAttrs.push([m[1], m[2]]);
    else if ((m = /^\[([\w-]+)(?:="([^"]*)")?\]/.exec(resto))) c.attrs.push([m[1], m[2]]);
    else throw new Error(`selector no soportado por dom_falso: ${s}`);
    resto = resto.slice(m[0].length);
  }
  return c;
}

class Elemento extends Nodo {
  constructor(tag, ns = NS_HTML) {
    super(1);
    this.tagName = ns === NS_HTML ? tag.toUpperCase() : tag; this.namespaceURI = ns;
    this.attrs = new Map(); this.escuchas = new Map(); this.dataset = {};
    const est = new Map();
    this.style = { setProperty: (k, v) => est.set(k, v), getPropertyValue: (k) => est.get(k), set cssText(v) { est.set('cssText', v); }, _mapa: est };
    this._valor = '';
    this.classList = {
      add: (...c) => { const s = new Set(this.className.split(/\s+/).filter(Boolean)); c.forEach((x) => s.add(x)); this.className = [...s].join(' '); },
      remove: (...c) => { const s = new Set(this.className.split(/\s+/).filter(Boolean)); c.forEach((x) => s.delete(x)); this.className = [...s].join(' '); },
      toggle: (c, f) => { const t = f === undefined ? !this.classList.contains(c) : f; t ? this.classList.add(c) : this.classList.remove(c); return t; },
      contains: (c) => this.className.split(/\s+/).includes(c),
    };
  }
  get className() { return this.attrs.get('class') || ''; }
  set className(v) { this.attrs.set('class', String(v)); }
  get id() { return this.attrs.get('id') || ''; }
  get hidden() { return this.attrs.has('hidden'); }
  set hidden(v) { if (v) this.attrs.set('hidden', ''); else this.attrs.delete('hidden'); }
  get disabled() { return this.attrs.has('disabled'); }
  set disabled(v) { if (v) this.attrs.set('disabled', ''); else this.attrs.delete('disabled'); }
  get value() { return this._valor; }
  set value(v) { this._valor = String(v); }
  get checked() { return this.attrs.has('checked'); }
  set checked(v) { if (v) this.attrs.set('checked', ''); else this.attrs.delete('checked'); }
  get open() { return this.attrs.has('open'); }
  set open(v) { if (v) this.attrs.set('open', ''); else this.attrs.delete('open'); }
  setAttribute(k, v) { this.attrs.set(k, String(v)); }
  getAttribute(k) { return this.attrs.has(k) ? this.attrs.get(k) : null; }
  removeAttribute(k) { this.attrs.delete(k); }
  hasAttribute(k) { return this.attrs.has(k); }
  addEventListener(t, fn) { if (!this.escuchas.has(t)) this.escuchas.set(t, []); this.escuchas.get(t).push(fn); }
  removeEventListener(t, fn) { const l = this.escuchas.get(t) || []; const i = l.indexOf(fn); if (i !== -1) l.splice(i, 1); }
  /** Dispara un evento sobre el elemento y, si `burbuja`, sobre sus ancestros. Devuelve el objeto evento. */
  disparar(tipo, props = {}, burbuja = true) {
    const ev = { type: tipo, target: this, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, stopPropagation() { this._parado = true; }, ...props };
    for (let x = this; x && !ev._parado; x = burbuja ? x.parentNode : null) {
      for (const fn of [...(x.escuchas ? x.escuchas.get(tipo) || [] : [])]) fn(ev);
    }
    return ev;
  }
  click() { return this.disparar('click'); }
  focus() { globalThis.document.activeElement = this; }
  blur() { if (globalThis.document.activeElement === this) globalThis.document.activeElement = globalThis.document.body; }
  select() {}
  scrollIntoView() {}
  get scrollHeight() { return 0; } get clientHeight() { return 0; } get scrollTop() { return 0; } set scrollTop(_v) {}
  set innerHTML(_v) { throw new Error('innerHTML está prohibido en el panel'); }
  get innerHTML() { throw new Error('innerHTML está prohibido en el panel'); }
  set outerHTML(_v) { throw new Error('outerHTML está prohibido en el panel'); }
  insertAdjacentHTML() { throw new Error('insertAdjacentHTML está prohibido en el panel'); }
  _coincide(c) {
    if (c.tag && this.tagName.toUpperCase() !== c.tag) return false;
    if (c.id && this.id !== c.id) return false;
    const cl = this.className.split(/\s+/);
    if (!c.clases.every((x) => cl.includes(x))) return false;
    if (!c.attrs.every(([k, v]) => this.attrs.has(k) && (v === undefined || this.attrs.get(k) === v))) return false;
    if (c.noAttrs.some(([k, v]) => this.attrs.has(k) && (v === undefined || this.attrs.get(k) === v))) return false;
    return true;
  }
  _todos(sel) {
    const grupos = sel.split(',').map((g) => g.trim()).filter(Boolean).map((g) => g.split(/\s+/).map(parsearCompuesto));
    const salida = [];
    const visitar = (n, ancestros) => {
      for (const h of n.childNodes) {
        if (h.nodeType !== 1) continue;
        for (const cadena of grupos) {
          const ult = cadena[cadena.length - 1];
          if (!h._coincide(ult)) continue;
          let i = cadena.length - 2; let ok = true;
          for (let a = ancestros.length - 1; i >= 0 && a >= 0; a -= 1) if (ancestros[a]._coincide(cadena[i])) i -= 1;
          if (i >= 0) ok = false;
          if (ok) { salida.push(h); break; }
        }
        visitar(h, [...ancestros, h]);
      }
    };
    visitar(this, []);
    return salida;
  }
  querySelectorAll(sel) { return this._todos(sel); }
  querySelector(sel) { return this._todos(sel)[0] || null; }
  closest(sel) { const c = parsearCompuesto(sel); for (let x = this; x && x.nodeType === 1; x = x.parentNode) if (x._coincide(c)) return x; return null; }
  /** HTML serializado con TODO el texto escapado (solo para aserciones). */
  get html() {
    const esc = (t) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const attrs = [...this.attrs].map(([k, v]) => ` ${k}="${esc(v).replace(/"/g, '&quot;')}"`).join('');
    return `<${this.tagName.toLowerCase()}${attrs}>${this.childNodes.map((n) => (n.nodeType === 3 ? esc(n.data) : n.html)).join('')}</${this.tagName.toLowerCase()}>`;
  }
}

export function crearDocumento() {
  const doc = {
    nodeType: 9, activeElement: null, escuchas: new Map(), cookie: '',
    createElement: (t) => new Elemento(t), createElementNS: (ns, t) => new Elemento(t, ns), createTextNode: (d) => new Texto(d),
    createDocumentFragment: () => new Nodo(11),
    addEventListener(t, fn) { if (!this.escuchas.has(t)) this.escuchas.set(t, []); this.escuchas.get(t).push(fn); },
    removeEventListener(t, fn) { const l = this.escuchas.get(t) || []; const i = l.indexOf(fn); if (i !== -1) l.splice(i, 1); },
    execCommand: () => true, getElementById(id) { return this.body._todos('*').find?.((e) => e.id === id) || null; },
    teclado(key, props = {}) { const ev = { type: 'keydown', key, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, stopPropagation() { this._parado = true; }, ...props }; for (const fn of [...(this.escuchas.get('keydown') || [])]) fn(ev); return ev; },
    querySelector(sel) { return this.body.querySelector(sel); }, querySelectorAll(sel) { return this.body.querySelectorAll(sel); },
  };
  doc.documentElement = new Elemento('html');
  doc.body = new Elemento('body');
  doc.documentElement.appendChild(doc.body);
  doc.activeElement = doc.body;
  return doc;
}

/** Instala un `document` global nuevo y lo devuelve. */
export function instalar() {
  const doc = crearDocumento();
  globalThis.document = doc;
  return doc;
}

export const texto = (n) => n.textContent;
export const buscar = (n, sel) => n.querySelector(sel);
export const buscarTodos = (n, sel) => n.querySelectorAll(sel);
