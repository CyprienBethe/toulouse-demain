// Scenarios "actuel" (today) and "2028".
//
// One OTP graph holds the three feeds (tisseo, sncf, futur). A scenario is a
// filter sent with every request. Its resolved version, with the real agency
// and route ids, is written by scripts/reference_trips.py (--filters-output)
// and published with each graph as scenario-filters.json:
//
//   {"request": {...modes...},
//    "scenarios": {"actuel": {"label", "excluded_agencies": [...], "excluded_routes": [...], "filters": [...]},
//                  "2028":   {...}}}
//
// The same file tells which itineraries of today are still possible in 2028
// (they use no agency and no route excluded by the 2028 scenario).

export const SCENARIOS = ['actuel', '2028'];
export const SCENARIO_LABELS = { actuel: "Aujourd'hui", 2028: '2028' };
export const FUTURE_FEED = 'futur';

/** Validate and index scenario-filters.json. Throws on an unusable file. */
export function parseScenarioFilters(json) {
  if (!json || typeof json !== 'object' || !json.scenarios) throw new Error('scenario filters: no "scenarios"');
  const scenarios = {};
  for (const name of SCENARIOS) {
    const s = json.scenarios[name];
    if (!s || !Array.isArray(s.filters)) throw new Error(`scenario filters: scenario "${name}" missing`);
    scenarios[name] = {
      label: typeof s.label === 'string' ? s.label : SCENARIO_LABELS[name],
      filters: s.filters,
      excludedAgencies: new Set(stringList(s.excluded_agencies)),
      excludedRoutes: new Set(stringList(s.excluded_routes)),
    };
  }
  return { request: json.request || null, scenarios };
}

function stringList(value) {
  return Array.isArray(value) ? value.filter((v) => typeof v === 'string') : [];
}

/** Feed id of a leg ("tisseo", "sncf", "futur"), from its route or agency id. */
export function feedOf(leg) {
  const id = leg?.route?.gtfsId || leg?.agency?.gtfsId || '';
  const i = id.indexOf(':');
  return i > 0 ? id.slice(0, i) : null;
}

/** True if a leg uses an agency or a route that the scenario excludes. */
export function legExcluded(leg, scenario) {
  if (!scenario) return false;
  const agency = leg?.agency?.gtfsId;
  const route = leg?.route?.gtfsId;
  return Boolean((agency && scenario.excludedAgencies.has(agency)) || (route && scenario.excludedRoutes.has(route)));
}

/** True if no leg of the itinerary is excluded by the scenario. */
export function allowedIn(itinerary, scenario) {
  return (itinerary?.legs || []).every((leg) => !legExcluded(leg, scenario));
}

/**
 * True for a leg on a line that does not exist yet: a line excluded from the
 * "actuel" scenario, or any line of the future feed.
 */
export function isFutureLeg(leg, filters) {
  if (!leg?.route) return false;
  if (feedOf(leg) === FUTURE_FEED) return true;
  return legExcluded(leg, filters?.scenarios?.actuel);
}
