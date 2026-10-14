"""extract_futur_osm.py on a small synthetic OSM file (synthetic coordinates, not real positions)."""

from __future__ import annotations

import csv
import json

import pytest
import yaml

from conftest import PARAMS, gtfs_tables, offset, real_lines, synthetic_positions

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


# ----------------------------------------------------------------------------- CI cases of 14/10/2026
# In the first CI run, "Raisin" was matched to a homonym 14 km away and "Ormeau" to a node named
# "Bel Air" (scored 1.00 through another name key). Both are reproduced here on synthetic positions.


def full_line_osm(tmp_path, with_real=("Raisin", "Ormeau"), with_track=True):
    """Every station as an existing stop with its name; decoys with lower ids (read first)."""
    lines, pos = real_lines(), synthetic_positions()
    elements, ids, nid = [], {}, 10_000
    for line_id, stations in lines.items():
        for st in stations:
            if st.name in ("Raisin", "Ormeau") and st.name not in with_real:
                continue
            if st.name not in ids:
                nid += 1
                ids[st.name] = nid
                elements.append(node(nid, pos[(line_id, st.order)],
                                     {"public_transport": "stop_position", "subway": "yes", "name": st.name}))
    c = {s.name: pos[("C", s.order)] for s in lines["C"]}
    decoys = [
        node(5, offset(c["Lycée Toulouse-Lautrec"], 3000, -14_300), {"public_transport": "platform", "name": "Raisin"}),
        node(6, offset(c["Colomiers - Gare"], -2000, 1500),
             {"public_transport": "platform", "name": "Bel Air", "old_name": "Ormeau"}),
        node(7, offset(c["Colomiers - Gare"], -2500, 1000), {"public_transport": "platform", "name": "Ormeau"}),
    ]
    elements = decoys + elements
    if with_track:
        for wid, stations in ((900, lines["C"]), (901, lines["B_EXT"])):
            refs = [ids[s.name] for s in stations if s.name in ids]
            elements.append(way(wid, refs, {"railway": "construction", "construction": "subway"}))
    osm_file = tmp_path / "line.osm"
    osm_file.write_text("<?xml version='1.0' encoding='UTF-8'?>\n<osm version=\"0.6\" generator=\"test\">\n"
                        + "\n".join(elements) + "\n</osm>\n", encoding="utf-8")
    return osm_file, ids


def extract(tmp_path, osm_file):
    out_dir = tmp_path / "osm-out"
    assert efo.main(["--osm", str(osm_file), "--params", str(PARAMS), "--output-dir", str(out_dir)]) == 0
    rows = {(r["ligne"], r["nom_officiel"]): r for r in csv.DictReader(open(out_dir / "stations_osm.csv", encoding="utf-8"))}
    return rows, (out_dir / "rapport_osm.md").read_text(encoding="utf-8")


def test_homonyms_far_away_are_not_chosen(tmp_path):
    osm_file, ids = full_line_osm(tmp_path)
    rows, _ = extract(tmp_path, osm_file)
    assert rows[("C", "Raisin")]["osm_id"] == str(ids["Raisin"])  # not node 5, 14 km south
    assert rows[("C", "Ormeau")]["osm_id"] == str(ids["Ormeau"])  # not "Bel Air" nor the Colomiers homonym
    assert rows[("C", "Ormeau")]["osm_nom"] == "Ormeau"
    assert len(rows) == 24
    assert all(r["precision"].startswith("station exacte") for r in rows.values())  # stops on the track


def test_rejected_candidate_gives_missing_station(tmp_path):
    osm_file, _ = full_line_osm(tmp_path, with_real=(), with_track=False)
    rows, report = extract(tmp_path, osm_file)
    assert ("C", "Raisin") not in rows and ("C", "Ormeau") not in rows
    assert "10. Raisin : candidat REJETÉ Raisin (node/5)" in report
    assert "16. Ormeau : candidat REJETÉ Ormeau (node/7)" in report
    assert "10. Raisin : MANQUANTE" in report and "16. Ormeau : MANQUANTE" in report
    assert len(rows) == 22  # all the other stations are kept
    lines, pos = real_lines(), synthetic_positions()
    for st in lines["C"]:
        if ("C", st.name) in rows:
            assert (float(rows[("C", st.name)]["lat"]), float(rows[("C", st.name)]["lon"])) == pytest.approx(
                pos[("C", st.order)], abs=1e-6)


def test_other_name_key_never_scores_one():
    bel_air = {"names": [("name", "Bel Air"), ("old_name", "Ormeau")]}
    score, matched = efo.candidate_score("Ormeau", bel_air)
    assert score == 0.95 and matched == "old_name=Ormeau"
    assert efo.candidate_score("Ormeau", {"names": [("name", "Ormeau")]}) == (1.0, "name=Ormeau")
    assert efo.name_score("Raisin", "Raisins") < 1.0


def test_guards_reject_isolated_outlier():
    class S:
        def __init__(self, order):
            self.order = order

    def cand(osm_id, east_m):
        lat, lon = offset((43.6, 1.4), east_m, 0)
        return {"osm_id": osm_id, "osm_type": "node", "lat": lat, "lon": lon, "label": str(osm_id),
                "construction": False, "rank": 1, "score": 1.0, "d_track": None}

    stations = [S(i) for i in range(1, 6)]
    cands = {1: [cand(1, 0)], 2: [cand(2, 1200)], 3: [cand(3, 15_000)], 4: [cand(4, 3600)], 5: [cand(5, 4800)]}
    picks, rejected = efo.choose_stations(stations, cands)
    assert picks[3] is None and 3 in rejected
    assert all(picks[o] for o in (1, 2, 4, 5))
    # first station wrong: the terminus is rejected, not its correct neighbour
    cands = {1: [cand(1, -9000)], 2: [cand(2, 1200)], 3: [cand(3, 2400)], 4: [cand(4, 3600)], 5: [cand(5, 4800)]}
    picks, _ = efo.choose_stations(stations, cands)
    assert picks[1] is None and all(picks[o] for o in (2, 3, 4, 5))
