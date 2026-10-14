#!/usr/bin/env python3
"""Keep only the part of the national SNCF GTFS that serves the routing zone.

Usage:
    python scripts/filter_gtfs_sncf.py --input build/raw/sncf-national.gtfs.zip \
        --zone build/zone.json --output build/otp/gtfs/sncf.gtfs.zip \
        --report build/report/sncf-filter.json

Rules (simple on purpose):
1. A "zone stop" is a stop (location_type empty or 0) inside the zone bbox.
2. A trip is kept when it calls at least --min-stops zone stops (default 2):
   a train that only touches one station of the zone is useless for trips
   inside the agglomeration.
3. Kept trips are cut to their zone stops: stops outside the zone are removed,
   times of the remaining stops are unchanged.
4. Every other file is filtered by its key columns (trip_id, route_id,
   service_id, stop_id, shape_id, agency_id...) so that no reference is left
   dangling. Files without key columns (feed_info.txt...) are copied as-is.

Only the Python standard library is used; files are streamed row by row.
"""

from __future__ import annotations

import argparse
import collections
import csv
import io
import json
import sys
import zipfile
from pathlib import Path

# Column name -> name of the set of kept identifiers it must belong to.
KEY_COLUMNS = {
    "trip_id": "trips",
    "from_trip_id": "trips",
    "to_trip_id": "trips",
    "route_id": "routes",
    "from_route_id": "routes",
    "to_route_id": "routes",
    "service_id": "services",
    "stop_id": "stops",
    "from_stop_id": "stops",
    "to_stop_id": "stops",
    "shape_id": "shapes",
    "agency_id": "agencies",
}


def open_csv(archive: zipfile.ZipFile, name: str) -> csv.DictReader:
    raw = archive.open(name)
    return csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))


def open_output(out: zipfile.ZipFile, name: str) -> io.TextIOWrapper:
    """Open a text stream that writes one CSV file directly into the output zip."""
    return io.TextIOWrapper(out.open(name, "w"), encoding="utf-8", newline="")


def in_bbox(lon: float, lat: float, bbox: list[float]) -> bool:
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def filter_feed(input_zip: Path, bbox: list[float], output_zip: Path, min_stops: int) -> dict:
    report: dict = {"bbox": bbox, "min_stops": min_stops, "files": {}}
    with zipfile.ZipFile(input_zip) as archive:
        names = {Path(n).name: n for n in archive.namelist() if n.endswith(".txt")}
        for required in ("stops.txt", "stop_times.txt", "trips.txt", "routes.txt"):
            if required not in names:
                raise ValueError(f"{required} missing from {input_zip}")

        # 1. Zone stops and parent relations.
        parent_of: dict[str, str] = {}
        zone_stops: set[str] = set()
        for row in open_csv(archive, names["stops.txt"]):
            stop_id = row["stop_id"]
            if row.get("parent_station"):
                parent_of[stop_id] = row["parent_station"]
            if row.get("location_type", "") not in ("", "0"):
                continue
            try:
                lon, lat = float(row["stop_lon"]), float(row["stop_lat"])
            except (KeyError, ValueError):
                continue
            if in_bbox(lon, lat, bbox):
                zone_stops.add(stop_id)
        report["zone_stops"] = len(zone_stops)

        # 2. First pass on stop_times: count zone calls per trip.
        calls_in_zone: collections.Counter[str] = collections.Counter()
        for row in open_csv(archive, names["stop_times.txt"]):
            if row["stop_id"] in zone_stops:
                calls_in_zone[row["trip_id"]] += 1
        kept: dict[str, set[str]] = {
            "trips": {trip for trip, count in calls_in_zone.items() if count >= min_stops},
            "routes": set(),
            "services": set(),
            "shapes": set(),
            "stops": set(),
            "agencies": set(),
        }

        # 3. Routes, services and shapes used by the kept trips.
        for row in open_csv(archive, names["trips.txt"]):
            if row["trip_id"] in kept["trips"]:
                kept["routes"].add(row["route_id"])
                kept["services"].add(row["service_id"])
                if row.get("shape_id"):
                    kept["shapes"].add(row["shape_id"])

        filter_agencies = False
        route_types: collections.Counter[str] = collections.Counter()
        for row in open_csv(archive, names["routes.txt"]):
            if row["route_id"] in kept["routes"]:
                route_types[row.get("route_type", "?")] += 1
                if row.get("agency_id"):
                    kept["agencies"].add(row["agency_id"])
                    filter_agencies = True

        output_zip.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as out:
            # 4. Second pass on stop_times: keep zone calls of kept trips only.
            missing_times = 0
            rows_in = rows_out = 0
            reader = open_csv(archive, names["stop_times.txt"])
            with open_output(out, "stop_times.txt") as text:
                writer = csv.DictWriter(text, fieldnames=reader.fieldnames, lineterminator="\n")
                writer.writeheader()
                for row in reader:
                    rows_in += 1
                    if row["trip_id"] in kept["trips"] and row["stop_id"] in zone_stops:
                        writer.writerow(row)
                        rows_out += 1
                        kept["stops"].add(row["stop_id"])
                        if not row.get("arrival_time") or not row.get("departure_time"):
                            missing_times += 1
            report["files"]["stop_times.txt"] = {"rows_in": rows_in, "rows_out": rows_out}
            report["stop_times_without_time"] = missing_times

            # Parent stations of kept stops (walk up the hierarchy).
            for stop_id in list(kept["stops"]):
                parent = parent_of.get(stop_id)
                while parent and parent not in kept["stops"]:
                    kept["stops"].add(parent)
                    parent = parent_of.get(parent)

            active = dict(kept)
            if not filter_agencies:
                active.pop("agencies")

            # 5. Every other file, filtered by its key columns.
            for name, member in sorted(names.items()):
                if name == "stop_times.txt":
                    continue
                reader = open_csv(archive, member)
                fieldnames = reader.fieldnames or []
                checks = [
                    (column, active[KEY_COLUMNS[column]])
                    for column in fieldnames
                    if column in KEY_COLUMNS and KEY_COLUMNS[column] in active
                ]
                rows_in = rows_out = 0
                with open_output(out, name) as text:
                    writer = csv.DictWriter(text, fieldnames=fieldnames, lineterminator="\n")
                    writer.writeheader()
                    for row in reader:
                        rows_in += 1
                        if all(not row.get(column) or row[column] in allowed for column, allowed in checks):
                            writer.writerow(row)
                            rows_out += 1
                report["files"][name] = {"rows_in": rows_in, "rows_out": rows_out}

    report["kept"] = {key: len(value) for key, value in kept.items()}
    report["route_types"] = dict(route_types)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--zone", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--min-stops", type=int, default=2)
    args = parser.parse_args()

    bbox = json.loads(args.zone.read_text(encoding="utf-8"))["bbox"]
    try:
        report = filter_feed(args.input, bbox, args.output, args.min_stops)
    except (ValueError, KeyError, zipfile.BadZipFile) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"SNCF filtered: {report['kept']['trips']} trips, {report['kept']['stops']} stops, "
        f"{report['kept']['routes']} routes kept"
    )
    if report["kept"]["trips"] == 0:
        print("ERROR: no SNCF trip serves the zone, check the bbox", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
