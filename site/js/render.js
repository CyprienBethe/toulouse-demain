// Building the results list, the double bar and the detail view.

import { badgeColors, contrast, WHITE } from './colors.js';
import { h, srOnly } from './dom.js';
import { formatDuration, formatDurationLong, formatTime } from './format.js';
import { clockIcon, modeIcon, verdictIcon } from './icons.js';
import { badgeText, buildSteps, lineName, summaryText, transitLegs } from './itinerary.js';

/** Line badge: route colour, readable text, dashed outline for a line not built yet. */
export function badge(leg) {
  const colors = badgeColors(leg.route?.color);
  const classes = ['badge'];
  if (leg.future) classes.push('future');
  else if (colors.outlined) classes.push('outlined');
  return h('span', { class: classes.join(' '), vars: { '--badge-bg': colors.background, '--badge-fg': colors.text } },
    modeIcon(leg.route?.mode || leg.mode),
    h('span', { 'aria-hidden': 'true', text: badgeText(leg) }),
    srOnly(`${lineName(leg)}${leg.future ? ', ligne en projet' : ''}`));
}

/** Colour of a line on the map and on the detail rail (visible on white). */
export function lineColor(leg) {
  const { background } = badgeColors(leg.route?.color);
  return contrast(background, WHITE) < 1.5 ? '#6F84A3' : background;
}

function tripLines(trip) {
  return h('span', { class: 'trip-lines' },
    transitLegs(trip).map(badge),
    h('span', { class: 'trip-summary', text: summaryText(trip) }));
}

/** A clock time with tabular digits and a normal colon: <span class="clock">8<span class="colon">:</span>31</span>. */
export function clock(ms) {
  const [hours, minutes] = formatTime(ms).split(':');
  return h('span', { class: 'clock' }, hours, h('span', { class: 'colon', text: ':' }), minutes);
}

function timeRange(trip, attrs = {}) {
  return h('span', attrs, clock(trip.start), ' – ', clock(trip.end));
}

function spokenTrip(trip) {
  return `Départ ${formatTime(trip.start)}, arrivée ${formatTime(trip.end)}, ${formatDurationLong(trip.minutes)}.`;
}

/** The double bar: today (hatched) and this trip (full), on the list's scale. */
export function barsBlock(row, { scale, dateType, best }) {
  const arrive = dateType === 'arrive';
  const timeOf = (t) => formatTime(arrive ? t.start : t.end);
  const word = arrive ? 'départ' : 'arrivée';
  const width = (minutes) => `${Math.max(2, Math.round((minutes / scale) * 1000) / 10)}%`;
  const spokenBar = (minutes) => formatDurationLong(minutes) + (arrive ? " avant l'heure demandée" : " après l'heure demandée");
  const parts = [];
  const spoken = [];
  if (row.todayBar !== null && best) {
    parts.push(
      h('span', { class: 'bar-label', text: "Aujourd'hui" }),
      h('span', { class: 'bar-track' }, h('span', { class: 'bar today', vars: { '--w': width(row.todayBar) } })),
      h('span', { class: 'bar-value' }, clock(arrive ? best.start : best.end)),
    );
    spoken.push(`Aujourd'hui, meilleur trajet : ${word} à ${timeOf(best)}, ${spokenBar(row.todayBar)}.`);
  }
  parts.push(
    h('span', { class: 'bar-label strong', text: '2028' }),
    h('span', { class: 'bar-track' }, h('span', { class: 'bar future', vars: { '--w': width(row.tripBar) } })),
    h('span', { class: 'bar-value strong' }, clock(arrive ? row.trip.start : row.trip.end)),
  );
  spoken.push(`En 2028, ce trajet : ${word} à ${timeOf(row.trip)}, ${spokenBar(row.tripBar)}.`);
  return h('span', { class: 'bars', role: 'img', 'aria-label': spoken.join(' ') }, parts);
}

export function verdictLine(row) {
  return h('span', { class: `verdict ${row.verdict}` }, verdictIcon(row.verdict), h('span', { text: row.label }));
}

/**
 * One result. `row` is {trip} for today, or a comparison row for 2028
 * (with todayBar, tripBar, verdict, label). `onOpen` opens the detail.
 */
export function tripItem(row, { onOpen, comparison, dateType }) {
  const { trip } = row;
  const button = h('button', { type: 'button', class: 'trip-button', onclick: () => onOpen(row) },
    srOnly(spokenTrip(trip)),
    h('span', { class: 'trip-top', 'aria-hidden': 'true' },
      timeRange(trip, { class: 'trip-times' }),
      h('span', { class: 'trip-duration num', text: formatDuration(trip.minutes) })),
    tripLines(trip),
    comparison ? barsBlock(row, { scale: comparison.scale, dateType, best: comparison.best }) : null,
    comparison ? verdictLine(row) : null);
  return h('li', {}, button);
}

/** A message box: title, text and optional action buttons or links. */
export function noticeBox({ title, text, actions = [] }) {
  return h('div', { class: 'notice-inner' },
    h('h3', { text: title }),
    h('p', { text }),
    actions.length ? h('div', { class: 'actions' }, actions) : null);
}

function placeStep(step) {
  return h('li', { class: `step place${step.end ? ' end' : ''}` },
    h('span', { class: 'step-time' }, clock(step.time)),
    h('span', { class: 'step-rail', 'aria-hidden': 'true' }),
    h('div', { class: 'step-body' }, h('strong', { text: step.title }), h('span', { class: 'step-sub', text: step.sub })));
}

function walkStep(step) {
  return h('li', { class: 'step walk' },
    h('span', { class: 'step-time' }),
    h('span', { class: 'step-rail', 'aria-hidden': 'true' }),
    h('div', { class: 'step-body' },
      h('span', {}, h('strong', { text: step.title }), step.sub ? ` · ${step.sub}` : ''),
      step.wait ? h('span', { class: 'wait' }, clockIcon(), h('span', { text: step.wait })) : null));
}

let stopsCounter = 0;
function rideStep(step) {
  const { leg } = step;
  const body = h('div', { class: 'step-body' },
    h('div', { class: 'ride-line' },
      badge(leg),
      step.direction ? h('strong', { text: `Direction ${step.direction}` }) : null,
      leg.future ? h('span', { class: 'future-tag', text: 'En projet' }) : null),
    h('span', { class: 'step-sub', text: step.sub }));
  if (step.stops.length) {
    const id = `stops-${++stopsCounter}`;
    const count = step.stops.length;
    const label = (open) => `${open ? 'Masquer' : 'Voir'} ${count > 1 ? `les ${count} arrêts intermédiaires` : "l'arrêt intermédiaire"}`;
    const list = h('ul', { class: 'stops', id, hidden: true },
      step.stops.map((s) => h('li', {}, h('span', { class: 'stop-time' }, s.time ? clock(s.time) : ''), h('span', { text: s.name }))));
    const toggle = h('button', { type: 'button', class: 'stops-toggle', 'aria-expanded': 'false', 'aria-controls': id, text: label(false) });
    toggle.addEventListener('click', () => {
      const open = toggle.getAttribute('aria-expanded') !== 'true';
      toggle.setAttribute('aria-expanded', String(open));
      toggle.textContent = label(open);
      list.hidden = !open;
    });
    body.append(toggle, list);
  }
  return h('li', { class: `step ride${leg.future ? ' future' : ''}`, vars: { '--line-color': lineColor(leg) } },
    h('span', { class: 'step-time' }),
    h('span', { class: 'step-rail', 'aria-hidden': 'true' }),
    body);
}

/**
 * Detail of a trip: summary, (2028) comparison with today, and the steps.
 * `compare` is null or {row, comparison, dateType}.
 */
export function detailView(trip, { originLabel, destinationLabel, compare }) {
  const head = h('div', { class: 'detail-head' },
    h('h2', { id: 'detail-title', tabindex: '-1' },
      srOnly(spokenTrip(trip)),
      timeRange(trip, { 'aria-hidden': 'true' }),
      h('span', { class: 'num', 'aria-hidden': 'true', text: formatDuration(trip.minutes) })),
    tripLines(trip),
    h('p', { class: 'detail-route', text: `${originLabel} → ${destinationLabel}` }));

  let card = null;
  if (compare?.row && compare.comparison) {
    const { row, comparison, dateType } = compare;
    const best = comparison.best;
    card = h('section', { class: 'compare-card', 'aria-labelledby': 'compare-title' },
      h('h3', { id: 'compare-title', text: "Comparé à aujourd'hui" }),
      barsBlock(row, { scale: Math.max(row.todayBar ?? 0, row.tripBar, 1), dateType, best }),
      verdictLine(row),
      best ? h('p', { class: 'today-best' },
        h('span', {}, "Meilleur trajet d'aujourd'hui : ", timeRange(best), `, ${formatDuration(best.minutes)}`),
        transitLegs(best).map(badge)) : null);
  }

  const steps = buildSteps(trip, originLabel, destinationLabel).map((step) => {
    if (step.type === 'place') return placeStep(step);
    if (step.type === 'walk') return walkStep(step);
    return rideStep(step);
  });
  return [head, card, h('ol', { class: 'timeline', 'aria-label': 'Étapes du trajet' }, steps)];
}
