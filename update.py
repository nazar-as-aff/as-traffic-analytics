"""
AS Talent Agency — Traffic Meta Auto-Update
Runs via GitHub Actions on a schedule.
Fetches OF API data for all Smart Links and updates index.html in this repo.
Netlify is connected to this repo via Continuous Deployment, so a git push
to main automatically triggers a new deploy. This script does NOT call the
Netlify API directly anymore — committing index.html is enough.
"""

import os
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

# ── CONFIG ─────────────────────────────────────────────────────────────────
OF_API_KEY = os.environ["OF_API_KEY"]

SMART_LINKS = [
    # ── Yuriy (YR) ──────────────────────────────────────────────
    {"id": "01KW9BHKKESX6F9STJGD5B4NJX", "model": "Octocuro",     "con": "YR", "color": "#7c3aed", "startDate": "2026-07-02", "offer": "Free Trial"},
    {"id": "01KX3RM06SKCY288Q50JAWQSG4", "model": "E.Momota", "con": "YR", "color": "#e879a9", "startDate": "2026-07-08", "offer": "Free Trial"},
    # ── Traffic Devils (TD) ─────────────────────────────────────
    {"id": "01KSPXD1G50JJQ6XYRPR1FD5GN", "model": "Octokura",      "con": "TD", "color": "#0ea5e9", "startDate": "2026-05-29", "offer": "Free Trial"},
    {"id": "01KT4EBCJW9Z7T73718FWF1GNS", "model": "Nancy Ace",     "con": "TD", "color": "#f59e0b", "startDate": "2026-06-02", "offer": "Free Trial"},
    {"id": "01KT736WE764G4R2JMXQEYHHXD", "model": "Ellie Bird",    "con": "TD", "color": "#8b5cf6", "startDate": "2026-06-03", "offer": "Free Trial"},
    {"id": "01KTXGC29Y0KVDMDWJDYTA5KW7", "model": "Emiri Momota",  "con": "TD", "color": "#14b8a6", "startDate": "2026-06-12", "offer": "Free Trial"},
    {"id": "01KVSVDP1HEK77R67350QFA4GS", "model": "Emiri Momota",  "con": "TD", "color": "#65a30d", "startDate": "2026-06-23", "offer": "Tracking Link"},
    {"id": "01KTBSPQBQVM77HR203WHWXZB7", "model": "Chloe Temple",  "con": "VL", "color": "#ec4899", "startDate": "2026-06-05", "offer": "Free Trial"},
    {"id": "01KTBS3785SXY0E748E84XFQP7", "model": "Jennifer White","con": "VL", "color": "#f97316", "startDate": "2026-06-05", "offer": "Free Trial"},
    {"id": "01KTBQYWGAVZ1EAP0ABZE9V784", "model": "Amanda Essen",  "con": "VL", "color": "#10b981", "startDate": "2026-06-05", "offer": "Free Trial"},
    {"id": "01KTBQV7R1AAMDWY0NEQ7VC9CM", "model": "Ellie Bird",    "con": "VL", "color": "#8b5cf6", "startDate": "2026-06-05", "offer": "Free Trial"},
    {"id": "01KT47TPJJBK10C1WKH36H91X6", "model": "Nancy Ace",    "con": "VL", "color": "#f59e0b", "startDate": "2026-06-03", "offer": "Free Trial"},
    {"id": "01KX14VNRVBHW5KRPVDD7G4K1X", "model": "E.Momota s1", "con": "TD", "color": "#f43f5e", "startDate": "2026-07-09", "offer": "Free Trial"},
    # ── Ocean Lead (OL) ─────────────────────────────────────────
    {"id": "01KW9Q2FDB4BCWHMKANRJHQ5J7", "model": "E.Momota", "con": "OL", "color": "#e879a9", "startDate": "2026-07-02", "offer": "Free Trial"},
    {"id": "01KW9S98BTQQPYC47G4AFXGFEV", "model": "Octocuro",     "con": "OL", "color": "#0891b2", "startDate": "2026-07-02", "offer": "Free Trial"},
]

GEO = {}   # populated live below from the same 30-day click data used for Fraud Detection
DEVS = {}  # populated live below from the same 30-day click data used for Fraud Detection

MSGS3 = {
    "01KW9BHKKESX6F9STJGD5B4NJX": 0,   # Octocuro (YR)
    "01KX3RM06SKCY288Q50JAWQSG4": 0,   # E.Momota (YR)
    "01KX14VNRVBHW5KRPVDD7G4K1X": 0,   # E.Momota s1 (TD) — new
    "01KW9Q2FDB4BCWHMKANRJHQ5J7": 0,   # Emira Momota (OL) — new
    "01KW9S98BTQQPYC47G4AFXGFEV": 0,   # Octocuro (OL) — new
    "01KSPXD1G50JJQ6XYRPR1FD5GN": 17, "01KT4EBCJW9Z7T73718FWF1GNS": 8,
    "01KT736WE764G4R2JMXQEYHHXD": 1,  "01KTXGC29Y0KVDMDWJDYTA5KW7": 1,
    "01KTBSPQBQVM77HR203WHWXZB7": 7,  "01KTBS3785SXY0E748E84XFQP7": 11,
    "01KTBQYWGAVZ1EAP0ABZE9V784": 14, "01KTBQV7R1AAMDWY0NEQ7VC9CM": 15,
    "01KT47TPJJBK10C1WKH36H91X6": 8,
}

# ── FRAUD DETECTION CONFIG ───────────────────────────────────────────────────
FRAUD_LOOKBACK_DAYS = 30   # rolling window for bot-rate stats & click log (not all-time)
FRAUD_MAX_PAGES_PER_LINK = 100  # safety cap: 100 * 100 = 10,000 clicks/link max per run
FRAUD_LOG_PER_LINK = 30    # most recent rows per link kept for the detail click log
FRAUD_LOG_MAX_TOTAL = 250  # total rows kept in the click log across all links (keeps file size sane)

# ── FETCH OF API ────────────────────────────────────────────────────────────
API_RETRY_ATTEMPTS = 3        # total tries per request before giving up
API_RETRY_BACKOFF = 2         # seconds; doubles each retry (2s, 4s, 8s...)

def api_get(url):
    last_err = None
    for attempt in range(1, API_RETRY_ATTEMPTS + 1):
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {OF_API_KEY}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            last_err = e
            # Only retry on transient server-side errors (5xx). 4xx (bad request,
            # unauthorized, not found) won't fix themselves — fail immediately.
            if e.code >= 500 and attempt < API_RETRY_ATTEMPTS:
                wait = API_RETRY_BACKOFF * (2 ** (attempt - 1))
                print(f"    retry {attempt}/{API_RETRY_ATTEMPTS} after HTTP {e.code}, waiting {wait}s...")
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            if attempt < API_RETRY_ATTEMPTS:
                wait = API_RETRY_BACKOFF * (2 ** (attempt - 1))
                print(f"    retry {attempt}/{API_RETRY_ATTEMPTS} after {e}, waiting {wait}s...")
                time.sleep(wait)
                continue
            raise
    raise last_err

now_utc = datetime.now(timezone.utc)
date_str = now_utc.strftime("%d.%m.%Y, %H:%M UTC")  # e.g. "22.06.2026, 14:32 UTC"
iso_str = now_utc.strftime("%Y-%m-%dT%H:%M:00Z")
fraud_since = (now_utc - timedelta(days=FRAUD_LOOKBACK_DAYS)).strftime("%Y-%m-%d")

def classify_bot(row):
    """Classify a bot click into a subtype based on browser_name/family/user_agent."""
    name = (row.get("browser_name") or "").lower()
    family = (row.get("browser_family") or "").lower()
    ua = (row.get("user_agent") or "").lower()
    if "facebook" in name or "facebook" in family:
        return "fb"
    if "telegram" in name or "telegram" in ua:
        return "tg"
    if "crawler" in name or "crawler" in family or "meta-externalads" in ua:
        return "meta"
    return "other"

def fmt_click_time(iso):
    try:
        return iso.replace("T", " ")[:16]
    except Exception:
        return iso

def fetch_clicks(link_id):
    """Paginate through listSmartLinkClicks for the rolling fraud window."""
    rows = []
    offset = 0
    hit_cap = True
    for _ in range(FRAUD_MAX_PAGES_PER_LINK):
        url = (
            f"https://app.onlyfansapi.com/api/smart-links/{link_id}/clicks"
            f"?date_start={fraud_since}&limit=100&offset={offset}"
            f"&include_bots=true&include_duplicates=true"
        )
        data = api_get(url)
        page_rows = data["data"]["rows"]
        rows.extend(page_rows)
        if len(page_rows) < 100:
            hit_cap = False
            break
        offset += 100
    if hit_cap:
        print(f"  FRAUD WARNING: link {link_id} hit the {FRAUD_MAX_PAGES_PER_LINK}-page cap "
              f"({len(rows)} clicks) — true volume may be higher, bot-rate stats are a lower bound.")
    return rows

DEVICE_COLORS = {"Mobile": "#1570ef", "Bot": "#f04438", "Desktop": "#10b981", "Tablet": "#f59e0b", "Other": "#98a2b3"}

def aggregate_geo(clicks, top_n=4):
    """Country breakdown of clicks -> [{c, n, s%}], top N + 'Other' bucket, sorted desc."""
    counts = {}
    for c in clicks:
        cc = c.get("country_code") or "Other"
        counts[cc] = counts.get(cc, 0) + 1
    total = sum(counts.values())
    if not total:
        return []
    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    top = ordered[:top_n]
    rest = ordered[top_n:]
    result = [{"c": cc, "n": n, "s": round(n / total * 100, 1)} for cc, n in top]
    if rest:
        rest_n = sum(n for _, n in rest)
        result.append({"c": "Other", "n": rest_n, "s": round(rest_n / total * 100, 1)})
    return result

def aggregate_devices(clicks):
    """Device-type breakdown of clicks -> [{d, n, s%, cl}], sorted desc."""
    counts = {}
    for c in clicks:
        dt = c.get("browser_device_type") or "Other"
        counts[dt] = counts.get(dt, 0) + 1
    total = sum(counts.values())
    if not total:
        return []
    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return [
        {"d": dt, "n": n, "s": round(n / total * 100, 1), "cl": DEVICE_COLORS.get(dt, "#98a2b3")}
        for dt, n in ordered
    ]

print(f"[{now_utc.isoformat()}] Fetching {len(SMART_LINKS)} Smart Links...")

td_links = []
vl_links = []
yr_links = []
ol_links = []
errors = []
fstats_list = []
fclicks_list = []

for lnk in SMART_LINKS:
    # ── FRAUD DETECTION + live geo/device aggregation (runs first: entry below needs the result) ──
    live_geo, live_devs = [], []
    try:
        clicks = fetch_clicks(lnk["id"])
        total = len(clicks)
        bots = sum(1 for c in clicks if c.get("is_bot"))
        real = total - bots
        tg = fb = meta = other_bot = 0
        for c in clicks:
            if not c.get("is_bot"):
                continue
            cls = classify_bot(c)
            if cls == "fb": fb += 1
            elif cls == "tg": tg += 1
            elif cls == "meta": meta += 1
            else: other_bot += 1
        fstats_list.append({
            "model": lnk["model"], "con": lnk["con"], "color": lnk["color"],
            "total": total, "bots": bots, "tgBot": tg, "fbBot": fb,
            "metaCrl": meta, "otherBot": other_bot, "real": real,
        })
        bot_pct = round(bots / total * 100) if total else 0
        print(f"  FRAUD {lnk['model']}: {total} clicks in last {FRAUD_LOOKBACK_DAYS}d, {bots} bots ({bot_pct}%)")

        # live geo/device breakdown — same 30-day click data, no extra API calls
        live_geo = aggregate_geo(clicks)
        live_devs = aggregate_devices(clicks)

        # most recent rows for the detail log (API returns newest-first)
        for c in clicks[:FRAUD_LOG_PER_LINK]:
            fclicks_list.append({
                "t": fmt_click_time(c.get("created_at", "")),
                "con": lnk["con"],
                "model": lnk["model"],
                "lid": lnk["id"],
                "ip": c.get("ip_address") or "—",
                "ua": c.get("user_agent") or c.get("browser_name") or "Unknown",
                "id": c.get("id", ""),
                "country": c.get("country_code") or "Other",
                "device": c.get("browser_device_type") or "Other",
                "gross": c.get("gross_clicks", 1),
                "bot": bool(c.get("is_bot")),
            })
    except Exception as e:
        print(f"  FRAUD ERR {lnk['model']}: {e}")
    GEO[lnk["id"]] = live_geo
    DEVS[lnk["id"]] = live_devs

    try:
        url = f"https://app.onlyfansapi.com/api/smart-links/{lnk['id']}/stats"
        data = api_get(url)
        s = data["data"]["summary"]
        daily_raw = data["data"].get("daily_metrics", [])
        daily = [
            {"d": d["timestamp"], "c": d["clicks"], "s": d["subs"], "sp": d["spenders"], "r": d["revenue"]}
            for d in daily_raw
            if d["clicks"] or d["subs"] or d["revenue"]
        ]
        entry = {
            "id": lnk["id"],
            "startDate": lnk["startDate"],
            "model": lnk["model"],
            "color": lnk["color"],
            "offer": lnk["offer"],
            "clicks": s["clicks_total"],
            "subs": s["subs_total"],
            "spenders": s["spenders_total"],
            "revenue": s["revenue_total"],
            "msgs3": MSGS3.get(lnk["id"], 0),
            "geo": GEO.get(lnk["id"], []),
            "devs": DEVS.get(lnk["id"], []),
            "daily": daily,
        }
        print(f"  OK {lnk['model']} ({lnk['con']}): {entry['clicks']} clicks / {entry['subs']} subs / ${entry['revenue']:.2f}")
        if lnk["con"] == "YR":
            yr_links.append(entry)
        elif lnk["con"] == "TD":
            td_links.append(entry)
        elif lnk["con"] == "VL":
            vl_links.append(entry)
        else:
            ol_links.append(entry)
    except Exception as e:
        print(f"  ERR {lnk['model']}: {e}")
        errors.append(lnk["model"])

if errors:
    print(f"WARNING: {len(errors)} link(s) failed: {', '.join(errors)}")

if not yr_links and not td_links and not vl_links and not ol_links:
    print("FATAL: no data fetched for any link. Aborting without touching index.html.")
    raise SystemExit(1)

# keep only the most recent N rows across all links, newest first
fclicks_list.sort(key=lambda r: r["t"], reverse=True)
fclicks_list = fclicks_list[:FRAUD_LOG_MAX_TOTAL]


# ── BUILD LINKS JS ──────────────────────────────────────────────────────────
def link_to_js(l):
    geo = json.dumps(l["geo"]).replace('"c"', 'c').replace('"n"', 'n').replace('"s"', 's')
    devs = json.dumps(l["devs"]).replace('"d"', 'd').replace('"n"', 'n').replace('"s"', 's').replace('"cl"', 'cl')
    daily = json.dumps(l["daily"]).replace('"d"', 'd').replace('"c"', 'c').replace('"s"', 's').replace('"sp"', 'sp').replace('"r"', 'r')
    return (
        f"    {{id:'{l['id']}',startDate:'{l['startDate']}',model:'{l['model']}',"
        f"color:'{l['color']}',offer:'{l['offer']}',clicks:{l['clicks']},subs:{l['subs']},"
        f"spenders:{l['spenders']},revenue:{l['revenue']},msgs3:{l['msgs3']},"
        f"geo:{geo},devs:{devs},daily:{daily}}}"
    )

links_js = "var LINKS = {\n  YR: [\n"
links_js += ",\n".join(link_to_js(l) for l in yr_links)
links_js += "\n  ],\n  OL: [\n"
links_js += ",\n".join(link_to_js(l) for l in ol_links)
links_js += "\n  ],\n  TD: [\n"
links_js += ",\n".join(link_to_js(l) for l in td_links)
links_js += "\n  ],\n  VL: [\n"
links_js += ",\n".join(link_to_js(l) for l in vl_links)
links_js += "\n  ]\n};"

def to_js_array(items, unquote_keys):
    """json.dumps an array of dicts, then strip quotes from known object keys
    so it matches the unquoted-key JS object literal style used elsewhere
    in this file (var LINKS, GEO, DEVS)."""
    s = json.dumps(items)
    for k in unquote_keys:
        s = re.sub(r'"%s":' % re.escape(k), '%s:' % k, s)
    return s

FSTATS_KEYS = ["model", "con", "color", "total", "bots", "tgBot", "fbBot", "metaCrl", "otherBot", "real"]
FCLICKS_KEYS = ["t", "con", "model", "lid", "ip", "ua", "id", "country", "device", "gross", "bot"]
fstats_js = to_js_array(fstats_list, FSTATS_KEYS)
fclicks_js = to_js_array(fclicks_list, FCLICKS_KEYS)

# ── UPDATE index.html ───────────────────────────────────────────────────────
with open("index.html", encoding="utf-8") as f:
    html = f.read()

html = re.sub(r'var LINKS = \{.*?\};\nvar ALL', links_js + '\nvar ALL', html, flags=re.DOTALL)
html = re.sub(r'var FSTATS=\[.*?\];', f'var FSTATS={fstats_js};', html, flags=re.DOTALL)
html = re.sub(r'var FCLICKS=\[.*?\];', f'var FCLICKS={fclicks_js};', html, flags=re.DOTALL)

# Update the visible date badge in the header — text + machine-readable UTC timestamp
html = re.sub(
    r'<span class="upd"[^>]*>[^<]*</span>',
    f'<span class="upd" data-utc="{iso_str}">{date_str}</span>',
    html,
)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"index.html updated successfully ({len(fclicks_list)} fraud log rows, {len(fstats_list)} model bot-stats). Netlify will redeploy automatically after git push.")
