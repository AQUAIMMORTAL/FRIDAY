"""
web_search.py — Web search for FRIDAY using DuckDuckGo
"""
import requests
from bs4 import BeautifulSoup

try:
    from duckduckgo_search import DDGS
    _DDG = True
except ImportError:
    _DDG = False

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}


def _ddg_search(query: str, max_results: int = 5) -> list[dict]:
    if not _DDG:
        raise RuntimeError("duckduckgo-search not installed. Run: pip install duckduckgo-search")
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    return results


def _fetch_page(url: str, max_chars: int = 2000) -> str:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=8)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        return text[:max_chars]
    except Exception as e:
        return f"[Fetch error: {e}]"


def web_search(parameters: dict, **_) -> str:
    """
    Search the web and return summarised results.
    parameters:
        query: str        — search query
        deep:  bool       — if True, fetch and include page content (slower)
        max_results: int  — number of results (default 5)
    """
    query       = parameters.get("query", "").strip()
    deep        = parameters.get("deep", False)
    max_results = int(parameters.get("max_results", 5))

    if not query:
        return "No search query provided."

    try:
        results = _ddg_search(query, max_results=max_results)
    except Exception as e:
        return f"[Web Search Error] {e}"

    if not results:
        return f"No results found for: {query}"

    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "No title")
        href  = r.get("href", "")
        body  = r.get("body", "")
        lines.append(f"[{i}] {title}")
        lines.append(f"    URL: {href}")
        if body:
            lines.append(f"    {body[:300]}")
        if deep and href:
            content = _fetch_page(href)
            lines.append(f"    --- Page content ---")
            lines.append(f"    {content[:600]}")
        lines.append("")

    return "\n".join(lines)


def fetch_url(parameters: dict, **_) -> str:
    """
    Fetch and extract text content from a specific URL.
    parameters:
        url: str
        max_chars: int  (default 3000)
    """
    url       = parameters.get("url", "").strip()
    max_chars = int(parameters.get("max_chars", 3000))
    if not url:
        return "No URL provided."
    return _fetch_page(url, max_chars=max_chars)
