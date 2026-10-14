#!/usr/bin/env python3
"""Compute the routing zone from the stops of the Tisséo GTFS.

Usage:
    python scripts/compute_zone.py --gtfs build/raw/tisseo.gtfs.zip \
        --config config/zone.json --output build/zone.json

The zone is the bounding box of every Tisséo stop, enlarged by `buffer_km`
on each side. No coordinate is typed by hand: they all come from stops.txt.
The same box is used to clip OpenStreetMap and to filter the SNCF GTFS.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
import zipfile
from pathlib import Path

# Length of one degree of latitude, in km (mean value on the WGS84 ellipsoid).
KM_PER_DEGREE_LAT = 111.32


def read_stop_coordinates(gtfs_zip: Path) -> list[tuple[float, float]]:
    """Return (lon, lat) for every stop of the feed with usable coordinates."""
    coordinates = []
    with zipfile.ZipFile(gtfs_zip) as archive:
        with archive.open("stops.txt") as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig"))
            for row in reader:
                try:
                    lat = float(row.get("stop_lat") or "nan")
                    lon = float(row.get("stop_lon") or "nan")
                except ValueError:
                    continue
                # Skip empty or (0, 0) coordinates, which are data errors.
                if math.isnan(lat) or math.isnan(lon) or (lat == 0 and lon == 0):
                    continue
                coordinates.append((lon, lat))
    return coordinates


def compute_zone(coordinates: list[tuple[float, float]], buffer_km: float, max_span_km: float) -> dict:
    if not coordinates:
        raise ValueError("no stop with valid coordinates in stops.txt")
    lons = [c[0] for c in coordinates]
    lats = [c[1] for c in coordinates]
    min_lon, max_lon, min_lat, max_lat = min(lons), max(lons), min(lats), max(lats)

    mid_lat = (min_lat + max_lat) / 2
    km_per_degree_lon = KM_PER_DEGREE_LAT * math.cos(math.radians(mid_lat))
    span_km = max((max_lat - min_lat) * KM_PER_DEGREE_LAT, (max_lon - min_lon) * km_per_degree_lon)
    if span_km > max_span_km:
        raise ValueError(
            f"stops span {span_km:.0f} km, more than max_span_km={max_span_km}: "
            "a stop is probably misplaced, check stops.txt"
        )

    d_lat = buffer_km / KM_PER_DEGREE_LAT
    d_lon = buffer_km / km_per_degree_lon
    bbox = [
        round(min_lon - d_lon, 5),
        round(min_lat - d_lat, 5),
        round(max_lon + d_lon, 5),
        round(max_lat + d_lat, 5),
    ]
    return {
        "bbox": bbox,
        "bbox_format": "min_lon,min_lat,max_lon,max_lat (WGS84)",
        "stops_bbox": [min_lon, min_lat, max_lon, max_lat],
        "stop_count": len(coordinates),
        "buffer_km": buffer_km,
        "stops_span_km": round(span_km, 1),
        "source": "stops.txt du GTFS Tisséo",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gtfs", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    try:
        zone = compute_zone(
            read_stop_coordinates(args.gtfs),
            buffer_km=float(config["buffer_km"]),
            max_span_km=float(config["max_span_km"]),
        )
    except (ValueError, KeyError, zipfile.BadZipFile) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(zone, indent=2), encoding="utf-8")
    print(f"Zone bbox: {','.join(str(v) for v in zone['bbox'])} ({zone['stop_count']} stops)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
