// French formats for times, durations, distances and dates.
//
// All times are shown in the time zone of the network (Europe/Paris), whatever
// the time zone of the visitor's device. Spaces inside a value ("1 h 18",
// "42 min") are non-breaking (U+00A0), so a value never wraps on two lines.

export const TIME_ZONE = 'Europe/Paris';
const NBSP = ' ';

const partsFormatter = new Intl.DateTimeFormat('en-US', {
  timeZone: TIME_ZONE,
  hourCycle: 'h23',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
});

/** Accept an ISO string (with offset), a Date or a number of milliseconds. */
export function toMs(value) {
  if (typeof value === 'number') return value;
  if (value instanceof Date) return value.getTime();
  const ms = Date.parse(value);
  if (Number.isNaN(ms)) throw new Error(`invalid date: ${value}`);
  return ms;
}

/** Calendar parts of an instant in Paris: {year, month, day, hour, minute, second}. */
export function parisParts(value) {
  const parts = {};
  for (const part of partsFormatter.formatToParts(new Date(toMs(value)))) {
    if (part.type !== 'literal') parts[part.type] = Number(part.value);
  }
  return parts;
}

/** Offset of Paris from UTC at an instant, in minutes (60 in winter, 120 in summer). */
export function parisOffsetMinutes(value) {
  const ms = Math.floor(toMs(value) / 1000) * 1000;
  const p = parisParts(ms);
  const asUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second);
  return Math.round((asUtc - ms) / 60000);
}

/**
 * Instant (ms) of a Paris wall-clock time: date "YYYY-MM-DD", time "HH:MM".
 * During the autumn change (a time that happens twice) the first one is used;
 * during the spring change (a time that does not exist) the time after the jump.
 */
export function parisLocalToMs(date, time) {
  const [year, month, day] = date.split('-').map(Number);
  const [hour, minute] = time.split(':').map(Number);
  const wall = Date.UTC(year, month - 1, day, hour, minute);
  // Try the summer offset first, then the winter one: keep the first that
  // gives back the same wall-clock time.
  for (const offset of [120, 60]) {
    const ms = wall - offset * 60000;
    if (parisOffsetMinutes(ms) === offset) return ms;
  }
  // Skipped hour (spring): read it with the winter offset, which lands after the jump.
  return wall - 60 * 60000;
}

const pad = (n) => String(n).padStart(2, '0');

/** ISO 8601 with the Paris offset, as OTP expects: "2026-10-20T08:30:00+02:00". */
export function toParisIso(value) {
  const ms = toMs(value);
  const p = parisParts(ms);
  const offset = parisOffsetMinutes(ms);
  const sign = offset >= 0 ? '+' : '-';
  const abs = Math.abs(offset);
  return `${p.year}-${pad(p.month)}-${pad(p.day)}T${pad(p.hour)}:${pad(p.minute)}:${pad(p.second)}`
    + `${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`;
}

/** "YYYY-MM-DD" and "HH:MM" of an instant in Paris (values for <input type=date|time>). */
export function parisDateInput(value) {
  const p = parisParts(value);
  return `${p.year}-${pad(p.month)}-${pad(p.day)}`;
}
export function parisTimeInput(value) {
  const p = parisParts(value);
  return `${pad(p.hour)}:${pad(p.minute)}`;
}

/** Whole minutes since the epoch (seconds dropped): every comparison uses the shown minutes. */
export function epochMinute(value) {
  return Math.floor(toMs(value) / 60000);
}

/** Clock time in Paris, without leading zero for the hour: "8:32", "14:05". */
export function formatTime(value) {
  const p = parisParts(value);
  return `${p.hour}:${pad(p.minute)}`;
}

/** Minutes between two instants, as shown (8:31 → 9:19 is 48 min, whatever the seconds). */
export function minutesBetween(start, end) {
  return epochMinute(end) - epochMinute(start);
}

/** Duration: "42 min", "1 h", "1 h 05", "1 h 18". */
export function formatDuration(minutes) {
  const total = Math.max(0, Math.round(minutes));
  if (total < 60) return `${total}${NBSP}min`;
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  return rest === 0 ? `${hours}${NBSP}h` : `${hours}${NBSP}h${NBSP}${pad(rest)}`;
}

/** Duration read aloud by screen readers: "1 heure 18 minutes", "42 minutes". */
export function formatDurationLong(minutes) {
  const total = Math.max(0, Math.round(minutes));
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  const words = [];
  if (hours) words.push(`${hours} heure${hours > 1 ? 's' : ''}`);
  if (rest || !hours) words.push(`${rest} minute${rest > 1 ? 's' : ''}`);
  return words.join(' ');
}

const decimal = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1, minimumFractionDigits: 1 });

/** Distance: "450 m" (rounded to 10 m), "1,2 km". */
export function formatDistance(meters) {
  const m = Math.max(0, meters || 0);
  if (m < 995) return `${Math.max(10, Math.round(m / 10) * 10)}${NBSP}m`;
  return `${decimal.format(m / 1000)}${NBSP}km`;
}

const dayFormatter = new Intl.DateTimeFormat('fr-FR', {
  timeZone: TIME_ZONE, weekday: 'long', day: 'numeric', month: 'long',
});

/** "Mardi 20 octobre". */
export function formatDay(value) {
  const text = dayFormatter.format(new Date(toMs(value)));
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** "14/10" (day and month, for the demonstration banner). */
export function formatShortDate(value) {
  const p = parisParts(value);
  return `${pad(p.day)}/${pad(p.month)}`;
}

/** "1 correspondance", "2 correspondances", "Direct". */
export function formatTransfers(count) {
  if (!count) return 'Direct';
  return `${count} correspondance${count > 1 ? 's' : ''}`;
}

/** "1 arrêt", "5 arrêts". */
export function formatStops(count) {
  return `${count} arrêt${count > 1 ? 's' : ''}`;
}
