"""
AS Talent Agency — Traffic Meta Auto-Update
Runs via GitHub Actions on a schedule.
Fetches OF API data for all 9 Smart Links and updates index.html in this repo.
Netlify is connected to this repo via Continuous Deployment, so a git push
to main automatically triggers a new deploy. This script does NOT call the
Netlify API directly anymore — committing index.html is enough.
"""

import os
import json
import re
import urllib.request
from datetime import datetime, timezone

# ── CONFIG ─────────────────────────────────────────────────────────────────
OF_API_KEY = os.environ["OF_API_KEY"]

SMART_LINKS = [
    {"id": "01KSPXD1G50JJQ6XYRPR1FD5GN", "model": "Octokura",      "con": "TD", "color": "#0ea5e9", "startDate": "2026-05-29"},
    {"id": "01KT4EBCJW9Z7T73718FWF1GNS", "model": "Nancy Ace",     "con": "TD", "color": "#f59e0b", "startDate": "2026-06-02"},
    {"id": "01KT736WE764G4R2JMXQEYHHXD", "model": "Ellie Bird",    "con": "TD", "color": "#8b5cf6", "startDate": "2026-06-03"},
    {"id": "01KTXGC29Y0KVDMDWJDYTA5KW7", "model": "Emiri Momota",  "con": "TD", "color": "#14b8a6", "startDate": "2026-06-12"},
    {"id": "01KTBSPQBQVM77HR203WHWXZB7", "model": "Chloe Temple",  "con": "VL", "color": "#ec4899", "startDate": "2026-06-05"},
    {"id": "01KTBS3785SXY0E748E84XFQP7", "model": "Jennifer White","con": "VL", "color": "#f97316", "startDate": "2026-06-05"},
    {"id": "01KTBQYWGAVZ1EAP0ABZE9V784", "model": "Amanda Essen",  "con": "VL", "color": "#10b981", "startDate": "2026-06-05"},
    {"id": "01KTBQV7R1AAMDWY0NEQ7VC9CM", "model": "Ellie Bird",    "con": "VL", "color": "#8b5cf6", "startDate": "2026-06-05"},
    {"id": "01KT47TPJJBK10C1WKH36H91X6", "model": "Nancy Ace",    "con": "VL", "color": "#f59e0b", "startDate": "2026-06-03"},
]

GEO = {
    "01KSPXD1G50JJQ6XYRPR1FD5GN": [{"c":"US","n":39,"s":42.9},{"c":"GB","n":16,"s":17.6},{"c":"AU","n":15,"s":16.5},{"c":"FR","n":9,"s":9.9},{"c":"CA","n":6,"s":6.6},{"c":"Other","n":6,"s":6.6}],
    "01KT4EBCJW9Z7T73718FWF1GNS": [{"c":"US","n":28,"s":40.6},{"c":"GB","n":15,"s":21.7},{"c":"CA","n":12,"s":17.4},{"c":"AU","n":8,"s":11.6},{"c":"Other","n":6,"s":8.7}],
    "01KT736WE764G4R2JMXQEYHHXD": [{"c":"US","n":22,"s":37.3},{"c":"GB","n":14,"s":23.7},{"c":"CA","n":10,"s":16.9},{"c":"AU","n":7,"s":11.9},{"c":"Other","n":6,"s":10.2}],
    "01KTXGC29Y0KVDMDWJDYTA5KW7": [{"c":"US","n":40,"s":64.5},{"c":"UA","n":1,"s":1.6},{"c":"PL","n":1,"s":1.6},{"c":"Other","n":20,"s":32.3}],
    "01KTBSPQBQVM77HR203WHWXZB7": [{"c":"US","n":609,"s":52.5},{"c":"GB","n":321,"s":27.6},{"c":"CA","n":215,"s":18.5},{"c":"NL","n":3,"s":0.3},{"c":"Other","n":6,"s":0.5}],
    "01KTBS3785SXY0E748E84XFQP7": [{"c":"US","n":52,"s":38.2},{"c":"GB","n":42,"s":30.9},{"c":"CA","n":28,"s":20.6},{"c":"AU","n":12,"s":8.8},{"c":"Other","n":6,"s":1.5}],
    "01KTBQYWGAVZ1EAP0ABZE9V784": [{"c":"US","n":88,"s":50.3},{"c":"GB","n":42,"s":24.0},{"c":"CA","n":28,"s":16.0},{"c":"AU","n":12,"s":6.9},{"c":"Other","n":5,"s":2.9}],
    "01KTBQV7R1AAMDWY0NEQ7VC9CM": [{"c":"US","n":88,"s":50.3},{"c":"GB","n":42,"s":24.0},{"c":"CA","n":28,"s":16.0},{"c":"AU","n":12,"s":6.9},{"c":"Other","n":5,"s":2.9}],
    "01KT47TPJJBK10C1WKH36H91X6": [{"c":"US","n":30,"s":41.7},{"c":"GB","n":18,"s":25.0},{"c":"CA","n":14,"s":19.4},{"c":"AU","n":6,"s":8.3},{"c":"Other","n":4,"s":5.6}],
}

DEVS = {
    "01KSPXD1G50JJQ6XYRPR1FD5GN": [{"d":"Mobile","n":62,"s":68.1,"cl":"#1570ef"},{"d":"Bot","n":28,"s":30.8,"cl":"#f04438"},{"d":"Desktop","n":1,"s":1.1,"cl":"#10b981"}],
    "01KT4EBCJW9Z7T73718FWF1GNS": [{"d":"Mobile","n":52,"s":75.4,"cl":"#1570ef"},{"d":"Bot","n":15,"s":21.7,"cl":"#f04438"},{"d":"Desktop","n":2,"s":2.9,"cl":"#10b981"}],
    "01KT736WE764G4R2JMXQEYHHXD": [{"d":"Mobile","n":34,"s":68.0,"cl":"#1570ef"},{"d":"Bot","n":16,"s":32.0,"cl":"#f04438"}],
    "01KTXGC29Y0KVDMDWJDYTA5KW7": [{"d":"Mobile","n":2,"s":66.7,"cl":"#1570ef"},{"d":"Desktop","n":1,"s":33.3,"cl":"#10b981"}],
    "01KTBSPQBQVM77HR203WHWXZB7": [{"d":"Mobile","n":1466,"s":100,"cl":"#1570ef"}],
    "01KTBS3785SXY0E748E84XFQP7": [{"d":"Mobile","n":1800,"s":80.2,"cl":"#1570ef"},{"d":"Bot","n":400,"s":17.8,"cl":"#f04438"},{"d":"Desktop","n":44,"s":2.0,"cl":"#10b981"}],
    "01KTBQYWGAVZ1EAP0ABZE9V784": [{"d":"Mobile","n":148,"s":79.6,"cl":"#1570ef"},{"d":"Bot","n":32,"s":17.2,"cl":"#f04438"},{"d":"Desktop","n":6,"s":3.2,"cl":"#10b981"}],
    "01KTBQV7R1AAMDWY0NEQ7VC9CM": [{"d":"Mobile","n":136,"s":77.7,"cl":"#1570ef"},{"d":"Bot","n":35,"s":20.0,"cl":"#f04438"},{"d":"Desktop","n":4,"s":2.3,"cl":"#10b981"}],
    "01KT47TPJJBK10C1WKH36H91X6": [{"d":"Mobile","n":57,"s":79.2,"cl":"#1570ef"},{"d":"Bot","n":13,"s":18.1,"cl":"#f04438"},{"d":"Desktop","n":2,"s":2.8,"cl":"#10b981"}],
}

MSGS3 = {
    "01KSPXD1G50JJQ6XYRPR1FD5GN": 17, "01KT4EBCJW9Z7T73718FWF1GNS": 8,
    "01KT736WE764G4R2JMXQEYHHXD": 1,  "01KTXGC29Y0KVDMDWJDYTA5KW7": 1,
    "01KTBSPQBQVM77HR203WHWXZB7": 7,  "01KTBS3785SXY0E748E84XFQP7": 11,
    "01KTBQYWGAVZ1EAP0ABZE9V784": 14, "01KTBQV7R1AAMDWY0NEQ7VC9CM": 15,
    "01KT47TPJJBK10C1WKH36H91X6": 8,
}

# ── FETCH OF API ────────────────────────────────────────────────────────────
def api_get(url):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {OF_API_KEY}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

now_utc = datetime.now(timezone.utc)
date_str = now_utc.strftime("%B %-d, %Y")  # e.g. "June 19, 2026"

print(f"[{now_utc.isoformat()}] Fetching 9 Smart Links...")

td_links = []
vl_links = []
errors = []

for lnk in SMART_LINKS:
    try:
        url = f"https://app.onlyfansapi.com/api/smart-links/{lnk['id']}/stats"
        data = api_get(url)
        s = data["response"]["data"]["summary"]
        entry = {
            "id": lnk["id"],
            "startDate": lnk["startDate"],
            "model": lnk["model"],
            "color": lnk["color"],
            "clicks": s["clicks_total"],
            "subs": s["subs_total"],
            "spenders": s["spenders_total"],
            "revenue": s["revenue_total"],
            "msgs3": MSGS3.get(lnk["id"], 0),
            "geo": GEO.get(lnk["id"], []),
            "devs": DEVS.get(lnk["id"], []),
        }
        print(f"  OK {lnk['model']} ({lnk['con']}): {entry['clicks']} clicks / {entry['subs']} subs / ${entry['revenue']:.2f}")
        if lnk["con"] == "TD":
            td_links.append(entry)
        else:
            vl_links.append(entry)
    except Exception as e:
        print(f"  ERR {lnk['model']}: {e}")
        errors.append(lnk["model"])

if errors:
    print(f"WARNING: {len(errors)} link(s) failed: {', '.join(errors)}")

if not td_links and not vl_links:
    print("FATAL: no data fetched for any link. Aborting without touching index.html.")
    raise SystemExit(1)

# ── BUILD LINKS JS ──────────────────────────────────────────────────────────
def link_to_js(l):
    geo = json.dumps(l["geo"]).replace('"c"', 'c').replace('"n"', 'n').replace('"s"', 's')
    devs = json.dumps(l["devs"]).replace('"d"', 'd').replace('"n"', 'n').replace('"s"', 's').replace('"cl"', 'cl')
    return (
        f"    {{id:'{l['id']}',startDate:'{l['startDate']}',model:'{l['model']}',"
        f"color:'{l['color']}',clicks:{l['clicks']},subs:{l['subs']},"
        f"spenders:{l['spenders']},revenue:{l['revenue']},msgs3:{l['msgs3']},"
        f"geo:{geo},devs:{devs}}}"
    )

links_js = "var LINKS = {\n  TD: [\n"
links_js += ",\n".join(link_to_js(l) for l in td_links)
links_js += "\n  ],\n  VL: [\n"
links_js += ",\n".join(link_to_js(l) for l in vl_links)
links_js += "\n  ]\n};"

# ── UPDATE index.html ───────────────────────────────────────────────────────
with open("index.html", encoding="utf-8") as f:
    html = f.read()

html = re.sub(r'var LINKS = \{.*?\};\nvar ALL', links_js + '\nvar ALL', html, flags=re.DOTALL)

# Update the visible date badge in the header (works for both EN and older UA format)
html = re.sub(r'(June|May|July|April)\s+\d+,\s+2026\s*&middot;\s*4 TD \+ 5 VL',
              date_str + ' &middot; 4 TD + 5 VL', html)
html = re.sub(r'\d+\s+[а-яА-ЯіІ]+\s+2026\s*&middot;\s*4 TD \+ 5 VL',
              date_str + ' &middot; 4 TD + 5 VL', html)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("index.html updated successfully. Netlify will redeploy automatically after git push.")
