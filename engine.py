"""
Market Signal Engine — Core pipeline.

Layers:
  1. Config (YAML per salon)
  2. Capture (fake_signals for demo, swappable)
  3. Normalization + Enrichment
  4. Scoring
  5. Activation (LLM-powered, 3 personas)
  6. Delivery (Streamlit dashboard)
"""

import yaml
import json
import os
from datetime import datetime
from pathlib import Path

import anthropic

from capture.rss_signals import generate_signals


# ─── Layer 1: Config ───────────────────────────────────────────────────────────

def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


# ─── Scoring ──────────────────────────────────────────────────────────────────

def score_signal(signal: dict, config: dict) -> dict:
    """
    Score a signal on 3 axes (0-10 each), combine with weighted sum.
    Formula is transparent and configurable per salon.
    """
    weights = config["scoring"]["weights"]
    signal_type_lookup = {s["id"]: s for s in config.get("signal_types", [])}
    signal_meta = signal_type_lookup.get(signal["signal_type"], {})
    signal["signal_meta"] = signal_meta

    # Account fit: from LLM-scored icp_score
    account_fit = signal.get("account_info", {}).get("icp_score", 5)

    # Signal strength: based on signal type weight
    type_weight = signal_meta.get("weight", 1.0)
    signal_strength = min(10, type_weight * 3.3)  # scale 1-3 weight to ~3-10

    # Timing: recency bonus
    detected = datetime.fromisoformat(signal["detected_at"])
    days_ago = (datetime.now() - detected).days
    if days_ago <= 2:
        timing = 10
    elif days_ago <= 7:
        timing = 8
    elif days_ago <= 14:
        timing = 5
    else:
        timing = 3

    composite = (
        account_fit * weights["account_fit"]
        + signal_strength * weights["signal_strength"]
        + timing * weights["timing"]
    )

    signal["scores"] = {
        "account_fit": round(account_fit, 1),
        "signal_strength": round(signal_strength, 1),
        "timing": round(timing, 1),
        "composite": round(composite, 2),
    }

    thresholds = config["scoring"]["thresholds"]
    if composite >= thresholds["hot"]:
        signal["priority"] = "HOT 🔴"
    elif composite >= thresholds["warm"]:
        signal["priority"] = "WARM 🟠"
    else:
        signal["priority"] = "COLD 🔵"

    return signal


# ─── Layer 5: Activation (LLM) ────────────────────────────────────────────────

ACTIVATION_SYSTEM_PROMPT = """Tu es un expert en veille stratégique pour les salons professionnels RX France.

Pour chaque signal marché détecté, tu dois produire des recommandations d'activation pour TROIS personas distinctes. Chaque activation DOIT répondre aux 4 questions clés :
1. POURQUOI ce signal est important pour cette persona
2. QUELLE ACTION concrète recommander
3. QUEL MESSAGE envoyer (prêt à copier-coller)
4. QUEL CONTENU créer (brief précis)

Réponds TOUJOURS en JSON valide avec la structure exacte demandée. Sois concret, spécifique, actionnable. Pas de généralités."""


def build_activation_prompt(signal: dict, config: dict) -> str:
    salon = config["salon"]
    personas = config["personas"]

    return f"""Salon : {salon['name']} ({salon['short_code']}) — {salon['dates']}, {salon['location']}
Thématiques : {', '.join(salon['themes'])}

SIGNAL DÉTECTÉ :
- Entreprise : {signal['company']}
- Type : {signal['signal_type']} ({signal.get('signal_meta', {}).get('label', '')})
- Titre : {signal['title']}
- Résumé : {signal['summary']}
- Date : {signal['detected_at'][:10]}
- Score composite : {signal['scores']['composite']}/10 (Fit: {signal['scores']['account_fit']}, Force: {signal['scores']['signal_strength']}, Timing: {signal['scores']['timing']})
- Priorité : {signal['priority']}
- Entités : {json.dumps(signal.get('raw_entities', {}), ensure_ascii=False)}

CONTEXTE COMPTE :
{json.dumps(signal.get('account_info', {}), ensure_ascii=False, indent=2)}

Génère les activations pour les 3 personas ci-dessous. Réponds en JSON STRICT avec cette structure :

{{
  "sales": {{
    "pourquoi": "...",
    "action": "...",
    "message_linkedin": "...",
    "email_subject": "...",
    "email_body": "...",
    "follow_up_sequence": ["J+3: ...", "J+7: ..."]
  }},
  "direction_salon": {{
    "pourquoi": "...",
    "action": "...",
    "insight_3_phrases": "...",
    "angle_positionnement": "..."
  }},
  "marketing": {{
    "pourquoi": "...",
    "action": "...",
    "post_linkedin_draft": "...",
    "content_idea": "...",
    "visual_brief": "..."
  }}
}}

PERSONAS :
- Sales ({personas['sales']['role']}): {personas['sales']['goal']}. Ton: {personas['sales']['tone']}
- Direction Salon ({personas['direction_salon']['role']}): {personas['direction_salon']['goal']}. Ton: {personas['direction_salon']['tone']}
- Marketing ({personas['marketing']['role']}): {personas['marketing']['goal']}. Ton: {personas['marketing']['tone']}

Sois SPÉCIFIQUE : mentionne le nom de l'entreprise, les personnes, les produits. Pas de placeholders."""


def activate_signal(signal: dict, config: dict, client: anthropic.Anthropic) -> dict:
    """Call Claude to generate activation outputs for a single signal."""
    prompt = build_activation_prompt(signal, config)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4000,
        system=ACTIVATION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text

    # Extract JSON — try multiple strategies
    activation = None
    # Strategy 1: direct parse
    try:
        activation = json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: find ```json ... ``` block
    if activation is None:
        import re
        m = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if m:
            try:
                activation = json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

    # Strategy 3: find outermost { ... }
    if activation is None:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                activation = json.loads(text[start:end])
            except json.JSONDecodeError:
                # Try fixing common issues: trailing commas
                candidate = text[start:end]
                candidate = re.sub(r',\s*}', '}', candidate)
                candidate = re.sub(r',\s*]', ']', candidate)
                try:
                    activation = json.loads(candidate)
                except json.JSONDecodeError:
                    pass

    if activation is None:
        activation = {"error": "Could not parse activation", "raw": text[:500]}

    signal["activation"] = activation
    return signal


# ─── Full Pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(config_path: str, activate: bool = True) -> list[dict]:
    """Run the full pipeline: capture → normalize → score → activate."""
    config = load_config(config_path)
    print(f"▶ Salon: {config['salon']['name']}")

    # Capture
    raw = generate_signals(config)
    print(f"  📡 Captured {len(raw)} raw signals")

    # Score
    scored = [score_signal(s, config) for s in raw]
    scored.sort(key=lambda s: s["scores"]["composite"], reverse=True)
    hot = sum(1 for s in scored if "HOT" in s.get("priority", ""))
    warm = sum(1 for s in scored if "WARM" in s.get("priority", ""))
    print(f"  📊 Scored: {hot} HOT, {warm} WARM, {len(scored)-hot-warm} COLD")

    # Layer 5: Activate (optional, requires API key)
    if activate and os.environ.get("ANTHROPIC_API_KEY"):
        client = anthropic.Anthropic()
        for i, sig in enumerate(scored):
            if "HOT" in sig.get("priority", "") or "WARM" in sig.get("priority", ""):
                print(f"  🤖 Activating [{i+1}/{len(scored)}] {sig['company']} — {sig['signal_meta'].get('label', sig['signal_type'])}")
                activate_signal(sig, config, client)
        print(f"  ✅ Activation complete")
    elif activate:
        print(f"  ⚠️  Set ANTHROPIC_API_KEY to enable LLM activation")

    return scored


if __name__ == "__main__":
    import sys
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/bdaip_2026.yaml"
    results = run_pipeline(config_path)
    # Save results
    out_path = "data/last_run.json"
    os.makedirs("data", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n💾 Results saved to {out_path}")
