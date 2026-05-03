# ckwr — Community Knowledge Watch & Report

Daily automated pipeline that collects technical community activity from multiple
information sources, builds a growing Knowledge Graph, and generates human-readable
summaries — all stored as versioned history in this repository.

## Tracked Sources

| Source ID | Type | Target |
|---|---|---|
| `llm-d/sig-autoscaling` | GitHub | llm-d repos — autoscaling issues/PRs |
| `llm-d/sig-benchmarking` | GitHub | llm-d repos — benchmarking issues/PRs |
| `kubernetes/sig-network-multi-network` | GitHub | k8snetworkplumbingwg + kubernetes/community |

Sources are configured in [`config.yaml`](./config.yaml) — add new entries to track more.

## Repository Structure

```
ckwr/
├── config.yaml                          # Source configuration (edit to add sources)
├── knowledge-graph/
│   ├── schema.jsonld                    # OWL ontology (classes & properties)
│   └── graph.jsonld                     # Cumulative Knowledge Graph (JSON-LD)
├── summaries/
│   └── YYYY/MM/YYYY-MM-DD/
│       ├── index.md
│       ├── llm-d_sig-autoscaling.md
│       ├── llm-d_sig-benchmarking.md
│       └── kubernetes_sig-network-multi-network.md
├── scripts/
│   ├── daily_routine.py                 # Orchestrator entry point
│   ├── sources/
│   │   ├── base.py                      # DataSource ABC + SourceItem dataclass
│   │   ├── github.py                    # GitHub Issues/PR adapter
│   │   └── __init__.py                  # SOURCE_REGISTRY
│   ├── kg_updater.py                    # Entity extraction → JSON-LD merge
│   ├── summary_writer.py                # Markdown summary generation
│   └── requirements.txt
└── .github/workflows/
    └── daily_routine.yml                # Runs daily at 09:00 UTC (18:00 JST)
```

## Adding a New Information Source

The system uses a plugin architecture. Each source type is a class implementing
`DataSource` (see `scripts/sources/base.py`).

**Steps to add a new source type** (e.g. web articles, Zhihu, mailing lists):

1. Create `scripts/sources/<type>.py` implementing `DataSource.fetch()`.
2. Register it in `scripts/sources/__init__.py` → `SOURCE_REGISTRY`.
3. Add a block to `config.yaml` with `type: <type>` and source-specific config.

Example stubs are commented out in `config.yaml` (Chipsandcheese, Zhihu).

## Knowledge Graph Format

`knowledge-graph/graph.jsonld` is a **JSON-LD** document (W3C standard).
Compatible with:
- **SPARQL** engines (Apache Jena, Blazegraph, Oxigraph)
- **rdflib** (Python): `g = rdflib.ConjunctiveGraph(); g.parse("graph.jsonld")`
- **LLM RAG pipelines** (readable structured JSON)
- Graph databases that accept JSON-LD import

The ontology (`schema.jsonld`) defines entity classes and relationship properties.
New entities are merged incrementally — existing nodes are updated, not duplicated.

## Summaries

Each daily run writes one Markdown file per source under `summaries/YYYY/MM/YYYY-MM-DD/`.
Contents: Overview · Key Topics · Notable PRs/Issues · Decisions · Concepts & Tools.

These are designed to be the basis for reports in other formats (e.g. Slack digests,
email newsletters, Notion pages).

## Setup

### GitHub Secret Required

Add one secret in **Settings → Secrets and variables → Actions**:

| Secret | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key (for Claude entity extraction and summarisation) |

`GITHUB_TOKEN` is automatically provided by GitHub Actions — no manual setup needed.

### Run Manually

```bash
pip install -r scripts/requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
export GITHUB_TOKEN=ghp_...        # optional, but recommended
python scripts/daily_routine.py
# options:
#   --hours 48       fetch last 48 hours instead of 24
#   --no-push        skip git commit and push
#   --config path    use a different config file
```

## Automation

GitHub Actions runs the pipeline daily at **09:00 UTC (18:00 JST)**.
It can also be triggered manually from the Actions tab with a custom `--hours` value.
