# ckwr — Community Knowledge Watch & Report

Daily automated pipeline that collects Slack discussions from the **llm-d** and **Kubernetes** communities, builds a growing Knowledge Graph, and generates human-readable summaries — all stored as versioned history in this repository.

## Tracked Channels

| Workspace | Channel |
|---|---|
| llm-d | `#sig-autoscaling` |
| llm-d | `#sig-benchmarking` |
| Kubernetes | `#sig-network-multi-network` |

## Repository Structure

```
ckwr/
├── knowledge-graph/
│   ├── schema.jsonld        # OWL ontology (classes & properties)
│   └── graph.jsonld         # Cumulative Knowledge Graph (JSON-LD)
├── summaries/
│   └── YYYY/MM/YYYY-MM-DD/
│       ├── index.md                          # Daily index
│       ├── llm-d_sig-autoscaling.md
│       ├── llm-d_sig-benchmarking.md
│       └── kubernetes_sig-network-multi-network.md
├── scripts/
│   ├── daily_routine.py     # Entry point
│   ├── slack_reader.py      # Slack Web API reader
│   ├── kg_updater.py        # Knowledge Graph updater (Claude API)
│   ├── summary_writer.py    # Markdown summary generator (Claude API)
│   └── requirements.txt
└── .github/workflows/
    └── daily_routine.yml    # GitHub Actions: runs daily at 09:00 UTC
```

## Knowledge Graph Format

The KG is stored as **JSON-LD** (`knowledge-graph/graph.jsonld`), a W3C standard format for Linked Data. It is compatible with:

- **SPARQL** query engines (Apache Jena, Blazegraph, etc.)
- **rdflib** (Python)
- **Graph databases** (e.g. import via JSON-LD context)
- **LLM retrieval** pipelines (structured JSON is directly readable)

The ontology (`schema.jsonld`) defines entity classes (Person, Issue, PR, Feature, Concept, Tool, Discussion) and relationships (participatesIn, mentions, relatedTo, resolves, dependsOn, occursIn).

## Summaries

Each daily run produces one Markdown file per channel under `summaries/YYYY/MM/YYYY-MM-DD/`. Summaries include:
- Overview of the day's themes
- Key topics discussed
- Decisions / action items
- Mentioned issues, PRs, and external resources

## Setup

### Required GitHub Secrets

Add the following in **Settings → Secrets and variables → Actions**:

| Secret | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `SLACK_TOKEN_LLMD` | Slack user token (`xoxp-...`) for the llm-d workspace |
| `SLACK_TOKEN_K8S` | Slack user token (`xoxp-...`) for kubernetes.slack.com |

### How to get Slack user tokens

1. Visit `https://<workspace>.slack.com/account/settings`
2. Under **Personal Access Tokens** (or use the legacy token endpoint for personal use)
3. Alternatively: create a Slack App in each workspace with `channels:history`, `channels:read`, `users:read` scopes and use its OAuth token

### Run Manually

```bash
pip install -r scripts/requirements.txt
export ANTHROPIC_API_KEY=...
export SLACK_TOKEN_LLMD=...
export SLACK_TOKEN_K8S=...
python scripts/daily_routine.py
# or: python scripts/daily_routine.py --hours 48 --no-push
```

## Automation

A GitHub Actions workflow (`daily_routine.yml`) runs automatically every day at **09:00 UTC (18:00 JST)**. It can also be triggered manually via the Actions tab with a custom `hours` parameter.
