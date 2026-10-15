"""Tests of the request building in scripts/reference_trips.py.

Run: python -m unittest discover -s scripts/tests -v

The schema test also validates every request against the official GTFS
GraphQL schema of OTP 2.10.0 when graphql-core is installed and the schema
file is given by OTP_SCHEMA (CI: .github/workflows/checks.yml). Otherwise it
is skipped.
"""

from __future__ import annotations

import contextlib
import csv
import datetime as dt
import http.server
import importlib.util
import io
import json
import os
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest import mock
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


class AirportChecksTest(unittest.TestCase):
    """Capitole → Aéroport: in 2028 the airport shuttle (AERO) is replaced by the Ligne Aéroport tram."""

    TRIP = next(t for t in TRIPS["trips"] if t["id"] == "capitole-aeroport")
    itinerary = staticmethod(TripChecksTest.itinerary)

    def results(self, legs_2028):
        return {"2028": {"itineraries": [self.itinerary(30, legs_2028)]},
                "actuel": {"itineraries": [self.itinerary(33, [(None, None), ("tisseo", "AERO")])]}}

    def test_tram_expected_in_2028(self):
        ok = self.results([("tisseo", "A"), ("futur", "C"), ("futur", "Aéroport")])
        self.assertEqual(rt.evaluate_checks(self.TRIP, ok, {"tisseo", "sncf", "futur"}), ([], []))
        # Faster by bus 31, say: only a warning.
        failures, warnings = rt.evaluate_checks(self.TRIP, self.results([("tisseo", "31")]), {"tisseo", "futur"})
        self.assertEqual((failures, len(warnings)), ([], 1))
        self.assertIn("Aéroport", warnings[0])

    def test_shuttle_in_2028_is_a_failure(self):
        # The exclusion of scenario-2028.json did not work: failure, whichever itinerary uses it.
        results = self.results([("futur", "C"), ("futur", "Aéroport")])
        results["2028"]["itineraries"].append(self.itinerary(40, [(None, None), ("tisseo", "AERO")]))
        failures, _ = rt.evaluate_checks(self.TRIP, results, {"tisseo", "futur"})
        self.assertEqual(len(failures), 1)
        self.assertIn("ligne AERO (tisseo)", failures[0])

    def test_shuttle_check_skipped_without_future_feed(self):
        # Future feed absent: scenario 2028 is today's network, the shuttle is still there.
        failures, warnings = rt.evaluate_checks(self.TRIP, self.results([("tisseo", "AERO")]), {"tisseo", "sncf"})
        self.assertEqual(failures, [])
        self.assertTrue(any("contrôle ignoré" in w for w in warnings), warnings)

    def test_config(self):
        checks = [c for c in self.TRIP["checks"] if c["scenario"] == "2028"]
        self.assertIn({"feed": "tisseo", "line": "AERO"}, [c.get("never_uses_line") for c in checks])
        self.assertIn({"feed": "futur", "line": "Aéroport"}, [c.get("fastest_uses") for c in checks])


class ReferenceTripsConfigTest(unittest.TestCase):
    def test_mockup_trip_colomiers_diagora(self):
        # Example trip of the mock-ups: Gare de Colomiers → Diagora (Labège), both scenarios.
        trip = next(t for t in TRIPS["trips"] if t["id"] == "colomiers-diagora")
        self.assertEqual(trip["mode"], "transit")
        self.assertEqual(trip["scenarios"], ["actuel", "2028"])
        self.assertEqual(trip["label"].split(" → "), ["Gare de Colomiers", "Diagora (Labège)"])
        # Diagora must be found even when the future feed could not be built.
        self.assertIn("sncf", [c["feed"] for c in trip["to"]])
        checks = {c["scenario"]: c for c in trip["checks"]}
        self.assertEqual(checks["actuel"]["severity"], "failure")
        self.assertEqual(checks["2028"]["fastest_uses"], {"feed": "futur", "line": "C"})

    def test_trip_ids_are_unique(self):
        ids = [t["id"] for t in TRIPS["trips"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_diagora_resolution_order(self):
        trip = next(t for t in TRIPS["trips"] if t["id"] == "colomiers-diagora")
        with tempfile.TemporaryDirectory() as tmp:
            gtfs = Path(tmp)
            write_stops(gtfs / "futur.gtfs.zip", [("F1", "Diagora", 43.544148, 1.509680)])
            write_stops(gtfs / "sncf.gtfs.zip", [("S1", "Labège Innopole", 43.547467, 1.512964)])
            write_stops(gtfs / "tisseo.gtfs.zip", [("T1", "Capitole", 43.6, 1.44)])
            place = rt.resolve_place(trip["to"], gtfs, {})
            self.assertEqual((place["feed"], place["lat"]), ("futur", 43.544148))
            # Without the future feed: last resort, the Labège-Innopole station.
            (gtfs / "futur.gtfs.zip").unlink()
            place = rt.resolve_place(trip["to"], gtfs, {})
            self.assertEqual(place["feed"], "sncf")


def write_stops(path: Path, stops: list[tuple]) -> None:
    """Minimal GTFS zip with only stops.txt (enough for resolve_place)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["stop_id", "stop_name", "stop_lat", "stop_lon"])
    writer.writerows(stops)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("stops.txt", buffer.getvalue())


class FakeOtp(http.server.BaseHTTPRequestHandler):
    """Answers the three queries of reference_trips.py like OTP would (synthetic data)."""

    requests: list[dict] = []

    def log_message(self, *args):  # keep the test output quiet
        pass

    def do_POST(self):
        assert self.path == "/otp/gtfs/v1", self.path
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOtp.requests.append(body)
        if body["query"] == rt.FEEDS_QUERY:
            answer = {"data": {"feeds": [
                {"feedId": "tisseo", "agencies": [{"gtfsId": "tisseo:1", "name": "Tisséo"}]},
                {"feedId": "sncf", "agencies": [{"gtfsId": "sncf:A1", "name": "SNCF"}]},
                {"feedId": "futur", "agencies": [{"gtfsId": "futur:FUT", "name": "Futur"}]}]}}
        elif body["query"] == rt.ROUTES_QUERY:
            answer = {"data": {"routes": [{"gtfsId": r, "shortName": r.split(":")[1], "mode": "SUBWAY"}
                                          for r in sorted(ROUTES)]}}
        else:
            answer = self.plan(body["variables"])
        data = json.dumps(answer).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    @staticmethod
    def plan(variables: dict) -> dict:
        """One itinerary: walk only for street modes; line C if allowed, else line B."""
        start = variables["dateTime"]["earliestDeparture"]
        place = {"name": "X", "lat": 43.6, "lon": 1.4, "stop": None}
        if variables["modes"].get("directOnly"):
            legs = [{"mode": variables["modes"]["direct"][0], "duration": 600, "from": place, "to": place,
                     "agency": None, "route": None}]
        else:
            filters = (variables.get("preferences") or {}).get("transit", {}).get("filters", [])
            excluded = {a for f in filters for s in f["exclude"] for a in s.get("agencies", [])}
            agency, route = ("tisseo:1", "tisseo:B") if "futur:FUT" in excluded else ("futur:FUT", "futur:C")
            legs = [{"mode": "SUBWAY", "duration": 1500, "from": place, "to": place,
                     "agency": {"gtfsId": agency}, "route": {"gtfsId": route, "shortName": route.split(":")[1]},
                     "legGeometry": {"points": "_p~iF~ps|U_ulLnnqC"}}]
        node = {"start": start, "end": start, "duration": sum(l["duration"] for l in legs),
                "numberOfTransfers": 0, "walkDistance": 100, "legs": legs}
        return {"data": {"planConnection": {"routingErrors": [], "edges": [{"node": node}]}}}


class MainEndToEndTest(unittest.TestCase):
    """main() against a fake OTP server: outputs and the demo-responses.json contract."""

    def run_main(self, tmp: Path) -> tuple[int, dict]:
        gtfs = tmp / "gtfs"
        gtfs.mkdir()
        write_stops(gtfs / "tisseo.gtfs.zip", [
            ("T1", "Capitole", 43.6045, 1.4455), ("T2", "Aéroport", 43.6312, 1.3747),
            ("T3", "Marengo-SNCF", 43.611, 1.455), ("T4", "Ramonville", 43.5559, 1.4771),
            ("T5", "Colomiers Gare", 43.6044, 1.3353), ("T6", "Labège Gare", 43.539, 1.5206)])
        write_stops(gtfs / "sncf.gtfs.zip", [("S1", "Colomiers", 43.6037, 1.3342),
                                             ("S2", "Labège Innopole", 43.5475, 1.513)])
        write_stops(gtfs / "futur.gtfs.zip", [("F1", "Diagora", 43.544148, 1.509680)])
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeOtp)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        FakeOtp.requests = []
        argv = ["reference_trips.py", "--otp-url", f"http://127.0.0.1:{server.server_address[1]}",
                "--gtfs-dir", str(gtfs), "--trips", str(ROOT / "config" / "reference-trips.json"),
                "--scenarios", str(ROOT / "config" / "scenarios.json"), "--output", str(tmp / "trips.json"),
                "--filters-output", str(tmp / "filters.json"), "--raw-output", str(tmp / "demo.json")]
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            code = rt.main()
        return code, json.loads((tmp / "demo.json").read_text(encoding="utf-8"))

    def test_demo_responses_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, demo = self.run_main(Path(tmp))
            self.assertEqual(code, 0, (Path(tmp) / "trips.json").read_text(encoding="utf-8"))
            self.assertEqual(set(demo), {"recorded_at", "query", "requests", "scenario_filters"})
            recorded = dt.datetime.fromisoformat(demo["recorded_at"])
            self.assertEqual(recorded.utcoffset(), dt.timedelta(0))
            self.assertEqual(demo["query"], rt.PLAN_QUERY)
            # Same content as scenario-filters.json.
            filters = json.loads((Path(tmp) / "filters.json").read_text(encoding="utf-8"))
            self.assertEqual(demo["scenario_filters"], filters)

            transit = [t for t in TRIPS["trips"] if t["mode"] == "transit"]
            expected = [(t["id"], s) for t in transit for s in t["scenarios"]]
            self.assertEqual([(r["id"], r["scenario"]) for r in demo["requests"]], expected)
            for request in demo["requests"]:
                self.assertEqual(set(request), {"id", "label", "scenario", "variables", "response"})
                self.assertIn(request["scenario"], {"actuel", "2028"})
                self.assertIn("planConnection", request["response"]["data"])
                self.assertIn("transit", request["variables"]["modes"])
            # The variables are those sent to OTP, and the response is OTP's body unchanged.
            plans = [r for r in FakeOtp.requests if r["query"] == rt.PLAN_QUERY and "transit" in r["variables"]["modes"]]
            self.assertEqual([r["variables"] for r in plans], [r["variables"] for r in demo["requests"]])
            diagora = {r["scenario"]: r for r in demo["requests"] if r["id"] == "colomiers-diagora"}
            self.assertEqual(diagora["actuel"]["variables"]["preferences"],
                             {"transit": {"filters": [{"exclude": [{"agencies": ["futur:FUT"]}]}]}})
            self.assertEqual(diagora["2028"]["response"], FakeOtp.plan(diagora["2028"]["variables"]))
            self.assertEqual(diagora["2028"]["variables"]["destination"]["label"], "Diagora (Labège)")


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
