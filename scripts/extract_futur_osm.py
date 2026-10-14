#!/usr/bin/env python3
"""Extract the future metro stations and a simplified track from an OpenStreetMap extract.

Run in CI (the workspace cannot reach OSM), before build_gtfs_futur.py:

    python scripts/extract_futur_osm.py --osm <region>.osm.pbf --output-dir build/futur-osm

For each station of data/futur/stations_*.csv, the script looks for an OSM object with a matching
name tagged as a station under construction (railway=construction + construction=station,
public_transport=station + construction=*, construction:railway=station...). Existing objects are
accepted only with an identical name (e.g. Ramonville, the current terminus of line B).
The track of each hop is the shortest path over the railway ways under construction (and the
existing metro), simplified; when no path is found the hop is left out (straight line in the GTFS).

Outputs (data derived under ODbL, © OpenStreetMap contributors):
    stations_osm.csv      position, OSM object and precision of every matched station
    traces_osm.geojson    one LineString per hop
    rapport_osm.md        matched / unmatched stations, for human review
"""

from __future__ import annotations

import argparse
import csv
import heapq
import json
import math
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_gtfs_futur import (  # noqa: E402
    DEFAULT_PARAMS,
    REPO_ROOT,
    BuildError,
    haversine_m,
    load_params,
    load_stations,
    normalize_name,
    resolve_path,
)

LICENCE = "données dérivées sous ODbL - © les contributeurs d'OpenStreetMap"
# lat_min, lon_min, lat_max, lon_max: Toulouse urban area, wide margin.
BBOX = (43.40, 1.15, 43.80, 1.70)
NAME_KEYS = ("name", "official_name", "alt_name", "old_name", "name:fr", "construction:name")
MIN_SCORE = 0.85
SNAP_M = 300  # max distance between a station and the track
SIMPLIFY_M = 5  # Douglas-Peucker tolerance


def in_bbox(lat: float, lon: float) -> bool:
    return BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3]


def is_construction(tags: dict) -> bool:
    return (
        tags.get("railway") == "construction"
        or tags.get("public_transport") == "construction"
        or "construction" in tags
        or any(k.startswith("construction:") for k in tags)
    )


def station_rank(tags: dict) -> int:
    """2 = station, 1 = platform, 0 = not a station-like object."""
    values = {
        tags.get("railway"),
        tags.get("public_transport"),
        tags.get("construction"),
        tags.get("construction:railway"),
        tags.get("construction:public_transport"),
    }
    if values & {"station", "halt"}:
        return 2
    if values & {"platform", "stop_position", "stop"}:
        return 1
    return 0


def is_track(tags: dict) -> bool:
    railway = tags.get("railway")
    if railway == "subway":
        return True
    if railway == "construction":
        return tags.get("construction", "subway") in {"subway", "light_rail", "rail", "yes", "monorail"}
    return tags.get("construction:railway") in {"subway", "light_rail"}


def name_score(expected: str, candidate: str) -> float:
    a, b = normalize_name(expected), normalize_name(candidate)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    shorter, longer = sorted((a, b), key=len)
    if len(shorter) >= 5 and shorter in longer:
        return 0.9
    return SequenceMatcher(None, a, b).ratio()


def read_osm(path: Path):
    """Station-like objects and railway track graph from the OSM file."""
    import osmium  # imported here so that the module can be imported without pyosmium

    candidates, edges, coords = [], [], {}  # edges: (a, b, metres, under construction?)
    keys = ("railway", "public_transport", "construction", "construction:railway", "construction:public_transport")
    processor = osmium.FileProcessor(str(path)).with_locations().with_filter(osmium.filter.KeyFilter(*keys))
    for obj in processor:
        tags = dict(obj.tags)
        if obj.is_node():
            if not obj.location.valid():
                continue
            lat, lon = obj.location.lat, obj.location.lon
            kind = "node"
        elif obj.is_way():
            pts = [(n.ref, n.location.lat, n.location.lon) for n in obj.nodes if n.location.valid()]
            if not pts:
                continue
            if is_track(tags) and any(in_bbox(p[1], p[2]) for p in pts):
                building = tags.get("railway") != "subway"
                for (ra, la, oa), (rb, lb, ob) in zip(pts, pts[1:]):
                    coords[ra], coords[rb] = (la, oa), (lb, ob)
                    edges.append((ra, rb, haversine_m(la, oa, lb, ob), building))
            unique = {p[0]: p for p in pts}.values()
            lat = sum(p[1] for p in unique) / len(unique)
            lon = sum(p[2] for p in unique) / len(unique)
            kind = "way"
        else:
            continue
        rank = station_rank(tags)
        names = [tags[k] for k in NAME_KEYS if tags.get(k)]
        if rank and names and in_bbox(lat, lon):
            candidates.append(
                {
                    "osm_type": kind,
                    "osm_id": obj.id,
                    "lat": lat,
                    "lon": lon,
                    "names": names,
                    "rank": rank,
                    "construction": is_construction(tags),
                    "tags": tags,
                }
            )
    # Two graphs: tracks under construction only (tried first), then with the existing metro too
    # (needed to start the line B extension from the current Ramonville station).
    graphs = []
    for only_construction in (True, False):
        graph: dict[int, list[tuple[int, float]]] = {}
        for a, b, w, building in edges:
            if building or not only_construction:
                graph.setdefault(a, []).append((b, w))
                graph.setdefault(b, []).append((a, w))
        graphs.append(graph)
    return candidates, graphs, coords


def match_station(station, candidates, same_station: bool):
    best = None
    for cand in candidates:
        score = max(name_score(station.name, n) for n in cand["names"])
        if cand["construction"]:
            if score < MIN_SCORE:
                continue
        elif score < 1.0:
            continue  # existing objects only with the very same name
        key = (cand["construction"], cand["rank"], score)
        if best is None or key > best[0]:
            best = (key, cand, score)
    if best is None:
        return None
    _, cand, score = best
    what = "station" if cand["rank"] == 2 else "quai"
    if cand["construction"]:
        precision = f"station exacte (OSM : {what} en construction)"
    elif same_station:
        precision = f"station exacte (OSM : {what} existante)"
    else:
        precision = f"approximative (OSM : {what} existante de même nom, la future station est à proximité)"
    return cand, score, precision


def nearest_node(graph, coords, lat, lon):
    best, best_d = None, float("inf")
    for ref in graph:
        la, lo = coords[ref]
        d = haversine_m(lat, lon, la, lo)
        if d < best_d:
            best, best_d = ref, d
    return best, best_d


def shortest_path(graph, start, goal):
    dist, prev, heap = {start: 0.0}, {}, [(0.0, start)]
    while heap:
        d, node = heapq.heappop(heap)
        if node == goal:
            path = [node]
            while node in prev:
                node = prev[node]
                path.append(node)
            return d, path[::-1]
        if d > dist.get(node, float("inf")):
            continue
        for nxt, w in graph.get(node, []):
            nd = d + w
            if nd < dist.get(nxt, float("inf")):
                dist[nxt], prev[nxt] = nd, node
                heapq.heappush(heap, (nd, nxt))
    return None, None


def simplify(points, tolerance_m=SIMPLIFY_M):
    """Douglas-Peucker on (lat, lon) points, using a local metric projection."""
    if len(points) < 3:
        return list(points)
    lat0 = math.radians(points[0][0])
    xy = [(math.radians(lon) * 6371008.8 * math.cos(lat0), math.radians(lat) * 6371008.8) for lat, lon in points]
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        (x1, y1), (x2, y2) = xy[i], xy[j]
        seg = math.hypot(x2 - x1, y2 - y1)
        best_k, best_d = None, -1.0
        for k in range(i + 1, j):
            x0, y0 = xy[k]
            if seg == 0:
                d = math.hypot(x0 - x1, y0 - y1)
            else:
                d = abs((x2 - x1) * (y1 - y0) - (x1 - x0) * (y2 - y1)) / seg
            if d > best_d:
                best_k, best_d = k, d
        if best_k is not None and best_d > tolerance_m:
            keep[best_k] = True
            stack += [(i, best_k), (best_k, j)]
    return [p for p, k in zip(points, keep) if k]


def run(args) -> int:
    params_path = Path(args.params)
    params = load_params(params_path)
    base = REPO_ROOT if params_path.resolve().is_relative_to(REPO_ROOT) else params_path.parent
    candidates, graphs, coords = read_osm(Path(args.osm))
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows, features, report = [], [], ["# Extraction OSM des lignes futures", "", LICENCE, ""]
    for line in params["lignes"]:
        stations = load_stations(resolve_path(line["stations"], base), line["id"])
        report += [f"## Ligne {line['nom_court']} ({line['id']})", ""]
        found = {}
        for st in stations:
            same = bool(st.anchor and st.anchor[1])
            match = match_station(st, candidates, same)
            if match is None:
                report.append(f"- {st.order}. {st.name} : NON TROUVÉE")
                continue
            cand, score, precision = match
            url = f"https://www.openstreetmap.org/{cand['osm_type']}/{cand['osm_id']}"
            found[st.order] = (cand["lat"], cand["lon"])
            rows.append(
                {
                    "ligne": line["id"],
                    "ordre": st.order,
                    "nom_officiel": st.name,
                    "lat": f"{cand['lat']:.6f}",
                    "lon": f"{cand['lon']:.6f}",
                    "precision": precision,
                    "osm_type": cand["osm_type"],
                    "osm_id": cand["osm_id"],
                    "osm_nom": cand["names"][0],
                    "score_nom": f"{score:.2f}",
                    "source": url,
                    "licence": LICENCE,
                }
            )
            report.append(f"- {st.order}. {st.name} → « {cand['names'][0]} » ({url}, score {score:.2f}) : {precision}")
        report.append("")
        for a, b in zip(stations, stations[1:]):
            if a.order not in found or b.order not in found:
                continue
            (la, lo_a), (lb, lo_b) = found[a.order], found[b.order]
            straight = haversine_m(la, lo_a, lb, lo_b)
            method, geometry = "droit", [(la, lo_a), (lb, lo_b)]
            for graph in graphs:
                if not graph:
                    continue
                na, da = nearest_node(graph, coords, la, lo_a)
                nb, db = nearest_node(graph, coords, lb, lo_b)
                if da > SNAP_M or db > SNAP_M or na == nb:
                    continue
                length, path = shortest_path(graph, na, nb)
                if path and length <= 3 * straight + 500:
                    geometry = [(la, lo_a)] + simplify([coords[n] for n in path]) + [(lb, lo_b)]
                    method = "osm"
                    break
            report.append(f"- tracé {a.name} → {b.name} : {method}")
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "ligne": line["id"],
                        "de_ordre": a.order,
                        "a_ordre": b.order,
                        "de": a.name,
                        "a": b.name,
                        "methode": method,
                    },
                    "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in geometry]},
                }
            )
        report.append("")

    fields = ["ligne", "ordre", "nom_officiel", "lat", "lon", "precision", "osm_type", "osm_id", "osm_nom",
              "score_nom", "source", "licence"]
    with open(out_dir / "stations_osm.csv", "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    with open(out_dir / "traces_osm.geojson", "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "licence": LICENCE, "features": features}, fh, ensure_ascii=False, indent=1)
    (out_dir / "rapport_osm.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    total = sum(len(load_stations(resolve_path(l["stations"], base), l["id"])) for l in params["lignes"])
    print(f"Stations trouvées dans OSM : {len(rows)}/{total} ; rapport : {out_dir / 'rapport_osm.md'}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Extrait de l'OSM les stations et le tracé des lignes futures.")
    parser.add_argument("--osm", required=True, help="extrait OpenStreetMap (.osm.pbf ou .osm)")
    parser.add_argument("--params", default=str(DEFAULT_PARAMS))
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "build" / "futur-osm"))
    try:
        return run(parser.parse_args(argv))
    except BuildError as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
