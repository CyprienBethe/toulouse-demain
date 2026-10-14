"""Independent structural checks of a GTFS feed (GTFS Schedule reference, required parts).

Written separately from build_gtfs_futur.py so that a bug in the builder is not hidden by the
same bug in the checker.
"""

from __future__ import annotations

import re

REQUIRED = {
    "agency.txt": ["agency_name", "agency_url", "agency_timezone"],
    "stops.txt": ["stop_id", "stop_name", "stop_lat", "stop_lon"],
    "routes.txt": ["route_id", "route_type"],
    "trips.txt": ["route_id", "service_id", "trip_id"],
    "stop_times.txt": ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
    "calendar.txt": ["service_id", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
                     "start_date", "end_date"],
    "feed_info.txt": ["feed_publisher_name", "feed_publisher_url", "feed_lang"],
}
TIME = re.compile(r"^\d{2,}:[0-5]\d:[0-5]\d$")
DATE = re.compile(r"^\d{8}$")
COLOR = re.compile(r"^([0-9A-Fa-f]{6})?$")


def seconds(value: str) -> int:
    h, m, s = (int(x) for x in value.split(":"))
    return h * 3600 + m * 60 + s


def check_feed(tables: dict[str, list[dict]], prefix: str = "FUT_") -> list[str]:
    """Return a list of problems (empty = feed passes)."""
    errors: list[str] = []
    for name, columns in REQUIRED.items():
        if name not in tables or not tables[name]:
            errors.append(f"{name} absent ou vide")
            continue
        for col in columns:
            if col not in tables[name][0]:
                errors.append(f"{name} : colonne obligatoire {col} absente")
    if errors:
        return errors

    def unique(table, key):
        values = [r[key] for r in tables[table]]
        if len(values) != len(set(values)):
            errors.append(f"{table} : {key} en double")
        for v in values:
            if not v.startswith(prefix):
                errors.append(f"{table} : identifiant {v} sans le préfixe {prefix}")
                break
        return set(values)

    agencies = unique("agency.txt", "agency_id")
    stops = unique("stops.txt", "stop_id")
    routes = unique("routes.txt", "route_id")
    trips = unique("trips.txt", "trip_id")
    services = unique("calendar.txt", "service_id")
    services |= {d["service_id"] for d in tables.get("calendar_dates.txt", []) if d["exception_type"] == "1"}
    stop_rows = {s["stop_id"]: s for s in tables["stops.txt"]}

    for s in tables["stops.txt"]:
        lat, lon = float(s["stop_lat"]), float(s["stop_lon"])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            errors.append(f"stops.txt : coordonnées invalides {s['stop_id']}")
        parent = s.get("parent_station", "")
        if parent:
            if parent not in stops or stop_rows[parent].get("location_type") != "1":
                errors.append(f"stops.txt : parent_station invalide pour {s['stop_id']}")
    for r in tables["routes.txt"]:
        if r.get("agency_id") and r["agency_id"] not in agencies:
            errors.append(f"routes.txt : agency_id inconnu {r['agency_id']}")
        if not (r.get("route_short_name") or r.get("route_long_name")):
            errors.append(f"routes.txt : {r['route_id']} sans nom")
        if not COLOR.match(r.get("route_color", "")) or not COLOR.match(r.get("route_text_color", "")):
            errors.append(f"routes.txt : couleur invalide pour {r['route_id']}")
    shapes = {r["shape_id"] for r in tables.get("shapes.txt", [])}
    for t in tables["trips.txt"]:
        if t["route_id"] not in routes:
            errors.append(f"trips.txt : route_id inconnu {t['route_id']}")
        if t["service_id"] not in services:
            errors.append(f"trips.txt : service_id inconnu {t['service_id']}")
        if t.get("shape_id") and t["shape_id"] not in shapes:
            errors.append(f"trips.txt : shape_id inconnu {t['shape_id']}")
    for c in tables["calendar.txt"]:
        if not (DATE.match(c["start_date"]) and DATE.match(c["end_date"])) or c["start_date"] > c["end_date"]:
            errors.append(f"calendar.txt : dates invalides pour {c['service_id']}")
    for d in tables.get("calendar_dates.txt", []):
        if d["service_id"] not in services or d["exception_type"] not in ("1", "2") or not DATE.match(d["date"]):
            errors.append(f"calendar_dates.txt : ligne invalide {d}")

    by_trip: dict[str, list[dict]] = {}
    for st in tables["stop_times.txt"]:
        if st["trip_id"] not in trips:
            errors.append(f"stop_times.txt : trip_id inconnu {st['trip_id']}")
            break
        if st["stop_id"] not in stops or stop_rows[st["stop_id"]].get("location_type", "0") not in ("", "0"):
            errors.append(f"stop_times.txt : stop_id invalide {st['stop_id']}")
            break
        if not (TIME.match(st["arrival_time"]) and TIME.match(st["departure_time"])):
            errors.append(f"stop_times.txt : heure invalide {st}")
            break
        by_trip.setdefault(st["trip_id"], []).append(st)
    if set(by_trip) != trips:
        errors.append("trips.txt : certaines courses n'ont aucun horaire")
    for trip_id, rows in by_trip.items():
        rows.sort(key=lambda r: int(r["stop_sequence"]))
        if len(rows) < 2:
            errors.append(f"{trip_id} : moins de deux arrêts")
        prev_dep, prev_dist = None, -1.0
        for r in rows:
            arr, dep = seconds(r["arrival_time"]), seconds(r["departure_time"])
            if dep < arr or (prev_dep is not None and arr <= prev_dep):
                errors.append(f"{trip_id} : horaires non croissants")
                break
            dist = float(r.get("shape_dist_traveled") or 0)
            if dist < prev_dist:
                errors.append(f"{trip_id} : shape_dist_traveled décroissant")
                break
            prev_dep, prev_dist = dep, dist
    shape_pts: dict[str, list[dict]] = {}
    for p in tables.get("shapes.txt", []):
        shape_pts.setdefault(p["shape_id"], []).append(p)
    for sid, pts in shape_pts.items():
        pts.sort(key=lambda p: int(p["shape_pt_sequence"]))
        dists = [float(p["shape_dist_traveled"]) for p in pts]
        if dists != sorted(dists) or len(pts) < 2:
            errors.append(f"shapes.txt : forme {sid} incohérente")
    for tr in tables.get("transfers.txt", []):
        if tr["from_stop_id"] not in stops or tr["to_stop_id"] not in stops:
            errors.append(f"transfers.txt : arrêt inconnu {tr}")
        if tr["transfer_type"] == "2" and not tr.get("min_transfer_time"):
            errors.append("transfers.txt : min_transfer_time manquant")
    for a in tables.get("attributions.txt", []):
        if "1" not in (a.get("is_producer"), a.get("is_operator"), a.get("is_authority")):
            errors.append(f"attributions.txt : rôle manquant pour {a['organization_name']}")
    return errors
