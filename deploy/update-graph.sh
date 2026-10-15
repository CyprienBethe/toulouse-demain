#!/usr/bin/env bash
# Download the latest graph published by GitHub Actions and restart OTP.
#
# Usage (on the server): deploy/update-graph.sh [--force]
#   --force: download and restart even if the latest release is already installed.
# Run every Monday by the systemd timer toulouse-demain-graph.timer, installed
# by bootstrap.sh (logs: journalctl -u toulouse-demain-graph).
#
# Safety: the files are checked against SHA256SUMS, and the graph is refused
# if it was built by another OTP image than the one in docker-compose.yml.
# OTP is unavailable while it reloads the graph (about 10 s, see CI report);
# the script waits until OTP answers again, and fails if it does not.
#
# Files written:
#   data/otp/   graph.obj, router-config.json, otp-config.json (read by OTP),
#               last-build-report.md and SHA256SUMS of the installed release;
#   data/meta/  scenario-filters.json and scenario-2028.json, served by Caddy
#               under /meta/ for the site.
set -euo pipefail
cd "$(dirname "$0")"

force=false
if [[ "${1:-}" == "--force" ]]; then
  force=true
fi

repo=$(sed -n 's/^GRAPH_REPOSITORY=//p' .env | tr -d '"' | tail -n 1)
if [[ -z "$repo" ]]; then
  echo "ERROR: GRAPH_REPOSITORY is not set in .env" >&2
  exit 1
fi
base_url="https://github.com/${repo}/releases/latest/download"
data_dir=./data/otp
meta_dir=./data/meta
mkdir -p "$data_dir" "$meta_dir"
# Download next to the data (not in /tmp, which may be in memory).
tmp=$(mktemp -d ./data/download.XXXXXX)
trap 'rm -rf "$tmp"' EXIT

echo "$(date -u +%FT%TZ) checking the latest graph of ${repo}"
curl -fsSL --retry 3 -o "$tmp/manifest.txt" "${base_url}/manifest.txt"
curl -fsSL --retry 3 -o "$tmp/SHA256SUMS" "${base_url}/SHA256SUMS"
if [[ "$force" == false && -f "$data_dir/graph.obj" && -f "$data_dir/SHA256SUMS" ]] \
  && cmp -s "$tmp/SHA256SUMS" "$data_dir/SHA256SUMS"; then
  echo "$(date -u +%FT%TZ) already up to date (same release as installed), nothing to do"
  exit 0
fi

while read -r file; do
  [[ "$file" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "ERROR: unexpected file name '${file}'" >&2; exit 1; }
  [[ "$file" == SHA256SUMS ]] && continue
  curl -fsSL --retry 3 -o "$tmp/${file}" "${base_url}/${file}"
done < "$tmp/manifest.txt"
(cd "$tmp" && sha256sum --check --quiet SHA256SUMS)

expected_image=$(grep -oE 'docker\.io/opentripplanner/opentripplanner:[^"[:space:]]+' docker-compose.yml | head -n 1)
built_image=$(cat "$tmp/otp-image.txt")
if [[ "$expected_image" != "$built_image" ]]; then
  echo "ERROR: graph built with ${built_image}, server runs ${expected_image}." >&2
  echo "Update the repository on the server (git pull) or wait for the next build." >&2
  exit 1
fi

cat "$tmp"/graph.obj.gz.part* | gunzip > "$tmp/graph.obj"
cp "$tmp/router-config.json" "$tmp/otp-config.json" "$data_dir/"
cp "$tmp/report.md" "$data_dir/last-build-report.md"
rm -f "$data_dir"/scenario-*.json  # older versions of this script kept them here

# Files for the site, replaced atomically (rename in the same directory);
# a file absent from the release is removed (scenario-2028.json is absent
# when the future feed could not be built).
for name in scenario-filters.json scenario-2028.json; do
  if [[ -f "$tmp/$name" ]]; then
    cp "$tmp/$name" "$meta_dir/.$name.new"
    chmod 644 "$meta_dir/.$name.new"
    mv -f "$meta_dir/.$name.new" "$meta_dir/$name"
  else
    rm -f "$meta_dir/$name"
  fi
done

mv "$tmp/graph.obj" "$data_dir/graph.obj.new"
mv -f "$data_dir/graph.obj.new" "$data_dir/graph.obj"

docker compose up -d --force-recreate otp
echo "$(date -u +%FT%TZ) graph installed, OTP restarting"

# 200 on /otp/actuators/health once the graph is loaded (port bound to 127.0.0.1).
for _ in $(seq 1 60); do
  if curl -fsS -o /dev/null http://127.0.0.1:8080/otp/actuators/health 2>/dev/null; then
    # Recorded only once OTP runs with the new graph: a failed update is retried.
    cp "$tmp/SHA256SUMS" "$data_dir/SHA256SUMS"
    echo "$(date -u +%FT%TZ) OTP is ready"
    exit 0
  fi
  sleep 5
done
echo "ERROR: OTP did not become ready within 5 minutes (docker compose logs otp)" >&2
exit 1
