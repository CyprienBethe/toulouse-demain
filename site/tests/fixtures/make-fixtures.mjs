// Writes the SYNTHETIC test fixtures of the site (node tests/fixtures/make-fixtures.mjs).
//
// Nothing here comes from the real OTP server: lines, ids, times and
// coordinates are made up, close to the case validated by Cyprien
// (Colomiers → Labège, departure 8:30: today a train leaves at 8:43 and
// arrives at 9:28; in 2028 metro C leaves at 8:31 and arrives at 9:19).
// Coordinates are rough positions, only used to draw something on the map.
// These files live in site/tests/, which is never published.

import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { encodePolyline } from '../../js/polyline.js';
import { buildVariables } from '../../js/otp.js';

const here = dirname(fileURLToPath(import.meta.url));
const NOTE = 'SYNTHETIC test fixture (site/tests/fixtures/make-fixtures.mjs): made-up data, not an OTP answer, never published.';
const DAY = '2026-10-20';
const at = (hhmm) => `${DAY}T${hhmm}:00+02:00`;

// Rough positions [lon, lat] (synthetic).
const P = {
  origin: [1.3366, 43.6118],
  colomiersStation: [1.3352, 43.6112],
  arenes: [1.4185, 43.5934],
  matabiau: [1.4537, 43.6110],
  jeanJaures: [1.4490, 43.6060],
  francoisVerdier: [1.4552, 43.6000],
  montaudran: [1.4800, 43.5740],
  ramonville: [1.4760, 43.5560],
  labegeMadron: [1.5040, 43.5520],
  labegeInnopole: [1.5100, 43.5500],
  diagoraStation: [1.5115, 43.5470],
  destination: [1.5128, 43.5462],
};

const AGENCY = {
  sncf: { gtfsId: 'sncf:SYNTH_SNCF', name: 'SNCF (synthétique)' },
  tisseo: { gtfsId: 'tisseo:SYNTH_TISSEO', name: 'Tisséo (synthétique)' },
  futur: { gtfsId: 'futur:SYNTH_FUT', name: 'Réseau 2028 (synthétique)' },
};
const ROUTE = {
  ter1: { gtfsId: 'sncf:SYNTH_TER_1', shortName: 'TER', longName: 'Colomiers - Toulouse', color: '3F4A5A', textColor: 'FFFFFF', mode: 'RAIL' },
  ter2: { gtfsId: 'sncf:SYNTH_TER_2', shortName: 'TER', longName: 'Toulouse - Labège', color: '3F4A5A', textColor: 'FFFFFF', mode: 'RAIL' },
  a: { gtfsId: 'tisseo:SYNTH_A', shortName: 'A', longName: 'Métro A', color: 'C53030', textColor: 'FFFFFF', mode: 'SUBWAY' },
  b: { gtfsId: 'tisseo:SYNTH_B', shortName: 'B', longName: 'Métro B', color: 'F2C230', textColor: '000000', mode: 'SUBWAY' },
  bus79: { gtfsId: 'tisseo:SYNTH_79', shortName: '79', longName: 'Ramonville - Labège', color: 'FFFFFF', textColor: '000000', mode: 'BUS' },
  c: { gtfsId: 'futur:FUT_C', shortName: 'C', longName: 'Métro C', color: '5BBF8A', textColor: '000000', mode: 'SUBWAY' },
  bFut: { gtfsId: 'futur:FUT_B', shortName: 'B', longName: 'Métro B prolongé', color: 'F2C230', textColor: '000000', mode: 'SUBWAY' },
};

const place = (name, [lon, lat]) => ({ name, lat, lon });
const seconds = (a, b) => (Date.parse(at(b)) - Date.parse(at(a))) / 1000;

function walk(from, to, start, end, meters, path) {
  return {
    mode: 'WALK', transitLeg: false, duration: seconds(start, end), distance: meters, headsign: null,
    start: { scheduledTime: at(start) }, end: { scheduledTime: at(end) },
    from: place(...from), to: place(...to), agency: null, route: null, intermediatePlaces: [],
    legGeometry: { points: encodePolyline(path || [from[1], to[1]]) },
  };
}

function ride(route, agency, from, to, start, end, headsign, stops, path) {
  return {
    mode: route.mode, transitLeg: true, duration: seconds(start, end), distance: 1000, headsign,
    start: { scheduledTime: at(start) }, end: { scheduledTime: at(end) },
    from: place(...from), to: place(...to), agency, route,
    intermediatePlaces: stops.map(([name, time]) => ({ name, arrival: { scheduledTime: at(time) } })),
    legGeometry: { points: encodePolyline(path || [from[1], to[1]]) },
  };
}

function itinerary(legs) {
  const start = legs[0].start.scheduledTime;
  const end = legs.at(-1).end.scheduledTime;
  const walking = legs.filter((l) => l.mode === 'WALK');
  return {
    start, end,
    duration: (Date.parse(end) - Date.parse(start)) / 1000,
    numberOfTransfers: Math.max(0, legs.filter((l) => l.transitLeg).length - 1),
    walkDistance: walking.reduce((s, l) => s + l.distance, 0),
    walkTime: walking.reduce((s, l) => s + l.duration, 0),
    legs,
  };
}

const answer = (nodes, searchDateTime = at('08:30')) => ({
  _synthetic: NOTE,
  data: { planConnection: { searchDateTime, routingErrors: [], edges: nodes.map((node, i) => ({ cursor: `c${i}`, node })) } },
});

const O = ['Gare de Colomiers', P.origin];
const D = ['Diagora, Labège', P.destination];
const colomiers = ['Colomiers', P.colomiersStation];
const matabiau = ['Toulouse-Matabiau', P.matabiau];
const innopole = ['Labège-Innopole', P.labegeInnopole];
const arenes = ['Toulouse-Arènes', P.arenes];
const jeanJaures = ['Jean Jaurès', P.jeanJaures];
const ramonville = ['Ramonville', P.ramonville];
const madron = ['Labège Madron', P.labegeMadron];

// Today, best trip: train at 8:43 (change at Matabiau), arrival 9:28 (45 min).
const ter843 = itinerary([
  ride(ROUTE.ter1, AGENCY.sncf, colomiers, matabiau, '08:43', '09:00', 'Toulouse-Matabiau', [['Toulouse-Arènes', '08:52']], [P.colomiersStation, P.arenes, P.matabiau]),
  walk(matabiau, matabiau, '09:00', '09:02', 120),
  ride(ROUTE.ter2, AGENCY.sncf, matabiau, innopole, '09:08', '09:19', 'Carcassonne', [['Montaudran', '09:14']], [P.matabiau, P.montaudran, P.labegeInnopole]),
  walk(innopole, D, '09:19', '09:28', 650, [P.labegeInnopole, P.destination]),
]);
// Fix the departure: the train leaves from the station where the trip starts.
ter843.legs[0].from = place(...O);

// Today: train + metro A + metro B (Tisséo) + bus 79, arrival 9:45.
const terAB79 = itinerary([
  ride(ROUTE.ter1, AGENCY.sncf, colomiers, arenes, '08:36', '08:50', 'Toulouse-Matabiau', [], [P.colomiersStation, P.arenes]),
  walk(arenes, arenes, '08:50', '08:52', 150),
  ride(ROUTE.a, AGENCY.tisseo, arenes, jeanJaures, '08:55', '09:01', 'Balma-Gramont', [['Esquirol', '08:58']], [P.arenes, P.jeanJaures]),
  walk(jeanJaures, jeanJaures, '09:01', '09:02', 80),
  ride(ROUTE.b, AGENCY.tisseo, jeanJaures, ramonville, '09:04', '09:20', 'Ramonville', [['François Verdier', '09:06'], ['Saint-Agne', '09:12']], [P.jeanJaures, P.francoisVerdier, P.ramonville]),
  walk(ramonville, ramonville, '09:20', '09:22', 100),
  ride(ROUTE.bus79, AGENCY.tisseo, ramonville, ['Diagora', P.diagoraStation], '09:26', '09:41', 'Labège', [['Parc du Canal', '09:31']], [P.ramonville, P.diagoraStation]),
  walk(['Diagora', P.diagoraStation], D, '09:41', '09:45', 250),
]);
terAB79.legs[0].from = place(...O);

// Today: a later direct train, arrival 9:58.
const ter913 = itinerary([
  ride(ROUTE.ter1, AGENCY.sncf, O, innopole, '09:13', '09:50', 'Carcassonne', [['Toulouse-Arènes', '09:22'], ['Toulouse-Matabiau', '09:31']], [P.colomiersStation, P.arenes, P.matabiau, P.labegeInnopole]),
  walk(innopole, D, '09:50', '09:58', 650, [P.labegeInnopole, P.destination]),
]);

// 2028: metro C, departure 8:31, arrival 9:19 (48 min).
const metroC = itinerary([
  walk(O, ['Colomiers - Gare', P.colomiersStation], '08:31', '08:34', 220),
  ride(ROUTE.c, AGENCY.futur, ['Colomiers - Gare', P.colomiersStation], ['Diagora', P.diagoraStation], '08:34', '09:13', 'Labège - Gare',
    [['Matabiau Gare', '08:52'], ['François-Verdier', '08:55'], ['Montaudran Gare - Piste des Géants', '09:02']],
    [P.colomiersStation, [1.3800, 43.6300], P.matabiau, P.francoisVerdier, P.montaudran, P.diagoraStation]),
  walk(['Diagora', P.diagoraStation], D, '09:13', '09:19', 400),
]);

// 2028: train + metro A + metro B extended (future feed), arrival 9:35.
const terABext = itinerary([
  ride(ROUTE.ter1, AGENCY.sncf, O, arenes, '08:36', '08:50', 'Toulouse-Matabiau', [], [P.colomiersStation, P.arenes]),
  walk(arenes, arenes, '08:50', '08:52', 150),
  ride(ROUTE.a, AGENCY.tisseo, arenes, jeanJaures, '08:55', '09:01', 'Balma-Gramont', [['Esquirol', '08:58']], [P.arenes, P.jeanJaures]),
  walk(jeanJaures, jeanJaures, '09:01', '09:02', 80),
  ride(ROUTE.bFut, AGENCY.futur, jeanJaures, madron, '09:04', '09:26', 'Labège Madron', [['Ramonville', '09:20'], ['Parc du Canal', '09:23']], [P.jeanJaures, P.francoisVerdier, P.ramonville, P.labegeMadron]),
  walk(madron, D, '09:26', '09:35', 700, [P.labegeMadron, P.destination]),
]);

export const filters = {
  _synthetic: NOTE,
  request: { direct: ['WALK'], access: ['WALK'], egress: ['WALK'], transfer: ['WALK'], transit_modes: ['BUS', 'TRAM', 'SUBWAY', 'RAIL', 'GONDOLA'] },
  scenarios: {
    actuel: {
      label: 'Réseau actuel',
      excluded_agencies: [AGENCY.futur.gtfsId],
      excluded_routes: [],
      filters: [{ exclude: [{ agencies: [AGENCY.futur.gtfsId] }] }],
    },
    2028: {
      label: 'Réseau 2028',
      excluded_agencies: [],
      excluded_routes: [ROUTE.b.gtfsId],
      filters: [{ exclude: [{ routes: [ROUTE.b.gtfsId] }] }],
    },
  },
};

const actuel = answer([ter843, terAB79, ter913]);
const future = answer([metroC, ter843, terABext]);
const noTrip = {
  _synthetic: NOTE,
  data: { planConnection: { searchDateTime: at('08:30'), routingErrors: [{ code: 'NO_TRANSIT_CONNECTION', description: 'synthetic' }], edges: [] } },
};

const origin = { label: 'Gare de Colomiers', lon: P.origin[0], lat: P.origin[1] };
const destination = { label: 'Diagora, Labège', lon: P.destination[0], lat: P.destination[1] };
const when = { type: 'depart', iso: at('08:30') };
const demo = {
  _synthetic: NOTE,
  recorded_at: '2026-10-19T06:10:00Z',
  requests: ['actuel', '2028'].map((scenario) => ({
    id: `synth-colomiers-labege-${scenario}`,
    label: 'Gare de Colomiers → Diagora, Labège',
    scenario,
    variables: buildVariables({ origin, destination, when, mode: 'transit', filters: filters.scenarios[scenario].filters }),
    response: scenario === '2028' ? future : actuel,
  })),
  scenario_filters: filters,
};

// Geocoder answers (Géoplateforme format, synthetic).
const geocoder = {
  _synthetic: NOTE,
  colomiers: {
    type: 'FeatureCollection',
    features: [
      { type: 'Feature', geometry: { type: 'Point', coordinates: P.origin }, properties: { _type: 'poi', toponym: 'Gare de Colomiers', name: ['Gare de Colomiers'], city: ['Colomiers'], postcode: ['31770'] } },
      { type: 'Feature', geometry: { type: 'Point', coordinates: [1.3392, 43.6105] }, properties: { _type: 'address', label: 'Allée du Comminges 31770 Colomiers', name: 'Allée du Comminges', city: 'Colomiers', postcode: '31770', type: 'street' } },
      { type: 'Feature', geometry: { type: 'Point', coordinates: [2.3, 48.9] }, properties: { _type: 'address', label: 'Rue de Colomiers 75000 Paris', name: 'Rue de Colomiers', city: 'Paris', postcode: '75000', type: 'street' } },
    ],
  },
  labege: {
    type: 'FeatureCollection',
    features: [
      { type: 'Feature', geometry: { type: 'Point', coordinates: P.destination }, properties: { _type: 'address', label: 'Diagora 31670 Labège', name: 'Diagora', city: 'Labège', postcode: '31670', type: 'street' } },
    ],
  },
  reverse: {
    type: 'FeatureCollection',
    features: [
      { type: 'Feature', geometry: { type: 'Point', coordinates: [1.4442, 43.6047] }, properties: { _type: 'address', label: '1 Place du Capitole 31000 Toulouse', name: '1 Place du Capitole', city: 'Toulouse', postcode: '31000', type: 'housenumber' } },
    ],
  },
};

const files = {
  'synthetic-scenario-filters.json': filters,
  'synthetic-plan-actuel.json': actuel,
  'synthetic-plan-2028.json': future,
  'synthetic-plan-no-trip.json': noTrip,
  'synthetic-demo-responses.json': demo,
  'synthetic-geocoder.json': geocoder,
};
for (const [name, content] of Object.entries(files)) {
  writeFileSync(join(here, name), `${JSON.stringify(content, null, 2)}\n`);
}
console.log(`wrote ${Object.keys(files).length} synthetic fixtures in ${here}`);
