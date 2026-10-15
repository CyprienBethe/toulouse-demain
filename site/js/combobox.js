// Address field with suggestions (ARIA 1.2 "combobox" pattern): type at
// least 3 characters, pick a suggestion with the mouse, a finger or the
// arrow keys and Enter. Escape closes the list.

import { clear, h } from './dom.js';

const MIN_CHARS = 3;
const DEBOUNCE_MS = 300;

/**
 * - input, list: the <input role=combobox> and its <ul role=listbox>
 * - search(text, signal) → Promise<[{label, name, detail, lat, lon}]>
 * - onChange(place | null): a place was picked, or the text was edited
 */
export function placeField({ input, list, search, onChange }) {
  let options = [];
  let active = -1;
  let timer = null;
  let controller = null;
  let picked = null;

  const close = () => {
    list.hidden = true;
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
    active = -1;
  };

  const highlight = (index) => {
    active = index;
    [...list.querySelectorAll('[role=option]')].forEach((el, i) => el.setAttribute('aria-selected', String(i === index)));
    if (index >= 0) {
      const id = `${list.id}-${index}`;
      input.setAttribute('aria-activedescendant', id);
      document.getElementById(id)?.scrollIntoView({ block: 'nearest' });
    } else input.removeAttribute('aria-activedescendant');
  };

  const choose = (index) => {
    const place = options[index];
    if (!place) return;
    picked = place;
    input.value = place.label;
    close();
    onChange(place);
  };

  const showInfo = (text) => {
    clear(list).append(h('li', { class: 'info', role: 'option', 'aria-disabled': 'true', text }));
    options = [];
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
  };

  const render = (places) => {
    options = places;
    clear(list);
    if (!places.length) {
      showInfo('Aucune adresse trouvée dans la zone couverte.');
      return;
    }
    places.forEach((place, i) => {
      const li = h('li', { id: `${list.id}-${i}`, role: 'option', 'aria-selected': 'false' },
        h('span', { class: 'name', text: place.name }),
        place.detail ? h('span', { class: 'detail', text: place.detail }) : null);
      // mousedown, not click: the input must not lose its value on blur first.
      li.addEventListener('mousedown', (event) => { event.preventDefault(); choose(i); });
      list.append(li);
    });
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
    highlight(-1);
  };

  const run = async (text) => {
    controller?.abort();
    controller = new AbortController();
    try {
      render(await search(text, controller.signal));
    } catch (error) {
      if (error?.name === 'AbortError') return;
      showInfo("La recherche d'adresse ne répond pas. Vous pouvez toucher la carte à la place.");
    }
  };

  input.addEventListener('input', () => {
    if (picked) {
      picked = null;
      onChange(null);
    }
    clearTimeout(timer);
    const text = input.value.trim();
    if (text.length < MIN_CHARS) {
      controller?.abort();
      close();
      return;
    }
    timer = setTimeout(() => run(text), DEBOUNCE_MS);
  });

  input.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown' && options.length) {
      event.preventDefault();
      if (list.hidden) { list.hidden = false; input.setAttribute('aria-expanded', 'true'); }
      highlight((active + 1) % options.length);
    } else if (event.key === 'ArrowUp' && options.length) {
      event.preventDefault();
      highlight(active <= 0 ? options.length - 1 : active - 1);
    } else if (event.key === 'Enter' && !list.hidden && active >= 0) {
      event.preventDefault();
      choose(active);
    } else if (event.key === 'Escape' && !list.hidden) {
      event.preventDefault();
      close();
    }
  });

  input.addEventListener('blur', () => setTimeout(close, 150));

  return {
    /** Set the field from outside (map, "Ma position", swap, demonstration). */
    set(place) {
      picked = place;
      input.value = place ? place.label : '';
      close();
    },
    get place() { return picked; },
    get text() { return input.value.trim(); },
    /** First suggestion for the typed text (used when the form is sent without picking). */
    async resolve() {
      if (picked) return picked;
      const text = input.value.trim();
      if (text.length < MIN_CHARS) return null;
      const places = await search(text);
      if (places[0]) this.set(places[0]);
      return places[0] || null;
    },
  };
}
