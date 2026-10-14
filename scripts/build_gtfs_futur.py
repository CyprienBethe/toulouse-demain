#!/usr/bin/env python3
"""Build the "futur" GTFS feed (scenario "Réseau 2028") for Toulouse Demain.

Contract (fixed with the architect):

    python scripts/build_gtfs_futur.py --tisseo-gtfs <tisseo.zip> --output build/gtfs/futur.gtfs.zip

``--tisseo-gtfs`` is optional. The routing engine loads the output under the feed id ``futur``.

Inputs
    data/futur/stations_ligne_c.csv, data/futur/stations_ligne_b_prolongee.csv (stations, in order)
    data/futur/parametres.yaml (headways, service hours, travel times; see docs/hypotheses-reseau-2028.md)
    build/futur-osm/ (optional): positions and track produced by scripts/extract_futur_osm.py

Station positions, by priority: the CSV, then the OSM extraction, then the Tisséo stop named in
column ``arret_tisseo_reference``. A station without any position stops the build (exit code 2):
we never invent a coordinate.

With the Tisséo GTFS: service dates follow its calendar (public holidays run as Sundays), headway
ratios and service hours are measured on its metro line B, and a proximity report lists the
nearest existing stops. Without it: a standalone 21-day calendar and the default parameters.

Output: a GTFS zip (data derived under ODbL) and a Markdown report next to it.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import hashlib
import io
import json
import math
import statistics
import sys
import unicodedata
import zipfile
from collections import defaultdict
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PARAMS = REPO_ROOT / "data" / "futur" / "parametres.yaml"
DEFAULT_OSM_DIR = REPO_ROOT / "build" / "futur-osm"
DEFAULT_OUTPUT = REPO_ROOT / "build" / "gtfs" / "futur.gtfs.zip"

WEEKDAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
GTFS_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# Plausibility bounds for the distance between two consecutive stations (metres).
MIN_HOP_M = 300
MAX_HOP_M = 4000
# Departures before 04:00 belong to the previous night (some feeds code them 00:30, not 24:30).
NIGHT_CUT_S = 4 * 3600


class BuildError(Exception):
    """Blocking problem: the feed would be wrong, so we stop."""


# --------------------------------------------------------------------------- helpers


def normalize_name(name: str) -> str:
    """Lowercase, accents removed, letters and digits only: 'Marengo - SNCF' -> 'marengosncf'."""
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return "".join(c for c in text.lower() if c.isalnum())


def slug(name: str) -> str:
    """Identifier-friendly version of a name: 'Labège - Gare' -> 'LABEGE_GARE'."""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c))
    out, prev_sep = [], False
    for c in text.upper():
        if c.isalnum():
            out.append(c)
            prev_sep = False
        elif not prev_sep:
            out.append("_")
            prev_sep = True
    return "".join(out).strip("_")


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def polyline_length_m(points: list[tuple[float, float]]) -> float:
    return sum(haversine_m(*points[i], *points[i + 1]) for i in range(len(points) - 1))


def parse_hhmm(value: str) -> int:
    """'05:15' or '27:00' or '05:15:30' -> seconds since the start of the service day."""
    parts = [int(p) for p in str(value).strip().split(":")]
    while len(parts) < 3:
        parts.append(0)
    h, m, s = parts
    return h * 3600 + m * 60 + s


def fmt_time(seconds: int) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def fmt_minsec(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    return f"{m} min {s:02d}"


def gtfs_date(d: dt.date) -> str:
    return d.strftime("%Y%m%d")


def parse_gtfs_date(value: str) -> dt.date:
    return dt.datetime.strptime(value.strip(), "%Y%m%d").date()


def parse_anchor(value: str) -> tuple[str, bool] | None:
    """'Ramonville (même station)' -> ('Ramonville', True); 'La Vache (station voisine)' -> (.., False)."""
    value = (value or "").strip()
    if not value:
        return None
    same = False
    if value.endswith(")") and "(" in value:
        name, qualifier = value[:-1].rsplit("(", 1)
        same = normalize_name(qualifier) == normalize_name("même station")
        value = name.strip()
    return value, same


# --------------------------------------------------------------------------- inputs


@dataclasses.dataclass
class Station:
    line_id: str
    order: int
    name: str
    commune: str
    lat: float | None
    lon: float | None
    precision: str
    connections: str
    source: str
    anchor: tuple[str, bool] | None
    origin: str = ""  # where the position used in the feed comes from (filled at build time)


def load_params(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        params = yaml.safe_load(fh)
    for key in ("flux", "temps_arret_s", "lignes", "coefficients_intervalle", "profils", "services"):
        if key not in params:
            raise BuildError(f"{path}: clé « {key} » manquante")
    covered = set()
    for svc in params["services"]:
        if svc["profil"] not in params["profils"]:
            raise BuildError(f"service {svc['id']} : profil inconnu {svc['profil']}")
        for day in svc["jours"]:
            if day not in WEEKDAYS_FR:
                raise BuildError(f"service {svc['id']} : jour inconnu « {day} »")
            if day in covered:
                raise BuildError(f"le jour « {day} » appartient à deux services")
            covered.add(day)
    if covered != set(WEEKDAYS_FR):
        raise BuildError(f"jours sans service : {sorted(set(WEEKDAYS_FR) - covered)}")
    for profile, windows in params["profils"].items():
        for start, end, period in windows:
            if period not in params["coefficients_intervalle"]:
                raise BuildError(f"profil {profile} : période « {period} » sans coefficient")
            if parse_hhmm(start) >= parse_hhmm(end):
                raise BuildError(f"profil {profile} : fenêtre {start}-{end} vide")
    return params


def resolve_path(value: str, base: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def load_stations(csv_path: Path, line_id: str) -> list[Station]:
    stations = []
    with open(csv_path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            lat_txt, lon_txt = (row.get("lat") or "").strip(), (row.get("lon") or "").strip()
            if bool(lat_txt) != bool(lon_txt):
                raise BuildError(f"{csv_path.name} : lat et lon doivent être remplies ensemble ({row['nom_officiel']})")
            stations.append(
                Station(
                    line_id=line_id,
                    order=int(row["ordre"]),
                    name=row["nom_officiel"].strip(),
                    commune=row.get("commune", "").strip(),
                    lat=float(lat_txt) if lat_txt else None,
                    lon=float(lon_txt) if lon_txt else None,
                    precision=row.get("precision", "").strip(),
                    connections=row.get("correspondances", "").strip(),
                    source=row.get("source", "").strip(),
                    anchor=parse_anchor(row.get("arret_tisseo_reference", "")),
                )
            )
    stations.sort(key=lambda s: s.order)
    if [s.order for s in stations] != list(range(1, len(stations) + 1)):
        raise BuildError(f"{csv_path.name} : la colonne « ordre » doit aller de 1 à {len(stations)} sans trou")
    if len(stations) < 2:
        raise BuildError(f"{csv_path.name} : au moins deux stations sont nécessaires")
    return stations


def load_osm_outputs(osm_dir: Path | None):
    """Positions and hop tracks written by extract_futur_osm.py (both optional)."""
    positions, traces = {}, {}
    if not osm_dir:
        return positions, traces
    stations_csv = osm_dir / "stations_osm.csv"
    if stations_csv.exists():
        with open(stations_csv, encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("lat") and row.get("lon"):
                    positions[(row["ligne"], int(row["ordre"]))] = {
                        "lat": float(row["lat"]),
                        "lon": float(row["lon"]),
                        "precision": row.get("precision", ""),
                        "source": row.get("source", ""),
                    }
    traces_file = osm_dir / "traces_osm.geojson"
    if traces_file.exists():
        with open(traces_file, encoding="utf-8") as fh:
            data = json.load(fh)
        for feat in data.get("features", []):
            props = feat.get("properties", {})
            if props.get("methode") != "osm":
                continue
            coords = [(lat, lon) for lon, lat in feat["geometry"]["coordinates"]]
            traces[(props["ligne"], int(props["de_ordre"]), int(props["a_ordre"]))] = coords
    return positions, traces


# --------------------------------------------------------------------------- Tisséo GTFS


class TisseoGtfs:
    """Minimal streaming reader for the official Tisséo GTFS zip (only what we need)."""

    def __init__(self, path: Path):
        self.path = path
        self.zf = zipfile.ZipFile(path)
        self.names = {Path(n).name: n for n in self.zf.namelist()}

    def has(self, name: str) -> bool:
        return name in self.names

    def rows(self, name: str):
        if not self.has(name):
            return
        with self.zf.open(self.names[name]) as raw:
            yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))

    def load(self, ref_line: str) -> None:
        self.stops = list(self.rows("stops.txt"))
        self.routes = list(self.rows("routes.txt"))
        self.trips = list(self.rows("trips.txt"))
        self.ids = {
            "agency": {r.get("agency_id", "") for r in self.rows("agency.txt")},
            "stops": {s["stop_id"] for s in self.stops},
            "routes": {r["route_id"] for r in self.routes},
            "trips": {t["trip_id"] for t in self.trips},
            "services": {t["service_id"] for t in self.trips},
            "shapes": {t.get("shape_id", "") for t in self.trips} - {""},
        }
        metro_routes = {r["route_id"] for r in self.routes if r.get("route_type", "").strip() == "1"}
        self.ref_routes = {
            r["route_id"]
            for r in self.routes
            if r["route_id"] in metro_routes and r.get("route_short_name", "").strip().upper() == ref_line.upper()
        }
        metro_trips = {t["trip_id"] for t in self.trips if t["route_id"] in metro_routes}
        self.ref_trips = {t["trip_id"]: t["service_id"] for t in self.trips if t["route_id"] in self.ref_routes}
        # One pass over stop_times: stops served by the metro, first departure of each reference trip.
        self.metro_stop_ids: set[str] = set()
        first: dict[str, tuple[int, int, str]] = {}
        for st in self.rows("stop_times.txt"):
            trip_id = st["trip_id"]
            if trip_id in metro_trips:
                self.metro_stop_ids.add(st["stop_id"])
            if trip_id in self.ref_trips:
                seq = int(st["stop_sequence"])
                if trip_id not in first or seq < first[trip_id][0]:
                    dep = st.get("departure_time") or st.get("arrival_time")
                    if dep:
                        first[trip_id] = (seq, parse_hhmm(dep), st["stop_id"])
        self.ref_first = {trip: (dep, stop) for trip, (_, dep, stop) in first.items()}
        self.services_by_date = self._services_by_date()

    def _services_by_date(self) -> dict[dt.date, set[str]]:
        by_date: dict[dt.date, set[str]] = defaultdict(set)
        for row in self.rows("calendar.txt"):
            start, end = parse_gtfs_date(row["start_date"]), parse_gtfs_date(row["end_date"])
            flags = [row.get(day, "0").strip() == "1" for day in GTFS_WEEKDAYS]
            day = start
            while day <= end:
                if flags[day.weekday()]:
                    by_date[day].add(row["service_id"])
                day += dt.timedelta(days=1)
        for row in self.rows("calendar_dates.txt"):
            day = parse_gtfs_date(row["date"])
            if row["exception_type"].strip() == "1":
                by_date[day].add(row["service_id"])
            else:
                by_date[day].discard(row["service_id"])
        return {d: s for d, s in by_date.items() if s}

    def departures_on(self, day: dt.date) -> list[tuple[int, str]]:
        """(departure, first stop) of the reference-line trips running on that day."""
        services = self.services_by_date.get(day, set())
        return [self.ref_first[t] for t, svc in self.ref_trips.items() if svc in services and t in self.ref_first]

    def trip_count_on(self, day: dt.date) -> int:
        services = self.services_by_date.get(day, set())
        if self.ref_trips:
            return sum(1 for svc in self.ref_trips.values() if svc in services)
        return sum(1 for t in self.trips if t["service_id"] in services)

    def find_stop(self, name: str) -> dict | None:
        """Tisséo stop with this name, preferring stations served by the metro."""
        target = normalize_name(name)
        candidates = [s for s in self.stops if normalize_name(s.get("stop_name", "")) == target]
        if not candidates:
            return None
        metro_parents = {s.get("parent_station", "") for s in self.stops if s["stop_id"] in self.metro_stop_ids}

        def rank(stop):
            served = stop["stop_id"] in self.metro_stop_ids or stop["stop_id"] in metro_parents
            return (served, stop.get("location_type", "").strip() == "1")

        return max(candidates, key=rank)


# --------------------------------------------------------------------------- positions and times


def resolve_positions(lines, osm_positions, tisseo: TisseoGtfs | None) -> list[str]:
    """Fill lat/lon of every station; returns the list of stations still without a position."""
    missing = []
    for line in lines:
        for st in line["stations"]:
            if st.lat is not None:
                st.origin = f"CSV : {st.precision}"
                continue
            osm = osm_positions.get((st.line_id, st.order))
            if osm:
                st.lat, st.lon = osm["lat"], osm["lon"]
                st.origin = f"OpenStreetMap ({osm['source']}) : {osm['precision']}"
                continue
            if st.anchor and tisseo is not None:
                anchor_name, same_station = st.anchor
                stop = tisseo.find_stop(anchor_name)
                if stop:
                    st.lat, st.lon = float(stop["stop_lat"]), float(stop["stop_lon"])
                    if same_station:
                        st.origin = f"GTFS Tisséo, arrêt {stop['stop_id']} : station exacte (station existante)"
                    else:
                        st.origin = (
                            f"GTFS Tisséo, arrêt {stop['stop_id']} « {stop['stop_name']} » : approximative "
                            "(station existante voisine, la future station est à proximité)"
                        )
                    continue
            missing.append(f"ligne {st.line_id}, n° {st.order} « {st.name} »")
    return missing


def hop_polylines(line, traces) -> list[list[tuple[float, float]]]:
    """Track between consecutive stations: OSM when available, straight segment otherwise."""
    out = []
    stations = line["stations"]
    for a, b in zip(stations, stations[1:]):
        pa, pb = (a.lat, a.lon), (b.lat, b.lon)
        poly = traces.get((line["id"], a.order, b.order))
        if poly:
            poly = list(poly)
            if haversine_m(*poly[0], *pa) > 1:
                poly.insert(0, pa)
            if haversine_m(*poly[-1], *pb) > 1:
                poly.append(pb)
            line["trace_sources"].append("osm")
        else:
            poly = [pa, pb]
            line["trace_sources"].append("droit")
        out.append(poly)
    return out


def compute_offsets(hop_lengths: list[float], checkpoints: list[tuple[int, float]], dwell: int):
    """Arrival/departure offsets (s) at each station from the trip start.

    checkpoints: (station index, cumulative arrival time in s), increasing, first = (0, 0),
    last = (n-1, total). Between two checkpoints, the time left after dwells is split in
    proportion to the distance of each hop.
    """
    n = len(hop_lengths) + 1
    if checkpoints[0] != (0, 0) or checkpoints[-1][0] != n - 1:
        raise BuildError("les points de calage doivent commencer au premier terminus et finir au second")
    run = [0.0] * (n - 1)
    for (ia, ta), (ib, tb) in zip(checkpoints, checkpoints[1:]):
        if ib <= ia or tb <= ta:
            raise BuildError("points de calage non croissants")
        dwells = (ib - ia - 1) + (1 if ia > 0 else 0)
        running = (tb - ta) - dwells * dwell
        dist = sum(hop_lengths[ia:ib])
        if running <= 0 or dist <= 0:
            raise BuildError(f"temps ou distance nuls entre les stations {ia + 1} et {ib + 1}")
        for i in range(ia, ib):
            run[i] = running * hop_lengths[i] / dist
    arrivals, departures = [0.0], [0.0]
    for i in range(n - 1):
        arr = departures[-1] + run[i]
        arrivals.append(arr)
        departures.append(arr + (dwell if i + 1 < n - 1 else 0))
    arr_int = [int(round(x)) for x in arrivals]
    dep_int = [int(round(x)) for x in departures]
    for i in range(n - 1):
        if not dep_int[i] < arr_int[i + 1]:
            raise BuildError(f"temps non croissants entre les stations {i + 1} et {i + 2}")
    return arr_int, dep_int, run


def checkpoint_indices(line) -> list[tuple[int, float]]:
    index = {normalize_name(s.name): i for i, s in enumerate(line["stations"])}
    out = []
    for cp in line["points_de_calage"]:
        key = normalize_name(cp["station"])
        if key not in index:
            raise BuildError(f"ligne {line['id']} : point de calage « {cp['station']} » absent du CSV")
        out.append((index[key], float(cp["minutes"]) * 60))
    out.sort()
    return out


# --------------------------------------------------------------------------- headways and calendar


def period_at(profile_windows, t: int) -> str:
    for start, end, period in profile_windows:
        if parse_hhmm(start) <= t < parse_hhmm(end):
            return period
    return profile_windows[-1][2]


def representative_day(tisseo: TisseoGtfs, weekday: int) -> dt.date | None:
    """Day of that weekday whose reference-line trip count is the median (avoids holidays)."""
    days = [(tisseo.trip_count_on(d), d) for d in sorted(tisseo.services_by_date) if d.weekday() == weekday]
    days = [(n, d) for n, d in days if n > 0]
    if not days:
        return None
    median = statistics.median_low([n for n, _ in days])
    return next(d for n, d in days if n == median)


def gaps_on(tisseo: TisseoGtfs, day: dt.date) -> list[tuple[int, int]]:
    """(departure time, gap to the next departure) from the two main termini of the reference line."""
    by_stop: dict[str, list[int]] = defaultdict(list)
    for dep, stop in tisseo.departures_on(day):
        if dep >= NIGHT_CUT_S:
            by_stop[stop].append(dep)
    main = sorted(by_stop.values(), key=len, reverse=True)[:2]
    out = []
    for deps in main:
        deps.sort()
        out += [(a, b - a) for a, b in zip(deps, deps[1:]) if b > a]
    return out


def amplitude_on(tisseo: TisseoGtfs, day: dt.date) -> tuple[int, int] | None:
    """First and last departure of the service day, including the night coded on the next date."""
    deps = [d for d, _ in tisseo.departures_on(day) if d >= NIGHT_CUT_S]
    if not deps:
        return None
    last = max(deps)
    night = [d for d, _ in tisseo.departures_on(day + dt.timedelta(days=1)) if d < NIGHT_CUT_S]
    if night:
        last = max(last, 24 * 3600 + max(night))
    return min(deps), last


def calibrate(params, tisseo: TisseoGtfs, notes: list[str]) -> dict:
    """Measure headway ratios and service hours on the reference line of the Tisséo GTFS."""
    ref = params.get("calibration_tisseo", {}).get("ligne_reference", "B")
    result = {"coefficients": {}, "amplitude": {}, "mesures": {}, "jours": {}}
    if not tisseo.ref_first:
        notes.append(f"Calibration impossible : ligne de métro « {ref} » introuvable dans le GTFS Tisséo.")
        return result
    profile_day = {"semaine": 1, "samedi": 5, "dimanche": 6}  # Tuesday, Saturday, Sunday
    measured: dict[str, float] = {}
    for profile, windows in params["profils"].items():
        weekday = profile_day.get(profile, 1)
        day = representative_day(tisseo, weekday)
        if day is None:
            continue
        result["jours"][profile] = day.isoformat()
        gaps = gaps_on(tisseo, day)
        per_period: dict[str, list[int]] = defaultdict(list)
        for start, end, period in windows:
            per_period[period] += [g for t, g in gaps if parse_hhmm(start) <= t < parse_hhmm(end)]
        for period, sel in per_period.items():
            # A period shared by several profiles (soirée) is measured on the first one (semaine).
            if period not in measured and sel:
                measured[period] = statistics.median(sel)
    result["mesures"] = measured
    if "pointe" in measured:
        for period, value in measured.items():
            result["coefficients"][period] = max(1.0, round(value / measured["pointe"], 2))
    else:
        notes.append("Calibration partielle : pas de mesure en pointe sur la ligne de référence.")
    for svc in params["services"]:
        weekday = WEEKDAYS_FR.index(svc["jours"][0])
        day = representative_day(tisseo, weekday)
        if day is None:
            continue
        span = amplitude_on(tisseo, day)
        if span:
            result["amplitude"][svc["id"]] = (span[0], span[1], day.isoformat())
    return result


def build_calendar(params, tisseo: TisseoGtfs | None, start: dt.date):
    """Return (start, end, {date: service id or None}) for the futur feed."""
    services = params["services"]
    default = {WEEKDAYS_FR.index(d): s["id"] for s in services for d in s["jours"]}
    if tisseo is None or not tisseo.services_by_date:
        days = params["flux"].get("jours_autonomes", 21)
        dates = [start + dt.timedelta(days=i) for i in range(days)]
        return dates[0], dates[-1], {d: default[d.weekday()] for d in dates}
    holiday_service = next((s["id"] for s in services if s.get("jours_feries")), None)
    dates = sorted(tisseo.services_by_date)
    first, last = dates[0], dates[-1]
    counts = {}
    day = first
    while day <= last:
        counts[day] = tisseo.trip_count_on(day)
        day += dt.timedelta(days=1)
    reference = {}
    for svc in services:
        values = [n for d, n in counts.items() if default[d.weekday()] == svc["id"] and n > 0]
        reference[svc["id"]] = statistics.median(values) if values else None
    assigned = {}
    for day, n in counts.items():
        svc = default[day.weekday()]
        if n == 0:
            assigned[day] = None
        elif (
            holiday_service
            and svc != holiday_service
            and reference.get(holiday_service) is not None
            and reference.get(svc) is not None
            and abs(n - reference[holiday_service]) < abs(n - reference[svc])
        ):
            assigned[day] = holiday_service
        else:
            assigned[day] = svc
    return first, last, assigned


# --------------------------------------------------------------------------- feed assembly


def build_feed(params, lines, tisseo: TisseoGtfs | None, start: dt.date, osm_used: bool):
    notes: list[str] = []
    prefix = params["flux"]["prefixe_id"]
    dwell = int(params["temps_arret_s"])

    calib = calibrate(params, tisseo, notes) if tisseo is not None and params.get("calibration_tisseo", {}).get("actif") else None
    coefficients = dict(params["coefficients_intervalle"])
    coeff_origin = {k: "hypothèse (parametres.yaml)" for k in coefficients}
    if calib:
        for period, value in calib["coefficients"].items():
            if period in coefficients:
                coefficients[period] = value
                coeff_origin[period] = f"mesuré sur la ligne B Tisséo ({fmt_minsec(calib['mesures'][period])})"

    amplitude = {}
    for svc in params["services"]:
        first, last = parse_hhmm(svc["premier_depart"]), parse_hhmm(svc["dernier_depart"])
        origin = "parametres.yaml"
        if calib and svc["id"] in calib["amplitude"]:
            first, last, day = calib["amplitude"][svc["id"]]
            origin = f"mesuré sur la ligne B Tisséo le {day}"
        amplitude[svc["id"]] = (first, last, origin)

    tables: dict[str, list[dict]] = defaultdict(list)
    agency_id = f"{prefix}TD"
    tables["agency.txt"].append(
        {
            "agency_id": agency_id,
            "agency_name": params["flux"]["agence"]["nom"],
            "agency_url": params["flux"]["agence"]["url"],
            "agency_timezone": params["flux"]["fuseau"],
            "agency_lang": params["flux"]["langue"],
        }
    )

    # Stops: one parent station per name (shared by lines), one platform per line.
    parents: dict[str, dict] = {}
    for line in lines:
        for st in line["stations"]:
            key = normalize_name(st.name)
            parents.setdefault(key, {"name": st.name, "points": []})["points"].append((st.lat, st.lon))
    for key, info in parents.items():
        lat = sum(p[0] for p in info["points"]) / len(info["points"])
        lon = sum(p[1] for p in info["points"]) / len(info["points"])
        info["stop_id"] = f"{prefix}STA_{slug(info['name'])}"
        tables["stops.txt"].append(
            {
                "stop_id": info["stop_id"],
                "stop_name": info["name"],
                "stop_lat": f"{lat:.6f}",
                "stop_lon": f"{lon:.6f}",
                "location_type": "1",
                "parent_station": "",
                "stop_desc": "Station en projet (simulation Toulouse Demain)",
            }
        )
    platform_id = {}
    for line in lines:
        for st in line["stations"]:
            sid = f"{prefix}{line['id']}_{slug(st.name)}"
            platform_id[(line["id"], st.order)] = sid
            tables["stops.txt"].append(
                {
                    "stop_id": sid,
                    "stop_name": st.name,
                    "stop_lat": f"{st.lat:.6f}",
                    "stop_lon": f"{st.lon:.6f}",
                    "location_type": "0",
                    "parent_station": parents[normalize_name(st.name)]["stop_id"],
                    "stop_desc": f"Ligne {line['nom_court']} en projet. Position : {st.origin}"[:500],
                }
            )

    services_used = set()
    for line in lines:
        route_id = f"{prefix}{line['id']}"
        tables["routes.txt"].append(
            {
                "route_id": route_id,
                "agency_id": agency_id,
                "route_short_name": line["nom_court"],
                "route_long_name": line["nom_long"],
                "route_desc": "Ligne en projet : horaires simulés, voir les hypothèses du projet Toulouse Demain",
                "route_type": "1",
                "route_color": line.get("couleur", ""),
                "route_text_color": line.get("couleur_texte", ""),
            }
        )
        stations = line["stations"]
        polylines = line["polylines"]
        hop_lengths = [polyline_length_m(p) for p in polylines]
        checkpoints = checkpoint_indices(line)
        total = checkpoints[-1][1]
        directions = {
            0: (list(range(len(stations))), hop_lengths, checkpoints, polylines),
            1: (
                list(reversed(range(len(stations)))),
                list(reversed(hop_lengths)),
                sorted((len(stations) - 1 - i, total - t) for i, t in checkpoints),
                [list(reversed(p)) for p in reversed(polylines)],
            ),
        }
        line["schedule"] = {}
        for direction, (idx, lengths, cps, polys) in directions.items():
            arr, dep, run = compute_offsets(lengths, cps, dwell)
            line["schedule"][direction] = (idx, arr, dep, lengths)
            shape_id = f"{prefix}SH_{line['id']}_{direction}"
            cum = 0.0
            seq = 0
            dist_at_stop = [0.0]
            for h, poly in enumerate(polys):
                pts = poly if h == 0 else poly[1:]
                prev = None if h == 0 else polys[h - 1][-1]
                for p in pts:
                    if prev is not None:
                        cum += haversine_m(*prev, *p)
                    seq += 1
                    tables["shapes.txt"].append(
                        {
                            "shape_id": shape_id,
                            "shape_pt_lat": f"{p[0]:.6f}",
                            "shape_pt_lon": f"{p[1]:.6f}",
                            "shape_pt_sequence": str(seq),
                            "shape_dist_traveled": f"{cum:.1f}",
                        }
                    )
                    prev = p
                dist_at_stop.append(cum)
            headsign = stations[idx[-1]].name
            for svc in params["services"]:
                first, last, _ = amplitude[svc["id"]]
                windows = params["profils"][svc["profil"]]
                t, k = first, 0
                while t <= last:
                    k += 1
                    trip_id = f"{prefix}{line['id']}_{svc['id']}_{direction}_{k:04d}"
                    tables["trips.txt"].append(
                        {
                            "route_id": route_id,
                            "service_id": f"{prefix}{svc['id']}",
                            "trip_id": trip_id,
                            "trip_headsign": headsign,
                            "direction_id": str(direction),
                            "shape_id": shape_id,
                        }
                    )
                    for s, i in enumerate(idx):
                        tables["stop_times.txt"].append(
                            {
                                "trip_id": trip_id,
                                "arrival_time": fmt_time(t + arr[s]),
                                "departure_time": fmt_time(t + dep[s]),
                                "stop_id": platform_id[(line["id"], stations[i].order)],
                                "stop_sequence": str(s + 1),
                                "timepoint": "0",
                                "shape_dist_traveled": f"{dist_at_stop[s]:.1f}",
                            }
                        )
                    services_used.add(svc["id"])
                    headway = line["intervalle_pointe_s"] * coefficients[period_at(windows, t)]
                    t += max(60, int(round(headway)))

    # Calendar
    cal_start, cal_end, assigned = build_calendar(params, tisseo, start)
    default = {WEEKDAYS_FR.index(d): s["id"] for s in params["services"] for d in s["jours"]}
    for svc in params["services"]:
        row = {"service_id": f"{prefix}{svc['id']}"}
        for i, day in enumerate(GTFS_WEEKDAYS):
            row[day] = "1" if WEEKDAYS_FR[i] in svc["jours"] else "0"
        row["start_date"], row["end_date"] = gtfs_date(cal_start), gtfs_date(cal_end)
        tables["calendar.txt"].append(row)
    exceptions = []
    day = cal_start
    while day <= cal_end:
        normal, actual = default[day.weekday()], assigned.get(day)
        if actual != normal:
            tables["calendar_dates.txt"].append(
                {"service_id": f"{prefix}{normal}", "date": gtfs_date(day), "exception_type": "2"}
            )
            if actual:
                tables["calendar_dates.txt"].append(
                    {"service_id": f"{prefix}{actual}", "date": gtfs_date(day), "exception_type": "1"}
                )
            exceptions.append((day, normal, actual))
        day += dt.timedelta(days=1)

    # Transfers inside the futur feed (cross-feed transfers are left to the engine, see the doc).
    line_by_id = {line["id"]: line for line in lines}
    for corr in params.get("correspondances_internes", []):
        key = normalize_name(corr["station"])
        ids = []
        for lid in corr["lignes"]:
            st = next((s for s in line_by_id[lid]["stations"] if normalize_name(s.name) == key), None)
            if st is None:
                raise BuildError(f"correspondance « {corr['station']} » : station absente de la ligne {lid}")
            ids.append(platform_id[(lid, st.order)])
        for a in ids:
            for b in ids:
                if a != b:
                    tables["transfers.txt"].append(
                        {
                            "from_stop_id": a,
                            "to_stop_id": b,
                            "transfer_type": "2",
                            "min_transfer_time": str(int(corr["temps_min_s"])),
                        }
                    )

    version = hashlib.sha256(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()[:8]
    tables["feed_info.txt"].append(
        {
            "feed_publisher_name": params["flux"]["nom_editeur"],
            "feed_publisher_url": params["flux"]["url_editeur"],
            "feed_lang": params["flux"]["langue"],
            "feed_start_date": gtfs_date(cal_start),
            "feed_end_date": gtfs_date(cal_end),
            "feed_version": f"futur-{gtfs_date(cal_start)}-{version}",
            "feed_license": f"{params['flux']['licence']} ({params['flux']['licence_url']}) - données dérivées sous ODbL",
        }
    )
    attributions = [
        (f"{prefix}ATT_TD", "Toulouse Demain - données simulées, non officielles (ODbL)", "1", "0", "0",
         params["flux"]["url_editeur"]),
        (f"{prefix}ATT_TISSEO", "Tisséo Collectivités - chiffres publics des projets ; GTFS Tisséo (ODbL)", "0", "0", "1",
         "https://tisseo-collectivites.fr"),
    ]
    if osm_used:
        attributions.append(
            (f"{prefix}ATT_OSM", "© les contributeurs d'OpenStreetMap (ODbL)", "1", "0", "0",
             "https://www.openstreetmap.org/copyright")
        )
    for att_id, name, prod, oper, auth, url in attributions:
        tables["attributions.txt"].append(
            {
                "attribution_id": att_id,
                "organization_name": name,
                "is_producer": prod,
                "is_operator": oper,
                "is_authority": auth,
                "attribution_url": url,
            }
        )

    if tisseo is not None:
        check_collisions(tables, tisseo)

    context = {
        "notes": notes,
        "coefficients": coefficients,
        "coeff_origin": coeff_origin,
        "amplitude": amplitude,
        "calibration": calib,
        "calendar": (cal_start, cal_end, exceptions),
        "dwell": dwell,
    }
    return tables, context


def check_collisions(tables, tisseo: TisseoGtfs) -> None:
    pairs = {
        "agency": ("agency.txt", "agency_id"),
        "stops": ("stops.txt", "stop_id"),
        "routes": ("routes.txt", "route_id"),
        "trips": ("trips.txt", "trip_id"),
        "services": ("calendar.txt", "service_id"),
        "shapes": ("shapes.txt", "shape_id"),
    }
    for kind, (table, column) in pairs.items():
        ours = {row[column] for row in tables[table]}
        clash = ours & tisseo.ids[kind]
        if clash:
            raise BuildError(f"identifiants en collision avec Tisséo ({kind}) : {sorted(clash)[:5]}")


def write_zip(tables: dict[str, list[dict]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_name(output.name + ".tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(tables):
            rows = tables[name]
            if not rows:
                continue
            columns = list(rows[0].keys())
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))  # reproducible archive
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, buf.getvalue().encode("utf-8"))
    tmp.replace(output)


# --------------------------------------------------------------------------- report


def nearest_tisseo(tisseo: TisseoGtfs, lat: float, lon: float, radius: float, limit: int = 3):
    found = []
    for s in tisseo.stops:
        try:
            d = haversine_m(lat, lon, float(s["stop_lat"]), float(s["stop_lon"]))
        except (KeyError, ValueError):
            continue
        if d <= radius and s.get("location_type", "0").strip() in ("", "0", "1"):
            found.append((d, s))
    found.sort(key=lambda x: x[0])
    seen, out = set(), []
    for d, s in found:
        key = normalize_name(s.get("stop_name", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(f"{s.get('stop_name', '')} ({d:.0f} m)")
        if len(out) == limit:
            break
    return out


def write_report(path: Path, params, lines, context, tisseo: TisseoGtfs | None, osm_dir: Path | None, tables) -> list[str]:
    warnings = list(context["notes"])
    out = ["# Rapport de construction du GTFS « futur »", ""]
    out.append("Données dérivées sous ODbL. Horaires simulés : voir docs/hypotheses-reseau-2028.md.")
    out.append("")
    out.append(f"- GTFS Tisséo : {'oui (' + tisseo.path.name + ')' if tisseo else 'non (calendrier autonome)'}")
    out.append(f"- Extraction OSM : {'oui (' + str(osm_dir) + ')' if osm_dir and osm_dir.exists() else 'non'}")
    cal_start, cal_end, exceptions = context["calendar"]
    out.append(f"- Calendrier : du {cal_start.isoformat()} au {cal_end.isoformat()}, {len(exceptions)} jour(s) modifié(s)")
    for day, normal, actual in exceptions[:30]:
        out.append(f"  - {day.isoformat()} : {normal} → {actual or 'aucun service'}")
    out.append(f"- Temps d'arrêt en station : {context['dwell']} s")
    out.append("")
    for line in lines:
        out.append(f"## Ligne {line['nom_court']} ({line['id']})")
        out.append("")
        out.append("| # | Station | lat | lon | Position |")
        out.append("| --- | --- | --- | --- | --- |")
        for st in line["stations"]:
            out.append(f"| {st.order} | {st.name} | {st.lat:.6f} | {st.lon:.6f} | {st.origin} |")
        out.append("")
        idx, arr, dep, lengths = line["schedule"][0]
        stations = line["stations"]
        out.append("| De | À | Distance (m) | Tracé | Arrivée cumulée |")
        out.append("| --- | --- | --- | --- | --- |")
        for h, length in enumerate(lengths):
            if length < MIN_HOP_M or length > MAX_HOP_M:
                warnings.append(
                    f"Ligne {line['id']} : distance peu plausible {stations[h].name} → {stations[h + 1].name} ({length:.0f} m)"
                )
            out.append(
                f"| {stations[h].name} | {stations[h + 1].name} | {length:.0f} | {line['trace_sources'][h]} | {fmt_minsec(arr[h + 1])} |"
            )
        total_m = sum(lengths)
        out.append("")
        out.append(
            f"Longueur : {total_m / 1000:.2f} km ; temps de bout en bout : {fmt_minsec(arr[-1])} ; "
            f"vitesse commerciale : {total_m / 1000 / (arr[-1] / 3600):.1f} km/h."
        )
        out.append("")
    out.append("## Intervalles")
    out.append("")
    out.append("| Période | Coefficient | Origine | " + " | ".join(f"Ligne {l['id']}" for l in lines) + " |")
    out.append("| --- | --- | --- | " + " | ".join("---" for _ in lines) + " |")
    for period, coef in context["coefficients"].items():
        values = " | ".join(fmt_minsec(max(60, l["intervalle_pointe_s"] * coef)) for l in lines)
        out.append(f"| {period} | {coef} | {context['coeff_origin'][period]} | {values} |")
    out.append("")
    out.append("| Service | Premier départ | Dernier départ | Origine |")
    out.append("| --- | --- | --- | --- |")
    for svc_id, (first, last, origin) in context["amplitude"].items():
        out.append(f"| {svc_id} | {fmt_time(first)} | {fmt_time(last)} | {origin} |")
    out.append("")
    if tisseo is not None:
        radius = params.get("correspondances_tisseo", {}).get("rayon_m", 400)
        out.append(f"## Arrêts Tisséo à moins de {radius} m")
        out.append("")
        out.append("Les correspondances avec le réseau actuel sont calculées par le moteur (marche sur le réseau OSM).")
        out.append("")
        out.append("| Ligne | Station | Correspondances attendues | Arrêts Tisséo proches |")
        out.append("| --- | --- | --- | --- |")
        for line in lines:
            for st in line["stations"]:
                near = nearest_tisseo(tisseo, st.lat, st.lon, radius)
                tisseo_modes = [c for c in st.connections.split(";") if c.strip().startswith(("Métro A", "Métro B", "Tram"))]
                tisseo_modes = [c for c in tisseo_modes if "prolongement" not in c]
                if tisseo_modes and not near:
                    warnings.append(f"{st.name} : correspondance attendue mais aucun arrêt Tisséo à moins de {radius} m")
                out.append(f"| {line['id']} | {st.name} | {st.connections or '-'} | {', '.join(near) or '-'} |")
        out.append("")
    counts = {name: len(rows) for name, rows in sorted(tables.items())}
    out.append("## Contenu du GTFS")
    out.append("")
    for name, n in counts.items():
        out.append(f"- {name} : {n} ligne(s)")
    out.append("")
    out.append("## Avertissements")
    out.append("")
    out += [f"- {w}" for w in warnings] or ["- aucun"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return warnings


# --------------------------------------------------------------------------- main


def run(args) -> int:
    params_path = Path(args.params)
    params = load_params(params_path)
    base = REPO_ROOT if params_path.resolve().is_relative_to(REPO_ROOT) else params_path.parent
    lines = []
    for line in params["lignes"]:
        line = dict(line)
        line["stations"] = load_stations(resolve_path(line["stations"], base), line["id"])
        line["trace_sources"] = []
        lines.append(line)

    osm_dir = Path(args.osm_dir) if args.osm_dir else None
    osm_positions, osm_traces = load_osm_outputs(osm_dir if osm_dir and osm_dir.exists() else None)

    tisseo = None
    if args.tisseo_gtfs:
        tisseo = TisseoGtfs(Path(args.tisseo_gtfs))
        tisseo.load(params.get("calibration_tisseo", {}).get("ligne_reference", "B"))

    missing = resolve_positions(lines, osm_positions, tisseo)
    if missing:
        raise BuildError(
            "stations sans coordonnées vérifiables (aucune n'est inventée) :\n  - "
            + "\n  - ".join(missing)
            + "\nComplétez lat/lon dans data/futur/*.csv (source OSM ou officielle) "
            "ou lancez d'abord scripts/extract_futur_osm.py sur un extrait OSM."
        )
    for line in lines:
        line["polylines"] = hop_polylines(line, osm_traces)

    start = dt.date.fromisoformat(args.start_date) if args.start_date else dt.date.today()
    osm_used = bool(osm_positions) or bool(osm_traces)
    tables, context = build_feed(params, lines, tisseo, start, osm_used)

    output = Path(args.output)
    write_zip(tables, output)
    report = output.with_name(output.name.split(".")[0] + "-rapport.md")
    warnings = write_report(report, params, lines, context, tisseo, osm_dir, tables)
    print(f"GTFS futur écrit : {output} ({len(tables['trips.txt'])} courses, {len(tables['stops.txt'])} arrêts)")
    print(f"Rapport : {report}")
    for w in warnings:
        print(f"AVERTISSEMENT : {w}", file=sys.stderr)
    return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Construit le GTFS des lignes futures (scénario 2028).")
    parser.add_argument("--tisseo-gtfs", help="GTFS officiel Tisséo (zip), facultatif")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="zip GTFS à produire")
    parser.add_argument("--params", default=str(DEFAULT_PARAMS), help="fichier de paramètres YAML")
    parser.add_argument("--osm-dir", default=str(DEFAULT_OSM_DIR), help="sorties de extract_futur_osm.py (si présentes)")
    parser.add_argument("--start-date", help="AAAA-MM-JJ, début du calendrier autonome (défaut : aujourd'hui)")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    try:
        return run(parse_args(argv))
    except BuildError as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
