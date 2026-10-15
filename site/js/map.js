// The map (MapLibre GL JS 6.11.2, served from vendor/, and OpenFreeMap tiles).
//
// The map is never needed to use the site: everything it shows is also
// written in the list and the detail. It is loaded after the page, so the
// form is usable at once; if it cannot start (no WebGL, tiles unreachable),
// a short message says so and the site keeps working.

import { MAP_STYLE, ZONE_BOX } from '../config.js';
import { h } from './dom.js';
import { lineColor } from './render.js';
import { decodePolyline } from './polyline.js';

const ATTRIBUTION = 'Horaires <a href="https://www.data.gouv.fr/datasets/tisseo-reseau-transport-urbain-toulousain">Tisséo</a>, '
  + '<a href="https://www.data.gouv.fr/datasets/horaires-sncf">SNCF</a> (ODbL)';
const EMPTY = { type: 'FeatureCollection', features: [] };
const reducedMotion = () => globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

export function createMap({ container, message, legend, onPick }) {
  let map = null;
  let lib = null;
  let ready = false;
  let pending = null; // last drawing asked before the map was ready
  let popup = null;

  const showMessage = (text) => {
    message.textContent = text;
    message.hidden = !text;
  };

  async function start() {
    try {
      lib = await import('../vendor/maplibre-gl/maplibre-gl.mjs');
      loadCss();
      const [west, south, east, north] = ZONE_BOX;
      map = new lib.Map({
        container,
        style: MAP_STYLE,
        bounds: [[west + 0.25, south + 0.18], [east - 0.25, north - 0.18]],
        maxBounds: [[west - 0.3, south - 0.3], [east + 0.3, north + 0.3]],
        attributionControl: { compact: false, customAttribution: ATTRIBUTION },
        dragRotate: false,
        pitchWithRotate: false,
        touchPitch: false,
        fadeDuration: reducedMotion() ? 0 : 300,
        locale: {
          'Map.Title': 'Carte',
          'NavigationControl.ZoomIn': 'Zoomer',
          'NavigationControl.ZoomOut': 'Dézoomer',
          'Popup.Close': 'Fermer',
          'AttributionControl.ToggleAttribution': 'Afficher ou masquer les sources de la carte',
          'AttributionControl.MapFeedback': 'Signaler une erreur de carte',
        },
      });
      map.touchZoomRotate.disableRotation();
      map.addControl(new lib.NavigationControl({ showCompass: false }), 'top-right');
      map.on('load', () => {
        addLayers();
        ready = true;
        showMessage('');
        if (pending) draw(pending);
      });
      map.on('error', (event) => {
        // Tile or style errors: the map stays as it is; tell once.
        if (!ready) showMessage("Le fond de carte n'a pas pu se charger. Les trajets restent lisibles dans la liste.");
        console.warn('map error', event?.error?.message || event);
      });
      map.on('click', (event) => openPicker(event.lngLat));
    } catch (error) {
      console.warn('map unavailable', error);
      showMessage("La carte ne peut pas s'afficher sur cet appareil. Les trajets restent lisibles dans la liste.");
    }
  }

  function loadCss() {
    if (document.querySelector('link[data-maplibre]')) return;
    document.head.append(h('link', { rel: 'stylesheet', href: 'vendor/maplibre-gl/maplibre-gl.css', 'data-maplibre': '' }));
  }

  function addLayers() {
    map.addSource('trip', { type: 'geojson', data: EMPTY });
    map.addSource('trip-points', { type: 'geojson', data: EMPTY });
    const ride = ['==', ['get', 'kind'], 'ride'];
    map.addLayer({ id: 'trip-casing', type: 'line', source: 'trip', filter: ride,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#FFFFFF', 'line-width': 10 } });
    map.addLayer({ id: 'trip-walk', type: 'line', source: 'trip', filter: ['==', ['get', 'kind'], 'walk'],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#4F6585', 'line-width': 4, 'line-dasharray': [0.1, 2] } });
    map.addLayer({ id: 'trip-line', type: 'line', source: 'trip', filter: ['all', ride, ['!=', ['get', 'future'], true]],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': ['get', 'color'], 'line-width': 6 } });
    map.addLayer({ id: 'trip-line-future', type: 'line', source: 'trip', filter: ['all', ride, ['==', ['get', 'future'], true]],
      layout: { 'line-join': 'round' },
      paint: { 'line-color': ['get', 'color'], 'line-width': 6, 'line-dasharray': [1.4, 1] } });
    map.addLayer({ id: 'trip-points', type: 'circle', source: 'trip-points',
      paint: {
        'circle-radius': ['match', ['get', 'kind'], 'stop', 4.5, 7],
        'circle-color': ['match', ['get', 'kind'], 'end', '#24476F', '#FFFFFF'],
        'circle-stroke-color': '#24476F',
        'circle-stroke-width': ['match', ['get', 'kind'], 'stop', 2, 3],
      } });
  }

  function openPicker(lngLat) {
    if (!onPick) return;
    popup?.remove();
    const pick = (role) => () => {
      popup?.remove();
      onPick(role, { lat: lngLat.lat, lon: lngLat.lng });
    };
    const content = h('div', { class: 'pick-popup' },
      h('button', { type: 'button', text: "Partir d'ici", onclick: pick('origin') }),
      h('button', { type: 'button', text: 'Arriver ici', onclick: pick('destination') }));
    popup = new lib.Popup({ closeButton: true, focusAfterOpen: true, maxWidth: '240px' })
      .setLngLat(lngLat).setDOMContent(content).addTo(map);
  }

  /** Draw a trip (or only the chosen places when trip is null). */
  function draw(drawing) {
    pending = drawing;
    if (!ready) return;
    const { trip, origin, destination } = drawing;
    const lines = [];
    const points = [];
    const coords = [];
    if (trip) {
      for (const leg of trip.legs) {
        let path = [];
        try { path = decodePolyline(leg.points); } catch { path = []; }
        if (path.length < 2 && Number.isFinite(leg.from.lat) && Number.isFinite(leg.to.lat)) {
          path = [[leg.from.lon, leg.from.lat], [leg.to.lon, leg.to.lat]];
        }
        if (path.length < 2) continue;
        coords.push(...path);
        lines.push({
          type: 'Feature',
          properties: { kind: leg.transit ? 'ride' : 'walk', color: leg.transit ? lineColor(leg) : '#4F6585', future: Boolean(leg.future) },
          geometry: { type: 'LineString', coordinates: path },
        });
        if (leg.transit) {
          for (const end of [leg.from, leg.to]) {
            if (Number.isFinite(end.lat)) points.push(point('stop', end.lon, end.lat));
          }
        }
      }
    }
    if (origin) { points.push(point('start', origin.lon, origin.lat)); coords.push([origin.lon, origin.lat]); }
    if (destination) { points.push(point('end', destination.lon, destination.lat)); coords.push([destination.lon, destination.lat]); }
    map.getSource('trip').setData({ type: 'FeatureCollection', features: lines });
    map.getSource('trip-points').setData({ type: 'FeatureCollection', features: points });
    legend.hidden = !trip;
    if (coords.length) fit(coords);
  }

  function fit(coords) {
    const bounds = coords.reduce((b, c) => b.extend(c), new lib.LngLatBounds(coords[0], coords[0]));
    const small = container.clientWidth < 500;
    map.fitBounds(bounds, {
      padding: small ? { top: 52, bottom: 70, left: 30, right: 56 } : { top: 60, bottom: 90, left: 60, right: 70 },
      maxZoom: 15,
      animate: !reducedMotion(),
      duration: 600,
    });
  }

  const point = (kind, lon, lat) => ({ type: 'Feature', properties: { kind }, geometry: { type: 'Point', coordinates: [lon, lat] } });

  start();
  return {
    draw,
    resize: () => map?.resize(),
  };
}
