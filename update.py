"""
AS Talent Agency — Traffic Meta Auto-Update
Запускается GitHub Actions каждые 6 часов.
Дёргает OF API по всем 9 Smart Links → обновляет index.html на Netlify.
"""

import os
import json
import urllib.request
import urllib.error
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
OF_API_KEY    = os.environ["OF_API_KEY"]       # GitHub Secret
NETLIFY_TOKEN = os.environ["NETLIFY_TOKEN"]    # GitHub Secret
NETLIFY_SITE_ID = os.environ["NETLIFY_SITE_ID"] # GitHub Secret

SMART_LINKS = [
    # TD — Traffic Devils
    {"id": "01KSPXD1G50JJQ6XYRPR1FD5GN", "model": "Octokura",      "con": "TD", "color": "#0ea5e9", "startDate": "2026-05-29", "msgs3": 17},
    {"id": "01KT4EBCJW9Z7T73718FWF1GNS", "model": "Nancy Ace",     "con": "TD", "color": "#f59e0b", "startDate": "2026-06-02", "msgs3": 8},
    {"id": "01KT736WE764G4R2JMXQEYHHXD", "model": "Ellie Bird",    "con": "TD", "color": "#8b5cf6", "startDate": "2026-06-03", "msgs3": 1},
    {"id": "01KTXGC29Y0KVDMDWJDYTA5KW7", "model": "Emiri Momota",  "con": "TD", "color": "#14b8a6", "startDate": "2026-06-12", "msgs3": 1},
    # VL — Vasyl Lev
    {"id": "01KTBSPQBQVM77HR203WHWXZB7", "model": "Chloe Temple",  "con": "VL", "color": "#ec4899", "startDate": "2026-06-05", "msgs3": 7},
    {"id": "01KTBS3785SXY0E748E84XFQP7", "model": "Jennifer White","con": "VL", "color": "#f97316", "startDate": "2026-06-05", "msgs3": 11},
    {"id": "01KTBQYWGAVZ1EAP0ABZE9V784", "model": "Amanda Essen",  "con": "VL", "color": "#10b981", "startDate": "2026-06-05", "msgs3": 14},
    {"id": "01KTBQV7R1AAMDWY0NEQ7VC9CM", "model": "Ellie Bird",    "con": "VL", "color": "#8b5cf6", "startDate": "2026-06-05", "msgs3": 15},
    {"id": "01KT47TPJJBK10C1WKH36H91X6", "model": "Nancy Ace",    "con": "VL", "color": "#f59e0b", "startDate": "2026-06-03", "msgs3": 8},
]

# ── HELPERS ───────────────────────────────────────────────────────────────────
def api_get(url):
    req = urllib.request.Request(url, headers={"x-api-key": OF_API_KEY})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def fetch_link_stats(link_id):
    url = f"https://app.onlyfansapi.com/api/smart-links/{link_id}/stats"
    data = api_get(url)
    s = data["response"]["data"]["summary"]
    return {
        "clicks":   s["clicks_total"],
        "subs":     s["subs_total"],
        "revenue":  s["revenue_total"],
        "spenders": s["spenders_total"],
    }

# ── FETCH ALL ─────────────────────────────────────────────────────────────────
print(f"[{datetime.utcnow().isoformat()}] Fetching 9 Smart Links...")
results = []
for lnk in SMART_LINKS:
    try:
        stats = fetch_link_stats(lnk["id"])
        results.append({**lnk, **stats})
        print(f"  ✓ {lnk['model']} ({lnk['con']}): {stats['clicks']} clicks · {stats['subs']} subs · ${stats['revenue']:.2f}")
    except Exception as e:
        print(f"  ✗ {lnk['model']}: {e}")
        results.append({**lnk, "clicks": 0, "subs": 0, "revenue": 0, "spenders": 0})

# ── WRITE data.json ───────────────────────────────────────────────────────────
output = {
    "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    "links": results
}
with open("data.json", "w") as f:
    json.dump(output, f)
print("data.json written.")

# ── DEPLOY TO NETLIFY (Files API) ─────────────────────────────────────────────
# Read current index.html
with open("index.html", "rb") as f:
    html_bytes = f.read()

# Read data.json
with open("data.json", "rb") as f:
    json_bytes = f.read()

import hashlib

def sha1(b):
    return hashlib.sha1(b).hexdigest()

deploy_payload = json.dumps({
    "files": {
        "/index.html": sha1(html_bytes),
        "/data.json":  sha1(json_bytes),
    }
}).encode()

# 1. Create deploy
req = urllib.request.Request(
    f"https://api.netlify.com/api/v1/sites/{NETLIFY_SITE_ID}/deploys",
    data=deploy_payload,
    headers={
        "Authorization": f"Bearer {NETLIFY_TOKEN}",
        "Content-Type": "application/json",
    },
    method="POST"
)
with urllib.request.urlopen(req, timeout=30) as r:
    deploy = json.loads(r.read())

deploy_id = deploy["id"]
print(f"Deploy created: {deploy_id}")

# 2. Upload files
for path, content in [("/index.html", html_bytes), ("/data.json", json_bytes)]:
    req2 = urllib.request.Request(
        f"https://api.netlify.com/api/v1/deploys/{deploy_id}/files{path}",
        data=content,
        headers={
            "Authorization": f"Bearer {NETLIFY_TOKEN}",
            "Content-Type": "application/octet-stream",
        },
        method="PUT"
    )
    with urllib.request.urlopen(req2, timeout=60) as r:
        r.read()
    print(f"  Uploaded {path}")

print(f"\n✅ Done! Site updated: https://as-traffic-analytics.netlify.app")
