#!/usr/bin/env python3
"""
shift_codes.py — Find all active SHiFT codes for every Borderlands game.
=========================================================================
One file. No browser needed. Just run it.

  python3 shift_codes.py           # All games
  python3 shift_codes.py bl4       # Just Borderlands 4
  python3 shift_codes.py bl3       # Just Borderlands 3
  python3 shift_codes.py --copy    # Copy codes to clipboard

Redeem at: https://shift.gearboxsoftware.com/rewards
"""

# ── Auto-install deps ─────────────────────────────────────────────

import subprocess, sys

def _ensure_deps():
    needed = {"requests": "requests", "bs4": "beautifulsoup4", "lxml": "lxml"}
    missing = []
    for mod, pkg in needed.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"📦 Installing: {', '.join(missing)}...")
        cmd = [sys.executable, "-m", "pip", "install", *missing]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0 and "externally-managed" in r.stderr:
                cmd.append("--break-system-packages")
                subprocess.run(cmd, check=True)
            elif r.returncode != 0:
                print(r.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"❌ Install failed: {e}")
            sys.exit(1)
        print()

_ensure_deps()

# ── Imports ───────────────────────────────────────────────────────

import re, json, argparse
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────

CODE_RE = re.compile(
    r"\b([A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5})\b", re.I
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    )
}

# ── Game sources (MentalMars + Blueberries as primary) ────────────

GAMES = {
    "bl4": {
        "name": "Borderlands 4",
        "sources": [
            "https://mentalmars.com/game-news/borderlands-4-shift-codes/",
            "https://www.blueberries.gg/borderlands/active-shift-codes/",
            "https://thebasedotaku.com/codes/borderlands-4/",
            "https://www.gamesradar.com/games/borderlands/borderlands-4-shift-codes-golden-keys/",
            "https://www.pcgamer.com/games/fps/borderlands-4-shift-codes/",
            "https://www.pcgamesn.com/borderlands-4/shift-codes",
            "https://www.dexerto.com/gaming/borderlands-4-shift-codes-3249396/",
            "https://progameguides.com/borderlands/borderlands-4-shift-codes/",
            "https://www.eurogamer.net/borderlands-4-shift-codes-list",
            "https://game8.co/games/Borderlands-4/archives/548406",
        ],
    },
    "bl3": {
        "name": "Borderlands 3",
        "sources": [
            "https://mentalmars.com/game-news/borderlands-3-shift-codes/",
            "https://www.gamesradar.com/borderlands-3-shift-codes/",
            "https://www.pcgamer.com/borderlands-3-shift-codes/",
            "https://www.pcgamesn.com/borderlands-3/shift-codes",
            "https://progameguides.com/borderlands/borderlands-3-shift-codes/",
            "https://www.esports.net/wiki/guides/borderlands-3-shift-codes/",
        ],
    },
    "wonderlands": {
        "name": "Tiny Tina's Wonderlands",
        "sources": [
            "https://mentalmars.com/game-news/tiny-tinas-wonderlands-shift-codes/",
            "https://progameguides.com/tiny-tinas-wonderlands/tiny-tinas-wonderlands-shift-codes/",
            "https://www.gamesradar.com/tiny-tinas-wonderlands-shift-codes/",
        ],
    },
    "bl2": {
        "name": "Borderlands 2",
        "sources": [
            "https://mentalmars.com/game-news/borderlands-2-golden-keys/",
            "https://progameguides.com/borderlands/borderlands-2-shift-codes/",
        ],
    },
    "bltps": {
        "name": "Borderlands: The Pre-Sequel",
        "sources": [
            "https://mentalmars.com/game-news/borderlands-the-pre-sequel-shift-codes/",
            "https://progameguides.com/borderlands/borderlands-the-pre-sequel-shift-codes/",
        ],
    },
    "bl1": {
        "name": "Borderlands GOTY Enhanced",
        "sources": [
            "https://mentalmars.com/game-news/borderlands-game-of-the-year-shift-codes/",
        ],
    },
}

# ── Expired detection ─────────────────────────────────────────────

EXPIRED_WORDS = ["expired", "no longer", "inactive", "invalid", "removed", "ended"]

def _context_expired(tag):
    ctx = ""
    for anc in [tag.parent, getattr(tag.parent, "parent", None)]:
        if anc:
            ctx += " " + anc.get_text(" ", strip=True).lower()
    for sib in tag.find_all_next(string=True, limit=3):
        ctx += " " + sib.strip().lower()
    for p in tag.parents:
        if p.name in ("s", "del", "strike"):
            return True
        if "line-through" in p.get("style", ""):
            return True
        cls = " ".join(p.get("class", []))
        if "expired" in cls or "inactive" in cls:
            return True
    return any(w in ctx for w in EXPIRED_WORDS)

# ── Scraper ───────────────────────────────────────────────────────

def scrape_game(key):
    cfg = GAMES[key]
    active, expired = set(), set()

    for url in cfg["sources"]:
        domain = url.split("/")[2]
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            for junk in soup(["script", "style", "nav", "footer", "header"]):
                junk.decompose()
            for node in soup.find_all(string=CODE_RE):
                for m in CODE_RE.finditer(str(node)):
                    code = m.group(1).upper()
                    if _context_expired(node):
                        expired.add(code)
                    else:
                        active.add(code)
            print(f"    ✓ {domain}")
        except Exception:
            print(f"    ✗ {domain}")

    active -= expired
    return sorted(active), sorted(expired)

# ── Main ──────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Find all active SHiFT codes for Borderlands games",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""games:
  bl4          Borderlands 4
  bl3          Borderlands 3
  wonderlands  Tiny Tina's Wonderlands
  bl2          Borderlands 2
  bltps        Borderlands: The Pre-Sequel
  bl1          Borderlands GOTY Enhanced

examples:
  python3 shift_codes.py           All games
  python3 shift_codes.py bl4 bl3   Just BL4 and BL3
  python3 shift_codes.py --copy    Copy all codes to clipboard""")
    ap.add_argument("games", nargs="*", choices=[*GAMES.keys(), []], default=[],
                    help="Games to check (default: all)")
    ap.add_argument("--copy", action="store_true",
                    help="Copy all active codes to clipboard")
    ap.add_argument("--json", action="store_true",
                    help="Output as JSON")
    args = ap.parse_args()

    game_keys = args.games if args.games else list(GAMES.keys())

    print(f"\n{'='*55}")
    print(f"  SHiFT Code Finder — {datetime.now().strftime('%B %d, %Y')}")
    print(f"{'='*55}\n")

    all_results = {}
    all_codes = []

    for key in game_keys:
        name = GAMES[key]["name"]
        print(f"🔍 {name}...")
        active, expired = scrape_game(key)
        all_results[key] = {"name": name, "active": active, "expired_count": len(expired)}
        all_codes.extend(active)

        if active:
            print(f"\n  ✅ {len(active)} active codes:")
            for c in active:
                print(f"     {c}")
        else:
            print(f"\n  ⚠ No active codes found")
        print(f"  ({len(expired)} expired codes filtered out)\n")

    # Summary
    total_active = sum(len(v["active"]) for v in all_results.values())
    print(f"{'='*55}")
    print(f"  TOTAL: {total_active} active codes across {len(game_keys)} games")
    print(f"  Redeem at: https://shift.gearboxsoftware.com/rewards")
    print(f"{'='*55}\n")

    # JSON output
    if args.json:
        print(json.dumps(all_results, indent=2))

    # Clipboard
    if args.copy and all_codes:
        try:
            import pyperclip
            pyperclip.copy("\n".join(all_codes))
            print(f"📋 {len(all_codes)} codes copied to clipboard!")
        except ImportError:
            # Fallback: pbcopy on Mac, clip on Windows
            import platform as _p
            text = "\n".join(all_codes)
            try:
                if _p.system() == "Darwin":
                    subprocess.run(["pbcopy"], input=text.encode(), check=True)
                    print(f"📋 {len(all_codes)} codes copied to clipboard!")
                elif _p.system() == "Windows":
                    subprocess.run(["clip"], input=text.encode(), check=True)
                    print(f"📋 {len(all_codes)} codes copied to clipboard!")
                else:
                    print("Install pyperclip for clipboard: pip install pyperclip")
            except Exception:
                print("Couldn't copy — install pyperclip or copy manually above.")


if __name__ == "__main__":
    main()
