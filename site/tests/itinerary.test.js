import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { formatTime } from '../js/format.js';
import { badgeText, buildSteps, lineName, summaryText, toTrip } from '../js/itinerary.js';
import { decodePolyline, encodePolyline } from '../js/polyline.js';
import { parseScenarioFilters } from '../js/scenarios.js';

const fixture = (name) => JSON.parse(readFileSync(new URL(`fixtures/${name}`, import.meta.url), 'utf8'));
const plain = (s) => s.replace(/ /g, ' ');
const filters = parseScenarioFilters(fixture('synthetic-scenario-filters.json'));
const [metroC, , extendedB] = fixture('synthetic-plan-2028.json').data.planConnection.edges.map((e) => toTrip(e.node, filters));
const [train] = fixture('synthetic-plan-actuel.json').data.planConnection.edges.map((e) => toTrip(e.node, filters));

test('résumé d\'un trajet en mots', () => {
  assert.equal(plain(summaryText(metroC)), 'Métro C direct, 9 min à pied');
  assert.equal(plain(summaryText(train)), '1 correspondance, 11 min à pied');
  const walkOnly = { legs: [{ mode: 'WALK', transit: false, distance: 1380 }], walkMinutes: 17 };
  assert.equal(plain(summaryText(walkOnly)), 'À pied, 1,4 km');
  const bike = { legs: [{ mode: 'BICYCLE', transit: false, distance: 5230 }], walkMinutes: 0 };
  assert.equal(plain(summaryText(bike)), 'À vélo, 5,2 km');
});

test('lignes futures repérées (flux futur ou ligne exclue du réseau actuel)', () => {
  assert.deepEqual(metroC.legs.filter((l) => l.transit).map((l) => l.future), [true]);
  assert.deepEqual(extendedB.legs.filter((l) => l.transit).map((l) => [l.route.shortName, l.future]), [['TER', false], ['A', false], ['B', true]]);
  assert.equal(train.legs.some((l) => l.future), false);
});

test('noms de ligne : mode et nom court', () => {
  const leg = (mode, shortName) => ({ mode, route: { mode, shortName } });
  assert.equal(lineName(leg('SUBWAY', 'C')), 'Métro C');
  assert.equal(lineName(leg('BUS', '79')), 'Bus 79');
  assert.equal(lineName(leg('RAIL', 'TER')), 'TER');
  assert.equal(lineName(leg('RAIL', '')), 'Train');
  assert.equal(lineName(leg('GONDOLA', 'TLO')), 'Téléphérique TLO');
  assert.equal(badgeText(leg('RAIL', '')), 'Train');
  assert.equal(badgeText(leg('TRAM', 'T1')), 'T1');
});

test('étapes du détail : marcher, attendre, monter, descendre', () => {
  const steps = buildSteps(metroC, 'Gare de Colomiers', 'Diagora, Labège');
  const summary = steps.map((s) => [s.type, s.time ? formatTime(s.time) : '', plain(s.title), plain(s.sub || ''), plain(s.wait || '')]);
  assert.deepEqual(summary, [
    ['place', '8:31', 'Gare de Colomiers', 'Départ', ''],
    ['walk', '', 'Marcher 3 min', "220 m jusqu'à Colomiers - Gare", ''],
    ['place', '8:34', 'Colomiers - Gare', 'Monter : Métro C', ''],
    ['ride', '', 'Métro C', '4 arrêts · 39 min', ''],
    ['place', '9:13', 'Diagora', 'Descendre', ''],
    ['walk', '', 'Marcher 6 min', "400 m jusqu'à Diagora, Labège", ''],
    ['place', '9:19', 'Diagora, Labège', 'Arrivée', ''],
  ]);
  assert.equal(steps[3].direction, 'Labège - Gare');
  assert.equal(steps[3].stops.length, 3);
});

test('une correspondance est une étape « Marcher » avec son temps d\'attente', () => {
  const steps = buildSteps(train, 'Gare de Colomiers', 'Diagora, Labège');
  const walk = steps.find((s) => s.type === 'walk' && s.wait);
  assert.equal(plain(walk.title), 'Marcher 2 min');
  assert.equal(plain(walk.wait), 'Attendre 6 min');
  // The trip starts on the train: the boarding step is also the departure.
  assert.equal(steps[0].sub, 'Départ, monter : TER');
});

test('deux trajets identiques ont la même clé, deux trajets différents non', () => {
  const again = toTrip(fixture('synthetic-plan-2028.json').data.planConnection.edges[1].node, filters);
  assert.equal(again.key, train.key);
  assert.notEqual(metroC.key, train.key);
});

test('polyline : exemple de référence de Google, aller-retour', () => {
  assert.deepEqual(decodePolyline('_p~iF~ps|U_ulLnnqC_mqNvxq`@'), [[-120.2, 38.5], [-120.95, 40.7], [-126.453, 43.252]]);
  const coords = [[1.4442, 43.6047], [1.45, 43.61], [1.3366, 43.6118]];
  assert.deepEqual(decodePolyline(encodePolyline(coords)), coords);
  assert.deepEqual(decodePolyline(''), []);
  assert.throws(() => decodePolyline('_p~iF~ps|U_'));
});
