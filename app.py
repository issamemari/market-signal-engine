"""
Market Signal Engine — FastAPI Backend (Layer 6: Delivery)

Run with: python app.py
"""

import json
import os
import uuid
from pathlib import Path

import anthropic
import yaml
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from engine import load_config, score_signal, activate_signal
from capture.rss_signals import generate_signals as rss_generate_signals
from capture.fake_signals import generate_signals as fake_generate_signals

app = FastAPI(title="Market Signal Engine")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# In-memory store for signals and activations per session
_signal_cache: dict[str, list[dict]] = {}
_activation_cache: dict[str, dict] = {}


def _config_dir() -> Path:
    return Path("config")


def _list_configs() -> list[str]:
    return sorted(f.stem for f in _config_dir().glob("*.yaml"))


def _get_signals(config_name: str, source: str = "rss") -> list[dict]:
    cache_key = f"{config_name}:{source}"
    if cache_key in _signal_cache:
        return _signal_cache[cache_key]
    config_path = str(_config_dir() / f"{config_name}.yaml")
    config = load_config(config_path)
    gen = fake_generate_signals if source == "fake" else rss_generate_signals
    raw = gen(config)
    scored = [score_signal(s, config) for s in raw]
    scored.sort(key=lambda s: s["scores"]["composite"], reverse=True)
    _signal_cache[cache_key] = scored
    return scored


# ─── Pages ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def config_page(request: Request):
    return templates.TemplateResponse("config.html", {"request": request})


@app.get("/signals", response_class=HTMLResponse)
async def signals_page(request: Request):
    return templates.TemplateResponse("signals.html", {"request": request})


# ─── API ──────────────────────────────────────────────────────────────────────

@app.get("/api/configs")
async def list_configs():
    configs = []
    for name in _list_configs():
        config = load_config(str(_config_dir() / f"{name}.yaml"))
        configs.append({
            "name": name,
            "salon": config["salon"],
            "signal_types_count": len(config.get("signal_types", [])),
        })
    return configs


@app.get("/api/config/{name}")
async def get_config(name: str):
    path = _config_dir() / f"{name}.yaml"
    if not path.exists():
        return JSONResponse({"error": "Config not found"}, status_code=404)
    config = load_config(str(path))
    return config


@app.post("/api/config")
async def save_config(request: Request):
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        return JSONResponse({"error": "Name is required"}, status_code=400)

    # Build YAML structure
    config = {
        "salon": data["salon"],
        "personas": data.get("personas", {
            "sales": {"role": "Commercial", "goal": "Vendre des espaces", "tone": "Direct, business", "channels": ["LinkedIn DM", "Email"]},
            "direction_salon": {"role": "Directeur du salon", "goal": "Positionner le salon", "tone": "Stratégique", "channels": ["Brief interne"]},
            "marketing": {"role": "Marketing", "goal": "Créer du contenu", "tone": "Inspirant", "channels": ["LinkedIn post", "Newsletter"]},
        }),
        "signal_types": data.get("signal_types", []),
        "scoring": data.get("scoring", {
            "weights": {"account_fit": 0.35, "signal_strength": 0.40, "timing": 0.25},
            "thresholds": {"hot": 7.5, "warm": 5.0, "cold": 0.0},
        }),
    }

    path = _config_dir() / f"{name}.yaml"
    with open(path, "w") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    # Clear cached signals for this config
    _signal_cache.pop(name, None)

    return {"status": "ok", "name": name}


@app.get("/api/signals/{config_name}")
async def get_signals(config_name: str, source: str = "rss"):
    path = _config_dir() / f"{config_name}.yaml"
    if not path.exists():
        return JSONResponse({"error": "Config not found"}, status_code=404)
    signals = _get_signals(config_name, source=source)
    # Merge any cached activations
    for sig in signals:
        if sig["id"] in _activation_cache:
            sig["activation"] = _activation_cache[sig["id"]]
    return signals


@app.post("/api/activate/{signal_id}")
async def activate(signal_id: str, request: Request):
    data = await request.json()
    config_name = data.get("config_name")
    if not config_name:
        return JSONResponse({"error": "config_name required"}, status_code=400)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return JSONResponse({"error": "ANTHROPIC_API_KEY not set"}, status_code=500)

    signals = _get_signals(config_name)
    signal = next((s for s in signals if s["id"] == signal_id), None)
    if not signal:
        return JSONResponse({"error": "Signal not found"}, status_code=404)

    config = load_config(str(_config_dir() / f"{config_name}.yaml"))
    client = anthropic.Anthropic()
    activate_signal(signal, config, client)

    _activation_cache[signal_id] = signal.get("activation", {})
    return signal.get("activation", {})


@app.post("/api/refresh/{config_name}")
async def refresh_signals(config_name: str):
    # Clear both rss and fake cache entries
    _signal_cache.pop(f"{config_name}:rss", None)
    _signal_cache.pop(f"{config_name}:fake", None)
    # Clear RSS file cache
    from capture.rss_signals import clear_cache
    config = load_config(str(_config_dir() / f"{config_name}.yaml"))
    short_code = config.get("salon", {}).get("short_code", "default")
    clear_cache(short_code)
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
