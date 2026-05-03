"""Generates Markdown summaries for each channel using Claude API."""

from datetime import date
from pathlib import Path
from typing import Any

import anthropic

SUMMARIES_DIR = Path(__file__).parent.parent / "summaries"

SUMMARY_SYSTEM = """\
You are a technical writer summarizing Slack discussions for Kubernetes and LLM inference communities.
Produce a concise Markdown summary of the provided channel messages.

Structure your summary as:
## Overview
One paragraph describing the overall themes discussed today.

## Key Topics
Bullet list of main topics with brief descriptions.

## Notable Decisions / Action Items
Bullet list of any decisions made, action items, or next steps mentioned.

## Mentioned Resources
Bullet list of GitHub issues, PRs, external links, or tools referenced (if any).

Write in English. Be concise and technical. Omit pleasantries and off-topic small talk.
"""


def _build_transcript(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for msg in messages:
        lines.append(f"[{msg['datetime']}] {msg['user_name']}: {msg['text']}")
        for reply in msg.get("replies", []):
            lines.append(f"  ↳ [{reply['datetime']}] {reply['user_name']}: {reply['text']}")
    return "\n".join(lines)


def write_summaries(channel_messages: dict[str, list[dict[str, Any]]], run_date: date) -> None:
    """Generate and save a Markdown summary per channel.

    channel_messages: {"workspace/channel": [msg, ...]}
    """
    client = anthropic.Anthropic()
    date_dir = SUMMARIES_DIR / str(run_date.year) / f"{run_date.month:02d}" / str(run_date)
    date_dir.mkdir(parents=True, exist_ok=True)

    index_entries: list[str] = []

    for channel_key, messages in channel_messages.items():
        channel_slug = channel_key.replace("/", "_")
        out_path = date_dir / f"{channel_slug}.md"

        if not messages:
            content = f"# {channel_key} — {run_date}\n\n_No messages in the past 24 hours._\n"
            out_path.write_text(content, encoding="utf-8")
            index_entries.append(f"- [{channel_key}]({out_path.relative_to(SUMMARIES_DIR)}): no activity")
            continue

        print(f"[SummaryWriter] Summarising {channel_key} ({len(messages)} messages)...")
        transcript = _build_transcript(messages)

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SUMMARY_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Channel: {channel_key}\nDate: {run_date}\n\n"
                        f"Messages:\n{transcript}"
                    ),
                }
            ],
        )

        summary_md = response.content[0].text
        header = f"# {channel_key} — {run_date}\n\n"
        out_path.write_text(header + summary_md + "\n", encoding="utf-8")
        print(f"[SummaryWriter] Written: {out_path}")

        first_line = summary_md.split("\n")[0].lstrip("#").strip()
        index_entries.append(f"- [{channel_key}]({out_path.relative_to(SUMMARIES_DIR)}): {first_line}")

    # Write a daily index file
    index_path = date_dir / "index.md"
    index_content = f"# Daily Summary — {run_date}\n\n" + "\n".join(index_entries) + "\n"
    index_path.write_text(index_content, encoding="utf-8")
    print(f"[SummaryWriter] Index written: {index_path}")
