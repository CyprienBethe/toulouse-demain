"""Shared fixtures for the futur GTFS tests.

All coordinates generated here are SYNTHETIC test values on an artificial straight line.
They are not station positions and must never be copied into data/futur/.
"""

from __future__ import annotations

import csv
import io
import math
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_gtfs_futur as bgf  # noqa: E402

PARAMS = REPO_ROOT / "data" / "futur" / "parametres.yaml"
ORIGIN = (43.60, 1.30)  # synthetic origin of the artificial line


def offset(point, east_m: float, north_m: float):
    lat, lon = point
    return (
        lat + north_m / 111_320.0,
        lon + east_m / (111_320.0 * math.cos(math.radians(lat))),
    )


def real_lines():
    params = bgf.load_params(PARAMS)
    return {l["id"]: bgf.load_stations(REPO_ROOT / l["stations"], l["id"]) for l in params["lignes"]}


def synthetic_positions():
    """{(line, order): (lat, lon)}: line C eastwards with 1.2-1.5 km hops, B_EXT southwards to Labège Madron,
    AEROPORT northwards from Blagnac (2.2 km)."""
    lines = real_lines()
    pos, east = {}, 0.0
    for st in lines["C"]:
        pos[("C", st.order)] = offset(ORIGIN, east, 0)
        east += 1200 + 150 * (st.order % 3)
    madron = next(s for s in lines["C"] if s.name == "Labège Madron")
    end = pos[("C", madron.order)]
    n = len(lines["B_EXT"])
    for st in lines["B_EXT"]:
        pos[("B_EXT", st.order)] = offset(end, 0, -1350 * (n - st.order))
    blagnac = next(s for s in lines["C"] if s.name == "Blagnac")
    start = pos[("C", blagnac.order)]
    for st in lines["AEROPORT"]:
        pos[("AEROPORT", st.order)] = offset(start, 0, 2200 * (st.order - 1))
    return pos


def write_osm_positions(directory: Path, positions: dict, skip=()):
    directory.mkdir(parents=True, exist_ok=True)
    lines = real_lines()
    with open(directory / "stations_osm.csv", "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["ligne", "ordre", "nom_officiel", "lat", "lon", "precision", "source"])
        writer.writeheader()
        for (line_id, order), (lat, lon) in positions.items():
            name = lines[line_id][order - 1].name
            if name in skip:
                continue
            writer.writerow(
                {
                    "ligne": line_id,
                    "ordre": order,
                    "nom_officiel": name,
                    "lat": f"{lat:.6f}",
                    "lon": f"{lon:.6f}",
                    "precision": "station exacte (TEST : position synthétique)",
                    "source": "test",
                }
            )
    return directory


def gtfs_tables(path: Path) -> dict[str, list[dict]]:
    with zipfile.ZipFile(path) as zf:
        return {
            name: list(csv.DictReader(io.TextIOWrapper(zf.open(name), encoding="utf-8-sig")))
            for name in zf.namelist()
        }


def active_services(tables, day: str) -> set[str]:
    """Services of a GTFS (as read by gtfs_tables) running on day 'YYYYMMDD'."""
    import datetime as _dt

    weekday = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][
        _dt.datetime.strptime(day, "%Y%m%d").weekday()]
    active = {c["service_id"] for c in tables.get("calendar.txt", [])
              if c["start_date"] <= day <= c["end_date"] and c[weekday] == "1"}
    for d in tables.get("calendar_dates.txt", []):
        if d["date"] == day:
            (active.add if d["exception_type"] == "1" else active.discard)(d["service_id"])
    return active


def departures(windows, first, last):
    """Departure times following [(start_s, end_s, headway_s)] windows."""
    out, t = [], first
    while t <= last:
        out.append(t)
        headway = next(h for s, e, h in windows if s <= t < e)
        t += headway
    return out


def make_tisseo_zip(path: Path, positions: dict, extra_stops=(), night_next_day=False, extra_service_date=None,
                    aero_routes=("AERO",)):
    """Synthetic Tisséo-like GTFS: metro B Borderouge - Université - Ramonville with known headways,
    shapes, metro A, a bus stop, and the airport shuttle route (short name "AERO", no trip needed).

    night_next_day: adds Thursday/Friday/Saturday night trips (00:20 to 02:20) coded on the next
    date's service with times below 24:00, as some feeds do.
    extra_service_date: "YYYYMMDD" with extra peak trains (07:01 to 08:59, every 2 min) on that day only.
    aero_routes: route_short_name of each airport shuttle route to write (several, or none, to test
    the lignes_tisseo_remplacees checks).
    """
    lines = real_lines()
    by_name = {st.name: positions[(lid, st.order)] for lid, sts in lines.items() for st in sts}
    ramonville = by_name["Ramonville"]
    la_vache = offset(by_name["La Vache Gare - Le Grand marché"], 80, 0)
    verdier = offset(by_name["François Verdier"], 0, 60)
    marengo = offset(by_name["Matabiau Gare"], -120, 0)
    borderouge = offset(ORIGIN, 0, 8000)
    middle = ((ramonville[0] + borderouge[0]) / 2, (ramonville[1] + borderouge[1]) / 2)
    stops = [
        ("SA_RAM", "Ramonville", ramonville, "1", ""),
        ("SP_RAM", "Ramonville", ramonville, "0", "SA_RAM"),
        ("SA_LVA", "La Vache", la_vache, "1", ""),
        ("SP_LVA", "La Vache", la_vache, "0", "SA_LVA"),
        ("SA_FV", "François Verdier", verdier, "1", ""),
        ("SP_FV", "François Verdier", verdier, "0", "SA_FV"),
        ("SA_MAR", "Marengo-SNCF", marengo, "1", ""),
        ("SP_MAR", "Marengo-SNCF", marengo, "0", "SA_MAR"),
        ("BUS_MAR", "Marengo SNCF", offset(marengo, 500, 0), "0", ""),
        ("SA_BOR", "Borderouge", borderouge, "1", ""),
        ("SP_BOR", "Borderouge", borderouge, "0", "SA_BOR"),
        ("SP_UPS", "Université Paul Sabatier", middle, "0", ""),
        *extra_stops,
    ]
    h = 3600
    week = [(0, 7 * h, 240), (7 * h, 9 * h, 120), (9 * h, 16.5 * h, 240), (16.5 * h, 19 * h, 120),
            (19 * h, 20.5 * h, 240), (20.5 * h, 30 * h, 360)]
    sat = [(0, 20.5 * h, 240), (20.5 * h, 30 * h, 360)]
    sun = [(0, 30 * h, 360)]
    trips, stop_times = [], []
    plans = [("WEEK", week, int(5.25 * h), 24 * h), ("SAT", sat, int(5.25 * h), 24 * h),
             ("SUN", sun, int(5.25 * h), 24 * h)]
    if night_next_day:
        plans.append(("NIGHT", [(0, 4 * h, 3600)], int(h / 3), int(2.4 * h)))
    if extra_service_date:
        plans.append(("EXTRA", [(0, 30 * h, 120)], 7 * h + 60, 9 * h - 60))
    for service, windows, first, last in plans:
        for direction, (a, b) in enumerate((("SP_RAM", "SP_BOR"), ("SP_BOR", "SP_RAM"))):
            for k, t in enumerate(departures(windows, first, last)):
                trip_id = f"B_{service}_{direction}_{k}"
                trips.append({"route_id": "LB", "service_id": service, "trip_id": trip_id, "direction_id": direction,
                              "shape_id": f"SH_B{direction}"})
                for seq, (stop, dt_) in enumerate(((a, 0), ("SP_UPS", 700), (b, 1500)), start=1):
                    stamp = bgf.fmt_time(int(t + dt_))
                    stop_times.append(
                        {"trip_id": trip_id, "arrival_time": stamp, "departure_time": stamp, "stop_id": stop,
                         "stop_sequence": seq}
                    )
    trips.append({"route_id": "LA", "service_id": "WEEK", "trip_id": "A_1", "direction_id": 0, "shape_id": ""})
    stop_times += [
        {"trip_id": "A_1", "arrival_time": "08:00:00", "departure_time": "08:00:00", "stop_id": "SP_MAR", "stop_sequence": 1},
        {"trip_id": "A_1", "arrival_time": "08:05:00", "departure_time": "08:05:00", "stop_id": "SP_BOR", "stop_sequence": 2},
    ]
    files = {
        "agency.txt": [{"agency_id": "TISSEO", "agency_name": "Tisséo (test)", "agency_url": "https://example.org",
                        "agency_timezone": "Europe/Paris"}],
        "stops.txt": [
            {"stop_id": sid, "stop_name": name, "stop_lat": f"{p[0]:.6f}", "stop_lon": f"{p[1]:.6f}",
             "location_type": lt, "parent_station": parent}
            for sid, name, p, lt, parent in stops
        ],
        "routes.txt": [
            {"route_id": "LA", "agency_id": "TISSEO", "route_short_name": "A", "route_type": 1},
            {"route_id": "LB", "agency_id": "TISSEO", "route_short_name": "B", "route_type": 1},
            {"route_id": "BUS", "agency_id": "TISSEO", "route_short_name": "14", "route_type": 3},
            *({"route_id": f"line:{99 + k}", "agency_id": "TISSEO", "route_short_name": name, "route_type": 3}
              for k, name in enumerate(aero_routes)),
        ],
        "trips.txt": trips,
        "stop_times.txt": stop_times,
        "calendar.txt": [
            {"service_id": s, "monday": m[0], "tuesday": m[1], "wednesday": m[2], "thursday": m[3], "friday": m[4],
             "saturday": m[5], "sunday": m[6], "start_date": "20261012", "end_date": "20261115"}
            for s, m in (("WEEK", "1111100"), ("SAT", "0000010"), ("SUN", "0000001"), ("NIGHT", "0000111"))
        ],
        # 11 November (Wednesday, public holiday): Sunday service.
        "calendar_dates.txt": [
            {"service_id": "WEEK", "date": "20261111", "exception_type": 2},
            {"service_id": "SUN", "date": "20261111", "exception_type": 1},
        ] + ([{"service_id": "EXTRA", "date": extra_service_date, "exception_type": 1}] if extra_service_date else []),
        "shapes.txt": [
            {"shape_id": f"SH_B{d}", "shape_pt_lat": f"{p[0]:.6f}", "shape_pt_lon": f"{p[1]:.6f}", "shape_pt_sequence": i}
            for d, pts in ((0, (ramonville, middle, borderouge)), (1, (borderouge, middle, ramonville)))
            for i, p in enumerate(pts, start=1)
        ],
    }
    with zipfile.ZipFile(path, "w") as zf:
        for name, rows in files.items():
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            zf.writestr(name, buf.getvalue())
    return path


def sncf_positions(positions):
    """Synthetic SNCF stations around the anchors of the two TER halts (La Vache, Labège - Gare)."""
    lines = real_lines()
    by_name = {st.name: positions[(lid, st.order)] for lid, sts in lines.items() for st in sts}
    la_vache = offset(by_name["La Vache Gare - Le Grand marché"], 80, 0)  # the Tisséo stop of make_tisseo_zip
    cadene = by_name["Labège - Gare"]
    return {
        "Montauban": offset(la_vache, -1500, 15_000),
        "Lalande-Église": offset(la_vache, -200, 2000),
        "Toulouse Matabiau": offset(la_vache, 300, -2500),
        "Labège Innopole": offset(cadene, -800, 300),
        "Labège Village": offset(cadene, 900, 200),
        "Escalquens": offset(cadene, 3000, -500),
        "Colomiers": offset(ORIGIN, -500, 300),
    }


def make_sncf_zip(path: Path, positions: dict, served_halt=None, drop_stations=(), express_only=False):
    """Synthetic filtered SNCF GTFS (calendar_dates only, as the SNCF feed), StopArea + StopPoint.

    NORD: Montauban - Lalande-Église - Toulouse Matabiau (and back) every hour 06:00-21:00, plus
    one express train Montauban - Toulouse Matabiau at 07:30. SUD: Toulouse Matabiau - Labège
    Innopole - Labège Village - Escalquens (and back), every hour. OUEST: Colomiers - Matabiau.
    served_halt: name of an extra stop served by the NORD trains between Lalande and Matabiau
    (the halt already opened). drop_stations: stations left out. express_only: NORD trains end at
    Lalande-Église, so that no train calls at Lalande-Église then Matabiau.
    """
    pos = sncf_positions(positions)
    if served_halt:
        pos[served_halt] = offset(pos["Lalande-Église"], 400, -3000)
    names = [n for n in pos if n not in drop_stations]
    sid = {n: f"StopPoint:OCETrain TER-{87_000_000 + k}" for k, n in enumerate(names)}
    stops = []
    for n in names:
        stops.append({"stop_id": f"StopArea:OCE{87_000_000 + names.index(n)}", "stop_name": n,
                      "stop_lat": f"{pos[n][0]:.6f}", "stop_lon": f"{pos[n][1]:.6f}", "location_type": "1",
                      "parent_station": ""})
        stops.append({"stop_id": sid[n], "stop_name": n, "stop_lat": f"{pos[n][0]:.6f}",
                      "stop_lon": f"{pos[n][1]:.6f}", "location_type": "0",
                      "parent_station": f"StopArea:OCE{87_000_000 + names.index(n)}"})
    nord = [("Montauban", 0), ("Lalande-Église", 1500), ("Toulouse Matabiau", 2100)]
    if served_halt:
        nord.insert(2, (served_halt, 1800))
    if express_only:  # NORD trains end at Lalande-Église; only the express goes on to Matabiau
        nord = nord[:2]
    patterns = {
        "NORD": nord,
        "SUD": [("Toulouse Matabiau", 0), ("Labège Innopole", 600), ("Labège Village", 840), ("Escalquens", 1080)],
        "OUEST": [("Colomiers", 0), ("Toulouse Matabiau", 900)],
        "CAR": [("Labège Innopole", 0), ("Labège Village", 420)],  # an SNCF coach (route_type 3)
    }
    patterns = {r: ([n for n, _ in calls if n not in drop_stations], [o for n, o in calls if n not in drop_stations])
                for r, calls in patterns.items()}
    trips, stop_times = [], []
    for route, (seq, offsets) in patterns.items():
        for direction, (order, offs) in enumerate(((seq, offsets), (seq[::-1], [offsets[-1] - o for o in offsets[::-1]]))):
            for hour in range(6, 22):
                tid = f"OCESN{route}{direction}{hour:02d}F"
                trips.append({"route_id": f"FR:Line::{route}:", "service_id": "000001", "trip_id": tid,
                              "trip_headsign": order[-1], "direction_id": direction})
                for k, (n, o) in enumerate(zip(order, offs), start=1):
                    t = bgf.fmt_time(hour * 3600 + o)
                    stop_times.append({"trip_id": tid, "arrival_time": t, "departure_time": t, "stop_id": sid[n],
                                       "stop_sequence": k - 1, "pickup_type": 0, "drop_off_type": 0})
    if "Lalande-Église" not in drop_stations:
        trips.append({"route_id": "FR:Line::NORD:", "service_id": "000001", "trip_id": "OCESNEXPRESS",
                      "trip_headsign": "Toulouse Matabiau", "direction_id": 1})
        for k, (n, t) in enumerate((("Montauban", "07:30:00"), ("Toulouse Matabiau", "07:55:00"))):
            stop_times.append({"trip_id": "OCESNEXPRESS", "arrival_time": t, "departure_time": t, "stop_id": sid[n],
                               "stop_sequence": k, "pickup_type": 0, "drop_off_type": 0})
    files = {
        "agency.txt": [{"agency_id": "1187", "agency_name": "SNCF (test)", "agency_url": "https://example.org",
                        "agency_timezone": "Europe/Paris"}],
        "stops.txt": stops,
        "routes.txt": [{"route_id": f"FR:Line::{r}:", "agency_id": "1187", "route_short_name": short,
                        "route_long_name": f"Ligne {r} (test)", "route_type": 3 if r == "CAR" else 2,
                        "route_color": "0749FF",
                        "route_text_color": "FFFFFF"}
                       for r, short in (("NORD", "K1"), ("SUD", "C3"), ("OUEST", "C6"), ("CAR", "Car"))],
        "trips.txt": trips,
        "stop_times.txt": stop_times,
        # Monday 19 to Friday 23 October 2026.
        "calendar_dates.txt": [{"service_id": "000001", "date": f"202610{d}", "exception_type": 1}
                               for d in range(19, 24)],
    }
    with zipfile.ZipFile(path, "w") as zf:
        for name, rows in files.items():
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            zf.writestr(name, buf.getvalue())
    return path


@pytest.fixture
def positions():
    return synthetic_positions()


@pytest.fixture
def params_copy(tmp_path):
    """Writable copy of the real parameters, with absolute CSV paths."""
    def _make(mutate=None):
        params = yaml.safe_load(PARAMS.read_text(encoding="utf-8"))
        for line in params["lignes"]:
            line["stations"] = str(REPO_ROOT / line["stations"])
        params["haltes_ter"]["stations"] = str(REPO_ROOT / params["haltes_ter"]["stations"])
        if mutate:
            mutate(params)
        path = tmp_path / "parametres.yaml"
        path.write_text(yaml.safe_dump(params, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return path
    return _make
