// The comparator built into the 2028 results (rule validated by Cyprien on
// 14/10/2026, docs/ux/parcours.md section 6).
//
// - The same request is sent to both scenarios.
// - The 2028 list gathers the 2028 trips and the trips of today that are still
//   possible in 2028 (no agency or route excluded by the 2028 scenario),
//   without duplicates, like Google Maps or Citymapper: all the options.
// - Each trip has a double bar on one scale for the whole list: "today" and
//   "2028". A bar is the door-to-door time, waiting included, from the
//   requested time to the arrival. "Today" is the best trip of today
//   (earliest arrival).
// - "Arrive by" searches compare departure times instead (latest departure).
//
// Every computation uses whole minutes as shown on screen (8:31, 9:19), so
// a label always agrees with the times next to it.

import { epochMinute, formatDuration } from './format.js';
import { allowedIn } from './scenarios.js';

/** Sort trips: by arrival for "depart at" / "now", by departure (latest first) for "arrive by". */
export function sortTrips(trips, dateType) {
  const list = [...trips];
  if (dateType === 'arrive') list.sort((a, b) => b.start - a.start || a.end - b.end);
  else list.sort((a, b) => a.end - b.end || b.start - a.start);
  return list;
}

/** Remove trips with the same key, keeping the first one. */
export function uniqueTrips(trips) {
  const seen = new Set();
  return trips.filter((t) => (seen.has(t.key) ? false : (seen.add(t.key), true)));
}

/**
 * The 2028 list: 2028 trips + today's trips still possible in 2028, no
 * duplicates, sorted. Each row: {trip, existsToday}. `existsToday` is true for
 * a trip that uses no line excluded from today's network.
 */
export function mergeAlternatives({ future, today, filters, dateType }) {
  const scenario2028 = filters.scenarios['2028'];
  const actuel = filters.scenarios.actuel;
  const stillPossible = (today || []).filter((t) => allowedIn(t, scenario2028));
  const merged = uniqueTrips(sortTrips([...(future || []), ...stillPossible], dateType));
  return merged.map((trip) => ({ trip, existsToday: allowedIn(trip, actuel) }));
}

/** Best trip of today: earliest arrival ("depart"), latest departure ("arrive"). */
export function bestTrip(trips, dateType) {
  return sortTrips(trips || [], dateType)[0] || null;
}

/**
 * Comparison of one trip with the best trip of today.
 * Returns {todayBar, tripBar, delta, verdict}: bars in minutes; delta > 0
 * means better than today (earlier arrival, or later departure for
 * "arrive by"); verdict is 'better', 'worse', 'same' or 'no-today'.
 */
export function compareTrip({ trip, existsToday }, best, requestedAt, dateType) {
  const asked = epochMinute(requestedAt);
  const arrive = dateType === 'arrive';
  const barOf = (t) => Math.max(0, arrive ? asked - epochMinute(t.start) : epochMinute(t.end) - asked);
  const tripBar = barOf(trip);
  if (!best) return { todayBar: null, tripBar, delta: null, verdict: existsToday ? 'same' : 'no-today' };
  const todayBar = barOf(best);
  const delta = arrive
    ? epochMinute(trip.start) - epochMinute(best.start)
    : epochMinute(best.end) - epochMinute(trip.end);
  let verdict = 'same';
  if (!existsToday && delta >= 1) verdict = 'better';
  else if (!existsToday && delta <= -1) verdict = 'worse';
  return { todayBar, tripBar, delta, verdict };
}

/** Label of a comparison, in words (an arrow is drawn next to it). */
export function comparisonLabel({ verdict, delta }, dateType) {
  if (verdict === 'same') return "Comme aujourd'hui";
  if (verdict === 'no-today') return "Aucun trajet aujourd'hui pour cette demande";
  const amount = formatDuration(Math.abs(delta));
  if (dateType === 'arrive') {
    return verdict === 'better'
      ? `Départ ${amount} plus tard qu'aujourd'hui`
      : `Départ ${amount} plus tôt qu'aujourd'hui`;
  }
  return verdict === 'better'
    ? `Arrivée ${amount} plus tôt qu'aujourd'hui`
    : `Arrivée ${amount} plus tard qu'aujourd'hui`;
}

/**
 * Everything the 2028 list needs.
 * Returns {rows: [{trip, existsToday, todayBar, tripBar, delta, verdict, label}], best, scale}
 * where `scale` is the longest bar of the list (same scale for every row).
 */
export function buildComparison({ future, today, filters, dateType, requestedAt }) {
  const best = bestTrip(today, dateType);
  const rows = mergeAlternatives({ future, today, filters, dateType }).map((row) => {
    const comparison = compareTrip(row, best, requestedAt, dateType);
    return { ...row, ...comparison, label: comparisonLabel(comparison, dateType) };
  });
  const scale = Math.max(1, ...rows.flatMap((r) => [r.todayBar ?? 0, r.tripBar]));
  return { rows, best, scale };
}
