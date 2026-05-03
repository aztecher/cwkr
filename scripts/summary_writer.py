"""Generates Markdown summaries for each source using Claude API."""

from datetime import date
from pathlib import Path

import anthropic

from sources.base import SourceItem

SUMMARIES_DIR = Path(__file__).parent.parent / "summaries"

SUMMARY_SYSTEM = """\
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


def _build_content(items: list[SourceItem]) -> str:
    if not items:
        return "(no items)"
    return "\n\n---\n\n".join(item.to_text() for item in items)


def write_summaries(source_items: dict[str, list[SourceItem]], run_date: date) -> None:
    """Generate and save a Markdown summary per source.

    source_items: {source_id: [SourceItem, ...]}
    """
    client = anthropic.Anthropic()
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

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SUMMARY_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Source: {source_id}\n"
                        f"Date: {run_date}\n"
                        f"Items: {len(items)}\n\n"
                        + _build_content(items)
                    ),
                }
            ],
        )

        body = response.content[0].text
        out_path.write_text(f"# {source_id} — {run_date}\n\n{body}\n", encoding="utf-8")
        print(f"[SummaryWriter] Written: {out_path.name}")

        first_heading = next((l.lstrip("#").strip() for l in body.splitlines() if l.startswith("##")), "")
        index_lines.append(f"- [{source_id}]({out_path.name}): {first_heading}")

    index_path = date_dir / "index.md"
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    print(f"[SummaryWriter] Index: {index_path}")
