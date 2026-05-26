"""Interest News Agent tools."""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from xml.etree import ElementTree as ET

from proagent.core.agent import ToolDef


SOURCE_CATALOG = {
    "core_news": {
        "description": "重大国际、科技、AI、财经资讯",
        "feeds": [
            {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
            {"name": "BBC Technology", "url": "https://feeds.bbci.co.uk/news/technology/rss.xml"},
            {"name": "Hacker News", "url": "https://news.ycombinator.com/rss"},
            {"name": "arXiv cs.AI", "url": "https://export.arxiv.org/rss/cs.AI"},
        ],
        "search_queries": [
            "重大国际新闻 最新",
            "科技新闻 AI 行业 最新",
            "人工智能 行业 新闻 融资 模型 发布",
            "财经新闻 全球市场 最新",
        ],
    },
    "anime": {
        "description": "日漫、中国动漫、上海漫展信息",
        "feeds": [
            {"name": "Anime News Network", "url": "https://www.animenewsnetwork.com/all/rss.xml"},
        ],
        "search_queries": [
            "日本 动漫 新闻 最新",
            "中国 动画 动漫 新闻 最新",
            "上海 漫展 动漫 展 近期",
            "CP 漫展 上海 最新",
        ],
    },
    "football": {
        "description": "五大联赛与世界杯资讯",
        "feeds": [
            {"name": "BBC Football", "url": "https://feeds.bbci.co.uk/sport/football/rss.xml"},
        ],
        "search_queries": [
            "英超 西甲 意甲 德甲 法甲 最新 新闻",
            "世界杯 足球 最新 新闻 FIFA",
            "FIFA World Cup latest news",
        ],
    },
}


def get_tools(runtime):
    return [
        ToolDef(
            name="news_source_catalog",
            description="Return the default source catalog for the Interest News Agent.",
            parameters={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Optional category: core_news | anime | football",
                        "default": "",
                    }
                },
            },
            handler=lambda category="", **_: _source_catalog(category),
            category="read_only",
        ),
        ToolDef(
            name="fetch_feed",
            description="Fetch and parse the latest items from an RSS or Atom feed URL.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "RSS or Atom feed URL"},
                    "max_items": {"type": "integer", "description": "Maximum items to return", "default": 8},
                    "include_summary": {"type": "boolean", "description": "Include feed summary text", "default": True},
                },
                "required": ["url"],
            },
            handler=lambda url, max_items=8, include_summary=True, **_: _fetch_feed(url, max_items, include_summary),
            category="read_only",
        ),
        ToolDef(
            name="web_news_search",
            description=(
                "Search current web/news results using the ddgs CLI when installed. "
                "Returns linked snippets for digest source discovery."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Maximum results", "default": 5},
                    "mode": {
                        "type": "string",
                        "description": "Search mode: news or text",
                        "default": "news",
                    },
                },
                "required": ["query"],
            },
            handler=lambda query, max_results=5, mode="news", **_: _web_news_search(query, max_results, mode),
            category="read_only",
        ),
        ToolDef(
            name="digest_outline",
            description="Return the required Chinese markdown outline for a Discord news digest.",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Digest title", "default": "今日兴趣新闻简报"},
                    "time_window": {"type": "string", "description": "Digest time window", "default": "today"},
                },
            },
            handler=lambda title="今日兴趣新闻简报", time_window="today", **_: _digest_outline(title, time_window),
            category="suggest",
        ),
    ]


def _source_catalog(category: str = "") -> str:
    key = (category or "").strip()
    data = SOURCE_CATALOG.get(key) if key else SOURCE_CATALOG
    if data is None:
        return json.dumps({"error": f"Unknown category: {category}", "valid": sorted(SOURCE_CATALOG)}, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False, indent=2)


def _fetch_feed(url: str, max_items: int = 8, include_summary: bool = True) -> str:
    feed_url = (url or "").strip()
    if not feed_url:
        return json.dumps({"error": "Feed URL is required."}, ensure_ascii=False)
    try:
        req = urllib.request.Request(feed_url, headers={"User-Agent": "ProAgent-NewsDigest/0.1"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            xml_bytes = resp.read()
    except urllib.error.HTTPError as e:
        return json.dumps({"error": f"HTTP {e.code} from {feed_url}"}, ensure_ascii=False)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return json.dumps({"error": f"Network error from {feed_url}: {e}"}, ensure_ascii=False)

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        return json.dumps({"error": f"Invalid XML from {feed_url}: {e}"}, ensure_ascii=False)

    items = []
    for node in root.iter():
        tag = _strip_ns(node.tag)
        if tag not in ("item", "entry"):
            continue
        children = {_strip_ns(child.tag): child for child in node}
        title = _text(children.get("title"))
        link = _link(children.get("link"))
        if not link:
            link = _text(children.get("id"))
        published = _text(children.get("pubDate")) or _text(children.get("published")) or _text(children.get("updated"))
        summary = _text(children.get("description")) or _text(children.get("summary"))
        item = {
            "title": title,
            "url": link,
            "published": published,
        }
        if include_summary:
            item["summary"] = summary[:700]
        if item["title"] or item["url"]:
            items.append(item)
        if len(items) >= max(1, min(int(max_items), 20)):
            break

    return json.dumps({"source": feed_url, "items": items}, ensure_ascii=False, indent=2)


def _web_news_search(query: str, max_results: int = 5, mode: str = "news") -> str:
    q = (query or "").strip()
    if not q:
        return json.dumps({"error": "Query is required."}, ensure_ascii=False)
    ddgs = shutil.which("ddgs")
    if not ddgs:
        return json.dumps(
            {
                "error": "ddgs CLI is not installed.",
                "fallback": "Use fetch_feed with catalog feeds, or install ddgs to enable DuckDuckGo search.",
            },
            ensure_ascii=False,
        )

    search_mode = "text" if str(mode).lower() == "text" else "news"
    cmd = [
        ddgs,
        search_mode,
        "-q",
        q,
        "-m",
        str(max(1, min(int(max_results), 10))),
        "-o",
        "json",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError) as e:
        return json.dumps({"error": f"Search failed: {e}"}, ensure_ascii=False)
    if proc.returncode != 0:
        return json.dumps({"error": proc.stderr.strip() or proc.stdout.strip()}, ensure_ascii=False)
    return proc.stdout.strip() or "[]"


def _digest_outline(title: str, time_window: str) -> str:
    return (
        f"# {title}\n\n"
        f"时间窗口：{time_window}\n\n"
        "## 国际 / 科技 / AI / 财经\n"
        "- **标题**：摘要。来源：媒体名。原文链接：URL\n\n"
        "## 动漫 / 上海漫展\n"
        "- **标题**：摘要。来源：媒体名。原文链接：URL\n\n"
        "## 足球 / 世界杯\n"
        "- **标题**：摘要。来源：媒体名。原文链接：URL\n\n"
        "## 观察\n"
        "- 基于以上来源的简短综合判断。\n"
    )


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _text(node) -> str:
    if node is None or node.text is None:
        return ""
    return unescape(" ".join(node.text.split()))


def _link(node) -> str:
    if node is None:
        return ""
    href = node.attrib.get("href") if hasattr(node, "attrib") else ""
    return (href or _text(node)).strip()
