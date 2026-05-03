"""Daily routine entry point.

Usage:
    python scripts/daily_routine.py [--hours 24] [--no-push] [--config config.yaml]

Required environment variables:
    ANTHROPIC_API_KEY   – Anthropic API key
    GITHUB_TOKEN        – GitHub PAT (optional; unauthenticated = 60 req/h)
                          Automatically available in GitHub Actions as GITHUB_TOKEN.
"""

import argparse
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

# Allow running from repo root or scripts/
_SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(_SCRIPTS_DIR))

from sources import SOURCE_REGISTRY, SourceItem
from kg_updater import update_graph
from summary_writer import write_summaries

_REPO_ROOT = _SCRIPTS_DIR.parent


def _load_config(config_path: Path) -> list[dict]:
    with config_path.open() as f:
        cfg = yaml.safe_load(f)
    return cfg.get("sources", [])


def _check_env() -> bool:
    missing = [v for v in ("ANTHROPIC_API_KEY",) if not os.getenv(v)]
    if missing:
        print(f"[daily_routine] Missing required env vars: {', '.join(missing)}")
        return False
    if not os.getenv("GITHUB_TOKEN"):
        print("[daily_routine] GITHUB_TOKEN not set — using unauthenticated GitHub API (60 req/h).")
    return True


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

    # Collect items from all configured sources
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

    # Update Knowledge Graph
    print("[daily_routine] Updating Knowledge Graph...")
    update_graph(all_items, run_date)

    # Write summaries
    print("[daily_routine] Writing summaries...")
    write_summaries(all_items, run_date)

    # Commit and push
    if not args.no_push:
        _git_commit_and_push(run_date)

    print(f"[daily_routine] Done — {run_date}")


if __name__ == "__main__":
    main()
