"""Tests run WITHOUT internet and WITHOUT API keys (website + LLM are faked)."""
import asyncio
import copy
import json

import pytest
from fastapi.testclient import TestClient

from app.config import estimate_cost_usd, settings
from app.main import app, get_analysis_service
from app.services.analysis_service import AnalysisService
from app.services.llm_service import LLMConfigError, LLMResponse, build_client, extract_json
from app.services.website_extractor import (
    PageContent,
    WebsiteContent,
    extract_website,
    parse_page,
    pick_extra_pages,
)
from app.utils.validators import BlockedURLError, InvalidURLError, is_public_ip, normalize_url, validate_public_url

SAMPLE_LLM_OUTPUT = {
    "brand": {"name": "ABC Technologies", "category": "Web Development", "summary": "Builds websites."},
    "analysis": {
        "competitor_analysis": {
            "brand_overview": "ABC builds websites for small businesses.",
            "main_category": "Web Development",
            "products_and_services": ["Websites", "SEO"],
            "competitors": [
                {"name": "XYZ Web", "website": "www.xyzweb.com", "main_service": "Web design",
                 "target_market": "Enterprise", "strengths": ["Big brand"], "weaknesses_or_gaps": ["Costly"]},
                {"name": "ABC Technologies", "website": "abc.example"},  # the brand itself -> removed
                {"name": "XYZ Web"},  # duplicate -> removed
                {"name": "Pixel Studio", "website": None},
                {"name": "Code House", "website": "https://codehouse.io"},
            ],
            "competitive_advantages": ["Affordable"],
            "opportunities": ["Improve online visibility"],
            "comparison_table": [{"aspect": "Brand Name", "your_brand": "ABC Technologies",
                                  "competitors": {"XYZ Web": "XYZ Web"}}],
        },
        "target_search_queries": [
            {"query": f"query {i}", "platforms": ["google", "twitter", "TikTok"], "intent": "Service Search"}
            for i in range(6)
        ],
        "seo_improvements": {
            "primary_keyword": "web development", "recommended_title": "Web Development | ABC",
            "meta_description": "ABC builds fast websites.",
            "supporting_content": [{"type": "FAQ", "title": "Website FAQ"}],
        },
        "top_services": [
            {"name": "Web Design", "description": "Design", "source": "Website"},
            {"name": "Hosting", "description": "Hosting", "source": "guess"},
            {"name": "Search Optimization", "description": "Improve search visibility", "source": "inferred"},
            {"name": "E-commerce Development", "description": "Build online stores", "source": "inferred"},
            {"name": "Website Maintenance", "description": "Maintain business websites", "source": "inferred"},
        ],
        "target_audience": {"primary_audience": ["Small businesses"],
                            "marketing_segments": [{"audience": "Audience 1", "business_type": "Startups",
                                                    "requirement": "Digital Solutions"}]},
    },
}


class FakeLLM:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = 0

    async def generate(self, system, user):
        self.calls += 1
        text = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        return LLMResponse(text, "gemini", "gemini-2.5-flash", 8000, 3000, 0.01)


async def fake_extract(url):
    page = PageContent(url=url, title="ABC Technologies - Home", meta_description="We build websites",
                       text="We build websites for small businesses. " * 20)
    return WebsiteContent(url=url, final_url=url, pages=[page])


async def fake_validate(url):
    return normalize_url(url)  # no DNS lookup in tests


def make_client(llm):
    service = AnalysisService(llm_service=llm, extractor=fake_extract, validator=fake_validate)
    app.dependency_overrides[get_analysis_service] = lambda: service
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_llm_api_urls_are_configurable(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_URL_TEMPLATE", "https://gemini.test/{model}")
    monkeypatch.setattr(settings, "ANTHROPIC_API_URL", "https://anthropic.test/messages")
    monkeypatch.setattr(settings, "OPENAI_API_URL", "https://openai.test/chat/completions")

    assert settings.api_url_for("gemini", "custom-model") == "https://gemini.test/custom-model"
    assert settings.api_url_for("anthropic", "claude") == "https://anthropic.test/messages"
    assert settings.api_url_for("openai", "gpt") == "https://openai.test/chat/completions"

    monkeypatch.setattr(settings, "GEMINI_API_URL_TEMPLATE", "")
    with pytest.raises(LLMConfigError, match="API URL"):
        build_client("gemini", "custom-model")


def test_gemini_38_paid_price_estimate():
    assert estimate_cost_usd("gemini-3.8-flash", 1946, 3873) == pytest.approx(0.015983)


# ---------- URL validation and SSRF ----------
def test_normalize_adds_https():
    assert normalize_url("example.com") == "https://example.com/"


@pytest.mark.parametrize("bad", ["", "   ", "ftp://example.com", "https://user:pass@example.com",
                                 "http://exa mple.com", "https://nodot", "https://example.com:abc"])
def test_invalid_urls(bad):
    with pytest.raises((InvalidURLError, BlockedURLError)):
        normalize_url(bad)


@pytest.mark.parametrize("ip,expected", [
    ("127.0.0.1", False), ("10.0.0.5", False), ("192.168.1.1", False), ("172.16.0.1", False),
    ("169.254.169.254", False), ("100.64.0.1", False), ("0.0.0.0", False), ("::1", False),
    ("::ffff:127.0.0.1", False), ("fe80::1%eth0", False), ("8.8.8.8", True), ("2606:4700::1111", True),
])
def test_is_public_ip(ip, expected):
    assert is_public_ip(ip) is expected


@pytest.mark.parametrize("url", ["http://127.0.0.1", "http://localhost/admin", "http://169.254.169.254/latest/",
                                 "http://192.168.0.1", "http://[::1]/", "http://printer.local",
                                 "https://example.com:8080"])
def test_ssrf_blocked(url):
    with pytest.raises(BlockedURLError):
        validate_public_url(url)


# ---------- JSON parsing ----------
def test_extract_json_with_fences_and_text():
    assert extract_json('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Here: {"a": {"b": 2}} done') == {"a": {"b": 2}}
    with pytest.raises(ValueError):
        extract_json("no json here")


# ---------- HTML extraction ----------
def test_parse_page_removes_noise_and_finds_links():
    html = """<html><head><title>ABC Tech</title><meta name="description" content="Web agency">
    <script type="application/ld+json">{"@type":"Organization","name":"ABC Technologies"}</script>
    <style>.x{}</style></head><body><nav><a href="/services">Services</a><a href="/about-us">About</a></nav>
    <h1>We build websites</h1><p>Fast websites for small business.</p><script>alert(1)</script>
    <a href="https://other.com/x">x</a></body></html>"""
    page = parse_page(html, "https://abc.example/")
    assert page.title == "ABC Tech"
    assert page.meta_description == "Web agency"
    assert "Organization: ABC Technologies" in page.structured_data
    assert "We build websites" in page.headings
    assert "alert" not in page.text
    assert "https://other.com/x" not in page.internal_links
    extra = pick_extra_pages(page.internal_links, "https://abc.example/", 2)
    assert set(extra) == {"https://abc.example/services", "https://abc.example/about-us"}


def test_sparse_static_page_uses_rendered_html(monkeypatch):
    from app.services import website_extractor

    static_html = "<html><body><main><div id='app'></div></main></body></html>"
    rendered_html = (
        "<html><head><title>Rendered business</title></head><body><main>"
        "<h1>Rendered business</h1><p>" + ("Business services and products. " * 10)
        + "</p></main></body></html>"
    )
    rendered_urls = []

    async def fake_fetch_html(client, url):
        return url, static_html

    async def fake_render_page(url):
        rendered_urls.append(url)
        return url, rendered_html

    monkeypatch.setattr(website_extractor, "fetch_html", fake_fetch_html)
    monkeypatch.setattr(website_extractor, "render_page", fake_render_page)
    monkeypatch.setattr(settings, "MAX_EXTRA_PAGES", 0)

    website = asyncio.run(extract_website("https://dynamic.example/"))

    assert rendered_urls == ["https://dynamic.example/"]
    assert website.home.title == "Rendered business"
    assert "Business services and products." in website.home.text


# ---------- API ----------
def test_link_analysis_success():
    llm = FakeLLM([json.dumps(SAMPLE_LLM_OUTPUT)])
    client = make_client(llm)
    resp = client.post("/link-analysis", json={"url": "https://abc.example"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    analysis = data["analysis"]
    for key in ["competitor_analysis", "target_search_queries", "seo_improvements", "top_services", "target_audience"]:
        assert key in analysis

    names = [c["name"] for c in analysis["competitor_analysis"]["competitors"]]
    assert names == ["XYZ Web", "Pixel Studio", "Code House"]
    assert all(c["source"] == "ai_suggestion" for c in analysis["competitor_analysis"]["competitors"])
    assert analysis["competitor_analysis"]["competitors"][0]["website"] == "https://xyzweb.com"

    assert len(analysis["target_search_queries"]) == 5
    assert analysis["target_search_queries"][0]["platforms"] == ["Google", "X (Twitter)"]
    assert len(analysis["top_services"]) == 5
    assert [s["source"] for s in analysis["top_services"]] == [
        "website", "inferred", "inferred", "inferred", "inferred"
    ]
    assert analysis["seo_improvements"]["current_title"] == "ABC Technologies - Home"
    assert data["meta"]["estimated_cost_usd"] == pytest.approx(0.0099)


def test_fewer_than_five_services_are_reprompted():
    short_output = copy.deepcopy(SAMPLE_LLM_OUTPUT)
    short_output["analysis"]["top_services"] = short_output["analysis"]["top_services"][:3]
    llm = FakeLLM([json.dumps(short_output), json.dumps(SAMPLE_LLM_OUTPUT)])

    resp = make_client(llm).post("/link-analysis", json={"url": "https://abc.example"})

    assert resp.status_code == 200
    assert llm.calls == 2
    assert len(resp.json()["analysis"]["top_services"]) == 5


def test_cache_avoids_second_llm_call():
    llm = FakeLLM([json.dumps(SAMPLE_LLM_OUTPUT)])
    client = make_client(llm)
    client.post("/link-analysis", json={"url": "https://abc.example"})
    second = client.post("/link-analysis", json={"url": "https://abc.example/"})
    assert second.json()["meta"]["cached"] is True
    assert llm.calls == 1


def test_bad_json_is_retried_once():
    llm = FakeLLM(["not json", json.dumps(SAMPLE_LLM_OUTPUT)])
    resp = make_client(llm).post("/link-analysis", json={"url": "https://abc.example"})
    assert resp.status_code == 200
    assert llm.calls == 2
    assert resp.json()["meta"]["llm_calls"] == 2


def test_bad_json_twice_returns_502():
    llm = FakeLLM(["not json"])
    resp = make_client(llm).post("/link-analysis", json={"url": "https://abc.example"})
    assert resp.status_code == 502
    assert resp.json() == {"success": False, "error": {"code": "llm_error",
                           "message": "The AI model did not return valid structured JSON after 2 tries."}}


def test_invalid_url_returns_400():
    client = TestClient(app)  # real service: fails before any LLM call
    resp = client.post("/link-analysis", json={"url": "ftp://example.com"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_url"


def test_private_url_returns_400():
    resp = TestClient(app).post("/link-analysis", json={"url": "http://127.0.0.1:80/"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "blocked_url"


def test_missing_body_returns_422():
    resp = TestClient(app).post("/link-analysis", json={})
    assert resp.status_code == 422
    assert resp.json()["success"] is False
