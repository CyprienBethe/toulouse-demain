#!/usr/bin/env python3
"""Extract the future metro stations and a simplified track from an OpenStreetMap extract.

Run in CI (the workspace cannot reach OSM), before build_gtfs_futur.py:

    python scripts/extract_futur_osm.py --osm <region>.osm.pbf --output-dir build/futur-osm

How a station is matched (data/futur/stations_*.csv, line by line):

1. Name. Candidates are station-like OSM objects (station, platform, stop) whose name matches.
   A score of 1.00 means the main ``name`` tag is the same (accents, case and punctuation
   ignored); a match on another key (alt_name, old_name...) is capped at 0.95. Objects tagged
   as under construction (``construction*``) are accepted from 0.85; existing objects need 1.00.
2. Preference. Under construction first, then the candidate closest to the track under
   construction (or, without a track nearby, closest to the neighbouring stations).
3. Geographic guards. A choice is rejected when the straight distance to the previous or next
   station is outside [300 m ; 3.5 km] (3.5 km per station in between when one is missing), or
   when it makes a detour: d(prev, x) + d(x, next) > 2.5 × d(prev, next) + 500 m. The next
   candidate is tried; when none passes, the station is left MISSING (never a false positive).

The track of each hop is the shortest path over the railway ways under construction (then also
the existing metro), simplified; when no path is found the hop is a straight line.

Outputs (data derived under ODbL, © OpenStreetMap contributors):
    stations_osm.csv      position, OSM object and precision of every matched station
    traces_osm.geojson    one LineString per hop
    rapport_osm.md        matched, rejected and missing stations, for human review
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
ALT_NAME_FACTOR = 0.95  # a match on another key than "name" is never worth 1.00
SNAP_M = 300  # max distance between a station and the track, for the shortest path
SIMPLIFY_M = 5  # Douglas-Peucker tolerance
ON_TRACK_M = 30  # an existing stop this close to the track under construction is the station itself
NEAR_TRACK_M = 150  # candidates closer than this to the track are preferred
GUARD_MIN_HOP_M = 300
GUARD_MAX_HOP_M = 3500
DETOUR_RATIO = 2.5
DETOUR_SLACK_M = 500


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
    """2 = station, 1 = platform or stop, 0 = not a station-like object."""
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
    """1.0 only for the same name once accents, case and punctuation are ignored."""
    a, b = normalize_name(expected), normalize_name(candidate)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    shorter, longer = sorted((a, b), key=len)
    if len(shorter) >= 5 and shorter in longer:
        return 0.9
    return min(SequenceMatcher(None, a, b).ratio(), 0.89)


def candidate_score(expected: str, cand: dict) -> tuple[float, str]:
    """Best score over the candidate's names, and the 'key=value' that gave it."""
    best, matched = 0.0, ""
    for key, value in cand["names"]:
        score = name_score(expected, value)
        if key != "name":
            score *= ALT_NAME_FACTOR
        if score > best:
            best, matched = score, f"{key}={value}"
    return round(best, 2), matched


# --------------------------------------------------------------------------- geometry


def _xy(lat: float, lon: float, lat0: float) -> tuple[float, float]:
    r = 6371008.8
    return math.radians(lon) * r * math.cos(math.radians(lat0)), math.radians(lat) * r


def distance_to_segments(lat: float, lon: float, segments) -> float | None:
    """Shortest distance (m) from a point to a list of ((lat, lon), (lat, lon)) segments."""
    if not segments:
        return None
    px, py = _xy(lat, lon, lat)
    best = float("inf")
    for (la, oa), (lb, ob) in segments:
        if abs(la - lat) > 0.05 and abs(lb - lat) > 0.05:
            continue  # more than ~5 km away in latitude: cannot be the closest
        ax, ay = _xy(la, oa, lat)
        bx, by = _xy(lb, ob, lat)
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
        best = min(best, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
    return best if best != float("inf") else None


def simplify(points, tolerance_m=SIMPLIFY_M):
    """Douglas-Peucker on (lat, lon) points, using a local metric projection."""
    if len(points) < 3:
        return list(points)
    lat0 = points[0][0]
    xy = [_xy(lat, lon, lat0) for lat, lon in points]
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


# --------------------------------------------------------------------------- OSM reading


def read_osm(path: Path):
    """Station-like objects, railway graphs and the segments of the track under construction."""
    import osmium  # imported here so that the module can be imported without pyosmium

    candidates, edges, coords = [], [], {}
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
            unique = list({p[0]: p for p in pts}.values())
            lat = sum(p[1] for p in unique) / len(unique)
            lon = sum(p[2] for p in unique) / len(unique)
            kind = "way"
        else:
            continue
        rank = station_rank(tags)
        names = [(k, tags[k]) for k in NAME_KEYS if tags.get(k)]
        if rank and names and in_bbox(lat, lon):
            candidates.append(
                {
                    "osm_type": kind,
                    "osm_id": obj.id,
                    "lat": lat,
                    "lon": lon,
                    "names": names,
                    "label": tags.get("name") or names[0][1],
                    "rank": rank,
                    "construction": is_construction(tags),
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
    segments = [(coords[a], coords[b]) for a, b, _, building in edges if building]
    return candidates, graphs, coords, segments


# --------------------------------------------------------------------------- station choice


def station_candidates(station, candidates, segments) -> list[dict]:
    """Candidates whose name is acceptable for this station, with score and track distance."""
    out = []
    for cand in candidates:
        score, matched = candidate_score(station.name, cand)
        if score < (MIN_SCORE if cand["construction"] else 1.0):
            continue
        out.append(dict(cand, score=score, matched=matched,
                        d_track=distance_to_segments(cand["lat"], cand["lon"], segments)))
    return out


def preference(cand: dict, prev: dict | None, nxt: dict | None):
    """Sort key: under construction, then near the track, then close to the neighbours."""
    near = cand["d_track"] is not None and cand["d_track"] <= NEAR_TRACK_M
    neighbours = sum(haversine_m(cand["lat"], cand["lon"], p["lat"], p["lon"]) for p in (prev, nxt) if p)
    return (not cand["construction"], not near, cand["d_track"] if near else neighbours,
            -cand["rank"], -cand["score"], cand["osm_id"])


def _neighbours(picks: dict, order: int, n: int):
    prev = next(((o, picks[o]) for o in range(order - 1, 0, -1) if picks.get(o)), None)
    nxt = next(((o, picks[o]) for o in range(order + 1, n + 1) if picks.get(o)), None)
    return prev, nxt


def violations(picks: dict, order: int, n: int, cand: dict | None = None) -> tuple[int, int, float, list[str]]:
    """(constraints broken, constraints checked, total excess in m, reasons) for one station."""
    cand = cand or picks[order]
    prev, nxt = _neighbours(picks, order, n)
    broken, checked, excess, reasons = 0, 0, 0.0, []
    for other in (prev, nxt):
        if not other:
            continue
        gap = abs(order - other[0])
        d = haversine_m(cand["lat"], cand["lon"], other[1]["lat"], other[1]["lon"])
        checked += 1
        over = max(0.0, d - GUARD_MAX_HOP_M * gap) + (max(0.0, GUARD_MIN_HOP_M - d) if gap == 1 else 0.0)
        if over > 0:
            broken += 1
            excess += over
            reasons.append(f"{d:.0f} m de la station n° {other[0]}")
    if prev and nxt:
        a = haversine_m(prev[1]["lat"], prev[1]["lon"], cand["lat"], cand["lon"])
        b = haversine_m(cand["lat"], cand["lon"], nxt[1]["lat"], nxt[1]["lon"])
        direct = haversine_m(prev[1]["lat"], prev[1]["lon"], nxt[1]["lat"], nxt[1]["lon"])
        checked += 1
        over = a + b - (DETOUR_RATIO * direct + DETOUR_SLACK_M)
        if over > 0:
            broken += 1
            excess += over
            reasons.append(f"détour de {a + b:.0f} m pour {direct:.0f} m entre les voisines")
    return broken, checked, excess, reasons


def choose_stations(stations, cands_by_order: dict[int, list[dict]]):
    """Pick one candidate (or none) per station, applying preference then the geographic guards."""
    n = len(stations)
    picks = {o: (sorted(c, key=lambda x: preference(x, None, None))[0] if c else None)
             for o, c in cands_by_order.items()}
    for o in range(1, n + 1):  # second pass: closeness to the neighbours picked so far
        if cands_by_order.get(o):
            prev, nxt = _neighbours(picks, o, n)
            picks[o] = sorted(cands_by_order[o], key=lambda x: preference(x, prev and prev[1], nxt and nxt[1]))[0]
    rejected: dict[int, list[str]] = {}
    tried: dict[int, set] = {o: set() for o in range(1, n + 1)}
    for _ in range(sum(len(c) for c in cands_by_order.values()) + n):
        scored = []
        for o in range(1, n + 1):
            if picks.get(o):
                broken, checked, excess, _ = violations(picks, o, n)
                if broken:
                    scored.append((broken / checked, excess, o))
        if not scored:
            break
        _, _, culprit = max(scored)
        bad = picks[culprit]
        _, _, _, reasons = violations(picks, culprit, n)
        rejected.setdefault(culprit, []).append(
            f"{bad['label']} ({bad['osm_type']}/{bad['osm_id']}) : {', '.join(reasons)}")
        tried[culprit].add(bad["osm_id"])
        picks[culprit] = None
        prev, nxt = _neighbours(picks, culprit, n)
        for alt in sorted(cands_by_order[culprit], key=lambda x: preference(x, prev and prev[1], nxt and nxt[1])):
            if alt["osm_id"] in tried[culprit]:
                continue
            if violations(picks, culprit, n, alt)[0] == 0:
                picks[culprit] = alt
                break
            tried[culprit].add(alt["osm_id"])
            rejected[culprit].append(f"{alt['label']} ({alt['osm_type']}/{alt['osm_id']}) : "
                                     + ", ".join(violations(picks, culprit, n, alt)[3]))
    return picks, rejected


def precision_of(cand: dict, same_station: bool) -> str:
    what, existing = ("station", "station existante") if cand["rank"] == 2 else ("quai ou arrêt", "quai ou arrêt existant")
    if cand["construction"]:
        return f"station exacte (OSM : {what} en construction)"
    if same_station:
        return f"station exacte (OSM : {existing}, même station)"
    if cand["d_track"] is not None and cand["d_track"] <= ON_TRACK_M:
        return f"station exacte (OSM : {what} de même nom sur le tracé en construction)"
    where = (f"à {cand['d_track']:.0f} m du tracé en construction" if cand["d_track"] is not None
             else "sans tracé en construction cartographié")
    return f"approximative (OSM : {existing} de même nom, {where})"


# --------------------------------------------------------------------------- track


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


def hop_track(graphs, coords, a, b):
    (la, lo_a), (lb, lo_b) = a, b
    straight = haversine_m(la, lo_a, lb, lo_b)
    for graph in graphs:
        if not graph:
            continue
        na, da = nearest_node(graph, coords, la, lo_a)
        nb, db = nearest_node(graph, coords, lb, lo_b)
        if da > SNAP_M or db > SNAP_M or na == nb:
            continue
        length, path = shortest_path(graph, na, nb)
        if path and length <= 3 * straight + 500:
            return "osm", [(la, lo_a)] + simplify([coords[n] for n in path]) + [(lb, lo_b)]
    return "droit", [(la, lo_a), (lb, lo_b)]


# --------------------------------------------------------------------------- main


def run(args) -> int:
    params_path = Path(args.params)
    params = load_params(params_path)
    base = REPO_ROOT if params_path.resolve().is_relative_to(REPO_ROOT) else params_path.parent
    candidates, graphs, coords, segments = read_osm(Path(args.osm))
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows, features, total = [], [], 0
    report = ["# Extraction OSM des lignes futures", "", LICENCE, "",
              f"Garde-fous : interstation entre {GUARD_MIN_HOP_M} m et {GUARD_MAX_HOP_M} m en ligne droite, "
              f"détour maximal {DETOUR_RATIO} × la distance entre voisines + {DETOUR_SLACK_M} m.", ""]
    for line in params["lignes"]:
        stations = load_stations(resolve_path(line["stations"], base), line["id"])
        total += len(stations)
        cands = {st.order: station_candidates(st, candidates, segments) for st in stations}
        picks, rejected = choose_stations(stations, cands)
        report += [f"## Ligne {line['nom_court']} ({line['id']})", ""]
        found = {}
        for st in stations:
            for reason in rejected.get(st.order, []):
                report.append(f"- {st.order}. {st.name} : candidat REJETÉ {reason}")
            cand = picks.get(st.order)
            if cand is None:
                report.append(f"- {st.order}. {st.name} : MANQUANTE ({len(cands[st.order])} candidat(s) de même nom)")
                continue
            precision = precision_of(cand, bool(st.anchor and st.anchor[1]))
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
                    "osm_nom": cand["label"],
                    "nom_apparie": cand["matched"],
                    "score_nom": f"{cand['score']:.2f}",
                    "distance_trace_m": "" if cand["d_track"] is None else f"{cand['d_track']:.0f}",
                    "source": url,
                    "licence": LICENCE,
                }
            )
            report.append(f"- {st.order}. {st.name} → « {cand['label']} » ({url}, {cand['matched']}, "
                          f"score {cand['score']:.2f}) : {precision}")
        report.append("")
        for a, b in zip(stations, stations[1:]):
            if a.order not in found or b.order not in found:
                continue
            method, geometry = hop_track(graphs, coords, found[a.order], found[b.order])
            report.append(f"- tracé {a.name} → {b.name} : {method}")
            features.append(
                {
                    "type": "Feature",
                    "properties": {"ligne": line["id"], "de_ordre": a.order, "a_ordre": b.order,
                                   "de": a.name, "a": b.name, "methode": method},
                    "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in geometry]},
                }
            )
        report.append("")

    fields = ["ligne", "ordre", "nom_officiel", "lat", "lon", "precision", "osm_type", "osm_id", "osm_nom",
              "nom_apparie", "score_nom", "distance_trace_m", "source", "licence"]
    with open(out_dir / "stations_osm.csv", "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    with open(out_dir / "traces_osm.geojson", "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "licence": LICENCE, "features": features}, fh, ensure_ascii=False, indent=1)
    (out_dir / "rapport_osm.md").write_text("\n".join(report) + "\n", encoding="utf-8")
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
