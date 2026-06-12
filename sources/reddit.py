"""Reddit source.

Uses PRAW (authenticated, via REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET) when
credentials are present, since it's rate-limit-friendly and gives clean
access to search and listing endpoints. Falls back to Reddit's public
`.json` endpoints (no auth required, but aggressively rate-limited and
occasionally blocked) when credentials are missing — useful for quick
local testing without registering an app.

Searches both a topic-keyword search across all of Reddit and the
configured subreddit list (config.yaml `sources.reddit.subreddits`),
sorted by "hot"/relevance over the past week.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import requests

from sources.base import Item, Source

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 10
USER_AGENT_FALLBACK = "uptodate-tldr/0.1"


class RedditSource(Source):
    name = "reddit"

    def fetch(self, topic: str, config: dict[str, Any]) -> list[Item]:
        max_results = config.get("max_results", 30)
        subreddits: list[str] = config.get("subreddits", [])

        client_id = os.environ.get("REDDIT_CLIENT_ID")
        client_secret = os.environ.get("REDDIT_CLIENT_SECRET")

        if client_id and client_secret:
            return self._fetch_via_praw(topic, subreddits, max_results, client_id, client_secret)
        return self._fetch_via_public_json(topic, subreddits, max_results)

    def _fetch_via_praw(
        self,
        topic: str,
        subreddits: list[str],
        max_results: int,
        client_id: str,
        client_secret: str,
    ) -> list[Item]:
        try:
            import praw
        except ImportError:
            logger.warning("praw not installed; falling back to public JSON API")
            return self._fetch_via_public_json(topic, subreddits, max_results)

        try:
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=os.environ.get("REDDIT_USER_AGENT", USER_AGENT_FALLBACK),
            )
            reddit.read_only = True

            items: list[Item] = []
            subreddit_path = "+".join(subreddits) if subreddits else "all"
            for submission in reddit.subreddit(subreddit_path).search(
                topic, sort="hot", time_filter="week", limit=max_results
            ):
                items.append(_submission_to_item(submission))
            return items
        except Exception:
            logger.warning("Reddit (PRAW) request failed", exc_info=True)
            return []

    def _fetch_via_public_json(
        self, topic: str, subreddits: list[str], max_results: int
    ) -> list[Item]:
        subreddit_path = "+".join(subreddits) if subreddits else "all"
        url = f"https://www.reddit.com/r/{subreddit_path}/search.json"

        try:
            response = requests.get(
                url,
                params={
                    "q": topic,
                    "restrict_sr": "true" if subreddits else "false",
                    "sort": "hot",
                    "t": "week",
                    "limit": max_results,
                },
                headers={"User-Agent": os.environ.get("REDDIT_USER_AGENT", USER_AGENT_FALLBACK)},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException:
            logger.warning("Reddit (public JSON) request failed", exc_info=True)
            return []

        children = response.json().get("data", {}).get("children", [])
        items: list[Item] = []
        for child in children:
            data = child.get("data", {})
            title = data.get("title")
            if not title:
                continue

            permalink = data.get("permalink", "")
            items.append(
                Item(
                    source=self.name,
                    title=title,
                    url=f"https://reddit.com{permalink}" if permalink else data.get("url", ""),
                    score=data.get("score", 0) or 0,
                    published_at=_parse_created_utc(data.get("created_utc")),
                    summary_raw=(data.get("selftext") or "")[:500],
                )
            )

        return items


def _submission_to_item(submission: Any) -> Item:
    return Item(
        source=RedditSource.name,
        title=submission.title,
        url=f"https://reddit.com{submission.permalink}",
        score=submission.score or 0,
        published_at=_parse_created_utc(submission.created_utc),
        summary_raw=(submission.selftext or "")[:500],
    )


def _parse_created_utc(created_utc: float | None) -> datetime:
    if created_utc is None:
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(created_utc, tz=timezone.utc)
