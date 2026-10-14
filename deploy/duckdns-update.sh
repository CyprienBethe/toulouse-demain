#!/usr/bin/env bash
# Point the DuckDNS subdomain to the current public IP of this machine.
# Only needed when the IP can change (e.g. a Raspberry Pi behind a home box).
#
# Usage: ./duckdns-update.sh   (reads DUCKDNS_SUBDOMAIN and DUCKDNS_TOKEN from .env)
# Suggested cron, every 5 minutes:
#   */5 * * * * cd /home/<user>/toulouse-demain/deploy && ./duckdns-update.sh > /dev/null
# API: https://www.duckdns.org/spec.jsp (without "ip", DuckDNS uses the caller's IPv4).
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
response=$(curl -fsS --retry 3 -K - <<< "url = \"https://www.duckdns.org/update?domains=${subdomain}&token=${token}\"")
echo "DuckDNS answer: ${response}"
[[ "$response" == OK* ]]
