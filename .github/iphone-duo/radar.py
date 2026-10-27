#!/usr/bin/env python3
"""Check exact store/SKU pickup status from InStockRadar's server-rendered table."""
import argparse
import os
import json
from pathlib import Path
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

URL = "https://instockradar.com/us/iphone-duo"
LABEL = "iphone-duo-stock"
# Monitored physical Apple stores in the broad ~200-mile area of ZIP 27889.
# Store names verified against the live InStockRadar page on 2026-10-26.
NEARBY_STORES = {
    "Crabtree Valley Mall",      # Raleigh, NC
    "Southpoint",                # Durham, NC
    "Friendly Center",           # Greensboro, NC
    "Lynnhaven Mall",            # Virginia Beach, VA
    "Short Pump Town Center",    # Richmond, VA
}
STORE_META = {'Crabtree Valley Mall': ['4325 Glenwood Avenue, Raleigh, NC 27612', 'crabtreevalleymall'], 'Southpoint': ['8030 Renaissance Parkway, Durham, NC 27713', 'southpoint'], 'Friendly Center': ['3320 West Friendly Avenue, Greensboro, NC 27410', 'friendlycenter'], 'Lynnhaven Mall': ['701 Lynnhaven Parkway, Virginia Beach, VA 23452', 'lynnhavenmall'], 'Short Pump Town Center': ['11800 W. Broad Street, Richmond, VA 23233', 'shortpumptowncenter'], 'SouthPark': ['4400 Sharon Road, Charlotte, NC 28211', 'southpark'], 'Birkdale Village': ['8805 Townley Rd, Huntersville, NC 28078', 'birkdalevillage']}
NEARBY_STORES = set(STORE_META)
COLORS = {"night-sky": "Night Sky", "star-white": "Star White"}
STORAGE = {"256": "256GB", "512": "512GB", "1024": "1TB", "2048": "2TB"}
VALID_STATES = {"available", "unavailable", "pickup not offered", "unknown"}

class ParseError(RuntimeError):
    pass

def parse_inventory(html, include_all=False, now=None):
    """Read public page data; reject missing, stale or ambiguous inventory."""
    now = now or datetime.now(timezone.utc).timestamp()
    tag = BeautifulSoup(html, "html.parser").find("script", id="page-data", type="application/json")
    if not tag:
        raise ParseError("Missing InStockRadar public page data")
    data = json.loads(tag.string or tag.get_text())
    if data.get("family") != "iphoneduo" or data.get("cc") != "us":
        raise ParseError("Wrong product or country")
    snap = data["snap"]
    if snap.get("family") != "iphoneduo" or snap.get("cc") != "us":
        raise ParseError("Wrong snapshot product or country")
    parts = data["cf"]["parts"]
    colors = {"nightsky": ("Night Sky", "night-sky"), "starwhite": ("Star White", "star-white")}
    sizes = {"256gb": ("256GB", "256"), "512gb": ("512GB", "512"), "1tb": ("1TB", "1024"), "2tb": ("2TB", "2048")}
    if len(parts) != 8 or {(v[0],v[1]) for v in parts.values()} != {(s,c) for s in sizes for c in colors}:
        raise ParseError("Unexpected configurations")
    inventory = []
    seen = set()
    for row in data["stores"]:
        sid, name, city = row[:3]
        if name not in NEARBY_STORES:
            continue
        if name in seen:
            raise ParseError("Duplicate store")
        seen.add(name)
        observation = snap["stores"][sid]
        checked = observation["c"]
        if not isinstance(checked, (int, float)) or not -60 <= now - checked <= 300:
            raise ParseError(f"Stale source check for {name}; preserving previous results and alerts")
        entries = observation["a"]
        if not isinstance(entries, list) or any(not isinstance(e,list) or len(e)!=2 or e[0] not in parts for e in entries):
            raise ParseError("Invalid availability entries")
        available = {e[0] for e in entries}
        for part, config in parts.items():
            size, color = config[:2]
            state = "available" if part in available else "unavailable"
            if include_all or state == "available":
                inventory.append({"key": f"{sid}:{colors[color][1]}:{sizes[size][1]}",
                    "store": name, "city": city, "color": colors[color][0], "storage": sizes[size][0],
                    "state": state, "checked_at": datetime.fromtimestamp(checked,timezone.utc).isoformat(),
                    "url": "https://instockradar.com/us/iphone-duo#s-"+sid})
    if seen != NEARBY_STORES:
        raise ParseError("Missing monitored stores")
    return inventory, len(data["stores"])

def github(method, path, **kwargs):
    repo = os.environ["GITHUB_REPOSITORY"]
    r = requests.request(
        method, f"https://api.github.com/repos/{repo}/{path}",
        headers={
            "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=20, **kwargs)
    r.raise_for_status()
    return r.json() if r.content else {}

def synchronize_issues(current):
    """Open an issue for each new nearby available SKU; close after confirmed sellout."""
    open_issues = github("GET", f"issues?state=open&labels={LABEL}&per_page=100")
    open_by_key = {}
    for issue in open_issues:
        if "pull_request" in issue:
            continue
        body = issue.get("body") or ""
        for line in body.splitlines():
            if line.startswith("<!-- duo-stock-key:") and line.endswith(" -->"):
                key = line[len("<!-- duo-stock-key:"):-len(" -->")]
                open_by_key[key] = issue
                break
    by_key = {item["key"]: item for item in current}
    for key, issue in open_by_key.items():
        if key not in by_key:
            github("PATCH", f"issues/{issue['number']}", json={"state": "closed"})
            print(f"Closed sold-out issue #{issue['number']} for {key}")
    if not by_key:
        print("Verified 0 available monitored SKUs; no new notifications.")
        return
    try:
        github("POST", "labels", json={
            "name": LABEL, "color": "0969da",
            "description": "Available iPhone Duo Apple Store pickup near ZIP 27889"
        })
    except requests.HTTPError as exc:
        if exc.response.status_code != 422:  # already exists
            raise
    user = os.environ["GITHUB_REPOSITORY"].split("/")[0]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    for key, item in by_key.items():
        if key in open_by_key:
            print(f"Existing stock issue #{open_by_key[key]['number']}: {key}")
            continue
        title = f"iPhone Duo pickup: {item['color']} {item['storage']} at {item['store']}"
        body = "\n".join([
            f"<!-- duo-stock-key:{key} -->",
            f"**Potential Apple Store pickup stock detected at {now}.**",
            f"- Store: **{item['store']}**, {item['city']}",
            f"- Configuration: **{item['color']} {item['storage']}**",
            f"- [InStockRadar store page]({item['url']})",
            f"- [InStockRadar overview]({URL})",
            "",
            "Check Apple's website before traveling or attempting pickup. "
            "Third-party pickup availability may change at any time.",
        ])
        issue = github("POST", "issues", json={
            "title": title, "body": body, "labels": [LABEL], "assignees": [user]
        })
        print(f"NEW STOCK ALERT: {issue['html_url']}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Read the live website and print findings; never notify")
    parser.add_argument("--output")
    args = parser.parse_args()
    response = requests.get(URL, timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (compatible; DuoStockMonitor/1.0)"})
    response.raise_for_status()
    available, rows = parse_inventory(response.text)
    if args.output:
        all_items, _ = parse_inventory(response.text, include_all=True)
        stores = []
        for name, (address, slug) in STORE_META.items():
            stores.append({"name":name,"address":address,"region":"Charlotte area" if name in {"SouthPark","Birkdale Village"} else "Eastern NC & Virginia", "url":"https://www.apple.com/retail/"+slug+"/", "configurations":[x for x in all_items if x["store"]==name]})
        target=Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"checked_at":min(x["checked_at"] for x in all_items),"fetched_at":datetime.now(timezone.utc).isoformat(),"source":URL,"source_name":"InStockRadar","stores":stores},indent=2)+"\n")
    print(f"Verified HTML: {rows} store rows, {len(NEARBY_STORES)} monitored Apple stores")
    for item in available:
        print(f"IN STOCK: {item['store']}, {item['city']}: {item['color']} {item['storage']}")
    if args.dry_run:
        print("DRY RUN: notification writes disabled")
        return
    synchronize_issues(available)

if __name__ == "__main__":
    main()


