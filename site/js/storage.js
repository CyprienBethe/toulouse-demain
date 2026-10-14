// Small values kept in the visitor's browser (localStorage). The site must
// work without it (private browsing, blocked storage): every access is in a
// try/catch and a missing value falls back to the default.

const PREFIX = 'toulouse-demain.';

export function readStored(key, fallback, storage) {
  try {
    const value = (storage ?? globalThis.localStorage).getItem(PREFIX + key);
    return value === null ? fallback : value;
  } catch {
    return fallback;
  }
}

export function writeStored(key, value, storage) {
  try {
    (storage ?? globalThis.localStorage).setItem(PREFIX + key, value);
    return true;
  } catch {
    return false;
  }
}

/** Last chosen scenario; "actuel" (today) on the very first visit. */
export function storedScenario(storage) {
  const value = readStored('scenario', 'actuel', storage);
  return value === '2028' ? '2028' : 'actuel';
}

export function storeScenario(value, storage) {
  return writeStored('scenario', value === '2028' ? '2028' : 'actuel', storage);
}
