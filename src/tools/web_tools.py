"""Web tools: web_search and web_fetch."""

from __future__ import annotations

from typing import Any

from tools.registry import ToolRegistry


WEB_SEARCH_SCHEMA = {
    "name": "web_search",
    "description": (
        "Search the web for current information. Returns titles, snippets, and URLs. "
        "Use for up-to-date facts, news, prices, or any information you don't have."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (default: 5)",
                "default": 5,
            },
        },
        "required": ["query"],
    },
}

WEB_FETCH_SCHEMA = {
    "name": "web_fetch",
    "description": (
        "Fetch and read the content of a specific URL. Returns the page content as markdown. "
        "Use after web_search to read the full content of a promising result."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "extract": {
                "type": "string",
                "enum": ["full", "main_content"],
                "description": "How much content to return: full page or just main content (default: main_content)",
                "default": "main_content",
            },
        },
        "required": ["url"],
    },
}


def handle_web_search(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    """Search the web using DuckDuckGo."""
    query = input_data.get("query", "")
    num_results = input_data.get("num_results", 5)

    if not query:
        return {"error": "query is required"}

    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=num_results):
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", ""),
                })

        return {
            "query": query,
            "results": results,
            "count": len(results),
        }
    except ImportError:
        return {"error": "ddgs package not installed. Run: pip install ddgs"}
    except Exception as e:
        return {"error": f"Search failed: {e}"}


def handle_web_fetch(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    """Fetch a URL and return its content as markdown."""
    url = input_data.get("url", "")
    extract = input_data.get("extract", "main_content")

    if not url:
        return {"error": "url is required"}

    try:
        import httpx
        import html2text

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }

        response = httpx.get(url, headers=headers, timeout=30.0, follow_redirects=True)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")

        if "text/html" in content_type or not content_type:
            converter = html2text.HTML2Text()
            converter.ignore_links = False
            converter.ignore_images = True
            converter.body_width = 0  # No line wrapping
            markdown = converter.handle(response.text)

            # Truncate if too large
            MAX_CHARS = 20_000
            if len(markdown) > MAX_CHARS:
                markdown = markdown[:MAX_CHARS] + "\n\n[... content truncated ...]"

            return {
                "url": url,
                "content": markdown,
                "chars": len(markdown),
            }
        elif "application/json" in content_type:
            return {
                "url": url,
                "content": response.text[:10_000],
                "content_type": "json",
            }
        else:
            return {
                "url": url,
                "content": response.text[:5_000],
                "content_type": content_type,
            }

    except ImportError as e:
        return {"error": f"Missing package: {e}. Run: pip install httpx html2text"}
    except Exception as e:
        return {"error": f"Fetch failed for {url}: {e}"}


def register_web_tools(registry: ToolRegistry) -> None:
    """Register web tools into the registry."""
    registry.register(WEB_SEARCH_SCHEMA, handle_web_search)
    registry.register(WEB_FETCH_SCHEMA, handle_web_fetch)
