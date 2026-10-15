#!/usr/bin/env bash
# Point the DuckDNS subdomain to the current public IPv4 of this machine.
# On Oracle Cloud the address is normally stable; this keeps DuckDNS right if
# it ever changes (and is required for a Raspberry Pi behind a home box).
#
# Usage: deploy/duckdns-update.sh   (reads DUCKDNS_SUBDOMAIN and DUCKDNS_TOKEN from .env)
# Run every 30 minutes by the systemd timer toulouse-demain-duckdns.timer,
# installed by bootstrap.sh (logs: journalctl -u toulouse-demain-duckdns).
# API: https://www.duckdns.org/spec.jsp (without "ip", DuckDNS uses the caller's IPv4).
# The token is a secret: it is never printed, and never put on a command line.
set -euo pipefail
cd "$(dirname "$0")"

read_env() { sed -n "s/^$1=//p" .env | tr -d '"' | tail -n 1; }
subdomain=$(read_env DUCKDNS_SUBDOMAIN)
token=$(read_env DUCKDNS_TOKEN)
if [[ -z "$subdomain" || -z "$token" ]]; then
  echo "ERROR: DUCKDNS_SUBDOMAIN and DUCKDNS_TOKEN must be set in .env" >&2
  exit 1
fi

# The URL (with the token) goes through stdin, so it never shows in `ps`.
# verbose=true: the answer also gives the IP recorded by DuckDNS.
response=$(curl -fsS --retry 3 -K - <<< "url = \"https://www.duckdns.org/update?domains=${subdomain}&token=${token}&verbose=true\"")
echo "DuckDNS answer for ${subdomain}.duckdns.org: $(printf '%s' "$response" | tr -s '\n' ' ')"
[[ "$response" == OK* ]]
