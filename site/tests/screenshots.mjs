// Screenshots of the site with the SYNTHETIC fixtures (developer tool, not run in CI).
//
//   npm install --no-save playwright-core@1.56.1
//   node tests/screenshots.mjs [output-dir]
// Env: CHROMIUM (browser path, default /opt/pw-browsers/chromium),
//      PLAYWRIGHT_MODULE (module to import, default "playwright-core"),
//      AXE (optional path to axe.min.js of axe-core: accessibility audit of each screen).
//
// The site is served from this folder; the itinerary server, the geocoder
// and the base map are replaced by the fixtures of tests/fixtures/. Nothing
// leaves the machine. Screenshots are not versioned.

import { createServer } from 'node:http';
import { mkdirSync, readFileSync } from 'node:fs';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

const site = fileURLToPath(new URL('..', import.meta.url));
const out = process.argv[2] || join(site, 'tests', 'screenshots');
mkdirSync(out, { recursive: true });
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
const fixture = (name) => readFileSync(join(site, 'tests', 'fixtures', name), 'utf8');
const geocoder = JSON.parse(fixture('synthetic-geocoder.json'));
const API = 'https://essai.duckdns.org';

const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.txt': 'text/plain' };
const server = createServer((req, res) => {
  const path = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)).replace(/^(\.\.[/\\])+/, '');
  const file = join(site, path.endsWith('/') ? `${path}index.html` : path);
  try {
    const body = readFileSync(file);
    res.writeHead(200, { 'Content-Type': TYPES[extname(file)] || 'application/octet-stream' });
    res.end(body);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('not found');
  }
});
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}/`;

const testConfig = readFileSync(join(site, 'config.js'), 'utf8')
  .replace(/export const API_BASE = '[^']*';/, `export const API_BASE = '${API}';`);
const style = {
  version: 8,
  name: 'synthetic test style',
  sources: {
    attribution: {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
      attribution: '<a href="https://openfreemap.org">OpenFreeMap</a> <a href="https://www.openmaptiles.org/">© OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    },
  },
  layers: [
    { id: 'background', type: 'background', paint: { 'background-color': '#EDF0F4' } },
    { id: 'attribution', type: 'line', source: 'attribution' },
  ],
};
const cors = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS' };

async function setupRoutes(context, { serverDown = false } = {}) {
  await context.route('**/config.js', (route) => route.fulfill({ contentType: 'text/javascript', body: testConfig }));
  await context.route('**/demo/demo-responses.json', (route) => route.fulfill({ contentType: 'application/json', body: fixture('synthetic-demo-responses.json') }));
  await context.route(`${API}/**`, async (route) => {
    const request = route.request();
    if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors });
    if (serverDown) return route.abort('connectionrefused');
    if (request.url().endsWith('/meta/scenario-filters.json')) {
      return route.fulfill({ headers: cors, contentType: 'application/json', body: fixture('synthetic-scenario-filters.json') });
    }
    const { variables } = JSON.parse(request.postData() || '{}');
    const excluded = JSON.stringify(variables?.preferences || {});
    const name = excluded.includes('futur:SYNTH_FUT') ? 'synthetic-plan-actuel.json' : 'synthetic-plan-2028.json';
    await new Promise((r) => setTimeout(r, 150));
    return route.fulfill({ headers: cors, contentType: 'application/json', body: fixture(name) });
  });
  await context.route('https://data.geopf.fr/**', (route) => {
    const url = new URL(route.request().url());
    const q = (url.searchParams.get('q') || '').toLowerCase();
    const body = url.pathname.includes('reverse') ? geocoder.reverse : q.includes('lab') || q.includes('diag') ? geocoder.labege : geocoder.colomiers;
    return route.fulfill({ headers: cors, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await context.route('https://tiles.openfreemap.org/**', (route) => route.fulfill({ headers: cors, contentType: 'application/json', body: JSON.stringify(style) }));
}

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM || '/opt/pw-browsers/chromium',
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});
const problems = [];
const axeSource = process.env.AXE ? readFileSync(process.env.AXE, 'utf8') : null;

async function audit(page, name) {
  if (!axeSource) return;
  await page.evaluate(axeSource);
  const violations = await page.evaluate(async () => (await globalThis.axe.run(document, {
    runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice'] },
  })).violations.map((v) => `${v.impact} ${v.id}: ${v.nodes.length} × ${v.nodes[0].target.join(' ')} — ${v.help}`));
  for (const v of violations) problems.push(`[axe ${name}] ${v}`);
}

async function newPage(viewport, options = {}) {
  const context = await browser.newContext({ viewport, locale: 'fr-FR', timezoneId: 'Europe/Paris', deviceScaleFactor: 1 });
  await setupRoutes(context, options);
  const page = await context.newPage();
  await page.clock.setFixedTime(new Date('2026-10-20T08:25:00+02:00'));
  // With the server down, network errors in the console are expected.
  page.on('console', (m) => {
    if (['error', 'warning'].includes(m.type()) && !options.serverDown) problems.push(`[${viewport.width}] console ${m.type()}: ${m.text()}`);
  });
  page.on('pageerror', (e) => problems.push(`[${viewport.width}] page error: ${e.message}`));
  return { context, page };
}

async function shot(page, name, fullPage = true) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(800);
  await page.screenshot({ path: join(out, `${name}.png`), fullPage });
  console.log('screenshot', name);
  await audit(page, name);
}

async function pick(page, inputId, text) {
  await page.fill(`#${inputId}`, text);
  await page.waitForSelector(`#${inputId.replace('input', 'list')} [role=option]:not(.info)`);
  await page.click(`#${inputId.replace('input', 'list')} [role=option]:not(.info) >> nth=0`);
}

async function search(page) {
  await pick(page, 'from-input', 'Gare de Colom');
  await pick(page, 'to-input', 'Diagora');
  await page.click('label[for=when-depart]');
  await page.fill('#when-date', '2026-10-20');
  await page.fill('#when-time', '08:30');
  await page.click('button[type=submit]');
  await page.waitForSelector('#results-list .trip-button');
}

for (const [label, viewport] of [['mobile', { width: 390, height: 844 }], ['desktop', { width: 1280, height: 800 }]]) {
  const full = label === 'mobile';
  const { context, page } = await newPage(viewport);
  await page.goto(base);
  await page.waitForSelector('.maplibregl-canvas', { timeout: 15000 }).catch(() => problems.push(`[${label}] no map canvas`));
  await shot(page, `${label}-1-recherche-aujourdhui`, full);
  await search(page);
  await shot(page, `${label}-2-resultats-aujourdhui`, full);
  await page.click('[data-scenario="2028"]');
  await page.waitForSelector('#results-list .bars');
  await shot(page, `${label}-3-resultats-2028`, full);
  await page.click('#results-list .trip-button >> nth=0');
  await page.waitForSelector('#detail-title');
  await page.click('.stops-toggle >> nth=0').catch(() => {});
  await shot(page, `${label}-4-detail-2028`, full);
  await page.click('#back');
  await page.click('#projection a');
  await page.waitForSelector('#hypotheses[open]');
  await shot(page, `${label}-5-hypotheses`, false);
  await page.keyboard.press('Escape');
  // Memorised scenario: a new visit opens on 2028.
  await page.reload();
  const pressed = await page.getAttribute('[data-scenario="2028"]', 'aria-pressed');
  if (pressed !== 'true') problems.push(`[${label}] scenario not remembered after reload`);
  await shot(page, `${label}-6-recherche-2028-memorise`, full);
  await context.close();

  const demo = await newPage(viewport);
  await demo.page.goto(`${base}?demo=1`);
  await demo.page.waitForSelector('#demo-trips button');
  await shot(demo.page, `${label}-7-demo-recherche`, full);
  await demo.page.click('#demo-trips button');
  await demo.page.waitForSelector('#results-list .trip-button');
  await demo.page.click('[data-scenario="2028"]');
  await demo.page.waitForSelector('#results-list .bars');
  await shot(demo.page, `${label}-8-demo-2028`, full);
  await demo.context.close();

  const down = await newPage(viewport, { serverDown: true });
  await down.page.goto(base);
  await search(down.page).catch(() => {});
  await down.page.waitForSelector('#results-notice:not([hidden])');
  await shot(down.page, `${label}-9-serveur-injoignable`, full);
  await down.context.close();
}

// A few behaviours that the screenshots above do not show.
{
  const viewport = { width: 1280, height: 800 };
  const { context, page } = await newPage(viewport);
  const expect = async (what, ok) => { if (!(await ok)) problems.push(`[check] ${what}`); };
  await page.goto(base);
  await pick(page, 'from-input', 'Gare de Colom');
  await pick(page, 'to-input', 'Diagora');
  await page.click('label[for=when-arrive]');
  await page.fill('#when-date', '2026-10-20');
  await page.fill('#when-time', '10:00');
  await page.click('[data-scenario="2028"]');
  await page.click('button[type=submit]');
  await page.waitForSelector('#results-list .verdict');
  await expect('header says "arrivée avant 10:00"', page.textContent('#res-when').then((t) => t.includes('arrivée avant 10:00')));
  await expect('"arrive by" compares departures', page.textContent('#results-list').then((t) => t.includes("Départ 42 min plus tôt qu'aujourd'hui")));
  await page.click('#edit');
  await page.click('label[for=mode-walk]');
  await page.click('label[for=when-now]');
  await page.click('button[type=submit]');
  await page.waitForSelector('#results-notice:not([hidden])');
  await expect('walk in 2028: no double bar', page.locator('#results-list .bars').count().then((n) => n === 0));
  await expect('walk in 2028: explained', page.textContent('#results-notice').then((t) => t.includes('le réseau 2028 ne change rien')));
  await expect('header says "départ maintenant (8:25)"', page.textContent('#res-when').then((t) => t.includes('départ maintenant (8:25), à pied')));
  await context.close();

  const missing = await browser.newContext({ viewport, locale: 'fr-FR', timezoneId: 'Europe/Paris' });
  await setupRoutes(missing);
  await missing.route('**/demo/demo-responses.json', (route) => route.fulfill({ status: 404, body: 'not found' }));
  const p2 = await missing.newPage();
  await p2.goto(`${base}?demo=1`);
  await p2.waitForSelector('#search-notice:not([hidden])');
  await expect('missing demo file explained', p2.textContent('#search-notice').then((t) => t.includes('Pas de démonstration')));
  await missing.close();
  console.log('behaviour checks done');
}

await browser.close();
server.close();
if (problems.length) {
  console.log(`\n${problems.length} problem(s):`);
  for (const p of problems) console.log(' -', p);
} else console.log('\nno console error, no page error');
