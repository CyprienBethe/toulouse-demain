import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  epochMinute, formatDay, formatDistance, formatDuration, formatDurationLong, formatShortDate, formatTime,
  formatTransfers, minutesBetween, parisLocalToMs, parisOffsetMinutes, toParisIso,
} from '../js/format.js';

// Values use non-breaking spaces; compare with plain spaces.
const plain = (s) => s.replace(/ /g, ' ');

test('heures en français, sans zéro devant l\'heure, à l\'heure de Paris', () => {
  assert.equal(formatTime('2026-10-20T08:32:00+02:00'), '8:32');
  assert.equal(formatTime('2026-10-20T06:32:00Z'), '8:32');
  assert.equal(formatTime('2026-10-20T14:05:59+02:00'), '14:05');
  assert.equal(formatTime('2026-12-01T00:07:00+01:00'), '0:07');
});

test('durées : « 42 min », « 1 h 18 », « 1 h », « 1 h 05 »', () => {
  assert.equal(plain(formatDuration(42)), '42 min');
  assert.equal(plain(formatDuration(78)), '1 h 18');
  assert.equal(plain(formatDuration(60)), '1 h');
  assert.equal(plain(formatDuration(65)), '1 h 05');
  assert.equal(plain(formatDuration(0)), '0 min');
  assert.ok(formatDuration(78).includes(' '), 'espaces insécables');
  assert.equal(formatDurationLong(78), '1 heure 18 minutes');
  assert.equal(formatDurationLong(1), '1 minute');
  assert.equal(formatDurationLong(120), '2 heures');
});

test('durée affichée = écart des heures affichées (secondes ignorées)', () => {
  assert.equal(minutesBetween('2026-10-20T08:31:00+02:00', '2026-10-20T09:19:00+02:00'), 48);
  assert.equal(minutesBetween('2026-10-20T08:43:00+02:00', '2026-10-20T09:28:00+02:00'), 45);
  assert.equal(minutesBetween('2026-10-20T08:31:50+02:00', '2026-10-20T09:19:10+02:00'), 48);
  assert.equal(epochMinute('2026-10-20T08:31:59+02:00'), epochMinute('2026-10-20T08:31:00+02:00'));
});

test('distances : « 450 m », « 1,2 km »', () => {
  assert.equal(plain(formatDistance(447)), '450 m');
  assert.equal(plain(formatDistance(3)), '10 m');
  assert.equal(plain(formatDistance(1234)), '1,2 km');
  assert.equal(plain(formatDistance(1000)), '1,0 km');
});

test('heure de Paris → ISO avec décalage, été comme hiver', () => {
  assert.equal(toParisIso(parisLocalToMs('2026-10-20', '08:30')), '2026-10-20T08:30:00+02:00');
  assert.equal(toParisIso(parisLocalToMs('2026-11-03', '08:30')), '2026-11-03T08:30:00+01:00');
  assert.equal(parisOffsetMinutes(Date.parse('2026-07-01T12:00:00Z')), 120);
  assert.equal(parisOffsetMinutes(Date.parse('2026-01-01T12:00:00Z')), 60);
  // Autumn change (25/10/2026): 2:30 happens twice; the first one is kept.
  assert.equal(toParisIso(parisLocalToMs('2026-10-25', '02:30')), '2026-10-25T02:30:00+02:00');
  // Spring change (28/03/2027): 2:30 does not exist; the time after the jump.
  assert.equal(toParisIso(parisLocalToMs('2027-03-28', '02:30')), '2027-03-28T03:30:00+02:00');
});

test('jour et correspondances en toutes lettres', () => {
  assert.equal(formatDay('2026-10-20T08:30:00+02:00'), 'Mardi 20 octobre');
  assert.equal(formatShortDate('2026-10-19T06:10:00Z'), '19/10');
  assert.equal(formatTransfers(0), 'Direct');
  assert.equal(formatTransfers(1), '1 correspondance');
  assert.equal(formatTransfers(2), '2 correspondances');
});
