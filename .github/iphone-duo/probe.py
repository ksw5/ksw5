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
