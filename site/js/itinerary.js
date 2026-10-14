// Itineraries: from the raw OTP answer to what the interface shows.

import {
  epochMinute, formatDistance, formatDuration, formatStops, formatTransfers, minutesBetween, toMs,
} from './format.js';
import { isFutureLeg } from './scenarios.js';

const MODE_NAMES = {
  SUBWAY: 'Métro',
  TRAM: 'Tram',
  BUS: 'Bus',
  TROLLEYBUS: 'Bus',
  COACH: 'Car',
  RAIL: 'Train',
  MONORAIL: 'Métro',
  GONDOLA: 'Téléphérique',
  CABLE_CAR: 'Téléphérique',
  FUNICULAR: 'Funiculaire',
  FERRY: 'Bateau',
  WALK: 'Marche',
  BICYCLE: 'Vélo',
};

/** French name of a mode: "Métro", "Bus", "Train"… */
export function modeName(mode) {
  return MODE_NAMES[mode] || 'Transport';
}

/** Short text on a line badge: the GTFS short name, else the mode. */
export function badgeText(leg) {
  const short = (leg.route?.shortName || '').trim();
  return short || modeName(leg.route?.mode || leg.mode);
}

/** Full name of a line: "Métro C", "Bus 79", "TER", "Train". */
export function lineName(leg) {
  const mode = leg.route?.mode || leg.mode;
  const short = (leg.route?.shortName || '').trim();
  const name = modeName(mode);
  if (!short) return name;
  // A short name such as "TER" already says what it is.
  if (mode === 'RAIL' && /[a-z]/i.test(short) && !/^\d/.test(short)) return short;
  return `${name} ${short}`;
}

/** Convert one OTP itinerary (planConnection edge node) into a trip. */
export function toTrip(node, filters) {
  const legs = (node.legs || []).map((leg) => {
    const transit = Boolean(leg.transitLeg ?? leg.route);
    return {
      mode: leg.mode,
      transit,
      start: toMs(leg.start?.scheduledTime),
      end: toMs(leg.end?.scheduledTime),
      duration: Number(leg.duration) || 0,
      distance: Number(leg.distance) || 0,
      headsign: leg.headsign || '',
      from: { name: leg.from?.name || '', lat: leg.from?.lat, lon: leg.from?.lon },
      to: { name: leg.to?.name || '', lat: leg.to?.lat, lon: leg.to?.lon },
      agency: leg.agency || null,
      route: leg.route || null,
      stops: (leg.intermediatePlaces || []).map((p) => ({
        name: p.name || '',
        time: p.arrival?.scheduledTime ? toMs(p.arrival.scheduledTime) : null,
      })),
      points: leg.legGeometry?.points || '',
      future: transit && isFutureLeg(leg, filters),
    };
  });
  const walkSeconds = legs.filter((l) => l.mode === 'WALK').reduce((s, l) => s + l.duration, 0);
  const trip = {
    start: toMs(node.start),
    end: toMs(node.end),
    legs,
    transfers: Number(node.numberOfTransfers) || 0,
    walkMinutes: Math.round((Number(node.walkTime) || walkSeconds) / 60),
    walkMeters: Number(node.walkDistance) || 0,
  };
  trip.minutes = minutesBetween(trip.start, trip.end);
  trip.key = tripKey(trip);
  return trip;
}

/**
 * Identity of a trip, used to remove duplicates between the two scenarios:
 * shown departure and arrival minutes, plus each transit leg (route and minute).
 */
export function tripKey(trip) {
  const rides = trip.legs.filter((l) => l.transit)
    .map((l) => `${l.route?.gtfsId || l.mode}@${epochMinute(l.start)}`);
  return [epochMinute(trip.start), epochMinute(trip.end), ...rides].join('|');
}

export function transitLegs(trip) {
  return trip.legs.filter((l) => l.transit);
}

/** One line under a trip: "Métro C direct, 7 min à pied", "2 correspondances, 12 min à pied", "À pied, 1,4 km". */
export function summaryText(trip) {
  const rides = transitLegs(trip);
  if (!rides.length) {
    const bike = trip.legs.some((l) => l.mode === 'BICYCLE');
    const meters = trip.legs.reduce((s, l) => s + l.distance, 0);
    return `${bike ? 'À vélo' : 'À pied'}, ${formatDistance(meters)}`;
  }
  const head = rides.length === 1 ? `${lineName(rides[0])} direct` : formatTransfers(rides.length - 1);
  return trip.walkMinutes >= 1 ? `${head}, ${formatDuration(trip.walkMinutes)} à pied` : head;
}

/**
 * Steps of the detail view (timeline). Each step is one of:
 * - {type: 'place', time, title, sub, end}: departure, boarding, alighting, arrival;
 * - {type: 'walk', title, sub, wait}: walk or ride a bike, with the wait that follows;
 * - {type: 'ride', leg, title, direction, sub, stops}: a transit leg.
 */
export function buildSteps(trip, originLabel, destinationLabel) {
  const steps = [];
  const first = trip.legs[0];
  // When the trip starts or ends right at a stop, the boarding (alighting)
  // step already says where and when: no separate departure (arrival) step.
  if (!first?.transit) {
    steps.push({ type: 'place', time: trip.start, title: originLabel || first?.from.name || 'Départ', sub: 'Départ' });
  }
  trip.legs.forEach((leg, i) => {
    const next = trip.legs[i + 1];
    const previous = trip.legs[i - 1];
    if (!leg.transit) {
      const verb = leg.mode === 'BICYCLE' ? 'Rouler à vélo' : 'Marcher';
      const target = next ? next.from.name : destinationLabel || leg.to.name;
      const wait = next?.transit ? minutesBetween(leg.end, next.start) : 0;
      steps.push({
        type: 'walk',
        title: `${verb} ${formatDuration(minutesBetween(leg.start, leg.end) || Math.round(leg.duration / 60))}`,
        sub: `${formatDistance(leg.distance)} jusqu'à ${target}`,
        wait: wait >= 1 ? `Attendre ${formatDuration(wait)}` : '',
      });
      return;
    }
    if (previous?.transit) {
      // Two rides in a row: the change happens at the same stop.
      const wait = minutesBetween(previous.end, leg.start);
      steps.push({ type: 'walk', title: 'Correspondance sur place', sub: leg.from.name, wait: wait >= 1 ? `Attendre ${formatDuration(wait)}` : '' });
    }
    const name = lineName(leg);
    const isFirst = i === 0;
    const isLast = !next;
    steps.push({ type: 'place', time: leg.start, title: leg.from.name, sub: isFirst ? `Départ, monter : ${name}` : `Monter : ${name}` });
    const minutes = minutesBetween(leg.start, leg.end);
    steps.push({
      type: 'ride',
      leg,
      title: name,
      direction: leg.headsign,
      sub: `${formatStops(leg.stops.length + 1)} · ${formatDuration(minutes)}`,
      stops: leg.stops,
    });
    steps.push({ type: 'place', time: leg.end, title: leg.to.name, sub: isLast ? 'Descendre, arrivée' : 'Descendre', end: isLast });
  });
  if (!trip.legs.at(-1)?.transit) {
    steps.push({ type: 'place', time: trip.end, title: destinationLabel || trip.legs.at(-1)?.to.name || 'Arrivée', sub: 'Arrivée', end: true });
  }
  return steps;
}
