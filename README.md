# SHiFT Code Finder

A lightweight Python script that scrapes 20+ sources to find every active SHiFT code across all Borderlands and Wonderlands games. 

## Supported Games

| Flag | Game |
|------|------|
| `bl4` | Borderlands 4 |
| `bl3` | Borderlands 3 |
| `wonderlands` | Tiny Tina's Wonderlands |
| `bl2` | Borderlands 2 |
| `bltps` | Borderlands: The Pre-Sequel |
| `bl1` | Borderlands GOTY Enhanced |

## Quick Start

```bash
python3 shift_codes.py
```

Dependencies install automatically on first run. Requires Python 3.9+ (ships with macOS; [download for Windows](https://www.python.org/downloads/)).

## Usage

```bash
# All games at once
python3 shift_codes.py

# Specific games
python3 shift_codes.py bl4
python3 shift_codes.py bl4 bl3 wonderlands

# Copy all active codes to clipboard
python3 shift_codes.py --copy

# Output as JSON (for piping or scripting)
python3 shift_codes.py --json
```

## How It Works

1. Scrapes code lists from multiple sources per game (MentalMars, Blueberries.gg, GamesRadar, PCGamer, Dexerto, PCGamesN, and more).
2. Extracts 25-character SHiFT codes using pattern matching.
3. Filters out expired codes by checking surrounding text, CSS strikethrough styling, and class names.
4. Deduplicates and displays the results.

## Redeeming Codes

Codes can be redeemed two ways:

- **Website:** Go to [shift.gearboxsoftware.com/rewards](https://shift.gearboxsoftware.com/rewards), log in, paste a code, and click Check.
- **In-game:** Open the SHiFT menu from the main menu or pause screen, go to the Rewards tab, and enter the code.

Your SHiFT account must be linked to the platform you play on (PlayStation, Xbox, Steam, Epic, etc). Codes are universal across all platforms.

## Sources

Each game pulls from a curated set of sources, prioritized by reliability:

- **Tier 1 (Archives):** MentalMars — the gold standard for categorized, maintained code lists with explicit expired/active/permanent labels. Blueberries.gg — clean scannable tables with confirmed expiry dates. TheBasedOtaku — community-maintained tracker updated daily.
- **Tier 2 (Major Outlets):** GamesRadar, PCGamer, PCGamesN, Dexerto, Eurogamer — major gaming sites that track codes alongside their coverage.
- **Tier 3 (Additional):** ProGameGuides, PrimaGames, Esports.net, Game8 — supplementary sources to catch anything the others miss.

Codes found on any source but marked expired on any other source are filtered out.

## Example Output

```
=======================================================
  SHiFT Code Finder — March 10, 2026
=======================================================

🔍 Borderlands 4...
    ✓ mentalmars.com
    ✓ www.blueberries.gg
    ✓ www.gamesradar.com
    ...

  ✅ 14 active codes:
     39FJB-CT5S3-5FTTW-BBB3J-F3HKZ
     3HX3J-RJWSJ-CFBBC-3BJ3B-RWZ36
     3SRB3-95CC3-K6TB5-BTJTB-66ZHW
     ...
  (47 expired codes filtered out)

🔍 Borderlands 3...
  ✅ 22 active codes:
     ...

=======================================================
  TOTAL: 36 active codes across 6 games
  Redeem at: https://shift.gearboxsoftware.com/rewards
=======================================================
```

## Requirements

- Python 3.9+
- Internet connection

Dependencies (`requests`, `beautifulsoup4`, `lxml`) install automatically on first run. No virtual environment, Selenium, or browser needed.

## Platform Support

Runs on macOS, Windows, and Linux. No platform-specific setup required — just `python3 shift_codes.py`.

## License

Personal use. Not affiliated with Gearbox Software or 2K Games. SHiFT is a trademark of Gearbox Software, LLC.
