"""Updates the JSON-LD Knowledge Graph using Claude API for entity/relationship extraction."""

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import anthropic

from sources.base import SourceItem

GRAPH_PATH = Path(__file__).parent.parent / "knowledge-graph" / "graph.jsonld"

CONTEXT = {
    "@vocab": "https://github.com/aztecher/ckwr/ontology#",
    "ckwr": "https://github.com/aztecher/ckwr/ontology#",
    "schema": "https://schema.org/",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}

EXTRACTION_SYSTEM = """\
You are a Knowledge Graph extraction assistant for Kubernetes and LLM inference projects.
Given a batch of GitHub Issues and Pull Requests from a technical community, extract
entities and relationships and output them as a JSON-LD graph node array.

Entity types:
- ckwr:Person       – contributors (use GitHub login as slug)
- ckwr:Issue        – GitHub issues
- ckwr:PullRequest  – GitHub PRs
- ckwr:Feature      – proposed or discussed features / capabilities
- ckwr:Concept      – technical concepts, algorithms, methodologies
- ckwr:Tool         – software tools or frameworks mentioned
- ckwr:Discussion   – a summary node for this batch (one per source-day)

Relationship properties:
- ckwr:participatesIn  Person → Discussion
- ckwr:mentions        Discussion → any Entity
- ckwr:relatedTo       Entity → Entity  (bidirectional concept links)
- ckwr:resolves        PullRequest → Issue
- ckwr:dependsOn       Entity → Entity
- ckwr:createdBy       Entity → Person
- ckwr:occursIn        Discussion → Component

IRI patterns:
- Person:      ckwr:person/<github-login>
- Issue:       ckwr:issue/<owner>/<repo>/<number>
- PullRequest: ckwr:pr/<owner>/<repo>/<number>
- Feature:     ckwr:feature/<slug>
- Concept:     ckwr:concept/<slug>
- Tool:        ckwr:tool/<slug>
- Discussion:  ckwr:discussion/<source-id-slug>/<YYYY-MM-DD>

Slugs: lowercase, hyphens only.
Return ONLY a raw JSON array of nodes. No markdown, no explanation.
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
    index = {node["@id"]: i for i, node in enumerate(existing) if "@id" in node}
    for node in new_nodes:
        nid = node.get("@id")
        if not nid:
            continue
        if nid in index:
            target = existing[index[nid]]
            for k, v in node.items():
                if k not in target:
                    target[k] = v
                elif isinstance(v, list) and isinstance(target[k], list):
                    seen = {json.dumps(x, sort_keys=True) for x in target[k]}
                    for item in v:
                        serialised = json.dumps(item, sort_keys=True)
                        if serialised not in seen:
                            target[k].append(item)
                            seen.add(serialised)
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


def _build_prompt(source_id: str, component_iri: str, items: list[SourceItem], run_date: date) -> str:
    lines = [
        f"Source: {source_id}",
        f"Component IRI: {component_iri}",
        f"Date: {run_date}",
        f"Items: {len(items)}",
        "",
    ]
    for item in items:
        lines.append("---")
        lines.append(item.to_text())
    return "\n".join(lines)


def update_graph(source_items: dict[str, list[SourceItem]], run_date: date) -> None:
    """Extract entities from all source items and merge into the Knowledge Graph.

    source_items: {source_id: [SourceItem, ...]}
    """
    client = anthropic.Anthropic()
    graph = _load_graph()

    for source_id, items in source_items.items():
        if not items:
            print(f"[KGUpdater] No items for '{source_id}', skipping.")
            continue

        component_iri = items[0].component_iri
        print(f"[KGUpdater] Extracting from '{source_id}' ({len(items)} items)...")

        prompt = _build_prompt(source_id, component_iri, items, run_date)

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
            print(f"[KGUpdater] Merged {len(new_nodes)} nodes from '{source_id}'.")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[KGUpdater] Parse error for '{source_id}': {e}\nRaw output (first 500):\n{raw[:500]}")

    _save_graph(graph)
    print(f"[KGUpdater] Graph saved → {GRAPH_PATH}")
