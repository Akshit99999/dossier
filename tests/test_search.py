from dossier_agent import search


def test_search_without_endpoint_is_optional(monkeypatch):
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    monkeypatch.setenv("ENABLE_DDG_SEARCH", "0")
    assert search.search_web("test question") == []


def test_search_falls_back_to_ddg_when_searxng_fails(monkeypatch):
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    monkeypatch.setattr(
        search,
        "_search_ddg",
        lambda query, max_results=5: [
            search.SearchResult("DDG Title", "https://ddg.example", "DDG Snippet")
        ],
    )
    results = search.search_web("test query")
    assert len(results) == 1
    assert results[0].url == "https://ddg.example"


def test_search_normalizes_and_limits_results(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {"title": "First", "url": "https://one.example", "content": "One"},
                    {"title": "Second", "url": "https://two.example", "content": "Two"},
                ]
            }

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(search.httpx, "get", fake_get)
    results = search.search_web("test question", endpoint="http://search.local", max_results=1)

    assert results == [search.SearchResult("First", "https://one.example", "One")]
    assert calls[0][0] == "http://search.local/search"
    assert calls[0][1]["params"]["q"] == "test question"


def test_search_context_marks_results_as_untrusted():
    context = search.format_search_context(
        [search.SearchResult("Title", "https://example.com", "Snippet")]
    )
    assert "untrusted evidence" in context
    assert "https://example.com" in context
