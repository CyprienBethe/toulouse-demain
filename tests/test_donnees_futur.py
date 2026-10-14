"""Checks on the versioned data: data/futur/*.csv and data/futur/parametres.yaml."""

from __future__ import annotations

import csv
import itertools

import pytest

from conftest import PARAMS, REPO_ROOT, real_lines

import build_gtfs_futur as bgf

COLUMNS = ["ordre", "nom_officiel", "commune", "lat", "lon", "precision", "correspondances", "source"]
CSV_FILES = ["stations_ligne_c.csv", "stations_ligne_b_prolongee.csv"]
# Generous box around the Toulouse area: a coordinate outside is a typo.
BBOX = (43.45, 1.20, 43.75, 1.65)


@pytest.mark.parametrize("name", CSV_FILES)
def test_csv_columns_and_sources(name):
    with open(REPO_ROOT / "data" / "futur" / name, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames[: len(COLUMNS)] == COLUMNS
        rows = list(reader)
    for row in rows:
        assert row["nom_officiel"].strip(), row
        assert row["precision"].strip(), f"précision vide : {row['nom_officiel']}"
        assert all(url.strip().startswith("https://") for url in row["source"].split(";")), row["source"]
        if row["lat"]:
            lat, lon = float(row["lat"]), float(row["lon"])
            assert BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3], row["nom_officiel"]
            assert len(row["lat"].split(".")[1]) == 6 and len(row["lon"].split(".")[1]) == 6, "6 décimales"
            assert row["precision"].startswith(("station exacte", "approximative")), row["precision"]
        else:
            assert not row["lon"]


def test_line_c_has_21_stations_and_b_extension_3():
    lines = real_lines()
    assert len(lines["C"]) == 21  # Tisséo / Toulouse Métropole : 21 stations
    assert [s.name for s in lines["B_EXT"]] == ["Ramonville", "Parc du Canal", "Labège Madron"]
    assert lines["C"][0].name == "Colomiers - Gare"
    assert lines["C"][-1].name == "Labège - Gare"
    names = [s.name for s in lines["C"]]
    assert len(set(names)) == len(names)


def test_shared_station_is_written_the_same_way():
    lines = real_lines()
    c = {bgf.normalize_name(s.name) for s in lines["C"]}
    assert bgf.normalize_name("Labège Madron") in c
    assert bgf.normalize_name(lines["B_EXT"][-1].name) in c


def test_params_are_consistent():
    params = bgf.load_params(PARAMS)
    lines = real_lines()
    for line in params["lignes"]:
        names = {bgf.normalize_name(s.name) for s in lines[line["id"]]}
        for cp in line["points_de_calage"]:
            assert bgf.normalize_name(cp["station"]) in names, cp
        assert line["points_de_calage"][0]["minutes"] == 0
    c = next(l for l in params["lignes"] if l["id"] == "C")
    assert c["intervalle_pointe_s"] == 205  # 3 min 25 (Tisséo 2022)
    assert c["points_de_calage"][-1]["minutes"] == 37  # Toulouse Métropole
    b = next(l for l in params["lignes"] if l["id"] == "B_EXT")
    assert b["intervalle_pointe_s"] == 300  # 5 min (Tisséo 2022)
    assert b["points_de_calage"][-1]["minutes"] == 3.5  # 3 min 30 (Tisséo 2022)


def test_known_coordinates_are_plausible():
    """Distances between consecutive stations, when both positions are already in the CSV."""
    lines = real_lines()
    checked = 0
    for stations in lines.values():
        for a, b in itertools.pairwise(stations):
            if a.lat is None or b.lat is None:
                continue
            d = bgf.haversine_m(a.lat, a.lon, b.lat, b.lon)
            assert bgf.MIN_HOP_M <= d <= bgf.MAX_HOP_M, f"{a.name} → {b.name} : {d:.0f} m"
            checked += 1
    if not checked:
        pytest.skip("aucune paire de stations consécutives n'a encore de coordonnées dans les CSV")


def test_build_refuses_to_invent_missing_coordinates(tmp_path, capsys):
    """Today the CSVs have no coordinates: without OSM or Tisséo the build must stop, not guess."""
    code = bgf.main(["--output", str(tmp_path / "futur.gtfs.zip"), "--osm-dir", str(tmp_path / "absent")])
    err = capsys.readouterr().err
    assert code == 2
    assert "sans coordonnées" in err and "Colomiers - Gare" in err
    assert not (tmp_path / "futur.gtfs.zip").exists()
