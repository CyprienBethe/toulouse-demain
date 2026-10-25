#!/usr/bin/env python3
"""Compute the reference trips in each scenario against a running OTP server.

Usage:
    python scripts/reference_trips.py --otp-url http://127.0.0.1:8080 \
        --gtfs-dir build/otp/gtfs --trips config/reference-trips.json \
        --scenarios config/scenarios.json --output build/report/trips.json \
        [--allow-missing-feed futur] \
        [--scenario-file 2028=build/gtfs/scenario-2028.json] \
        [--filters-output build/report/scenario-filters.json] \
        [--raw-output build/report/demo-responses.json]

How a scenario works: the graph contains the three feeds (tisseo, sncf,
futur). For each request, the agencies of the feeds listed in
`exclude_feeds` (and the routes in `exclude_routes`) are excluded with the
`preferences.transit.filters` argument of the `planConnection` query of the
OTP GTFS GraphQL API. The front-end must send exactly the same filters: their
resolved version (real agency and route ids) is written to --filters-output.

Options:
- --allow-missing-feed FEED: a scenario that excludes FEED while FEED is not
  in the graph gives a warning instead of a failure (used when the future
  feed could not be built: the current network is still tested and published).
- --scenario-file SCENARIO=PATH: JSON file {"exclude_routes": [...]} whose
  routes are also excluded in SCENARIO (the Tisséo lines replaced by a line
  of the future feed). Ignored, with a warning, when the future feed is absent.
- --raw-output FILE: raw GraphQL answers of the transit reference trips, for
  the demo mode of the front-end (published with the graph as
  demo-responses.json). Contract, read by site/:
    {"recorded_at": "<ISO 8601, UTC>",
     "query": "<PLAN_QUERY, the GraphQL query that produced the answers>",
     "requests": [{"id": "<trip id>", "label": "<trip label>",
                   "scenario": "actuel" | "2028",
                   "variables": {...}, "response": {...}}],
     "scenario_filters": {<same content as --filters-output>}}
  "response" is the JSON body returned by OTP, unchanged ({"data": ...}, or
  {"errors": [...]} when the request failed).

Checks that make the script fail (exit code 1):
- a reference trip returns no itinerary;
- an itinerary of a scenario uses a feed that the scenario excludes;
- a walk (or bicycle) trip does not return a walk-only (or bicycle) itinerary;
- a per-trip check of severity "failure" (config/reference-trips.json).
Warnings are reported but do not fail the script.

Per-trip checks ("checks" in config/reference-trips.json), each for one scenario:
- "fastest_uses": {"feed", "line"}: the fastest itinerary has a leg on that line;
- "never_uses_feed": "<feed>": no itinerary uses that feed;
- "never_uses_line": {"feed", "line"}: no itinerary has a leg on that line
  (for example a Tisséo line replaced in 2028 by a line of the future feed).
- "uses_stop": {"feed", "pattern"}: at least one itinerary boards or alights a
  vehicle of that feed at a stop whose normalized name matches the pattern
  (for example a TER halt of the future feed).
"line" is the route short name returned by OTP. Optional "requires_feed": the
check is skipped (warning) when that feed is absent from the graph.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from zoneinfo import ZoneInfo

FUTURE_FEED = "futur"
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

FEEDS_QUERY = "{ feeds { feedId agencies { gtfsId name } } }"
ROUTES_QUERY = "{ routes { gtfsId shortName mode } }"

# Also the query of the demo answers (--raw-output): it asks for what an
# itinerary card and its map need (times, lines and colours, leg geometry as an
# encoded polyline).
PLAN_QUERY = """
query Plan($origin: PlanLabeledLocationInput!, $destination: PlanLabeledLocationInput!,
           $dateTime: PlanDateTimeInput!, $modes: PlanModesInput, $preferences: PlanPreferencesInput) {
  planConnection(origin: $origin, destination: $destination, dateTime: $dateTime,
                 modes: $modes, preferences: $preferences, first: 3) {
    searchDateTime
    routingErrors { code description }
    edges {
      node {
        start
        end
        duration
        numberOfTransfers
        walkDistance
        walkTime
        waitingTime
        legs {
          mode
          transitLeg
          start { scheduledTime estimated { time delay } }
          end { scheduledTime estimated { time delay } }
          duration
          distance
          headsign
          from { name lat lon stop { gtfsId } }
          to { name lat lon stop { gtfsId } }
          agency { gtfsId name }
          route { gtfsId shortName longName color textColor }
          legGeometry { points }
        }
      }
    }
  }
}
"""

# Street-only searches: no transit at all.
STREET_ONLY_MODES = {"walk": "WALK", "bicycle": "BICYCLE"}


def normalize(name: str) -> str:
    """Lower case, no accents, punctuation replaced by spaces."""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def load_stops(gtfs_zip: Path) -> list[dict]:
    with zipfile.ZipFile(gtfs_zip) as archive:
        with archive.open("stops.txt") as raw:
            rows = list(csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig")))
    stops = []
    for row in rows:
        try:
            stops.append({
                "id": row["stop_id"],
                "name": row.get("stop_name", ""),
                "key": normalize(row.get("stop_name", "")),
                "lat": float(row["stop_lat"]),
                "lon": float(row["stop_lon"]),
            })
        except (KeyError, ValueError):
            continue
    return stops


def resolve_place(candidates: list[dict], gtfs_dir: Path, cache: dict) -> dict | None:
    """First candidate (feed + name pattern) matching at least one stop wins."""
    for candidate in candidates:
        feed = candidate["feed"]
        path = gtfs_dir / f"{feed}.gtfs.zip"
        if feed not in cache:
            cache[feed] = load_stops(path) if path.exists() else []
        pattern = re.compile(candidate["pattern"])
        matches = [s for s in cache[feed] if pattern.search(s["key"])]
        if matches:
            return {
                "lat": round(sum(s["lat"] for s in matches) / len(matches), 6),
                "lon": round(sum(s["lon"] for s in matches) / len(matches), 6),
                "feed": feed,
                "pattern": candidate["pattern"],
                "matched_stops": len(matches),
                "matched_names": sorted({s["name"] for s in matches})[:3],
            }
    return None


def next_departure(config: dict, now: dt.datetime | None = None) -> dt.datetime:
    """Next given weekday at the given local time, strictly in the future."""
    tz = ZoneInfo(config["timezone"])
    now = now.astimezone(tz) if now else dt.datetime.now(tz)
    hour, minute = (int(v) for v in config["time"].split(":"))
    for offset in range(0, 8):
        day = now.date() + dt.timedelta(days=offset)
        candidate = dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
        if day.weekday() == WEEKDAYS.index(config["weekday"]) and candidate > now:
            return candidate
    raise ValueError("cannot compute departure date")


def graphql(url: str, query: str, variables: dict | None = None, timeout: int = 60) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    request = urllib.request.Request(f"{url}/otp/gtfs/v1", data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def public_request(request: dict) -> dict:
    """The request settings without the explanation keys (starting with _)."""
    return {key: value for key, value in request.items() if not key.startswith("_")}


def build_modes(mode: str, request: dict) -> dict:
    """`modes` argument of planConnection. Never null: OTP 2.10.0 crashes on modes: null."""
    if mode in STREET_ONLY_MODES:
        return {"directOnly": True, "direct": [STREET_ONLY_MODES[mode]]}
    if mode == "transit":
        return {
            "direct": list(request["direct"]),
            "transit": {
                "access": list(request["access"]),
                "egress": list(request["egress"]),
                "transfer": list(request["transfer"]),
                "transit": [{"mode": m} for m in request["transit_modes"]],
            },
        }
    raise ValueError(f"unknown trip mode: {mode}")


def build_variables(label: str, origin: dict, destination: dict, departure: dt.datetime,
                    mode: str, filters: list, request: dict) -> dict:
    """GraphQL variables for one planConnection request, without any null value."""
    names = label.split(" → ")
    variables = {
        "origin": {"label": names[0],
                   "location": {"coordinate": {"latitude": origin["lat"], "longitude": origin["lon"]}}},
        "destination": {"label": names[-1],
                        "location": {"coordinate": {"latitude": destination["lat"],
                                                    "longitude": destination["lon"]}}},
        "dateTime": {"earliestDeparture": departure.isoformat()},
        "modes": build_modes(mode, request),
    }
    if filters:
        variables["preferences"] = {"transit": {"filters": filters}}
    return variables


def scenario_filters(scenario: dict, agencies_by_feed: dict[str, list[str]]) -> tuple[list, list[str]]:
    """Build the planConnection `filters` value for a scenario."""
    excluded_agencies = [a for feed in scenario.get("exclude_feeds", []) for a in agencies_by_feed.get(feed, [])]
    selectors = []
    if excluded_agencies:
        selectors.append({"agencies": excluded_agencies})
    if scenario.get("exclude_routes"):
        selectors.append({"routes": list(scenario["exclude_routes"])})
    return ([{"exclude": selectors}] if selectors else []), excluded_agencies


def prepare_scenarios(scenarios: dict, agencies_by_feed: dict[str, list[str]], route_ids: set[str],
                      allowed_missing: set[str], scenario_files: dict[str, Path]) -> tuple[dict, list, list]:
    """Merge the scenario files, check the feeds, and resolve the filters.

    Returns (resolved scenarios, failures, warnings).
    """
    failures: list[str] = []
    warnings: list[str] = []
    resolved: dict = {}
    future_present = bool(agencies_by_feed.get(FUTURE_FEED))
    for name, scenario in scenarios.items():
        scenario = {key: value for key, value in scenario.items() if not key.startswith("_")}
        scenario["exclude_routes"] = list(scenario.get("exclude_routes", []))
        path = scenario_files.get(name)
        if path is not None:
            if not path.exists():
                warnings.append(f"scénario {name} : fichier {path} absent, aucune ligne remplacée")
            elif not future_present:
                warnings.append(f"scénario {name} : fichier {path} ignoré car le flux {FUTURE_FEED} est absent")
            else:
                extra = json.loads(path.read_text(encoding="utf-8")).get("exclude_routes", [])
                scenario["exclude_routes"] += [r for r in extra if r not in scenario["exclude_routes"]]
        for route in scenario["exclude_routes"]:
            if route not in route_ids:
                warnings.append(f"scénario {name} : la ligne {route} à exclure n'existe pas dans le graphe")
        for feed in scenario.get("exclude_feeds", []):
            if not agencies_by_feed.get(feed):
                if feed in allowed_missing:
                    warnings.append(f"scénario {name} : le flux {feed} est absent du graphe "
                                    "(toléré : les deux scénarios sont alors identiques)")
                else:
                    failures.append(f"scénario {name} : le flux {feed} est absent du graphe")
        filters, excluded_agencies = scenario_filters(scenario, agencies_by_feed)
        resolved[name] = {
            "label": scenario["label"],
            "excluded_agencies": excluded_agencies,
            "excluded_routes": scenario["exclude_routes"],
            "filters": filters,
        }
    return resolved, failures, warnings


def filters_document(request: dict, resolved: dict) -> dict:
    """Content of scenario-filters.json: what the front-end sends for each scenario."""
    return {
        "_explication": "Filtres à envoyer dans preferences.transit.filters de planConnection, "
                        "par scénario, et modes à envoyer pour un trajet en transports en commun.",
        "request": request,
        "scenarios": resolved,
    }


def demo_document(recorded_at: dt.datetime, requests: list[dict], filters: dict) -> dict:
    """Content of demo-responses.json (contract in the module docstring)."""
    return {
        "recorded_at": recorded_at.astimezone(dt.timezone.utc).isoformat(timespec="seconds"),
        "query": PLAN_QUERY,
        "requests": requests,
        "scenario_filters": filters,
    }


def write_json(path: Path, content: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")


def summarize(node: dict) -> dict:
    legs = []
    for leg in node["legs"]:
        route = leg.get("route") or {}
        agency = (leg.get("agency") or {}).get("gtfsId") or ""
        legs.append({
            "mode": leg["mode"],
            "line": route.get("shortName"),
            "route": route.get("gtfsId"),
            "feed": agency.split(":", 1)[0] if agency else None,
            "from": leg["from"]["name"],
            "to": leg["to"]["name"],
            "minutes": round((leg.get("duration") or 0) / 60),
        })
    return {
        "start": node["start"],
        "end": node["end"],
        "minutes": round(node["duration"] / 60),
        "transfers": node["numberOfTransfers"],
        "walk_meters": round(node.get("walkDistance") or 0),
        "legs": legs,
        "feeds": sorted({leg["feed"] for leg in legs if leg["feed"]}),
    }


def evaluate_checks(trip: dict, results: dict, feeds_present: set[str] | None = None) -> tuple[list[str], list[str]]:
    """Per-trip checks from config/reference-trips.json: (failures, warnings).

    A check with "requires_feed" is skipped, with a warning, when that feed is not in the graph
    (feeds_present; None = all present): without the future feed, scenario 2028 is today's network.
    """
    failures: list[str] = []
    warnings: list[str] = []
    for check in trip.get("checks", []):
        scenario = check["scenario"]
        required = check.get("requires_feed")
        if required and feeds_present is not None and required not in feeds_present:
            warnings.append(f"{trip['id']} / {scenario} : contrôle ignoré, le flux {required} est absent du graphe")
            continue
        itineraries = (results.get(scenario) or {}).get("itineraries") or []
        problem = None
        if "fastest_uses" in check:
            wanted = check["fastest_uses"]
            if not itineraries:
                problem = f"aucun itinéraire, impossible de vérifier la ligne {wanted['line']}"
            else:
                fastest = min(itineraries, key=lambda i: i["minutes"])
                uses = any(leg["feed"] == wanted["feed"] and leg["line"] == wanted["line"] for leg in fastest["legs"])
                if not uses:
                    problem = f"le trajet le plus rapide n'emprunte pas la ligne {wanted['line']} ({wanted['feed']})"
        if "never_uses_feed" in check:
            feed = check["never_uses_feed"]
            if any(feed in itinerary["feeds"] for itinerary in itineraries):
                problem = f"un itinéraire emprunte le flux {feed}"
        if "never_uses_line" in check:
            unwanted = check["never_uses_line"]
            if any(leg["feed"] == unwanted["feed"] and leg["line"] == unwanted["line"]
                   for itinerary in itineraries for leg in itinerary["legs"]):
                problem = f"un itinéraire emprunte la ligne {unwanted['line']} ({unwanted['feed']})"
        if "uses_stop" in check:
            wanted = check["uses_stop"]
            pattern = re.compile(wanted["pattern"])
            if not any(leg["feed"] == wanted["feed"] and any(pattern.search(normalize(leg[end] or ""))
                                                             for end in ("from", "to"))
                       for itinerary in itineraries for leg in itinerary["legs"]):
                problem = f"aucun itinéraire ne monte ni ne descend à l'arrêt « {wanted['pattern']} » ({wanted['feed']})"
        if problem:
            message = f"{trip['id']} / {scenario} : {problem}"
            (failures if check.get("severity") == "failure" else warnings).append(message)
    return failures, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--otp-url", default="http://127.0.0.1:8080")
    parser.add_argument("--gtfs-dir", type=Path, required=True)
    parser.add_argument("--trips", type=Path, required=True)
    parser.add_argument("--scenarios", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-missing-feed", action="append", default=[], metavar="FEED")
    parser.add_argument("--scenario-file", action="append", default=[], metavar="SCENARIO=PATH")
    parser.add_argument("--filters-output", type=Path)
    parser.add_argument("--raw-output", type=Path, metavar="FILE",
                        help="raw GraphQL answers of the transit trips (demo-responses.json)")
    args = parser.parse_args()
    recorded_at = dt.datetime.now(dt.timezone.utc)

    trips_config = json.loads(args.trips.read_text(encoding="utf-8"))
    scenarios_config = json.loads(args.scenarios.read_text(encoding="utf-8"))
    request = public_request(scenarios_config["request"])
    scenario_files = {}
    for item in args.scenario_file:
        name, _, path = item.partition("=")
        scenario_files[name] = Path(path)
    departure = next_departure(trips_config["departure"])

    feeds = graphql(args.otp_url, FEEDS_QUERY)["data"]["feeds"]
    agencies_by_feed = {f["feedId"]: [a["gtfsId"] for a in f.get("agencies") or []] for f in feeds}
    routes = graphql(args.otp_url, ROUTES_QUERY)["data"]["routes"]
    route_ids = {r["gtfsId"] for r in routes}
    modes_in_graph = sorted({r["mode"] for r in routes if r.get("mode")})

    resolved, failures, warnings = prepare_scenarios(
        scenarios_config["scenarios"], agencies_by_feed, route_ids, set(args.allow_missing_feed), scenario_files)
    missing_modes = [m for m in modes_in_graph if m not in request["transit_modes"]]
    if missing_modes:
        warnings.append(f"modes présents dans le graphe mais absents de request.transit_modes : {missing_modes}")

    output: dict = {
        "departure": departure.isoformat(),
        "feeds": {feed: len(agencies) for feed, agencies in agencies_by_feed.items()},
        "modes_in_graph": modes_in_graph,
        "request": request,
        "scenarios": resolved,
        "trips": [],
        "failures": failures,
        "warnings": warnings,
    }

    stop_cache: dict = {}
    raw_requests: list[dict] = []
    for trip in trips_config["trips"]:
        result = {"id": trip["id"], "label": trip["label"], "mode": trip["mode"], "results": {}}
        origin = resolve_place(trip["from"], args.gtfs_dir, stop_cache)
        destination = resolve_place(trip["to"], args.gtfs_dir, stop_cache)
        result["from"], result["to"] = origin, destination
        if not origin or not destination:
            failures.append(f"{trip['id']} : arrêt de départ ou d'arrivée introuvable")
            output["trips"].append(result)
            continue

        for scenario_name in trip["scenarios"]:
            variables = build_variables(trip["label"], origin, destination, departure, trip["mode"],
                                        resolved[scenario_name]["filters"], request)
            started = time.monotonic()
            try:
                response = graphql(args.otp_url, PLAN_QUERY, variables)
            except (urllib.error.URLError, TimeoutError) as error:
                response = {"errors": [{"message": str(error)}]}
            elapsed_ms = round((time.monotonic() - started) * 1000)
            if trip["mode"] == "transit":
                raw_requests.append({"id": trip["id"], "label": trip["label"], "scenario": scenario_name,
                                     "variables": variables, "response": response})

            entry: dict = {"response_ms": elapsed_ms}
            if response.get("errors"):
                entry["errors"] = [e.get("message") for e in response["errors"]]
                failures.append(f"{trip['id']} / {scenario_name} : erreur GraphQL")
            plan = (response.get("data") or {}).get("planConnection") or {}
            entry["routing_errors"] = plan.get("routingErrors") or []
            entry["itineraries"] = [summarize(edge["node"]) for edge in plan.get("edges") or []]
            result["results"][scenario_name] = entry

            excluded_feeds = set(scenarios_config["scenarios"][scenario_name].get("exclude_feeds", []))
            itineraries = entry["itineraries"]
            if not itineraries:
                failures.append(f"{trip['id']} / {scenario_name} : aucun itinéraire")
            for itinerary in itineraries:
                if excluded_feeds & set(itinerary["feeds"]):
                    failures.append(f"{trip['id']} / {scenario_name} : utilise un flux exclu {sorted(excluded_feeds)}")
            if trip["mode"] in STREET_ONLY_MODES and itineraries:
                # Street-only itinerary: no transit leg, at least one leg in the expected mode.
                expected = STREET_ONLY_MODES[trip["mode"]]
                if not any(all(leg["feed"] is None for leg in i["legs"])
                           and any(leg["mode"] == expected for leg in i["legs"]) for i in itineraries):
                    failures.append(f"{trip['id']} : pas d'itinéraire en {trip['mode']} seul")
        check_failures, check_warnings = evaluate_checks(
            trip, result["results"], {feed for feed, agencies in agencies_by_feed.items() if agencies})
        failures += check_failures
        warnings += check_warnings
        output["trips"].append(result)

    output["success"] = not failures
    write_json(args.output, output)
    filters = filters_document(request, resolved)
    if args.filters_output:
        write_json(args.filters_output, filters)
    if args.raw_output:
        write_json(args.raw_output, demo_document(recorded_at, raw_requests, filters))
    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    print(f"{len(output['trips'])} reference trips computed, {len(failures)} failure(s), {len(warnings)} warning(s)")
    return 0 if output["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
