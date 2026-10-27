#!/usr/bin/env python3
"""Check T-Mobile's public store-level iPhone Duo stock flag, not checkout pickup inventory.

Only a product-specific page with an explicit "In stock" and "confirmed available
for purchase" is alertable. Exact SKU and pickup eligibility CANNOT be determined
from this page; alert titles and bodies say so. Read-only by default in --dry-run.
"""
import argparse
import re
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

LABEL = "tmobile-iphone-duo-stock"
SITE = "https://www.t-mobile.com"
ZIP = "27889"
TZ = ZoneInfo("America/New_York")
MAX_STATUS_AGE_DAYS = 7
# Specific T-Mobile public store pages independently located using T-Mobile's listings.
# A sample of stores around ZIP 27889, NOT complete 200-mile coverage.
SLUGS = (
    ("Greenville", "t-mobile-greenville-nc-27858-9422"),
    ("Williamston", "t-mobile-williamston-nc-27892-1u42"),
    ("Goldsboro", "t-mobile-goldsboro-nc-27534-9420"),
    ("Durham", "t-mobile-durham-nc-27713-2sme"),
    ("Greensboro", "t-mobile-greensboro-nc-27408-9408"),
    ("Fayetteville", "t-mobile-fayetteville-nc-28314-9356"),
)
DASHBOARD_ISSUE = 5
HTTP = requests.Session()
HTTP.headers.update({"User-Agent": "Mozilla/5.0 (compatible; iPhoneDuoPersonalMonitor/1.0)"})

def inventory_url(slug):
    return f"{SITE}/stores/pd/{slug}/apple-iphone-duo"

def parse(html, final_url, requested_url, now=None):
    """Return (state, details), where state is available/unavailable/unknown.

    The store URL must resolve to the intended iPhone Duo product page.
    Unknown observations are never treated as available (or confirmed sold out).
    """
    if final_url.rstrip("/") != requested_url.rstrip("/"):
        return "unknown", "Product page redirected; no reliable stock information."
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    if not h1 or not re.search(r"\biPhone\s+Duo\s+at\b",h1.get_text(" ",strip=True), re.I):
        return "unknown", "Not a verified iPhone Duo store product page."
    status = soup.select_one("#stock-description")
    details = soup.select_one("#stock-details")
    if not status or not details:
        return "unknown", "Missing product-stock indicators."
    status_text = status.get_text(" ",strip=True).casefold()
    details_text = details.get_text(" ",strip=True)
    if status_text == "in stock" and re.search(r"\bthis item is confirmed available for purchase\b",details_text, re.I):
        match = re.search(r"\bLast updated on\s+([A-Za-z]{3,9}\s+\d{1,2})\b", details_text, re.I)
        if not match:
            return "unknown", "In-stock label lacks last-updated date."
        now = now or datetime.now(TZ)
        day = match.group(1)
        parsed = None
        for fmt in ("%b %d %Y", "%B %d %Y"):
            try:
                parsed = datetime.strptime(f"{day} {now.year}",fmt).date()
                break
            except ValueError:
                pass
        if parsed is None:
            return "unknown", f"Cannot parse T-Mobile inventory date: {day!r}"
        if parsed > now.date():
            parsed = parsed.replace(year=parsed.year - 1)
        age = (now.date() - parsed).days
        if age > MAX_STATUS_AGE_DAYS:
            return "unknown", f"Stale inventory date ({day}, {age} days old)."
        return "available", f"T-Mobile says In stock; last updated {day} ({age} days ago)."
    if status_text in ("high demand", "out of stock", "unavailable", "sold out"):
        return "unavailable", f"T-Mobile says {status.get_text(' ', strip=True)}. {details_text[:120]}"
    return "unknown", f"Unrecognized inventory indicator: {status_text!r}."

def github(method,path,**kw):
    repo = os.environ["GITHUB_REPOSITORY"]
    resp = HTTP.request(method, f"https://api.github.com/repos/{repo}/{path}",
        timeout=25,headers={
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },**kw)
    resp.raise_for_status()
    return resp.json() if resp.content else {}

def collect():
    known={}
    for i,(city,slug) in enumerate(SLUGS):
        if i: time.sleep(0.5)  # be polite to T-Mobile; only 16 pages/20min
        url=inventory_url(slug)
        try:
            resp=HTTP.get(url,timeout=18)
            resp.raise_for_status()
            state,details=parse(resp.text,resp.url,url)
            if state=="unknown":
                print(f"UNKNOWN {city} {slug}: {details}")
            else:
                print(f"{state.upper()} {city} {slug}: {details}")
            name=slug
            if state=="available":
                h1=BeautifulSoup(resp.text,"html.parser").find("h1")
                if h1: name=re.sub(r"^iPhone\s+Duo\s+at\s+T-Mobile\s*","",h1.get_text(" ",strip=True),flags=re.I)
            known[slug]=(state,details,city,name,url)
        except requests.RequestException as ex:
            print(f"UNKNOWN {city} {slug}: request error {type(ex).__name__}")
            known[slug]=("unknown",str(ex),city,slug,url)
    return known

def main():
    import json
    ap=argparse.ArgumentParser()
    ap.add_argument("--dry-run",action="store_true")
    args=ap.parse_args()
    known=collect()
    checked=datetime.now(timezone.utc).isoformat(timespec="seconds")
    stores=[]
    for slug, (state,details,city,name,url) in known.items():
        stores.append({
            "id":slug, "city":city, "name":name, "url":url,
            "state":("listing_in_stock_unverified" if state=="available" else
                     "high_demand_unverified" if state=="unavailable" else "unknown"),
            "note":details, "pickup_verified":False,
            "checked_at":checked,
        })
    data={
        "source":"tmobile", "kind":"model_listing_not_pickup",
        "zipcode":"27889", "checked_at":checked,
        "check_interval_minutes":5, "pickup_confirmed":0, "stores":stores,
        "warning":"T-Mobile's public model-level In stock label does NOT confirm pickup at checkout. We do not notify based on it."
    }
    print("Listing-only results:", json.dumps([(x["city"],x["state"]) for x in stores]))
    if args.dry_run:
        print("DRY RUN: no writes and no stock alerts")
        return
    # Only publish display data. Never create an assigned stock notification.
    body = ("<!-- duo-dashboard-data -->\n<!-- JSON_START -->\n"+
            json.dumps(data,indent=2)+"\n<!-- JSON_END -->\n"+
            "Machine-readable status for the public stock dashboard, not pickup confirmation.")
    result=github("PATCH",f"issues/{DASHBOARD_ISSUE}",json={"body":body})
    print("Updated dashboard data issue #",result["number"])

if __name__=="__main__":
    main()
