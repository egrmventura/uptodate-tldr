"""Full-text article scraper: URL → title, author, publish date, body text.

Given a URL, fetch the page and extract the article's title, author, publish
date, and main body text, stripping ads, nav, and boilerplate. This module is a
standalone utility — it operates on URLs, not topics, so it is not a `Source`.
The ingestion stage uses it to enrich `Item`s with full body text (see the
`scraping.enabled` config flag and the enrichment wiring in `main.py`).

Like the sources, `scrape()` never raises: a paywalled, blocked, timed-out, or
unparseable page logs a warning and returns `None`, so a single bad page can't
abort a run. A page that fetches but yields too little article text (below
`min_body_chars`) is treated as blocked/paywalled and also returns `None`.

Extraction is heuristic (requests + BeautifulSoup over the lxml parser):
- title:  og:title -> <title> -> first <h1>
- author: <meta name/property=author|article:author> -> rel="author"
- date:   article:published_time -> <time datetime> -> <meta name=date>
- body:   strip script/style/nav/header/footer/aside/form, then take the
          <article> (or the densest text container) and join its paragraphs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests
from bs4 import BeautifulSoup

from sources.base import parse_timestamp

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 10
DEFAULT_MIN_BODY_CHARS = 200
# A polite desktop UA — some sites 403 the default python-requests UA.
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
# Tags that never contain article body text.
_BOILERPLATE_TAGS = ["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]


@dataclass
class ScrapedArticle:
    url: str
    title: str | None
    author: str | None
    published_at: datetime | None
    body: str


def scrape(url: str, config: dict[str, Any] | None = None) -> ScrapedArticle | None:
    """Fetch `url` and extract a ScrapedArticle, or None if blocked/unparseable.

    Never raises — all network and parse failures log and return None.
    """
    config = config or {}
    min_body_chars = config.get("min_body_chars", DEFAULT_MIN_BODY_CHARS)

    try:
        response = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=config.get("timeout", REQUEST_TIMEOUT_SECONDS),
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.warning("Scraper: request failed for %s", url, exc_info=True)
        return None

    return _extract(url, response.text, min_body_chars)


def _extract(url: str, html: str, min_body_chars: int) -> ScrapedArticle | None:
    """Parse HTML into a ScrapedArticle. Returns None if the body is too thin
    to be a real article (paywall/interstitial/blocked)."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        logger.warning("Scraper: parse failed for %s", url, exc_info=True)
        return None

    title = _extract_title(soup)
    author = _extract_author(soup)
    published_at = _extract_date(soup)

    # Strip boilerplate before pulling body text.
    for tag in soup(_BOILERPLATE_TAGS):
        tag.decompose()

    body = _extract_body(soup)

    if len(body) < min_body_chars:
        logger.warning(
            "Scraper: body too short (%d < %d) for %s — treating as blocked/paywalled",
            len(body),
            min_body_chars,
            url,
        )
        return None

    return ScrapedArticle(
        url=url,
        title=title,
        author=author,
        published_at=published_at,
        body=body,
    )


def _meta(soup: BeautifulSoup, **attrs: str) -> str | None:
    tag = soup.find("meta", attrs=attrs)
    if tag:
        content = tag.get("content")
        if content and content.strip():
            return content.strip()
    return None


def _extract_title(soup: BeautifulSoup) -> str | None:
    og = _meta(soup, property="og:title")
    if og:
        return og
    if soup.title and soup.title.string and soup.title.string.strip():
        return soup.title.string.strip()
    h1 = soup.find("h1")
    if h1:
        text = h1.get_text(strip=True)
        if text:
            return text
    return None


def _extract_author(soup: BeautifulSoup) -> str | None:
    for attrs in ({"name": "author"}, {"property": "article:author"}, {"name": "twitter:creator"}):
        author = _meta(soup, **attrs)
        if author:
            return author
    rel_author = soup.find(attrs={"rel": "author"})
    if rel_author:
        text = rel_author.get_text(strip=True)
        if text:
            return text
    return None


def _extract_date(soup: BeautifulSoup) -> datetime | None:
    raw = (
        _meta(soup, property="article:published_time")
        or _meta(soup, name="date")
        or _meta(soup, property="og:published_time")
    )
    if not raw:
        time_tag = soup.find("time")
        if time_tag and time_tag.get("datetime"):
            raw = time_tag["datetime"].strip()
    if not raw:
        return None
    parsed = parse_timestamp(raw)
    return parsed


def _extract_body(soup: BeautifulSoup) -> str:
    """Return the main article text as newline-joined paragraphs.

    Prefers an <article> element; otherwise picks the container with the most
    paragraph text, so a dense article body wins over sparse nav/sidebars."""
    article = soup.find("article")
    container = article if article is not None else _densest_container(soup)
    if container is None:
        container = soup.body or soup

    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    paragraphs = [p for p in paragraphs if p]
    if paragraphs:
        return "\n".join(paragraphs)

    # No <p> tags — fall back to the container's raw text.
    return container.get_text(" ", strip=True)


def _densest_container(soup: BeautifulSoup):
    """Find the element whose paragraphs hold the most text."""
    best = None
    best_len = 0
    for candidate in soup.find_all(["main", "div", "section"]):
        text_len = sum(len(p.get_text(strip=True)) for p in candidate.find_all("p", recursive=False))
        # recursive=False on the first pass biases toward direct-child paragraphs;
        # fall back to a full descendant count if nothing scored.
        if text_len == 0:
            text_len = sum(len(p.get_text(strip=True)) for p in candidate.find_all("p"))
        if text_len > best_len:
            best_len = text_len
            best = candidate
    return best
