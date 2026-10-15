import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  ApiError, assertNoNull, buildModes, buildVariables, checkGraphqlBody, DEFAULT_REQUEST, isPlaceholderApi,
  mergeRequest, modeOfVariables, PLAN_QUERY, postGraphql, TRIP_MODES,
} from '../js/otp.js';
import { apiErrorMessage, routingErrorMessage } from '../js/messages.js';

const root = new URL('../../', import.meta.url);
const scenariosConfig = JSON.parse(readFileSync(new URL('config/scenarios.json', root), 'utf8'));
const filters = JSON.parse(readFileSync(new URL('site/tests/fixtures/synthetic-scenario-filters.json', root), 'utf8'));

const origin = { label: 'Gare de Colomiers', lat: 43.6118, lon: 1.3366 };
const destination = { label: 'Diagora, Labège', lat: 43.5462, lon: 1.5128 };
const when = { type: 'depart', iso: '2026-10-20T08:30:00+02:00' };

function containsNull(value) {
  if (value === null || value === undefined) return true;
  if (Array.isArray(value)) return value.some(containsNull);
  if (typeof value === 'object') return Object.values(value).some(containsNull);
  return false;
}

test('les modes par défaut du site sont ceux de config/scenarios.json', () => {
  const request = Object.fromEntries(Object.entries(scenariosConfig.request).filter(([k]) => !k.startsWith('_')));
  assert.deepEqual({ ...DEFAULT_REQUEST }, request);
});

test('jamais de modes nul, jamais de valeur nulle, pour chaque mode et chaque scénario', () => {
  for (const mode of TRIP_MODES) {
    for (const scenario of ['actuel', '2028']) {
      for (const type of ['depart', 'arrive']) {
        const variables = buildVariables({
          origin, destination, when: { ...when, type }, mode, filters: filters.scenarios[scenario].filters, request: filters.request,
        });
        assert.ok(variables.modes && typeof variables.modes === 'object', `${mode} ${scenario}`);
        assert.equal(containsNull(variables), false, JSON.stringify(variables));
      }
    }
  }
});

test('transports en commun : modes explicites, comme reference_trips.build_modes', () => {
  assert.deepEqual(buildModes('transit'), {
    direct: ['WALK'],
    transit: {
      access: ['WALK'], egress: ['WALK'], transfer: ['WALK'],
      transit: [{ mode: 'BUS' }, { mode: 'TRAM' }, { mode: 'SUBWAY' }, { mode: 'RAIL' }, { mode: 'GONDOLA' }],
    },
  });
  assert.deepEqual(buildModes('walk'), { directOnly: true, direct: ['WALK'] });
  assert.deepEqual(buildModes('bicycle'), { directOnly: true, direct: ['BICYCLE'] });
  assert.throws(() => buildModes('car'));
});

test('les listes du serveur remplacent les valeurs par défaut, sauf si elles sont vides ou invalides', () => {
  assert.deepEqual(mergeRequest({ transit_modes: ['BUS', 'RAIL'] }).transit_modes, ['BUS', 'RAIL']);
  assert.deepEqual(mergeRequest({ transit_modes: [] }).transit_modes, DEFAULT_REQUEST.transit_modes);
  assert.deepEqual(mergeRequest({ transit_modes: null }).transit_modes, DEFAULT_REQUEST.transit_modes);
  assert.deepEqual(mergeRequest(null), { ...DEFAULT_REQUEST });
});

test('variables : départ ou arrivée, préférences seulement s\'il y a des filtres', () => {
  const depart = buildVariables({ origin, destination, when, mode: 'transit', filters: [] });
  assert.deepEqual(depart.dateTime, { earliestDeparture: '2026-10-20T08:30:00+02:00' });
  assert.equal('preferences' in depart, false);
  const arrive = buildVariables({ origin, destination, when: { type: 'arrive', iso: when.iso }, mode: 'transit', filters: filters.scenarios.actuel.filters });
  assert.deepEqual(arrive.dateTime, { latestArrival: '2026-10-20T08:30:00+02:00' });
  assert.deepEqual(arrive.preferences, { transit: { filters: [{ exclude: [{ agencies: ['futur:SYNTH_FUT'] }] }] } });
  assert.deepEqual(depart.origin, { location: { coordinate: { latitude: 43.6118, longitude: 1.3366 } }, label: 'Gare de Colomiers' });
});

test('un lieu sans libellé n\'envoie pas de libellé nul ; un lieu sans coordonnées est refusé', () => {
  const v = buildVariables({ origin: { lat: 43.6, lon: 1.44 }, destination, when, mode: 'walk' });
  assert.equal('label' in v.origin, false);
  assert.throws(() => buildVariables({ origin: { label: 'x' }, destination, when, mode: 'walk' }));
  assert.throws(() => assertNoNull({ modes: null }), /variables.modes is null/);
});

test('la requête déclare modes non nul', () => {
  assert.match(PLAN_QUERY, /\$modes: PlanModesInput!/);
  assert.match(PLAN_QUERY, /planConnection\(/);
});

test('le mode se relit dans les variables (mode démonstration)', () => {
  for (const mode of TRIP_MODES) {
    assert.equal(modeOfVariables(buildVariables({ origin, destination, when, mode })), mode);
  }
});

test('adresse d\'exemple du serveur détectée', () => {
  assert.equal(isPlaceholderApi('https://SOUS-DOMAINE.duckdns.org'), true);
  assert.equal(isPlaceholderApi(''), true);
  assert.equal(isPlaceholderApi('https://toulouse-demain.duckdns.org'), false);
});

test('erreurs GraphQL et HTTP classées pour l\'interface', async () => {
  assert.deepEqual(checkGraphqlBody({ data: { a: 1 } }), { a: 1 });
  assert.throws(() => checkGraphqlBody({ errors: [{ message: 'boom' }] }), (e) => e.kind === 'bad-response');
  const reply = (status, body) => async () => ({ status, ok: status < 400, json: async () => body });
  await assert.rejects(postGraphql('x', 'q', {}, { fetchImpl: reply(429) }), (e) => e.kind === 'rate-limited');
  await assert.rejects(postGraphql('x', 'q', {}, { fetchImpl: reply(502) }), (e) => e.kind === 'server');
  await assert.rejects(postGraphql('x', 'q', {}, { fetchImpl: async () => { throw new TypeError('Failed to fetch'); } }),
    (e) => e instanceof ApiError && e.kind === 'unreachable');
  const data = await postGraphql('x', 'q', {}, { fetchImpl: reply(200, { data: { planConnection: { edges: [] } } }) });
  assert.deepEqual(data, { planConnection: { edges: [] } });
});

test('la requête part en POST JSON, sans cookie', async () => {
  let seen;
  const fetchImpl = async (url, init) => { seen = { url, init }; return { status: 200, ok: true, json: async () => ({ data: {} }) }; };
  const variables = buildVariables({ origin, destination, when, mode: 'walk' });
  await postGraphql('https://api.example/otp/gtfs/v1', PLAN_QUERY, variables, { fetchImpl });
  assert.equal(seen.init.method, 'POST');
  assert.equal(seen.init.credentials, 'omit');
  assert.equal(seen.init.headers['Content-Type'], 'application/json');
  assert.deepEqual(JSON.parse(seen.init.body).variables, variables);
});

test('aucun trajet : message selon le code d\'erreur d\'OTP ; chaque erreur a un message', () => {
  const noTrip = JSON.parse(readFileSync(new URL('site/tests/fixtures/synthetic-plan-no-trip.json', root), 'utf8'));
  const data = checkGraphqlBody(noTrip);
  assert.equal(data.planConnection.edges.length, 0);
  assert.match(routingErrorMessage(data.planConnection.routingErrors[0].code), /Aucun trajet trouvé/);
  assert.match(routingErrorMessage('OUTSIDE_SERVICE_PERIOD'), /trois prochaines semaines/);
  for (const kind of ['not-configured', 'unreachable', 'rate-limited', 'timeout', 'server', 'bad-response', 'filters', 'demo-missing', 'demo-unknown']) {
    const { title, text } = apiErrorMessage(kind);
    assert.ok(title && text, kind);
  }
});
