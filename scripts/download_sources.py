#!/usr/bin/env python3
"""Download the raw data sources listed in config/sources.json.

Usage:
    python scripts/download_sources.py --config config/sources.json \
        --output-dir build/raw --report build/report/sources.json

Only the Python standard library is used. Each file is streamed to disk,
its SHA-256 is computed on the fly, and a small JSON report is written so the
CI report can show what was actually downloaded (size, date, checksum).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = "toulouse-demain-pipeline (+https://github.com/CyprienBethe/toulouse-demain)"
CHUNK_SIZE = 1024 * 1024
RETRIES = 3


def download(url: str, destination: Path) -> dict:
    """Stream one URL to disk and return metadata about the download."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".part")
    last_error: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        started = time.monotonic()
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=120) as response, tmp.open("wb") as out:
                sha256 = hashlib.sha256()
                size = 0
                while True:
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    out.write(chunk)
                    sha256.update(chunk)
                    size += len(chunk)
                headers = response.headers
                final_url = response.geturl()
            tmp.replace(destination)
            return {
                "url": url,
                "final_url": final_url,
                "file": str(destination),
                "bytes": size,
                "sha256": sha256.hexdigest(),
                "last_modified": headers.get("Last-Modified"),
                "seconds": round(time.monotonic() - started, 1),
                "attempts": attempt,
            }
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
            print(f"  attempt {attempt}/{RETRIES} failed: {error}", file=sys.stderr)
            time.sleep(5 * attempt)
    raise RuntimeError(f"download failed for {url}: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    sources = json.loads(args.config.read_text(encoding="utf-8"))["sources"]
    report: dict[str, dict] = {}
    failed = False
    for name, source in sources.items():
        print(f"Downloading {name}: {source['url']}")
        try:
            report[name] = download(source["url"], args.output_dir / source["file"])
            report[name]["page"] = source.get("page")
            print(f"  ok, {report[name]['bytes']} bytes")
        except RuntimeError as error:
            report[name] = {"url": source["url"], "error": str(error)}
            failed = True
            print(f"  ERROR: {error}", file=sys.stderr)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
