"""ArXiv source, via the `arxiv` package (wraps the official arXiv API).

Searches by topic keyword, optionally scoped to a category (e.g. `cs.AI`),
sorted by submission date descending. ArXiv has no engagement metric like
upvotes, so `score` is left at 0 and the ranker instead uses
`extra["citations"]` (see below) as the signal for this source.

Note: the arXiv API does not provide citation counts. We leave
`extra["citations"]` at 0 here; it's a documented extension point — see the
README "Known limitations" section for how to wire up a citation-count
provider (e.g. Semantic Scholar) without changing the Item schema.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import arxiv

from resilience import is_transient_arxiv, retry_with_backoff
from sources.base import Item, Source

logger = logging.getLogger(__name__)


class ArxivSource(Source):
    name = "arxiv"

    def fetch(self, topic: str, config: dict[str, Any]) -> list[Item]:
        max_results = config.get("max_results", 20)
        category = config.get("category")

        query = f"all:{topic}"
        if category:
            query = f"({query}) AND cat:{category}"

        def _request() -> list[arxiv.Result]:
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending,
            )
            client = arxiv.Client()
            return list(client.results(search))

        try:
            # arXiv 429s under rapid repeated runs — retry with backoff, then
            # fall back to [] (isolated) if the rate limit hasn't cleared.
            results = retry_with_backoff(_request, label="ArXiv", is_transient=is_transient_arxiv)
        except Exception:
            logger.warning("ArXiv request failed", exc_info=True)
            return []

        items: list[Item] = []
        for result in results:
            published_at = result.published or datetime.now(timezone.utc)
            items.append(
                Item(
                    source=self.name,
                    title=result.title.strip(),
                    url=result.entry_id,
                    score=0,
                    published_at=published_at,
                    summary_raw=(result.summary or "").strip().replace("\n", " ")[:500],
                    extra={"citations": 0},
                )
            )

        return items
