"""World tools — peek_outside: a raw, wide-net snapshot of news and research."""

from __future__ import annotations

import json
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from .registry import ToolRegistry

_TIMEOUT = 10
_HN_FETCH = 50    # IDs to try
_HN_KEEP = 20     # stories to return
_ARXIV_KEEP = 15
_BBC_PER_FEED = 5

PEEK_OUTSIDE_SCHEMA = {
    "name": "peek_outside",
    "description": (
        "Pull a raw, wide-net snapshot of what's happening in the world right now: "
        "freshly submitted research papers (arXiv) and recent news headlines "
        "(Hacker News new queue, BBC world/science/tech). "
        "No filters, no suggested angles — just the world as it is at this moment. "
        "Do what you want with it in your own time."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Aurelia/1.0"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _arxiv() -> list[dict[str, str]]:
    cats = "cat:cs+OR+cat:physics+OR+cat:q-bio+OR+cat:astro-ph+OR+cat:math+OR+cat:econ"
    url = (
        "http://export.arxiv.org/api/query"
        f"?search_query={cats}"
        "&sortBy=submittedDate&sortOrder=descending"
        f"&max_results={_ARXIV_KEEP}"
    )
    root = ET.fromstring(_fetch(url))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    results = []
    for entry in root.findall("a:entry", ns):
        title_el = entry.find("a:title", ns)
        id_el = entry.find("a:id", ns)
        pub_el = entry.find("a:published", ns)
        cat_el = entry.find("{http://arxiv.org/schemas/atom}primary_category")

        title = (title_el.text or "").strip().replace("\n", " ")
        url_val = (id_el.text or "").strip()
        submitted = (pub_el.text or "")[:10]
        category = cat_el.get("term", "") if cat_el is not None else ""

        if title and url_val:
            results.append({
                "title": title,
                "url": url_val,
                "category": category,
                "submitted": submitted,
            })
    return results


def _hn() -> list[dict[str, str]]:
    ids = json.loads(_fetch("https://hacker-news.firebaseio.com/v0/newstories.json"))[:_HN_FETCH]

    def fetch_item(item_id: int) -> dict[str, str] | None:
        try:
            item = json.loads(_fetch(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"))
            if not (item and item.get("type") == "story" and item.get("title") and item.get("url")):
                return None
            ts = item.get("time", 0)
            age_min = (datetime.now(timezone.utc).timestamp() - ts) / 60 if ts else 0
            if age_min < 60:
                age = f"{int(age_min)}m ago"
            elif age_min < 1440:
                age = f"{int(age_min / 60)}h ago"
            else:
                age = f"{int(age_min / 1440)}d ago"
            return {"title": item["title"], "url": item["url"], "posted": age}
        except Exception:
            return None

    results: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(fetch_item, i) for i in ids]
        for future in as_completed(futures):
            item = future.result()
            if item:
                results.append(item)
            if len(results) >= _HN_KEEP:
                for f in futures:
                    f.cancel()
                break
    return results[:_HN_KEEP]


def _bbc() -> list[dict[str, str]]:
    feeds = [
        ("world",      "http://feeds.bbci.co.uk/news/world/rss.xml"),
        ("science",    "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
        ("technology", "http://feeds.bbci.co.uk/news/technology/rss.xml"),
    ]
    results = []
    for section, url in feeds:
        try:
            root = ET.fromstring(_fetch(url))
            channel = root.find("channel")
            if channel is None:
                continue
            for item in channel.findall("item")[:_BBC_PER_FEED]:
                title_el = item.find("title")
                link_el = item.find("link")
                title = (title_el.text or "").strip()
                link = (link_el.text or "").strip()
                if title and link:
                    results.append({"title": title, "url": link, "section": section})
        except Exception:
            pass
    return results


def handle_peek_outside(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    sources: dict[str, Any] = {}
    errors: dict[str, str] = {}

    tasks = {"arxiv": _arxiv, "hacker_news": _hn, "bbc": _bbc}

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                sources[name] = future.result()
            except Exception as e:
                errors[name] = str(e)

    result: dict[str, Any] = {"fetched_at": fetched_at, "sources": sources}
    if errors:
        result["errors"] = errors
    return result


def register_world_tools(registry: ToolRegistry) -> None:
    registry.register(PEEK_OUTSIDE_SCHEMA, handle_peek_outside)
