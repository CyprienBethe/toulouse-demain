// Pictograms (16 px). Drawn with strokes in currentColor.
import { svgIcon } from './dom.js';

const MODE_PATHS = {
  SUBWAY: ['M4 12V4.5A2.5 2.5 0 0 1 6.5 2h3A2.5 2.5 0 0 1 12 4.5V12Z', 'M4 7.5h8', 'M6 12 4.5 14.5M10 12l1.5 2.5'],
  RAIL: ['M4 11V5l2-3h4l2 3v6a1.5 1.5 0 0 1-1.5 1.5h-5A1.5 1.5 0 0 1 4 11Z', 'M4 6.5h8', 'M6 9.5h.01M10 9.5h.01', 'M6 12.5l-1.5 2M10 12.5l1.5 2'],
  BUS: ['M3.5 12V4a2 2 0 0 1 2-2h5a2 2 0 0 1 2 2v8Z', 'M3.5 7.5h9', 'M5.5 12v2.5M10.5 12v2.5'],
  TRAM: ['M6 1.5h4M8 1.5V4', 'M4.5 12V6a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v6Z', 'M4.5 8h7', 'M6 12l-1.5 2.5M10 12l1.5 2.5'],
  GONDOLA: ['M1.5 3.5 14.5 1.5', 'M8 2.7V5.5', 'M5.5 5.5h5A1.5 1.5 0 0 1 12 7v5a1.5 1.5 0 0 1-1.5 1.5h-5A1.5 1.5 0 0 1 4 12V7a1.5 1.5 0 0 1 1.5-1.5Z', 'M4 9h8'],
};
MODE_PATHS.MONORAIL = MODE_PATHS.SUBWAY;
MODE_PATHS.TROLLEYBUS = MODE_PATHS.BUS;
MODE_PATHS.COACH = MODE_PATHS.BUS;
MODE_PATHS.CABLE_CAR = MODE_PATHS.GONDOLA;
MODE_PATHS.FUNICULAR = MODE_PATHS.TRAM;

export function modeIcon(mode) {
  return svgIcon(16, MODE_PATHS[mode] || ['M8 3a5 5 0 1 0 0 10A5 5 0 0 0 8 3Z']);
}

/** Arrow next to a comparison: earlier arrival (down: less time), later (up), same (=). */
export function verdictIcon(verdict) {
  if (verdict === 'better') return svgIcon(16, ['M8 2v11', 'M3.5 8.5 8 13l4.5-4.5']);
  if (verdict === 'worse') return svgIcon(16, ['M8 14V3', 'M3.5 7.5 8 3l4.5 4.5']);
  return svgIcon(16, ['M3 6h10', 'M3 10h10']);
}

export function clockIcon() {
  return svgIcon(16, ['M8 2.5a5.5 5.5 0 1 0 0 11a5.5 5.5 0 0 0 0-11Z', 'M8 5v3.2l2 1.3']);
}
