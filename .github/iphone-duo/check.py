#!/usr/bin/env python3
"""Check exact store/SKU pickup status from Duo Checker's server-rendered table."""
import argparse
import os
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

URL = "https://duo-checker.on-forge.com/"
LABEL = "iphone-duo-stock"
# Monitored physical Apple stores in the broad ~200-mile area of ZIP 27889.
# Store names verified against the live Duo Checker page on 2026-10-26.
NEARBY_STORES = {
    "Crabtree Valley Mall",      # Raleigh, NC
    "Southpoint",                # Durham, NC
    "Friendly Center",           # Greensboro, NC
    "Lynnhaven Mall",            # Virginia Beach, VA
    "Short Pump Town Center",    # Richmond, VA
}
COLORS = {"night-sky": "Night Sky", "star-white": "Star White"}
STORAGE = {"256": "256GB", "512": "512GB", "1024": "1TB", "2048": "2TB"}
VALID_STATES = {"available", "unavailable", "pickup not offered", "unknown"}

class ParseError(RuntimeError):
    pass

def parse_inventory(html):
    """Return list of verified available local SKU entries; reject unexpected markup."""
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    if not heading or "iphone duo pickup availability" not in heading.get_text(" ", strip=True).lower():
        raise ParseError("Unexpected product/page heading. No notifications issued.")
    all_rows = soup.select("tr[data-store]")
    if len(all_rows) < 200:
        raise ParseError(f"Only {len(all_rows)} store rows; expected 200+. No notifications issued.")

    seen = set()
    available = []
    for row in all_rows:
        anchor = row.select_one('th[scope="row"] a[href]')
        if not anchor:
            raise ParseError("Store row missing link/name")
        store = anchor.get_text(" ", strip=True)
        if store not in NEARBY_STORES:
            continue
        if store in seen:
            raise ParseError(f"Duplicate nearby store {store}")
        seen.add(store)
        city_el = row.select_one('th[scope="row"] small')
        city = city_el.get_text(" ", strip=True) if city_el else ""
        cells = row.select("td[data-color][data-storage]")
        if len(cells) != len(COLORS) * len(STORAGE):
            raise ParseError(f"Unexpected SKU count for {store}: {len(cells)}")
        for cell in cells:
            color = cell.get("data-color")
            storage = cell.get("data-storage")
            if color not in COLORS or storage not in STORAGE:
                raise ParseError(f"Unexpected SKU identifiers in {store}: {color}/{storage}")
            indicator = cell.select_one("span[title]")
            if not indicator:
                raise ParseError(f"Missing availability indicator for {store}/{color}/{storage}")
            title = indicator.get("title", "")
            expected_title = f"{COLORS[color]} {STORAGE[storage]}:"
            if not title.startswith(expected_title):
                raise ParseError(f"Unexpected indicator title: {title!r}")
            state = title.partition(":")[2].strip().lower()
            if state not in VALID_STATES:
                raise ParseError(f"Unexpected status {state!r} at {store}")
            classes = set(indicator.get("class", []))
            if state == "available":
                if "sq-available" not in classes:
                    raise ParseError(f"Availability indicator class mismatch at {store}")
                available.append({
                    "key": f"{anchor['href'].rstrip('/').rsplit('/', 1)[-1]}:{color}:{storage}",
                    "store": store, "city": city,
                    "color": COLORS[color], "storage": STORAGE[storage],
                    "url": anchor["href"],
                })
            elif "sq-available" in classes:
                raise ParseError(f"Conflicting availability data at {store}")
    missing = NEARBY_STORES - seen
    if missing:
        raise ParseError(f"Missing target Apple stores: {', '.join(sorted(missing))}")
    return available, len(all_rows)

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
            f"- [Duo Checker store page]({item['url']})",
            f"- [Duo Checker overview]({URL})",
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
    args = parser.parse_args()
    response = requests.get(URL, timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (compatible; DuoStockMonitor/1.0)"})
    response.raise_for_status()
    available, rows = parse_inventory(response.text)
    print(f"Verified HTML: {rows} store rows, {len(NEARBY_STORES)} monitored Apple stores")
    for item in available:
        print(f"IN STOCK: {item['store']}, {item['city']}: {item['color']} {item['storage']}")
    if args.dry_run:
        print("DRY RUN: notification writes disabled")
        return
    synchronize_issues(available)

if __name__ == "__main__":
    main()
