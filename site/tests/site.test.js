// Static checks of the published files: security policy, no inline code,
// no external resource, every referenced file present, vendored files intact.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { API_BASE, MAP_STYLE } from '../config.js';
import { GEOCODER_BASE } from '../js/geocode.js';

const site = new URL('../', import.meta.url);
const read = (path) => readFileSync(new URL(path, site), 'utf8');
const html = read('index.html');
const css = read('css/app.css');
const csp = /http-equiv="Content-Security-Policy" content="([^"]+)"/.exec(html)[1];
const directives = Object.fromEntries(csp.split(';').map((d) => d.trim().split(/\s+/)).filter((d) => d[0]).map(([k, ...v]) => [k, v]));

function allowedBy(sources, url) {
  const { origin, host, protocol } = new URL(url);
  return sources.some((s) => {
    if (s === origin) return true;
    const wildcard = /^https:\/\/\*\.(.+)$/.exec(s);
    return Boolean(wildcard && protocol === 'https:' && host.endsWith(`.${wildcard[1]}`));
  });
}

test('la politique de sécurité autorise le serveur de config.js, le géocodeur et le fond de carte, rien d\'autre', () => {
  const connect = directives['connect-src'];
  assert.ok(allowedBy(connect, API_BASE.replace('SOUS-DOMAINE', 'exemple')), `config.js API_BASE ${API_BASE} not allowed by connect-src`);
  assert.ok(allowedBy(connect, GEOCODER_BASE));
  assert.ok(allowedBy(connect, MAP_STYLE));
  assert.equal(connect.some((s) => ['*', 'https:', 'http:', 'data:'].includes(s)), false, 'no catch-all source');
  assert.deepEqual(directives['script-src'], ["'self'"]);
  assert.deepEqual(directives['default-src'], ["'none'"]);
  assert.equal(/unsafe-inline|unsafe-eval/.test(csp), false);
});

test('aucun script en ligne, aucun attribut style, aucun gestionnaire en ligne', () => {
  for (const tag of html.match(/<script\b[^>]*>/g)) assert.match(tag, /\bsrc="/);
  assert.equal(/<script\b[^>]*>[^<]+<\/script>/.test(html), false);
  assert.equal(/\sstyle="/.test(html), false);
  assert.equal(/\son[a-z]+="/.test(html), false);
  for (const file of readdirSync(new URL('js/', site))) {
    const code = read(`js/${file}`);
    assert.equal(/\.innerHTML\s*=|insertAdjacentHTML|document\.write|eval\(|new Function\(/.test(code), false, file);
  }
});

test('aucune ressource externe chargée par la page (police, script, style)', () => {
  const refs = [...html.matchAll(/<(?:script|link)\b[^>]*(?:src|href)="([^"]+)"/g)].map((m) => m[1]);
  for (const ref of refs) assert.equal(/^(https?:)?\/\//.test(ref), false, ref);
  assert.equal(/fonts\.googleapis|fonts\.gstatic|googletagmanager|analytics/.test(html + css), false);
});

test('chaque fichier local référencé existe (HTML, CSS, imports JS)', () => {
  const refs = [...html.matchAll(/(?:src|href)="([^"#:]+)"/g)].map((m) => m[1]);
  refs.push(...[...css.matchAll(/url\('(\.\.\/[^']+)'\)/g)].map((m) => `css/${m[1]}`));
  for (const file of readdirSync(new URL('js/', site))) {
    for (const m of read(`js/${file}`).matchAll(/(?:from|import\()\s*'(\.\.?\/[^']+)'/g)) refs.push(`js/${m[1]}`);
  }
  for (const ref of refs) assert.ok(existsSync(new URL(ref, site)), ref);
  assert.ok(!refs.some((r) => r.includes('tests/')), 'tests must never be referenced by the site');
});

test('fichiers embarqués intacts (MapLibre GL JS 6.11.2, Schibsted Grotesk)', () => {
  const lines = read('vendor/SHA256SUMS').trim().split('\n');
  assert.ok(lines.length >= 9);
  for (const line of lines) {
    const [hash, path] = line.split(/\s+/);
    const actual = createHash('sha256').update(readFileSync(new URL(path, site))).digest('hex');
    assert.equal(actual, hash, path);
  }
  assert.match(read('vendor/maplibre-gl/maplibre-gl.mjs'), /blob\/v6\.11\.2\/LICENSE\.txt/);
});

test('aucune dépendance à l\'exécution', () => {
  const pkg = JSON.parse(read('package.json'));
  assert.equal(pkg.dependencies, undefined);
  assert.deepEqual(Object.keys(pkg.devDependencies), ['graphql']);
  assert.match(pkg.devDependencies.graphql, /^\d+\.\d+\.\d+$/, 'exact version');
});
