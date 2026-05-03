"""Abstract base class and shared data types for all data source adapters."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SourceItem:
    """Normalised representation of a single item fetched from any data source."""

    source_id: str       # logical source identifier, e.g. "llm-d/sig-autoscaling"
    item_id: str         # globally unique within this source, e.g. "llm-d/llm-d#42"
    title: str
    body: str            # full text content
    url: str
    author: str
    created_at: datetime
    updated_at: datetime
    item_type: str       # "issue" | "pr" | "discussion" | "article" | "comment" | ...
    component_iri: str   # KG component IRI, e.g. "cwkr:component/llm-d/sig-autoscaling"
    labels: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_text(self) -> str:
        """Plain-text representation suitable for LLM prompts."""
        parts = [
            f"[{self.item_type.upper()}] {self.title}",
            f"URL: {self.url}",
            f"Author: {self.author}",
            f"Updated: {self.updated_at.isoformat()}",
        ]
        if self.labels:
            parts.append(f"Labels: {', '.join(self.labels)}")
        if self.body.strip():
            body_preview = self.body[:2000].strip()
            parts.append(f"\n{body_preview}")
        return "\n".join(parts)


class DataSource(ABC):
    """Base class for all data source adapters.

    To add a new source type:
      1. Create scripts/sources/<type>.py
      2. Subclass DataSource and implement fetch() and source_type
      3. Register it in sources/__init__.py SOURCE_REGISTRY
      4. Add a config block in config.yaml
    """

    def __init__(self, source_id: str, component_iri: str, config: dict[str, Any]) -> None:
        self.source_id = source_id
        self.component_iri = component_iri
        self.config = config

    @abstractmethod
    def fetch(self, since: datetime) -> list[SourceItem]:
        """Fetch items updated/published since `since` (UTC)."""

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Short type identifier matching SOURCE_REGISTRY key."""
