# AI-Powered Website Link Analysis API

A FastAPI app that reads a website, sends the cleaned content to an LLM (Large Language Model), and returns **5 sections of analysis** as JSON (JavaScript Object Notation):

1. Competitor vs Your Brand
2. Top 5 Target Search Queries (Google, Facebook, Instagram, LinkedIn, X/Twitter)
3. SEO (Search Engine Optimization) Improvements
4. Top 5 Services
5. Target Audience

---

## 1. Tech Stack

| Part                                              | Tool                                                                   |
| ------------------------------------------------- | ---------------------------------------------------------------------- |
| Language                                          | Python 3.10+                                                           |
| API (Application Programming Interface) framework | FastAPI + Uvicorn                                                      |
| Data validation                                   | Pydantic v2                                                            |
| HTTP (HyperText Transfer Protocol) client         | HTTPX (async)                                                          |
| HTML (HyperText Markup Language) parser           | BeautifulSoup                                                          |
| JavaScript-rendered websites                      | Playwright + Chromium fallback                                         |
| LLM                                               | Google Gemini (default), Anthropic Claude or OpenAI - change in `.env` |
| Tests                                             | Pytest                                                                 |

---

## 2. Project Structure

```
ai-link-analysis/
├── app/
│   ├── main.py                  # FastAPI app, endpoint, error handlers
│   ├── config.py                # settings from .env + model prices
│   ├── schemas.py               # Pydantic request/response models
│   ├── services/
│   │   ├── website_extractor.py # safe fetch + clean website text
│   │   ├── llm_service.py       # Gemini / Claude / OpenAI clients, retry, fallback
│   │   ├── analysis_service.py  # main flow, prompt, JSON check, cache
│   │   └── competitor_service.py# clean + label competitors
│   └── utils/
│       └── validators.py        # URL check + SSRF protection
├── tests/
│   └── test_link_analysis.py    # Tests run without internet or API keys
├── start.bat                    # Windows setup, test, and launch helper
├── screenshot/                  # Swagger, API, validation, and test evidence
│   └── response_1794988467405.json # Full successful Swagger response
├── .env.example
├── requirements.txt
└── README.md
```

---

## 3. Setup and Run

### Windows: quickest setup

1. Copy [.env.example](.env.example) to `.env`.
2. Open `.env` and set:

   ```env
   LLM_PROVIDER=gemini
   LLM_MODEL=gemini-3.8-flash
   LLM_FALLBACK_PROVIDER=
   LLM_FALLBACK_MODEL=
   GEMINI_API_KEY=your-real-gemini-key
   ```

3. Double-click `start.bat`, or run it from Command Prompt:

   ```bat
   start.bat
   ```

`start.bat` creates `.venv` if needed, installs dependencies and the Chromium browser if missing, runs all tests, and then starts the API at port 4000.

Claude fallback is optional. When you do not have an Anthropic API key, leave `LLM_FALLBACK_PROVIDER` and `LLM_FALLBACK_MODEL` empty.

### Manual setup

```bash
# 1. Get the code
git clone https://github.com/MAliSheikh/ai-link-analysis.git
cd ai-link-analysis

# 2. Create a virtual environment (venv)
python -m venv .venv
# Windows:      .venv\Scripts\activate
# Mac / Linux:  source .venv/bin/activate

# 3. Install packages
pip install -r requirements.txt
python -m playwright install chromium

# 4. Create your .env file and add your API key
cp .env.example .env        # Windows: copy .env.example .env
```

Get a free Gemini API key from **Google AI Studio** (https://aistudio.google.com) and put it in `.env`:

```
GEMINI_API_KEY=your-key-here
```

Configure the provider and optional fallback in `.env`. A provider's API key is required when that provider is enabled.

| Variable                    | Purpose                                                          |
| --------------------------- | ---------------------------------------------------------------- |
| `LLM_PROVIDER`              | Main provider: `gemini`, `anthropic`, or `openai`                |
| `LLM_MODEL`                 | Model name for the main provider                                 |
| `LLM_FALLBACK_PROVIDER`     | Optional fallback provider; leave empty to disable               |
| `LLM_FALLBACK_MODEL`        | Model name for the fallback provider                             |
| `GEMINI_API_KEY`            | Gemini API key                                                   |
| `ANTHROPIC_API_KEY`         | Anthropic API key                                                |
| `OPENAI_API_KEY`            | OpenAI API key                                                   |
| `GEMINI_API_URL_TEMPLATE`   | Gemini endpoint template; `{model}` is replaced with `LLM_MODEL` |
| `ANTHROPIC_API_URL`         | Anthropic Messages API endpoint                                  |
| `OPENAI_API_URL`            | OpenAI Chat Completions API endpoint                             |
| `GEMINI_THINKING_BUDGET`    | Gemini 2.5 thinking budget; `0` disables thinking                |
| `OPENAI_REASONING_EFFORT`   | Optional OpenAI reasoning effort                                 |
| `FETCH_TIMEOUT_SECONDS`     | Website request timeout                                          |
| `JS_RENDER_TIMEOUT_SECONDS` | Maximum time allowed for browser rendering of a JavaScript page  |
| `MAX_PAGE_BYTES`            | Maximum bytes read from each page                                |
| `MAX_REDIRECTS`             | Maximum website redirects to follow                              |
| `MAX_EXTRA_PAGES`           | Maximum helpful inner pages to fetch                             |
| `MAX_CONTENT_CHARS`         | Maximum website text sent to the model                           |
| `LLM_TIMEOUT_SECONDS`       | Model request timeout                                            |
| `MAX_OUTPUT_TOKENS`         | Maximum model output tokens                                      |
| `CACHE_TTL_SECONDS`         | Analysis cache lifetime; `0` disables caching                    |

Defaults and example endpoint values are provided in `.env.example`.

```bash
# 5. Start the server
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

- API docs (Swagger UI - User Interface): http://localhost:4000/docs
- Health check: http://localhost:4000/health

```bash
# 6. Run tests
.venv\Scripts\python.exe -m pytest -q
```

If Windows PowerShell cannot run `.venv\Scripts\python.exe -m pytest -q` as written, run it from Command Prompt instead.

### Test the live API

After `start.bat` has opened the server:

```bat
curl http://localhost:4000/health
```

From PowerShell:

```powershell
$body = @{ url = "https://www.python.org" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:4000/link-analysis" -ContentType "application/json" -Body $body
```

Swagger UI: http://localhost:4000/docs

---

## 4. How to Use

**Request**

```bash
curl -X POST http://localhost:4000/link-analysis \
  -H "Content-Type: application/json" \
  -d '{"url": "https://scenvora.com/"}'
```

**Example response (excerpt from the successful Scenvora Swagger run)**

The excerpt below contains real values; fields are omitted for brevity. The [complete JSON response](screenshot/response_1794988467405.json) and Swagger screenshots are in the [`screenshot/`](screenshot/) folder.

```json
{
  "success": true,
  "website": "https://scenvora.com/",
  "brand": {
    "name": "Scenvora",
    "category": "Fragrance & Perfumery",
    "summary": "Scenvora is a boutique Pakistani fragrance brand specializing in small-batch, artisanal eau de parfum crafted with layered top, heart, and base notes. Offering individual scents and discovery tester kits, the brand provides accessible luxury with nationwide cash-on-delivery service."
  },
  "analysis": {
    "competitor_analysis": {
      "competitors": [
        { "name": "Scents'N Stories", "source": "ai_suggestion" },
        { "name": "J. Fragrances", "source": "ai_suggestion" },
        { "name": "Rawaha", "source": "ai_suggestion" }
      ],
      "note": "Competitors are AI-generated suggestions based on the website content and the model's general knowledge. They are not verified with live market data. Please check them before use."
    },
    "target_search_queries": [
      { "query": "best long lasting perfume in Pakistan", "platforms": ["Google"] },
      { "query": "perfume tester kit online Pakistan", "platforms": ["Google"] },
      { "query": "artisan small batch eau de parfum", "platforms": ["Instagram", "Google"] },
      { "query": "affordable luxury perfumes for women Pakistan", "platforms": ["Google", "Facebook"] },
      { "query": "cash on delivery perfume Pakistan", "platforms": ["Google", "Facebook"] }
    ],
    "seo_improvements": {
      "current_title": "Scenvora — Luxury Perfume",
      "current_meta_description": "Discover Scenvora perfumes in an immersive 3D experience.",
      "primary_keyword": "luxury perfume Pakistan",
      "recommended_title": "Luxury Perfume in Pakistan | Scenvora Fragrances",
      "meta_description": "Explore Scenvora luxury perfumes in Pakistan. Discover artisanal small-batch Eau de Parfum and discovery sampler kits with convenient cash on delivery."
    },
    "top_services": [
      { "name": "Handcrafted Eau de Parfum", "source": "website" },
      { "name": "Signature Tester Discovery Kit", "source": "website" },
      { "name": "Bespoke Scent Consultation", "source": "inferred" },
      { "name": "Corporate & Event Fragrance Gifting", "source": "inferred" },
      { "name": "Refill & Subscription Program", "source": "inferred" }
    ],
    "target_audience": {
      "primary_audience": [
        "Young working professionals seeking signature luxury scents",
        "Fragrance enthusiasts interested in layered perfume notes"
      ],
      "geographic_focus": "Pakistan (nationwide delivery)"
    }
  },
  "notes": [
    "Search volumes and rankings are not included because no search-volume data source is connected.",
    "Services marked 'inferred' are AI recommendations, not services named on the website.",
    "Estimated cost uses standard paid list prices; actual charges depend on the provider account tier and may differ."
  ],
  "meta": {
    "provider": "gemini",
    "model": "gemini-3.8-flash",
    "input_tokens": 2085,
    "output_tokens": 3993,
    "estimated_cost_usd": 0.016538,
    "llm_calls": 1,
    "llm_time_seconds": 35.57,
    "total_time_seconds": 59.666,
    "pages_analyzed": [
      "https://scenvora.com/",
      "https://scenvora.com/products?sort=newest",
      "https://scenvora.com/products?family=Floral%20Fruity"
    ],
    "content_characters_sent": 3882,
    "cached": false
  }
}
```

The Scenvora response above is a separate example run from the five-site pilot measurements in Section 6; token counts, cost, and timing can vary between runs. Recommendations marked `inferred` and AI-suggested competitor claims should be verified before use.

**Error responses** (always the same shape)

| Case                                              | HTTP status | `error.code`          |
| ------------------------------------------------- | ----------- | --------------------- |
| Bad URL (for example `ftp://...`)                 | 400         | `invalid_url`         |
| Private / internal address (SSRF)                 | 400         | `blocked_url`         |
| Missing `url` in body                             | 422         | `invalid_request`     |
| Website has almost no text (JavaScript-only site) | 422         | `not_enough_content`  |
| Website down, timeout, or blocks bots             | 502         | `website_unreachable` |
| LLM failed or returned bad JSON 2 times           | 502         | `llm_error`           |
| API key missing                                   | 500         | `llm_not_configured`  |

```json
{ "success": false, "error": { "code": "blocked_url", "message": "This URL points to a private or internal network address..." } }
```

---

## 5. How It Works (Processing Flow)

1. **Validate URL** - only `http`/`https`, ports 80/443, no username/password in URL.
2. **SSRF protection** - DNS (Domain Name System) lookup, and **every** IP (Internet Protocol) address must be public. Blocks `localhost`, `127.0.0.1`, `10.x`, `192.168.x`, `169.254.169.254` (cloud metadata), IPv6 local, `::ffff:127.0.0.1` tricks, `.local`/`.internal` names.
3. **Safe fetch** - redirects are followed **by hand**, and each new address is checked again. Max 3 MB (megabytes) per page, 15 s timeout.
4. **Extract** - title, meta description, JSON-LD (structured data, often has the real company name), headings, menu items, main text. Scripts, styles, forms and SVG are removed. Duplicate lines are removed.
5. **JavaScript rendering** - if static HTML has too little readable text, Chromium renders the page and the extractor parses the rendered HTML. Image, media, and font requests are skipped; every browser HTTP(S) request is checked against private/internal addresses.
6. **Inner pages** - up to 2 helpful pages (About, Services, Products, Solutions) are read too, for better accuracy.
7. **Trim** - content is cut to 12,000 characters (about 3,000 tokens). Home page gets 60%.
8. **LLM call** - one call creates all 5 sections, in JSON mode.
9. **Validate** - Pydantic checks the JSON. If it is broken, we ask the LLM **once** more with the error message.
10. **Clean** - remove the brand from its own competitor list, remove duplicates, label competitors `ai_suggestion`, keep only the allowed platforms, keep max 5 queries/services.
11. **Cache** - result is kept for 1 hour, so the same URL does not cost again.

### Honesty rules (from the test instructions)

- Services are marked `"source": "website"` (found on the site) or `"inferred"` (AI suggestion).
- Competitors are always marked `"source": "ai_suggestion"` with a note, because no live market-data API is used.
- No search volumes or rankings are returned (no data source for them).
- The prompt tells the LLM that website text is untrusted, so hidden instructions on a page (prompt injection) are ignored.

---

## 6. LLM Research - Cost, Speed and Accuracy

Prices and model details below were checked against provider documentation on **18 November 2026**. Prices are standard paid-tier USD per million tokens unless noted; free-tier availability and quotas vary by provider and account.

### A. Comparison

| Provider / model             | Input / 1M                                 | Output / 1M                                | Context                         | Speed information                                                                                           | JSON capability                                                                                           | Accuracy evidence / fit                                                                                                       | Availability / access                                                   |
| ---------------------------- | ------------------------------------------ | ------------------------------------------ | ------------------------------- | ----------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Google `gemini-3.8-flash`    | $0.75 through Dec 31, 2026                 | $3.75 through Dec 31, 2026                 | 1,048,576 tokens                | Flash model; provider describes it as speed- and cost-efficient. Cross-provider latency not measured.       | Structured outputs supported; this app requests JSON MIME type and validates with Pydantic.               | No independent accuracy benchmark. **Selected for this project** because Gemini is configured and has a large context window. | Gemini free-tier access may be available; quotas and eligibility apply. |
| Anthropic `claude-haiku-5-5` | $0.10 up to 100K input tokens; $0.50 above | $0.50 up to 100K input tokens; $2.50 above | 1M tokens                       | Anthropic describes it as its fastest current model.                                                        | Provider structured-output support exists; this app currently uses prompted JSON and Pydantic validation. | No independent accuracy benchmark. Potential lower-cost option if an Anthropic key is added and tested.                       | Paid API key required; none configured here.                            |
| OpenAI `gpt-5.4-mini`        | $0.75                                      | $4.50                                      | 400K tokens; 272K maximum input | OpenAI describes it as faster and efficient for high-volume workloads. Cross-provider latency not measured. | Structured outputs supported; this app's adapter uses JSON response mode.                                 | No independent accuracy benchmark.                                                                                            | Paid API key required; not configured here.                             |

Model capabilities and provider descriptions are not a substitute for application-specific accuracy or latency benchmarks. Model capacity and rate limits may vary; no model is guaranteed to avoid temporary overload.

### B. Estimated cost per website analysis

On 18 November 2026, a sequential Gemini 3.8 Flash pilot analyzed five public websites. All five requests succeeded in one LLM call and returned exactly five services and five search queries. Mean LLM time was **39.504 seconds** and mean total time was **47.700 seconds**. Paid-tier estimates below are not invoices.

| Website     | Input / output tokens | LLM / total seconds | Estimated paid cost |
| ----------- | --------------------: | ------------------: | ------------------: |
| Scenvora    |         2,096 / 4,455 |     41.710 / 66.774 |           $0.018278 |
| Python.org  |         3,639 / 4,139 |     34.711 / 38.509 |           $0.018250 |
| Mozilla.org |         3,073 / 4,281 |     37.230 / 42.715 |           $0.018358 |
| Shopify.com |         3,248 / 4,934 |     42.541 / 46.173 |           $0.020938 |
| IKEA.com    |         1,494 / 5,076 |     41.330 / 44.327 |           $0.020155 |

| Website     | Expected brand label       | Returned brand             | Match |
| ----------- | -------------------------- | -------------------------- | ----- |
| Scenvora    | Scenvora                   | Scenvora                   | Pass  |
| Python.org  | Python Software Foundation | Python Software Foundation | Pass  |
| Mozilla.org | Mozilla                    | Mozilla                    | Pass  |
| Shopify.com | Shopify                    | Shopify                    | Pass  |
| IKEA.com    | IKEA                       | IKEA                       | Pass  |

This is a narrow manual smoke check: **5/5 brand labels matched**, and **5/5 responses** passed the exact-five services and exact-five queries requirements. Only Scenvora's service sources were spot-checked: two website offerings and three recommendations marked `inferred`. Competitor, SEO, audience, and the other service claims still require human verification. This is **not** a comprehensive accuracy benchmark; no labeled multi-site factual-accuracy benchmark has been run.

The cross-provider cost estimates below apply the Scenvora Gemini token counts (2,096 input, 4,455 output) to each model's listed rates. They are illustrative because providers tokenize the same prompt differently.

| Model                                       | Cost per analysis (estimate) | Cost per 1,000 analyses |
| ------------------------------------------- | ---------------------------- | ----------------------- |
| Gemini 3.8 Flash, standard paid tier        | $0.018278                    | $18.28                  |
| Claude Haiku 5.5 (prompt under 100K tokens) | $0.002437                    | $2.44                   |
| GPT-5.4 mini                                | $0.021620                    | $21.62                  |

These are list-price estimates, not measured invoices. `meta.estimated_cost_usd` uses configured standard paid-tier prices; Gemini free-tier usage may have no token charge while it remains within the account's free quota. The app cannot determine the account's tier. Gemini's published standard rates for this model are scheduled to change on **1 January 2027**, so re-check prices before then.

### C. Measured vs estimated

| Measure       | Evidence                                                                                                                                                                                                                                       |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Prices        | Provider documentation checked 18 Nov 2026; listed paid-tier prices can change.                                                                                                                                                                |
| Token counts  | Measured for five Gemini website requests above. Other providers' token counts were not measured and may differ.                                                                                                                               |
| Response time | Five Gemini requests averaged 39.504 s LLM time and 47.700 s total; this is a small pilot, not a long-term or cross-provider benchmark.                                                                                                        |
| Cost          | Recalculated from measured Gemini tokens using standard paid-tier prices; not invoices.                                                                                                                                                        |
| Accuracy      | Manual pilot check: 5/5 brand labels matched and 5/5 responses passed schema/count checks. Other semantic claims were not comprehensively scored; **no formal factual-accuracy benchmark** against a labeled multi-site test set has been run. |

### D. Final Recommendation

| Item                     | Answer                                                                                              |
| ------------------------ | --------------------------------------------------------------------------------------------------- |
| Recommended provider     | Google Gemini API                                                                                   |
| Recommended model        | `gemini-3.8-flash`                                                                                  |
| Observed token usage     | 2,096 input and 4,455 output tokens for one Scenvora run; not a universal average                   |
| Estimated paid-tier cost | $0.018278 for that observed run; free-tier eligibility can change the actual charge                 |
| Observed response time   | 41.710 s LLM time and 66.774 s total for Scenvora; five-site pilot means were 39.504 s and 47.700 s |
| Fallback model           | None configured. Claude requires an Anthropic key; the current setup uses Gemini only.              |

**Why `gemini-3.8-flash`?**

1. It is the model configured for the available Gemini credential.
2. The model supports structured output and provides a 1M-token context window; the application sends a much smaller 12,000-character website excerpt.
3. All five pilot requests completed successfully. This small pilot does not establish typical long-term latency, accuracy, or availability.
4. Gemini free-tier use may be available, but has account-specific quotas and can return temporary capacity errors. Paid-tier estimates use the published token rates.

Claude Haiku 5.5 is a lower-cost candidate at this request size, but it is not configured because no Anthropic key is available. Adding a provider key and validating output quality are prerequisites before enabling it as fallback.

**Balancing accuracy, speed and cost:**
- To compare providers fairly, run the same labeled website set with each provider and compare factual support, JSON validity, latency, and cost. That cross-provider benchmark has not yet been run.
- Haiku 5.5's input/output rates increase above 100K prompt tokens; this app's 12,000-character cap stays well below that threshold for ordinary English text.

### E. Cost Optimization (what this project does)

| Idea                                                          | Done in code                                      |
| ------------------------------------------------------------- | ------------------------------------------------- |
| Remove scripts, styles, SVG, forms, duplicate lines           | Yes - `website_extractor.py`                      |
| Limit content size (12,000 characters)                        | Yes - `MAX_CONTENT_CHARS`                         |
| Only 2 extra pages, chosen by keyword score                   | Yes - `pick_extra_pages()`                        |
| One LLM call for all 5 sections (not 5 calls)                 | Yes - system prompt is shared                     |
| Short, fixed system prompt                                    | Yes                                               |
| Cache results for 1 hour                                      | Yes - `TTLCache`                                  |
| Retry only on temporary errors (429, 5xx, timeout)            | Yes                                               |
| Fix broken JSON with max 1 extra call                         | Yes                                               |
| Require exactly 5 services and label inferred recommendations | Yes - Pydantic validation and the analysis prompt |
| Easy switch to a smaller model                                | Yes - `.env` only                                 |

**More ideas for production:** use Redis instead of memory cache; use the provider's **prompt caching** for the fixed system prompt; use a provider's **Batch API** for jobs that do not need an instant answer; use a small model only for extraction and a bigger one for competitors.

### Sources (checked 18 Nov 2026)

- [Google Gemini 3.8 Flash model details](https://aistudio.google.com/docs/models/gemini-3.8-flash)
- [Google Gemini API pricing](https://aistudio.google.com/docs/pricing)
- [Google structured outputs](https://aistudio.google.com/docs/structured-output)
- [Anthropic Claude Haiku 5.5 model details](https://platform.claude.com/docs/en/models/haiku-5-5/overview)
- [Anthropic Claude API pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [OpenAI GPT-5.4 mini model details](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
- [OpenAI API pricing](https://developers.openai.com/api/docs/pricing)

---

## 7. Security

- API keys only in `.env` (in `.gitignore`). `.env.example` has no real keys.
- SSRF protection on the first URL **and** on every redirect.
- Page size limit, timeout, and max 5 redirects.
- Website text is treated as untrusted data in the prompt.

**Known limit:** a DNS rebinding attack (DNS answer changes between our check and the real connection) is not fully blocked. A production fix is to connect directly to the checked IP address, or use an egress proxy.

## 8. Other Limits

- Some highly interactive sites may still return `not_enough_content` if they require login, block automated browsers, or render content only after user interaction. JavaScript rendering requires the Chromium browser installed by `start.bat` or `python -m playwright install chromium`.
- Some sites block bots (Cloudflare, HTTP 403) - we return a clear error.
- Competitors come from the LLM's knowledge, not live data. A search API (for example SerpAPI or Google Custom Search) could verify them.

## 9. Screenshots / Logs

Evidence from a local run is saved in [`screenshot/`](screenshot/):

| File                                                                                                                                | Evidence                                              |
| ----------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| [01-test-passed.png](screenshot/01-test-passed.png)                                                                                 | Automated tests passed                                |
| [02-api-logs.png](screenshot/02-api-logs.png)                                                                                       | API server logs                                       |
| [03-request-swaager.png](screenshot/03-request-swaager.png)                                                                         | Swagger request                                       |
| [04.1-resposne-swagger.png](screenshot/04.1-resposne-swagger.png)–[04.6-resposne-swagger.png](screenshot/04.6-resposne-swagger.png) | Successful Swagger response, split across screenshots |
| [05-linkvalidation-error.png](screenshot/05-linkvalidation-error.png)                                                               | URL validation error response                         |
| [response_1794988467405.json](screenshot/response_1794988467405.json)                                                               | Complete successful response in JSON format           |
