#!/usr/bin/env python
"""
CLI tool to fetch RSS feeds and classify articles into signals.
Run this BEFORE starting the web server.

Usage:
    python fetch_signals.py                  # all configs
    python fetch_signals.py bdaip_2026       # specific config
"""

import sys
from pathlib import Path

from engine import load_config
from capture.rss_signals import fetch_and_classify

CONFIG_DIR = Path("config")


def main():
    if len(sys.argv) > 1:
        names = sys.argv[1:]
    else:
        names = sorted(f.stem for f in CONFIG_DIR.glob("*.yaml"))

    if not names:
        print("No configs found in config/")
        sys.exit(1)

    for name in names:
        path = CONFIG_DIR / f"{name}.yaml"
        if not path.exists():
            print(f"❌ Config not found: {path}")
            continue

        config = load_config(str(path))
        salon = config["salon"]["name"]
        print(f"\n{'='*60}")
        print(f"▶ {salon} ({name})")
        print(f"{'='*60}")

        signals = fetch_and_classify(config)
        print(f"  💾 Cached {len(signals)} signals for {name}")

    print(f"\n✅ Done. Start the web server with: python app.py")


if __name__ == "__main__":
    main()
