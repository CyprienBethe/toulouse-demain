#!/usr/bin/env python3
"""Compute the reference trips in each scenario against a running OTP server.

Usage:
    python scripts/reference_trips.py --otp-url http://127.0.0.1:8080 \
        --gtfs-dir build/otp/gtfs --trips config/reference-trips.json \
        --scenarios config/scenarios.json --output build/report/trips.json

How a scenario works: the graph contains the three feeds (tisseo, sncf,
futur). For each request, the agencies of the feeds listed in
`exclude_feeds` (and the routes in `exclude_routes`) are excluded with the
`preferences.transit.filters` argument of the `planConnection` query of the
OTP GTFS GraphQL API. The front-end must send exactly the same filters.

Checks that make the script fail (exit code 1):
- a reference trip returns no itinerary;
- an itinerary of a scenario uses a feed that the scenario excludes;
- a walk (or bicycle) trip does not return a walk-only (or bicycle) itinerary.
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

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

FEEDS_QUERY = "{ feeds { feedId agencies { gtfsId name } } }"

PLAN_QUERY = """
query Plan($origin: PlanLabeledLocationInput!, $destination: PlanLabeledLocationInput!,
           $dateTime: PlanDateTimeInput!, $modes: PlanModesInput, $preferences: PlanPreferencesInput) {
  planConnection(origin: $origin, destination: $destination, dateTime: $dateTime,
                 modes: $modes, preferences: $preferences, first: 3) {
    routingErrors { code description }
    edges {
      node {
        start
        end
        duration
        numberOfTransfers
        walkDistance
        legs {
          mode
          duration
          distance
          from { name }
          to { name }
          agency { gtfsId }
          route { gtfsId shortName }
        }
      }
    }
  }
}
"""

# Street-only searches: no transit at all.
DIRECT_MODES = {
    "walk": {"directOnly": True, "direct": ["WALK"]},
    "bicycle": {"directOnly": True, "direct": ["BICYCLE"]},
}


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


def next_departure(config: dict, today: dt.date | None = None) -> dt.datetime:
    """Next given weekday at the given local time, strictly in the future."""
    tz = ZoneInfo(config["timezone"])
    now = dt.datetime.now(tz)
    hour, minute = (int(v) for v in config["time"].split(":"))
    day = today or now.date()
    for offset in range(0, 8):
        candidate_day = day + dt.timedelta(days=offset)
        candidate = dt.datetime(candidate_day.year, candidate_day.month, candidate_day.day,
                                hour, minute, tzinfo=tz)
        if candidate_day.weekday() == WEEKDAYS.index(config["weekday"]) and candidate > now:
            return candidate
    raise ValueError("cannot compute departure date")


def graphql(url: str, query: str, variables: dict | None = None, timeout: int = 60) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    request = urllib.request.Request(f"{url}/otp/gtfs/v1", data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def scenario_filters(scenario: dict, agencies_by_feed: dict[str, list[str]]) -> tuple[list, list[str]]:
    """Build the planConnection `filters` value for a scenario."""
    excluded_agencies = [a for feed in scenario.get("exclude_feeds", []) for a in agencies_by_feed.get(feed, [])]
    selectors = []
    if excluded_agencies:
        selectors.append({"agencies": excluded_agencies})
    if scenario.get("exclude_routes"):
        selectors.append({"routes": scenario["exclude_routes"]})
    return ([{"exclude": selectors}] if selectors else []), excluded_agencies


def summarize(node: dict) -> dict:
    legs = []
    for leg in node["legs"]:
        route = leg.get("route") or {}
        agency = (leg.get("agency") or {}).get("gtfsId") or ""
        legs.append({
            "mode": leg["mode"],
            "line": route.get("shortName"),
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--otp-url", default="http://127.0.0.1:8080")
    parser.add_argument("--gtfs-dir", type=Path, required=True)
    parser.add_argument("--trips", type=Path, required=True)
    parser.add_argument("--scenarios", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    trips_config = json.loads(args.trips.read_text(encoding="utf-8"))
    scenarios = json.loads(args.scenarios.read_text(encoding="utf-8"))["scenarios"]
    departure = next_departure(trips_config["departure"])

    feeds = graphql(args.otp_url, FEEDS_QUERY)["data"]["feeds"]
    agencies_by_feed = {f["feedId"]: [a["gtfsId"] for a in f.get("agencies") or []] for f in feeds}

    output: dict = {
        "departure": departure.isoformat(),
        "feeds": {feed: len(agencies) for feed, agencies in agencies_by_feed.items()},
        "scenarios": {},
        "trips": [],
        "failures": [],
    }
    filters_by_scenario = {}
    for name, scenario in scenarios.items():
        filters, excluded = scenario_filters(scenario, agencies_by_feed)
        filters_by_scenario[name] = filters
        output["scenarios"][name] = {"label": scenario["label"], "excluded_agencies": excluded,
                                     "filters": filters}
        for feed in scenario.get("exclude_feeds", []):
            if not agencies_by_feed.get(feed):
                output["failures"].append(f"scénario {name} : le flux {feed} est absent du graphe")

    stop_cache: dict = {}
    for trip in trips_config["trips"]:
        result = {"id": trip["id"], "label": trip["label"], "mode": trip["mode"], "results": {}}
        origin = resolve_place(trip["from"], args.gtfs_dir, stop_cache)
        destination = resolve_place(trip["to"], args.gtfs_dir, stop_cache)
        result["from"], result["to"] = origin, destination
        if not origin or not destination:
            output["failures"].append(f"{trip['id']} : arrêt de départ ou d'arrivée introuvable")
            output["trips"].append(result)
            continue

        for scenario_name in trip["scenarios"]:
            variables = {
                "origin": {"label": trip["label"].split(" → ")[0],
                           "location": {"coordinate": {"latitude": origin["lat"], "longitude": origin["lon"]}}},
                "destination": {"label": trip["label"].split(" → ")[-1],
                                "location": {"coordinate": {"latitude": destination["lat"],
                                                            "longitude": destination["lon"]}}},
                "dateTime": {"earliestDeparture": departure.isoformat()},
                "modes": DIRECT_MODES.get(trip["mode"]),
                "preferences": ({"transit": {"filters": filters_by_scenario[scenario_name]}}
                                if filters_by_scenario[scenario_name] else None),
            }
            started = time.monotonic()
            try:
                response = graphql(args.otp_url, PLAN_QUERY, variables)
            except (urllib.error.URLError, TimeoutError) as error:
                response = {"errors": [{"message": str(error)}]}
            elapsed_ms = round((time.monotonic() - started) * 1000)

            entry: dict = {"response_ms": elapsed_ms}
            if response.get("errors"):
                entry["errors"] = [e.get("message") for e in response["errors"]]
                output["failures"].append(f"{trip['id']} / {scenario_name} : erreur GraphQL")
            plan = (response.get("data") or {}).get("planConnection") or {}
            entry["routing_errors"] = plan.get("routingErrors") or []
            entry["itineraries"] = [summarize(edge["node"]) for edge in plan.get("edges") or []]
            result["results"][scenario_name] = entry

            excluded_feeds = set(scenarios[scenario_name].get("exclude_feeds", []))
            itineraries = entry["itineraries"]
            if not itineraries:
                output["failures"].append(f"{trip['id']} / {scenario_name} : aucun itinéraire")
            for itinerary in itineraries:
                if excluded_feeds & set(itinerary["feeds"]):
                    output["failures"].append(
                        f"{trip['id']} / {scenario_name} : utilise un flux exclu {sorted(excluded_feeds)}")
            if trip["mode"] in DIRECT_MODES and itineraries:
                # Street-only itinerary: no transit leg, at least one leg in the expected mode.
                expected = trip["mode"].upper()
                if not any(all(leg["feed"] is None for leg in i["legs"])
                           and any(leg["mode"] == expected for leg in i["legs"]) for i in itineraries):
                    output["failures"].append(f"{trip['id']} : pas d'itinéraire en {trip['mode']} seul")
        output["trips"].append(result)

    output["success"] = not output["failures"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    for failure in output["failures"]:
        print(f"FAIL: {failure}", file=sys.stderr)
    print(f"{len(output['trips'])} reference trips computed, {len(output['failures'])} failure(s)")
    return 0 if output["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
