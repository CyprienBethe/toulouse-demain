// Tiny DOM helpers. Text always goes through textContent, never innerHTML:
// names coming from the server or the geocoder can never inject HTML.

const SVG_NS = 'http://www.w3.org/2000/svg';

/** h('p', {class: 'x', text: 'hello'}, child, ...) */
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  setAttrs(el, attrs);
  append(el, children);
  return el;
}

function setAttrs(el, attrs) {
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') el.setAttribute('class', value);
    else if (key === 'text') el.textContent = value;
    else if (key === 'vars') {
      // CSS custom properties, set through the CSSOM (allowed by the CSP).
      for (const [name, v] of Object.entries(value)) el.style.setProperty(name, v);
    } else if (key.startsWith('on') && typeof value === 'function') el.addEventListener(key.slice(2), value);
    else el.setAttribute(key, value === true ? '' : String(value));
  }
}

function append(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false || child === '') continue;
    el.append(child instanceof Node ? child : String(child));
  }
}

/** Inline SVG icon from path data: svgIcon(16, ['M3 8h10']) */
export function svgIcon(size, paths, { viewBox = `0 0 ${size} ${size}`, className } = {}) {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('width', String(size));
  svg.setAttribute('height', String(size));
  svg.setAttribute('viewBox', viewBox);
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  if (className) svg.setAttribute('class', className);
  for (const d of paths) {
    const path = document.createElementNS(SVG_NS, 'path');
    path.setAttribute('d', d);
    svg.append(path);
  }
  return svg;
}

export function clear(el) {
  while (el.firstChild) el.firstChild.remove();
  return el;
}

/** Visually hidden text, read by screen readers. */
export function srOnly(text) {
  return h('span', { class: 'sr-only', text });
}
