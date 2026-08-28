#!/usr/bin/env python3
"""
NexaBank demo traffic + endpoint-discovery harness
==================================================

Adapted from the Arcadia harness for the NexaBank demo app
(https://nexabank.vt.f5-cloud-demo.com), which is fronted and protected by
F5 XC. Same framework — Tor transport, non-US exit routing for the Geo LB,
rate control, per-session randomization, and cacheable-ratio shaping — but the
traffic model is different because NexaBank is a **fully client-side static
app**:

  * "Quick Demo Login" is client-side only: it writes a sessionStorage object
    and redirects to dashboard.html. There is NO server auth, NO cookie, and
    NO login/transaction API. Protected pages are gated by an in-browser JS
    check, so the server serves them as plain static files regardless.
  * Transfers / IFSC checks / dashboards are all faked in JavaScript
    (setTimeout + DOM), with no network calls.

So realistic HTTP traffic here = a user **navigating between static pages**,
each of which pulls the shared CSS/JS. That's almost entirely cacheable
content (great for the CDN demo). The nginx config also exposes JSON
introspection endpoints (/whoami, /pod-info, /origin-info, /health) — handy for
a multi-cloud "which pod served me" angle; these are no-store (never cached).

Usage
-----
    pip install "requests[socks]" beautifulsoup4
    # Tor Browser open (SOCKS 127.0.0.1:9150)
    python3 nexabank_harness.py --crawl-only        # discover pages/assets
    python3 nexabank_harness.py                      # crawl once, then loop
    python3 nexabank_harness.py --skip-crawl --rate 4
    python3 nexabank_harness.py --check-cache        # CDN cache diagnosis

Stop the loop with Ctrl-C.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import socket
import sys
import time
from dataclasses import dataclass, field
from hashlib import md5
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

try:
    import requests
except ImportError:
    sys.exit("Missing dependency. Run:  pip install \"requests[socks]\" beautifulsoup4")

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Missing dependency. Run:  pip install beautifulsoup4")


# ============================================================================
# CONFIG
# ============================================================================

@dataclass
class Config:
    # --- Target -----------------------------------------------------------
    base_url: str = "https://nexabank.vt.f5-cloud-demo.com"
    entry_path: str = "/index.html"

    # --- Tor SOCKS proxy (Tor Browser bundle = 9150; system tor = 9050) ---
    socks_host: str = "127.0.0.1"
    socks_port: int = 9150

    # --- Tor control port (optional; for NEWNYM / exit pinning) -----------
    control_enabled: bool = False
    control_host: str = "127.0.0.1"
    control_port: int = 9151
    control_password: str = ""
    exit_countries: Tuple[str, ...] = ("de", "nl", "fr", "gb", "se", "ch")

    verify_exit_geo: bool = True
    disallowed_exit_countries: Tuple[str, ...] = ("US",)

    # --- Pacing -----------------------------------------------------------
    rate_per_min: Optional[float] = None   # actions/min (jittered +/-40%); via --rate
    min_sleep: float = 20.0
    max_sleep: float = 60.0
    cycle_sleep_min: float = 45.0
    cycle_sleep_max: float = 150.0
    new_circuit_each_cycle: bool = True

    # --- Per-session randomization ----------------------------------------
    # A "session" = a random user journey (ordered page visits). Each visit
    # fetches the page HTML plus its shared assets.
    journeys_per_session_range: Tuple[int, int] = (1, 2)   # journeys per login
    include_introspection: bool = True     # occasionally hit /whoami etc.
    introspection_chance: float = 0.35     # per session
    random_seed: Optional[int] = None

    # --- Cacheable-ratio shaping ------------------------------------------
    cacheable_ratio_target: Optional[float] = 0.55         # midpoint of 51-60%
    cacheable_ratio_band: Tuple[float, float] = (0.51, 0.60)
    cacheable_exts: Tuple[str, ...] = (
        ".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
        ".woff", ".woff2", ".ttf", ".eot", ".map",
    )

    # --- Crawler ----------------------------------------------------------
    crawl_max_pages: int = 60
    crawl_max_depth: int = 4
    dump_dir: Optional[str] = None
    request_timeout: float = 45.0
    user_agent: str = ("Mozilla/5.0 (Windows NT 10.0; rv:128.0) "
                       "Gecko/20100101 Firefox/128.0")

    # --- Site map (from source): page -> shared assets it loads -----------
    page_assets: Dict[str, Tuple[str, ...]] = field(default_factory=lambda: {
        "/index.html":                 ("/css/style.css",),
        "/login.html":                 ("/css/style.css", "/js/auth.js"),
        "/dashboard.html":             ("/css/style.css", "/js/auth.js", "/js/dashboard.js"),
        "/transfer.html":              ("/css/style.css", "/js/auth.js", "/js/transfer.js"),
        "/transactions.html":          ("/css/style.css", "/js/auth.js"),
        "/services.html":              ("/css/style.css",),
        "/loans/index.html":           ("/loans/css/loans.css",),
        "/loans/home-loan.html":       ("/loans/css/loans.css",),
        "/loans/personal-loan.html":   ("/loans/css/loans.css",),
        "/loans/vehicle-loan.html":    ("/loans/css/loans.css",),
    })

    # Realistic user journeys (ordered page keys). "quick_demo" mirrors the
    # Quick Demo Login flow: land on login, then the dashboard, then browse.
    journeys: Dict[str, Tuple[str, ...]] = field(default_factory=lambda: {
        "quick_demo":      ("/login.html", "/dashboard.html", "/transactions.html"),
        "login_and_bank":  ("/index.html", "/login.html", "/dashboard.html",
                            "/transfer.html", "/transactions.html"),
        "dashboard_check": ("/index.html", "/login.html", "/dashboard.html"),
        "explore_site":    ("/index.html", "/services.html", "/loans/index.html",
                            "/loans/home-loan.html"),
        "loan_shopping":   ("/loans/index.html", "/loans/personal-loan.html",
                            "/loans/vehicle-loan.html", "/loans/home-loan.html"),
    })
    journey_weights: Dict[str, float] = field(default_factory=lambda: {
        "quick_demo": 3.0, "login_and_bank": 3.0, "dashboard_check": 2.0,
        "explore_site": 2.0, "loan_shopping": 1.5,
    })

    # nginx JSON introspection endpoints (no-store; never cached)
    introspection_endpoints: Tuple[str, ...] = (
        "/whoami", "/pod-info", "/origin-info", "/health",
    )

    # Static assets used by --check-cache and cacheable top-ups.
    static_assets: Tuple[str, ...] = (
        "/css/style.css", "/js/auth.js", "/js/dashboard.js",
        "/js/transfer.js", "/loans/css/loans.css",
    )


CONFIG = Config()
log = logging.getLogger("nexabank")


# ============================================================================
# Traffic shaping — cacheable (static) vs non-cacheable request ratio
# ============================================================================

def _same_origin(base: str, url: str) -> bool:
    a, b = urlparse(base), urlparse(url)
    return (a.scheme, a.netloc) == (b.scheme, b.netloc)


def _is_cacheable_url(cfg: Config, url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in cfg.cacheable_exts)


class TrafficShaper:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.target = cfg.cacheable_ratio_target or 0.0
        self.cacheable = 0
        self.dynamic = 0

    @property
    def total(self) -> int:
        return self.cacheable + self.dynamic

    def fraction(self) -> float:
        return self.cacheable / self.total if self.total else 0.0

    def record(self, url: str) -> None:
        if not _same_origin(self.cfg.base_url, url):
            return  # ignore Tor geo-check calls to ipinfo etc.
        if _is_cacheable_url(self.cfg, url):
            self.cacheable += 1
        else:
            self.dynamic += 1

    def want_cacheable(self) -> bool:
        if self.total == 0:
            return True
        return self.fraction() < self.target


class ShapedSession(requests.Session):
    shaper: Optional[TrafficShaper] = None

    def request(self, method, url, *args, **kwargs):
        resp = super().request(method, url, *args, **kwargs)
        if self.shaper is not None:
            try:
                self.shaper.record(resp.url if resp is not None else url)
            except Exception:
                pass
        return resp


# ============================================================================
# Tor transport
# ============================================================================

def build_session(cfg: Config, shaper: Optional[TrafficShaper] = None) -> requests.Session:
    s = ShapedSession()
    s.shaper = shaper
    proxy = f"socks5h://{cfg.socks_host}:{cfg.socks_port}"
    s.proxies = {"http": proxy, "https": proxy}
    s.headers.update({
        "User-Agent": cfg.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })
    return s


def _control_command(cfg: Config, commands: List[str]) -> bool:
    try:
        with socket.create_connection((cfg.control_host, cfg.control_port), timeout=10) as sock:
            def send(line: str) -> str:
                sock.sendall((line + "\r\n").encode())
                time.sleep(0.3)
                return sock.recv(4096).decode(errors="replace")
            resp = send(f'AUTHENTICATE "{cfg.control_password}"' if cfg.control_password
                        else "AUTHENTICATE")
            if "250" not in resp:
                log.warning("Tor control auth failed: %s", resp.strip())
                return False
            for c in commands:
                resp = send(c)
                if "250" not in resp:
                    log.warning("Tor control cmd '%s' -> %s", c, resp.strip())
                    return False
            send("QUIT")
            return True
    except OSError as e:
        log.warning("Tor control port unreachable (%s). Pin exits via torrc instead.", e)
        return False


def pin_exit_countries(cfg: Config) -> None:
    if not cfg.control_enabled:
        return
    countries = ",".join("{" + c + "}" for c in cfg.exit_countries)
    ok = _control_command(cfg, [f'SETCONF ExitNodes="{countries}"', 'SETCONF StrictNodes=1'])
    log.info("Exit-country pinning %s (%s)", "applied" if ok else "NOT applied", countries)


def new_circuit(cfg: Config) -> None:
    if not cfg.control_enabled:
        return
    if _control_command(cfg, ["SIGNAL NEWNYM"]):
        log.info("Requested new Tor circuit (NEWNYM)")
        time.sleep(5)


def check_exit_geo(cfg: Config, session: requests.Session) -> Optional[dict]:
    for url in ("https://ipinfo.io/json", "https://ifconfig.co/json"):
        try:
            r = session.get(url, timeout=cfg.request_timeout)
            if r.ok:
                data = r.json()
                return {"ip": data.get("ip") or data.get("ip_addr"),
                        "country": (data.get("country") or "").upper()}
        except Exception:
            continue
    return None


# ============================================================================
# Crawler / discovery
# ============================================================================

_QUOTED_PATH = re.compile(
    r"""["'`](?P<u>/[A-Za-z0-9_][A-Za-z0-9_\-./]*(?:\?[A-Za-z0-9_\-./=&%]*)?)["'`]""")
_INTERESTING = re.compile(r"(?:\.html\b|\.js\b|\.css\b|/whoami|/pod-info|/origin-info|/health|\?)",
                          re.IGNORECASE)


def _scan_endpoints(text: str, base: str, sink: set) -> None:
    for m in _QUOTED_PATH.finditer(text):
        path = m.group("u")
        if _INTERESTING.search(path):
            sink.add(urljoin(base, path))


def _dump_body(cfg: Config, url: str, text: str) -> None:
    if not cfg.dump_dir:
        return
    os.makedirs(cfg.dump_dir, exist_ok=True)
    p = urlparse(url)
    base = (p.path.strip("/").replace("/", "__") or "index") + (("__" + p.query) if p.query else "")
    base = re.sub(r"[^A-Za-z0-9_.=&#-]", "_", base)[:120]
    try:
        with open(os.path.join(cfg.dump_dir, f"{base}.{md5(url.encode()).hexdigest()[:6]}.txt"),
                  "w", encoding="utf-8", errors="replace") as fh:
            fh.write(f"// SOURCE: {url}\n")
            fh.write(text)
    except OSError as e:
        log.debug("dump failed for %s: %s", url, e)


@dataclass
class Discovery:
    pages: List[str] = field(default_factory=list)
    assets: set = field(default_factory=set)
    endpoints: set = field(default_factory=set)

    def as_dict(self) -> dict:
        return {"pages": sorted(set(self.pages)),
                "assets": sorted(self.assets),
                "endpoints": sorted(self.endpoints)}


def crawl(cfg: Config, session: requests.Session) -> Discovery:
    disc = Discovery()
    start = urljoin(cfg.base_url, cfg.entry_path)
    queue: List[Tuple[str, int]] = [(start, 0)]
    seen: set = set()
    log.info("Crawling from %s (max %d pages, depth %d)", start, cfg.crawl_max_pages, cfg.crawl_max_depth)

    while queue and len(disc.pages) < cfg.crawl_max_pages:
        url, depth = queue.pop(0)
        if url in seen or depth > cfg.crawl_max_depth:
            continue
        seen.add(url)
        try:
            r = session.get(url, timeout=cfg.request_timeout, allow_redirects=True)
        except Exception as e:
            log.debug("GET %s failed: %s", url, e)
            continue

        ctype = r.headers.get("Content-Type", "")
        disc.pages.append(url)
        log.info("  [%d] %s -> %s (%s)", depth, url, r.status_code, ctype.split(";")[0])
        _dump_body(cfg, url, r.text)
        if "html" not in ctype:
            continue

        soup = BeautifulSoup(r.text, "html.parser")
        _scan_endpoints(r.text, url, disc.endpoints)
        for tag, attr in (("a", "href"), ("script", "src"), ("link", "href"), ("img", "src")):
            for el in soup.find_all(tag):
                ref = el.get(attr)
                if not ref or ref.startswith("#"):
                    continue
                nxt = urljoin(url, ref)
                if not _same_origin(cfg.base_url, nxt):
                    continue
                if tag in ("script", "link", "img"):
                    disc.assets.add(nxt)
                    _dump_body_asset(cfg, session, nxt)
                elif tag == "a" and nxt not in seen and nxt.split("#")[0] not in seen:
                    queue.append((nxt.split("#")[0], depth + 1))
        time.sleep(random.uniform(0.8, 2.2))
    return disc


def _dump_body_asset(cfg: Config, session: requests.Session, url: str) -> None:
    if not cfg.dump_dir:
        return
    try:
        r = session.get(url, timeout=cfg.request_timeout)
        _dump_body(cfg, url, r.text)
    except Exception:
        pass


# ============================================================================
# Traffic actions — page-navigation journeys (no backend to POST to)
# ============================================================================

def visit_page(cfg: Config, session: requests.Session, page: str) -> None:
    """Fetch a page's HTML then its shared assets — one realistic page view."""
    url = urljoin(cfg.base_url, page)
    try:
        r = session.get(url, timeout=cfg.request_timeout)
        log.info("  visit %-26s -> HTTP %s", page, r.status_code)
    except Exception as e:
        log.debug("  visit %s failed: %s", page, e)
        return
    for asset in cfg.page_assets.get(page, ()):
        try:
            session.get(urljoin(cfg.base_url, asset), timeout=cfg.request_timeout)
        except Exception:
            pass
        time.sleep(random.uniform(0.2, 0.8))


def fetch_one_asset(cfg: Config, session: requests.Session) -> None:
    url = urljoin(cfg.base_url, random.choice(cfg.static_assets))
    try:
        session.get(url, timeout=cfg.request_timeout)
    except Exception:
        pass


def hit_introspection(cfg: Config, session: requests.Session) -> None:
    ep = random.choice(cfg.introspection_endpoints)
    url = urljoin(cfg.base_url, ep)
    try:
        r = session.get(url, timeout=cfg.request_timeout)
        log.info("  introspect %-14s -> HTTP %s", ep, r.status_code)
    except Exception as e:
        log.debug("  introspect %s failed: %s", ep, e)


def run_journey(cfg: Config, session: requests.Session, name: str) -> None:
    pages = cfg.journeys.get(name, ())
    label = "quick demo login" if name == "quick_demo" else name
    log.info("Journey '%s' (%d pages)", label, len(pages))
    for page in pages:
        visit_page(cfg, session, page)
        _nap(cfg)


def check_cache(cfg: Config, session: requests.Session) -> None:
    log.info("=== CDN cache check (through Tor) ===")
    any_cacheable = False
    for path in cfg.static_assets:
        url = urljoin(cfg.base_url, path)
        try:
            r1 = session.get(url, timeout=cfg.request_timeout)
            time.sleep(1.0)
            r2 = session.get(url, timeout=cfg.request_timeout)
        except Exception as e:
            log.info("  %s -> request failed: %s", path, e)
            continue
        cc = r2.headers.get("Cache-Control", "")
        exp = r2.headers.get("Expires", "")
        etag = "yes" if r2.headers.get("ETag") else "no"
        status = {h: r2.headers.get(h) for h in
                  ("x-cache", "cache-status", "x-cdn", "age", "via") if r2.headers.get(h)}
        cacheable = bool(cc and ("max-age" in cc.lower() or "public" in cc.lower())) or bool(exp)
        any_cacheable = any_cacheable or cacheable
        log.info("  %s  HTTP %s/%s  Cache-Control: %s  Expires: %s  ETag: %s",
                 path, r1.status_code, r2.status_code, cc or "(none)", exp or "(none)", etag)
        if status:
            log.info("      cache-status: %s", status)
    log.info("--- verdict ---")
    if not any_cacheable:
        log.info("Static assets carry NO Cache-Control/Expires (nginx sets none). F5 XC CDN")
        log.info("honors origin cache headers by default -> everything is a MISS. Fix: set a")
        log.info("default Cache TTL in the CDN cache rules, or add Cache-Control at nginx.")
    else:
        log.info("Some assets are cacheable per origin headers; if still MISS, check the cache")
        log.info("rule paths/query handling and that traffic actually traverses the CDN.")


# ============================================================================
# Session runner
# ============================================================================

def _pick_journey(cfg: Config) -> str:
    names = list(cfg.journey_weights)
    weights = [cfg.journey_weights[n] for n in names]
    return random.choices(names, weights=weights, k=1)[0]


def run_cycle(cfg: Config, cycle_no: int, shaper: Optional[TrafficShaper] = None) -> None:
    session = build_session(cfg, shaper=shaper)
    if cfg.new_circuit_each_cycle:
        new_circuit(cfg)
    if cfg.verify_exit_geo:
        geo = check_exit_geo(cfg, session)
        if geo:
            flag = " <-- US EXIT, geo rule may NOT trigger!" if geo["country"] in cfg.disallowed_exit_countries else ""
            log.info("Cycle %d Tor exit: %s (%s)%s", cycle_no, geo["ip"], geo["country"], flag)
        else:
            log.info("Cycle %d: could not determine Tor exit geo (continuing).", cycle_no)

    n_journeys = random.randint(*cfg.journeys_per_session_range)
    for _ in range(n_journeys):
        run_journey(cfg, session, _pick_journey(cfg))
        if cfg.include_introspection and random.random() < cfg.introspection_chance:
            hit_introspection(cfg, session)
            _nap(cfg)

    # Steer the cumulative cacheable ratio into the band.
    if shaper is not None:
        lo, hi = cfg.cacheable_ratio_band
        n = 0
        while shaper.fraction() < lo and n < 40:
            fetch_one_asset(cfg, session); n += 1
            time.sleep(random.uniform(0.2, 0.8))
        while shaper.fraction() > (cfg.cacheable_ratio_target or hi) and n < 40:
            hit_introspection(cfg, session); n += 1
            time.sleep(random.uniform(0.3, 1.0))
        log.info("Cycle %d -> cacheable %.1f%% (%d/%d requests, target %.0f%%)",
                 cycle_no, shaper.fraction() * 100, shaper.cacheable, shaper.total,
                 (cfg.cacheable_ratio_target or 0) * 100)


def _nap(cfg: Config) -> None:
    if cfg.rate_per_min and cfg.rate_per_min > 0:
        base = 60.0 / cfg.rate_per_min
        time.sleep(random.uniform(base * 0.6, base * 1.4))
    else:
        time.sleep(random.uniform(cfg.min_sleep, cfg.max_sleep))


# ============================================================================
# Main
# ============================================================================

def main() -> None:
    ap = argparse.ArgumentParser(description="NexaBank demo traffic + discovery harness")
    ap.add_argument("--crawl-only", action="store_true", help="discover pages/assets and exit")
    ap.add_argument("--check-cache", action="store_true", help="CDN cache diagnosis, then exit")
    ap.add_argument("--skip-crawl", action="store_true", help="skip discovery, go straight to traffic")
    ap.add_argument("--once", action="store_true", help="run a single session then exit")
    ap.add_argument("--base-url", help="override target base URL")
    ap.add_argument("--socks-host", help="override Tor SOCKS host (e.g. Windows host IP from WSL)")
    ap.add_argument("--socks-port", type=int, help="Tor SOCKS port (9150 bundle / 9050 daemon)")
    ap.add_argument("--rate", type=float, metavar="PER_MIN",
                    help="actions per minute (jittered +/-40%%); overrides sleep range")
    ap.add_argument("--min-sleep", type=float)
    ap.add_argument("--max-sleep", type=float)
    ap.add_argument("--cacheable-ratio", type=float, metavar="PCT",
                    help="target %% cacheable requests (e.g. 55). 0 disables shaping.")
    ap.add_argument("--seed", type=int, help="random seed for reproducible sessions")
    ap.add_argument("--dump-dir", help="save raw HTML/JS bodies here")
    ap.add_argument("--report", default="nexabank_discovery.json", help="discovery output file")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s  %(levelname)-7s %(message)s", datefmt="%H:%M:%S")

    if args.base_url:
        CONFIG.base_url = args.base_url.rstrip("/")
    if args.socks_host:
        CONFIG.socks_host = args.socks_host
    if args.socks_port:
        CONFIG.socks_port = args.socks_port
    if args.rate is not None:
        CONFIG.rate_per_min = args.rate
    if args.min_sleep is not None:
        CONFIG.min_sleep = args.min_sleep
    if args.max_sleep is not None:
        CONFIG.max_sleep = args.max_sleep
    if args.cacheable_ratio is not None:
        pct = args.cacheable_ratio
        pct = pct / 100.0 if pct > 1 else pct
        CONFIG.cacheable_ratio_target = pct if pct > 0 else None
    if args.seed is not None:
        random.seed(args.seed)
    if args.dump_dir:
        CONFIG.dump_dir = args.dump_dir

    pin_exit_countries(CONFIG)
    session = build_session(CONFIG)
    geo = check_exit_geo(CONFIG, session) if CONFIG.verify_exit_geo else None
    if geo:
        log.info("Startup Tor exit: %s (%s) via socks5h://%s:%d",
                 geo["ip"], geo["country"], CONFIG.socks_host, CONFIG.socks_port)
    else:
        log.warning("Could not reach the internet through Tor on %s:%d. Is Tor Browser open? "
                    "Try --socks-port 9050 for a system tor daemon.",
                    CONFIG.socks_host, CONFIG.socks_port)

    if args.check_cache:
        check_cache(CONFIG, session)
        return

    if not args.skip_crawl:
        disc = crawl(CONFIG, session)
        with open(args.report, "w") as fh:
            json.dump(disc.as_dict(), fh, indent=2)
        log.info("Discovery: %d pages, %d assets, %d endpoints -> %s",
                 len(set(disc.pages)), len(disc.assets), len(disc.endpoints), args.report)
    elif os.path.exists(args.report):
        log.info("Skipping crawl — reusing %s.", args.report)
    else:
        log.info("Skipping crawl — traffic uses built-in page map.")

    if args.crawl_only:
        return

    shaper = TrafficShaper(CONFIG) if CONFIG.cacheable_ratio_target else None
    if shaper:
        log.info("Traffic shaping ON: targeting %.0f%% cacheable (band %.0f-%.0f%%)",
                 CONFIG.cacheable_ratio_target * 100,
                 CONFIG.cacheable_ratio_band[0] * 100, CONFIG.cacheable_ratio_band[1] * 100)

    cycle = 0
    try:
        while True:
            cycle += 1
            log.info("===== session %d =====", cycle)
            run_cycle(CONFIG, cycle, shaper=shaper)
            if args.once:
                break
            time.sleep(random.uniform(CONFIG.cycle_sleep_min, CONFIG.cycle_sleep_max))
    except KeyboardInterrupt:
        log.info("Stopped by user after %d session(s).", cycle)
    if shaper:
        log.info("Final cacheable ratio: %.1f%% (%d cacheable / %d total origin requests)",
                 shaper.fraction() * 100, shaper.cacheable, shaper.total)


if __name__ == "__main__":
    main()
