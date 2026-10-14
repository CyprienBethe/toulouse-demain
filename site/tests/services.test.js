// Geocoder, demonstration mode, scenario filters and local storage.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { findRecorded, parseDemo, recordedSearches } from '../js/demo.js';
import { parsePlaces, reverseUrl, searchPlaces, searchUrl } from '../js/geocode.js';
import { allowedIn, feedOf, parseScenarioFilters } from '../js/scenarios.js';
import { storedScenario, storeScenario } from '../js/storage.js';
import { ZONE_BOX } from '../config.js';

const fixture = (name) => JSON.parse(readFileSync(new URL(`fixtures/${name}`, import.meta.url), 'utf8'));
const geocoder = fixture('synthetic-geocoder.json');

test('géocodeur : adresse officielle de la Géoplateforme, biais vers Toulouse', () => {
  const url = new URL(searchUrl('gare colomiers', { near: { lat: 43.6045, lon: 1.444 } }));
  assert.equal(url.origin + url.pathname, 'https://data.geopf.fr/geocodage/search');
  assert.equal(url.searchParams.get('q'), 'gare colomiers');
  assert.equal(url.searchParams.get('autocomplete'), '1');
  assert.equal(url.searchParams.get('index'), 'address,poi');
  assert.equal(url.searchParams.get('lat'), '43.6045');
  assert.equal(new URL(reverseUrl(43.6, 1.44)).pathname, '/geocodage/reverse');
});

test('géocodeur : points d\'intérêt et adresses, hors zone retirés', () => {
  const places = parsePlaces(geocoder.colomiers, ZONE_BOX);
  assert.deepEqual(places.map((p) => p.label), ['Gare de Colomiers', 'Allée du Comminges, Colomiers']);
  assert.equal(places[0].lat, 43.6118);
  assert.equal(parsePlaces(geocoder.colomiers).length, 3);
  assert.deepEqual(parsePlaces(geocoder.reverse).map((p) => p.label), ['1 Place du Capitole, Toulouse']);
  assert.deepEqual(parsePlaces({}), []);
});

test('géocodeur : index combiné refusé (HTTP 400) → adresses seules', async () => {
  const urls = [];
  const fetchImpl = async (url) => {
    urls.push(url);
    if (url.includes('poi')) return { ok: false, status: 400, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => geocoder.labege };
  };
  const places = await searchPlaces('diagora', { fetchImpl });
  assert.equal(urls.length, 2);
  assert.equal(new URL(urls[1]).searchParams.get('index'), 'address');
  assert.deepEqual(places.map((p) => p.label), ['Diagora, Labège']);
});

test('filtres de scénario : fichier lu et validé', () => {
  const filters = parseScenarioFilters(fixture('synthetic-scenario-filters.json'));
  assert.equal(filters.scenarios.actuel.excludedAgencies.has('futur:SYNTH_FUT'), true);
  assert.equal(filters.scenarios['2028'].excludedRoutes.has('tisseo:SYNTH_B'), true);
  assert.throws(() => parseScenarioFilters({ scenarios: { actuel: { filters: [] } } }));
  assert.throws(() => parseScenarioFilters(null));
  const leg = (agency, route) => ({ agency: { gtfsId: agency }, route: { gtfsId: route } });
  assert.equal(feedOf(leg('futur:X', 'futur:FUT_C')), 'futur');
  assert.equal(allowedIn({ legs: [leg('tisseo:1', 'tisseo:SYNTH_B')] }, filters.scenarios['2028']), false);
  assert.equal(allowedIn({ legs: [leg('sncf:1', 'sncf:T')] }, filters.scenarios['2028']), true);
  assert.equal(allowedIn({ legs: [{ mode: 'WALK' }] }, filters.scenarios.actuel), true);
});

test('démonstration : contrat du fichier, recherche des réponses enregistrées', () => {
  const demo = parseDemo(fixture('synthetic-demo-responses.json'));
  assert.equal(demo.recordedAt, Date.parse('2026-10-19T06:10:00Z'));
  const searches = recordedSearches(demo);
  assert.equal(searches.length, 1);
  assert.equal(searches[0].label, 'Gare de Colomiers → Diagora, Labège');
  const query = searches[0].query;
  assert.deepEqual(query.when, { type: 'depart', iso: '2026-10-20T08:30:00+02:00' });
  assert.equal(query.mode, 'transit');
  assert.ok(findRecorded(demo, query, 'actuel'));
  assert.ok(findRecorded(demo, query, '2028'));
  assert.notEqual(findRecorded(demo, query, 'actuel'), findRecorded(demo, query, '2028'));
  // Another time, another mode or a far place: not recorded.
  assert.equal(findRecorded(demo, { ...query, when: { type: 'depart', iso: '2026-10-20T09:30:00+02:00' } }, '2028'), null);
  assert.equal(findRecorded(demo, { ...query, mode: 'walk' }, '2028'), null);
  assert.equal(findRecorded(demo, { ...query, origin: { lat: 43.7, lon: 1.4 } }, '2028'), null);
  assert.throws(() => parseDemo({ requests: [] }));
  assert.throws(() => parseDemo({}));
});

test('scénario mémorisé : « Aujourd\'hui » à la première visite, le site marche sans stockage', () => {
  const memory = new Map();
  const storage = { getItem: (k) => (memory.has(k) ? memory.get(k) : null), setItem: (k, v) => memory.set(k, v) };
  assert.equal(storedScenario(storage), 'actuel');
  assert.equal(storeScenario('2028', storage), true);
  assert.equal(storedScenario(storage), '2028');
  const broken = { getItem: () => { throw new Error('SecurityError'); }, setItem: () => { throw new Error('QuotaExceeded'); } };
  assert.equal(storedScenario(broken), 'actuel');
  assert.equal(storeScenario('2028', broken), false);
  memory.set('toulouse-demain.scenario', 'nimporte');
  assert.equal(storedScenario(storage), 'actuel');
});
