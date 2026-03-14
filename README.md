# SHiFT Code Finder

A lightweight Python script that scrapes 40+ sources to find every active SHiFT code across all Borderlands and Wonderlands games — and optionally auto-redeems them on your Gearbox account.

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

### Interactive Mode

Run without arguments to get a full interactive menu:

```bash
python3 shift_codes.py
```

The menu lets you:

1. Link your SHiFT account and select a platform
2. Find codes for all games
3. Find codes for a specific game
4. Find and auto-redeem codes
5. Copy all active codes to clipboard
6. View your redemption history
7. Reset history
8. Clear the page cache
9. Log out

It also shows your current account status, platform, and when you last ran a scan.

### Non-Interactive / CLI Mode

Any flag or game argument skips the menu and runs directly:

```bash
# Scrape all games immediately (skip menu)
python3 shift_codes.py --auto

# Specific games
python3 shift_codes.py bl4
python3 shift_codes.py bl4 bl3 wonderlands

# Copy all active codes to clipboard
python3 shift_codes.py --copy

# Output as JSON (clean stdout, progress on stderr)
python3 shift_codes.py --json
python3 shift_codes.py --json > codes.json    # pipe-friendly

# Cache results for 10 minutes (avoids re-scraping on repeated runs)
python3 shift_codes.py --cache

# Auto-redeem codes on your SHiFT account
python3 shift_codes.py --redeem
python3 shift_codes.py --redeem --platform xbox
python3 shift_codes.py bl4 --redeem --platform playstation

# Clear your redeemed code history
python3 shift_codes.py --reset-history
```

Flags can be combined freely — `--json --copy --cache` all work together.

## Auto-Redeem

The `--redeem` flag (or menu option 4) logs into your SHiFT account and automatically redeems all found codes.

### Authentication

Login is attempted in this order:

1. **Saved session** — reuses cookies from a previous login (`~/.cache/shift-codes/session.json`). Sessions are verified before use and re-authenticated if expired.
2. **Environment variables** — set `SHIFT_EMAIL` and `SHIFT_PASSWORD`:
   ```bash
   export SHIFT_EMAIL="you@example.com"
   export SHIFT_PASSWORD="yourpassword"
   python3 shift_codes.py --redeem
   ```
3. **Browser cookies** — automatically extracts session cookies from Chrome or Edge on macOS (decrypts the cookie database using the macOS Keychain).
4. **Browser-based login** — opens the SHiFT website so you can log in, then captures the session cookies.

### Platforms

Use `--platform` to choose where codes are redeemed. Your choice is saved between sessions.

| Flag | Platform |
|------|----------|
| `steam` | Steam (default) |
| `epic` | Epic Games Store |
| `xbox` | Xbox |
| `playstation` | PlayStation |
| `nintendo` | Nintendo Switch |

### How It Works

1. Logs in to `shift.gearboxsoftware.com` using session cookies + CSRF tokens.
2. Submits each code to the entitlement API.
3. Selects the correct platform form and confirms redemption.
4. Reports status for each code: redeemed, already redeemed, expired, or invalid.
5. Tracks redemption history per code, per platform, with timestamps.
6. Handles rate limits automatically with exponential backoff (30s, 60s, 120s) and jittered delays between codes.

## How Code Scraping Works

1. Scrapes 40+ sources per game concurrently (12-worker thread pool) across 4 tiers of reliability.
2. Extracts 25-character SHiFT codes (`XXXXX-XXXXX-XXXXX-XXXXX-XXXXX`) using pattern matching.
3. Filters out expired codes by inspecting:
   - Surrounding text and parent elements for expiry keywords
   - CSS strikethrough styling and class names
   - Data attributes
4. Detects and filters "dump sites" (sources returning 40+ codes that include historical/expired codes).
5. Deduplicates across all sources and sorts by confidence — codes found on more sources rank higher.

### Source Tiers

- **Tier 1 — Aggregators:** Orcicorn SHiFT Archive, ShiftCodesTK, xSmashx88x GitHub Tracker. Automated, structured data — most reliable.
- **Tier 2 — Community Trackers:** MentalMars, Blueberries.gg, TheBasedOtaku, Mobalytics, LockerCodes.io, Kyber's Corner. Manually curated, updated daily.
- **Tier 3 — Major Outlets:** GamesRadar, PCGamer, PCGamesN, Dexerto, Eurogamer, GameSpot, Game Rant, NME. Editorial coverage with code tracking.
- **Tier 4 — Supplementary:** ProGameGuides, Game8, Hold To Reset, TheGamePost, GamingDeputy, TechShout, Esports.net. Extra coverage to catch anything the others miss.

BL4 alone pulls from 22 sources. Codes found on any source but marked expired on any other are automatically filtered out.

## Redeeming Codes Manually

- **Website:** Go to [shift.gearboxsoftware.com/rewards](https://shift.gearboxsoftware.com/rewards), log in, paste a code, and click Check.
- **In-game:** Open the SHiFT menu from the main menu or pause screen, go to the Rewards tab, and enter the code.

Your SHiFT account must be linked to the platform you play on. Codes are universal across all platforms.

## Example Output

```
=======================================================
  SHiFT Code Finder — March 10, 2026
=======================================================

  Borderlands 4...
    + mentalmars.com
    + www.blueberries.gg
    + www.gamesradar.com
    ...

  14 active codes:
     39FJB-CT5S3-5FTTW-BBB3J-F3HKZ
     3HX3J-RJWSJ-CFBBC-3BJ3B-RWZ36
     3SRB3-95CC3-K6TB5-BTJTB-66ZHW
     ...
  (47 expired codes filtered out)

  Borderlands 3...
  22 active codes:
     ...

=======================================================
  TOTAL: 36 active codes across 6 games
  Redeem at: https://shift.gearboxsoftware.com/rewards
=======================================================
```

## Data Storage

All data is stored in `~/.cache/shift-codes/`:

| File | Purpose |
|------|---------|
| `session.json` | Saved SHiFT login cookies (auto-reused on next run) |
| `settings.json` | Platform preference, account status, last-checked date |
| `redeemed_history.json` | Per-code, per-platform redemption history with timestamps |
| `cache/` | Temporary page cache (10-minute TTL) |

## Requirements

- Python 3.9+
- Internet connection

Dependencies (`requests`, `beautifulsoup4`, `lxml`) install automatically on first run. Optional: `pyperclip` for clipboard support, `cryptography` for browser cookie extraction on macOS. No virtual environment, Selenium, or browser needed.

## Platform Support

Runs on macOS, Windows, and Linux. No platform-specific setup required — just `python3 shift_codes.py`.

## License

Personal use. Not affiliated with Gearbox Software or 2K Games. SHiFT is a trademark of Gearbox Software, LLC.
