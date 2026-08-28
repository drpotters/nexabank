# NexaBank demo traffic harness

Adapted from the Arcadia harness for **NexaBank**
(`https://nexabank.vt.f5-cloud-demo.com`). Same framework — Tor transport,
non-US exit routing for the Geo LB, rate control, per-session randomization,
cacheable-ratio shaping, crawler, and `--check-cache`. The **traffic model is
different** because NexaBank is built differently.

## Key finding: NexaBank is a 100% client-side static app

From the source (`github.com/drpotters/nexabank`):

- **"Quick Demo Login" is client-side only.** The button runs
  `completeLogin("DemoUser01")`, which writes a `sessionStorage` object and
  redirects to `dashboard.html`. **No server auth, no cookie, no login API.**
  Protected pages (`dashboard/transfer/transactions`) are gated only by an
  in-browser JS check — the server serves them as plain static files anyway.
- **Transfers, IFSC checks, dashboards are all faked in JavaScript**
  (`setTimeout` + DOM). There is **no backend API** to POST to.

So there are no transaction endpoints to drive. Realistic HTTP traffic here is
a user **navigating between static pages**, each pulling the shared CSS/JS —
i.e. mostly **cacheable static content**, which is ideal for the CDN/Geo demo.

## What the harness does

Each **session** picks one or two random **user journeys** and walks them page
by page; every page view fetches the HTML plus its shared assets:

| Journey | Pages |
|---------|-------|
| `quick_demo` | login → dashboard → transactions (mirrors Quick Demo Login) |
| `login_and_bank` | index → login → dashboard → transfer → transactions |
| `dashboard_check` | index → login → dashboard |
| `explore_site` | index → services → loans → home-loan |
| `loan_shopping` | loans → personal → vehicle → home-loan |

It also occasionally hits the nginx **introspection endpoints**
(`/whoami`, `/pod-info`, `/origin-info`, `/health`) — great for a multi-cloud
"which pod/node/platform served me" angle. These are `no-store` (never cached).

Journey/page mix, pacing, and the cacheable ratio are all tunable (below).

## Optional: Controlling where traffic originates
### Non-US (for the Geo LB rule)

Tor exits are mostly non-US already, and the harness **prints the exit
country each cycle** and warns if it lands in the US. To *pin* exits to
specific countries, edit the Tor Browser torrc:

```
# <Tor Browser>/Browser/TorBrowser/Data/Tor/torrc
ExitNodes {de},{nl},{fr},{gb},{se},{ch}
StrictNodes 1
```

```
# torrc alternate config
ExcludeExitNodes {us},{ru},{cn},{ir},{kp}
StrictNodes 1
```

### US-only (for US-based Geo LB rule)

```
# <Tor Browser>/Browser/TorBrowser/Data/Tor/torrc
EntryNodes {us}
ExitNodes {us}
StrictNodes 1
```

## Run it

```bash
pip install "requests[socks]" beautifulsoup4
# Tor Browser open (SOCKS 127.0.0.1:9150)

python3 nexabank_harness.py --crawl-only     # discover pages/assets -> nexabank_discovery.json
python3 nexabank_harness.py                  # crawl once, then loop sessions
python3 nexabank_harness.py --skip-crawl --rate 4
python3 nexabank_harness.py --check-cache    # CDN cache diagnosis
```

## Flags (same family as the Arcadia harness)

| Flag | Effect |
|------|--------|
| `--crawl-only` / `--skip-crawl` | discover only / skip discovery |
| `--check-cache` | fetch static assets twice, report cache headers, exit |
| `--once` | single session then exit |
| `--rate PER_MIN` | actions per minute (jittered ±40%) |
| `--min-sleep` / `--max-sleep` | seconds between actions (when `--rate` unset) |
| `--cacheable-ratio PCT` | target % cacheable requests (default 55; 0 = off) |
| `--seed N` | reproducible session sequence |
| `--socks-host` / `--socks-port` | Tor SOCKS location (9150 bundle / 9050 daemon) |
| `--base-url` | override target |
| `--dump-dir DIR` | save raw HTML/JS bodies |

## Cacheable ratio

On by default at **55%** (band 51–60%). Requests are classified by extension
(`.css/.js/...` = cacheable; `.html` and the JSON introspection endpoints =
non-cacheable). Each session tops up toward the target and a persistent counter
keeps the **cumulative** ratio in-band — simulated across 12 sessions it holds
52.8–55.0%.

## Same CDN caching caveat as Arcadia

NexaBank's nginx (`nginx/templates`) sets **no `Cache-Control` on static
assets** (only `no-store` on the introspection endpoints). With 1-click CDN
honoring origin headers, static assets won't cache until you either set a
default Cache TTL in the CDN cache rules or add `Cache-Control` at nginx. Run
`--check-cache` to confirm, then re-run to watch `Age`/HIT appear once caching
is enabled. (Full explanation in `CDN_CACHING.md`.)
