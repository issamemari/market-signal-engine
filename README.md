# Market Signal Engine

Market intelligence tool for trade show organizers. Automatically discovers companies and business signals relevant to a salon by scanning news sources, classifying articles with an LLM, scoring them, and generating actionable recommendations for three personas (Sales, Show Director, Marketing).

Works with any LLM provider: Anthropic, OpenAI, Google Gemini, Mistral, and [many more](https://docs.litellm.ai/docs/providers) via [LiteLLM](https://github.com/BerriAI/litellm).

## How It Works

```
YAML Config (salon themes, signal types, personas)
        │
        ▼
   LLM generates Google News search queries from salon context
        │
        ▼
   RSS Fetch (Google News + L'Usine Digitale, Maddyness, TechCrunch, ...)
        │
        ▼
   LLM classifies each article:
     → extracts company name & sector
     → scores company-salon fit (0-10)
     → determines signal type
        │
        ▼
   Scoring engine (weighted composite: fit × 35% + strength × 40% + timing × 25%)
        │
        ▼
   Web dashboard with filters, scores, and LLM-generated activations per persona
```

No hardcoded target companies — everything is discovered from news based on the salon's themes.

## Running with Docker

### Prerequisites

- Docker and Docker Compose
- An API key for your chosen LLM provider (see [Choosing an LLM Provider](#choosing-an-llm-provider))

### Step 1: Fetch and classify signals

```bash
export MANUS_API_KEY=...
export LLM_MODEL=manus/manus-1.6
docker compose run --rm fetch
```

This will:
1. Ask the LLM to generate ~30 search queries tailored to each salon's themes
2. Fetch articles from Google News RSS + tech press feeds
3. Classify each article with the LLM (10 threads, rate-limited at 40 rpm)
4. Cache results to disk incrementally (safe to Ctrl+C)

### Step 2: Start the dashboard

```bash
docker compose up web
```

Open **http://localhost:8000**. Select a salon to see scored signals, filter by priority or company, and generate per-persona activations.

### Both steps together

```bash
export MANUS_API_KEY=...
export LLM_MODEL=manus/manus-1.6
docker compose run --rm fetch && docker compose up web
```

### Refresh signals

Re-run the fetch command. It will overwrite the cached signals:

```bash
docker compose run --rm fetch
```

Or hit the refresh button in the dashboard (clears the cache, but you still need to re-run fetch to repopulate it).

## Choosing an LLM Provider

The engine uses [LiteLLM](https://docs.litellm.ai/docs/providers) under the hood, so it works with any supported provider. Set the appropriate API key and model via environment variables.

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `LLM_MODEL` | Model for all LLM tasks | `anthropic/claude-haiku-4-5-20251001` |
| `LLM_CLASSIFY_MODEL` | Override model for query generation + article classification | Falls back to `LLM_MODEL` |
| `LLM_ACTIVATE_MODEL` | Override model for activation generation | Falls back to `LLM_MODEL` |

### Provider Examples

**Anthropic (default)**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
python fetch_signals.py
```

**OpenAI**
```bash
export OPENAI_API_KEY=sk-...
export LLM_MODEL=openai/gpt-4o-mini
python fetch_signals.py
```

**Google Gemini**
```bash
export GEMINI_API_KEY=...
export LLM_MODEL=gemini/gemini-2.0-flash
python fetch_signals.py
```

**Mistral**
```bash
export MISTRAL_API_KEY=...
export LLM_MODEL=mistral/mistral-small-latest
python fetch_signals.py
```

**Manus** (async — the engine polls until the task completes)
```bash
export MANUS_API_KEY=...
export LLM_MODEL=manus/manus-1.6
python fetch_signals.py
```

Available Manus models: `manus/manus-1.6` (general), `manus/manus-1.6-lite` (fast), `manus/manus-1.6-max` (advanced).

**Mix providers per task** — use a cheap model for classification and a stronger one for activations:
```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export LLM_CLASSIFY_MODEL=openai/gpt-4o-mini
export LLM_ACTIVATE_MODEL=anthropic/claude-sonnet-4-20250514
```

Model identifiers follow [LiteLLM conventions](https://docs.litellm.ai/docs/providers): `provider/model-name`.

### With Docker

All `LLM_*` and API key variables are forwarded automatically by `docker-compose.yml`:

```bash
export LLM_MODEL=openai/gpt-4o-mini
export OPENAI_API_KEY=sk-...
docker compose run --rm fetch
docker compose up web
```

## Running without Docker

```bash
pip install -r requirements.txt

export MANUS_API_KEY=...
export LLM_MODEL=manus/manus-1.6

# Fetch signals for all salons (or specify one: python fetch_signals.py bdaip_2026)
python fetch_signals.py

# Start the web server
python app.py
# → http://localhost:8000
```

## Project Structure

```
├── config/
│   ├── bdaip_2026.yaml          # Big Data & AI Paris 2026
│   └── mapic_2026.yaml          # MAPIC 2026 (retail/real-estate)
├── capture/
│   ├── rss_signals.py           # RSS fetching + LLM classification
│   └── fake_signals.py          # Synthetic signal generator (demo, no API key needed)
├── llm.py                       # Provider-agnostic LLM wrapper (LiteLLM)
├── engine.py                    # Scoring + LLM activation pipeline
├── fetch_signals.py             # CLI entry point for signal fetching
├── app.py                       # FastAPI web server
├── static/
│   ├── app.js                   # Dashboard frontend
│   └── style.css
├── templates/
│   ├── config.html              # Salon config editor
│   └── signals.html             # Signal dashboard
├── data/
│   └── rss_cache_BDAIP.json     # Cached signals (auto-generated, committed)
├── Dockerfile
├── docker-compose.yml
└── DOCUMENTATION.md             # Detailed technical documentation
```

## Config Format

Each salon is a YAML file in `config/`:

```yaml
salon:
  name: "Big Data & AI Paris 2026"
  short_code: "BDAIP"
  dates: "15-16 septembre 2026"
  location: "Palais des Congrès, Paris"
  themes:
    - "Intelligence Artificielle Générative"
    - "Data Engineering & DataOps"
    - "Cloud & Infrastructure Data"

signal_types:
  - id: "funding"
    label: "Levée de fonds ≥10M€"
    description: "Série A+ ou méga-round"
    weight: 2.5
  - id: "nomination"
    label: "Nomination C-level"
    description: "Nouveau CDO, CTO, VP Data/AI"
    weight: 3.0
  # ...

scoring:
  weights:
    account_fit: 0.35
    signal_strength: 0.40
    timing: 0.25
  thresholds:
    hot: 7.5
    warm: 5.0
```

Themes drive the search queries. Signal types define what to look for and their scoring weight. No target companies needed.

## Scoring

Each signal is scored on three axes (0-10):

| Axis | Source |
|------|--------|
| **Account Fit** | LLM-scored company-salon relevance (`company_salon_fit`) |
| **Signal Strength** | Signal type weight from config |
| **Timing** | Recency: ≤2 days = 10, ≤7d = 8, ≤14d = 5, older = 3 |

Priority: **HOT** (≥7.5) · **WARM** (≥5.0) · **COLD** (<5.0)

## Activations

Click "Générer les activations" on any signal to get tailored recommendations for:

- **Sales** — LinkedIn message, email draft, follow-up sequence
- **Direction Salon** — Strategic insight, positioning angle
- **Marketing** — LinkedIn post draft, content idea, visual brief

## Demo Mode

View synthetic signals without an API key:

```
http://localhost:8000/api/signals/bdaip_2026?source=fake
```

## Adding a New Salon

1. Create `config/my_salon.yaml` (or use the config editor at http://localhost:8000)
2. Run `docker compose run --rm fetch` (or `python fetch_signals.py my_salon`)
3. Open the dashboard and select your salon

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/configs` | List all salon configs |
| `GET` | `/api/config/{name}` | Get full config |
| `POST` | `/api/config` | Create/update a config |
| `GET` | `/api/signals/{name}` | Get scored signals |
| `POST` | `/api/activate/{signal_id}` | Generate activations for a signal |
| `POST` | `/api/refresh/{name}` | Clear signal cache |
