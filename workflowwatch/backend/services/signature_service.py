"""
Event signature normalization for WP-7 auto-labeling.
Produces stable, canonical strings from event data (app + title + domain)
used as keys for label cache lookups and as input to embedding similarity.
"""

import re
from urllib.parse import urlparse

# Common app name variants → canonical name
_APP_ALIASES: dict[str, str] = {
    "google chrome": "chrome",
    "google chrome helper": "chrome",
    "chromium": "chrome",
    "chrome": "chrome",
    "code - oss": "vscode",
    "visual studio code": "vscode",
    "code": "vscode",
    "code helper (renderer)": "vscode",
    "code helper": "vscode",
    "zed": "zed",
    "zed-preview": "zed",
    "pycharm": "pycharm",
    "pycharm ce": "pycharm",
    "intellij idea": "intellij",
    "intellij idea ce": "intellij",
    "webstorm": "webstorm",
    "rubymine": "rubymine",
    "goland": "goland",
    "clion": "clion",
    "datagrip": "datagrip",
    "rider": "rider",
    "android studio": "android studio",
    "xcode": "xcode",
    "firefox": "firefox",
    "mozilla firefox": "firefox",
    "firefox developer edition": "firefox",
    "safari": "safari",
    "terminal": "terminal",
    "iterm2": "terminal",
    "iterm": "terminal",
    "alacritty": "terminal",
    "kitty": "terminal",
    "wezterm": "terminal",
    "ghostty": "terminal",
    "hyper": "terminal",
    "figma": "figma",
    "sketch": "sketch",
    "slack": "slack",
    "discord": "discord",
    "microsoft teams": "teams",
    "zoom": "zoom",
    "spotify": "spotify",
    "notion": "notion",
    "obsidian": "obsidian",
    "linear": "linear",
    "bear": "bear",
    "1password": "1password",
    "finder": "finder",
    "activity monitor": "activity monitor",
    "system preferences": "system preferences",
    "system settings": "system preferences",
}

# Noise patterns to strip from titles before normalizing
_TITLE_NOISE_PATTERNS = [
    r'\s*[-–—]\s*\d+:\d+(?::\d+)?',          # " - 42:7" (line:col) or "12:30:01" (time)
    r'\s*\(\d+\)\s*$',                         # " (3)" trailing count
    r'\s*[-–—]\s*[Mm]odified\s*$',             # " - Modified"
    r'\s*[-–—]\s*[Ee]dited\s*$',               # " - Edited"
    r'\s*\*\s*$',                               # Trailing asterisk (unsaved)
    r'\s*•\s*\d+\s*$',                         # "• 3" indicator
    r'\s*[-–—]\s*\d+\s+unread.*$',             # "- 3 unread messages"
    r'\s*[-–—]\s*\d+\s+new.*$',               # "- 5 new"
    r'\s*\[\d+\]\s*$',                         # "[42]" trailing
    r'\s*[-–—]\s*Page\s+\d+.*$',              # " - Page 3 of 10"
]
_TITLE_NOISE_RE = re.compile('|'.join(_TITLE_NOISE_PATTERNS), re.IGNORECASE)

# Strip well-known app suffixes from titles (e.g., "file.py — Visual Studio Code")
_APP_SUFFIX_RE = re.compile(
    r'\s*[-–—]\s*(?:Visual Studio Code|Code|VS Code|PyCharm(?: CE)?|IntelliJ IDEA(?: CE)?|'
    r'WebStorm|GoLand|CLion|Rider|Xcode|Android Studio|'
    r'Google Chrome|Chrome|Chromium|Firefox(?:[^\w]Developer Edition)?|Safari|'
    r'Terminal|iTerm2?|Alacritty|Kitty|WezTerm|Ghostty|'
    r'Slack|Discord|Microsoft Teams|Zoom|Figma|Sketch|Notion|Obsidian)\s*$',
    re.IGNORECASE,
)


def normalize_app(app: str | None) -> str:
    """Canonicalize app name: lowercase, resolve known aliases."""
    if not app or not isinstance(app, str):
        return ""
    key = app.lower().strip()
    return _APP_ALIASES.get(key, key)


_LEADING_COUNT_RE = re.compile(r'^\(\d+\)\s*')  # "(3) general" → "general"


def normalize_title(title: str | None) -> str:
    """
    Strip dynamic/noisy suffixes from a window title, return lowercase prefix.
    Aim: same document = same title fragment regardless of edit state.
    """
    if not title or not isinstance(title, str):
        return ""
    t = title.strip()
    # Strip leading notification counts: "(3) general" → "general"
    t = _LEADING_COUNT_RE.sub('', t)
    # Strip known app names from the end
    t = _APP_SUFFIX_RE.sub('', t)
    # Strip noise patterns
    t = _TITLE_NOISE_RE.sub('', t)
    t = t.strip(' -–—')
    # Truncate to first 60 chars, lowercase
    return t[:60].lower()


def extract_domain(url: str | None) -> str:
    """Extract bare domain from URL (strips www.)."""
    if not url or not isinstance(url, str):
        return ""
    try:
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def event_signature(data: dict | None) -> str:
    """
    Produce a stable, normalized string representing an event's semantic identity.
    Format: "app|title_prefix|domain"

    Used as:
    - Key for SQLite label cache lookups (exact match)
    - Input text for embedding similarity search

    Same app + document → same signature regardless of dynamic title noise.
    """
    if not data or not isinstance(data, dict):
        return "unknown||"
    app = normalize_app(data.get("app"))
    title = normalize_title(data.get("title"))
    domain = extract_domain(data.get("url"))
    return f"{app}|{title}|{domain}"
