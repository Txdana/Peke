"""Situational awareness: read the prompt and the environment, then decide a plan.

Pure standard-library helpers (no network except a loopback port check) so they are
cheap to call and easy to test.
"""
import importlib.util
import math
import re
import shutil
import socket
from dataclasses import dataclass, field
from datetime import datetime
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlsplit

_TRAIL = ".,;:!?)]}>\"'"
_URL = re.compile(r"""(?i)(?<![@\w.])((?:https?://|www\.)[^\s<>"'`]+)""")
_BARE = re.compile(
    r"""(?i)(?<![@\w./-])((?:[a-z0-9-]+\.)+(?:com|org|net|io|dev|ai|co|gov|edu|app|info|xyz|zw|za|uk|us|ke|ng|eu)(?:/[^\s<>"'`]*)?)(?![\w@-])"""
)
_STOP = set(
    "a an the and or of to in on for with from by at as is are was were be been it this that these those i me my "
    "we you your our can could should would will do does did how what which who when where why about into over "
    "please find get show tell give make all any some more most than then them they their there here also just "
    "using use via scrape search look up latest current today now new check see see also email tell know want need help".split()
)
_FRESH = re.compile(r"(?i)\b(latest|today|now|current(?:ly)?|recent(?:ly)?|news|this (?:week|month|year)|breaking|price|score|live|just released|20\d\d)\b")
_SCRAPE = re.compile(r"(?i)\b(scrape|extract|list (?:all|every)|every|table|dataset|collect|crawl)\b")
_ENDPOINT = re.compile(r"(?i)\b(api|endpoints?|reverse[- ]engineer|network|xhr|hidden|json feed|graphql|rea)\b")
_SEARCH = re.compile(r"(?i)\b(search|look up|google|find out|research|find me|find)\b")


def extract_urls(prompt: str) -> list[str]:
    """URLs (and bare domains) the user wrote, in order, de-duplicated, scheme-normalised."""
    found: list[str] = []
    for regex in (_URL, _BARE):
        for match in regex.finditer(prompt):
            raw = match.group(1).rstrip(_TRAIL)
            if not raw:
                continue
            if raw.lower().startswith("www."):
                raw = "https://" + raw
            elif not re.match(r"(?i)https?://", raw):
                raw = "https://" + raw
            try:
                parts = urlsplit(raw)
                if not parts.hostname or "." not in parts.hostname:
                    continue
            except ValueError:
                continue
            if raw not in found and not any(raw == f.rstrip("/") or raw.rstrip("/") == f for f in found):
                found.append(raw)
    return found


def keywords(prompt: str) -> list[str]:
    text = re.sub(r"\S+@\S+", " ", prompt)  # emails are not search terms
    text = _URL.sub(" ", text)
    text = _BARE.sub(" ", text)
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9+#.-]{1,}", text.lower())
    out: list[str] = []
    for w in words:
        w = w.strip(".-")
        if len(w) > 1 and w not in _STOP and w not in out:
            out.append(w)
    return out


def search_query(prompt: str) -> str:
    """Prompt minus URLs and filler, capped to a search-engine-friendly length."""
    return " ".join(keywords(prompt)[:12]) or prompt.strip()[:200]


def analyze_intent(prompt: str, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now()
    years = [int(y) for y in re.findall(r"\b(20\d\d)\b", prompt)]
    return {
        "wants_fresh": bool(_FRESH.search(prompt)) or any(y >= now.year - 1 for y in years),
        "wants_scrape": bool(_SCRAPE.search(prompt)),
        "wants_endpoints": bool(_ENDPOINT.search(prompt)),
        "explicit_search": bool(_SEARCH.search(prompt)),
        "years": years,
    }


def _tokens(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for w in re.findall(r"[a-z0-9][a-z0-9+#.-]{1,}", text.lower()):
        counts[w.strip(".-")] = counts.get(w.strip(".-"), 0) + 1
    return counts


def score_text(kw: list[str], title: str, text: str) -> float:
    """Length-normalised keyword relevance (title hits count triple)."""
    if not kw:
        return 0.0
    body, head = _tokens(text), _tokens(title)
    raw = 0.0
    for k in kw:
        tf = sum(c for t, c in body.items() if t == k or t.startswith(k))
        hf = sum(c for t, c in head.items() if t == k or t.startswith(k))
        raw += (1 + math.log(tf)) if tf else 0
        raw += 3 * ((1 + math.log(hf)) if hf else 0)
    coverage = sum(1 for k in kw if any(t == k or t.startswith(k) for t in body) or any(t.startswith(k) for t in head)) / len(kw)
    return round(raw / math.sqrt(1 + len(text) / 2000) * (0.5 + coverage), 3)


def best_excerpt(text: str, kw: list[str], size: int = 700) -> str:
    """The ``size``-char window with the most keyword hits (falls back to the start)."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= size:
        return text
    low, step = text.lower(), max(100, size // 4)
    best, best_at = -1, 0
    for start in range(0, len(text) - size + step, step):
        window = low[start:start + size]
        hits = sum(window.count(k) for k in kw)
        if hits > best:
            best, best_at = hits, start
    chunk = text[best_at:best_at + size]
    if best_at and " " in chunk[:40]:
        chunk = chunk.split(" ", 1)[1]  # do not start mid-word
    return chunk.strip()


def page_title(raw_html: str | None) -> str:
    if not raw_html:
        return ""
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw_html)
    return re.sub(r"\s+", " ", unescape(m.group(1))).strip()[:200] if m else ""


def extract_links(raw_html: str | None, base_url: str, same_host: bool = True) -> list[tuple[str, str]]:
    """(absolute_url, anchor_text) pairs for http(s) links, optionally same-host only."""
    if not raw_html:
        return []
    host = urlsplit(base_url).netloc.lower()
    out: dict[str, str] = {}
    for href, inner in re.findall(r"""(?is)<a\b[^>]*?href=["']([^"'#][^"']*)["'][^>]*>(.*?)</a>""", raw_html):
        url = urljoin(base_url, unescape(href.strip()))
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or (same_host and parts.netloc.lower() != host):
            continue
        url = url.split("#", 1)[0]
        text = re.sub(r"(?s)<[^>]+>", " ", unescape(inner))
        out.setdefault(url, re.sub(r"\s+", " ", text).strip()[:160])
    return list(out.items())


def _port_open(host: str, port: int, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@dataclass
class Situation:
    now: str
    prompt_urls: list[str]
    keywords: list[str]
    intent: dict[str, Any]
    search: dict[str, Any] = field(default_factory=dict)
    rea: dict[str, Any] = field(default_factory=dict)
    model: dict[str, Any] = field(default_factory=dict)
    scrapling: bool = False
    mode: str = "none"  # search+links | search | links | none
    plan: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def assess_environment(settings: Any, prompt: str, search_status: dict[str, Any], use_search: bool = True,
                       deep: bool | None = None, now: datetime | None = None) -> Situation:
    """Combine prompt analysis with what this machine can actually do right now."""
    now = now or datetime.now().astimezone()
    urls = extract_urls(prompt)
    intent = analyze_intent(prompt, now)
    sit = Situation(now=now.isoformat(timespec="minutes"), prompt_urls=urls, keywords=keywords(prompt), intent=intent)
    sit.scrapling = importlib.util.find_spec("scrapling") is not None
    if not sit.scrapling:
        sit.warnings.append("Scrapling is not installed; pages cannot be fetched (pip install 'scrapling[fetchers]').")

    rea_cmd = getattr(settings, "rea_command", None)
    rea_bin = bool(rea_cmd and shutil.which(rea_cmd.split()[0]))
    cdp = getattr(settings, "rea_cdp_endpoint", "http://127.0.0.1:9222")
    try:
        p = urlsplit(cdp)
        cdp_up = _port_open(p.hostname or "127.0.0.1", p.port or 9222) if rea_bin else False
    except ValueError:
        cdp_up = False
    sit.rea = {"cli": rea_bin, "browser_debug_port": cdp_up,
               "live_page_analysis": rea_bin and cdp_up}

    mp = getattr(settings, "model_path", None)
    kind = getattr(settings, "provider_main_kind", "local_builtin")
    local_ok = bool(mp and mp.is_file()) if kind == "local_builtin" else kind == "ollama"
    sit.model = {"kind": kind, "ready": local_ok, "cloud": kind in {"openrouter", "custom_openai"}}

    sit.search = dict(search_status)
    can_search = use_search and bool(search_status.get("available"))
    if can_search and urls:
        sit.mode = "search+links"
    elif can_search:
        sit.mode = "search"
    elif urls:
        sit.mode = "links"
    else:
        sit.mode = "none"

    if sit.mode == "none":
        why = search_status.get("reason", "search is off")
        sit.warnings.append(f"No search ({why}) and no links in the prompt: add a URL or set SEARXNG_URL.")
    if not can_search and use_search and intent["wants_fresh"] and urls:
        sit.warnings.append("This looks time-sensitive but search is unavailable; answering only from the linked pages.")

    if sit.mode in {"search", "search+links"}:
        sit.plan.append("search via SearXNG" + (" (recent results only)" if intent["wants_fresh"] else ""))
    if urls:
        sit.plan.append(f"scrape {len(urls)} link(s) from the prompt first")
    sit.plan.append("rank pages by relevance to the prompt")
    if deep or (deep is None and intent["wants_endpoints"]):
        sit.plan.append("REA + subagent endpoint discovery on the best pages"
                        + ("" if sit.rea["live_page_analysis"] else " (static analysis only: REA/browser not ready)"))
    sit.plan.append("answer with citations" if sit.model["ready"] and not sit.model["cloud"]
                    else "return ranked excerpts (no local model ready)")
    return sit
