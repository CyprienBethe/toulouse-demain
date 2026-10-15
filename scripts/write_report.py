#!/usr/bin/env python3
"""Assemble the CI report (Markdown in French + JSON) from the step outputs.

Usage:
    python scripts/write_report.py --report-dir build/report --zone build/zone.json \
        --futur build/gtfs/futur.gtfs.zip --outcome download=success --outcome ... \
        --output build/report/report.md --json build/report/report.json [--futur-required]

--futur-required: the future feed is mandatory (pull requests and branches other
than main). Without it, a failed future feed is a "partial success": the
current network is still tested and published (main, weekly run).

Every input is optional: when a step failed, its file is missing and the
report says so, so that a failed run still produces a readable report. The
report is the only thing we can read from outside GitHub (no log access), so
it also includes the end of the log of each failed step.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import zipfile
from pathlib import Path

MARKER = "<!-- toulouse-demain:graph-report -->"
STEP_LABELS = {
    "download": "Téléchargement des sources",
    "zone": "Calcul de la zone",
    "osm": "Découpage OpenStreetMap",
    "sncf": "Filtrage du GTFS SNCF",
    "futur": "Construction du GTFS futur (data engineer)",
    "build": "Construction du graphe OTP",
    "serve": "Démarrage du serveur OTP",
    "trips": "Trajets de référence",
}
STEP_LOGS = {
    "download": "download.log", "zone": "zone.log", "osm": "osm.log", "sncf": "sncf.log",
    "futur": "futur.log", "build": "otp-build.log", "serve": "otp-serve.log", "trips": "trips.log",
}
OUTCOME_LABELS = {"success": "réussi", "failure": "ÉCHEC", "skipped": "non lancé", "cancelled": "annulé"}


def load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def size(value: int | None) -> str:
    """Decimal units: 1 Mo = 1 000 000 octets."""
    if value is None:
        return "non mesuré"
    for unit, factor in (("Go", 1e9), ("Mo", 1e6), ("ko", 1e3)):
        if value >= factor:
            return f"{value / factor:.2f} {unit}".replace(".", ",")
    return f"{value} o"


def duration(seconds: int | None) -> str:
    if seconds is None:
        return "non mesuré"
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes} min {secs:02d} s" if minutes else f"{secs} s"


def mib(value: float | None) -> str:
    return "non mesuré" if value is None else size(int(value * 1024 * 1024))


def futur_summary(path: Path) -> dict:
    if not path.exists():
        return {"present": False}
    summary: dict = {"present": True, "bytes": path.stat().st_size}
    try:
        with zipfile.ZipFile(path) as archive:
            for name in ("agency.txt", "routes.txt", "stops.txt", "trips.txt"):
                if name in archive.namelist():
                    with archive.open(name) as raw:
                        rows = list(csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig")))
                    summary[name] = len(rows)
                    if name == "routes.txt":
                        summary["routes"] = [r.get("route_short_name") or r.get("route_id") for r in rows]
    except zipfile.BadZipFile:
        summary["error"] = "zip illisible"
    return summary


def tail(path: Path, lines: int = 30) -> str | None:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    return "\n".join(content[-lines:])


def describe_itinerary(itinerary: dict) -> str:
    parts = []
    for leg in itinerary["legs"]:
        if leg["feed"]:
            parts.append(f"{leg['mode']} {leg['line'] or '?'} ({leg['feed']})")
        else:
            parts.append(f"{leg['mode'].lower()} {leg['minutes']} min")
    return " → ".join(parts)


def best(entry: dict | None) -> dict | None:
    if not entry or not entry.get("itineraries"):
        return None
    return min(entry["itineraries"], key=lambda i: i["minutes"])


def report_status(outcomes: dict[str, str], warnings: list, futur_required: bool) -> tuple[bool, bool, str]:
    """(success, futur_ok, status title) of the run.

    The future feed may fail on main and on the weekly run ("partial success": the current
    network is still published). Where it is required (pull requests), its failure fails the run.
    """
    futur_ok = outcomes.get("futur", "success") == "success"
    success = bool(outcomes) and all(v == "success" for k, v in outcomes.items() if k != "futur")
    if not futur_ok and futur_required:
        return False, False, "ÉCHEC (GTFS futur en échec : obligatoire sur une pull request)"
    if not success:
        return False, futur_ok, "ÉCHEC"
    if not futur_ok:
        return True, False, "SUCCÈS PARTIEL (réseau actuel seulement, GTFS futur en échec)"
    if warnings:
        return True, True, "SUCCÈS AVEC AVERTISSEMENTS"
    return True, True, "SUCCÈS"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--zone", type=Path, required=True)
    parser.add_argument("--futur", type=Path, required=True)
    parser.add_argument("--outcome", action="append", default=[], help="step=outcome")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--futur-required", action="store_true",
                        help="a failed future feed fails the run (pull requests)")
    args = parser.parse_args()

    d = args.report_dir
    outcomes = dict(item.split("=", 1) for item in args.outcome)
    sources = load(d / "sources.json") or {}
    zone = load(args.zone)
    osm = load(d / "osm-clip.json")
    sncf = load(d / "sncf-filter.json")
    build = load(d / "otp-build.json") or {}
    serve = load(d / "otp-serve.json") or {}
    trips = load(d / "trips.json")
    futur = futur_summary(args.futur)
    # The future feed is optional on main and on the weekly run: when it fails, the current
    # network is still tested and published ("partial success"). It is required elsewhere.
    warnings = (trips or {}).get("warnings") or []
    success, futur_ok, status = report_status(outcomes, warnings, args.futur_required)

    env = os.environ
    run_url = None
    if env.get("GITHUB_RUN_ID"):
        run_url = f"{env.get('GITHUB_SERVER_URL')}/{env.get('GITHUB_REPOSITORY')}/actions/runs/{env['GITHUB_RUN_ID']}"
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    md = [MARKER, f"## Rapport de construction du graphe : {status}", ""]
    md += [
        f"- Date : {now}",
        f"- Événement : `{env.get('GITHUB_EVENT_NAME', 'local')}`, branche `{env.get('GITHUB_REF_NAME', '?')}`, "
        f"commit `{env.get('GITHUB_SHA', '?')[:7]}`",
        f"- Image OTP : `{build.get('image') or serve.get('image') or '?'}`",
    ]
    if run_url:
        md.append(f"- Exécution : {run_url}")
    try:
        started = int((d / "timing.env").read_text().strip().split("=", 1)[1])
        md.append(f"- Durée depuis le début du workflow : {duration(int(dt.datetime.now().timestamp()) - started)}")
    except (OSError, ValueError, IndexError):
        pass
    md += ["", "### Étapes", "", "| Étape | Résultat |", "| --- | --- |"]
    for step, label in STEP_LABELS.items():
        outcome = OUTCOME_LABELS.get(outcomes.get(step, "skipped"), outcomes.get(step))
        if step == "futur" and outcomes.get(step) == "failure":
            outcome += (" (non toléré sur une pull request : le workflow échoue)" if args.futur_required
                        else " (toléré : graphe construit sans le flux futur)")
        md.append(f"| {label} | {outcome} |")

    md += ["", "### Données", "", "| Source | Taille | SHA-256 (début) | Last-Modified |", "| --- | --- | --- | --- |"]
    for name, info in sources.items():
        if "error" in info:
            md.append(f"| {name} | ÉCHEC : {info['error']} | | |")
        else:
            md.append(f"| {name} | {size(info.get('bytes'))} | `{info.get('sha256', '')[:12]}` | "
                      f"{info.get('last_modified') or '?'} |")
    if zone:
        md.append(f"\nZone (rectangle WGS84 min_lon,min_lat,max_lon,max_lat) : `{','.join(map(str, zone['bbox']))}` "
                  f"— calculée sur {zone['stop_count']} arrêts Tisséo + {zone['buffer_km']} km de marge.")
    if osm:
        md.append(f"OpenStreetMap découpé : {size(osm['input_bytes'])} → {size(osm['output_bytes'])} "
                  f"({osm['osmium_version']}).")
    if sncf:
        st = sncf["files"]["stop_times.txt"]
        md.append(f"GTFS SNCF filtré : {sncf['kept']['trips']} courses, {sncf['kept']['routes']} lignes, "
                  f"{sncf['kept']['stops']} arrêts gardés ; stop_times {st['rows_in']} → {st['rows_out']} lignes ; "
                  f"route_type {sncf['route_types']}.")
    if futur.get("present"):
        md.append(f"GTFS futur : {size(futur.get('bytes'))}, {futur.get('routes.txt', '?')} lignes "
                  f"({', '.join(map(str, futur.get('routes', [])))}), {futur.get('stops.txt', '?')} arrêts, "
                  f"{futur.get('trips.txt', '?')} courses.")
    else:
        md.append("GTFS futur : **absent** (`build/gtfs/futur.gtfs.zip` non produit).")

    xmx_build, xmx_serve = build.get("xmx", "?"), serve.get("xmx", "?")
    md += ["", "### Moteur OpenTripPlanner (mesures de cette exécution)", "", "| Mesure | Valeur |", "| --- | --- |",
           f"| Durée de construction du graphe | {duration(build.get('duration_seconds'))} |",
           f"| Mémoire max du conteneur pendant la construction (-Xmx{xmx_build}) | "
           f"{size(build.get('peak_container_memory_bytes'))} |",
           f"| Tas Java vivant max après GC, construction | {mib(build.get('max_live_heap_after_gc_mib'))} |",
           f"| Taille de graph.obj | {size(build.get('graph_bytes'))} |",
           f"| Démarrage du serveur (chargement du graphe) | {duration(serve.get('startup_seconds'))} |",
           f"| Mémoire du conteneur serveur prêt (-Xmx{xmx_serve}) | {size(serve.get('container_memory_when_ready_bytes'))} |",
           f"| Mémoire du conteneur serveur après les trajets | {size(serve.get('container_memory_after_queries_bytes'))} |",
           f"| Tas Java vivant max après GC, serveur | {mib(serve.get('max_live_heap_after_gc_mib'))} |"]
    if build.get("oom_killed"):
        md.append("\n**La construction a été tuée par manque de mémoire (OOM).**")

    if trips:
        md += ["", f"### Trajets de référence (départ {trips['departure']})", "",
               "| Trajet | Actuel | 2028 | Écart |", "| --- | --- | --- | --- |"]
        for trip in trips["trips"]:
            a, b = best(trip["results"].get("actuel")), best(trip["results"].get("2028"))
            gain = ""
            if a and b:
                delta = b["minutes"] - a["minutes"]
                gain = "identique" if delta == 0 else f"{abs(delta)} min {'plus court' if delta < 0 else 'plus long'} en 2028"
            md.append(f"| {trip['label']} | {str(a['minutes']) + ' min' if a else '—'} | "
                      f"{str(b['minutes']) + ' min' if b else '—'} | {gain} |")
        md.append("")
        for name, scenario in trips.get("scenarios", {}).items():
            md.append(f"- Scénario {name} : {len(scenario.get('excluded_agencies', []))} agence(s) exclue(s), "
                      f"lignes exclues : {', '.join(scenario.get('excluded_routes') or []) or 'aucune'}")
        if trips.get("modes_in_graph"):
            md.append(f"- Modes présents dans le graphe : {', '.join(trips['modes_in_graph'])} ; "
                      f"modes demandés : {', '.join(trips.get('request', {}).get('transit_modes', []))}")
        md += ["", "<details><summary>Détail des trajets</summary>", ""]
        for trip in trips["trips"]:
            md.append(f"**{trip['label']}** ({trip['mode']})")
            for side in ("from", "to"):
                place = trip.get(side)
                if place:
                    md.append(f"- {'Départ' if side == 'from' else 'Arrivée'} : {', '.join(place['matched_names'])} "
                              f"[{place['feed']}, {place['matched_stops']} arrêt(s), {place['lat']}, {place['lon']}]")
                else:
                    md.append(f"- {'Départ' if side == 'from' else 'Arrivée'} : introuvable")
            for scenario, entry in trip["results"].items():
                for itinerary in entry.get("itineraries", []):
                    md.append(f"- {scenario} : {itinerary['minutes']} min, {itinerary['transfers']} corresp., "
                              f"{describe_itinerary(itinerary)}")
                if not entry.get("itineraries"):
                    md.append(f"- {scenario} : aucun itinéraire {entry.get('routing_errors') or entry.get('errors') or ''}")
                md.append(f"  (réponse en {entry['response_ms']} ms)")
            md.append("")
        md.append("</details>")
        if trips["failures"]:
            md += ["", "### Contrôles en échec", ""] + [f"- {f}" for f in trips["failures"]]
        if warnings:
            md += ["", "### Avertissements", ""] + [f"- {w}" for w in warnings]

    failed_logs = [s for s, o in outcomes.items() if o == "failure"]
    if failed_logs:
        md += ["", "### Fin des journaux des étapes en échec"]
        for step in failed_logs:
            content = tail(d / "logs" / STEP_LOGS.get(step, f"{step}.log"))
            md += ["", f"<details><summary>{STEP_LABELS.get(step, step)}</summary>", "", "```",
                   content or "(journal absent)", "```", "</details>"]

    text = "\n".join(md) + "\n"
    if len(text) > 60000:  # GitHub comments are limited to 65536 characters.
        text = text[:60000] + "\n\n(rapport tronqué)\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    args.json.write_text(json.dumps({
        "success": success, "complete": success and futur_ok, "status": status,
        "warnings": warnings, "date": now, "run_url": run_url, "outcomes": outcomes,
        "sources": sources, "zone": zone, "osm": osm, "sncf_kept": (sncf or {}).get("kept"),
        "futur": futur, "otp_build": build, "otp_serve": serve, "trips": trips,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Report written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
