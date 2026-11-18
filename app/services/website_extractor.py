"""Fetch a website safely and pull out the useful text.

Steps: fetch home page -> follow redirects safely -> parse HTML (HyperText Markup Language)
-> remove noise (scripts, styles) -> keep title, meta tags, headings, menu, text
-> also read up to 2 helpful inner pages (About, Services, Products).
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.utils.validators import (
    AppError,
    ContentExtractionError,
    WebsiteFetchError,
    normalize_url,
    resolve_and_check_host,
)

logger = logging.getLogger(__name__)

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 LinkAnalysisBot/1.0")
NOISE_TAGS = ["script", "style", "noscript", "svg", "iframe", "canvas", "template", "form"]
HELPFUL_WORDS = ("about", "service", "product", "solution", "what-we-do", "offer",
                 "industr", "pricing", "feature", "company")
SKIP_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".zip", ".mp4", ".svg", ".webp", ".doc", ".docx")
MIN_READABLE_CHARS = 200
MAX_BROWSER_REQUESTS = 100
BLOCKED_BROWSER_RESOURCE_TYPES = {"font", "image", "media"}


@dataclass
class PageContent:
    url: str
    title: str = ""
    meta_description: str = ""
    site_name: str = ""
    headings: List[str] = field(default_factory=list)
    nav_items: List[str] = field(default_factory=list)
    structured_data: List[str] = field(default_factory=list)
    text: str = ""
    internal_links: List[str] = field(default_factory=list)

    def to_block(self, max_chars: int) -> str:
        lines = [f"### PAGE: {self.url}"]
        if self.title:
            lines.append(f"Title: {self.title}")
        if self.site_name:
            lines.append(f"Site name: {self.site_name}")
        if self.meta_description:
            lines.append(f"Meta description: {self.meta_description}")
        if self.structured_data:
            lines.append("Structured data: " + " | ".join(self.structured_data[:5]))
        if self.headings:
            lines.append("Headings: " + " | ".join(self.headings[:40]))
        if self.nav_items:
            lines.append("Menu items: " + " | ".join(self.nav_items[:30]))
        lines.append("Text:")
        header = "\n".join(lines)
        room = max(0, max_chars - len(header) - 1)
        return header + "\n" + self.text[:room]


@dataclass
class WebsiteContent:
    url: str
    final_url: str
    pages: List[PageContent]

    @property
    def domain(self) -> str:
        host = urlsplit(self.final_url).hostname or ""
        return host[4:] if host.startswith("www.") else host

    @property
    def home(self) -> PageContent:
        return self.pages[0]

    def to_prompt_text(self, max_chars: int) -> str:
        """Home page gets about 60% of the budget, other pages share the rest."""
        if len(self.pages) == 1:
            return self.home.to_block(max_chars)
        home_budget = int(max_chars * 0.6)
        other_budget = (max_chars - home_budget) // (len(self.pages) - 1)
        blocks = [self.home.to_block(home_budget)]
        blocks += [p.to_block(other_budget) for p in self.pages[1:]]
        return "\n\n".join(blocks)[:max_chars]


def _dedupe(items) -> List[str]:
    seen, out = set(), []
    for item in items:
        clean = " ".join(str(item).split())
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            out.append(clean)
    return out


def _same_site(url: str, base_host: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    strip = lambda h: h[4:] if h.startswith("www.") else h  # noqa: E731
    return strip(host) == strip(base_host)


def parse_page(html: str, url: str) -> PageContent:
    soup = BeautifulSoup(html, "html.parser")
    page = PageContent(url=url)

    if soup.title:
        page.title = " ".join(soup.title.get_text().split())

    def meta(attr: str, value: str) -> str:
        tag = soup.find("meta", attrs={attr: value})
        return " ".join(tag.get("content", "").split()) if tag else ""

    page.meta_description = meta("name", "description") or meta("property", "og:description")
    page.site_name = meta("property", "og:site_name")

    # JSON-LD (structured data) often has the real company name and description.
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for item in items:
            if isinstance(item, dict) and item.get("name"):
                kind = item.get("@type", "Thing")
                kind = ",".join(kind) if isinstance(kind, list) else kind
                desc = str(item.get("description", ""))[:200]
                page.structured_data.append(f"{kind}: {item['name']}" + (f" - {desc}" if desc else ""))

    base_host = urlsplit(url).hostname or ""
    links, nav = [], []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolute = urljoin(url, href).split("#")[0]
        if _same_site(absolute, base_host):
            links.append(absolute)
        if a.find_parent(["nav", "header"]):
            text = a.get_text(" ", strip=True)
            if 1 < len(text) < 40:
                nav.append(text)
    page.internal_links = _dedupe(links)
    page.nav_items = _dedupe(nav)

    for tag in soup(NOISE_TAGS):
        tag.decompose()

    page.headings = _dedupe(h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"]))

    root = soup.find("main") or soup.body or soup
    lines = [line.strip() for line in root.get_text("\n").split("\n")]
    lines = [line for line in lines if len(line) > 2]
    page.text = "\n".join(_dedupe(lines))
    return page


def pick_extra_pages(links: List[str], base_url: str, limit: int) -> List[str]:
    """Pick inner pages that most likely describe the business."""
    base = base_url.rstrip("/")
    scored = []
    for link in links:
        path = urlsplit(link).path.lower()
        if link.rstrip("/") == base or path.endswith(SKIP_EXTENSIONS) or path.count("/") > 3:
            continue
        score = sum(word in path for word in HELPFUL_WORDS)
        if score:
            scored.append((score, -len(path), link))
    scored.sort(reverse=True)
    return [link for _, _, link in scored[:limit]]


async def fetch_html(client: httpx.AsyncClient, url: str) -> Tuple[str, str]:
    """Download one page. Every redirect is checked again for SSRF safety."""
    current = url
    for _ in range(settings.MAX_REDIRECTS + 1):
        await asyncio.to_thread(resolve_and_check_host, urlsplit(current).hostname)
        try:
            async with client.stream("GET", current) as resp:
                if resp.is_redirect:
                    location = resp.headers.get("location")
                    if not location:
                        raise WebsiteFetchError("Website sent a redirect without a target address.")
                    current = normalize_url(urljoin(current, location))
                    continue
                if resp.status_code in (401, 403, 429):
                    raise WebsiteFetchError(
                        f"Website blocked our request (HTTP status {resp.status_code}). "
                        "It may block bots or need a login."
                    )
                if resp.status_code >= 400:
                    raise WebsiteFetchError(f"Website returned an error (HTTP status {resp.status_code}).")
                content_type = resp.headers.get("content-type", "").lower()
                if content_type and "html" not in content_type:
                    raise WebsiteFetchError(f"URL is not a web page (content type: {content_type}).")

                chunks, size = [], 0
                async for chunk in resp.aiter_bytes():
                    size += len(chunk)
                    if size > settings.MAX_PAGE_BYTES:
                        break  # very big page: keep the first part only
                    chunks.append(chunk)
                body = b"".join(chunks)
                try:
                    text = body.decode(resp.charset_encoding or "utf-8", errors="replace")
                except LookupError:
                    text = body.decode("utf-8", errors="replace")
                return current, text
        except httpx.TimeoutException:
            raise WebsiteFetchError("Website took too long to respond (timeout).")
        except httpx.HTTPError as exc:
            raise WebsiteFetchError(f"Could not connect to the website ({exc.__class__.__name__}).")
    raise WebsiteFetchError("Website has too many redirects.")


async def render_page(url: str) -> Tuple[str, str]:
    """Render a sparse page in Chromium, checking every browser request for SSRF."""
    try:
        from playwright.async_api import Error as PlaywrightError
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise WebsiteFetchError(
            "JavaScript rendering is unavailable. Install project dependencies and Chromium."
        ) from exc

    requests_seen = 0
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    service_workers="block",
                    user_agent=USER_AGENT,
                )
                page = await context.new_page()

                async def guard_request(route, request):
                    nonlocal requests_seen
                    requests_seen += 1
                    if requests_seen > MAX_BROWSER_REQUESTS:
                        await route.abort()
                        return
                    if request.resource_type in BLOCKED_BROWSER_RESOURCE_TYPES:
                        await route.abort()
                        return
                    try:
                        request_url = normalize_url(request.url)
                        host = urlsplit(request_url).hostname
                        await asyncio.to_thread(resolve_and_check_host, host)
                    except AppError:
                        await route.abort()
                        return
                    await route.continue_()

                await page.route("**/*", guard_request)
                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=int(settings.JS_RENDER_TIMEOUT_SECONDS * 1000),
                )
                await page.wait_for_timeout(1000)
                rendered_html = await page.content()
                if len(rendered_html.encode("utf-8")) > settings.MAX_PAGE_BYTES:
                    raise WebsiteFetchError(
                        "Rendered website page exceeds the configured size limit."
                    )
                final_url = normalize_url(page.url)
                await asyncio.to_thread(resolve_and_check_host, urlsplit(final_url).hostname)
                return final_url, rendered_html
            finally:
                await browser.close()
    except PlaywrightTimeoutError as exc:
        raise WebsiteFetchError("Website took too long to render in the browser.") from exc
    except PlaywrightError as exc:
        raise WebsiteFetchError(
            f"Could not render the website in the browser ({exc.__class__.__name__})."
        ) from exc


def _readable_chars(page: PageContent) -> int:
    return len(page.text) + len(page.meta_description)


async def _try_page(client: httpx.AsyncClient, url: str) -> Optional[PageContent]:
    try:
        final_url, html = await fetch_html(client, url)
        page = parse_page(html, final_url)
        if _readable_chars(page) < MIN_READABLE_CHARS:
            final_url, html = await render_page(url)
            page = parse_page(html, final_url)
        return page
    except AppError as exc:  # inner pages are optional
        logger.info("Skipped inner page %s: %s", url, exc.message)
        return None


async def extract_website(url: str) -> WebsiteContent:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml",
               "Accept-Language": "en-US,en;q=0.9"}
    timeout = httpx.Timeout(settings.FETCH_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=False) as client:
        final_url, html = await fetch_html(client, url)
        home = parse_page(html, final_url)
        if _readable_chars(home) < MIN_READABLE_CHARS:
            final_url, html = await render_page(final_url)
            home = parse_page(html, final_url)
        extra = pick_extra_pages(home.internal_links, final_url, settings.MAX_EXTRA_PAGES)
        extra_pages = await asyncio.gather(*(_try_page(client, link) for link in extra))

    pages = [home] + [p for p in extra_pages if p and p.text]
    readable = sum(len(p.text) for p in pages) + len(home.meta_description)
    if readable < MIN_READABLE_CHARS:
        raise ContentExtractionError(
            "Website has very little readable text. It may load content with JavaScript (JS) "
            "or block bots, so it cannot be analyzed reliably."
        )
    return WebsiteContent(url=url, final_url=final_url, pages=pages)
