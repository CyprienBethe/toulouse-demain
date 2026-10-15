import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildComparison, comparisonLabel, mergeAlternatives, sortTrips } from '../js/compare.js';
import { formatTime } from '../js/format.js';
import { toTrip } from '../js/itinerary.js';
import { parseScenarioFilters } from '../js/scenarios.js';

const fixture = (name) => JSON.parse(readFileSync(new URL(`fixtures/${name}`, import.meta.url), 'utf8'));
const plain = (s) => s.replace(/ /g, ' ');
const filters = parseScenarioFilters(fixture('synthetic-scenario-filters.json'));
const trips = (name) => fixture(name).data.planConnection.edges.map((e) => toTrip(e.node, filters));
const today = trips('synthetic-plan-actuel.json');
const future = trips('synthetic-plan-2028.json');
const requestedAt = Date.parse('2026-10-20T08:30:00+02:00');
const lines = (trip) => trip.legs.filter((l) => l.transit).map((l) => l.route.shortName).join('+');
const range = (trip) => `${formatTime(trip.start)}-${formatTime(trip.end)}`;

test('cas réel validé par Cyprien : Colomiers → Labège, départ 8:30', () => {
  const { rows, best, scale } = buildComparison({ future, today, filters, dateType: 'depart', requestedAt });
  // Best trip of today: the train at 8:43, arrival 9:28 (45 min).
  assert.equal(range(best), '8:43-9:28');
  assert.equal(best.minutes, 45);

  const c = rows.find((r) => lines(r.trip) === 'C');
  assert.equal(range(c.trip), '8:31-9:19');
  assert.equal(c.trip.minutes, 48);
  assert.equal(plain(c.label), "Arrivée 9 min plus tôt qu'aujourd'hui");
  assert.equal(c.verdict, 'better');
  // Door to door from 8:30, waiting included: 58 min today, 49 min with metro C.
  assert.equal(c.todayBar, 58);
  assert.equal(c.tripBar, 49);

  // The train, still possible in 2028, is listed too, once, "as today".
  const trains = rows.filter((r) => range(r.trip) === '8:43-9:28');
  assert.equal(trains.length, 1);
  assert.equal(trains[0].existsToday, true);
  assert.equal(trains[0].label, "Comme aujourd'hui");
  assert.equal(trains[0].tripBar, 58);
  assert.equal(scale, 88);
});

test('liste 2028 : trajets 2028 + trajets d\'aujourd\'hui encore possibles, sans doublon, triés par arrivée', () => {
  const rows = mergeAlternatives({ future, today, filters, dateType: 'depart' });
  assert.deepEqual(rows.map((r) => `${range(r.trip)} ${lines(r.trip)}`), [
    '8:31-9:19 C',
    '8:43-9:28 TER+TER',
    '8:36-9:35 TER+A+B',
    '9:13-9:58 TER',
  ]);
  // Today's trip on Tisséo line B (excluded in 2028: replaced by the extended B) is not listed.
  assert.equal(rows.some((r) => r.trip.legs.some((l) => l.route?.gtfsId === 'tisseo:SYNTH_B')), false);
  assert.deepEqual(rows.map((r) => r.existsToday), [false, true, false, true]);
});

test('écart honnête quand 2028 est moins bien, et « Comme aujourd\'hui » pour un trajet qui existe déjà', () => {
  const { rows } = buildComparison({ future, today, filters, dateType: 'depart', requestedAt });
  const extendedB = rows.find((r) => range(r.trip) === '8:36-9:35');
  assert.equal(plain(extendedB.label), "Arrivée 7 min plus tard qu'aujourd'hui");
  assert.equal(extendedB.verdict, 'worse');
  const laterTrain = rows.find((r) => range(r.trip) === '9:13-9:58');
  assert.equal(laterTrain.label, "Comme aujourd'hui");
  assert.equal(laterTrain.todayBar, 58);
  assert.equal(laterTrain.tripBar, 88);
});

test('écart de moins d\'une minute : « Comme aujourd\'hui »', () => {
  const shift = (trip, seconds) => ({ ...trip, end: trip.end + seconds * 1000, existsToday: false });
  const c = future[0];
  const best = { ...c, end: c.end + 40 * 1000 }; // same shown minute (9:19:40)
  const { rows } = buildComparison({ future: [shift(c, 0)], today: [best], filters, dateType: 'depart', requestedAt });
  assert.equal(rows[0].label, "Comme aujourd'hui");
  assert.equal(rows[0].delta, 0);
});

test('« arriver à » : on compare les heures de départ, tri par départ décroissant', () => {
  const deadline = Date.parse('2026-10-20T10:00:00+02:00');
  const { rows, best } = buildComparison({ future, today, filters, dateType: 'arrive', requestedAt: deadline });
  assert.equal(range(best), '9:13-9:58');
  assert.deepEqual(rows.map((r) => formatTime(r.trip.start)), ['9:13', '8:43', '8:36', '8:31']);
  const c = rows.find((r) => lines(r.trip) === 'C');
  assert.equal(plain(c.label), "Départ 42 min plus tôt qu'aujourd'hui");
  assert.equal(c.todayBar, 47);
  assert.equal(c.tripBar, 89);
  assert.equal(plain(comparisonLabel({ verdict: 'better', delta: 9 }, 'arrive')), "Départ 9 min plus tard qu'aujourd'hui");
});

test('sans trajet aujourd\'hui : pas de barre « aujourd\'hui », libellé explicite', () => {
  const { rows, best } = buildComparison({ future, today: [], filters, dateType: 'depart', requestedAt });
  assert.equal(best, null);
  const c = rows.find((r) => lines(r.trip) === 'C');
  assert.equal(c.todayBar, null);
  assert.equal(c.label, "Aucun trajet aujourd'hui pour cette demande");
  const train = rows.find((r) => range(r.trip) === '8:43-9:28');
  assert.equal(train.label, "Comme aujourd'hui");
});

test('écarts de plus d\'une heure', () => {
  assert.equal(plain(comparisonLabel({ verdict: 'better', delta: 65 }, 'depart')), "Arrivée 1 h 05 plus tôt qu'aujourd'hui");
});

test('tri stable : à arrivée égale, le départ le plus tardif d\'abord', () => {
  const a = { start: 1, end: 10 };
  const b = { start: 5, end: 10 };
  assert.deepEqual(sortTrips([a, b], 'depart'), [b, a]);
});
