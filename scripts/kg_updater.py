"""Updates the JSON-LD Knowledge Graph using Claude API for entity/relationship extraction."""

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import anthropic

GRAPH_PATH = Path(__file__).parent.parent / "knowledge-graph" / "graph.jsonld"

CONTEXT = {
    "@vocab": "https://github.com/aztecher/ckwr/ontology#",
    "ckwr": "https://github.com/aztecher/ckwr/ontology#",
    "schema": "https://schema.org/",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}

EXTRACTION_SYSTEM = """\
You are a Knowledge Graph extraction assistant for Kubernetes and LLM inference projects.
Given Slack messages from a technical community channel, extract entities and relationships
and output them as JSON-LD graph nodes.

Entity types:
- ckwr:Person       – community members mentioned or participating
- ckwr:Issue        – GitHub issues (e.g. "issue #123")
- ckwr:PullRequest  – GitHub PRs (e.g. "PR #456")
- ckwr:Feature      – proposed or discussed features
- ckwr:Concept      – technical concepts, algorithms, methodologies
- ckwr:Tool         – software tools or frameworks
- ckwr:Discussion   – the conversation itself (one per channel-day batch)

Relationship properties (as JSON-LD object properties):
- ckwr:participatesIn  Person → Discussion
- ckwr:mentions        Discussion → any Entity
- ckwr:relatedTo       Entity → Entity
- ckwr:resolves        PullRequest → Issue
- ckwr:dependsOn       Entity → Entity
- ckwr:createdBy       Entity → Person
- ckwr:occursIn        Discussion → Component (use existing IDs)

IDs must use the pattern:
- Person:      ckwr:person/<slack-username-or-name-slug>
- Issue:       ckwr:issue/<repo>/<number>
- PR:          ckwr:pr/<repo>/<number>
- Feature:     ckwr:feature/<slug>
- Concept:     ckwr:concept/<slug>
- Tool:        ckwr:tool/<slug>
- Discussion:  ckwr:discussion/<channel>/<YYYY-MM-DD>

Slugs should be lowercase-hyphenated.
Return ONLY a JSON array of new or updated nodes (no duplicates with existing IDs unless updating).
Do not wrap in markdown.
"""


def _load_graph() -> dict[str, Any]:
    if GRAPH_PATH.exists():
        with GRAPH_PATH.open() as f:
            return json.load(f)
    return {
        "@context": CONTEXT,
        "meta": {"created": str(date.today()), "last_updated": str(date.today()), "version": "0.1.0"},
        "@graph": [],
    }


def _save_graph(graph: dict[str, Any]) -> None:
    graph["meta"]["last_updated"] = str(date.today())
    with GRAPH_PATH.open("w") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)


def _merge_nodes(existing: list[dict], new_nodes: list[dict]) -> list[dict]:
    """Merge new_nodes into existing, updating by @id."""
    index = {node["@id"]: i for i, node in enumerate(existing) if "@id" in node}
    for node in new_nodes:
        nid = node.get("@id")
        if not nid:
            continue
        if nid in index:
            # Merge: update existing node with new fields, extend list fields
            target = existing[index[nid]]
            for k, v in node.items():
                if k not in target:
                    target[k] = v
                elif isinstance(v, list) and isinstance(target[k], list):
                    seen = {json.dumps(x, sort_keys=True) for x in target[k]}
                    for item in v:
                        if json.dumps(item, sort_keys=True) not in seen:
                            target[k].append(item)
                            seen.add(json.dumps(item, sort_keys=True))
        else:
            existing.append(node)
            index[nid] = len(existing) - 1
    return existing


def _extract_json(text: str) -> list[dict]:
    text = text.strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(text)


def update_graph(channel_messages: dict[str, list[dict[str, Any]]], run_date: date) -> None:
    """Extract entities from all channel messages and update the Knowledge Graph.

    channel_messages: {"workspace/channel": [msg, ...]}
    """
    client = anthropic.Anthropic()
    graph = _load_graph()

    for channel_key, messages in channel_messages.items():
        if not messages:
            print(f"[KGUpdater] No messages for {channel_key}, skipping.")
            continue

        print(f"[KGUpdater] Extracting entities from {channel_key} ({len(messages)} messages)...")

        # Build a readable transcript for Claude
        lines: list[str] = []
        for msg in messages:
            lines.append(f"[{msg['datetime']}] {msg['user_name']}: {msg['text']}")
            for reply in msg.get("replies", []):
                lines.append(f"  ↳ [{reply['datetime']}] {reply['user_name']}: {reply['text']}")
        transcript = "\n".join(lines)

        component_id = f"ckwr:component/{channel_key}"
        prompt = (
            f"Channel: {channel_key}\n"
            f"Date: {run_date}\n"
            f"Component IRI: {component_id}\n\n"
            f"Messages:\n{transcript}\n\n"
            "Extract all entities and relationships. Include a ckwr:Discussion node for this batch."
        )

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=EXTRACTION_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text
        try:
            new_nodes = _extract_json(raw)
            graph["@graph"] = _merge_nodes(graph["@graph"], new_nodes)
            print(f"[KGUpdater] Merged {len(new_nodes)} nodes from {channel_key}.")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[KGUpdater] Failed to parse response for {channel_key}: {e}\nRaw:\n{raw[:500]}")

    _save_graph(graph)
    print(f"[KGUpdater] Knowledge Graph saved to {GRAPH_PATH}.")
