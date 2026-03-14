#!/usr/bin/env python3
"""
shift_codes.py — Find all active SHiFT codes for every Borderlands game.
=========================================================================
One file. No browser needed. Just run it.

  python3 shift_codes.py           # Interactive menu
  python3 shift_codes.py --auto    # Skip menu, scrape all games
  python3 shift_codes.py bl4       # Skip menu, just Borderlands 4
  python3 shift_codes.py --redeem  # Skip menu, scrape + redeem

Redeem at: https://shift.gearboxsoftware.com/rewards
"""

# ── Auto-install deps ─────────────────────────────────────────────

import subprocess, sys, os

def _ensure_deps():
    needed = {"requests": "requests", "bs4": "beautifulsoup4", "lxml": "lxml"}
    missing = []
    for mod, pkg in needed.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        _log(f"Installing: {', '.join(missing)}...")
        # Prefer venv/user install over --break-system-packages
        cmd = [sys.executable, "-m", "pip", "install", "--user", *missing]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                # Fallback: try without --user
                cmd = [sys.executable, "-m", "pip", "install", *missing]
                r = subprocess.run(cmd, capture_output=True, text=True)
                if r.returncode != 0:
                    _log(f"Auto-install failed. Please install manually:")
                    _log(f"  pip install {' '.join(missing)}")
                    _log(f"  (or create a venv: python3 -m venv .venv && source .venv/bin/activate)")
                    sys.exit(1)
        except Exception as e:
            _log(f"Install failed: {e}")
            sys.exit(1)
        _log("")

# ── Logging helper (stderr for progress, stdout for data) ────────

def _log(msg=""):
    """Print progress/status to stderr so --json output stays clean on stdout."""
    print(msg, file=sys.stderr)

_ensure_deps()

# ── Imports ───────────────────────────────────────────────────────

import re, json, argparse, time, hashlib, getpass, webbrowser, random
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

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

CACHE_DIR = Path.home() / ".cache" / "shift-codes"
CACHE_TTL = 600  # 10 minutes

MAX_WORKERS = 12
MAX_RETRIES = 2
RETRY_BACKOFF = 1.5  # seconds, doubled each retry

SHIFT_BASE = "https://shift.gearboxsoftware.com"

# ── Game sources ──────────────────────────────────────────────────
#
# Tier 1 — Aggregators & archives (most reliable, structured data)
# Tier 2 — Dedicated community trackers
# Tier 3 — Major gaming outlets (editorial, updated frequently)
# Tier 4 — Supplementary (catch stragglers)

GAMES = {
    "bl4": {
        "name": "Borderlands 4",
        "sources": [
            # Tier 2 — Community trackers
            "https://mentalmars.com/game-news/borderlands-4-shift-codes/",
            "https://www.blueberries.gg/borderlands/active-shift-codes/",
            "https://thebasedotaku.com/codes/borderlands-4/",
            "https://mobalytics.gg/borderlands-4/shift-codes-borderlands-4",
            "https://www.lockercodes.io/borderlands/4/shift-codes",
            "https://kyberscorner.com/borderlands-4-all-known-shift-codes-golden-keys-and-more/",
            # Tier 3 — Major outlets
            "https://www.gamesradar.com/games/borderlands/borderlands-4-shift-codes-golden-keys/",
            "https://www.pcgamer.com/games/fps/borderlands-4-shift-codes/",
            "https://www.pcgamesn.com/borderlands-4/shift-codes",
            "https://www.dexerto.com/gaming/borderlands-4-shift-codes-3249396/",
            "https://gamerant.com/borderlands-4-bl4-shift-codes-golden-keys/",
            "https://www.nme.com/guides/gaming-guides/borderlands-4-shift-codes-3892419",
            # Tier 4 — Supplementary
            "https://progameguides.com/borderlands/borderlands-4-shift-codes/",
            "https://game8.co/games/Borderlands-4/archives/548406",
            "https://thegamepost.com/borderlands-4-all-shift-codes/",
            "https://www.gamingdeputy.com/borderlands-4-shift-codes/",
        ],
    },
    "bl3": {
        "name": "Borderlands 3",
        "sources": [
            # Tier 1 — Official
            "https://borderlands.2k.com/news/borderlands-3-shift-codes/",
            # Tier 2 — Community trackers
            "https://mentalmars.com/game-news/borderlands-3-shift-codes/",
            # Tier 3 — Major outlets
            "https://www.gamesradar.com/borderlands-3-shift-codes/",
            "https://www.pcgamer.com/borderlands-3-shift-codes/",
            "https://www.pcgamesn.com/borderlands-3/shift-codes",
            "https://www.dexerto.com/gaming/borderlands-3-shift-codes-golden-keys-diamond-keys-cosmetics-1838171/",
            "https://www.destructoid.com/borderlands-3-shift-codes/",
            # Tier 4 — Supplementary
            "https://progameguides.com/borderlands/borderlands-3-shift-codes/",
            # Removed: holdtoreset.com, techshout.com, esports.net — dump 190+ historical codes without expired markers
        ],
    },
    "wonderlands": {
        "name": "Tiny Tina's Wonderlands",
        "sources": [
            # Tier 2 — Community trackers
            "https://mentalmars.com/game-news/tiny-tinas-wonderlands-shift-codes/",
            # Tier 3 — Major outlets
            "https://www.gamesradar.com/tiny-tinas-wonderlands-shift-codes/",
            "https://www.pcgamer.com/tiny-tinas-wonderlands-shift-codes-skeleton-keys/",
            # Tier 4 — Supplementary
            "https://progameguides.com/tiny-tinas-wonderlands/tiny-tinas-wonderlands-shift-codes/",
            # Removed: holdtoreset.com — dumps historical codes without expired markers
        ],
    },
    "bl2": {
        "name": "Borderlands 2",
        "sources": [
            # Tier 2 — Community trackers
            "https://mentalmars.com/game-news/borderlands-2-golden-keys/",
            # Tier 4 — Supplementary
            "https://progameguides.com/borderlands/borderlands-2-shift-codes/",
            # Removed: holdtoreset.com — dumps historical codes without expired markers
        ],
    },
    "bltps": {
        "name": "Borderlands: The Pre-Sequel",
        "sources": [
            # Tier 2 — Community trackers
            "https://mentalmars.com/game-news/borderlands-the-pre-sequel-shift-codes/",
            # Tier 4 — Supplementary
            "https://progameguides.com/borderlands/borderlands-the-pre-sequel-shift-codes/",
        ],
    },
    "bl1": {
        "name": "Borderlands GOTY Enhanced",
        "sources": [
            # Tier 2 — Community trackers
            "https://mentalmars.com/game-news/borderlands-game-of-the-year-shift-codes/",
        ],
    },
}

PLATFORMS = ["steam", "epic", "xbox", "playstation", "nintendo"]

# ── Expired detection ─────────────────────────────────────────────

EXPIRED_WORDS = ["expired", "no longer", "inactive", "invalid", "removed", "ended",
                  "not available", "unavailable", "redeemed", "past codes", "old codes",
                  "previous codes", "historical"]
EXPIRED_CSS_CLASSES = ["expired", "inactive", "disabled", "old", "past", "strikethrough",
                       "crossed-out", "line-through", "unavailable", "invalid"]

def _context_expired(tag):
    """Check whether a code tag appears in an 'expired' context via DOM inspection."""
    ctx = ""
    # Check surrounding text: parent, grandparent, and preceding siblings too
    for anc in [tag.parent, getattr(tag.parent, "parent", None)]:
        if anc:
            ctx += " " + anc.get_text(" ", strip=True).lower()
    # Also check text BEFORE this tag (e.g., "Expired:" label preceding the code)
    for sib in tag.find_all_previous(string=True, limit=3):
        ctx += " " + sib.strip().lower()
    for sib in tag.find_all_next(string=True, limit=3):
        ctx += " " + sib.strip().lower()
    # Check strikethrough / line-through / expired CSS classes on any ancestor
    for p in tag.parents:
        if p.name in ("s", "del", "strike"):
            return True
        style = p.get("style", "")
        if "line-through" in style or "text-decoration: line" in style:
            return True
        cls = " ".join(p.get("class", []))
        if any(ec in cls for ec in EXPIRED_CSS_CLASSES):
            return True
        # Check data attributes (some sites use data-status="expired")
        for attr_val in p.attrs.values():
            if isinstance(attr_val, str) and "expired" in attr_val.lower():
                return True
    return any(w in ctx for w in EXPIRED_WORDS)

# ── HTTP helpers ─────────────────────────────────────────────────

def _make_session():
    """Create a requests.Session with default headers for connection reuse."""
    s = requests.Session()
    s.headers.update(HEADERS)
    return s

def _fetch_with_retry(session, url, retries=MAX_RETRIES):
    """GET a URL with retries and exponential backoff."""
    delay = RETRY_BACKOFF
    last_err = None
    for attempt in range(1 + retries):
        try:
            r = session.get(url, timeout=15)
            r.raise_for_status()
            return r
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status == 429 or status >= 500:
                last_err = e
                if attempt < retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
            raise
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_err = e
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
    raise last_err

# ── Cache helpers ────────────────────────────────────────────────

def _cache_key(url):
    return hashlib.md5(url.encode()).hexdigest()

def _get_cached(url):
    path = CACHE_DIR / _cache_key(url)
    try:
        age = time.time() - path.stat().st_mtime
        if age < CACHE_TTL:
            return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        pass
    return None

def _set_cache(url, text):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / _cache_key(url)
    path.write_text(text, encoding="utf-8")

# ── Redeemed history ─────────────────────────────────────────────

HISTORY_PATH = CACHE_DIR / "redeemed_history.json"

def _load_history():
    """Load redeemed code history. Returns {code: {status, date, platform}}."""
    if HISTORY_PATH.exists():
        try:
            return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}

def _save_history(history):
    """Persist redeemed code history to disk."""
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, indent=2), encoding="utf-8")

def _record_redeem(history, code, status, platform, save=True):
    """Record a redemption attempt in history, tracked per-platform.
    Some codes can be redeemed on multiple platforms, so we track each separately."""
    if code not in history:
        history[code] = {"platforms": {}}
    history[code]["platforms"][platform] = {
        "status": status,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    if save:
        _save_history(history)

def _is_redeemed(history, code, platform):
    """Check if a code was already successfully redeemed on a specific platform."""
    entry = history.get(code, {})
    plat_entry = entry.get("platforms", {}).get(platform, {})
    return plat_entry.get("status") in ("redeemed", "already_redeemed")

# ── Scraper ───────────────────────────────────────────────────────

def _scrape_url(session, url, use_cache=False):
    """Scrape a single URL and return (active_codes, expired_codes, domain, error)."""
    domain = url.split("/")[2]
    try:
        html = None
        if use_cache:
            html = _get_cached(url)
        if html is None:
            r = _fetch_with_retry(session, url)
            html = r.text
            if use_cache:
                _set_cache(url, html)

        soup = BeautifulSoup(html, "lxml")
        for junk in soup(["script", "style", "nav", "footer", "header"]):
            junk.decompose()

        active, expired = set(), set()
        for node in soup.find_all(string=CODE_RE):
            for m in CODE_RE.finditer(str(node)):
                code = m.group(1).upper()
                if _context_expired(node):
                    expired.add(code)
                else:
                    active.add(code)
        return active, expired, domain, None
    except Exception as e:
        err_type = type(e).__name__
        return set(), set(), domain, err_type

SOURCE_CAP = 40  # Sources returning more codes than this are "historical dumps"

def scrape_game(key, session, use_cache=False):
    cfg = GAMES[key]
    all_active, all_expired = set(), set()
    source_counts = {}  # code -> number of sources that list it as active
    curated_codes = set()  # codes found on sources returning ≤ SOURCE_CAP codes

    futures = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for url in cfg["sources"]:
            f = pool.submit(_scrape_url, session, url, use_cache)
            futures[f] = url

        for f in as_completed(futures):
            active, expired, domain, err = f.result()
            if err:
                _log(f"    x {domain} ({err})")
            else:
                is_dump = len(active) > SOURCE_CAP
                tag = f" ⚠ historical dump, needs confirmation" if is_dump else ""
                _log(f"    + {domain} ({len(active)} codes{tag})")
            all_active |= active
            all_expired |= expired
            for code in active:
                source_counts[code] = source_counts.get(code, 0) + 1
            # Track codes from curated (non-dump) sources
            if not err and len(active) <= SOURCE_CAP:
                curated_codes |= active

    all_active -= all_expired

    # If we have curated sources, only keep codes confirmed by at least one curated source
    # This filters out historical codes that only appear on dump sites
    if curated_codes:
        dump_only = all_active - curated_codes
        if dump_only:
            _log(f"    Filtered {len(dump_only)} codes only found on dump sites")
            all_active &= curated_codes

    # Sort by confidence: codes found on more sources first
    sorted_active = sorted(all_active, key=lambda c: (-source_counts.get(c, 0), c))
    return sorted_active, sorted(all_expired), source_counts

# ── SHiFT Redeem ─────────────────────────────────────────────────

def _extract_csrf(html):
    """Extract CSRF token from a SHiFT page's HTML."""
    m = re.search(r'name="csrf-token"\s+content="([^"]+)"', html)
    if not m:
        m = re.search(r'name="authenticity_token".*?value="([^"]+)"', html)
    return m.group(1) if m else None

def _shift_login(session):
    """Log in to shift.gearboxsoftware.com. Returns True on success."""
    _log("\n  Logging in to SHiFT...")

    # Check for saved cookies first
    cookie_path = Path.home() / ".cache" / "shift-codes" / "session.json"
    if cookie_path.exists():
        try:
            saved = json.loads(cookie_path.read_text())
            for name, value in saved.items():
                session.cookies.set(name, value, domain="shift.gearboxsoftware.com")
            # Verify session is still valid
            r = session.get(f"{SHIFT_BASE}/account", timeout=15, allow_redirects=False)
            if r.status_code == 200 and "sh_signed_in" in r.text:
                _log("  Resumed saved session.")
                return True
            # Session expired, clear and re-login
            session.cookies.clear()
        except Exception:
            pass

    # If env vars are set, use email/password login silently
    if os.environ.get("SHIFT_EMAIL") and os.environ.get("SHIFT_PASSWORD"):
        return _shift_login_credentials(session, cookie_path)

    # Browser-based login (default for interactive use)
    return _shift_login_browser(session, cookie_path)


def _read_browser_cookies(domain):
    """Try to read cookies for a domain from Edge/Chrome on macOS."""
    import sqlite3, tempfile, shutil
    # Browser cookie DB paths on macOS
    browsers = [
        ("Microsoft Edge", Path.home() / "Library/Application Support/Microsoft Edge/Default/Cookies"),
        ("Google Chrome", Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies"),
    ]
    for name, db_path in browsers:
        if not db_path.exists():
            continue
        try:
            # Copy the DB since the browser locks it
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
            tmp.close()
            shutil.copy2(str(db_path), tmp.name)
            conn = sqlite3.connect(tmp.name)
            # Get the encryption key from macOS Keychain
            label = "Microsoft Edge" if "Edge" in name else "Chrome"
            key_cmd = ["security", "find-generic-password", "-s", f"{label} Safe Storage", "-w"]
            result = subprocess.run(key_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                conn.close()
                os.unlink(tmp.name)
                continue
            key_password = result.stdout.strip()
            # Derive the key using PBKDF2
            import hashlib as _hlib
            dk = _hlib.pbkdf2_hmac("sha1", key_password.encode(), b"saltysalt", 1003, dklen=16)
            # Query cookies for the domain
            cursor = conn.execute(
                "SELECT name, encrypted_value FROM cookies WHERE host_key LIKE ?",
                (f"%{domain}%",)
            )
            cookies = {}
            try:
                from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
                from cryptography.hazmat.backends import default_backend
            except ImportError:
                conn.close()
                os.unlink(tmp.name)
                return None
            for cname, encrypted_value in cursor.fetchall():
                if not encrypted_value:
                    continue
                # Chromium v10 encryption: 'v10' prefix + AES-128-CBC
                if encrypted_value[:3] == b"v10":
                    try:
                        iv = b" " * 16
                        cipher = Cipher(algorithms.AES(dk), modes.CBC(iv), backend=default_backend())
                        decryptor = cipher.decryptor()
                        decrypted = decryptor.update(encrypted_value[3:]) + decryptor.finalize()
                        # Remove PKCS7 padding
                        pad_len = decrypted[-1]
                        if isinstance(pad_len, int) and 1 <= pad_len <= 16:
                            decrypted = decrypted[:-pad_len]
                        # Edge/Chrome prepend a 32-byte HMAC to the value —
                        # strip it to get the actual cookie content
                        if len(decrypted) > 32:
                            trimmed = decrypted[32:]
                            try:
                                value = trimmed.decode("utf-8")
                                value.encode("latin-1")
                                cookies[cname] = value
                                continue
                            except (UnicodeDecodeError, UnicodeEncodeError):
                                pass
                        # Fallback: try the full decrypted bytes (older format)
                        value = decrypted.decode("utf-8")
                        value.encode("latin-1")  # verify it's sendable
                        cookies[cname] = value
                    except (UnicodeDecodeError, UnicodeEncodeError):
                        continue  # skip cookies with bad decryption
                    except Exception:
                        continue
            conn.close()
            os.unlink(tmp.name)
            if cookies:
                _log(f"  Read cookies from {name}.")
                return cookies
        except Exception:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
            continue
    return None


def _parse_cookie_input(raw, session):
    """Parse cookies from various formats into the session. Returns count of cookies loaded."""
    count = 0
    # 1. Try JSON (Cookie Editor JSON export)
    try:
        cookie_list = json.loads(raw)
        if isinstance(cookie_list, list):
            for c in cookie_list:
                if isinstance(c, dict) and "name" in c and "value" in c:
                    session.cookies.set(c["name"], str(c["value"]),
                                        domain=c.get("domain", "shift.gearboxsoftware.com"))
                    count += 1
            if count:
                _log(f"  Loaded {count} cookies from JSON export.")
                return count
    except (json.JSONDecodeError, TypeError):
        pass

    # 2. Try Netscape/curl cookie format (tab-separated, from Cookie Editor "Netscape" export)
    if "\t" in raw:
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                domain, _, path, secure, expires, name, value = parts[:7]
                session.cookies.set(name, value, domain=domain, path=path)
                count += 1
        if count:
            _log(f"  Loaded {count} cookies from Netscape format.")
            return count

    # 3. Fall back to semicolon-separated cookie string
    for pair in raw.replace("\n", "").split(";"):
        pair = pair.strip()
        if "=" in pair:
            name, value = pair.split("=", 1)
            session.cookies.set(name.strip(), value.strip(),
                                domain="shift.gearboxsoftware.com")
            count += 1
    if count:
        _log(f"  Loaded {count} cookies from cookie string.")
    return count


def _shift_login_browser(session, cookie_path):
    """Open browser to SHiFT login page and capture session cookies."""
    _log(f"\n  Opening SHiFT login in your browser...")
    webbrowser.open(f"{SHIFT_BASE}/home")

    _log(f"  Log in to your SHiFT account if not already logged in.")
    _log(f"  Once logged in, come back here and press Enter.\n")

    input("  Press Enter after logging in on the website...")

    # Try to read cookies automatically from the browser
    _log("\n  Reading cookies from browser...")
    cookies = _read_browser_cookies("shift.gearboxsoftware.com")

    if cookies:
        for name, value in cookies.items():
            session.cookies.set(name, value, domain="shift.gearboxsoftware.com")
    else:
        _log("  Could not read cookies automatically.")
        _log("  Use Cookie Editor extension (or similar) to export cookies:\n")
        _log("    1. On the SHiFT website, click the Cookie Editor extension icon")
        _log("    2. Click \"Export\" (copies JSON to clipboard)")
        _log("    3. Paste here and press Enter twice when done\n")
        _log("  (Or paste a semicolon-separated cookie string)\n")

        # Read multiple lines to handle JSON paste
        _log("  Paste cookies below, then press Enter:")
        lines = []
        while True:
            try:
                line = input()
                lines.append(line)
                joined = "\n".join(lines).strip()
                # Stop when we have valid JSON (starts with [ and ends with ])
                if joined.startswith("[") and joined.endswith("]"):
                    try:
                        json.loads(joined)
                        break  # valid JSON, stop reading
                    except json.JSONDecodeError:
                        continue  # incomplete JSON, keep reading
                # For non-JSON input (cookie string), stop on empty line
                elif not joined.startswith("[") and line == "":
                    break
            except EOFError:
                break
        raw = "\n".join(lines).strip()

        if not raw:
            _log("  No cookies provided. Try email/password? (y/n)")
            if input("  ").strip().lower() == "y":
                return _shift_login_credentials(session, cookie_path)
            return False

        parsed = _parse_cookie_input(raw, session)
        if not parsed:
            _log("  Could not parse any cookies from input.")
            return False

    # Verify the session works
    try:
        r = session.get(f"{SHIFT_BASE}/account", timeout=15, allow_redirects=False)
        # If logged in, /account returns 200. If not, it redirects (302) to /home.
        if r.status_code == 302 or r.status_code == 301:
            _log("  Session cookies are invalid or expired.")
            _log("  Try exporting cookies as JSON format in Cookie Editor.")
            session.cookies.clear()
            return False
        if r.status_code != 200:
            _log(f"  SHiFT returned status {r.status_code}.")
            session.cookies.clear()
            return False
        # Double-check: logged-in pages have 'sh_signed_in' in the body class
        if "sh_signed_in" not in r.text:
            _log("  Session cookies are invalid or expired.")
            session.cookies.clear()
            return False
    except Exception as e:
        _log(f"  Could not verify session: {e}")
        return False

    # Save session cookies for reuse
    _save_shift_cookies(session, cookie_path)
    _log("  Logged in successfully!")
    return True


def _shift_login_credentials(session, cookie_path):
    """Log in using email/password (env vars or interactive prompt)."""
    # Fetch login page for CSRF token
    try:
        r = session.get(f"{SHIFT_BASE}/home", timeout=15)
        r.raise_for_status()
    except Exception as e:
        _log(f"  Failed to reach SHiFT: {e}")
        return False

    csrf = _extract_csrf(r.text)
    if not csrf:
        _log("  Could not find CSRF token on login page.")
        return False

    email = os.environ.get("SHIFT_EMAIL") or input("  SHiFT email: ")
    password = os.environ.get("SHIFT_PASSWORD") or getpass.getpass("  SHiFT password: ")

    try:
        r = session.post(
            f"{SHIFT_BASE}/sessions",
            data={
                "authenticity_token": csrf,
                "user[email]": email,
                "user[password]": password,
            },
            headers={"Referer": f"{SHIFT_BASE}/home"},
            timeout=15,
        )
    except Exception as e:
        _log(f"  Login request failed: {e}")
        return False

    # Check if login succeeded
    try:
        r = session.get(f"{SHIFT_BASE}/rewards", timeout=15)
        if "sign in" in r.text.lower() or r.status_code != 200:
            _log("  Login failed — check your email/password.")
            return False
    except Exception as e:
        _log(f"  Could not verify login: {e}")
        return False

    _save_shift_cookies(session, cookie_path)
    _log("  Logged in successfully!")
    return True


def _save_shift_cookies(session, cookie_path):
    """Save SHiFT session cookies to disk for reuse (with restricted permissions)."""
    try:
        cookie_path.parent.mkdir(parents=True, exist_ok=True)
        cookies = {c.name: c.value for c in session.cookies if "shift" in (c.domain or "")}
        cookie_path.write_text(json.dumps(cookies))
        # Restrict permissions: owner read/write only (0o600)
        cookie_path.chmod(0o600)
    except Exception:
        pass

def _parse_redeem_status(response):
    """Parse a SHiFT redemption status response into a status string.
    Returns None if the status is not yet final (still processing)."""
    text = ""
    has_url = False
    try:
        data = response.json()
        text = data.get("text", "")
        has_url = bool(data.get("url"))
    except (json.JSONDecodeError, ValueError, AttributeError):
        text = response.text if hasattr(response, "text") else str(response)

    t = text.lower()

    # "already" must be checked BEFORE "redeemed" since "already redeemed" contains both
    if "already" in t and ("redeemed" in t or "used" in t):
        return "already_redeemed"
    if "expired" in t:
        return "expired"
    if "invalid" in t or "not found" in t or "not a valid" in t:
        return "invalid"
    if "limit" in t and ("reached" in t or "exceed" in t):
        return "already_redeemed"
    if "redeemed" in t or "success" in t:
        return "redeemed"
    if "failed" in t or "unavailable" in t or "not available" in t:
        return "invalid"
    # If JSON has a redirect URL, processing is done
    if has_url:
        return "redeemed"
    # No definitive status — still processing
    return None


def _redeem_code(session, code, platform):
    """
    Redeem a single SHiFT code. Returns a status string:
    'redeemed', 'already_redeemed', 'expired', 'invalid', or 'error:<detail>'
    """
    # Map platform names to SHiFT service identifiers
    platform_service_map = {
        "playstation": "psn",
        "xbox": "xbl",
        "steam": "steam",
        "epic": "epic",
        "nintendo": "nintendo",
    }
    service_id = platform_service_map.get(platform, platform)

    ajax_headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "text/html, */*; q=0.01",
        "Referer": f"{SHIFT_BASE}/rewards",
    }

    # Phase 1: GET code check — returns HTML with platform-specific forms
    try:
        r = session.get(
            f"{SHIFT_BASE}/entitlement_offer_codes",
            params={"code": code},
            headers=ajax_headers,
            timeout=20,
        )
    except Exception as e:
        return f"error:check ({type(e).__name__})"

    if r.status_code == 429:
        return "error:rate_limited"
    if r.status_code in (401, 403):
        return "error:auth_expired"
    if r.status_code >= 400:
        return "invalid"

    response_lower = r.text.lower()

    # Check for immediate status messages in the response
    if "not a valid" in response_lower or "not found" in response_lower:
        return "invalid"
    if "expired" in response_lower and "form" not in response_lower:
        return "expired"
    if "already" in response_lower and "redeemed" in response_lower and "form" not in response_lower:
        return "already_redeemed"
    if "limit" in response_lower and ("reached" in response_lower or "exceed" in response_lower):
        return "already_redeemed"

    # Phase 2: Find and submit the platform-specific redemption form
    soup = BeautifulSoup(r.text, "lxml")
    forms = soup.find_all("form")
    if not forms:
        if "already" in response_lower or "redeemed" in response_lower:
            return "already_redeemed"
        return "error:no_forms_found"

    # Find the form matching the desired platform/service
    target_form = None
    for form in forms:
        # Check the service hidden input
        svc_input = form.find("input", {"name": "archway_code_redemption[service]"})
        if svc_input and svc_input.get("value", "").lower() == service_id:
            target_form = form
            break
        # Fallback: check button text
        submit_btn = form.find("input", {"type": "submit"})
        if submit_btn:
            btn_val = submit_btn.get("value", "").lower()
            if service_id in btn_val or platform in btn_val:
                target_form = form
                break

    if not target_form:
        # SHiFT may use a single form with platform pre-selected from account settings
        # Fall back to the first form (this is the normal case for most codes)
        target_form = forms[0]

    # Build form data from all inputs in the form
    form_data = {}
    for inp in target_form.find_all("input"):
        name = inp.get("name")
        if name:
            form_data[name] = inp.get("value", "")

    action = target_form.get("action", "/code_redemptions")
    action_url = urljoin(SHIFT_BASE, action)

    # Phase 3: POST the redemption form
    try:
        r = session.post(
            action_url,
            data=form_data,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "text/html, */*; q=0.01",
                "Referer": f"{SHIFT_BASE}/rewards",
            },
            timeout=20,
            allow_redirects=False,
        )
    except Exception as e:
        return f"error:redeem ({type(e).__name__})"

    if r.status_code == 429:
        return "error:rate_limited"

    # Phase 4: Follow redirect to status-polling endpoint
    if r.status_code in (301, 302, 303):
        status_url = r.headers.get("Location", "")
        if not status_url.startswith("http"):
            status_url = f"{SHIFT_BASE}{status_url}"

        # Poll the status endpoint (SHiFT processes async)
        for attempt in range(10):
            time.sleep(2)
            try:
                sr = session.get(status_url, headers=ajax_headers, timeout=10)
                status = _parse_redeem_status(sr)
                if status is not None:
                    return status
                # None = still processing, keep polling
            except Exception:
                pass
        return "error:poll_timeout"

    # Non-redirect response — check text directly
    status = _parse_redeem_status(r)
    return status if status is not None else "error:unknown_response"

def redeem_codes(session, codes, platform):
    """Redeem a list of codes, skipping ones already redeemed on this platform."""
    history = _load_history()

    # Filter out codes already redeemed on this specific platform
    new_codes = [c for c in codes if not _is_redeemed(history, c, platform)]
    skipped = len(codes) - len(new_codes)

    if skipped:
        _log(f"\n  Skipping {skipped} codes already redeemed on {platform}")
    if not new_codes:
        _log(f"  All {len(codes)} codes already redeemed on {platform}. Nothing to do.\n")
        return {"redeemed": 0, "already_redeemed": 0, "expired": 0, "invalid": 0, "error": 0, "skipped": skipped}

    _log(f"\n  Redeeming {len(new_codes)} codes for {platform}...\n")
    results = {"redeemed": 0, "already_redeemed": 0, "expired": 0, "invalid": 0, "error": 0, "skipped": skipped}

    for i, code in enumerate(new_codes, 1):
        status = _redeem_code(session, code, platform)

        if status == "redeemed":
            _log(f"    [{i}/{len(new_codes)}] {code} — Redeemed!")
            results["redeemed"] += 1
        elif status == "already_redeemed":
            _log(f"    [{i}/{len(new_codes)}] {code} — Already redeemed")
            results["already_redeemed"] += 1
        elif status == "expired":
            _log(f"    [{i}/{len(new_codes)}] {code} — Expired")
            results["expired"] += 1
        elif status == "invalid":
            _log(f"    [{i}/{len(new_codes)}] {code} — Invalid code")
            results["invalid"] += 1
        else:
            _log(f"    [{i}/{len(new_codes)}] {code} — {status}")
            results["error"] += 1

        # Record result in history (per-platform, defer save to end)
        _record_redeem(history, code, status, platform, save=False)

        # Rate-limit delay between redemptions
        if status == "error:rate_limited":
            wait = min(30 * (2 ** (results["error"] - 1)), 120)  # exponential: 30, 60, 120s
            _log(f"    Rate limited — waiting {wait}s...")
            time.sleep(wait)
        elif i < len(new_codes):
            time.sleep(2 + random.random() * 2)  # 2-4s jittered delay

    _log(f"\n  Results: {results['redeemed']} redeemed, "
         f"{results['already_redeemed']} already redeemed, "
         f"{results['expired']} expired, "
         f"{results['invalid']} invalid, "
         f"{results['error']} errors"
         + (f", {results['skipped']} skipped (previously redeemed)" if results['skipped'] else ""))
    # Save history once at the end (instead of after every code)
    _save_history(history)
    return results

# ── Clipboard ────────────────────────────────────────────────────

def _copy_to_clipboard(codes):
    """Copy codes to clipboard. Returns True on success."""
    text = "\n".join(codes)
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except ImportError:
        pass
    # Platform fallback
    import platform as _p
    cmd = {"Darwin": "pbcopy", "Windows": "clip"}.get(_p.system())
    if cmd:
        try:
            subprocess.run([cmd], input=text.encode(), check=True)
            return True
        except Exception:
            pass
    return False

# ── Settings persistence ─────────────────────────────────────────

SETTINGS_PATH = CACHE_DIR / "settings.json"

def _load_settings():
    if SETTINGS_PATH.exists():
        try:
            return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}

def _save_settings(settings):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")

# ── Interactive menu helpers ─────────────────────────────────────

def _prompt(msg, valid=None, default=None):
    while True:
        suffix = f" [{default}]" if default else ""
        raw = input(f"  {msg}{suffix}: ").strip()
        if not raw and default:
            return default
        if valid is None or raw.lower() in [v.lower() for v in valid]:
            return raw
        print(f"  Invalid choice. Options: {', '.join(valid)}")

def _print_banner():
    print(f"\n{'='*55}")
    print(f"  SHiFT Code Finder — {datetime.now().strftime('%B %d, %Y')}")
    print(f"{'='*55}")

def _print_menu(settings):
    platform = settings.get("platform", "not set")
    logged_in = settings.get("logged_in", False)
    account = settings.get("email", "not linked")
    last_checked = settings.get("last_checked", "never")

    print()
    print(f"  Account:  {account}")
    print(f"  Platform: {platform.title()}")
    print(f"  Status:   {'Logged in' if logged_in else 'Not logged in'}")
    print(f"  Last run: {last_checked}")
    print()
    print("  1) Link SHiFT Account / Select Platform")
    print("  2) Find Codes — All Games")
    print("  3) Find Codes — Choose Game")
    print("  4) Find & Auto-Redeem Codes")
    print("  5) Copy All Active Codes to Clipboard")
    print("  6) View Redemption History")
    print("  7) Reset History")
    print("  8) Clear Cache")
    if logged_in:
        print("  9) Log Out")
    print("  0) Exit")
    print()
    return input("  Choose [0-9]: ").strip()

def _action_link_account(settings, session):
    print()
    print("  -- Platform Selection --")
    print()
    for i, p in enumerate(PLATFORMS, 1):
        marker = " (current)" if p == settings.get("platform") else ""
        print(f"    {i}) {p.title()}{marker}")
    print()
    cur_idx = str(PLATFORMS.index(settings.get("platform", "steam")) + 1)
    choice = _prompt("Select platform (1-5)", [str(i) for i in range(1, len(PLATFORMS) + 1)], default=cur_idx)
    settings["platform"] = PLATFORMS[int(choice) - 1]
    print(f"\n  Platform set to: {settings['platform'].title()}")

    print()
    print("  -- SHiFT Account --")
    print()
    print("  Link your Gearbox SHiFT account to enable auto-redeem.")
    print("  (You can also set SHIFT_EMAIL and SHIFT_PASSWORD env vars)")
    print()
    link = _prompt("Link account now? (y/n)", ["y", "n"], default="y")
    if link.lower() == "y":
        if _shift_login(session):
            settings["logged_in"] = True
            settings["email"] = os.environ.get("SHIFT_EMAIL", settings.get("email", "linked"))
        else:
            settings["logged_in"] = False
    else:
        print("  Skipped. You can link later from the menu.")

    _save_settings(settings)
    print()

def _action_find_codes(session, settings, game_keys=None, use_cache=False, out=None):
    if game_keys is None:
        game_keys = list(GAMES.keys())
    if out is None:
        out = print

    history = _load_history()
    platform = settings.get("platform", "steam")

    all_results = {}
    all_codes = []
    seen_codes = set()

    for key in game_keys:
        name = GAMES[key]["name"]
        out(f"\n  {name}...")
        active, expired, source_counts = scrape_game(key, session, use_cache=use_cache)
        all_results[key] = {"name": name, "active": active, "expired_count": len(expired)}

        for c in active:
            if c not in seen_codes:
                all_codes.append(c)
                seen_codes.add(c)

        if active:
            redeemed_on_platform = [c for c in active if _is_redeemed(history, c, platform)]
            new_count = len(active) - len(redeemed_on_platform)
            suffix = ""
            if redeemed_on_platform:
                suffix = f" ({new_count} new, {len(redeemed_on_platform)} redeemed on {platform})"
            out(f"\n  {len(active)} active codes{suffix}:")
            for c in active:
                markers = []
                if _is_redeemed(history, c, platform):
                    markers.append("redeemed")
                sc = source_counts.get(c, 0)
                if sc >= 3:
                    markers.append(f"✓ {sc} sources")
                elif sc == 1:
                    markers.append("1 source")
                tag = f" [{', '.join(markers)}]" if markers else ""
                out(f"     {c}{tag}")
        else:
            out(f"\n  No active codes found")
        out(f"  ({len(expired)} expired codes filtered out)")

    total_active = sum(len(v["active"]) for v in all_results.values())
    total_new = sum(
        len([c for c in v["active"] if not _is_redeemed(history, c, platform)])
        for v in all_results.values()
    )
    out(f"\n{'='*55}")
    out(f"  TOTAL: {total_active} active codes across {len(game_keys)} games")
    if history and total_new < total_active:
        out(f"  NEW:   {total_new} codes not yet redeemed on {platform}")
    out(f"  Redeem at: https://shift.gearboxsoftware.com/rewards")
    out(f"{'='*55}\n")

    # Save last-checked timestamp
    settings["last_checked"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _save_settings(settings)

    return all_results, all_codes

def _action_clear_cache():
    """Clear cached page fetches."""
    count = 0
    if CACHE_DIR.exists():
        for f in CACHE_DIR.iterdir():
            if f.is_file() and f.name not in ("redeemed_history.json", "settings.json", "session.json"):
                f.unlink()
                count += 1
    print(f"\n  Cleared {count} cached pages.\n")

def _action_choose_game():
    print()
    print("  -- Select Games --")
    print()
    keys = list(GAMES.keys())
    for i, key in enumerate(keys, 1):
        print(f"    {i}) {GAMES[key]['name']}")
    print(f"    A) All games")
    print()
    raw = _prompt("Enter numbers separated by spaces, or A for all", default="A")
    if raw.upper() == "A":
        return keys
    selected = []
    for part in raw.split():
        try:
            idx = int(part) - 1
            if 0 <= idx < len(keys):
                selected.append(keys[idx])
        except ValueError:
            if part.lower() in GAMES:
                selected.append(part.lower())
    return selected or keys

def _action_view_history():
    history = _load_history()
    if not history:
        print("\n  No redemption history yet.\n")
        return
    print(f"\n  -- Redemption History ({len(history)} codes) --\n")
    for code, data in sorted(history.items()):
        platforms = data.get("platforms", {})
        parts = []
        for plat, info in platforms.items():
            parts.append(f"{plat}: {info['status']} ({info['date']})")
        print(f"  {code}")
        for p in parts:
            print(f"    {p}")
    print()

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
  python3 shift_codes.py              Interactive menu
  python3 shift_codes.py --auto       Skip menu, scrape all games
  python3 shift_codes.py bl4 bl3      Skip menu, specific games
  python3 shift_codes.py --redeem     Scrape + auto-redeem
  python3 shift_codes.py --json       JSON output (non-interactive)""")
    ap.add_argument("games", nargs="*", choices=[*GAMES.keys(), []], default=[],
                    help="Games to check (skips menu)")
    ap.add_argument("--auto", action="store_true",
                    help="Skip menu, scrape all games immediately")
    ap.add_argument("--copy", action="store_true",
                    help="Copy all active codes to clipboard")
    ap.add_argument("--json", action="store_true",
                    help="Output as JSON (to stdout; progress goes to stderr)")
    ap.add_argument("--cache", action="store_true",
                    help=f"Cache page fetches for {CACHE_TTL // 60} minutes")
    ap.add_argument("--redeem", action="store_true",
                    help="Auto-redeem all found codes on your SHiFT account")
    ap.add_argument("--platform", choices=PLATFORMS, default=None,
                    help="Platform to redeem for (overrides saved setting)")
    ap.add_argument("--reset-history", action="store_true",
                    help="Clear the redeemed code history and start fresh")
    args = ap.parse_args()

    session = _make_session()
    settings = _load_settings()

    # CLI --platform overrides saved setting
    if args.platform:
        settings["platform"] = args.platform
        _save_settings(settings)
    elif "platform" not in settings:
        settings["platform"] = "steam"

    # Handle history reset
    if args.reset_history:
        if HISTORY_PATH.exists():
            HISTORY_PATH.unlink()
            print("  Redeemed history cleared.\n")
        else:
            print("  No history to clear.\n")

    # ── Non-interactive mode (any CLI flag or game arg) ──────────
    non_interactive = args.auto or args.games or args.json or args.redeem or args.copy
    if non_interactive:
        game_keys = args.games if args.games else list(GAMES.keys())
        out = _log if args.json else print

        out(f"\n{'='*55}")
        out(f"  SHiFT Code Finder — {datetime.now().strftime('%B %d, %Y')}")
        out(f"{'='*55}\n")

        _results, all_codes = _action_find_codes(
            session, settings, game_keys, args.cache,
            out=_log if args.json else print
        )

        if args.json:
            print(json.dumps(_results, indent=2))

        if args.copy and all_codes:
            if _copy_to_clipboard(all_codes):
                (print if not args.json else _log)(f"  {len(all_codes)} codes copied to clipboard!")
            else:
                (print if not args.json else _log)("  Couldn't copy — install pyperclip or copy manually above.")

        if args.redeem and all_codes:
            if _shift_login(session):
                redeem_codes(session, all_codes, settings.get("platform", "steam"))
            else:
                print("\n  Skipping redeem — login failed.")
                print("  Set SHIFT_EMAIL and SHIFT_PASSWORD env vars, or use the menu.\n")
        return

    # ── Interactive menu mode ────────────────────────────────────
    _print_banner()

    while True:
        choice = _print_menu(settings)

        if choice == "0":
            print("\n  Goodbye!\n")
            break

        elif choice == "1":
            _action_link_account(settings, session)

        elif choice == "2":
            _action_find_codes(session, settings, use_cache=args.cache)
            input("  Press Enter to continue...")

        elif choice == "3":
            game_keys = _action_choose_game()
            if game_keys:
                _action_find_codes(session, settings, game_keys, use_cache=args.cache)
            input("  Press Enter to continue...")

        elif choice == "4":
            if not settings.get("platform"):
                print("\n  Please select a platform first (option 1).\n")
                continue
            game_keys = _action_choose_game()
            _results, all_codes = _action_find_codes(session, settings, game_keys, use_cache=args.cache)
            if all_codes:
                if not settings.get("logged_in"):
                    print("  Need to log in first...")
                    if _shift_login(session):
                        settings["logged_in"] = True
                        _save_settings(settings)
                    else:
                        print("  Login failed. Skipping redeem.\n")
                        input("  Press Enter to continue...")
                        continue
                redeem_codes(session, all_codes, settings["platform"])
            else:
                print("  No codes to redeem.")
            input("\n  Press Enter to continue...")

        elif choice == "5":
            _results, all_codes = _action_find_codes(session, settings, use_cache=args.cache)
            if all_codes:
                if _copy_to_clipboard(all_codes):
                    print(f"  {len(all_codes)} codes copied to clipboard!")
                else:
                    print("  Couldn't copy — install pyperclip or copy manually above.")
            input("  Press Enter to continue...")

        elif choice == "6":
            _action_view_history()
            input("  Press Enter to continue...")

        elif choice == "7":
            if HISTORY_PATH.exists():
                confirm = _prompt("Are you sure? This cannot be undone (y/n)", ["y", "n"], default="n")
                if confirm.lower() == "y":
                    HISTORY_PATH.unlink()
                    print("\n  Redeemed history cleared.\n")
                else:
                    print("\n  Cancelled.\n")
            else:
                print("\n  No history to clear.\n")

        elif choice == "8":
            _action_clear_cache()

        elif choice == "9":
            # Log out — clear saved session
            cookie_path = CACHE_DIR / "session.json"
            if cookie_path.exists():
                cookie_path.unlink()
            session.cookies.clear()
            settings["logged_in"] = False
            settings.pop("email", None)
            _save_settings(settings)
            print("\n  Logged out. Session cookies cleared.\n")

        else:
            print("\n  Invalid choice.\n")


if __name__ == "__main__":
    main()
