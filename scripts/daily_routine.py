"""Daily routine entry point.

Usage:
    python scripts/daily_routine.py [--hours 24] [--no-push] [--config config.yaml]

Requirements:
    - Claude Code CLI installed and authenticated (`claude` in PATH)
    - GITHUB_TOKEN env var (optional but recommended; 60 req/h without it)
    - Run from repo root or scripts/ directory

Typical invocation via cron wrapper:
    scripts/run_daily.sh
"""

import argparse
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

_SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(_SCRIPTS_DIR))

from sources import SOURCE_REGISTRY, SourceItem
from kg_updater import update_graph
from summary_writer import write_summaries

_REPO_ROOT = _SCRIPTS_DIR.parent


def _check_env() -> bool:
    ok = True
    # Verify claude CLI is available
    result = subprocess.run(["which", "claude"], capture_output=True)
    if result.returncode != 0:
        print("[daily_routine] ERROR: 'claude' CLI not found in PATH.", file=sys.stderr)
        print("[daily_routine]   Install Claude Code: https://claude.ai/code", file=sys.stderr)
        ok = False
    if not os.getenv("GITHUB_TOKEN"):
        print("[daily_routine] GITHUB_TOKEN not set — unauthenticated GitHub API (60 req/h).")
    return ok


def _git_commit_and_push(run_date: date) -> None:
    try:
        subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "add", "knowledge-graph/", "summaries/"],
            check=True,
        )
        diff = subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "diff", "--cached", "--quiet"],
            capture_output=True,
        )
        if diff.returncode == 0:
            print("[daily_routine] Nothing to commit.")
            return
        subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "commit", "-m", f"chore: daily update {run_date}"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "push", "-u", "origin", "HEAD"],
            check=True,
        )
        print(f"[daily_routine] Pushed: chore: daily update {run_date}")
    except subprocess.CalledProcessError as e:
        print(f"[daily_routine] Git error: {e}")


def _load_config(config_path: Path) -> list[dict]:
    with config_path.open() as f:
        cfg = yaml.safe_load(f)
    return cfg.get("sources", [])


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily data collection → Knowledge Graph routine")
    parser.add_argument("--hours", type=int, default=24, help="Hours of history to fetch (default: 24)")
    parser.add_argument("--no-push", action="store_true", help="Skip git commit and push")
    parser.add_argument("--config", type=Path, default=_REPO_ROOT / "config.yaml")
    args = parser.parse_args()

    if not _check_env():
        sys.exit(1)

    run_date = date.today()
    since = datetime.now(tz=timezone.utc) - timedelta(hours=args.hours)
    print(f"[daily_routine] Run date: {run_date} | Fetching since: {since.isoformat()}")

    source_configs = _load_config(args.config)
    if not source_configs:
        print("[daily_routine] No sources configured in config.yaml. Exiting.")
        sys.exit(1)

    all_items: dict[str, list[SourceItem]] = {}

    for cfg in source_configs:
        source_id = cfg["id"]
        source_type = cfg["type"]
        component_iri = cfg["component"]

        adapter_cls = SOURCE_REGISTRY.get(source_type)
        if adapter_cls is None:
            print(f"[daily_routine] Unknown source type '{source_type}' for '{source_id}' — skipping.")
            print(f"[daily_routine]   Available types: {list(SOURCE_REGISTRY)}")
            continue

        print(f"[daily_routine] Fetching '{source_id}' (type={source_type})...")
        adapter = adapter_cls(source_id=source_id, component_iri=component_iri, config=cfg)
        items = adapter.fetch(since=since)
        all_items[source_id] = items

    print("[daily_routine] Updating Knowledge Graph...")
    update_graph(all_items, run_date)

    print("[daily_routine] Writing summaries...")
    write_summaries(all_items, run_date)

    if not args.no_push:
        _git_commit_and_push(run_date)

    print(f"[daily_routine] Done — {run_date}")


if __name__ == "__main__":
    main()
