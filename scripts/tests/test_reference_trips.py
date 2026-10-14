"""Tests of the request building in scripts/reference_trips.py.

Run: python -m unittest discover -s scripts/tests -v

The schema test also validates every request against the official GTFS
GraphQL schema of OTP 2.10.0 when graphql-core is installed and the schema
file is given by OTP_SCHEMA (CI: .github/workflows/checks.yml). Otherwise it
is skipped.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("reference_trips", ROOT / "scripts" / "reference_trips.py")
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)

SCENARIOS = json.loads((ROOT / "config" / "scenarios.json").read_text(encoding="utf-8"))
REQUEST = rt.public_request(SCENARIOS["request"])
TRIPS = json.loads((ROOT / "config" / "reference-trips.json").read_text(encoding="utf-8"))
ORIGIN = {"lat": 43.6, "lon": 1.44}
DESTINATION = {"lat": 43.63, "lon": 1.37}
DEPARTURE = dt.datetime(2026, 10, 20, 8, 30, tzinfo=ZoneInfo("Europe/Paris"))
AGENCIES = {"tisseo": ["tisseo:1"], "sncf": ["sncf:A1"], "futur": ["futur:FUT"]}
ROUTES = {"tisseo:B", "tisseo:A", "futur:C", "futur:B"}


def contains_null(value) -> bool:
    if value is None:
        return True
    if isinstance(value, dict):
        return any(contains_null(v) for v in value.values())
    if isinstance(value, list):
        return any(contains_null(v) for v in value)
    return False


def all_variables() -> list[dict]:
    """Variables for every mode and scenario, with the real configuration."""
    resolved, _, _ = rt.prepare_scenarios(SCENARIOS["scenarios"], AGENCIES, ROUTES, set(), {})
    out = []
    for mode in ("transit", "walk", "bicycle"):
        for scenario in resolved.values():
            out.append(rt.build_variables("A → B", ORIGIN, DESTINATION, DEPARTURE, mode,
                                          scenario["filters"], REQUEST))
    return out


class BuildVariablesTest(unittest.TestCase):
    def test_no_null_anywhere(self):
        # OTP 2.10.0 crashes on `modes: null` ("modesArgs" is null).
        for variables in all_variables():
            self.assertFalse(contains_null(variables), variables)

    def test_transit_modes_are_explicit(self):
        variables = rt.build_variables("A → B", ORIGIN, DESTINATION, DEPARTURE, "transit", [], REQUEST)
        transit = variables["modes"]["transit"]
        self.assertEqual(transit["access"], ["WALK"])
        self.assertEqual(transit["egress"], ["WALK"])
        self.assertEqual(transit["transfer"], ["WALK"])
        modes = {m["mode"] for m in transit["transit"]}
        self.assertTrue({"BUS", "TRAM", "SUBWAY", "RAIL", "GONDOLA"} <= modes, modes)
        self.assertNotIn("directOnly", variables["modes"])

    def test_street_only_modes(self):
        walk = rt.build_variables("A → B", ORIGIN, DESTINATION, DEPARTURE, "walk", [], REQUEST)
        bike = rt.build_variables("A → B", ORIGIN, DESTINATION, DEPARTURE, "bicycle", [], REQUEST)
        self.assertEqual(walk["modes"], {"directOnly": True, "direct": ["WALK"]})
        self.assertEqual(bike["modes"], {"directOnly": True, "direct": ["BICYCLE"]})

    def test_preferences_only_when_filters(self):
        without = rt.build_variables("A → B", ORIGIN, DESTINATION, DEPARTURE, "transit", [], REQUEST)
        self.assertNotIn("preferences", without)
        filters = [{"exclude": [{"agencies": ["futur:FUT"]}]}]
        with_filters = rt.build_variables("A → B", ORIGIN, DESTINATION, DEPARTURE, "transit", filters, REQUEST)
        self.assertEqual(with_filters["preferences"], {"transit": {"filters": filters}})

    def test_departure_is_next_tuesday(self):
        config = TRIPS["departure"]
        wednesday = dt.datetime(2026, 10, 14, 10, 0, tzinfo=ZoneInfo("Europe/Paris"))
        self.assertEqual(rt.next_departure(config, wednesday).isoformat(), "2026-10-20T08:30:00+02:00")


class ScenarioTest(unittest.TestCase):
    def test_actuel_excludes_future_agencies(self):
        resolved, failures, warnings = rt.prepare_scenarios(SCENARIOS["scenarios"], AGENCIES, ROUTES, set(), {})
        self.assertEqual(resolved["actuel"]["filters"], [{"exclude": [{"agencies": ["futur:FUT"]}]}])
        self.assertEqual(resolved["2028"]["filters"], [])
        self.assertEqual((failures, warnings), ([], []))

    def test_missing_future_feed(self):
        agencies = {"tisseo": ["tisseo:1"], "sncf": ["sncf:A1"]}
        _, failures, warnings = rt.prepare_scenarios(SCENARIOS["scenarios"], agencies, ROUTES, set(), {})
        self.assertEqual(len(failures), 1)
        _, failures, warnings = rt.prepare_scenarios(SCENARIOS["scenarios"], agencies, ROUTES, {"futur"}, {})
        self.assertEqual(failures, [])
        self.assertEqual(len(warnings), 1)

    def test_scenario_file_excludes_replaced_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scenario-2028.json"
            path.write_text(json.dumps({"exclude_routes": ["tisseo:B"]}), encoding="utf-8")
            resolved, failures, warnings = rt.prepare_scenarios(
                SCENARIOS["scenarios"], AGENCIES, ROUTES, set(), {"2028": path})
            self.assertEqual(resolved["2028"]["filters"], [{"exclude": [{"routes": ["tisseo:B"]}]}])
            self.assertEqual(resolved["actuel"]["filters"], [{"exclude": [{"agencies": ["futur:FUT"]}]}])
            self.assertEqual((failures, warnings), ([], []))
            # Without the future feed, the replaced line must stay in service.
            agencies = {"tisseo": ["tisseo:1"], "sncf": ["sncf:A1"]}
            resolved, _, warnings = rt.prepare_scenarios(
                SCENARIOS["scenarios"], agencies, ROUTES, {"futur"}, {"2028": path})
            self.assertEqual(resolved["2028"]["filters"], [])
            self.assertEqual(len(warnings), 2)

    def test_unknown_route_is_a_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scenario-2028.json"
            path.write_text(json.dumps({"exclude_routes": ["tisseo:NOPE"]}), encoding="utf-8")
            _, failures, warnings = rt.prepare_scenarios(SCENARIOS["scenarios"], AGENCIES, ROUTES, set(), {"2028": path})
            self.assertEqual(failures, [])
            self.assertIn("tisseo:NOPE", warnings[0])


class TripChecksTest(unittest.TestCase):
    TRIP = next(t for t in TRIPS["trips"] if t["id"] == "colomiers-labege")

    @staticmethod
    def itinerary(minutes, legs):
        feeds = sorted({feed for feed, _ in legs if feed})
        return {"minutes": minutes, "feeds": feeds, "legs": [{"feed": f, "line": l} for f, l in legs]}

    def test_line_c_expected_in_2028(self):
        with_c = {"2028": {"itineraries": [self.itinerary(40, [(None, None), ("futur", "C")])]},
                  "actuel": {"itineraries": [self.itinerary(55, [("sncf", "TER")])]}}
        self.assertEqual(rt.evaluate_checks(self.TRIP, with_c), ([], []))
        without_c = {"2028": {"itineraries": [self.itinerary(55, [("sncf", "TER")])]},
                     "actuel": {"itineraries": [self.itinerary(55, [("sncf", "TER")])]}}
        failures, warnings = rt.evaluate_checks(self.TRIP, without_c)
        self.assertEqual(failures, [])
        self.assertEqual(len(warnings), 1)

    def test_actuel_never_uses_future_feed(self):
        results = {"2028": {"itineraries": [self.itinerary(40, [("futur", "C")])]},
                   "actuel": {"itineraries": [self.itinerary(40, [("futur", "C")])]}}
        failures, _ = rt.evaluate_checks(self.TRIP, results)
        self.assertEqual(len(failures), 1)


@unittest.skipUnless(os.environ.get("OTP_SCHEMA") and importlib.util.find_spec("graphql"),
                     "set OTP_SCHEMA and install graphql-core to validate against the OTP schema")
class OtpSchemaTest(unittest.TestCase):
    """Validate queries and variables against the official OTP 2.10.0 schema."""

    @classmethod
    def setUpClass(cls):
        from graphql import build_schema
        cls.schema = build_schema(Path(os.environ["OTP_SCHEMA"]).read_text(encoding="utf-8"))
        # OTP's schema has a deprecation mismatch (Node.id / Cluster.id) that graphql-core's
        # schema self-check rejects; it is unrelated to the queries validated here.
        cls.schema._validation_errors = []

    def test_queries_are_valid(self):
        from graphql import parse, validate
        for query in (rt.PLAN_QUERY, rt.FEEDS_QUERY, rt.ROUTES_QUERY):
            self.assertEqual(validate(self.schema, parse(query)), [], query)

    def test_variables_are_valid(self):
        from graphql import parse
        from graphql.execution.values import get_variable_values
        definitions = parse(rt.PLAN_QUERY).definitions[0].variable_definitions
        for variables in all_variables():
            result = get_variable_values(self.schema, definitions, variables)
            self.assertNotIsInstance(result, list, (result, variables))


if __name__ == "__main__":
    unittest.main()
