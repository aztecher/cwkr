"""Daily routine entry point.

Usage:
    python scripts/daily_routine.py [--hours 24]

Required environment variables:
    ANTHROPIC_API_KEY   – Anthropic API key
    SLACK_TOKEN_LLMD    – Slack user/bot token for the llm-d workspace
    SLACK_TOKEN_K8S     – Slack user/bot token for the kubernetes workspace
"""

import argparse
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Add scripts dir to path when running from repo root
sys.path.insert(0, str(Path(__file__).parent))

from slack_reader import SlackReader, WORKSPACES
from kg_updater import update_graph
from summary_writer import write_summaries


def _check_env() -> bool:
    missing = [v for v in ("ANTHROPIC_API_KEY", "SLACK_TOKEN_LLMD", "SLACK_TOKEN_K8S") if not os.getenv(v)]
    if missing:
        print(f"[daily_routine] Missing required environment variables: {', '.join(missing)}")
        return False
    return True


def _git_commit_and_push(run_date: date) -> None:
    repo_root = Path(__file__).parent.parent
    try:
        subprocess.run(["git", "-C", str(repo_root), "add", "knowledge-graph/", "summaries/"], check=True)
        msg = f"chore: daily update {run_date}"
        result = subprocess.run(
            ["git", "-C", str(repo_root), "diff", "--cached", "--quiet"],
            capture_output=True,
        )
        if result.returncode == 0:
            print("[daily_routine] No changes to commit.")
            return
        subprocess.run(["git", "-C", str(repo_root), "commit", "-m", msg], check=True)
        subprocess.run(["git", "-C", str(repo_root), "push", "origin", "HEAD"], check=True)
        print(f"[daily_routine] Committed and pushed: {msg}")
    except subprocess.CalledProcessError as e:
        print(f"[daily_routine] Git error: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily Slack → Knowledge Graph routine")
    parser.add_argument("--hours", type=int, default=24, help="Hours of history to fetch (default: 24)")
    parser.add_argument("--no-push", action="store_true", help="Skip git commit and push")
    args = parser.parse_args()

    if not _check_env():
        sys.exit(1)

    run_date = date.today()
    print(f"[daily_routine] Starting run for {run_date} (past {args.hours}h)")

    # Collect messages from all configured channels
    channel_messages: dict[str, list] = {}

    for workspace_name, ws_config in WORKSPACES.items():
        token = os.environ[ws_config["token_env"]]
        reader = SlackReader(token)
        for channel in ws_config["channels"]:
            key = f"{workspace_name}/{channel}"
            print(f"[daily_routine] Reading {key}...")
            messages = reader.read_channel(channel, hours=args.hours)
            channel_messages[key] = messages
            print(f"[daily_routine]   → {len(messages)} messages")

    # Update Knowledge Graph
    print("[daily_routine] Updating Knowledge Graph...")
    update_graph(channel_messages, run_date)

    # Write summaries
    print("[daily_routine] Writing summaries...")
    write_summaries(channel_messages, run_date)

    # Commit and push
    if not args.no_push:
        _git_commit_and_push(run_date)

    print(f"[daily_routine] Done. {run_date}")


if __name__ == "__main__":
    main()
