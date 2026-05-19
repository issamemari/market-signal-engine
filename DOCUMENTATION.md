# Market Signal Engine — Documentation

A market intelligence tool for trade show organizers. It automatically discovers companies and business signals relevant to a salon by scanning news sources, classifying articles with an LLM, scoring them, and generating actionable recommendations for three personas (Sales, Show Director, Marketing).

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        YAML Config                              │
│            (salon themes, signal types, personas)                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                   ┌─────────▼──────────┐
                   │  Pass 1: RSS Fetch  │  fetch_signals.py
                   │  (Google News +     │
                   │   tech press feeds) │
                   └─────────┬──────────┘
                             │ raw articles
                   ┌─────────▼──────────┐
                   │  Pass 2: LLM       │  Claude Haiku
                   │  Classification    │
                   │  (company, sector,  │
                   │   fit score, type)  │
                   └─────────┬──────────┘
                             │ signals (cached to disk)
                   ┌─────────▼──────────┐
                   │  Normalize + Score  │  engine.py
                   │  (dedup, weighted   │
                   │   composite score)  │
                   └─────────┬──────────┘
                             │
                   ┌─────────▼──────────┐
                   │  Activate (LLM)    │  engine.py
                   │  (per-persona      │
                   │   recommendations) │
                   └─────────┬──────────┘
                             │
                   ┌─────────▼──────────┐
                   │  Web Dashboard     │  app.py + static/
                   │  (FastAPI)         │
                   └────────────────────┘
```

## Quick Start

```bash
# 1. Install dependencies
pip install fastapi uvicorn pyyaml anthropic feedparser

# 2. Set your API key
export ANTHROPIC_API_KEY=sk-ant-...

# 3. Fetch and classify signals (populates cache)
python fetch_signals.py bdaip_2026

# 4. Start the dashboard
python app.py
# → http://localhost:8000
```

## File Structure

```
.
├── config/
│   ├── bdaip_2026.yaml        # Big Data & AI Paris config
│   └── mapic_2026.yaml        # MAPIC retail/real-estate config
├── capture/
│   ├── rss_signals.py         # RSS fetching + LLM classification
│   └── fake_signals.py        # Demo signal generator (no API needed)
├── engine.py                  # Core pipeline: normalize → score → activate
├── fetch_signals.py           # CLI to populate RSS cache
├── app.py                     # FastAPI web server
├── static/
│   └── app.js                 # Dashboard frontend logic
├── templates/
│   ├── config.html            # Config editor page
│   └── signals.html           # Signal dashboard page
└── data/
    └── rss_cache_BDAIP.json   # Cached signals (auto-generated)
```

## Pipeline Layers

### Layer 1: Config (`config/*.yaml`)

Each YAML file defines one salon. Key sections:

| Section | Purpose |
|---------|---------|
| `salon` | Name, short code, dates, location, **themes** |
| `personas` | Three personas (sales, direction_salon, marketing) with role, goal, tone |
| `signal_types` | Types of signals to detect (nomination, funding, etc.) with weights |
| `scoring` | Weight distribution and priority thresholds |

There are no hardcoded target companies. Companies are discovered automatically from news articles.

### Layer 2: Capture (`capture/rss_signals.py`)

#### Theme-Based Discovery

Instead of querying for known companies, the engine builds search queries by combining salon **themes** with **signal keywords**:

```
theme ("Intelligence Artificielle Générative")
  × signal keyword ("levée de fonds")
  → Google News query: "Intelligence Artificielle Générative levée de fonds"
```

The keyword map (`SIGNAL_KEYWORDS`) contains French-language search terms for each signal type:

| Signal Type | Example Keywords |
|-------------|-----------------|
| `nomination` | "nomination CDO CTO", "nommé directeur données" |
| `funding` | "levée de fonds", "financement série" |
| `product_launch` | "lance nouveau produit", "annonce solution" |
| `hiring_surge` | "recrute data IA", "recrutement massif" |
| `partnership` | "partenariat stratégique", "alliance technologique" |
| `competing_event` | "salon conférence sponsor" |
| `media_mention` | *(covered by tech feed RSS)* |

Queries are capped at 30 to avoid rate limits. Each query hits Google News RSS (`news.google.com/rss/search?q=...`), returning up to 20 articles. Static tech feeds (L'Usine Digitale, Le Monde Informatique, Maddyness, TechCrunch) are also fetched.

#### LLM Classification

Each unique article (deduplicated by title hash) is sent to **Claude Haiku** with a prompt containing the salon's themes and signal types. The LLM returns:

```json
{
  "relevant": true,
  "company": "Mistral AI",
  "company_sector": "IA Générative",
  "company_salon_fit": 9,
  "signal_type": "funding",
  "title": "Mistral AI lève 600M€ en Série B",
  "summary": "...",
  "raw_entities": {},
  "llm_strength_score": 8
}
```

Key field: **`company_salon_fit`** (0-10) — the LLM scores how relevant the discovered company is to the salon's themes. This replaces the old manual `icp_score` from hardcoded target accounts.

#### Parallelism & Rate Limiting

Classification runs with up to **10 concurrent threads** (`ThreadPoolExecutor`). A thread-safe `RateLimiter` class enforces **40 requests/minute** (under the API's 50 rpm cap). Each thread calls `limiter.wait()` before making an API request.

#### Caching

Results are cached to `data/rss_cache_{SHORT_CODE}.json` with a 1-hour TTL. The web server only reads from cache — it never fetches or classifies. Run `fetch_signals.py` to refresh.

### Layer 3: Normalization (`engine.py → normalize_signals`)

- **Deduplicates** signals by `company|signal_type|title[:50]`
- **Attaches signal type metadata** (label, weight) from config
- `account_info` comes pre-populated from LLM classification (name, sector, icp_score)

### Layer 4: Scoring (`engine.py → score_signal`)

Each signal gets a composite score from three axes:

| Axis | Source | Scale |
|------|--------|-------|
| **Account Fit** | `account_info.icp_score` (LLM-scored) | 0-10 |
| **Signal Strength** | Signal type weight × 3.3 | 0-10 |
| **Timing** | Recency (≤2d=10, ≤7d=8, ≤14d=5, else 3) | 3-10 |

Composite formula:

```
composite = account_fit × w_fit + signal_strength × w_strength + timing × w_timing
```

Default weights: fit 35%, strength 40%, timing 25%.

Priority tiers:
- **HOT** — composite ≥ 7.5
- **WARM** — composite ≥ 5.0
- **COLD** — below 5.0

### Layer 5: Activation (`engine.py → activate_signal`)

For HOT and WARM signals, Claude Haiku generates actionable recommendations for three personas:

| Persona | Output |
|---------|--------|
| **Sales** | pourquoi, action, LinkedIn message, email (subject+body), follow-up sequence |
| **Direction Salon** | pourquoi, action, 3-phrase insight, positioning angle |
| **Marketing** | pourquoi, action, LinkedIn post draft, content idea, visual brief |

Activations can be triggered from the dashboard on-demand per signal.

### Layer 6: Delivery (`app.py`)

FastAPI web server with two pages:

- **`/`** — Config editor: create/modify salon configs (themes, signal types, scoring weights)
- **`/signals?config=bdaip_2026`** — Signal dashboard with filters (priority, company), score breakdown, and activation generation

#### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/configs` | List all salon configs |
| `GET` | `/api/config/{name}` | Get full config YAML as JSON |
| `POST` | `/api/config` | Save/update a config |
| `GET` | `/api/signals/{name}` | Get scored signals (from cache) |
| `POST` | `/api/activate/{signal_id}` | Generate activations for one signal |
| `POST` | `/api/refresh/{name}` | Clear signal cache |

## Demo Mode

`capture/fake_signals.py` generates hundreds of realistic synthetic signals from a built-in company knowledge base (Databricks, Mistral AI, Snowflake, etc.). Use it without an API key:

```
GET /api/signals/bdaip_2026?source=fake
```

## Signal Schema

```json
{
  "id": "SIG-A1B2C3D4",
  "source": "Google News (Intelligence Artificielle levée de fonds)",
  "company": "Mistral AI",
  "signal_type": "funding",
  "title": "Mistral AI lève 600M€ en Série B",
  "summary": "Mistral AI annonce une levée de 600M€...",
  "url": "https://...",
  "detected_at": "2026-05-15T10:30:00",
  "raw_entities": {},
  "account_info": {
    "name": "Mistral AI",
    "sector": "IA Générative",
    "icp_score": 9
  },
  "signal_meta": {
    "id": "funding",
    "label": "Levée de fonds ≥10M€",
    "weight": 2.5
  },
  "scores": {
    "account_fit": 9,
    "signal_strength": 8.2,
    "timing": 10,
    "composite": 8.93
  },
  "priority": "HOT 🔴",
  "activation": { "sales": {...}, "direction_salon": {...}, "marketing": {...} }
}
```

## Adding a New Salon

1. Create `config/my_salon_2026.yaml` with salon themes, signal types, personas, and scoring weights
2. Run `python fetch_signals.py my_salon_2026`
3. Open `http://localhost:8000/signals?config=my_salon_2026`

Or use the config editor at `http://localhost:8000/`.
