#!/usr/bin/env bash
# Clip the regional OpenStreetMap extract to the routing zone.
#
# Usage: scripts/clip_osm.sh <input.osm.pbf> <zone.json> <output.osm.pbf> <report.json>
#
# Requires osmium-tool (https://osmcode.org/osmium-tool/). The bbox comes from
# zone.json, computed by scripts/compute_zone.py from the Tisséo stops.
# "complete_ways" keeps every way that crosses the border entirely, so streets
# at the edge of the zone are not cut in the middle.
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 <input.osm.pbf> <zone.json> <output.osm.pbf> <report.json>" >&2
  exit 2
fi
input=$1
zone=$2
output=$3
report=$4

bbox=$(python3 -c 'import json, sys; print(",".join(str(v) for v in json.load(open(sys.argv[1]))["bbox"]))' "$zone")
echo "Clipping ${input} to bbox ${bbox}"

# Warn (without failing) if the zone is not fully inside the extract coverage.
python3 - "$input" "$bbox" <<'PY' || true
import json, subprocess, sys
info = json.loads(subprocess.run(["osmium", "fileinfo", "-j", sys.argv[1]],
                                 check=True, capture_output=True, text=True).stdout)
boxes = info.get("header", {}).get("boxes", [])
zone = [float(v) for v in sys.argv[2].split(",")]
inside = any(b[0] <= zone[0] and b[1] <= zone[1] and b[2] >= zone[2] and b[3] >= zone[3] for b in boxes)
print(f"Extract header boxes: {boxes}; zone inside: {inside}")
if boxes and not inside:
    print("WARNING: the zone goes beyond the OSM extract, streets at the edge will be missing")
PY

mkdir -p "$(dirname "$output")" "$(dirname "$report")"
start=$(date +%s)
osmium extract --bbox "$bbox" --strategy complete_ways --overwrite -o "$output" "$input"
end=$(date +%s)

python3 - "$input" "$output" "$bbox" "$((end - start))" "$report" <<'PY'
import json, os, subprocess, sys
version = subprocess.run(["osmium", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
json.dump({
    "input_bytes": os.path.getsize(sys.argv[1]),
    "output_bytes": os.path.getsize(sys.argv[2]),
    "bbox": sys.argv[3],
    "seconds": int(sys.argv[4]),
    "osmium_version": version,
}, open(sys.argv[5], "w"), indent=2)
PY
echo "Clipped extract written to ${output}"
