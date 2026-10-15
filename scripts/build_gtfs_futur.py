#!/usr/bin/env python3
"""Build the "futur" GTFS feed (scenario "Réseau 2028") for Toulouse Demain.

Contract (fixed with the architect):

    python scripts/build_gtfs_futur.py --tisseo-gtfs <tisseo.zip> --output build/gtfs/futur.gtfs.zip

``--tisseo-gtfs`` is optional, and so is ``--sncf-gtfs <sncf.gtfs.zip>`` (the SNCF GTFS already
filtered to the zone, for the TER halts). The routing engine loads the output under the feed id
``futur``.

TER halts (``haltes_ter``, data/futur/haltes_ter.csv), with the SNCF GTFS: the SNCF lines whose
trains call at the two neighbouring stations of a halt are copied in this feed, the halt inserted
in those trains (time in proportion to the distance, plus a dwell that delays the rest of the
trip), and scenario 2028 excludes the original SNCF lines. A halt already served in the SNCF GTFS
is never duplicated.

Inputs
    data/futur/stations_*.csv (stations of each line, in order; metro C, B extension, Ligne Aéroport tram)
    data/futur/parametres.yaml (headways, service hours, travel times; see docs/hypotheses-reseau-2028.md)
    build/futur-osm/ (optional): positions and track produced by scripts/extract_futur_osm.py

Each line is a metro (route_type 1, default) or a tram (``route_type: 0``).

Station positions, by priority: the CSV, then the OSM extraction, then the Tisséo stop named in
column ``arret_tisseo_reference``. A station without any position stops the build (exit code 2):
we never invent a coordinate.

With the Tisséo GTFS: service dates follow its calendar (public holidays run as Sundays), headway
ratios and service hours are measured on its metro line B, and a proximity report lists the
nearest existing stops. Line B is copied (same stops, times and shapes) as route "B" of this
feed, and enough of its trains run on to Labège Madron to give the extension headway; scenario
2028 then excludes the Tisséo line B (scenario-2028.json). Without it: a standalone 21-day
calendar, the default parameters and a Ramonville – Labège Madron shuttle.

Scenario 2028 also excludes the Tisséo lines listed in ``lignes_tisseo_remplacees`` (for example
the airport shuttle, replaced by the Ligne Aéroport): each route_short_name is resolved to its
route_id in the Tisséo GTFS, and the build stops (exit code 2) if it matches no route or several.

Output, in the folder of --output: the GTFS zip (data derived under ODbL), scenario-2028.json
and a Markdown report.
"""

from __future__ import annotations

import argparse
import bisect
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
from collections import Counter, defaultdict
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
# Line B extension: a gap longer than this between two trains starts a new grid of extended trains.
RUN_GAP_S = 30 * 60
# GTFS route_type values a future line may have.
ROUTE_TYPES = {0: "tram", 1: "métro"}
# TER halts: pseudo line id (OSM extraction, identifiers), and the guards.
TER_LINE_ID = "TER"
HALT_DETOUR_RATIO = 1.5  # d(A, halt) + d(halt, B) must stay below 1.5 × d(A, B) + 300 m
HALT_DETOUR_SLACK_M = 300


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
    between: tuple[str, ...] = ()  # TER halt only: the two neighbouring SNCF stations
    announced: int | None = None  # TER halt only: trains per day announced (for the report)


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
    line_ids = [line["id"] for line in params["lignes"]]
    if len(line_ids) != len(set(line_ids)):
        raise BuildError(f"identifiants de ligne en double : {line_ids}")
    for line in params["lignes"]:
        if route_type(line) not in ROUTE_TYPES:
            raise BuildError(f"ligne {line['id']} : route_type {line.get('route_type')!r} non pris en charge "
                             f"({', '.join(f'{k} = {v}' for k, v in ROUTE_TYPES.items())})")
    haltes = params.get("haltes_ter")
    if haltes:
        for key in ("stations", "haltes"):
            if key not in haltes:
                raise BuildError(f"haltes_ter : clé « {key} » manquante")
        for h in haltes["haltes"]:
            between = h.get("entre") or []
            if len(between) != 2 or normalize_name(between[0]) == normalize_name(between[1]):
                raise BuildError(f"haltes_ter : la halte {h.get('station')} doit avoir deux gares voisines distinctes "
                                 f"(« entre »), pas {between}")
    for item in params.get("lignes_tisseo_remplacees") or []:
        if not str(item.get("ligne", "")).strip():
            raise BuildError(f"lignes_tisseo_remplacees : « ligne » (route_short_name Tisséo) manquante dans {item}")
        if item.get("remplacee_par") not in line_ids:
            raise BuildError(f"lignes_tisseo_remplacees : la ligne Tisséo {item['ligne']} est remplacée par "
                             f"« {item.get('remplacee_par')} », absente de « lignes » {line_ids}")
    return params


def route_type(line: dict) -> int:
    """GTFS route_type of a future line: 1 (metro) unless the parameters say otherwise."""
    try:
        return int(line.get("route_type", 1))
    except (TypeError, ValueError):
        return -1


def resolve_path(value: str, base: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def load_stations(csv_path: Path, line_id: str, min_count: int = 2) -> list[Station]:
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
    if len(stations) < min_count:
        raise BuildError(f"{csv_path.name} : au moins {min_count} stations sont nécessaires")
    return stations


def load_haltes(params, base: Path) -> list[Station]:
    """TER halts of haltes_ter (parametres.yaml), with their CSV row and their two neighbours."""
    cfg = params.get("haltes_ter")
    if not cfg:
        return []
    csv_path = resolve_path(cfg["stations"], base)
    by_name = {normalize_name(s.name): s for s in load_stations(csv_path, TER_LINE_ID, min_count=1)}
    out = []
    for item in cfg["haltes"]:
        st = by_name.get(normalize_name(item["station"]))
        if st is None:
            raise BuildError(f"haltes_ter : la halte « {item['station']} » est absente de {csv_path.name}")
        st.between = tuple(item["entre"])
        st.announced = item.get("trains_par_jour_annonces")
        out.append(st)
    return out


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
            "services": {t["service_id"] for t in self.trips}
            | {r["service_id"] for r in self.rows("calendar.txt")}
            | {r["service_id"] for r in self.rows("calendar_dates.txt")},
            "shapes": {t.get("shape_id", "") for t in self.trips} - {""},
        }
        metro_routes = {r["route_id"] for r in self.routes if r.get("route_type", "").strip() == "1"}
        self.ref_routes = {
            r["route_id"]
            for r in self.routes
            if r["route_id"] in metro_routes and r.get("route_short_name", "").strip().upper() == ref_line.upper()
        }
        metro_trips = {t["trip_id"] for t in self.trips if t["route_id"] in metro_routes}
        self.ref_route_rows = [r for r in self.routes if r["route_id"] in self.ref_routes]
        self.ref_trip_rows = [t for t in self.trips if t["route_id"] in self.ref_routes]
        self.ref_trips = {t["trip_id"]: t["service_id"] for t in self.ref_trip_rows}
        # One pass over stop_times: stops served by the metro, all stop times of the reference line.
        self.metro_stop_ids: set[str] = set()
        self.ref_stop_times: dict[str, list[dict]] = defaultdict(list)
        for st in self.rows("stop_times.txt"):
            trip_id = st["trip_id"]
            if trip_id in metro_trips:
                self.metro_stop_ids.add(st["stop_id"])
            if trip_id in self.ref_trips:
                self.ref_stop_times[trip_id].append(
                    {
                        "stop_id": st["stop_id"],
                        "seq": int(st["stop_sequence"]),
                        "arrival_time": (st.get("arrival_time") or "").strip(),
                        "departure_time": (st.get("departure_time") or "").strip(),
                    }
                )
        self.ref_first: dict[str, tuple[int, str]] = {}
        for trip_id, rows in self.ref_stop_times.items():
            rows.sort(key=lambda r: r["seq"])
            dep = rows[0]["departure_time"] or rows[0]["arrival_time"]
            if dep:
                self.ref_first[trip_id] = (parse_hhmm(dep), rows[0]["stop_id"])
        self.services_by_date = self._services_by_date()

    def shapes_for(self, shape_ids: set[str]) -> dict[str, list[tuple[float, float]]]:
        points: dict[str, list[tuple[int, float, float]]] = defaultdict(list)
        for row in self.rows("shapes.txt"):
            if row["shape_id"] in shape_ids:
                points[row["shape_id"]].append(
                    (int(row["shape_pt_sequence"]), float(row["shape_pt_lat"]), float(row["shape_pt_lon"]))
                )
        return {sid: [(lat, lon) for _, lat, lon in sorted(pts)] for sid, pts in points.items()}

    def calendar_rows(self, service_ids: set[str]) -> tuple[list[dict], list[dict]]:
        calendar = [r for r in self.rows("calendar.txt") if r["service_id"] in service_ids]
        dates = [r for r in self.rows("calendar_dates.txt") if r["service_id"] in service_ids]
        return calendar, dates

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

    def routes_named(self, short_name: str) -> list[dict]:
        """Routes whose route_short_name is this one (case and surrounding spaces ignored)."""
        target = short_name.strip().casefold()
        return [r for r in self.routes if (r.get("route_short_name") or "").strip().casefold() == target]

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


# --------------------------------------------------------------------------- line B through trains


def select_slots(items: list[tuple[int, str]], headway_at) -> set[str]:
    """Trains to extend: for a regular grid of slots, the train closest to each slot.

    items: (time at the junction station, trip id), sorted. The grid restarts after a gap longer
    than RUN_GAP_S, so that night trains do not shift the selection of the day.
    When trains are rarer than the target headway, every train is selected.
    """
    selected: set[str] = set()
    runs: list[list[tuple[int, str]]] = []
    for item in items:
        if runs and item[0] - runs[-1][-1][0] <= RUN_GAP_S:
            runs[-1].append(item)
        else:
            runs.append([item])
    for run in runs:
        times = [t for t, _ in run]
        slot = times[0]
        while slot <= times[-1]:
            k = bisect.bisect_left(times, slot)
            best = min((i for i in (k - 1, k) if 0 <= i < len(times)), key=lambda i: (abs(times[i] - slot), times[i]))
            selected.add(run[best][1])
            slot += max(60, headway_at(slot))
    return selected


def build_b_direct(params, line, tisseo: TisseoGtfs, tables, platform_id, coefficients, assigned, agency_id) -> dict:
    """Copy every trip of Tisséo line B, and extend the trains needed for the extension headway.

    Trains arriving at the junction (Ramonville) continue to the new stations; trains leaving it
    start from the new terminus. Copied stops, times and shapes are those of Tisséo.
    """
    prefix = params["flux"]["prefixe_id"]
    tis = f"{prefix}TIS_"
    cfg = line["prolongement_tisseo"]
    dwell = int(params["temps_arret_s"])
    stations = line["stations"]
    junction = normalize_name(cfg["raccordement"])
    if normalize_name(stations[0].name) != junction:
        raise BuildError(f"ligne {line['id']} : la première station doit être le raccordement {cfg['raccordement']}")
    junction_ids = {s["stop_id"] for s in tisseo.stops if normalize_name(s.get("stop_name", "")) == junction}
    idx0, arr0, dep0, _ = line["schedule"][0]
    idx1, arr1, dep1, _ = line["schedule"][1]
    profile_of = {s["id"]: s["profil"] for s in params["services"]}
    default = {WEEKDAYS_FR.index(d): s["id"] for s in params["services"] for d in s["jours"]}

    # Trains at the junction: arriving there (to extend after) or leaving from there (to extend before).
    inbound, outbound = {}, {}
    for trip in tisseo.ref_trip_rows:
        rows = tisseo.ref_stop_times.get(trip["trip_id"], [])
        if len(rows) < 2:
            continue
        last, first = rows[-1], rows[0]
        if last["stop_id"] in junction_ids and (last["arrival_time"] or last["departure_time"]):
            inbound[trip["trip_id"]] = parse_hhmm(last["arrival_time"] or last["departure_time"])
        elif first["stop_id"] in junction_ids and (first["departure_time"] or first["arrival_time"]):
            outbound[trip["trip_id"]] = parse_hhmm(first["departure_time"] or first["arrival_time"])

    # Days with the same set of line B services share one selection.
    b_services = set(tisseo.ref_trips.values())
    sig_dates: dict[frozenset, list[dt.date]] = defaultdict(list)
    for day, services in sorted(tisseo.services_by_date.items()):
        sig = frozenset(services & b_services)
        if sig:
            sig_dates[sig].append(day)
    selected_by_sig, profile_by_sig = {}, {}
    for sig, dates in sig_dates.items():
        profile = Counter(profile_of[assigned.get(d) or default[d.weekday()]] for d in dates).most_common(1)[0][0]
        windows = params["profils"][profile]

        def headway_at(t, windows=windows):
            return int(round(line["intervalle_pointe_s"] * coefficients[period_at(windows, t)]))

        sel = set()
        for group in (inbound, outbound):
            sel |= select_slots(sorted((t, tid) for tid, t in group.items() if tisseo.ref_trips[tid] in sig), headway_at)
        selected_by_sig[sig], profile_by_sig[sig] = sel, profile

    # One copy per trip, two (with their own dates) when the choice differs between days.
    variants, split_services = [], {}
    for trip in tisseo.ref_trip_rows:
        tid, svc = trip["trip_id"], trip["service_id"]
        ext_dates, plain_dates = [], []
        for sig, dates in sig_dates.items():
            if svc in sig:
                (ext_dates if tid in selected_by_sig[sig] else plain_dates).extend(dates)
        if not ext_dates and not plain_dates:
            continue  # never runs
        if not plain_dates or not ext_dates:
            variants.append((trip, bool(ext_dates), f"{tis}{svc}"))
            continue
        for ext, dates in ((True, ext_dates), (False, plain_dates)):
            key = (svc, tuple(sorted(dates)))
            if key not in split_services:
                digest = hashlib.sha256(",".join(d.isoformat() for d in key[1]).encode()).hexdigest()[:6]
                split_services[key] = f"{tis}{svc}_{digest}"
            variants.append((trip, ext, split_services[key]))

    # Route, stops, shapes
    route = tisseo.ref_route_rows[0]
    route_id = f"{prefix}B"
    tables["routes.txt"].append(
        {
            "route_id": route_id,
            "agency_id": agency_id,
            "route_short_name": route.get("route_short_name") or line["nom_court"],
            "route_long_name": f"{route.get('route_long_name') or 'Ligne B'} – prolongée jusqu'à {stations[-1].name} (projet)",
            "route_desc": "Ligne B du GTFS Tisséo recopiée et prolongée : horaires simulés sur le prolongement",
            "route_type": "1",
            "route_color": (route.get("route_color") or line.get("couleur", "")).upper(),
            "route_text_color": (route.get("route_text_color") or line.get("couleur_texte", "")).upper(),
        }
    )
    stop_by_id = {s["stop_id"]: s for s in tisseo.stops}
    used = {r["stop_id"] for t, _, _ in variants for r in tisseo.ref_stop_times[t["trip_id"]]}
    used |= {stop_by_id[s].get("parent_station") for s in used if s in stop_by_id and stop_by_id[s].get("parent_station")}
    for sid in sorted(used):
        stop = stop_by_id[sid]
        parent = stop.get("parent_station", "")
        tables["stops.txt"].append(
            {
                "stop_id": f"{tis}{sid}",
                "stop_name": stop["stop_name"],
                "stop_lat": f"{float(stop['stop_lat']):.6f}",
                "stop_lon": f"{float(stop['stop_lon']):.6f}",
                "location_type": (stop.get("location_type") or "0").strip() or "0",
                "parent_station": f"{tis}{parent}" if parent else "",
                "stop_desc": "Arrêt de la ligne B recopié du GTFS Tisséo (ODbL)",
            }
        )
    extension = [p for h, poly in enumerate(line["polylines"]) for p in (poly if h == 0 else poly[1:])]

    def write_shape(shape_id, points):
        cum, prev = 0.0, None
        for seq, p in enumerate(points, start=1):
            if prev is not None:
                cum += haversine_m(*prev, *p)
            tables["shapes.txt"].append(
                {"shape_id": shape_id, "shape_pt_lat": f"{p[0]:.6f}", "shape_pt_lon": f"{p[1]:.6f}",
                 "shape_pt_sequence": str(seq), "shape_dist_traveled": f"{cum:.1f}"}
            )
            prev = p

    base_shapes = tisseo.shapes_for({t.get("shape_id", "") for t, _, _ in variants} - {""})
    written_shapes = set()

    def shape_for(trip, ext_kind):
        sid = trip.get("shape_id", "")
        if sid not in base_shapes:
            return ""
        out_id = f"{tis}{sid}" + {"": "", "in": "_P", "out": "_PD"}[ext_kind]
        if out_id not in written_shapes:
            points = base_shapes[sid]
            if ext_kind == "in":
                points = points + extension
            elif ext_kind == "out":
                points = extension[::-1] + points
            write_shape(out_id, points)
            written_shapes.add(out_id)
        return out_id

    # Trips and stop times
    counts = Counter()
    used_original_services = set()
    for trip, ext, service_id in variants:
        tid = trip["trip_id"]
        kind = ("in" if tid in inbound else "out" if tid in outbound else "") if ext else ""
        rows = [
            {
                "trip_id": f"{tis}{tid}" + ("_P" if kind else ""),
                "arrival_time": r["arrival_time"],
                "departure_time": r["departure_time"],
                "stop_id": f"{tis}{r['stop_id']}",
                "timepoint": "1" if r["arrival_time"] and r["departure_time"] else "0",
                "shape_dist_traveled": "",
            }
            for r in tisseo.ref_stop_times[tid]
        ]
        headsign = trip.get("trip_headsign", "")
        if kind == "in":
            last = rows[-1]
            arrival = parse_hhmm(last["arrival_time"] or last["departure_time"])
            leave = max(parse_hhmm(last["departure_time"] or last["arrival_time"]), arrival + dwell)
            last["arrival_time"], last["departure_time"] = fmt_time(arrival), fmt_time(leave)
            for k in range(1, len(idx0)):
                st = stations[idx0[k]]
                rows.append({"trip_id": rows[0]["trip_id"], "arrival_time": fmt_time(leave + arr0[k]),
                             "departure_time": fmt_time(leave + dep0[k]),
                             "stop_id": platform_id[(line["id"], st.order)], "timepoint": "0", "shape_dist_traveled": ""})
            headsign = stations[idx0[-1]].name
        elif kind == "out":
            first = rows[0]
            leave = parse_hhmm(first["departure_time"] or first["arrival_time"])
            start = leave - dwell - arr1[-1]
            if start < 0:
                kind = ""
            else:
                first["arrival_time"], first["departure_time"] = fmt_time(leave - dwell), fmt_time(leave)
                before = [
                    {"trip_id": rows[0]["trip_id"], "arrival_time": fmt_time(start + arr1[k]),
                     "departure_time": fmt_time(start + dep1[k]),
                     "stop_id": platform_id[(line["id"], stations[idx1[k]].order)], "timepoint": "0",
                     "shape_dist_traveled": ""}
                    for k in range(len(idx1) - 1)
                ]
                rows = before + rows
        for seq, row in enumerate(rows, start=1):
            row["stop_sequence"] = str(seq)
        tables["trips.txt"].append(
            {
                "route_id": route_id,
                "service_id": service_id,
                "trip_id": rows[0]["trip_id"],
                "trip_headsign": headsign,
                "direction_id": trip.get("direction_id", ""),
                "shape_id": shape_for(trip, kind),
            }
        )
        tables["stop_times.txt"] += rows
        if kind:
            counts[f"prolongées {'vers' if kind == 'in' else 'depuis'} {stations[-1].name}"] += 1
        else:
            counts["non prolongées"] += 1
        if service_id == f"{tis}{trip['service_id']}":
            used_original_services.add(trip["service_id"])

    # Calendars: Tisséo's own services, plus explicit dates for the split ones.
    calendar, calendar_dates = tisseo.calendar_rows(used_original_services)
    for row in calendar:
        tables["calendar.txt"].append(
            {"service_id": f"{tis}{row['service_id']}", **{d: row.get(d, "0") for d in GTFS_WEEKDAYS},
             "start_date": row["start_date"], "end_date": row["end_date"]}
        )
    for row in calendar_dates:
        tables["calendar_dates.txt"].append(
            {"service_id": f"{tis}{row['service_id']}", "date": row["date"], "exception_type": row["exception_type"]}
        )
    for (_, dates), service_id in split_services.items():
        for day in dates:
            tables["calendar_dates.txt"].append({"service_id": service_id, "date": gtfs_date(day), "exception_type": "1"})

    # Achieved headway on the extension, on the busiest set of days, for the report.
    main_sig = max(sig_dates, key=lambda s: len(sig_dates[s]))
    windows = params["profils"][profile_by_sig[main_sig]]
    arrivals = sorted(inbound[t] for t in selected_by_sig[main_sig] if t in inbound)
    gaps: dict[str, list[int]] = defaultdict(list)
    for a, b in zip(arrivals, arrivals[1:]):
        if b - a <= RUN_GAP_S:
            gaps[period_at(windows, a)].append(b - a)
    return {
        "exclude_routes": [f"tisseo:{rid}" for rid in sorted(tisseo.ref_routes)],
        "copied_trips": len({t["trip_id"] for t, _, _ in variants}),
        "counts": dict(counts),
        "split_services": len(split_services),
        "main_days": f"{len(sig_dates[main_sig])} jour(s), profil {profile_by_sig[main_sig]}",
        "achieved": {p: statistics.mean(v) for p, v in gaps.items()},
    }


# --------------------------------------------------------------------------- TER halts


class SncfGtfs(TisseoGtfs):
    """The SNCF GTFS already filtered to the zone (scripts/filter_gtfs_sncf.py): small, read at once."""

    def load(self, ref_line: str = "") -> None:  # noqa: ARG002 (same signature as the Tisséo reader)
        self.stops = {s["stop_id"]: s for s in self.rows("stops.txt")}
        self.routes = {r["route_id"]: r for r in self.rows("routes.txt")}
        self.trips = {t["trip_id"]: t for t in self.rows("trips.txt")}
        self.stop_times: dict[str, list[dict]] = defaultdict(list)
        for row in self.rows("stop_times.txt"):
            self.stop_times[row["trip_id"]].append(row)
        for rows in self.stop_times.values():
            rows.sort(key=lambda r: int(r["stop_sequence"]))
        self.served = {r["stop_id"] for rows in self.stop_times.values() for r in rows}
        self.services_by_date = self._services_by_date()

    def name_of(self, stop_id: str) -> str:
        return self.stops.get(stop_id, {}).get("stop_name", "")

    def stops_named(self, name: str) -> set[str]:
        """Served stops whose own name, or whose parent station's name, is this one.

        Accents, case and punctuation are ignored. Without an exact match, a name that contains it
        is accepted ("Lalande-Église" for "Toulouse Lalande Église"), but only if it is one name.
        """
        target = normalize_name(name)
        names = {}
        for sid in self.served:
            stop = self.stops.get(sid, {})
            for candidate in (stop.get("stop_name", ""), self.name_of(stop.get("parent_station", ""))):
                if candidate:
                    names.setdefault(normalize_name(candidate), set()).add(sid)
        if target in names:
            return names[target]
        close = {k: v for k, v in names.items() if target and target in k}
        if len(close) > 1:
            raise BuildError(f"gare « {name} » ambiguë dans le GTFS SNCF {self.path.name} : "
                             + ", ".join(sorted({self.name_of(next(iter(v))) for v in close.values()})))
        return next(iter(close.values()), set())

    def position(self, stop_ids: set[str]) -> tuple[float, float]:
        pts = [(float(self.stops[s]["stop_lat"]), float(self.stops[s]["stop_lon"])) for s in stop_ids]
        return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def resolve_halte_positions(haltes, osm_positions, lines, tisseo: TisseoGtfs | None) -> None:
    """Position of each TER halt: CSV, OSM extraction, then a neighbouring station (future line or Tisséo).

    A halt left without a position is not added (warning in the report): it never blocks the feed.
    """
    future = {normalize_name(st.name): st for line in lines for st in line["stations"] if st.lat is not None}
    for st in haltes:
        if st.lat is not None:
            st.origin = f"CSV : {st.precision}"
            continue
        osm = osm_positions.get((TER_LINE_ID, st.order))
        if osm:
            st.lat, st.lon = osm["lat"], osm["lon"]
            st.origin = f"OpenStreetMap ({osm['source']}) : {osm['precision']}"
            continue
        if not st.anchor:
            continue
        name, _ = st.anchor
        near = future.get(normalize_name(name))
        if near is not None:
            st.lat, st.lon = near.lat, near.lon
            st.origin = (f"station future voisine « {near.name} » (ligne {near.line_id}) : approximative "
                         "(la halte est annoncée à côté)")
        elif tisseo is not None and (stop := tisseo.find_stop(name)):
            st.lat, st.lon = float(stop["stop_lat"]), float(stop["stop_lon"])
            st.origin = (f"GTFS Tisséo, arrêt {stop['stop_id']} « {stop['stop_name']} » : approximative "
                         "(la halte est annoncée à côté)")


def build_ter_haltes(params, haltes, sncf: SncfGtfs | None, tables, agency_id, notes) -> dict:
    """Add the TER halts to copies of the SNCF lines that run past them.

    For each halt: the trains that call at its two neighbouring stations one after the other are
    the ones that will stop at the halt (hypothesis). Every trip of their SNCF routes is copied in
    this feed (same stops and times); the halt is inserted in the matching trips, at a time split
    in proportion to the distance, followed by a dwell that delays the rest of the trip. Scenario
    2028 then excludes the original SNCF routes (scenario-2028.json).
    Loud failures: a neighbour missing from the SNCF GTFS, or no train calling at both.
    Skipped with a warning: a halt without a position, too far from its neighbours, or already
    served in the SNCF GTFS (it may open before 2028: never duplicated).
    """
    cfg = params.get("haltes_ter") or {}
    result = {"haltes": [], "excluded": [], "copied_trips": 0}
    if not haltes:
        return result
    if sncf is None:
        notes.append("Sans GTFS SNCF (--sncf-gtfs), haltes TER non ajoutées : "
                     + ", ".join(h.name for h in haltes) + ".")
        result["haltes"] = [{"name": h.name, "status": "non ajoutée (pas de GTFS SNCF)"} for h in haltes]
        return result
    prefix = params["flux"]["prefixe_id"]
    tag = f"{prefix}SNCF_"
    dwell = int(cfg.get("temps_arret_s", 60))
    radius = float(cfg.get("rayon_deja_desservie_m", 150))
    inserts: dict[str, list[tuple[int, Station, float]]] = defaultdict(list)  # trip -> (index, halt, share)
    added = []
    for h in haltes:
        a_name, b_name = h.between
        a_ids, b_ids = sncf.stops_named(a_name), sncf.stops_named(b_name)
        for name, ids in ((a_name, a_ids), (b_name, b_ids)):
            if not ids:
                raise BuildError(f"halte TER « {h.name} » : la gare voisine « {name} » n'est desservie par aucun "
                                 f"train du GTFS SNCF {sncf.path.name}. Corrigez « entre » dans parametres.yaml.")
        info = {"name": h.name, "between": f"{a_name} – {b_name}", "announced": h.announced, "origin": h.origin}
        result["haltes"].append(info)
        same = sorted({sncf.name_of(s) for s in sncf.served if normalize_name(sncf.name_of(s)) == normalize_name(h.name)})
        near = []
        if h.lat is not None:
            near = sorted({sncf.name_of(s) for s in sncf.served - a_ids - b_ids
                           if haversine_m(h.lat, h.lon, float(sncf.stops[s]["stop_lat"]),
                                          float(sncf.stops[s]["stop_lon"])) <= radius})
        if same or near:
            info["status"] = f"déjà desservie dans le GTFS SNCF actuel ({', '.join(same + near)}) : non ajoutée"
            notes.append(f"Halte TER {h.name} déjà desservie dans le GTFS SNCF ({', '.join(same + near)}) : "
                         "non dupliquée dans le scénario 2028.")
            continue
        if h.lat is None:
            info["status"] = "sans position vérifiable : non ajoutée"
            notes.append(f"Halte TER {h.name} sans position vérifiable (CSV, OSM, station voisine) : non ajoutée.")
            continue
        pa, pb = sncf.position(a_ids), sncf.position(b_ids)
        d_a, d_b, d_ab = haversine_m(*pa, h.lat, h.lon), haversine_m(h.lat, h.lon, *pb), haversine_m(*pa, *pb)
        info["distances"] = (d_a, d_b)
        if d_a + d_b > HALT_DETOUR_RATIO * d_ab + HALT_DETOUR_SLACK_M:
            info["status"] = f"position hors de la ligne ({d_a:.0f} m + {d_b:.0f} m pour {d_ab:.0f} m) : non ajoutée"
            notes.append(f"Halte TER {h.name} : position à {d_a:.0f} m de {a_name} et {d_b:.0f} m de {b_name}, "
                         f"qui sont à {d_ab:.0f} m l'une de l'autre : position douteuse, halte non ajoutée.")
            continue
        found = 0
        for tid, rows in sncf.stop_times.items():
            for i in range(len(rows) - 1):
                s, t = rows[i]["stop_id"], rows[i + 1]["stop_id"]
                if s in a_ids and t in b_ids:
                    inserts[tid].append((i, h, d_a / (d_a + d_b)))
                    found += 1
                elif s in b_ids and t in a_ids:
                    inserts[tid].append((i, h, d_b / (d_a + d_b)))
                    found += 1
        if not found:
            raise BuildError(f"halte TER « {h.name} » : aucun train du GTFS SNCF ne dessert successivement "
                             f"{a_name} et {b_name}. Rien n'est recopié ni exclu au hasard : corrigez « entre ».")
        info["status"] = "ajoutée"
        added.append(h)
    if not added:
        return result

    routes = sorted({sncf.trips[t]["route_id"] for t in inserts})
    copied = [t for t in sncf.trips.values() if t["route_id"] in routes and t["trip_id"] in sncf.stop_times]

    # Routes, stops, the halt stops
    for rid in routes:
        r = sncf.routes.get(rid, {})
        tables["routes.txt"].append({
            "route_id": f"{tag}{rid}", "agency_id": agency_id,
            "route_short_name": r.get("route_short_name", ""), "route_long_name": r.get("route_long_name", ""),
            "route_desc": "Ligne SNCF recopiée du GTFS SNCF (ODbL), avec halte(s) TER prévisionnelle(s) ajoutée(s)",
            "route_type": r.get("route_type", "2") or "2",
            "route_color": (r.get("route_color") or "").upper(), "route_text_color": (r.get("route_text_color") or "").upper(),
        })
        result["excluded"].append({"route": f"sncf:{rid}", "nom_court": r.get("route_short_name", ""),
                                   "nom_long": r.get("route_long_name", ""),
                                   "remplacee_par": "copie avec halte(s) " + ", ".join(h.name for h in added)})
    used = {r["stop_id"] for t in copied for r in sncf.stop_times[t["trip_id"]]}
    parents = {sncf.stops[s].get("parent_station") for s in used if s in sncf.stops} - {"", None}
    for sid in sorted(used | {p for p in parents if p in sncf.stops}):
        stop = sncf.stops[sid]
        parent = stop.get("parent_station", "")
        tables["stops.txt"].append({
            "stop_id": f"{tag}{sid}", "stop_name": stop["stop_name"],
            "stop_lat": f"{float(stop['stop_lat']):.6f}", "stop_lon": f"{float(stop['stop_lon']):.6f}",
            "location_type": (stop.get("location_type") or "0").strip() or "0",
            "parent_station": f"{tag}{parent}" if parent in sncf.stops else "",
            "stop_desc": "Arrêt recopié du GTFS SNCF (ODbL)",
        })
    halt_stop = {}
    for h in added:
        parent_id, platform = f"{prefix}STA_{slug(h.name)}", f"{prefix}TER_{slug(h.name)}"
        halt_stop[h.name] = platform
        for sid, loc, par in ((parent_id, "1", ""), (platform, "0", parent_id)):
            tables["stops.txt"].append({
                "stop_id": sid, "stop_name": h.name, "stop_lat": f"{h.lat:.6f}", "stop_lon": f"{h.lon:.6f}",
                "location_type": loc, "parent_station": par,
                "stop_desc": f"Halte TER prévisionnelle (simulation Toulouse Demain). Position : {h.origin}"[:500],
            })

    # Trips and stop times: the halt after row i, the rest of the trip delayed by the dwell.
    shapes = {t.get("shape_id", "") for t in copied} - {""}
    per_halt_trips: dict[str, set[str]] = defaultdict(set)
    skipped = Counter()
    for trip in copied:
        tid = trip["trip_id"]
        rows = sncf.stop_times[tid]
        at = {i: (h, share) for i, h, share in inserts.get(tid, [])}
        out, shift = [], 0
        for i, row in enumerate(rows):
            arr = parse_hhmm(row["arrival_time"] or row["departure_time"]) + shift
            dep = parse_hhmm(row["departure_time"] or row["arrival_time"]) + shift
            out.append({"trip_id": f"{tag}{tid}", "arrival_time": fmt_time(arr), "departure_time": fmt_time(dep),
                        "stop_id": f"{tag}{row['stop_id']}", "pickup_type": row.get("pickup_type", ""),
                        "drop_off_type": row.get("drop_off_type", "")})
            if i in at:
                h, share = at[i]
                nxt = parse_hhmm(rows[i + 1]["arrival_time"] or rows[i + 1]["departure_time"]) + shift
                halt_arr = dep + int(round((nxt - dep) * share))
                if not dep < halt_arr < nxt:
                    skipped[h.name] += 1  # same minute at both neighbours: no room for a stop
                    continue
                out.append({"trip_id": f"{tag}{tid}", "arrival_time": fmt_time(halt_arr),
                            "departure_time": fmt_time(halt_arr + dwell), "stop_id": halt_stop[h.name],
                            "pickup_type": "0", "drop_off_type": "0"})
                shift += dwell
                per_halt_trips[h.name].add(tid)
        for seq, row in enumerate(out, start=1):
            row["stop_sequence"] = str(seq)
        tables["stop_times.txt"] += out
        tables["trips.txt"].append({
            "route_id": f"{tag}{trip['route_id']}", "service_id": f"{tag}{trip['service_id']}",
            "trip_id": f"{tag}{tid}", "trip_headsign": trip.get("trip_headsign", ""),
            "direction_id": trip.get("direction_id", ""),
            "shape_id": f"{tag}{trip['shape_id']}" if trip.get("shape_id") in shapes else "",
        })
    services = {t["service_id"] for t in copied}
    calendar, calendar_dates = sncf.calendar_rows(services)
    for row in calendar:
        tables["calendar.txt"].append({"service_id": f"{tag}{row['service_id']}", **{d: row.get(d, "0") for d in GTFS_WEEKDAYS},
                                       "start_date": row["start_date"], "end_date": row["end_date"]})
    for row in calendar_dates:
        tables["calendar_dates.txt"].append({"service_id": f"{tag}{row['service_id']}", "date": row["date"],
                                             "exception_type": row["exception_type"]})
    for sid, points in sncf.shapes_for(shapes).items():
        cum, prev = 0.0, None
        for seq, p in enumerate(points, start=1):
            cum += haversine_m(*prev, *p) if prev else 0.0
            tables["shapes.txt"].append({"shape_id": f"{tag}{sid}", "shape_pt_lat": f"{p[0]:.6f}",
                                         "shape_pt_lon": f"{p[1]:.6f}", "shape_pt_sequence": str(seq),
                                         "shape_dist_traveled": f"{cum:.1f}"})
            prev = p

    # Trains per day at each halt (weekdays: median), to compare with the announced figure.
    trips_by_service: dict[str, list[str]] = defaultdict(list)
    for trip in copied:
        trips_by_service[trip["service_id"]].append(trip["trip_id"])
    for info in result["haltes"]:
        if info.get("status") != "ajoutée":
            continue
        mine = per_halt_trips[info["name"]]
        counts = [sum(1 for svc in svcs for t in trips_by_service.get(svc, []) if t in mine)
                  for day, svcs in sorted(sncf.services_by_date.items()) if day.weekday() < 5]
        counts = [n for n in counts if n > 0]
        info["trips"] = len(mine)
        info["per_weekday"] = statistics.median(counts) if counts else 0
        info["skipped"] = skipped[info["name"]]
    result["copied_trips"] = len(copied)
    result["dwell"] = dwell
    return result


# --------------------------------------------------------------------------- replaced Tisséo lines


def resolve_replaced_lines(params, lines, tisseo: TisseoGtfs | None, notes: list[str]) -> list[dict]:
    """Tisséo routes listed in lignes_tisseo_remplacees, resolved to their real route_id.

    The name must designate exactly one route of the Tisséo GTFS: otherwise the build stops, so
    that a renamed or duplicated line is never left running (or wrongly removed) in silence.
    Without the Tisséo GTFS nothing can be resolved: nothing is excluded, and the report says so.
    """
    items = params.get("lignes_tisseo_remplacees") or []
    by_id = {line["id"]: line for line in lines}
    if tisseo is None:
        if items:
            notes.append("Sans GTFS Tisséo, lignes Tisséo remplacées non résolues, donc non exclues : "
                         + ", ".join(str(i["ligne"]) for i in items) + ".")
        return []
    out = []
    for item in items:
        name = str(item["ligne"]).strip()
        matches = tisseo.routes_named(name)
        if len(matches) != 1:
            if matches:
                found = "; ".join(f"{r['route_id']} « {r.get('route_long_name', '')} »" for r in matches)
                problem = f"désigne {len(matches)} lignes ({found})"
            else:
                close = sorted({r.get("route_short_name", "").strip() for r in tisseo.routes
                                if normalize_name(name) in normalize_name(r.get("route_short_name", ""))
                                or normalize_name(name) in normalize_name(r.get("route_long_name", ""))} - {""})
                problem = "ne correspond à aucune ligne" + (f" (noms voisins : {', '.join(close)})" if close else "")
            raise BuildError(
                f"lignes_tisseo_remplacees : le route_short_name « {name} » {problem} dans le GTFS Tisséo "
                f"{tisseo.path.name}. Corrigez data/futur/parametres.yaml : aucune ligne n'est exclue au hasard."
            )
        route = matches[0]
        out.append({
            "route": f"tisseo:{route['route_id']}",
            "nom_court": route.get("route_short_name", "").strip(),
            "nom_long": route.get("route_long_name", "").strip(),
            "remplacee_par": by_id[item["remplacee_par"]]["nom_court"],
        })
    return out


# --------------------------------------------------------------------------- feed assembly


def build_feed(params, lines, tisseo: TisseoGtfs | None, start: dt.date, osm_used: bool,
               haltes=(), sncf: SncfGtfs | None = None):
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

    # Line B through trains (Cyprien's decision, 14/10/2026) need the Tisséo GTFS and its line B.
    direct = None
    for line in lines:
        if line.get("prolongement_tisseo") and tisseo is not None:
            if tisseo.ref_trip_rows and line["prolongement_tisseo"]["ligne"].upper() == str(
                params.get("calibration_tisseo", {}).get("ligne_reference", "B")
            ).upper():
                direct = line
            else:
                notes.append(f"Ligne {line['nom_court']} du GTFS Tisséo introuvable : prolongement simulé en navette.")
    replaced = resolve_replaced_lines(params, lines, tisseo, notes)
    cal_start, cal_end, assigned = build_calendar(params, tisseo, start)

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

    def own_stations(line):
        """Stations served by stops of this feed (the junction of the B extension is a copied Tisséo stop)."""
        if line is direct:
            junction = normalize_name(line["prolongement_tisseo"]["raccordement"])
            return [st for st in line["stations"] if normalize_name(st.name) != junction]
        return line["stations"]

    # Stops: one parent station per name (shared by lines), one platform per line.
    parents: dict[str, dict] = {}
    for line in lines:
        for st in own_stations(line):
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
        for st in own_stations(line):
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

    direct_info = None
    for line in lines:
        route_id = f"{prefix}{line['id']}"
        if line is not direct:
            tables["routes.txt"].append(
                {
                    "route_id": route_id,
                    "agency_id": agency_id,
                    "route_short_name": line["nom_court"],
                    "route_long_name": line["nom_long"],
                    "route_desc": "Ligne en projet : horaires simulés, voir les hypothèses du projet Toulouse Demain",
                    "route_type": str(route_type(line)),
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
            if line is direct:
                continue
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
                    headway = line["intervalle_pointe_s"] * coefficients[period_at(windows, t)]
                    t += max(60, int(round(headway)))

        if line is direct:
            direct_info = build_b_direct(params, line, tisseo, tables, platform_id, coefficients, assigned, agency_id)

    # TER halts (copies of the SNCF lines that run past them)
    ter = build_ter_haltes(params, haltes, sncf, tables, agency_id, notes)

    # Calendar
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

    # Tisséo routes excluded from scenario 2028 (scenario-2028.json): line B when it is copied, then the list.
    excluded = []
    if direct_info:
        excluded += [{"route": r, "nom_court": direct["prolongement_tisseo"]["ligne"], "nom_long": "",
                      "remplacee_par": f"{direct['nom_court']} (recopiée et prolongée)"}
                     for r in direct_info["exclude_routes"]]
    for item in replaced + ter["excluded"]:
        if item["route"] in {e["route"] for e in excluded}:
            raise BuildError(f"lignes_tisseo_remplacees : {item['route']} ({item['nom_court']}) est déjà exclue")
        excluded.append(item)

    context = {
        "notes": notes,
        "coefficients": coefficients,
        "coeff_origin": coeff_origin,
        "amplitude": amplitude,
        "calibration": calib,
        "calendar": (cal_start, cal_end, exceptions),
        "dwell": dwell,
        "direct": direct_info,
        "excluded": excluded,
        "ter": ter,
    }
    return tables, context


def check_collisions(tables, tisseo: TisseoGtfs) -> None:
    pairs = {
        "agency": ("agency.txt", "agency_id"),
        "stops": ("stops.txt", "stop_id"),
        "routes": ("routes.txt", "route_id"),
        "trips": ("trips.txt", "trip_id"),
        "services": ("calendar.txt", "service_id"),
        "service_dates": ("calendar_dates.txt", "service_id"),
        "shapes": ("shapes.txt", "shape_id"),
    }
    for kind, (table, column) in pairs.items():
        ours = {row[column] for row in tables[table]}
        clash = ours & tisseo.ids["services" if kind == "service_dates" else kind]
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
            columns = list(dict.fromkeys(k for row in rows for k in row))  # union, in order of appearance
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
    direct = context.get("direct")
    if direct:
        out.append("## Ligne B en rames directes (recopiée du GTFS Tisséo et prolongée)")
        out.append("")
        out.append(f"- Courses Tisséo recopiées : {direct['copied_trips']}")
        for label, n in sorted(direct["counts"].items()):
            out.append(f"- Courses {label} : {n}")
        out.append(f"- Services Tisséo dédoublés (choix différent selon les jours) : {direct['split_services']}")
        out.append(f"- Scénario 2028 : exclut {', '.join(direct['exclude_routes'])} (scenario-2028.json)")
        out.append(f"- Intervalle obtenu sur le prolongement, jours les plus fréquents ({direct['main_days']}) :")
        for period, value in sorted(direct["achieved"].items()):
            out.append(f"  - {period} : {fmt_minsec(value)} en moyenne")
        out.append("")
    out.append("## Lignes Tisséo exclues du scénario 2028 (scenario-2028.json)")
    out.append("")
    if context["excluded"]:
        out.append("| Ligne Tisséo | route_id | Nom long | Remplacée par |")
        out.append("| --- | --- | --- | --- |")
        for e in context["excluded"]:
            out.append(f"| {e['nom_court']} | {e['route']} | {e['nom_long'] or '-'} | {e['remplacee_par']} |")
    else:
        out.append("Aucune.")
    out.append("")
    ter = context.get("ter") or {}
    if ter.get("haltes"):
        out.append("## Haltes TER prévisionnelles")
        out.append("")
        out.append(f"Temps d'arrêt en halte : {ter.get('dwell', '-')} s ; courses SNCF recopiées : "
                   f"{ter.get('copied_trips', 0)}.")
        out.append("")
        out.append("| Halte | Entre | Statut | Position | Courses avec arrêt | Trains par jour de semaine (médiane) | Annoncés |")
        out.append("| --- | --- | --- | --- | --- | --- | --- |")
        for h in ter["haltes"]:
            out.append(f"| {h['name']} | {h.get('between', '-')} | {h['status']} | {h.get('origin') or '-'} | "
                       f"{h.get('trips', '-')} | {h.get('per_weekday', '-')} | {h.get('announced') or '-'} |")
            if h.get("skipped"):
                warnings.append(f"Halte TER {h['name']} : {h['skipped']} course(s) sans arrêt possible "
                                "(même minute aux deux gares voisines)")
        out.append("")
    for line in lines:
        out.append(f"## Ligne {line['nom_court']} ({line['id']}, {ROUTE_TYPES[route_type(line)]})")
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
                    warnings.append(f"Ligne {line['id']}, {st.name} : correspondance attendue "
                                    f"({', '.join(c.strip() for c in tisseo_modes)}) mais aucun arrêt Tisséo "
                                    f"à moins de {radius} m")
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
    haltes = load_haltes(params, base)
    resolve_halte_positions(haltes, osm_positions, lines, tisseo)
    sncf = None
    if args.sncf_gtfs:
        sncf = SncfGtfs(Path(args.sncf_gtfs))
        sncf.load()

    start = dt.date.fromisoformat(args.start_date) if args.start_date else dt.date.today()
    osm_used = bool(osm_positions) or bool(osm_traces)
    tables, context = build_feed(params, lines, tisseo, start, osm_used, haltes, sncf)

    output = Path(args.output)
    write_zip(tables, output)
    # Routes of the current network replaced by the futur feed in scenario 2028 (read by the CI).
    excluded = [e["route"] for e in context["excluded"]]
    (output.parent / "scenario-2028.json").write_text(json.dumps({"exclude_routes": excluded}) + "\n", encoding="utf-8")
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
    parser.add_argument("--sncf-gtfs", help="GTFS SNCF filtré à la zone (zip), facultatif : haltes TER")
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
