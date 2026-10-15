// Toulouse Demain — entry point of the site.
//
// One working screen: a panel (search → results → detail) over a map.
// The scenario (today / 2028) is the first control and is remembered.

import { API_BASE, FILTERS_URLS, GRAPHQL_URL, ZONE_BOX } from '../config.js';
import { placeField } from './combobox.js';
import { buildComparison, sortTrips, uniqueTrips } from './compare.js';
import { DEMO_FILE, findRecorded, parseDemo, recordedSearches } from './demo.js';
import { clear, h } from './dom.js';
import {
  formatDay, formatShortDate, formatTime, parisDateInput, parisLocalToMs, parisTimeInput, toParisIso,
} from './format.js';
import { reversePlace, searchPlaces } from './geocode.js';
import { toTrip } from './itinerary.js';
import { createMap } from './map.js';
import { apiErrorMessage, routingErrorMessage } from './messages.js';
import { ApiError, buildVariables, checkGraphqlBody, isPlaceholderApi, PLAN_QUERY, postGraphql } from './otp.js';
import { detailView, noticeBox, tripItem } from './render.js';
import { parseScenarioFilters } from './scenarios.js';
import { storedScenario, storeScenario } from './storage.js';

const $ = (id) => document.getElementById(id);
const ZONE_CENTER = { lat: (ZONE_BOX[1] + ZONE_BOX[3]) / 2, lon: (ZONE_BOX[0] + ZONE_BOX[2]) / 2 };
const inZone = ({ lat, lon }) => lon >= ZONE_BOX[0] && lon <= ZONE_BOX[2] && lat >= ZONE_BOX[1] && lat <= ZONE_BOX[3];
const wantsDemo = new URLSearchParams(location.search).get('demo') === '1';

const state = {
  scenario: storedScenario(),
  view: 'search',
  origin: null,
  destination: null,
  filters: null,
  demo: null,
  search: null, // {query, requestedAt, whenType, dateType}
  rows: [],
  comparison: null,
  openIndex: -1,
};
const answers = new Map(); // one promise per (request, scenario), kept for the visit
let filtersPromise = null;
let searchCounter = 0;
let map = null;

// ---------- Fields ----------

const geocode = (text, signal) => searchPlaces(text, { near: ZONE_CENTER, box: ZONE_BOX, signal });
const fields = {
  origin: placeField({ input: $('from-input'), list: $('from-list'), search: geocode, onChange: (p) => { state.origin = p; drawMap(); } }),
  destination: placeField({ input: $('to-input'), list: $('to-list'), search: geocode, onChange: (p) => { state.destination = p; drawMap(); } }),
};
const statusOf = { origin: $('from-status'), destination: $('to-status') };

function setPlace(role, place) {
  state[role] = place;
  fields[role].set(place);
  drawMap();
}

$('swap').addEventListener('click', () => {
  const { origin, destination } = state;
  const texts = [$('from-input').value, $('to-input').value];
  setPlace('origin', destination);
  setPlace('destination', origin);
  if (!destination) $('from-input').value = texts[1];
  if (!origin) $('to-input').value = texts[0];
});

$('locate').addEventListener('click', () => {
  const button = $('locate');
  const say = (text) => { statusOf.origin.textContent = text; };
  if (!navigator.geolocation) {
    say('Votre navigateur ne donne pas votre position. Tapez une adresse ou touchez la carte.');
    return;
  }
  button.setAttribute('aria-busy', 'true');
  say('Recherche de votre position…');
  navigator.geolocation.getCurrentPosition((position) => {
    button.removeAttribute('aria-busy');
    const place = { label: 'Ma position', lat: position.coords.latitude, lon: position.coords.longitude };
    if (!inZone(place)) {
      say('Votre position est hors de la zone couverte (agglomération toulousaine).');
      return;
    }
    say('');
    setPlace('origin', place);
  }, (error) => {
    button.removeAttribute('aria-busy');
    say(error.code === 1
      ? 'Position refusée : autorisez-la dans votre navigateur, ou tapez une adresse.'
      : 'Position introuvable pour le moment. Tapez une adresse ou touchez la carte.');
  }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
});

async function pickOnMap(role, point) {
  const place = { label: 'Point sur la carte', ...point };
  setPlace(role, place);
  statusOf[role].textContent = '';
  if (state.view !== 'search') showView('search');
  try {
    const found = await reversePlace(point.lat, point.lon);
    if (found && state[role] === place) setPlace(role, { ...place, label: `Près de ${found.label}` });
  } catch {
    // Keep "Point sur la carte".
  }
}

// ---------- Time and mode ----------

const radioValue = (name) => document.querySelector(`input[name=${name}]:checked`).value;
const setRadio = (name, value) => { document.querySelector(`input[name=${name}][value=${value}]`).checked = true; };

function syncWhenInputs() {
  const type = radioValue('when');
  $('when-inputs').hidden = type === 'now';
  if (type !== 'now' && !$('when-time').value) {
    const soon = Math.ceil(Date.now() / 300000) * 300000; // next 5 minutes
    $('when-date').value = parisDateInput(soon);
    $('when-time').value = parisTimeInput(soon);
  }
}
document.querySelectorAll('input[name=when]').forEach((r) => r.addEventListener('change', syncWhenInputs));

// ---------- Scenario ----------

function setScenario(scenario) {
  state.scenario = scenario;
  storeScenario(scenario);
  document.querySelectorAll('[data-scenario]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.scenario === scenario)));
  $('projection').hidden = scenario !== '2028';
  if (state.search && state.view !== 'search') {
    showView('results');
    showResults();
  }
}
document.querySelectorAll('[data-scenario]').forEach((b) => b.addEventListener('click', () => setScenario(b.dataset.scenario)));

// ---------- Views ----------

function showView(view) {
  state.view = view;
  $('app').dataset.view = view;
  $('view-search').hidden = view !== 'search';
  $('view-results').hidden = view !== 'results';
  $('view-detail').hidden = view !== 'detail';
  $('sheet').scrollTop = 0;
  if (window.scrollY > 0) window.scrollTo(0, 0);
  drawMap();
}

function drawMap() {
  if (!map) return;
  let trip = null;
  if (state.view === 'detail') trip = state.rows[state.openIndex]?.trip || null;
  else if (state.view === 'results') trip = state.rows[0]?.trip || null;
  const origin = state.view === 'search' ? state.origin : state.search?.query.origin;
  const destination = state.view === 'search' ? state.destination : state.search?.query.destination;
  map.draw({ trip, origin, destination });
}

$('edit').addEventListener('click', () => {
  showView('search');
  $('from-input').focus();
});
$('back').addEventListener('click', () => {
  const index = state.openIndex;
  showView('results');
  $('results-list').querySelectorAll('.trip-button')[index]?.focus();
});

// ---------- Search ----------

function formError(text, input) {
  const box = $('form-error');
  box.textContent = text;
  box.hidden = false;
  input?.focus();
}

$('search-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  $('form-error').hidden = true;
  const [origin, destination] = await Promise.all(
    ['origin', 'destination'].map((role) => fields[role].resolve().catch(() => null)));
  if (origin) state.origin = origin;
  if (destination) state.destination = destination;
  if (!origin) {
    formError("Choisissez un départ : une adresse, un lieu, « Ma position » ou un point sur la carte.", $('from-input'));
    return;
  }
  if (!destination) {
    formError("Choisissez une arrivée : une adresse, un lieu ou un point sur la carte.", $('to-input'));
    return;
  }
  const whenType = radioValue('when');
  let requestedAt = Date.now();
  if (whenType !== 'now') {
    if (!$('when-date').value || !$('when-time').value) {
      formError("Indiquez le jour et l'heure.", $('when-date'));
      return;
    }
    requestedAt = parisLocalToMs($('when-date').value, $('when-time').value);
  }
  startSearch({
    origin,
    destination,
    when: { type: whenType === 'arrive' ? 'arrive' : 'depart', iso: toParisIso(requestedAt) },
    mode: radioValue('mode'),
  }, requestedAt, whenType);
});

function startSearch(query, requestedAt, whenType) {
  state.search = { query, requestedAt, whenType, dateType: query.when.type };
  state.rows = [];
  state.comparison = null;
  renderHeader();
  showView('results');
  showResults();
}

function renderHeader() {
  const { query, requestedAt, whenType } = state.search;
  $('res-from').textContent = query.origin.label;
  $('res-to').textContent = query.destination.label;
  const day = formatDay(requestedAt);
  const time = formatTime(requestedAt);
  let text = `${day}, départ à ${time}`;
  if (whenType === 'now') text = `${day}, départ maintenant (${time})`;
  if (whenType === 'arrive') text = `${day}, arrivée avant ${time}`;
  text += { transit: '', walk: ', à pied', bicycle: ', à vélo' }[query.mode];
  $('res-when').textContent = text;
}

/** Scenarios to ask: in 2028 by transit, the same request goes to both networks. */
function scenariosToAsk(scenario, mode) {
  if (scenario === 'actuel') return ['actuel'];
  return mode === 'transit' ? ['2028', 'actuel'] : ['2028'];
}

async function getFilters() {
  if (state.filters) return state.filters;
  filtersPromise ??= loadFilters().catch((error) => { filtersPromise = null; throw error; });
  state.filters = await filtersPromise;
  return state.filters;
}

async function loadFilters() {
  const placeholder = isPlaceholderApi(API_BASE);
  const urls = placeholder ? FILTERS_URLS.filter((u) => !u.startsWith(API_BASE)) : FILTERS_URLS;
  let serverUnreachable = false;
  for (const url of urls) {
    let response;
    try {
      response = await fetch(url, { credentials: 'omit', cache: 'no-cache' });
    } catch {
      if (url.startsWith(API_BASE)) serverUnreachable = true;
      continue; // try the next copy
    }
    if (!response.ok) continue;
    try {
      return parseScenarioFilters(await response.json());
    } catch (error) {
      console.warn(`unusable ${url}`, error);
    }
  }
  const kind = placeholder ? 'not-configured' : serverUnreachable ? 'unreachable' : 'filters';
  throw new ApiError(kind, 'no usable scenario-filters.json');
}

function getAnswer(query, scenario, filters) {
  const key = JSON.stringify([query, scenario]);
  if (!answers.has(key)) {
    const promise = (async () => {
      let data;
      if (state.demo) {
        const response = findRecorded(state.demo, query, scenario);
        if (!response) throw new ApiError('demo-unknown', 'request not recorded');
        data = checkGraphqlBody(response);
      } else {
        if (isPlaceholderApi(API_BASE)) throw new ApiError('not-configured', 'API_BASE is the example value');
        const variables = buildVariables({ ...query, filters: filters.scenarios[scenario].filters, request: filters.request });
        data = await postGraphql(GRAPHQL_URL, PLAN_QUERY, variables);
      }
      const plan = data.planConnection || {};
      return {
        trips: (plan.edges || []).filter((e) => e?.node).map((e) => toTrip(e.node, filters)),
        routingErrors: plan.routingErrors || [],
      };
    })();
    answers.set(key, promise);
    promise.catch(() => answers.delete(key)); // an error is never kept: "Réessayer" asks again
  }
  return answers.get(key);
}

function setStatus(text, loading = false) {
  const el = $('results-status');
  el.textContent = text;
  el.classList.toggle('loading', loading);
}

async function showResults() {
  const search = state.search;
  const scenario = state.scenario;
  const ticket = ++searchCounter;
  clear($('results-list'));
  $('results-notice').hidden = true;
  $('bars-help').hidden = true;
  $('results-title').textContent = scenario === '2028' ? 'Trajets en 2028' : "Trajets sur le réseau d'aujourd'hui";
  setStatus('Recherche en cours…', true);
  state.rows = [];
  state.comparison = null;
  drawMap();
  try {
    const filters = state.demo ? state.demo.filters : await getFilters();
    const asked = scenariosToAsk(scenario, search.query.mode);
    const settled = await Promise.allSettled(asked.map((s) => getAnswer(search.query, s, filters)));
    if (ticket !== searchCounter) return; // a newer search or scenario replaced this one
    if (settled[0].status === 'rejected') throw settled[0].reason;
    renderResults(search, scenario, filters, settled[0].value, settled[1]);
  } catch (error) {
    if (ticket !== searchCounter) return;
    console.warn(error);
    renderError(error);
  }
}

function renderResults(search, scenario, filters, main, today) {
  const { dateType, requestedAt, query } = search;
  const list = $('results-list');
  let comparison = null;
  let rows;
  let note = '';
  if (scenario === '2028' && query.mode === 'transit' && today?.status === 'fulfilled') {
    comparison = buildComparison({ future: main.trips, today: today.value.trips, filters, dateType, requestedAt });
    rows = comparison.rows;
    const help = $('bars-help');
    help.textContent = dateType === 'arrive'
      ? `Barres : temps porte à porte jusqu'à ${formatTime(requestedAt)}, attente comprise. Hachurée : meilleur trajet d'aujourd'hui ; pleine : ce trajet en 2028.`
      : `Barres : temps porte à porte depuis ${formatTime(requestedAt)}, attente comprise. Hachurée : meilleur trajet d'aujourd'hui ; pleine : ce trajet en 2028.`;
    help.hidden = !rows.length;
  } else {
    rows = sortTrips(uniqueTrips(main.trips), dateType).map((trip) => ({ trip }));
    if (scenario === '2028' && query.mode !== 'transit') {
      note = `${query.mode === 'walk' ? 'À pied' : 'À vélo'}, le réseau 2028 ne change rien : le trajet est le même qu'aujourd'hui.`;
    } else if (scenario === '2028') {
      note = "Comparaison avec aujourd'hui indisponible : le calcul sur le réseau actuel n'a pas abouti. Réessayez plus tard.";
    }
  }
  state.rows = rows;
  state.comparison = comparison;
  const count = rows.length;
  const where = scenario === '2028' ? 'en 2028' : "sur le réseau d'aujourd'hui";
  $('results-title').textContent = count
    ? `${count} trajet${count > 1 ? 's' : ''} ${scenario === '2028' && comparison ? `possible${count > 1 ? 's' : ''} ` : ''}${where}`
    : `Aucun trajet ${where}`;
  setStatus('');
  rows.forEach((row, index) => list.append(tripItem(row, { onOpen: () => openDetail(index), comparison, dateType })));
  if (!count) {
    showNotice($('results-notice'), {
      title: 'Aucun trajet trouvé',
      text: routingErrorMessage(main.routingErrors[0]?.code),
      actions: [h('button', { type: 'button', class: 'secondary-button', text: 'Modifier la recherche', onclick: () => $('edit').click() })],
    });
  } else if (note) {
    showNotice($('results-notice'), { title: 'À savoir', text: note, soft: true });
  }
  drawMap();
  $('results-title').focus({ preventScroll: true });
}

function showNotice(box, { title, text, actions = [], soft = false }) {
  clear(box).append(noticeBox({ title, text, actions }));
  box.classList.toggle('soft', soft);
  box.hidden = false;
}

function demoLink(text = 'Essayer la démonstration') {
  const url = new URL(location.href);
  url.searchParams.set('demo', '1');
  url.hash = '';
  return h('a', { href: url.pathname + url.search, text });
}

function renderError(error) {
  const kind = error instanceof ApiError ? error.kind : 'unreachable';
  const { title, text } = apiErrorMessage(kind);
  const actions = [];
  if (!['not-configured', 'demo-unknown'].includes(kind)) {
    actions.push(h('button', { type: 'button', class: 'secondary-button', text: 'Réessayer', onclick: () => showResults() }));
  }
  if (kind === 'demo-unknown') {
    actions.push(h('button', { type: 'button', class: 'secondary-button', text: 'Voir les trajets enregistrés', onclick: () => $('edit').click() }));
  } else if (!state.demo) actions.push(demoLink());
  setStatus('');
  $('results-title').textContent = 'Pas de résultat pour le moment';
  showNotice($('results-notice'), { title, text, actions });
  $('results-title').focus({ preventScroll: true });
}

function openDetail(index) {
  const row = state.rows[index];
  if (!row) return;
  state.openIndex = index;
  const { query, dateType } = state.search;
  const content = clear($('detail-content'));
  content.append(...detailView(row.trip, {
    originLabel: query.origin.label,
    destinationLabel: query.destination.label,
    compare: state.comparison ? { row, comparison: state.comparison, dateType } : null,
  }).filter(Boolean));
  showView('detail');
  $('detail-title').focus({ preventScroll: true });
}

// ---------- Demonstration mode ----------

function fillFromQuery(query) {
  setPlace('origin', query.origin.label ? query.origin : { ...query.origin, label: 'Départ enregistré' });
  setPlace('destination', query.destination.label ? query.destination : { ...query.destination, label: 'Arrivée enregistrée' });
  setRadio('when', query.when.type);
  $('when-date').value = parisDateInput(query.when.iso);
  $('when-time').value = parisTimeInput(query.when.iso);
  syncWhenInputs();
  setRadio('mode', query.mode);
}

async function initDemo() {
  try {
    const response = await fetch(DEMO_FILE, { credentials: 'omit', cache: 'no-cache' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.demo = parseDemo(await response.json());
  } catch (error) {
    console.warn('demo unavailable', error);
    const { title, text } = apiErrorMessage('demo-missing');
    const url = new URL(location.href);
    url.searchParams.delete('demo');
    showNotice($('search-notice'), { title, text, actions: [h('a', { href: url.pathname + url.search, text: 'Faire une vraie recherche' })] });
    return;
  }
  const banner = $('demo-banner');
  const exit = new URL(location.href);
  exit.searchParams.delete('demo');
  clear(banner).append(
    h('strong', { text: `Démonstration : trajets enregistrés le ${formatShortDate(state.demo.recordedAt)}.` }),
    " Ce sont de vraies réponses du calculateur, rejouées telles quelles. ",
    h('a', { href: exit.pathname + exit.search, text: 'Quitter la démonstration' }));
  banner.hidden = false;
  const list = clear($('demo-trips-list'));
  for (const search of recordedSearches(state.demo)) {
    const { when, mode } = search.query;
    const modeText = { transit: 'transports', walk: 'à pied', bicycle: 'à vélo' }[mode];
    const detail = `${formatDay(when.iso)}, ${when.type === 'arrive' ? 'arrivée avant' : 'départ à'} ${formatTime(when.iso)}, ${modeText}`;
    list.append(h('li', {}, h('button', {
      type: 'button',
      onclick: () => {
        fillFromQuery(search.query);
        startSearch(search.query, Date.parse(search.query.when.iso), search.query.when.type);
      },
    }, search.label, h('span', { text: detail }))));
  }
  $('demo-trips').hidden = false;
}

// ---------- Hypotheses and sources ----------

const dialog = $('hypotheses');
let dialogOpener = null;
function openHypotheses(opener) {
  dialogOpener = opener || document.activeElement;
  if (typeof dialog.showModal === 'function') {
    if (!dialog.open) dialog.showModal();
  } else dialog.setAttribute('open', '');
  $('hyp-close').focus();
}
document.addEventListener('click', (event) => {
  const link = event.target.closest('[data-open-hypotheses]');
  if (!link) return;
  event.preventDefault();
  openHypotheses(link);
});
$('hyp-close').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
dialog.addEventListener('close', () => {
  if (location.hash === '#hypotheses') history.replaceState(null, '', location.pathname + location.search);
  dialogOpener?.focus?.();
});

// ---------- Start ----------

setScenario(state.scenario);
syncWhenInputs();
if (location.hash === '#hypotheses') openHypotheses();
if (wantsDemo) initDemo();
// The map library (about 1 MB) is loaded once the page is shown.
const startMap = () => {
  map = createMap({ container: $('map'), message: $('map-message'), legend: $('map-legend'), onPick: pickOnMap });
  drawMap();
};
if ('requestIdleCallback' in window) requestIdleCallback(startMap, { timeout: 1500 });
else setTimeout(startMap, 200);
