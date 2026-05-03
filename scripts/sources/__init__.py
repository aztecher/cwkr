"""Data source adapters. Each adapter implements DataSource and returns SourceItem objects."""

from .base import DataSource, SourceItem
from .github import GitHubSource

SOURCE_REGISTRY: dict[str, type[DataSource]] = {
    "github": GitHubSource,
    # future: "web_article": WebArticleSource,
    # future: "zhihu": ZhihuSource,
    # future: "google_groups": GoogleGroupsSource,
}

__all__ = ["DataSource", "SourceItem", "SOURCE_REGISTRY"]
