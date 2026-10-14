"""Builds sample futur GTFS feeds in a temporary folder and checks them.

Positions are synthetic (see conftest.py): the tests check the logic, not the real geography.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections import Counter

import pytest

from conftest import REPO_ROOT, active_services, gtfs_tables, make_tisseo_zip, real_lines, write_osm_positions
from gtfs_checks import check_feed, seconds

import build_gtfs_futur as bgf


def build(tmp_path, positions, tisseo=None, skip=(), start="2026-10-19", params=None):
    osm_dir = write_osm_positions(tmp_path / "osm", positions, skip=skip)
    out = tmp_path / "out" / "futur.gtfs.zip"
    args = ["--output", str(out), "--osm-dir", str(osm_dir), "--start-date", start]
    if tisseo:
        args += ["--tisseo-gtfs", str(tisseo)]
    if params:
        args += ["--params", str(params)]
    assert bgf.main(args) == 0
    return out, gtfs_tables(out)


def trips_of(tables, route, service=None, direction=None):
    out = []
    for t in tables["trips.txt"]:
        if t["route_id"] == route and (service is None or t["service_id"] == service) and (
            direction is None or t["direction_id"] == str(direction)
        ):
            out.append(t["trip_id"])
    return out


def stop_times_by_trip(tables):
    by_trip = {}
    for st in tables["stop_times.txt"]:
        by_trip.setdefault(st["trip_id"], []).append(st)
    for rows in by_trip.values():
        rows.sort(key=lambda r: int(r["stop_sequence"]))
    return by_trip


# ----------------------------------------------------------------------------- unit tests


def test_compute_offsets_splits_time_by_distance():
    arr, dep, run = bgf.compute_offsets([1000, 3000], [(0, 0), (2, 220)], dwell=20)
    assert arr == [0, 50, 220]
    assert dep == [0, 70, 220]
    assert run == pytest.approx([50, 150])


def test_compute_offsets_respects_intermediate_checkpoint():
    arr, _, _ = bgf.compute_offsets([1000, 1000, 2000], [(0, 0), (1, 100), (3, 400)], dwell=20)
    assert arr[1] == 100 and arr[3] == 400


def test_names_and_anchor_parsing():
    assert bgf.normalize_name("Marengo - SNCF") == bgf.normalize_name("Marengo-SNCF")
    assert bgf.slug("Labège - Gare") == "LABEGE_GARE"
    assert bgf.parse_anchor("Ramonville (même station)") == ("Ramonville", True)
    assert bgf.parse_anchor("La Vache (station voisine)") == ("La Vache", False)
    assert bgf.parse_anchor("") is None


# ----------------------------------------------------------------------------- standalone feed


@pytest.fixture
def standalone(tmp_path, positions):
    return build(tmp_path, positions)


def test_standalone_feed_is_valid(standalone):
    _, tables = standalone
    assert check_feed(tables) == []
    for name in ("agency.txt", "routes.txt", "stops.txt", "trips.txt", "stop_times.txt", "calendar.txt",
                 "feed_info.txt", "shapes.txt", "transfers.txt", "attributions.txt"):
        assert tables.get(name), name


def test_licence_and_attribution(standalone):
    _, tables = standalone
    info = tables["feed_info.txt"][0]
    assert "ODbL" in info["feed_license"]
    assert "données dérivées sous ODbL" in info["feed_license"]
    names = " ".join(a["organization_name"] for a in tables["attributions.txt"])
    assert "OpenStreetMap" in names


def test_standalone_calendar_covers_three_weeks(standalone):
    _, tables = standalone
    for row in tables["calendar.txt"]:
        assert (row["start_date"], row["end_date"]) == ("20261019", "20261108")
    assert "calendar_dates.txt" not in tables
    assert {r["service_id"] for r in tables["calendar.txt"]} == {"FUT_LUNMER", "FUT_JEUVEN", "FUT_SAM", "FUT_DIM"}


def test_station_order_matches_csv(standalone):
    _, tables = standalone
    names = {s["stop_id"]: s["stop_name"] for s in tables["stops.txt"]}
    by_trip = stop_times_by_trip(tables)
    for line_id, stations in real_lines().items():
        expected = [s.name for s in stations]
        for direction, order in ((0, expected), (1, expected[::-1])):
            trip = trips_of(tables, f"FUT_{line_id}", "FUT_LUNMER", direction)[0]
            assert [names[r["stop_id"]] for r in by_trip[trip]] == order


def test_official_travel_times(standalone):
    _, tables = standalone
    by_trip = stop_times_by_trip(tables)
    names = {s["stop_id"]: s["stop_name"] for s in tables["stops.txt"]}

    def time_between(trip, a, b):
        rows = {names[r["stop_id"]]: r for r in by_trip[trip]}
        return seconds(rows[b]["arrival_time"]) - seconds(rows[a]["departure_time"])

    c0 = trips_of(tables, "FUT_C", "FUT_LUNMER", 0)[0]
    c1 = trips_of(tables, "FUT_C", "FUT_LUNMER", 1)[0]
    assert time_between(c0, "Colomiers - Gare", "Labège - Gare") == 37 * 60
    assert time_between(c1, "Labège - Gare", "Colomiers - Gare") == 37 * 60
    # Labège → Matabiau 20 min (Tisséo 2022), Colomiers → Matabiau 17 min (deduced)
    assert time_between(c1, "Labège - Gare", "Matabiau Gare") == 20 * 60
    assert time_between(c0, "Colomiers - Gare", "Matabiau Gare") == 17 * 60
    b0 = trips_of(tables, "FUT_B_EXT", "FUT_LUNMER", 0)[0]
    assert time_between(b0, "Ramonville", "Labège Madron") == 210


def test_peak_headway_and_service_hours(standalone):
    _, tables = standalone
    by_trip = stop_times_by_trip(tables)
    for route, peak in (("FUT_C", 205), ("FUT_B_EXT", 300)):
        starts = sorted(seconds(by_trip[t][0]["departure_time"]) for t in trips_of(tables, route, "FUT_LUNMER", 0))
        assert starts[0] == bgf.parse_hhmm("05:15")
        assert starts[-1] <= bgf.parse_hhmm("24:00")
        gaps = Counter(b - a for a, b in zip(starts, starts[1:]) if 7 * 3600 + 600 <= a < 8 * 3600 + 1800)
        assert gaps.most_common(1)[0][0] == peak
        late = [seconds(by_trip[t][0]["departure_time"]) for t in trips_of(tables, route, "FUT_JEUVEN", 0)]
        assert bgf.parse_hhmm("24:00") < max(late) <= bgf.parse_hhmm("27:00")


def test_internal_transfer_at_labege_madron(standalone):
    _, tables = standalone
    pairs = {(t["from_stop_id"], t["to_stop_id"]) for t in tables["transfers.txt"]}
    assert ("FUT_C_LABEGE_MADRON", "FUT_B_EXT_LABEGE_MADRON") in pairs
    assert ("FUT_B_EXT_LABEGE_MADRON", "FUT_C_LABEGE_MADRON") in pairs
    parents = {s["stop_id"]: s["parent_station"] for s in tables["stops.txt"]}
    assert parents["FUT_C_LABEGE_MADRON"] == parents["FUT_B_EXT_LABEGE_MADRON"] == "FUT_STA_LABEGE_MADRON"


def test_distances_are_plausible(standalone):
    _, tables = standalone
    by_trip = stop_times_by_trip(tables)
    for route in ("FUT_C", "FUT_B_EXT"):
        rows = by_trip[trips_of(tables, route, "FUT_LUNMER", 0)[0]]
        dists = [float(r["shape_dist_traveled"]) for r in rows]
        hops = [b - a for a, b in zip(dists, dists[1:])]
        assert all(bgf.MIN_HOP_M <= h <= bgf.MAX_HOP_M for h in hops), hops


def test_standalone_keeps_shuttle_and_excludes_nothing(standalone):
    out, tables = standalone
    assert {r["route_id"] for r in tables["routes.txt"]} == {"FUT_C", "FUT_B_EXT"}
    assert json.loads((out.parent / "scenario-2028.json").read_text()) == {"exclude_routes": []}


def test_report_written(standalone):
    out, _ = standalone
    report = (out.parent / "futur-rapport.md").read_text(encoding="utf-8")
    assert "Ligne C" in report and "vitesse commerciale" in report


def test_gtfs_kit_reads_feed(standalone):
    gk = pytest.importorskip("gtfs_kit")
    out, _ = standalone
    feed = gk.read_feed(out, dist_units="m")
    assert set(feed.routes["route_short_name"]) == {"C", "B"}
    stats = gk.compute_trip_stats(feed)
    c = stats[stats["route_id"] == "FUT_C"]
    assert (c["duration"] == 37 / 60).all()  # hours
    assert (c["num_stops"] == 21).all()
    quality = feed.assess_quality().set_index("indicator")["value"]
    assert quality["assessment"] == "good feed", quality.to_dict()


@pytest.mark.skipif(not os.environ.get("GTFS_VALIDATOR_JAR"), reason="GTFS_VALIDATOR_JAR non défini (validateur MobilityData)")
def test_mobilitydata_validator(standalone, tmp_path):
    """Optional: official MobilityData validator (Java), e.g. in CI."""
    if not shutil.which("java"):
        pytest.skip("java absent")
    out, _ = standalone
    report_dir = tmp_path / "validation"
    subprocess.run(
        ["java", "-jar", os.environ["GTFS_VALIDATOR_JAR"], "-i", str(out), "-o", str(report_dir)],
        check=True, capture_output=True,
    )
    import json

    notices = json.loads((report_dir / "report.json").read_text())["notices"]
    errors = [n for n in notices if n.get("severity") == "ERROR"]
    assert errors == [], errors


# ----------------------------------------------------------------------------- with the Tisséo GTFS


@pytest.fixture
def with_tisseo(tmp_path, positions):
    tisseo = make_tisseo_zip(tmp_path / "tisseo.zip", positions)
    anchored = ("Ramonville", "La Vache Gare - Le Grand marché", "François Verdier", "Matabiau Gare")
    return build(tmp_path, positions, tisseo=tisseo, skip=anchored)


def test_tisseo_feed_is_valid(with_tisseo):
    _, tables = with_tisseo
    assert check_feed(tables) == []


def test_calendar_follows_tisseo_and_holidays(with_tisseo):
    _, tables = with_tisseo
    for row in tables["calendar.txt"]:
        assert (row["start_date"], row["end_date"]) == ("20261012", "20261115")
    exceptions = {(d["service_id"], d["date"], d["exception_type"]) for d in tables["calendar_dates.txt"]}
    # Line C services, and the copied Tisséo line B services with Tisséo's own exception.
    assert exceptions == {("FUT_LUNMER", "20261111", "2"), ("FUT_DIM", "20261111", "1"),
                          ("FUT_TIS_WEEK", "20261111", "2"), ("FUT_TIS_SUN", "20261111", "1")}


def test_positions_from_tisseo_anchors(with_tisseo):
    _, tables = with_tisseo
    stops = {s["stop_id"]: s for s in tables["stops.txt"]}
    assert "FUT_B_EXT_RAMONVILLE" not in stops  # through trains: Ramonville is the copied Tisséo stop
    ram = stops["FUT_TIS_SA_RAM"]
    assert ram["stop_name"] == "Ramonville" and "GTFS Tisséo" in ram["stop_desc"]
    mat = stops["FUT_C_MATABIAU_GARE"]
    assert "approximative" in mat["stop_desc"]
    assert "SA_MAR" in mat["stop_desc"]  # the metro station, not the bus stop of the same name


def test_headways_calibrated_on_line_b(with_tisseo):
    """Synthetic line B: 2 min peak, 4 min off-peak, 6 min evening → C: 3'25, 6'50, 10'15."""
    _, tables = with_tisseo
    by_trip = stop_times_by_trip(tables)
    starts = sorted(seconds(by_trip[t][0]["departure_time"]) for t in trips_of(tables, "FUT_C", "FUT_LUNMER", 0))
    gaps = {}
    for a, b in zip(starts, starts[1:]):
        gaps.setdefault(a // 3600, Counter())[b - a] += 1
    assert gaps[7].most_common(1)[0][0] == 205
    assert gaps[11].most_common(1)[0][0] == 410
    assert gaps[22].most_common(1)[0][0] == 615
    assert starts[-1] <= bgf.parse_hhmm("24:00")  # synthetic B stops at midnight every day


def test_night_trips_coded_on_next_day(tmp_path, positions):
    """Thursday night trips coded 00:20-02:20 on Friday: line C must run until 26:20, not all night."""
    tisseo = make_tisseo_zip(tmp_path / "tisseo.zip", positions, night_next_day=True)
    _, tables = build(tmp_path, positions, tisseo=tisseo)
    by_trip = stop_times_by_trip(tables)
    for service, last in (("FUT_JEUVEN", "26:20"), ("FUT_SAM", "26:20"), ("FUT_LUNMER", "24:00")):
        starts = [seconds(by_trip[t][0]["departure_time"]) for t in trips_of(tables, "FUT_C", service, 0)]
        assert min(starts) == bgf.parse_hhmm("05:15")
        assert bgf.parse_hhmm(last) - 900 < max(starts) <= bgf.parse_hhmm(last)


# ----------------------------------------------------------------------------- line B through trains


def tisseo_b_times(tisseo_zip):
    by_trip = {}
    for st in gtfs_tables(tisseo_zip)["stop_times.txt"]:
        if st["trip_id"].startswith("B_"):
            by_trip.setdefault(st["trip_id"], []).append(st)
    for rows in by_trip.values():
        rows.sort(key=lambda r: int(r["stop_sequence"]))
    return by_trip


@pytest.fixture
def direct(tmp_path, positions):
    tisseo = make_tisseo_zip(tmp_path / "tisseo.zip", positions)
    out, tables = build(tmp_path, positions, tisseo=tisseo)
    return out, tables, tisseo_b_times(tisseo)


def test_b_direct_route_and_scenario_file(direct):
    out, tables, _ = direct
    routes = {r["route_id"]: r for r in tables["routes.txt"]}
    assert set(routes) == {"FUT_C", "FUT_B"}  # no shuttle
    assert routes["FUT_B"]["route_short_name"] == "B"
    assert json.loads((out.parent / "scenario-2028.json").read_text()) == {"exclude_routes": ["tisseo:LB"]}
    assert check_feed(tables) == []


def test_b_direct_copies_every_trip_with_tisseo_times(direct):
    _, tables, tisseo = direct
    by_trip = stop_times_by_trip(tables)
    stops = {s["stop_id"]: s for s in tables["stops.txt"]}
    for tid, rows in tisseo.items():
        copies = [t for t in (f"FUT_TIS_{tid}", f"FUT_TIS_{tid}_P") if t in by_trip]
        assert len(copies) == 1, tid  # one copy per trip when the choice is the same every day
        copy = by_trip[copies[0]]
        tisseo_part = [r for r in copy if r["stop_id"].startswith("FUT_TIS_")]
        assert [r["stop_id"] for r in tisseo_part] == [f"FUT_TIS_{r['stop_id']}" for r in rows]
        extended = copies[0].endswith("_P")
        towards_labege = copy[-1]["stop_id"] == "FUT_B_EXT_LABEGE_MADRON"
        for k, (mine, theirs) in enumerate(zip(tisseo_part, rows)):
            # At Ramonville an extended train stops 20 s: only the Tisséo time that still applies is kept.
            if not (extended and towards_labege and k == len(rows) - 1):
                assert mine["departure_time"] == theirs["departure_time"]
            if not (extended and not towards_labege and k == 0):
                assert mine["arrival_time"] == theirs["arrival_time"]
    ups = stops["FUT_TIS_SP_UPS"]
    assert ups["stop_name"] == "Université Paul Sabatier"


def test_b_direct_extension_times(direct):
    _, tables, _ = direct
    by_trip = stop_times_by_trip(tables)
    names = {s["stop_id"]: s["stop_name"] for s in tables["stops.txt"]}
    extended = [t for t in by_trip if t.startswith("FUT_TIS_B_") and t.endswith("_P")]
    assert extended
    for tid in extended:
        rows = by_trip[tid]
        order = [names[r["stop_id"]] for r in rows]
        if order[-1] == "Labège Madron":  # towards Labège: Borderouge ... Ramonville, Parc du Canal, Labège Madron
            assert order[-3:] == ["Ramonville", "Parc du Canal", "Labège Madron"]
            ram, end = rows[-3], rows[-1]
            assert seconds(ram["departure_time"]) - seconds(ram["arrival_time"]) == 20
            assert seconds(end["arrival_time"]) - seconds(ram["departure_time"]) == 210
        else:  # from Labège: Labège Madron, Parc du Canal, Ramonville ... Borderouge
            assert order[:3] == ["Labège Madron", "Parc du Canal", "Ramonville"]
            assert seconds(rows[2]["arrival_time"]) - seconds(rows[0]["departure_time"]) == 210
    trips = {t["trip_id"]: t for t in tables["trips.txt"]}
    assert all(trips[t]["shape_id"].startswith("FUT_TIS_SH_B") for t in extended)


def extension_gaps(tables, day, start, end):
    """Gaps between trains arriving at Labège Madron on 'day', for arrivals in [start, end)."""
    services = active_services(tables, day)
    by_trip = stop_times_by_trip(tables)
    trips = {t["trip_id"]: t for t in tables["trips.txt"]}
    arrivals = sorted(
        seconds(rows[-1]["arrival_time"]) for tid, rows in by_trip.items()
        if trips[tid]["route_id"] == "FUT_B" and trips[tid]["service_id"] in services
        and rows[-1]["stop_id"] == "FUT_B_EXT_LABEGE_MADRON"
    )
    sel = [a for a in arrivals if start <= a < end]
    return [b - a for a, b in zip(sel, sel[1:])]


@pytest.mark.parametrize("start,end,target,trunk", [("07:20", "08:45", 300, 120), ("10:00", "16:00", 600, 240),
                                                   ("21:00", "23:30", 900, 360)])
def test_b_direct_extension_headway(direct, start, end, target, trunk):
    """Synthetic line B every 2 / 4 / 6 min; extension 5 min in the peak, then the same ratios."""
    _, tables, _ = direct
    gaps = extension_gaps(tables, "20261020", bgf.parse_hhmm(start), bgf.parse_hhmm(end))
    assert gaps and abs(sum(gaps) / len(gaps) - target) <= 0.1 * target, gaps
    assert max(gaps) - min(gaps) <= trunk  # never more than one train of line B away from the grid


def test_b_direct_split_when_days_differ(tmp_path, positions):
    """Extra peak trains on 21/10 only: that day gets its own choice, each trip runs once per day."""
    tisseo_zip = make_tisseo_zip(tmp_path / "tisseo.zip", positions, extra_service_date="20261021")
    _, tables = build(tmp_path, positions, tisseo=tisseo_zip)
    assert check_feed(tables) == []
    trips = {t["trip_id"]: t for t in tables["trips.txt"]}
    for day in ("20261020", "20261021", "20261111"):
        services = active_services(tables, day)
        running = Counter(tid.removesuffix("_P") for tid, t in trips.items()
                          if t["route_id"] == "FUT_B" and t["service_id"] in services)
        assert running and max(running.values()) == 1, day
    gaps = extension_gaps(tables, "20261021", bgf.parse_hhmm("07:10"), bgf.parse_hhmm("08:50"))
    assert abs(sum(gaps) / len(gaps) - 300) <= 30, gaps
    assert any(len(t["service_id"].split("_")) > 3 for t in trips.values() if t["route_id"] == "FUT_B")


def test_ids_do_not_collide_with_tisseo(tmp_path, positions):
    clash = (("FUT_STA_BLAGNAC", "Blagnac test", positions[("C", 4)], "0", ""),)
    tisseo = make_tisseo_zip(tmp_path / "tisseo.zip", positions, extra_stops=clash)
    osm_dir = write_osm_positions(tmp_path / "osm", positions)
    code = bgf.main(["--output", str(tmp_path / "f.zip"), "--osm-dir", str(osm_dir), "--tisseo-gtfs", str(tisseo)])
    assert code == 2


def test_command_line_contract(tmp_path, positions):
    """python scripts/build_gtfs_futur.py --tisseo-gtfs <zip> --output <zip>"""
    tisseo = make_tisseo_zip(tmp_path / "tisseo.zip", positions)
    osm_dir = write_osm_positions(tmp_path / "osm", positions)
    out = tmp_path / "build" / "gtfs" / "futur.gtfs.zip"
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "build_gtfs_futur.py"), "--tisseo-gtfs", str(tisseo),
         "--output", str(out), "--osm-dir", str(osm_dir)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert out.exists()
    assert (out.parent / "scenario-2028.json").exists()
