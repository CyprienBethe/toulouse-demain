// Validate the site's GraphQL query and variables against the official
// GTFS GraphQL schema of OTP 2.10.0.
//
// Needs the dev dependency `graphql` (npm ci) and the schema file:
//   curl -fsSL -o otp-schema.graphqls https://raw.githubusercontent.com/opentripplanner/OpenTripPlanner/v2.10.0/application/src/main/resources/org/opentripplanner/apis/gtfs/schema.graphqls
//   OTP_SCHEMA=otp-schema.graphqls npm test
// Skipped otherwise (the CI always runs it: .github/workflows/checks.yml).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { buildVariables, PLAN_QUERY, TRIP_MODES } from '../js/otp.js';

const SCHEMA_SHA256 = 'ee5c42d5fd6346b6062d057030f8cb2062517b31e93add66ca5a92cae247aac4';
const schemaPath = process.env.OTP_SCHEMA;
let graphql = null;
try {
  graphql = await import('graphql');
} catch {
  graphql = null;
}
const skip = !schemaPath ? 'OTP_SCHEMA is not set' : !graphql ? 'graphql is not installed (npm ci)' : false;

// The CI sets REQUIRE_OTP_SCHEMA=1: there, a skipped validation is a failure.
if (skip && process.env.REQUIRE_OTP_SCHEMA === '1') {
  test('validation contre le schéma OTP exigée', () => assert.fail(skip));
}

const filters = JSON.parse(readFileSync(new URL('fixtures/synthetic-scenario-filters.json', import.meta.url), 'utf8'));
const origin = { label: 'Gare de Colomiers', lat: 43.6118, lon: 1.3366 };
const destination = { label: 'Diagora, Labège', lat: 43.5462, lon: 1.5128 };

function loadSchema() {
  const text = readFileSync(schemaPath, 'utf8');
  assert.equal(createHash('sha256').update(text).digest('hex'), SCHEMA_SHA256, 'not the OTP 2.10.0 schema');
  const schema = graphql.buildSchema(text);
  // OTP's schema has a deprecation mismatch (Node.id / Cluster.id) that the
  // schema self-check rejects; it is unrelated to the query checked here.
  schema.__validationErrors = [];
  return schema;
}

test('la requête du site est valide pour OTP 2.10.0', { skip }, () => {
  const schema = loadSchema();
  const errors = graphql.validate(schema, graphql.parse(PLAN_QUERY));
  assert.deepEqual(errors.map((e) => e.message), []);
});

test('les variables sont valides pour chaque mode, scénario et type d\'heure', { skip }, async () => {
  const schema = loadSchema();
  const { getVariableValues } = await import('graphql/execution/values.js');
  const definitions = graphql.parse(PLAN_QUERY).definitions[0].variableDefinitions;
  for (const mode of TRIP_MODES) {
    for (const scenario of ['actuel', '2028']) {
      for (const type of ['depart', 'arrive']) {
        const variables = buildVariables({
          origin, destination, mode, when: { type, iso: '2026-10-20T08:30:00+02:00' },
          filters: filters.scenarios[scenario].filters, request: filters.request,
        });
        const result = getVariableValues(schema, definitions, variables);
        assert.equal(result.errors, undefined, `${mode}/${scenario}/${type}: ${result.errors?.map((e) => e.message)}`);
      }
    }
  }
});

test('modes nul refusé par la requête elle-même', { skip }, async () => {
  const schema = loadSchema();
  const { getVariableValues } = await import('graphql/execution/values.js');
  const definitions = graphql.parse(PLAN_QUERY).definitions[0].variableDefinitions;
  const variables = buildVariables({ origin, destination, mode: 'walk', when: { type: 'depart', iso: '2026-10-20T08:30:00+02:00' } });
  const result = getVariableValues(schema, definitions, { ...variables, modes: null });
  assert.ok(result.errors?.length, 'a null modes must be rejected before reaching OTP');
});
