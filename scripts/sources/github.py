"""GitHub data source adapter.

Fetches Issues and Pull Requests updated within the requested time window.
Filters by label and/or search terms defined in config.yaml.

Authentication:
  Set GITHUB_TOKEN env var (fine-grained PAT or classic PAT with public_repo scope).
  Without a token, the unauthenticated rate limit is 60 req/h — sufficient for
  small runs but GitHub Actions automatically provides GITHUB_TOKEN (5000 req/h).
"""

import os
import time
from datetime import datetime, timezone
from typing import Any

import requests

from .base import DataSource, SourceItem

_API = "https://api.github.com"
_ACCEPT = "application/vnd.github+json"
_API_VER = "2022-11-28"


class GitHubSource(DataSource):
    source_type = "github"

    def __init__(self, source_id: str, component_iri: str, config: dict[str, Any]) -> None:
        super().__init__(source_id, component_iri, config)
        token = os.getenv("GITHUB_TOKEN", "")
        self._headers = {
            "Accept": _ACCEPT,
            "X-GitHub-Api-Version": _API_VER,
            **({"Authorization": f"Bearer {token}"} if token else {}),
        }
        self._repos: list[str] = config.get("repos", [])
        self._filter_labels: set[str] = set(config.get("labels", []))
        self._search_terms: list[str] = [t.lower() for t in config.get("search_terms", [])]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _paginate(self, url: str, params: dict | None = None) -> list[dict]:
        results: list[dict] = []
        while url:
            resp = requests.get(url, headers=self._headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            results.extend(data if isinstance(data, list) else data.get("items", []))
            params = None
            url = resp.links.get("next", {}).get("url", "")
            time.sleep(0.3)
        return results

    def _fetch_issues(self, repo: str, since: datetime) -> list[dict]:
        return self._paginate(
            f"{_API}/repos/{repo}/issues",
            {"state": "all", "since": since.isoformat(), "per_page": 100, "sort": "updated"},
        )

    def _matches(self, raw: dict) -> bool:
        """Return True if the item passes label or search-term filters."""
        if not self._filter_labels and not self._search_terms:
            return True
        issue_labels = {lbl["name"] for lbl in raw.get("labels", [])}
        if self._filter_labels and issue_labels & self._filter_labels:
            return True
        if self._search_terms:
            haystack = f"{raw.get('title', '')} {raw.get('body') or ''}".lower()
            if any(term in haystack for term in self._search_terms):
                return True
        return False

    def _parse_dt(self, s: str) -> datetime:
        return datetime.fromisoformat(s.rstrip("Z")).replace(tzinfo=timezone.utc)

    def _to_item(self, raw: dict, repo: str) -> SourceItem:
        is_pr = "pull_request" in raw
        return SourceItem(
            source_id=self.source_id,
            item_id=f"{repo}#{raw['number']}",
            title=raw.get("title", ""),
            body=raw.get("body") or "",
            url=raw.get("html_url", ""),
            author=raw.get("user", {}).get("login", ""),
            created_at=self._parse_dt(raw["created_at"]),
            updated_at=self._parse_dt(raw["updated_at"]),
            item_type="pr" if is_pr else "issue",
            component_iri=self.component_iri,
            labels=[lbl["name"] for lbl in raw.get("labels", [])],
            metadata={
                "repo": repo,
                "number": raw["number"],
                "state": raw.get("state"),
                "comments": raw.get("comments", 0),
                "is_draft": raw.get("draft", False),
            },
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fetch(self, since: datetime) -> list[SourceItem]:
        items: list[SourceItem] = []
        seen: set[str] = set()

        for repo in self._repos:
            print(f"  [GitHub] {repo} ...")
            try:
                raw_list = self._fetch_issues(repo, since)
            except requests.HTTPError as exc:
                code = exc.response.status_code
                if code == 404:
                    print(f"  [GitHub] Repo not found: {repo} (skipping)")
                    continue
                if code == 403:
                    print(f"  [GitHub] Rate limited or forbidden for {repo} (skipping)")
                    continue
                raise

            for raw in raw_list:
                if not self._matches(raw):
                    continue
                item = self._to_item(raw, repo)
                if item.item_id not in seen:
                    seen.add(item.item_id)
                    items.append(item)

        print(f"  [GitHub] '{self.source_id}': {len(items)} items")
        return items
