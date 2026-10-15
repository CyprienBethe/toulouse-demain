"""TER halts of scenario 2028 on a synthetic SNCF GTFS (synthetic positions, see conftest.py)."""

from __future__ import annotations

import csv
import json
import re

import pytest

from conftest import gtfs_tables, make_sncf_zip, make_tisseo_zip, offset, sncf_positions, write_osm_positions
from gtfs_checks import check_feed, seconds

import build_gtfs_futur as bgf

LAUNAGUET, CADENE = "FUT_TER_ROUTE_DE_LAUNAGUET", "FUT_TER_LABEGE_LA_CADENE"


def build(tmp_path, positions, sncf_kwargs=None, tisseo=True, extra_osm=None, expect=0):
    osm_dir = write_osm_positions(tmp_path / "osm", positions)
    if extra_osm:  # TER rows of stations_osm.csv, as written by extract_futur_osm.py
        with open(osm_dir / "stations_osm.csv", "a", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh, lineterminator="\n")
            for order, (name, (lat, lon)) in extra_osm.items():
                writer.writerow(["TER", order, name, f"{lat:.6f}", f"{lon:.6f}", "station exacte (TEST)", "test"])
    sncf = make_sncf_zip(tmp_path / "sncf.zip", positions, **(sncf_kwargs or {}))
    out = tmp_path / "out" / "futur.gtfs.zip"
    args = ["--output", str(out), "--osm-dir", str(osm_dir), "--sncf-gtfs", str(sncf)]
    if tisseo:
        args += ["--tisseo-gtfs", str(make_tisseo_zip(tmp_path / "tisseo.zip", positions))]
    assert bgf.main(args) == expect
    if expect:
        return out, None, None
    report = (out.parent / "futur-rapport.md").read_text(encoding="utf-8")
    return out, gtfs_tables(out), report


def by_trip(tables):
    out = {}
    for st in tables["stop_times.txt"]:
        out.setdefault(st["trip_id"], []).append(st)
    for rows in out.values():
        rows.sort(key=lambda r: int(r["stop_sequence"]))
    return out


@pytest.fixture
def ter(tmp_path, positions):
    return build(tmp_path, positions)


def test_lines_with_a_halt_are_copied_and_excluded(ter):
    out, tables, _ = ter
    assert check_feed(tables) == []
    routes = {r["route_id"]: r for r in tables["routes.txt"]}
    assert {"FUT_SNCF_FR:Line::NORD:", "FUT_SNCF_FR:Line::SUD:"} <= set(routes)
    assert "FUT_SNCF_FR:Line::OUEST:" not in routes  # does not run past a halt
    assert "FUT_SNCF_FR:Line::CAR:" not in routes  # a coach between the two stations: never a halt
    assert routes["FUT_SNCF_FR:Line::SUD:"]["route_short_name"] == "C3"
    excluded = json.loads((out.parent / "scenario-2028.json").read_text())["exclude_routes"]
    assert excluded[-2:] == ["sncf:FR:Line::NORD:", "sncf:FR:Line::SUD:"]
    stops = {s["stop_id"]: s for s in tables["stops.txt"]}
    assert stops[LAUNAGUET]["parent_station"] == "FUT_STA_ROUTE_DE_LAUNAGUET"
    assert "Halte TER prévisionnelle" in stops[CADENE]["stop_desc"]


def test_every_trip_of_a_copied_line_is_kept(ter):
    _, tables, _ = ter
    trips = by_trip(tables)
    nord = [t for t in trips if t.startswith("FUT_SNCF_OCESNNORD")]
    assert len(nord) == 32  # 16 per direction
    assert "FUT_SNCF_OCESNEXPRESS" in trips  # copied too, so that it still runs in 2028
    express = [r["stop_id"] for r in trips["FUT_SNCF_OCESNEXPRESS"]]
    assert LAUNAGUET not in express  # it does not stop at Lalande-Église: no halt (hypothesis)
    assert [r["arrival_time"] for r in trips["FUT_SNCF_OCESNEXPRESS"]] == ["07:30:00", "07:55:00"]


def test_halt_time_in_proportion_to_distance_then_dwell(ter, positions):
    _, tables, _ = ter
    rows = by_trip(tables)["FUT_SNCF_OCESNNORD008F"]  # Montauban 08:00, Lalande 08:25, Matabiau 08:35
    names = [r["stop_id"] for r in rows]
    assert names[2] == LAUNAGUET and len(rows) == 4
    stops = {s["stop_id"]: s for s in tables["stops.txt"]}
    halt = (float(stops[LAUNAGUET]["stop_lat"]), float(stops[LAUNAGUET]["stop_lon"]))
    pos = sncf_positions(positions)
    d_a = bgf.haversine_m(*pos["Lalande-Église"], *halt)
    d_b = bgf.haversine_m(*halt, *pos["Toulouse Matabiau"])
    lalande_dep = seconds(rows[1]["departure_time"])
    assert seconds(rows[2]["arrival_time"]) - lalande_dep == round(600 * d_a / (d_a + d_b))
    assert seconds(rows[2]["departure_time"]) - seconds(rows[2]["arrival_time"]) == 60
    assert rows[3]["arrival_time"] == "08:36:00"  # Matabiau: 08:35 + the 60 s dwell
    assert [r["stop_sequence"] for r in rows] == ["1", "2", "3", "4"]
    back = by_trip(tables)["FUT_SNCF_OCESNNORD108F"]  # Matabiau 08:00, Lalande 08:10, Montauban 08:35
    assert [r["stop_id"] for r in back][1] == LAUNAGUET
    assert seconds(back[1]["arrival_time"]) - seconds(back[0]["departure_time"]) == round(600 * d_b / (d_a + d_b))
    assert back[-1]["arrival_time"] == "08:36:00"


def test_positions_from_neighbouring_stations(ter, positions):
    _, tables, report = ter
    stops = {s["stop_id"]: s for s in tables["stops.txt"]}
    assert "La Vache" in stops[LAUNAGUET]["stop_desc"] and "approximative" in stops[LAUNAGUET]["stop_desc"]
    assert "Labège - Gare" in stops[CADENE]["stop_desc"]
    assert "| Route de Launaguet | Lalande-Église – Toulouse Matabiau | ajoutée |" in report


def test_osm_position_comes_first(tmp_path, positions):
    pos = sncf_positions(positions)
    osm = offset(pos["Labège Innopole"], 400, 0)
    _, tables, _ = build(tmp_path, positions, extra_osm={2: ("Labège-La Cadène", osm)})
    stop = next(s for s in tables["stops.txt"] if s["stop_id"] == CADENE)
    assert (float(stop["stop_lat"]), float(stop["stop_lon"])) == pytest.approx(osm, abs=1e-6)
    assert "OpenStreetMap" in stop["stop_desc"]


def test_report_compares_trains_per_day_with_the_announcement(ter):
    _, _, report = ter
    # 16 trains per direction stop at Labège-La Cadène on each weekday; SNCF G&C announces 42.
    assert "| Labège-La Cadène | Labège Innopole – Labège Village | ajoutée |" in report
    line = next(l for l in report.splitlines() if l.startswith("| Labège-La Cadène"))
    assert line.endswith("| 32 | 32 | 42 |")
    assert "| AERO | tisseo:line:99 |" in report and "| C3 | sncf:FR:Line::SUD: |" in report


def test_halt_already_served_is_not_duplicated(tmp_path, positions):
    out, tables, report = build(tmp_path, positions, {"served_halt": "Route de Launaguet"})
    assert LAUNAGUET not in {s["stop_id"] for s in tables["stops.txt"]}
    assert "déjà desservie dans le GTFS SNCF actuel" in report
    excluded = json.loads((out.parent / "scenario-2028.json").read_text())["exclude_routes"]
    assert "sncf:FR:Line::NORD:" not in excluded and "sncf:FR:Line::SUD:" in excluded
    assert check_feed(tables) == []


def test_halt_without_position_is_skipped_not_invented(tmp_path, positions):
    # Without the Tisséo GTFS the La Vache anchor is unknown, and there is no OSM position.
    out, tables, report = build(tmp_path, positions, tisseo=False)
    assert LAUNAGUET not in {s["stop_id"] for s in tables["stops.txt"]}
    assert "Halte TER Route de Launaguet sans position vérifiable" in report
    assert CADENE in {s["stop_id"] for s in tables["stops.txt"]}  # anchored on line C: still added


def test_halt_far_from_its_neighbours_is_rejected(tmp_path, positions):
    far = offset(sncf_positions(positions)["Labège Village"], 0, 6000)
    _, tables, report = build(tmp_path, positions, extra_osm={2: ("Labège-La Cadène", far)})
    assert CADENE not in {s["stop_id"] for s in tables["stops.txt"]}
    assert "position douteuse" in report


@pytest.mark.parametrize("kwargs,expected", [
    ({"drop_stations": ("Labège Village", "Escalquens")}, "Labège Innopole → Labège Village : Labège Village non desservie"),
    ({"express_only": True}, "Lalande-Église → Toulouse Matabiau : 0 passage(s) de train"),
    ({"rename": {"Lalande-Église": "Grisolles"}}, "Lalande-Église : non desservie ; Lacourtensourt : non desservie"),
])
def test_loud_failures_with_a_diagnostic(tmp_path, positions, capsys, kwargs, expected):
    """No pair of candidate neighbours with trains: the build stops, and lists what the SNCF GTFS serves nearby."""
    out, _, _ = build(tmp_path, positions, kwargs, expect=2)
    err = capsys.readouterr().err
    assert "ne dessert successivement deux des gares voisines candidates" in err and expected in err
    assert "gares SNCF desservies par des trains à moins de 5 km de" in err
    assert re.search(r"gares juste avant ou après (Toulouse Matabiau|Labège Innopole) dans les trains : \S", err)
    assert re.search(r"Labège Innopole \(\d+ m, \d+ course\(s\)\)|Toulouse Matabiau \(\d+ m, \d+ course\(s\)\)", err)
    assert not out.exists()


def test_fallback_neighbour_is_used_and_reported(tmp_path, positions):
    """Lalande-Église no longer served: the next candidate northwards (here Saint-Jory) is used."""
    out, tables, report = build(tmp_path, positions, {"rename": {"Lalande-Église": "Saint-Jory"}})
    assert "| Route de Launaguet | Saint-Jory – Toulouse Matabiau | ajoutée |" in report
    assert "gares voisines de repli retenues, Saint-Jory et Toulouse Matabiau" in report
    assert "Lalande-Église : non desservie" in report
    assert LAUNAGUET in [r["stop_id"] for r in by_trip(tables)["FUT_SNCF_OCESNNORD008F"]]
    # Labège Village not served: Escalquens, the next one, is used (SUD trains call at Innopole then Escalquens).
    _, _, report = build(tmp_path / "b", positions, {"drop_stations": ("Labège Village",)})
    assert "| Labège-La Cadène | Labège Innopole – Escalquens | ajoutée |" in report


def test_coaches_and_other_stop_ids_are_ignored(tmp_path, positions, capsys):
    """motif_arrets_sncf: only the TER stop points; a feed without any stops the build with a diagnostic."""
    sncf = make_sncf_zip(tmp_path / "sncf.zip", positions)
    loaded = bgf.SncfGtfs(sncf)
    loaded.load()
    assert loaded.stops_named("Labège Innopole", "Train TER") and not loaded.stops_named("Labège Innopole", "TGV")


def test_neighbour_names(tmp_path, positions):
    sncf = bgf.SncfGtfs(make_sncf_zip(tmp_path / "sncf.zip", positions))
    sncf.load()
    assert sncf.stops_named("Lalande Eglise") == sncf.stops_named("Lalande-Église") != set()
    assert sncf.stops_named("Matabiau") == sncf.stops_named("Toulouse Matabiau")  # one longer name: accepted
    with pytest.raises(bgf.BuildError, match="ambiguë"):
        sncf.stops_named("Labège")  # Labège Innopole or Labège Village
    assert sncf.stops_named("Nowhere") == set()


def test_without_sncf_gtfs_no_halt(tmp_path, positions):
    osm_dir = write_osm_positions(tmp_path / "osm", positions)
    out = tmp_path / "futur.gtfs.zip"
    assert bgf.main(["--output", str(out), "--osm-dir", str(osm_dir), "--start-date", "2026-10-19"]) == 0
    report = (tmp_path / "futur-rapport.md").read_text(encoding="utf-8")
    assert "haltes TER non ajoutées" in report
