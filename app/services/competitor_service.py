"""Clean up the competitor list from the LLM and label it honestly.

We do NOT have a live market-data API, so competitors come from the model's general
knowledge. We clearly mark them as "ai_suggestion" (as the test instructions ask).
"""
from typing import List
from urllib.parse import urlsplit

from app.schemas import Competitor, CompetitorAnalysis

COMPETITOR_NOTE = (
    "Competitors are AI-generated suggestions based on the website content and the model's "
    "general knowledge. They are not verified with live market data. Please check them before use."
)


def _domain(url: str) -> str:
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def clean_competitors(competitors: List[Competitor], brand_name: str, brand_domain: str) -> List[Competitor]:
    seen, result = set(), []
    brand_key = brand_name.strip().lower()
    for comp in competitors:
        key = comp.name.strip().lower()
        if not key or key == brand_key or key in seen:
            continue  # remove empty, duplicate, or the brand itself
        domain = _domain(comp.website or "")
        if domain and domain == brand_domain:
            continue
        comp.website = f"https://{domain}" if domain else None
        comp.source = "ai_suggestion"
        seen.add(key)
        result.append(comp)
    return result[:5]


def finalize_competitor_analysis(section: CompetitorAnalysis, brand_name: str, brand_domain: str) -> CompetitorAnalysis:
    section.competitors = clean_competitors(section.competitors, brand_name, brand_domain)
    note = COMPETITOR_NOTE
    if len(section.competitors) < 3:
        note += " Fewer than 3 competitors were returned because the model was not confident about others."
    section.note = note
    return section
