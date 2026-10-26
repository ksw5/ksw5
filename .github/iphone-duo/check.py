#!/usr/bin/env python3
"""Conservative, no-secrets iPhone Duo monitor; only alert on explicit inventory."""
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

URL = "https://duo-checker.on-forge.com/"
LABEL = "iphone-duo-stock"
# Candidate Apple stores to verify for ~200-mile coverage of ZIP 27889.
NEARBY_STORES = (
    "Crabtree Valley Mall", "Southpoint", "Streets at Southpoint",
    "Friendly Center", "Lynnhaven Mall", "MacArthur Center",
    "Short Pump Town Center", "Mayfaire",
)
PRODUCT_PATTERN = re.compile(r"iPhone\s*(?:Duo|17)", re.I)
AVAILABLE = re.compile(r"(?<!not )(?<!un)available\s*(?:for pickup|today|now)?|in stock|pickup available", re.I)
UNAVAILABLE = re.compile(r"unavailable|out of stock|sold out|no availability|not available", re.I)

def extract(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer"]):
        tag.decompose()
    lines = [re.sub(r"\s+", " ", s).strip() for s in soup.stripped_strings]
    # Fail closed: a listing must explicitly join a specific store with product and availability.
    matches = []
    for store in NEARBY_STORES:
        for i, line in enumerate(lines):
            if store.lower() not in line.lower():
                continue
            context = " ".join(lines[max(0, i - 3):min(len(lines), i + 12)])
            if PRODUCT_PATTERN.search(context) and AVAILABLE.search(context) and not UNAVAILABLE.search(context):
                matches.append((store, context[:350]))
    return list(dict.fromkeys(matches)), len(lines)

def github(method, path, **kwargs):
    repo = os.environ["GITHUB_REPOSITORY"]
    response = requests.request(method, f"https://api.github.com/repos/{repo}/{path}",
        headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"},
        timeout=20, **kwargs)
    response.raise_for_status()
    return response.json() if response.content else {}

def main():
    resp = requests.get(URL, timeout=30, headers={"User-Agent": "Mozilla/5.0 (compatible; StockMonitor/1.0)"})
    resp.raise_for_status()
    matches, count = extract(resp.text)
    print(f"Fetched {resp.url}; parsed {count} visible text elements; candidate stock matches: {len(matches)}")
    print("NOTE: zero matches means either out of stock OR unsupported site markup; do not assume verified sold out.")
    for store, context in matches:
        print(f"Found: {store}: {context[:180]}")
    if not count:
        print("No readable page data; fail closed without changing issue state.")
        return
    # An explicit match is required before any notification is sent.
    existing = github("GET", f"issues?state=open&labels={LABEL}&per_page=100")
    tracked = next((i for i in existing if i["title"].startswith("iPhone Duo stock near 27889")), None)
    if not matches:
        # Do not close on uncertain absence; could be client-rendered or temporarily unreachable.
        return
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body = f"Potential pickup stock detected at {now} by [Duo Checker]({URL}). VERIFY on Apple's official website before traveling.\n\n" + "\n".join(
        f"- **{store}** — {context}" for store, context in matches)
    if tracked:
        print(f"Existing open issue #{tracked['number']}; no duplicate alert.")
        return
    # Ensure issue label, then create assigned notification.
    try:
        github("POST", "labels", json={"name": LABEL, "color": "0969da", "description": "iPhone Duo stock monitor"})
    except requests.HTTPError as e:
        if e.response.status_code != 422:
            raise
    owner = os.environ["GITHUB_REPOSITORY"].split("/")[0]
    issue = github("POST", "issues", json={
        "title": "iPhone Duo stock near 27889 — verify now",
        "body": body,
        "labels": [LABEL],
        "assignees": [owner],
    })
    print(f"Created stock notification: {issue['html_url']}")

if __name__ == "__main__":
    main()
