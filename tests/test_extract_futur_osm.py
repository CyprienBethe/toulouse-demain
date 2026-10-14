"""extract_futur_osm.py on a small synthetic OSM file (synthetic coordinates, not real positions)."""

from __future__ import annotations

import csv
import json

import pytest
import yaml

from conftest import PARAMS, gtfs_tables, offset

pytest.importorskip("osmium")

import build_gtfs_futur as bgf  # noqa: E402
import extract_futur_osm as efo  # noqa: E402

BASE = (43.60, 1.40)


def node(nid, point, tags=None):
    inner = "".join(f'<tag k="{k}" v="{v}"/>' for k, v in (tags or {}).items())
    return f'<node id="{nid}" version="1" lat="{point[0]:.7f}" lon="{point[1]:.7f}">{inner}</node>'


def way(wid, refs, tags):
    nds = "".join(f'<nd ref="{r}"/>' for r in refs)
    inner = "".join(f'<tag k="{k}" v="{v}"/>' for k, v in tags.items())
    return f'<way id="{wid}" version="1">{nds}{inner}</way>'


@pytest.fixture
def mini_case(tmp_path):
    stations_csv = tmp_path / "stations_test.csv"
    stations_csv.write_text(
        "ordre,nom_officiel,commune,lat,lon,precision,correspondances,source,remarques,arret_tisseo_reference\n"
        "1,Alpha Gare,X,,,manquante,,https://example.org,,\n"
        "2,Beta,X,,,manquante,,https://example.org,,\n"
        "3,Gamma,X,,,manquante,,https://example.org,,Gamma (même station)\n",
        encoding="utf-8",
    )
    params = yaml.safe_load(PARAMS.read_text(encoding="utf-8"))
    params["lignes"] = [
        {
            "id": "T", "nom_court": "T", "nom_long": "Test", "stations": str(stations_csv),
            "points_de_calage": [{"station": "Alpha Gare", "minutes": 0}, {"station": "Gamma", "minutes": 4}],
            "intervalle_pointe_s": 300,
        }
    ]
    params["correspondances_internes"] = []
    params_path = tmp_path / "params.yaml"
    params_path.write_text(yaml.safe_dump(params, allow_unicode=True), encoding="utf-8")

    alpha, beta, gamma = BASE, offset(BASE, 1200, 0), offset(BASE, 2400, 300)
    track = [offset(alpha, 0, 20), offset(alpha, 600, 120), offset(beta, 0, 20), offset(beta, 700, 200),
             offset(gamma, 0, 20)]
    elements = [
        node(1, alpha, {"railway": "construction", "construction": "station", "name": "Alpha Gare"}),
        node(2, offset(alpha, -50, 0), {"railway": "station", "name": "Alpha"}),  # existing, other name
        node(3, gamma, {"railway": "station", "station": "subway", "name": "Gamma"}),  # existing, same name
        node(4, offset(BASE, 9000, 0), {"railway": "construction", "construction": "station", "name": "Zeta"}),
    ]
    square = [offset(beta, -40, -40), offset(beta, 40, -40), offset(beta, 40, 40), offset(beta, -40, 40)]
    elements += [node(10 + i, p) for i, p in enumerate(square)]
    elements += [node(20 + i, p) for i, p in enumerate(track)]
    elements.append(way(100, [10, 11, 12, 13, 10], {"public_transport": "station", "construction": "yes", "name": "Beta"}))
    elements.append(way(101, [20, 21, 22, 23, 24], {"railway": "construction", "construction": "subway"}))
    osm_file = tmp_path / "mini.osm"
    osm_file.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n<osm version=\"0.6\" generator=\"test\">\n"
        + "\n".join(elements) + "\n</osm>\n",
        encoding="utf-8",
    )
    return params_path, osm_file, tmp_path / "osm-out"


def test_extract_matches_stations_and_track(mini_case):
    params_path, osm_file, out_dir = mini_case
    assert efo.main(["--osm", str(osm_file), "--params", str(params_path), "--output-dir", str(out_dir)]) == 0
    rows = list(csv.DictReader(open(out_dir / "stations_osm.csv", encoding="utf-8")))
    by_name = {r["nom_officiel"]: r for r in rows}
    assert set(by_name) == {"Alpha Gare", "Beta", "Gamma"}
    assert by_name["Alpha Gare"]["osm_id"] == "1"  # the construction node, not the existing "Alpha"
    assert by_name["Alpha Gare"]["precision"].startswith("station exacte")
    assert by_name["Beta"]["osm_type"] == "way"
    assert by_name["Gamma"]["precision"].startswith("station exacte (OSM : station existante")
    assert all("ODbL" in r["licence"] for r in rows)
    traces = json.loads((out_dir / "traces_osm.geojson").read_text(encoding="utf-8"))
    assert [f["properties"]["methode"] for f in traces["features"]] == ["osm", "osm"]
    assert len(traces["features"][0]["geometry"]["coordinates"]) > 2


def test_build_uses_osm_outputs(mini_case, tmp_path):
    params_path, osm_file, out_dir = mini_case
    efo.main(["--osm", str(osm_file), "--params", str(params_path), "--output-dir", str(out_dir)])
    out = tmp_path / "futur.gtfs.zip"
    assert bgf.main(["--params", str(params_path), "--osm-dir", str(out_dir), "--output", str(out),
                     "--start-date", "2026-10-19"]) == 0
    tables = gtfs_tables(out)
    assert len([p for p in tables["shapes.txt"] if p["shape_id"] == "FUT_SH_T_0"]) > 3
    assert any("OpenStreetMap" in a["organization_name"] for a in tables["attributions.txt"])


def test_name_score_and_simplify():
    assert efo.name_score("Montaudran Gare - Piste des Géants", "Montaudran Gare") == 0.9
    assert efo.name_score("Ormeau", "Ormeau") == 1.0
    assert efo.name_score("Raisin", "Bonnefoy") < efo.MIN_SCORE
    line = [offset(BASE, i * 100, 0) for i in range(10)]
    assert len(efo.simplify(line)) == 2
