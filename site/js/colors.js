// Line badge ("pastille") colours.
//
// Rule (docs/ux/parcours.md, section 4): the background is the GTFS
// route_color sent by OTP; the text is white or #16304F, whichever has the
// best contrast. If neither reaches 4.5:1, the background is darkened until
// white text does. route_text_color is read but never wins over this rule, so
// a badly chosen colour in a GTFS feed cannot give an unreadable badge.

export const WHITE = '#FFFFFF';
export const DARK_TEXT = '#16304F';
export const MIN_CONTRAST = 4.5;
const DEFAULT_BACKGROUND = WHITE;

/** "#5bbf8a", "5BBF8A" → "#5BBF8A"; anything else → null. */
export function normalizeHex(value) {
  if (typeof value !== 'string') return null;
  const match = /^#?([0-9a-f]{6})$/i.exec(value.trim());
  return match ? `#${match[1].toUpperCase()}` : null;
}

function channels(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function toHex([r, g, b]) {
  return `#${[r, g, b].map((c) => Math.round(c).toString(16).padStart(2, '0')).join('').toUpperCase()}`;
}

/** WCAG 2 relative luminance (0 = black, 1 = white). */
export function luminance(hex) {
  const [r, g, b] = channels(hex).map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG 2 contrast ratio between two colours (1 to 21). */
export function contrast(a, b) {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

/**
 * Colours of a line badge.
 * Returns {background, text, darkened, outlined}: `darkened` is true when the
 * route colour had to be darkened, `outlined` when the background is so light
 * that the badge needs a visible border on a white card.
 */
export function badgeColors(routeColor) {
  let background = normalizeHex(routeColor) || DEFAULT_BACKGROUND;
  const onWhite = contrast(background, WHITE);
  const onDark = contrast(background, DARK_TEXT);
  if (Math.max(onWhite, onDark) >= MIN_CONTRAST) {
    return {
      background,
      text: onWhite >= onDark ? WHITE : DARK_TEXT,
      darkened: false,
      outlined: onWhite < 1.5,
    };
  }
  // Darken step by step (same hue, each channel scaled down) until white text passes.
  const base = channels(background);
  for (let factor = 0.98; factor > 0; factor -= 0.02) {
    background = toHex(base.map((c) => c * factor));
    if (contrast(background, WHITE) >= MIN_CONTRAST) break;
  }
  return { background, text: WHITE, darkened: true, outlined: false };
}
