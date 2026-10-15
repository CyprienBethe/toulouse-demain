// Address search with the geocoding service of the IGN Géoplateforme, which
// took over the "API Adresse" of the Base Adresse Nationale (data.gouv.fr,
// "L'API Adresse de la Base Adresse Nationale est transférée à l'IGN").
//
// - https://data.geopf.fr/geocodage/search  (address and point of interest)
// - https://data.geopf.fr/geocodage/reverse (coordinates → address)
// Free and open, no key: 50 requests per second per IP address
// (data.gouv.fr, "API Géoplateforme - Géocodage"), terms of cartes.gouv.fr.
// The site sends at most one search per pause in typing (debounce).

export const GEOCODER_BASE = 'https://data.geopf.fr/geocodage';

/** URL of a search. `near` biases the results ({lat, lon}). */
export function searchUrl(text, { near, limit = 6, poi = true } = {}) {
  const params = new URLSearchParams({ q: text, limit: String(limit), autocomplete: '1' });
  params.set('index', poi ? 'address,poi' : 'address');
  if (near) {
    params.set('lat', String(near.lat));
    params.set('lon', String(near.lon));
  }
  return `${GEOCODER_BASE}/search?${params}`;
}

/** URL of a reverse search (the address of a point). */
export function reverseUrl(lat, lon) {
  const params = new URLSearchParams({ lat: String(lat), lon: String(lon), limit: '1', index: 'address' });
  return `${GEOCODER_BASE}/reverse?${params}`;
}

const first = (v) => (Array.isArray(v) ? v[0] : v);
const text = (v) => (typeof first(v) === 'string' ? first(v).trim() : '');

/** Main line, second line and city of a result: "12 Rue Alsace-Lorraine" / "31000 Toulouse" / "Toulouse". */
export function describeFeature(properties = {}) {
  const p = properties;
  const city = text(p.city);
  if (p._type === 'poi' || p.toponym || Array.isArray(p.name)) {
    const name = text(p.toponym) || text(p.name) || text(p.label);
    return { name, detail: [text(p.postcode), city].filter(Boolean).join(' '), city };
  }
  if (p.type === 'municipality') return { name: city || text(p.name) || text(p.label), detail: text(p.context), city: '' };
  const name = text(p.name) || text(p.label);
  return { name, detail: [text(p.postcode), city].filter(Boolean).join(' '), city };
}

function inBox(lat, lon, box) {
  if (!box) return true;
  const [west, south, east, north] = box;
  return lon >= west && lon <= east && lat >= south && lat <= north;
}

/**
 * Places of a GeoJSON answer, within the covered zone (`box` =
 * [west, south, east, north]), without duplicates: [{label, name, detail, lat, lon}].
 */
export function parsePlaces(geojson, box) {
  const out = [];
  const seen = new Set();
  for (const feature of geojson?.features || []) {
    const [lon, lat] = feature?.geometry?.coordinates || [];
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || !inBox(lat, lon, box)) continue;
    const { name, detail, city } = describeFeature(feature.properties);
    if (!name) continue;
    // "Gare de Colomiers" already says where it is; "Allée du Comminges" needs ", Colomiers".
    const label = city && !name.toLowerCase().includes(city.toLowerCase()) ? `${name}, ${city}` : name;
    if (seen.has(label)) continue;
    seen.add(label);
    out.push({ label, name, detail, lat, lon });
  }
  return out;
}

async function getJson(url, signal, fetchImpl) {
  const response = await (fetchImpl || globalThis.fetch)(url, { signal, credentials: 'omit' });
  if (!response.ok) {
    const error = new Error(`HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

/** Search places; falls back to addresses only if the combined index is refused. */
export async function searchPlaces(query, { near, box, signal, fetchImpl } = {}) {
  try {
    return parsePlaces(await getJson(searchUrl(query, { near }), signal, fetchImpl), box);
  } catch (error) {
    if (error?.status !== 400) throw error;
    return parsePlaces(await getJson(searchUrl(query, { near, poi: false }), signal, fetchImpl), box);
  }
}

/** Address of a point, or null. */
export async function reversePlace(lat, lon, { signal, fetchImpl } = {}) {
  const places = parsePlaces(await getJson(reverseUrl(lat, lon), signal, fetchImpl));
  return places[0] || null;
}
