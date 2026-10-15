"""Checks on the versioned data: data/futur/*.csv and data/futur/parametres.yaml."""

from __future__ import annotations

import csv
import itertools

import pytest

from conftest import PARAMS, REPO_ROOT, real_lines

import build_gtfs_futur as bgf

COLUMNS = ["ordre", "nom_officiel", "commune", "lat", "lon", "precision", "correspondances", "source"]
CSV_FILES = ["stations_ligne_c.csv", "stations_ligne_b_prolongee.csv", "stations_ligne_aeroport.csv",
             "haltes_ter.csv"]
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
    # Ligne Aéroport: from the Blagnac pole (station of line C, Tisséo 2024) to the airport.
    assert [s.name for s in lines["AEROPORT"]] == ["Blagnac", "Aéroport"]


def test_shared_station_is_written_the_same_way():
    lines = real_lines()
    c = {bgf.normalize_name(s.name) for s in lines["C"]}
    assert bgf.normalize_name("Labège Madron") in c
    assert bgf.normalize_name(lines["B_EXT"][-1].name) in c
    assert lines["AEROPORT"][0].name in {s.name for s in lines["C"]}  # same spelling: one parent station


def test_internal_transfers_name_stations_of_both_lines():
    params = bgf.load_params(PARAMS)
    lines = real_lines()
    pairs = {(c["station"], tuple(c["lignes"])) for c in params["correspondances_internes"]}
    assert ("Blagnac", ("C", "AEROPORT")) in pairs
    for station, line_ids in pairs:
        for lid in line_ids:
            assert station in {s.name for s in lines[lid]}, (station, lid)


def test_replaced_tisseo_lines():
    """Scenario 2028: the airport shuttle (route_short_name AERO in the Tisséo GTFS) is replaced by the tram."""
    params = bgf.load_params(PARAMS)
    replaced = {i["ligne"]: i["remplacee_par"] for i in params["lignes_tisseo_remplacees"]}
    assert replaced == {"AERO": "AEROPORT"}


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
    tram = next(l for l in params["lignes"] if l["id"] == "AEROPORT")
    assert bgf.route_type(tram) == 0  # tram
    assert tram["intervalle_pointe_s"] == 300  # « un tram toutes les cinq minutes » (Tisséo 2026)
    assert tram["points_de_calage"][-1] == {"station": "Aéroport", "minutes": 7}  # 7 min (Tisséo 2024)
    assert {bgf.route_type(l) for l in params["lignes"] if l["id"] != "AEROPORT"} == {1}
    colours = [l["couleur"].upper() for l in params["lignes"]]
    assert len(colours) == len(set(colours))


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


def test_ter_halts_are_consistent():
    """Two halts, marked as forecasts, each between two SNCF stations; Labège-La Cadène with its 42 trains."""
    params = bgf.load_params(PARAMS)
    haltes = bgf.load_haltes(params, REPO_ROOT)
    assert [(h.name, h.between) for h in haltes] == [
        ("Route de Launaguet", ("Lalande-Église", "Toulouse Matabiau")),
        ("Labège-La Cadène", ("Labège Innopole", "Labège Village")),
    ]
    with open(REPO_ROOT / "data" / "futur" / "haltes_ter.csv", encoding="utf-8", newline="") as fh:
        assert all(row["remarques"].startswith("PRÉVISIONNEL") for row in csv.DictReader(fh))
    assert haltes[1].announced == 42  # SNCF Gares & Connexions, 16/12/2024
    assert params["haltes_ter"]["temps_arret_s"] == 60


def _luminance(hex_colour: str) -> float:
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast(a: str, b: str) -> float:
    light, dark = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def test_line_colours_follow_the_ux_charter():
    """docs/ux/parcours.md: badge text white or #16304F, at least 4.5:1, without darkening the colour."""
    for line in bgf.load_params(PARAMS)["lignes"]:
        best = max(_contrast(line["couleur"], "FFFFFF"), _contrast(line["couleur"], "16304F"))
        assert best >= 4.5, (line["id"], line["couleur"], round(best, 2))
