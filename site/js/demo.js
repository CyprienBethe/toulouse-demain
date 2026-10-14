// Demonstration mode (?demo=1): replays real OTP answers recorded by the CI
// in demo/demo-responses.json, without calling the itinerary server.
//
// File contract (produced by the architect's workflow):
//   {"recorded_at": "<ISO>",
//    "requests": [{"id", "label", "scenario": "actuel" | "2028",
//                  "variables": {...GraphQL variables...}, "response": {...raw GraphQL answer...}}],
//    "scenario_filters": {...content of scenario-filters.json...}}
// The answers must come from the query in js/otp.js (PLAN_QUERY), or the
// fields the site reads are missing.

import { modeOfVariables } from './otp.js';
import { parseScenarioFilters, SCENARIOS } from './scenarios.js';
import { toMs } from './format.js';

export const DEMO_FILE = 'demo/demo-responses.json';

/** Validate the file. Throws on an unusable file. */
export function parseDemo(json) {
  if (!json || !Array.isArray(json.requests)) throw new Error('demo file: no "requests"');
  const recordedAt = toMs(json.recorded_at);
  const filters = parseScenarioFilters(json.scenario_filters);
  const requests = json.requests
    .filter((r) => r && SCENARIOS.includes(r.scenario) && r.variables && r.response)
    .map((r) => ({ ...r, query: describeVariables(r.variables) }))
    .filter((r) => r.query);
  if (!requests.length) throw new Error('demo file: no usable request');
  return { recordedAt, filters, requests };
}

/** What a recorded request asked: places, time and mode. Null if unreadable. */
export function describeVariables(variables) {
  const place = (p) => {
    const c = p?.location?.coordinate;
    if (!Number.isFinite(c?.latitude) || !Number.isFinite(c?.longitude)) return null;
    return { label: typeof p.label === 'string' ? p.label : '', lat: c.latitude, lon: c.longitude };
  };
  const origin = place(variables?.origin);
  const destination = place(variables?.destination);
  const dt = variables?.dateTime || {};
  const iso = dt.latestArrival || dt.earliestDeparture;
  if (!origin || !destination || typeof iso !== 'string') return null;
  return {
    origin,
    destination,
    when: { type: dt.latestArrival ? 'arrive' : 'depart', iso },
    mode: modeOfVariables(variables),
  };
}

const near = (a, b) => Math.abs(a.lat - b.lat) < 0.0005 && Math.abs(a.lon - b.lon) < 0.0007;

function sameQuery(a, b) {
  return a.mode === b.mode && a.when.type === b.when.type
    && Math.abs(toMs(a.when.iso) - toMs(b.when.iso)) < 60000
    && near(a.origin, b.origin) && near(a.destination, b.destination);
}

/** The recorded answer for a search in a scenario, or null. */
export function findRecorded(demo, query, scenario) {
  const hit = demo.requests.find((r) => r.scenario === scenario && sameQuery(r.query, query));
  return hit ? hit.response : null;
}

/** Recorded searches, one per request whatever the scenario: [{id, label, query}]. */
export function recordedSearches(demo) {
  const out = [];
  for (const r of demo.requests) {
    if (out.some((o) => sameQuery(o.query, r.query))) continue;
    const label = typeof r.label === 'string' && r.label.trim()
      ? r.label.trim() : `${r.query.origin.label} → ${r.query.destination.label}`;
    out.push({ id: String(r.id ?? out.length), label, query: r.query });
  }
  return out;
}
