#!/usr/bin/env python3
"""Run OpenTripPlanner in Docker and measure time and memory.

Usage:
    # Build the graph (blocks until OTP exits):
    python scripts/run_otp.py build --image IMAGE --base-dir build/otp --xmx 12g \
        --report build/report/otp-build.json --log build/report/logs/otp-build.log
    # Start the server in the background and wait until it is ready:
    python scripts/run_otp.py serve --image IMAGE --base-dir build/otp --xmx 6g \
        --report build/report/otp-serve.json --log build/report/logs/otp-serve.log
    # Measure memory after the test queries, then stop the server:
    python scripts/run_otp.py stop --report build/report/otp-serve.json \
        --log build/report/logs/otp-serve.log

Memory figures:
- "container memory" is what `docker stats` reports (cgroup usage without the
  file cache), sampled every few seconds: an upper bound of what OTP needs
  with the given -Xmx, because the JVM may keep garbage until it is forced to
  collect it.
- "live heap after GC" is read from the JVM garbage-collector log: the largest
  heap size right after a collection, a closer estimate of the real need.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

CONTAINER_BASE_DIR = "/var/opentripplanner"
UNITS = {
    "b": 1, "kb": 1000, "mb": 1000**2, "gb": 1000**3, "tb": 1000**4,
    "kib": 1024, "mib": 1024**2, "gib": 1024**3, "tib": 1024**4,
}
GC_LINE = re.compile(r"(\d+)([KMG])->(\d+)([KMG])\((\d+)([KMG])\)")
GC_UNITS = {"K": 1 / 1024, "M": 1, "G": 1024}


def docker(*args: str, check: bool = True) -> str:
    result = subprocess.run(["docker", *args], capture_output=True, text=True, check=check)
    return result.stdout.strip()


def memory_bytes(container: str) -> int | None:
    """Current memory use of a running container, from `docker stats`."""
    raw = docker("stats", "--no-stream", "--format", "{{.MemUsage}}", container, check=False)
    match = re.match(r"\s*([\d.]+)\s*([A-Za-z]+)", raw)
    if not match:
        return None
    return int(float(match.group(1)) * UNITS.get(match.group(2).lower(), 0)) or None


def is_running(container: str) -> bool:
    return docker("inspect", "-f", "{{.State.Running}}", container, check=False) == "true"


def save_logs(container: str, log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["docker", "logs", container], capture_output=True, text=True)
    log_file.write_text(result.stdout + result.stderr, encoding="utf-8", errors="replace")


def max_live_heap_mib(gc_log: Path) -> float | None:
    """Largest heap size right after a garbage collection, in MiB."""
    if not gc_log.exists():
        return None
    best = None
    for line in gc_log.read_text(encoding="utf-8", errors="replace").splitlines():
        match = GC_LINE.search(line)
        if match:
            after = int(match.group(3)) * GC_UNITS[match.group(4)]
            best = after if best is None else max(best, after)
    return round(best, 1) if best is not None else None


def start_container(name: str, image: str, base_dir: Path, xmx: str, gc_log_name: str,
                    otp_args: list[str], port: int | None = None) -> None:
    docker("rm", "-f", name, check=False)
    java_options = f"-Xmx{xmx} -Xlog:gc:file={CONTAINER_BASE_DIR}/{gc_log_name}"
    command = ["run", "-d", "--name", name, "-e", f"JAVA_TOOL_OPTIONS={java_options}",
               "-v", f"{base_dir.resolve()}:{CONTAINER_BASE_DIR}"]
    if port:
        command += ["-p", f"127.0.0.1:{port}:8080"]
    docker(*command, image, *otp_args)


def write_report(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    existing.update(data)
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def command_build(args: argparse.Namespace) -> int:
    name = "otp-build"
    graph = args.base_dir / "graph.obj"
    graph.unlink(missing_ok=True)
    start_container(name, args.image, args.base_dir, args.xmx, "gc-build.log", ["--build", "--save"])
    started = time.monotonic()
    peak = 0
    timed_out = False
    while is_running(name):
        peak = max(peak, memory_bytes(name) or 0)
        if time.monotonic() - started > args.timeout:
            timed_out = True
            docker("kill", name, check=False)
            break
        time.sleep(3)
    seconds = round(time.monotonic() - started)
    state = docker("inspect", "-f", "{{.State.ExitCode}} {{.State.OOMKilled}}", name, check=False).split()
    save_logs(name, args.log)
    docker("rm", "-f", name, check=False)

    exit_code = int(state[0]) if state else -1
    success = exit_code == 0 and graph.exists() and not timed_out
    write_report(args.report, {
        "image": args.image,
        "xmx": args.xmx,
        "success": success,
        "exit_code": exit_code,
        "oom_killed": len(state) > 1 and state[1] == "true",
        "timed_out": timed_out,
        "duration_seconds": seconds,
        "peak_container_memory_bytes": peak or None,
        "max_live_heap_after_gc_mib": max_live_heap_mib(args.base_dir / "gc-build.log"),
        "graph_bytes": graph.stat().st_size if graph.exists() else None,
    })
    print(f"OTP build finished in {seconds} s, success={success}, peak memory={peak} bytes")
    return 0 if success else 1


def command_serve(args: argparse.Namespace) -> int:
    name = "otp-serve"
    start_container(name, args.image, args.base_dir, args.xmx, "gc-serve.log",
                    ["--load", "--serve"], port=args.port)
    health = f"http://127.0.0.1:{args.port}/otp/actuators/health"
    started = time.monotonic()
    peak = 0
    ready = False
    while time.monotonic() - started < args.timeout:
        if not is_running(name):
            break
        peak = max(peak, memory_bytes(name) or 0)
        try:
            with urllib.request.urlopen(health, timeout=5) as response:
                if response.status == 200:
                    ready = True
                    break
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(3)
    seconds = round(time.monotonic() - started)
    write_report(args.report, {
        "image": args.image,
        "xmx": args.xmx,
        "ready": ready,
        "startup_seconds": seconds,
        "peak_container_memory_during_startup_bytes": peak or None,
        "container_memory_when_ready_bytes": memory_bytes(name) if ready else None,
    })
    if not ready:
        save_logs(name, args.log)
        print(f"OTP server not ready after {seconds} s", file=sys.stderr)
        return 1
    print(f"OTP server ready in {seconds} s")
    return 0


def command_stop(args: argparse.Namespace) -> int:
    name = "otp-serve"
    data = {"container_memory_after_queries_bytes": memory_bytes(name) if is_running(name) else None}
    save_logs(name, args.log)
    docker("rm", "-f", name, check=False)
    if args.base_dir:
        data["max_live_heap_after_gc_mib"] = max_live_heap_mib(args.base_dir / "gc-serve.log")
    write_report(args.report, data)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "serve", "stop"):
        p = sub.add_parser(command)
        p.add_argument("--report", type=Path, required=True)
        p.add_argument("--log", type=Path, required=True)
        p.add_argument("--base-dir", type=Path, required=command != "stop")
        if command != "stop":
            p.add_argument("--image", required=True)
            p.add_argument("--xmx", required=True, help="JVM max heap, e.g. 12g")
        if command == "build":
            p.add_argument("--timeout", type=int, default=5400, help="seconds")
        if command == "serve":
            p.add_argument("--port", type=int, default=8080)
            p.add_argument("--timeout", type=int, default=1200, help="seconds")
    args = parser.parse_args()
    return {"build": command_build, "serve": command_serve, "stop": command_stop}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
