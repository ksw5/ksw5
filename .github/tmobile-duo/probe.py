"""Read-only diagnostics for T-Mobile's public iPhone Duo store product pages."""
import re
import requests
from bs4 import BeautifulSoup

urls = {
    "Washington": "https://www.t-mobile.com/stores/pd/t-mobile-washington-nc-27889-404f/apple-iphone-duo",
    "Greenville": "https://www.t-mobile.com/stores/pd/t-mobile-greenville-nc-27858-9422/apple-iphone-duo",
    "Williamston": "https://www.t-mobile.com/stores/pd/t-mobile-williamston-nc-27892-1u42/apple-iphone-duo",
    "New Bern": "https://www.t-mobile.com/stores/pd/t-mobile-new-bern-nc-28562-1u06/apple-iphone-duo",
    "Durham": "https://www.t-mobile.com/stores/pd/t-mobile-durham-nc-27713-2sme/apple-iphone-duo",
    "NYC positive control": "https://www.t-mobile.com/stores/pd/t-mobile-new-york-ny-10017-3spl/apple-iphone-duo",
}
for city, url in urls.items():
    try:
        r = requests.get(url, timeout=14, headers={"User-Agent":"Mozilla/5.0 (compatible; TMobileStoreStockChecker/1.0)"})
        print("FETCH", city, r.status_code, len(r.content), r.url)
        if r.status_code != 200:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        heading = soup.find("h1")
        print("TITLE", city, soup.title.get_text(" ", strip=True)[:160] if soup.title else "", "H1",heading.get_text(" ", strip=True)[:100] if heading else "")
        text = soup.get_text(" ", strip=True)
        for pattern in ["This item is confirmed available", "Last updated on", "High demand", "Item may sell out quickly", "Pre-order Online or In-Store", "No In-Store Pickup"]:
            for m in list(re.finditer(re.escape(pattern), text, re.I))[:2]:
                print("STATE",city, pattern,repr(text[max(0,m.start()-90):m.end()+170]))
        for match in soup.find_all(string=re.compile(r"This item is confirmed available|Item may sell out quickly",re.I))[:3]:
            anc = match.parent
            print("MARKUP",city,str(anc.parent)[:2000])
    except Exception as exc:
        print("ERROR", city, type(exc).__name__, str(exc)[:250])
