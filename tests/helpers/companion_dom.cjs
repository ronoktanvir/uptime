class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.listeners = {}; this.attrs = {}; this.value = ''; this._text = ''; }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text + this.children.map(n => n.textContent).join(' '); }
  append(...nodes) { this.children.push(...nodes); }
  prepend(...nodes) { this.children.unshift(...nodes); }
  replaceChildren(...nodes) { this._text = ''; this.children = nodes; }
  setAttribute(k,v) { this.attrs[k] = v; }
  addEventListener(k,f) { this.listeners[k] = f; }
  all(tag) { return this.children.flatMap(n => [...(n.tagName === tag ? [n] : []), ...n.all(tag)]); }
  reportValidity() { return [...this.all('input'), ...this.all('textarea'), ...this.all('select')].every(n => !n.required || n.value); }
}
const document = {createElement: tag => new Element(tag)};

module.exports = {Element, document};
