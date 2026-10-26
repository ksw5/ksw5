"""Temporary read-only diagnostics for the live Duo Checker HTML (no alerts)."""
import json
import requests
from bs4 import BeautifulSoup

url = "https://duo-checker.on-forge.com/"
r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0 (compatible; DuoStockTester/1.0)"})
print("FETCH", r.status_code, r.url, "bytes", len(r.content), "type", r.headers.get("content-type"))
r.raise_for_status()
soup = BeautifulSoup(r.text, "html.parser")
print("TITLE", soup.title.get_text(" ", strip=True) if soup.title else "(none)")
print("TABLES", len(soup.select("table")), "ROWS", len(soup.select("tr")), "SCRIPTS", len(soup.select("script")))
for i, table in enumerate(soup.select("table")[:3]):
    print("TABLE", i, "attributes", dict(table.attrs))
    print(" HEADERS", [(x.get_text(" ", strip=True), dict(x.attrs)) for x in table.select("th")[:14]])
    for tr in table.select("tr")[:3]:
        print(" ROW", str(tr)[:1500])
for keyword in ("Crabtree Valley Mall", "Southpoint", "Friendly Center", "Lynnhaven Mall"):
    matches = soup.find_all(string=lambda x: x and keyword.casefold() in x.casefold())
    print("STORE_MATCH", keyword, len(matches))
    for item in matches[:2]:
        node = item.find_parent("tr") or item.find_parent("li") or item.parent
        print(" MARKUP", str(node)[:2200])
text = soup.get_text(" ", strip=True)
print("VISIBLE_TEXT_HEAD", text[:500])
print("JS_DATA_CONTAINERS", [x.get("id") for x in soup.select("script[id], [data-store-id], [data-availability]")[:15]])

from collections import Counter
classes = Counter()
positives = []
for tr in soup.select("tr[data-store]"):
    for cell in tr.select("td[data-color][data-storage]"):
        span = cell.select_one("span[title]")
        if not span:
            continue
        classes[" ".join(span.get("class", []))] += 1
        title = span.get("title", "")
        state = title.rsplit(":", 1)[-1].strip().lower()
        if state in ("available", "pickup available") or "sq-available" in span.get("class", []):
            a = tr.select_one("th a")
            positives.append({"store": a.get_text(" ", strip=True) if a else "?",
                              "url": a.get("href", "") if a else "",
                              "color": cell.get("data-color"), "storage": cell.get("data-storage"),
                              "state": state, "title": title,
                              "classes": span.get("class", [])})
print("STATUS_CLASSES", dict(classes))
print("ALL_POSITIVES", json.dumps(positives))
