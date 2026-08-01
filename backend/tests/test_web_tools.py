import httpx
import pytest

from uai_forge.models import ToolBinding
from uai_forge.web_tools import WebFetchTool, WebJsonTool, WebRssTool, WebSearchTool


def client_factory(handler):
    def factory(**kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    return factory


@pytest.mark.asyncio
async def test_web_search_parses_bounded_rss_results():
    rss = """<?xml version="1.0"?>
    <rss><channel>
      <item><title>First result</title><link>https://example.com/one</link><description>One &amp; useful</description></item>
      <item><title>Second result</title><link>https://example.com/two</link><description>Two</description></item>
      <item><title>Third result</title><link>https://example.com/three</link><description>Three</description></item>
    </channel></rss>"""

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "www.bing.com"
        assert request.url.params["q"] == "remote agents"
        assert request.url.params["format"] == "rss"
        return httpx.Response(
            200,
            headers={"content-type": "application/rss+xml"},
            content=rss.encode(),
            request=request,
        )

    tool = WebSearchTool(
        ToolBinding(plugin_id="tool.web_search"),
        client_factory=client_factory(handler),
    )
    result = await tool.invoke({"query": "remote agents", "max_results": 2}, {})

    assert result["count"] == 2
    assert [item["title"] for item in result["results"]] == [
        "First result",
        "Second result",
    ]
    assert result["results"][0]["snippet"] == "One & useful"
    assert result["untrusted"] is True


@pytest.mark.asyncio
async def test_web_fetch_extracts_text_without_scripts_and_bounds_output():
    html = """<!doctype html>
    <html><head><title>Example page</title><script>ignore me()</script></head>
    <body><h1>Heading</h1><p>Hello <a href="/docs">docs</a>.</p>
    <script>do_not_return_this()</script><p>""" + ("x" * 2_000) + "</p></body></html>"""

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://example.com/article")
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=html.encode(),
            request=request,
        )

    tool = WebFetchTool(
        ToolBinding(plugin_id="tool.web_fetch"),
        client_factory=client_factory(handler),
    )
    result = await tool.invoke(
        {"url": "https://example.com/article", "max_chars": 1_000},
        {},
    )

    assert result["title"] == "Example page"
    assert "Heading" in result["text"]
    assert "Hello docs." in result["text"]
    assert "do_not_return_this" not in result["text"]
    assert len(result["text"]) == 1_000
    assert result["truncated"] is True
    assert result["links"] == [{"url": "https://example.com/docs", "text": "docs"}]
    assert result["untrusted"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url,error_code",
    [
        ("http://example.com/", "web.url_scheme_not_allowed"),
        ("https://127.0.0.1/", "web.private_address_not_allowed"),
        ("https://example.com/?token=not-safe", "web.url_sensitive_query_not_allowed"),
        ("https://user:pass@example.com/", "web.url_userinfo_not_allowed"),
    ],
)
async def test_web_fetch_rejects_unsafe_urls_before_network(url, error_code):
    tool = WebFetchTool(ToolBinding(plugin_id="tool.web_fetch"))

    with pytest.raises(ValueError, match=error_code):
        await tool.invoke({"url": url}, {})


@pytest.mark.asyncio
async def test_web_fetch_revalidates_redirects_before_following():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"location": "https://127.0.0.1/private"},
            request=request,
        )

    tool = WebFetchTool(
        ToolBinding(plugin_id="tool.web_fetch"),
        client_factory=client_factory(handler),
    )

    with pytest.raises(ValueError, match="web.private_address_not_allowed"):
        await tool.invoke({"url": "https://example.com/start"}, {})


@pytest.mark.asyncio
async def test_web_json_reads_bounded_structured_data():
    payload = {"items": [{"id": 1, "title": "Public data"}], "ok": True}

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://api.example.com/data.json")
        assert "application/json" in request.headers["accept"]
        return httpx.Response(
            200,
            headers={"content-type": "application/json; charset=utf-8"},
            json=payload,
            request=request,
        )

    tool = WebJsonTool(
        ToolBinding(plugin_id="tool.web_json"),
        client_factory=client_factory(handler),
    )
    result = await tool.invoke({"url": "https://api.example.com/data.json"}, {})

    assert result["value"] == payload
    assert result["content_type"] == "application/json"
    assert result["truncated"] is False
    assert result["untrusted"] is True


@pytest.mark.asyncio
async def test_web_json_fails_closed_for_invalid_payload():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"<html>not json</html>",
            request=request,
        )

    tool = WebJsonTool(
        ToolBinding(plugin_id="tool.web_json"),
        client_factory=client_factory(handler),
    )

    with pytest.raises(RuntimeError, match="web_json.invalid_json"):
        await tool.invoke({"url": "https://api.example.com/data"}, {})


@pytest.mark.asyncio
async def test_web_rss_reads_rss_and_atom_article_metadata():
    feed = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>Atom entry</title>
        <link href="https://example.com/atom" />
        <summary>Atom summary</summary>
        <updated>2026-08-02T00:00:00Z</updated>
      </entry>
      <entry>
        <title>Second entry</title>
        <link href="https://example.com/second" />
        <summary>Second summary</summary>
      </entry>
    </feed>"""

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://example.com/feed.xml")
        assert "application/atom+xml" in request.headers["accept"]
        return httpx.Response(
            200,
            headers={"content-type": "application/atom+xml"},
            content=feed.encode(),
            request=request,
        )

    tool = WebRssTool(
        ToolBinding(plugin_id="tool.web_rss"),
        client_factory=client_factory(handler),
    )
    result = await tool.invoke(
        {"url": "https://example.com/feed.xml", "max_items": 1},
        {},
    )

    assert result["count"] == 1
    assert result["items"] == [
        {
            "title": "Atom entry",
            "url": "https://example.com/atom",
            "summary": "Atom summary",
            "published": "2026-08-02T00:00:00Z",
        }
    ]
    assert result["untrusted"] is True
