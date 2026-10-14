// Settings of the site. The only value to change before going live is API_BASE.

// Address of the itinerary server (Caddy + OpenTripPlanner), without a final "/".
// TO REPLACE with the real DuckDNS sub-domain, for example
// 'https://toulouse-demain.duckdns.org'. If the server moves elsewhere than
// *.duckdns.org, also update connect-src in the Content-Security-Policy of
// index.html (a test checks that both agree).
export const API_BASE = 'https://SOUS-DOMAINE.duckdns.org';

// Contract with the server (docs/adr/0001-moteur-et-hebergement.md):
// - OTP GraphQL API: POST {API_BASE}/otp/gtfs/v1
// - resolved scenario filters: GET {API_BASE}/meta/scenario-filters.json
export const GRAPHQL_URL = `${API_BASE}/otp/gtfs/v1`;
export const FILTERS_URLS = [
  `${API_BASE}/meta/scenario-filters.json`,
  // Fallback: copy taken from the latest graph release when the site is
  // published (.github/workflows/pages.yml), if the server does not serve it.
  'data/scenario-filters.json',
];

// Area covered by the graph: rectangle of all Tisséo stops + 10 km, measured
// by the first CI run (ADR 0001, "Mesures du premier passage du CI", [S28]).
// [west, south, east, north]. Addresses outside are not proposed.
export const ZONE_BOX = [1.02706, 43.30141, 1.81453, 43.83973];

// Base map: OpenFreeMap "Positron" style (free, no key, no cookie;
// https://openfreemap.org, consulted on 14/10/2026).
export const MAP_STYLE = 'https://tiles.openfreemap.org/styles/positron';
