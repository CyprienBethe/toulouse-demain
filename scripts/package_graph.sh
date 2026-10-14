#!/usr/bin/env bash
# Package the OTP graph and its runtime configuration for a GitHub Release.
#
# Usage: scripts/package_graph.sh <otp-base-dir> <otp-image> <report.md> <output-dir> [extra files...]
#
# Extra files (for example scenario-filters.json and scenario-2028.json for the
# front-end) are published next to the graph, under their own name.
#
# GitHub limits each release asset to 2 GiB, so graph.obj is compressed and
# cut into parts of 1900 MiB. The server (deploy/update-graph.sh) downloads
# manifest.txt, then every listed file, checks SHA256SUMS and reassembles.
set -euo pipefail

if [[ $# -lt 4 ]]; then
  echo "usage: $0 <otp-base-dir> <otp-image> <report.md> <output-dir> [extra files...]" >&2
  exit 2
fi
base=$1
image=$2
report=$3
out=$4
shift 4

rm -rf "$out"
mkdir -p "$out"
gzip -1 -c "$base/graph.obj" | split -b 1900m -d -a 2 - "$out/graph.obj.gz.part"
cp "$base/router-config.json" "$base/otp-config.json" "$out/"
printf '%s\n' "$image" > "$out/otp-image.txt"
cp "$report" "$out/report.md"
for extra in "$@"; do
  cp "$extra" "$out/"
done

cd "$out"
files=(*)
sha256sum "${files[@]}" > SHA256SUMS
printf '%s\n' "${files[@]}" SHA256SUMS > manifest.txt
ls -l
