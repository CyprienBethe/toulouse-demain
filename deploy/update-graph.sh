#!/usr/bin/env bash
# Download the latest graph published by GitHub Actions and restart OTP.
#
# Usage (on the server, in the deploy/ directory): ./update-graph.sh
# Suggested weekly cron, after the Monday CI build (crontab -e):
#   0 7 * * 1 cd /home/<user>/toulouse-demain/deploy && ./update-graph.sh >> update-graph.log 2>&1
#
# Safety: the files are checked against SHA256SUMS, and the graph is refused
# if it was built by another OTP image than the one in docker-compose.yml.
# OTP is unavailable while it reloads the graph (duration: see CI report).
set -euo pipefail
cd "$(dirname "$0")"

repo=$(sed -n 's/^GRAPH_REPOSITORY=//p' .env | tr -d '"' | tail -n 1)
if [[ -z "$repo" ]]; then
  echo "ERROR: GRAPH_REPOSITORY is not set in .env" >&2
  exit 1
fi
base_url="https://github.com/${repo}/releases/latest/download"
data_dir=./data/otp
mkdir -p "$data_dir"
# Download next to the data (not in /tmp, which may be in memory).
tmp=$(mktemp -d ./data/download.XXXXXX)
trap 'rm -rf "$tmp"' EXIT

echo "$(date -u +%FT%TZ) downloading the latest graph from ${repo}"
curl -fsSL --retry 3 -o "$tmp/manifest.txt" "${base_url}/manifest.txt"
while read -r file; do
  [[ "$file" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "ERROR: unexpected file name '${file}'" >&2; exit 1; }
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
mv "$tmp/graph.obj" "$data_dir/graph.obj.new"
mv -f "$data_dir/graph.obj.new" "$data_dir/graph.obj"

docker compose up -d --force-recreate otp
echo "$(date -u +%FT%TZ) graph updated, OTP restarting (check: curl https://<API_DOMAIN>/health)"
