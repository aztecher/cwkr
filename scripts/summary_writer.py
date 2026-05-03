"""Generates Markdown summaries for each source using Claude Code CLI."""

import subprocess
import sys
from datetime import date
from pathlib import Path

from sources.base import SourceItem

SUMMARIES_DIR = Path(__file__).parent.parent / "summaries"

_SUMMARY_PROMPT = """\
You are a technical writer summarising GitHub activity for Kubernetes and LLM inference communities.
Given a list of Issues and Pull Requests, produce a concise Markdown summary.

Structure:
## Overview
One paragraph describing the overall themes of today's activity.

## Key Topics
Bullet list of main topics with brief descriptions.

## Notable PRs / Issues
Bullet list: link title to URL, include state (open/closed/merged) and one-line description.

## Decisions / Action Items
Bullet list of decisions made or next steps identified (skip if none).

## Mentioned Concepts & Tools
Bullet list of technical concepts, tools, or projects referenced (skip if none).

Write in English. Be concise and technical. Omit pleasantries.
If there are no items, write a single line: _No activity in this period._

"""


def _call_claude(prompt: str, timeout: int = 300) -> str:
    """Invoke Claude Code CLI non-interactively and return stdout."""
    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        print("[SummaryWriter] ERROR: 'claude' command not found. Is Claude Code CLI installed?", file=sys.stderr)
        raise
    except subprocess.TimeoutExpired:
        print(f"[SummaryWriter] ERROR: claude CLI timed out after {timeout}s.", file=sys.stderr)
        raise
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI exited {result.returncode}:\n{result.stderr[:500]}")
    return result.stdout.strip()


def _build_content(items: list[SourceItem]) -> str:
    if not items:
        return "(no items)"
    return "\n\n---\n\n".join(item.to_text() for item in items)


def write_summaries(source_items: dict[str, list[SourceItem]], run_date: date) -> None:
    """Generate and save a Markdown summary per source."""
    date_dir = SUMMARIES_DIR / str(run_date.year) / f"{run_date.month:02d}" / str(run_date)
    date_dir.mkdir(parents=True, exist_ok=True)

    index_lines: list[str] = [f"# Daily Summary — {run_date}\n"]

    for source_id, items in source_items.items():
        slug = source_id.replace("/", "_")
        out_path = date_dir / f"{slug}.md"

        if not items:
            out_path.write_text(
                f"# {source_id} — {run_date}\n\n_No activity in this period._\n",
                encoding="utf-8",
            )
            index_lines.append(f"- [{source_id}]({out_path.name}): no activity")
            continue

        print(f"[SummaryWriter] Summarising '{source_id}' ({len(items)} items)...")

        prompt = (
            _SUMMARY_PROMPT
            + f"Source: {source_id}\n"
            + f"Date: {run_date}\n"
            + f"Items: {len(items)}\n\n"
            + _build_content(items)
        )

        try:
            body = _call_claude(prompt)
        except Exception as e:
            print(f"[SummaryWriter] Claude CLI error for '{source_id}': {e}")
            body = f"_Summary generation failed: {e}_"

        out_path.write_text(f"# {source_id} — {run_date}\n\n{body}\n", encoding="utf-8")
        print(f"[SummaryWriter] Written: {out_path.name}")

        first_heading = next((l.lstrip("#").strip() for l in body.splitlines() if l.startswith("##")), "")
        index_lines.append(f"- [{source_id}]({out_path.name}): {first_heading}")

    index_path = date_dir / "index.md"
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    print(f"[SummaryWriter] Index: {index_path}")
