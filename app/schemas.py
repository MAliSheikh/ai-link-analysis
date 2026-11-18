"""Pydantic models = the shape (structure) of requests and responses.
They also validate the JSON (JavaScript Object Notation) that comes back from the LLM."""
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

ALLOWED_PLATFORMS = ["Google", "Facebook", "Instagram", "LinkedIn", "X (Twitter)"]
_PLATFORM_ALIASES = {
    "google": "Google", "google search": "Google",
    "facebook": "Facebook", "fb": "Facebook",
    "instagram": "Instagram", "ig": "Instagram",
    "linkedin": "LinkedIn",
    "x": "X (Twitter)", "twitter": "X (Twitter)", "x (twitter)": "X (Twitter)", "x/twitter": "X (Twitter)",
}


# ---------- Request ----------
class LinkAnalysisRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048, examples=["https://example.com"])


# ---------- LLM output parts ----------
class BrandInfo(BaseModel):
    name: str
    category: str
    summary: str


class Competitor(BaseModel):
    name: str
    website: Optional[str] = None
    main_service: str = ""
    target_market: str = ""
    strengths: List[str] = []
    weaknesses_or_gaps: List[str] = []
    source: str = "ai_suggestion"


class ComparisonRow(BaseModel):
    aspect: str
    your_brand: str
    competitors: Dict[str, str] = {}


class CompetitorAnalysis(BaseModel):
    brand_overview: str
    main_category: str = ""
    products_and_services: List[str] = []
    competitors: List[Competitor] = []
    competitive_advantages: List[str] = []
    opportunities: List[str] = []
    comparison_table: List[ComparisonRow] = []
    note: str = ""


class SearchQuery(BaseModel):
    query: str
    platforms: List[str]
    intent: str
    business_relevance: str = ""
    target_audience: str = ""

    @field_validator("platforms", mode="before")
    @classmethod
    def normalize_platforms(cls, value):
        if isinstance(value, str):
            value = [value]
        result = []
        for item in value or []:
            name = _PLATFORM_ALIASES.get(str(item).strip().lower())
            if name and name not in result:
                result.append(name)
        return result or ["Google"]


class SupportingContent(BaseModel):
    type: str
    title: str
    reason: str = ""


class SEOImprovements(BaseModel):
    current_title: Optional[str] = None
    current_meta_description: Optional[str] = None
    primary_keyword: str
    secondary_keywords: List[str] = []
    long_tail_keywords: List[str] = []
    business_keywords: List[str] = []
    recommended_title: str
    title_structure: str = ""
    meta_description: str
    supporting_content: List[SupportingContent] = []


class Service(BaseModel):
    name: str
    description: str
    target_industry: str = ""
    target_customer: str = ""
    main_benefit: str = ""
    source: Literal["website", "inferred"] = "website"

    @field_validator("source", mode="before")
    @classmethod
    def normalize_source(cls, value):
        value = str(value or "").strip().lower()
        return "website" if value == "website" else "inferred"


class AudienceSegment(BaseModel):
    audience: str
    business_type: str
    requirement: str


class TargetAudience(BaseModel):
    primary_audience: List[str] = []
    secondary_audience: List[str] = []
    industries: List[str] = []
    business_types: List[str] = []
    customer_profiles: List[str] = []
    geographic_focus: str = "Not clearly stated on the website"
    customer_needs: List[str] = []
    customer_challenges: List[str] = []
    customer_interests: List[str] = []
    marketing_segments: List[AudienceSegment] = []


class Analysis(BaseModel):
    competitor_analysis: CompetitorAnalysis
    target_search_queries: List[SearchQuery]
    seo_improvements: SEOImprovements
    top_services: List[Service] = Field(min_length=5, max_length=5)
    target_audience: TargetAudience


class LLMAnalysisOutput(BaseModel):
    """The exact JSON we ask the LLM to return."""
    brand: BrandInfo
    analysis: Analysis


# ---------- API response ----------
class AnalysisMeta(BaseModel):
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: Optional[float] = None
    llm_calls: int = 1
    llm_time_seconds: float
    total_time_seconds: float
    pages_analyzed: List[str] = []
    content_characters_sent: int = 0
    cached: bool = False


class LinkAnalysisResponse(BaseModel):
    success: bool = True
    website: str
    brand: BrandInfo
    analysis: Analysis
    notes: List[str] = []
    meta: AnalysisMeta


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
