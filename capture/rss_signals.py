"""
Market Signal Engine — RSS-based Capture Module (Layer 2)

Fetches real articles from RSS feeds (Google News by salon theme, tech press),
classifies them with an LLM, and outputs signals matching the existing schema.
"""

import hashlib
import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import feedparser

from llm import chat

# ─── Feed Sources ─────────────────────────────────────────────────────────────

TECH_FEEDS = {
    "L'Usine Digitale": "https://www.usine-digitale.fr/rss",
    "Le Monde Informatique": "https://www.lemondeinformatique.fr/flux-rss/thematique/toutes-les-actualites/rss.xml",
    "Maddyness": "https://www.maddyness.com/feed/",
    "TechCrunch": "https://techcrunch.com/feed/",
}

JOB_FEEDS = {}

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=fr&gl=FR&ceid=FR:fr"

CACHE_TTL_SECONDS = None  # no expiry — cache lives forever until manually refreshed
MAX_REQUESTS_PER_MINUTE = 40  # stay under 50 rpm limit


class RateLimiter:
    """Simple token-bucket rate limiter (thread-safe)."""
    def __init__(self, rpm: int):
        self._interval = 60.0 / rpm
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self):
        with self._lock:
            now = time.monotonic()
            wait_time = self._last + self._interval - now
            if wait_time > 0:
                time.sleep(wait_time)
            self._last = time.monotonic()

# ─── LLM-powered query generation ────────────────────────────────────────────

QUERY_GEN_PROMPT = """Tu es un expert en veille stratégique pour les salons professionnels.
On te donne les informations d'un salon et les types de signaux à détecter.
Tu dois générer une liste de requêtes de recherche Google News optimisées pour découvrir des articles pertinents.

Règles :
- Génère exactement {max_queries} requêtes, pas plus, pas moins
- Les requêtes doivent être en français (sauf si le salon est anglophone)
- Chaque requête doit être courte (3-6 mots) et efficace pour Google News
- Couvre un mix de thématiques du salon × types de signaux
- Varie les formulations pour maximiser la couverture
- Ne mets PAS de guillemets dans les requêtes

Réponds UNIQUEMENT avec un JSON array de strings, sans texte avant ou après.
Exemple : ["requête 1", "requête 2", "requête 3"]"""


def generate_queries_with_llm(config: dict, max_queries: int = 30) -> list[str]:
    """Use LLM to generate search queries based on salon config."""
    salon = config["salon"]
    signal_types = config.get("signal_types", [])
    types_desc = "\n".join(f"- {st['id']}: {st['label']} — {st['description']}" for st in signal_types)

    user_prompt = f"""SALON :
Nom : {salon['name']}
Dates : {salon['dates']}
Lieu : {salon['location']}
Thématiques : {', '.join(salon['themes'])}

TYPES DE SIGNAUX À DÉTECTER :
{types_desc}

Génère {max_queries} requêtes Google News pour découvrir des articles pertinents sur des entreprises liées à ce salon."""

    text = chat(
        system=QUERY_GEN_PROMPT.format(max_queries=max_queries),
        user=user_prompt,
        task="classify",
        max_tokens=1000,
    )

    try:
        queries = json.loads(text)
        if isinstance(queries, list):
            return [q for q in queries if isinstance(q, str)][:max_queries]
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                queries = json.loads(text[start:end])
                return [q for q in queries if isinstance(q, str)][:max_queries]
            except json.JSONDecodeError:
                pass

    print("  ⚠️  Failed to parse LLM query response, using fallback")
    # Fallback: simple theme-based queries
    return [f"{theme}" for theme in config.get("salon", {}).get("themes", [])]


# ─── Cache helpers ────────────────────────────────────────────────────────────

def _cache_path(short_code: str) -> Path:
    return Path("data") / f"rss_cache_{short_code}.json"


def _load_cache(short_code: str) -> dict | None:
    path = _cache_path(short_code)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, KeyError):
        return None


def _save_cache(short_code: str, signals: list[dict]):
    Path("data").mkdir(exist_ok=True)
    data = {"timestamp": time.time(), "signals": signals}
    _cache_path(short_code).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def clear_cache(short_code: str):
    path = _cache_path(short_code)
    if path.exists():
        path.unlink()


# ─── RSS Fetching ─────────────────────────────────────────────────────────────

def _parse_feed(url: str, source_name: str) -> list[dict]:
    """Parse a single RSS feed, return list of article dicts."""
    try:
        feed = feedparser.parse(url)
    except Exception:
        return []

    articles = []
    for entry in feed.entries[:20]:  # cap per feed
        published = ""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime(*entry.published_parsed[:6]).isoformat()
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            published = datetime(*entry.updated_parsed[:6]).isoformat()
        else:
            published = datetime.now().isoformat()

        articles.append({
            "title": entry.get("title", ""),
            "summary": entry.get("summary", entry.get("description", "")),
            "url": entry.get("link", ""),
            "source": source_name,
            "published": published,
        })
    return articles


def fetch_all_feeds(config: dict, queries: list[str] | None = None) -> list[dict]:
    """Fetch Google News by LLM-generated queries + all tech feeds. Returns raw articles."""
    articles = []

    if queries is None:
        queries = generate_queries_with_llm(config)

    for query in queries:
        url = GOOGLE_NEWS_RSS.format(query=query.replace(" ", "+"))
        articles.extend(_parse_feed(url, f"Google News ({query})"))

    # Tech feeds
    for name, url in TECH_FEEDS.items():
        articles.extend(_parse_feed(url, name))

    # Job feeds (best-effort)
    for name, url in JOB_FEEDS.items():
        articles.extend(_parse_feed(url, name))

    return articles


# ─── LLM Classification ──────────────────────────────────────────────────────

CLASSIFICATION_SYSTEM_PROMPT = """Tu es un analyste de veille stratégique pour les salons professionnels.
On te donne un article de presse et un contexte (thématiques du salon, types de signaux).
Tu dois déterminer si l'article est pertinent et, si oui, extraire un signal structuré.
Tu dois aussi identifier l'entreprise mentionnée et évaluer son adéquation avec le salon.

Réponds TOUJOURS en JSON valide. Pas de texte avant ou après le JSON."""


def _build_classification_prompt(article: dict, config: dict) -> str:
    salon = config["salon"]
    signal_types = config.get("signal_types", [])

    types_desc = "\n".join(
        f"- {st['id']}: {st['label']} — {st['description']}"
        for st in signal_types
    )

    return f"""ARTICLE :
Titre : {article['title']}
Description : {article['summary'][:500]}
Source : {article['source']}
Date : {article['published'][:10] if article['published'] else 'inconnue'}

CONTEXTE :
Salon : {salon['name']} — Thématiques : {', '.join(salon['themes'])}
Types de signaux :
{types_desc}

INSTRUCTION :
Analyse cet article. Si il concerne une entreprise identifiable ET correspond à un type de signal, retourne :
{{
  "relevant": true,
  "company": "<nom de l'entreprise principale mentionnée>",
  "company_sector": "<secteur d'activité de l'entreprise>",
  "company_salon_fit": <score de 0 à 10 indiquant l'adéquation de l'entreprise avec les thématiques du salon>,
  "signal_type": "<id du type de signal>",
  "title": "<titre propre en français pour affichage>",
  "summary": "<résumé 2-3 phrases en français>",
  "raw_entities": {{}},
  "llm_strength_score": <1-10>
}}

Le champ company_salon_fit doit refléter à quel point l'entreprise et son secteur sont pertinents pour les thématiques du salon (0 = aucun rapport, 10 = parfaitement aligné).

Si l'article n'est PAS pertinent (ne concerne aucune entreprise ou aucun type de signal), retourne :
{{"relevant": false}}"""


def classify_article(article: dict, config: dict, limiter: RateLimiter | None = None) -> dict | None:
    """Classify a single article using LLM. Returns a signal dict or None."""
    prompt = _build_classification_prompt(article, config)

    try:
        if limiter:
            limiter.wait()
        text = chat(
            system=CLASSIFICATION_SYSTEM_PROMPT,
            user=prompt,
            task="classify",
            max_tokens=500,
        )

        # Parse JSON from response
        result = None
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            # Try extracting JSON from text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    result = json.loads(text[start:end])
                except json.JSONDecodeError:
                    return None

        if result is None or not result.get("relevant"):
            return None

        # Build signal matching existing schema
        signal_id = f"SIG-{uuid.uuid4().hex[:8].upper()}"
        return {
            "id": signal_id,
            "source": article["source"],
            "company": result["company"],
            "signal_type": result["signal_type"],
            "title": result.get("title", article["title"]),
            "summary": result.get("summary", article["summary"][:200]),
            "url": article["url"],
            "detected_at": article.get("published") or datetime.now().isoformat(),
            "raw_entities": result.get("raw_entities", {}),
            "account_info": {
                "name": result["company"],
                "sector": result.get("company_sector", ""),
                "icp_score": result.get("company_salon_fit", 5),
            },
            "scores": {},
            "priority": "",
            "activation": {},
        }

    except Exception as e:
        print(f"  ⚠️  Classification error: {e}")
        return None


# ─── Main entry point ────────────────────────────────────────────────────────

def generate_signals(config: dict) -> list[dict]:
    """
    Same signature as fake_signals.generate_signals.
    Returns cached RSS signals only — never fetches or classifies.
    Run `python fetch_signals.py` first to populate the cache.
    """
    short_code = config.get("salon", {}).get("short_code", "default")

    cached = _load_cache(short_code)
    if cached:
        return cached["signals"]

    print(f"  ⚠️  No RSS cache for {short_code}. Run: python fetch_signals.py {short_code}")
    return []


def fetch_and_classify(config: dict) -> list[dict]:
    """
    Fetch RSS feeds and classify articles with Claude Haiku.
    Saves results to file cache. Intended to be run from CLI, not the web server.
    """
    short_code = config.get("salon", {}).get("short_code", "default")

    print(f"  🧠 Generating search queries with LLM...")
    queries = generate_queries_with_llm(config)
    print(f"  🔎 Generated {len(queries)} queries:")
    for q in queries:
        print(f"      • {q}")

    print(f"  📡 Fetching RSS feeds...")
    articles = fetch_all_feeds(config, queries=queries)
    print(f"  📰 Fetched {len(articles)} articles")

    signals = []

    # Deduplicate articles by title hash before classifying
    seen_titles = set()
    unique_articles = []
    for a in articles:
        h = hashlib.md5(a["title"].encode()).hexdigest()
        if h not in seen_titles:
            seen_titles.add(h)
            unique_articles.append(a)

    limiter = RateLimiter(MAX_REQUESTS_PER_MINUTE)
    max_workers = 1
    from llm import get_model
    model_name = get_model("classify")
    print(f"  🔍 Classifying {len(unique_articles)} unique articles with {model_name} ({max_workers} threads, {MAX_REQUESTS_PER_MINUTE} rpm)...")

    def _classify(idx_article):
        i, article = idx_article
        return i, classify_article(article, config, limiter)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_classify, (i, a)): i for i, a in enumerate(unique_articles)}
        for future in as_completed(futures):
            i, sig = future.result()
            if sig:
                signals.append(sig)
                _save_cache(short_code, signals)
                print(f"    ✅ [{i+1}/{len(unique_articles)}] {sig['company']} — {sig['signal_type']} ({len(signals)} cached)")

    print(f"  📊 {len(signals)} relevant signals found")
    return signals
