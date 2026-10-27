#!/usr/bin/env python3
"""Check T-Mobile's public store-level iPhone Duo stock flag, not checkout pickup inventory.

Only a product-specific page with an explicit "In stock" and "confirmed available
for purchase" is alertable. Exact SKU and pickup eligibility CANNOT be determined
from this page; alert titles and bodies say so. Read-only by default in --dry-run.
"""
import argparse
import json
from pathlib import Path
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
    ("Charlotte", "t-mobile-charlotte-nc-28262-9342"),
    ("Charlotte", "t-mobile-charlotte-nc-28273-198d"),
    ("Charlotte", "t-mobile-charlotte-nc-28213-2062"),
    ("Charlotte", "t-mobile-charlotte-nc-28209-145"),
    ("Charlotte", "t-mobile-charlotte-nc-28227-2286"),
    ("Charlotte", "t-mobile-charlotte-nc-28216-2rsb"),
    ("Charlotte", "t-mobile-charlotte-nc-28226-2911"),
    ("Charlotte", "t-mobile-charlotte-nc-28277-9352"),
    ("Concord", "t-mobile-concord-nc-28027-4382"),
    ("Concord", "t-mobile-concord-nc-28027-4021"),
    ("Washington", "t-mobile-washington-nc-27889-404f"),
    ("Greenville", "t-mobile-greenville-nc-27858-9422"),
    ("Williamston", "t-mobile-williamston-nc-27892-1u42"),
    ("New Bern", "t-mobile-new-bern-nc-28562-1u06"),
    ("Kinston", "t-mobile-kinston-nc-28504-2u52"),
    ("Rocky Mount", "t-mobile-rocky-mount-nc-27804-2smf"),
    ("Goldsboro", "t-mobile-goldsboro-nc-27534-9420"),
    ("Goldsboro", "t-mobile-goldsboro-nc-27530-468g"),
    ("Raleigh", "t-mobile-raleigh-nc-27612-9820"),
    ("Raleigh", "t-mobile-raleigh-nc-27609-9362"),
    ("Raleigh", "t-mobile-raleigh-nc-27617-4sfq"),
    ("Durham", "t-mobile-durham-nc-27713-2sme"),
    ("Greensboro", "t-mobile-greensboro-nc-27408-9408"),
    ("Jacksonville", "t-mobile-jacksonville-nc-28546-372g"),
    ("Wilmington", "t-mobile-wilmington-nc-28403-2smt"),
    ("Fayetteville", "t-mobile-fayetteville-nc-28314-9356"),
)
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

def issue_store_key(body):
    marker = re.search(r"<!-- tmobile-duo-key:([^ ]+) -->",body or "")
    return marker.group(1) if marker else None

def update_issues(known):
    """No spurious updates for unknown/failed/redirected/temporarily inaccessible stores."""
    existing = github("GET",f"issues?labels={LABEL}&state=open&per_page=100")
    existing = {key:issue for issue in existing
        if "pull_request" not in issue and (key := issue_store_key(issue.get("body"))) }
    good = {slug:result for slug,result in known.items() if result[0] == "available"}
    sold_out = {slug for slug,result in known.items() if result[0] == "unavailable"}
    for key,issue in existing.items():
        if key in sold_out:
            github("PATCH",f"issues/{issue['number']}",json={"state":"closed"})
            print(f"Closed T-Mobile stock alert #{issue['number']}: {key}")
    if not good:
        print("No new confirmed T-Mobile 'In stock' store pages.")
        return
    try:
        github("POST","labels",json={"name":LABEL,"color":"e20074",
            "description":"T-Mobile iPhone Duo in stock near Washington, NC"})
    except requests.HTTPError as ex:
        if ex.response.status_code != 422:  # label already exists
            raise
    owner = os.environ["GITHUB_REPOSITORY"].split("/")[0]
    for slug, (state,details,city,name,url) in good.items():
        if slug in existing:
            print(f"Already notified about {name}, {city}")
            continue
        checked = datetime.now(TZ).strftime("%b %d, %Y at %I:%M %p %Z")
        title = f"T-Mobile reports iPhone Duo in stock — {name}, {city}"
        body = "\n".join([
            f"<!-- tmobile-duo-key:{slug} -->",
            f"T-Mobile's public **store-level** iPhone Duo page reported **In stock** on {checked}.",
            f"- Store: **{name}**, {city}, NC",
            f"- Source: {url}",
            f"- Stock timestamp: {details}",
            "",
            "**Important:** This is the MODEL-LEVEL in-store indicator only. "
            "**Color, storage size and online in-store pickup eligibility are not confirmed.** "
            "Open the link, select your exact configuration, and verify the pickup option "
            "at checkout or call the store before traveling. Inventory may sell out.",
        ])
        issue=github("POST","issues",json={"title":title,"body":body,
            "labels":[LABEL],"assignees":[owner]})
        print(f"NEW T-MOBILE ALERT: {issue['html_url']}")


# Addresses verified from each canonical /stores/bd/ page on 2026-10-27.
STORE_META = {
  "t-mobile-charlotte-nc-28262-9342": {
    "name": "T-Mobile The Shoppes at Univ Place",
    "address": "8944 Jm Keynes Drive, Charlotte, NC, 28262"
  },
  "t-mobile-charlotte-nc-28273-198d": {
    "name": "T-Mobile S Tryon St & Steele Creek Rd",
    "address": "12820 S Tryon St, Charlotte, NC, 28273"
  },
  "t-mobile-charlotte-nc-28213-2062": {
    "name": "T-Mobile N Tryon & Lambeth Dr",
    "address": "5025 N Tryon St, Charlotte, NC, 28213"
  },
  "t-mobile-charlotte-nc-28209-145": {
    "name": "T-Mobile South & Woodlawn",
    "address": "4651 South Blvd, Charlotte, NC, 28209"
  },
  "t-mobile-charlotte-nc-28227-2286": {
    "name": "T-Mobile Albemarle Rd & Circ. Rd",
    "address": "9030 Albemarle Rd, Charlotte, NC, 28227"
  },
  "t-mobile-charlotte-nc-28216-2rsb": {
    "name": "T-Mobile Northlake Commons",
    "address": "9335 Center Lake Dr, Charlotte, NC, 28216"
  },
  "t-mobile-charlotte-nc-28226-2911": {
    "name": "T-Mobile Arboretum",
    "address": "3351 Pineville-matthews Rd, Charlotte, NC, 28226"
  },
  "t-mobile-charlotte-nc-28277-9352": {
    "name": "T-Mobile Shoppes at Ardrey Kell",
    "address": "16615 Lancaster Hwy, Charlotte, NC, 28277"
  },
  "t-mobile-concord-nc-28027-4382": {
    "name": "T-Mobile Concord Mills",
    "address": "8111 Concord Mills Blvd, Concord, NC, 28027"
  },
  "t-mobile-concord-nc-28027-4021": {
    "name": "T-Mobile Concord Mills Blvd & Thunder Rd Nw",
    "address": "8561 Concord Mills Blvd, Concord, NC, 28027"
  },
  "t-mobile-washington-nc-27889-404f": {
    "name": "T-Mobile Carolina Ave & W 15th St",
    "address": "1417 Carolina Ave, Washington, NC, 27889"
  },
  "t-mobile-greenville-nc-27858-9422": {
    "name": "T-Mobile Arlington Plaza",
    "address": "600-C SE Greenville Blvd, Greenville, NC, 27858"
  },
  "t-mobile-williamston-nc-27892-1u42": {
    "name": "T-Mobile Walmart Dr & Washington St",
    "address": "1067 Walmart Drive, Williamston, NC, 27892"
  },
  "t-mobile-new-bern-nc-28562-1u06": {
    "name": "T-Mobile Martin Luther King Jr Blvd & Lowes Blvd",
    "address": "3125 Martin Luther King Jr Blvd, New Bern, NC, 28562"
  },
  "t-mobile-kinston-nc-28504-2u52": {
    "name": "T-Mobile Westgate Plaza",
    "address": "4140 West Vernon Avenue, Kinston, NC, 28504"
  },
  "t-mobile-rocky-mount-nc-27804-2smf": {
    "name": "T-Mobile Cobb Corners Dr & Benvenue Rd",
    "address": "1243 Cobb Corners Dr, Rocky Mount, NC, 27804"
  },
  "t-mobile-goldsboro-nc-27534-9420": {
    "name": "T-Mobile Ashley Plaza",
    "address": "225 N Berkeley Blvd, Goldsboro, NC, 27534"
  },
  "t-mobile-goldsboro-nc-27530-468g": {
    "name": "T-Mobile Shoppes at Goldsboro",
    "address": "2912 US Hwy 70 W, Goldsboro, NC, 27530"
  },
  "t-mobile-raleigh-nc-27612-9820": {
    "name": "T-Mobile Crabtree Valley Mall",
    "address": "4325 Glenwood Ave, Raleigh, NC, 27612"
  },
  "t-mobile-raleigh-nc-27609-9362": {
    "name": "T-Mobile Creekside Crossing",
    "address": "424 East Six Forks Road, Raleigh, NC, 27609"
  },
  "t-mobile-raleigh-nc-27617-4sfq": {
    "name": "T-Mobile Brier Creek",
    "address": "7880 Alexander Promenade Pl, Raleigh, NC, 27617"
  },
  "t-mobile-durham-nc-27713-2sme": {
    "name": "T-Mobile Fayetteville Rd & E NC Hwy 54",
    "address": "6409 Fayetteville Rd, Durham, NC, 27713"
  },
  "t-mobile-greensboro-nc-27408-9408": {
    "name": "T-Mobile Pinedale Crossing",
    "address": "2511 Battleground Ave, Greensboro, NC, 27408"
  },
  "t-mobile-jacksonville-nc-28546-372g": {
    "name": "T-Mobile Western & Jacksonville Pkwy",
    "address": "1631 Western Blvd, Jacksonville, NC, 28546"
  },
  "t-mobile-wilmington-nc-28403-2smt": {
    "name": "T-Mobile Oleander Dr & Peachtree Ave",
    "address": "4401 Oleander Dr, Wilmington, NC, 28403"
  },
  "t-mobile-fayetteville-nc-28314-9356": {
    "name": "T-Mobile Skibo Rd & Chason Ridge Dr",
    "address": "2050 Skibo Rd, Fayetteville, NC, 28314"
  }
}
def store_metadata(html):
    soup=BeautifulSoup(html, "html.parser")
    def visit(obj):
        if isinstance(obj, list):
            for v in obj:
                found=visit(v)
                if found: return found
        if isinstance(obj, dict):
            address=obj.get("address")
            if isinstance(address, dict) and address.get("streetAddress"):
                return {"name": obj.get("name",""), "address": ", ".join(str(address.get(k,"")) for k in ("streetAddress","addressLocality","addressRegion","postalCode") if address.get(k))}
            for v in obj.values():
                if isinstance(v,(dict,list)):
                    found=visit(v)
                    if found: return found
        return None
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            found=visit(json.loads(script.string or script.get_text()))
            if found: return found
        except (ValueError,TypeError): pass
    return {}

def collect():
    known={}
    for i,(city,slug) in enumerate(SLUGS):
        if i: time.sleep(0.5)  # be polite to T-Mobile; only 16 pages/20min
        url=inventory_url(slug)
        try:
            resp=HTTP.get(url,timeout=18)
            resp.raise_for_status()
            if resp.url.rstrip('/') == url.rstrip('/'):
                STORE_META[slug] = store_metadata(resp.text) or STORE_META.get(slug,{})
            state,details=parse(resp.text,resp.url,url)
            if state=="unknown":
                print(f"UNKNOWN {city} {slug}: {details}")
            else:
                print(f"{state.upper()} {city} {slug}: {details}")
            name=STORE_META.get(slug,{}).get("name") or slug
            if state=="available":
                h1=BeautifulSoup(resp.text,"html.parser").find("h1")
                if h1: name=re.sub(r"^iPhone\s+Duo\s+at\s+T-Mobile\s*","",h1.get_text(" ",strip=True),flags=re.I)
            known[slug]=(state,details,city,name,url)
        except requests.RequestException as ex:
            print(f"UNKNOWN {city} {slug}: request error {type(ex).__name__}")
            known[slug]=("unknown",str(ex),city,STORE_META.get(slug,{}).get("name") or slug,url)
    return known

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dry-run",action="store_true")
    ap.add_argument("--output", help="Write a dashboard JSON snapshot")
    args=ap.parse_args()
    known=collect()
    if args.output:
        target=Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"checked_at": datetime.now(TZ).isoformat(), "zip": ZIP, "product": "iPhone Duo", "stores": [{"id": slug, "state": row[0], "details": row[1], "city": row[2], "name": row[3], "address": STORE_META.get(slug,{}).get("address",""), "url": row[4], "region": "Charlotte area" if row[2] in ("Charlotte", "Concord") else "Eastern NC", "pickup_confirmed": False} for slug,row in known.items()]}, indent=2) + "\n")
    print(f"Checked {len(SLUGS)} candidate T-Mobile stores near ZIP {ZIP}; "
          f"available={sum(x[0]=='available' for x in known.values())}, "
          f"unknown={sum(x[0]=='unknown' for x in known.values())}")
    if args.dry_run:
        print("DRY RUN: no GitHub issues will be created or modified")
    else:
        update_issues(known)

if __name__=="__main__":
    main()
