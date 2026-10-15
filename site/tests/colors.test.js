import { test } from 'node:test';
import assert from 'node:assert/strict';
import { badgeColors, contrast, DARK_TEXT, normalizeHex, WHITE } from '../js/colors.js';

const round1 = (x) => Math.round(x * 10) / 10;

test('ratios de contraste de docs/ux/parcours.md', () => {
  // "#24476F sur le vert de C ne fait que 4,2:1, alors que #16304F fait 5,9:1"
  assert.equal(round1(contrast('#24476F', '#5BBF8A')), 4.2);
  assert.equal(round1(contrast('#16304F', '#5BBF8A')), 5.9);
  // Pastel profond : blanc dessus 9,5:1 ; brique 5,8:1 sur blanc.
  assert.equal(round1(contrast('#FFFFFF', '#24476F')), 9.5);
  assert.equal(round1(contrast('#A8473C', '#FFFFFF')), 5.8);
  assert.equal(round1(contrast('#000000', '#FFFFFF')), 21);
});

test('texte blanc ou #16304F, le plus contrasté des deux', () => {
  assert.deepEqual(badgeColors('5BBF8A'), { background: '#5BBF8A', text: DARK_TEXT, darkened: false, outlined: false });
  assert.equal(badgeColors('#F2C230').text, DARK_TEXT);
  assert.equal(badgeColors('3F4A5A').text, WHITE);
  assert.equal(badgeColors('C53030').text, WHITE);
});

test('route_text_color ne l\'emporte jamais sur la règle de contraste', () => {
  // Same background whatever text colour the GTFS asks for: the function only takes route_color.
  assert.equal(badgeColors('F2C230').text, DARK_TEXT);
});

test('sous 4,5:1 pour les deux textes, le fond est assombri jusqu\'à 4,5:1 en blanc', () => {
  const grey = badgeColors('808080');
  assert.ok(contrast('#808080', WHITE) < 4.5 && contrast('#808080', DARK_TEXT) < 4.5);
  assert.equal(grey.darkened, true);
  assert.equal(grey.text, WHITE);
  assert.ok(contrast(grey.background, WHITE) >= 4.5, grey.background);
  // Darkened, not replaced: still a grey.
  const [r, g, b] = grey.background.slice(1).match(/../g).map((h) => parseInt(h, 16));
  assert.ok(r === g && g === b && r < 0x80);
  const orange = badgeColors('E8772E');
  assert.ok(Math.max(contrast(orange.background, WHITE), contrast(orange.background, DARK_TEXT)) >= 4.5);
});

test('couleur absente ou invalide : fond blanc bordé, texte foncé', () => {
  for (const value of [null, undefined, '', 'red', '12345', '#GGGGGG']) {
    const c = badgeColors(value);
    assert.equal(c.background, '#FFFFFF');
    assert.equal(c.text, DARK_TEXT);
    assert.equal(c.outlined, true);
  }
  assert.equal(normalizeHex('5bbf8a'), '#5BBF8A');
  assert.equal(normalizeHex('#5bbf8a'), '#5BBF8A');
  assert.equal(normalizeHex('url(x)'), null);
});
