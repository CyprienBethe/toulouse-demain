#!/usr/bin/env bash
# Package the OTP graph and its runtime configuration for a GitHub Release.
#
# Usage: scripts/package_graph.sh <otp-base-dir> <otp-image> <report.md> <output-dir>
#
# GitHub limits each release asset to 2 GiB, so graph.obj is compressed and
# cut into parts of 1900 MiB. The server (deploy/update-graph.sh) downloads
# manifest.txt, then every listed file, checks SHA256SUMS and reassembles.
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 <otp-base-dir> <otp-image> <report.md> <output-dir>" >&2
  exit 2
fi
base=$1
image=$2
report=$3
out=$4

rm -rf "$out"
mkdir -p "$out"
gzip -1 -c "$base/graph.obj" | split -b 1900m -d -a 2 - "$out/graph.obj.gz.part"
cp "$base/router-config.json" "$base/otp-config.json" "$out/"
printf '%s\n' "$image" > "$out/otp-image.txt"
cp "$report" "$out/report.md"

cd "$out"
files=(*)
sha256sum "${files[@]}" > SHA256SUMS
printf '%s\n' "${files[@]}" SHA256SUMS > manifest.txt
ls -l
