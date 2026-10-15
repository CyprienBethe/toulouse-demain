// Requests to OpenTripPlanner 2.10.0 (GTFS GraphQL API, `planConnection`).
//
// Same shape as scripts/reference_trips.py (build_modes, build_variables),
// which is checked by the CI on the real graph. Two rules from the ADR 0001:
// - never send `modes: null` (OTP 2.10.0 crashes): `modes` is always built,
//   and declared non-null (`PlanModesInput!`) in the query below;
// - never send any null value: `preferences` is left out when a scenario has
//   no filter, and assertNoNull() checks every request before it leaves.

export const PLAN_QUERY = `query Plan($origin: PlanLabeledLocationInput!, $destination: PlanLabeledLocationInput!,
           $dateTime: PlanDateTimeInput!, $modes: PlanModesInput!, $preferences: PlanPreferencesInput) {
  planConnection(origin: $origin, destination: $destination, dateTime: $dateTime,
                 modes: $modes, preferences: $preferences, first: 3) {
    searchDateTime
    routingErrors { code description }
    edges {
      node {
        start
        end
        duration
        numberOfTransfers
        walkDistance
        walkTime
        legs {
          mode
          transitLeg
          duration
          distance
          headsign
          start { scheduledTime }
          end { scheduledTime }
          from { name lat lon }
          to { name lat lon }
          agency { gtfsId name }
          route { gtfsId shortName longName color textColor mode }
          intermediatePlaces { name arrival { scheduledTime } }
          legGeometry { points }
        }
      }
    }
  }
}`;

/**
 * Modes for a transit trip, copied from `request` in config/scenarios.json.
 * The server's scenario-filters.json gives the same block; it wins when present.
 * A test checks that this copy matches config/scenarios.json.
 */
export const DEFAULT_REQUEST = Object.freeze({
  direct: ['WALK'],
  access: ['WALK'],
  egress: ['WALK'],
  transfer: ['WALK'],
  transit_modes: ['BUS', 'TRAM', 'SUBWAY', 'RAIL', 'GONDOLA'],
});

/** Street-only searches: no transit at all. */
const STREET_ONLY_MODES = { walk: 'WALK', bicycle: 'BICYCLE' };
export const TRIP_MODES = ['transit', 'walk', 'bicycle'];

/** Keep the server's lists when they are usable, otherwise the defaults. */
export function mergeRequest(request) {
  const out = {};
  for (const key of Object.keys(DEFAULT_REQUEST)) {
    const value = request && request[key];
    out[key] = Array.isArray(value) && value.length && value.every((v) => typeof v === 'string')
      ? [...value] : [...DEFAULT_REQUEST[key]];
  }
  return out;
}

/** `modes` argument of planConnection. Never null. */
export function buildModes(mode, request = DEFAULT_REQUEST) {
  if (STREET_ONLY_MODES[mode]) return { directOnly: true, direct: [STREET_ONLY_MODES[mode]] };
  if (mode === 'transit') {
    const r = mergeRequest(request);
    return {
      direct: r.direct,
      transit: {
        access: r.access,
        egress: r.egress,
        transfer: r.transfer,
        transit: r.transit_modes.map((m) => ({ mode: m })),
      },
    };
  }
  throw new Error(`unknown trip mode: ${mode}`);
}

const round6 = (n) => Math.round(n * 1e6) / 1e6;

function location(place) {
  if (!Number.isFinite(place?.lat) || !Number.isFinite(place?.lon)) {
    throw new Error('a place needs numeric lat and lon');
  }
  const out = { location: { coordinate: { latitude: round6(place.lat), longitude: round6(place.lon) } } };
  if (typeof place.label === 'string' && place.label.trim()) out.label = place.label.trim().slice(0, 120);
  return out;
}

/**
 * GraphQL variables of one planConnection request.
 * - origin, destination: {label, lat, lon}
 * - when: {type: 'depart' | 'arrive', iso: '2026-10-20T08:30:00+02:00'}
 * - mode: 'transit' | 'walk' | 'bicycle'
 * - filters: the scenario's `filters` from scenario-filters.json
 */
export function buildVariables({ origin, destination, when, mode, filters, request }) {
  if (typeof when?.iso !== 'string') throw new Error('when.iso is required');
  const variables = {
    origin: location(origin),
    destination: location(destination),
    dateTime: when.type === 'arrive' ? { latestArrival: when.iso } : { earliestDeparture: when.iso },
    modes: buildModes(mode, request),
  };
  if (Array.isArray(filters) && filters.length) variables.preferences = { transit: { filters } };
  assertNoNull(variables);
  return variables;
}

/** Throw if a value, at any depth, is null or undefined. */
export function assertNoNull(value, path = 'variables') {
  if (value === null || value === undefined) throw new Error(`${path} is ${value}`);
  if (Array.isArray(value)) value.forEach((v, i) => assertNoNull(v, `${path}[${i}]`));
  else if (typeof value === 'object') {
    for (const [key, v] of Object.entries(value)) assertNoNull(v, `${path}.${key}`);
  }
}

/** Mode of a request, read back from its variables (used by the demonstration mode). */
export function modeOfVariables(variables) {
  const modes = variables?.modes || {};
  if (modes.directOnly) return (modes.direct || []).includes('BICYCLE') ? 'bicycle' : 'walk';
  return 'transit';
}

// --- HTTP ---------------------------------------------------------------

/** Error with a `kind` the interface turns into a message (see messages.js). */
export class ApiError extends Error {
  constructor(kind, message, status) {
    super(message);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = status;
  }
}

/** True while config.js still holds the example address. */
export function isPlaceholderApi(apiBase) {
  return !apiBase || /SOUS-DOMAINE/i.test(apiBase);
}

/**
 * POST a GraphQL request and return `data`.
 * Kinds of ApiError: not-configured, unreachable, timeout, rate-limited,
 * server, bad-response.
 */
export async function postGraphql(endpoint, query, variables, { signal, timeoutMs = 30000, fetchImpl } = {}) {
  const doFetch = fetchImpl || globalThis.fetch;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(new ApiError('timeout', 'request timed out')), timeoutMs);
  if (signal) signal.addEventListener('abort', () => controller.abort(signal.reason), { once: true });
  let response;
  try {
    response = await doFetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, variables }),
      signal: controller.signal,
      credentials: 'omit',
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    if (error instanceof ApiError) throw error;
    if (controller.signal.reason instanceof ApiError) throw controller.signal.reason;
    // A network error, a DNS error and a refused CORS request all look the same.
    throw new ApiError('unreachable', String(error?.message || error));
  } finally {
    clearTimeout(timer);
  }
  return readGraphqlResponse(response);
}

async function readGraphqlResponse(response) {
  if (response.status === 429) throw new ApiError('rate-limited', 'too many requests', 429);
  if (response.status >= 500) throw new ApiError('server', `HTTP ${response.status}`, response.status);
  if (!response.ok) throw new ApiError('bad-response', `HTTP ${response.status}`, response.status);
  let body;
  try {
    body = await response.json();
  } catch {
    throw new ApiError('bad-response', 'response is not JSON', response.status);
  }
  return checkGraphqlBody(body);
}

/** The `data` of a GraphQL body, or an ApiError if the server reported errors. */
export function checkGraphqlBody(body) {
  if (body && Array.isArray(body.errors) && body.errors.length) {
    throw new ApiError('bad-response', body.errors.map((e) => e?.message).join(' ; '));
  }
  if (!body || typeof body.data !== 'object' || body.data === null) {
    throw new ApiError('bad-response', 'no data in response');
  }
  return body.data;
}
