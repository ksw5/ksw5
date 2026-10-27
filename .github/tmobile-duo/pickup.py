"""Read-only T-Mobile pickup selector monitor. Never adds to cart or reserves stock."""
import json, os, re, time
from pathlib import Path
from datetime import datetime, timezone

MODEL = 'iPhone Duo'
URL = 'https://www.t-mobile.com/cell-phone/apple-iphone-duo'
AREAS = [('Eastern NC','Washington','27889'), ('Charlotte area','Charlotte','28202')]
COLORS = ['Star White','Night Sky']
SIZES = ['256GB','512GB','1TB','2TB']
NO_PICKUP = "The chosen item isn't available for pickup at stores within 20 miles"

def classify(text, options):
    if NO_PICKUP in text:
        return 'unavailable', []
    good = [o['text'] for o in options if o['enabled'] and re.search(r'\b(?:available for pickup|ready for pickup|pick up today|pickup today|in stock|hurry, only a few left)\b',o['text'],re.I) and not re.search(r'\b(?:not available|unavailable|out of stock)\b',o['text'],re.I)]
    return ('available', good) if good else ('unknown', [])

def now(): return datetime.now(timezone.utc).isoformat()

def settle(page):
    page.wait_for_timeout(1500)
    try: page.wait_for_load_state('networkidle',timeout=4000)
    except Exception: pass

def read_search(page, zipcode):
    dialog=page.get_by_role('dialog',name='Select a store for pickup')
    box=dialog.get_by_role('textbox',name='Search',exact=True)
    box.fill(zipcode)
    # Require a fresh result mutation after submission, not a previous ZIP's message.
    dialog.evaluate("e => {window.__pickupChanges=0; window.__pickupObserver?.disconnect(); window.__pickupObserver=new MutationObserver(m=>{if(m.some(x=>x.type==='childList'||x.type==='characterData'))window.__pickupChanges++}); window.__pickupObserver.observe(e,{subtree:true,childList:true,characterData:true});}")
    box.press('Enter')
    page.wait_for_function('window.__pickupChanges > 0',timeout=20000)
    page.wait_for_function("() => {const d=document.querySelector('[role=dialog][aria-label=\"Select a store for pickup\"]'); return d && (d.innerText.includes(\"The chosen item isn't available for pickup at stores within 20 miles\") || [...d.querySelectorAll('input[type=radio]')].some(e=>e.labels?.[0]?.innerText.includes('In Stock')||e.labels?.[0]?.innerText.includes('Hurry, only a few left')))}",timeout=30000)
    settle(page)
    text=dialog.inner_text()
    page.wait_for_timeout(1500)
    if text != dialog.inner_text():
        settle(page); text=dialog.inner_text()
    if box.input_value() != zipcode: raise ValueError('Search location did not remain selected')
    options=dialog.get_by_role('radio').evaluate_all("els=>els.map(e=>({text:e.getAttribute('aria-label')||e.labels?.[0]?.innerText||'',enabled:!e.disabled&&e.getAttribute('aria-disabled')!=='true'}))")
    state,stores=classify(text,options)
    return state,stores,text[:6000]

def dismiss_cookie_notice(page):
    """Close an ordinary consent notice through its visible controls."""
    for label in ('Reject All', 'Reject all cookies', 'Accept All Cookies', 'Confirm My Choices'):
        button = page.get_by_role('button', name=re.compile('^' + re.escape(label) + '$', re.I))
        if button.count() and button.first.is_visible():
            button.first.click()
            return
    close = page.locator('#onetrust-close-btn-container button:visible')
    if close.count():
        close.first.click()

def collect():
    from playwright.sync_api import sync_playwright
    results=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(locale='en-US')
        page.set_default_timeout(18000)
        blocked=False
        for color in COLORS:
            for size in SIZES:
                base={'color':color,'storage':size,'source':'pickup_selector','url':URL}
                error=None
                if not blocked:
                    try:
                        page.goto(URL,wait_until='domcontentloaded',timeout=45000)
                        settle(page)
                        dismiss_cookie_notice(page)
                        page.get_by_role('group',name='Device colors',exact=True).locator('label.color-swatch-card').filter(has_text=color).click()
                        settle(page)
                        choice=page.get_by_role('radiogroup',name='Storage and payments').get_by_role('radio',name=re.compile('^'+re.escape(size)+r'\b'))
                        if not choice.is_checked():
                            if not choice.is_enabled(): raise ValueError('Storage option disabled; pickup not checked for this configuration')
                            page.locator("label[for=\""+choice.get_attribute("id")+"\"]").click();settle(page)
                        alt=page.get_by_role('img',name=re.compile(r'^Apple '+re.escape(MODEL)+' - '+re.escape(color)+' - '+re.escape(size))).first.get_attribute('alt')
                        if not alt: raise ValueError('Selected configuration could not be verified')
                        page.locator('label[data-radiofieldid="BOPIS"]').click()
                        page.locator('[data-publish-event-topic="INITIATE_BOPIS_STORE_LOCATOR_MODAL"]:visible').click()
                    except Exception as ex:
                        body=page.locator('body').inner_text()[:3000]
                        if re.search(r'verify you are human|automated traffic|access denied|checking your browser',body,re.I): blocked=True
                        error=('Site blocked automated access' if blocked else str(ex)[:1500])
                else: error='Site blocked automated access; no further requests attempted'
                for region,city,zipcode in AREAS:
                    row={**base,'region':region,'city':city,'zip':zipcode,'radius_miles':20,'checked_at':now(),'state':'unknown','stores':[]}
                    if error: row['details']=error
                    else:
                        try:
                            state,stores,evidence=read_search(page,zipcode)
                            row.update(state=state,stores=stores,details=evidence)
                        except Exception as ex:
                            row['details']='Pickup search could not be verified: '+str(ex).split('Call log:')[0][:300]
                    results.append(row)
                    print(json.dumps({k:row[k] for k in ('color','storage','zip','state','details')}),flush=True)
        browser.close()
    return {'checked_at':now(),'source':'pickup_selector','results':results}


def update_alerts(data):
    """Alert only explicit, enabled pickup options; never alert unknown results."""
    if not os.environ.get('GITHUB_TOKEN'): return
    from check import github
    import hashlib
    label='tmobile-duo-pickup'
    rows=data.get('results',[])
    existing=github('GET',f'issues?labels={label}&state=open&per_page=100')
    keys={re.search(r'<!-- pickup:([^ ]+) -->',i.get('body') or '').group(1):i for i in existing if re.search(r'<!-- pickup:([^ ]+) -->',i.get('body') or '')}
    positives=[]
    for row in rows:
        prefix=row['zip']+'-'+row['color'].replace(' ','_')+'-'+row['storage']
        if row['state']=='unavailable':
            for key,issue in keys.items():
                if key.startswith(prefix+'-'): github('PATCH',f"issues/{issue['number']}",json={'state':'closed'})
        if row['state']=='available':
            for store in row['stores']:
                key=prefix+'-'+hashlib.sha256(store.encode()).hexdigest()[:12]
                if key not in keys: positives.append((key,row,store))
    if not positives: return
    try: github('POST','labels',json={'name':label,'color':'168361','description':'Configuration-specific T-Mobile pickup selector alerts'})
    except Exception as ex:
        if getattr(getattr(ex,'response',None),'status_code',None)!=422: raise
    for key,row,store in positives:
        github('POST','issues',json={'title':f"Pickup reported: iPhone Duo {row['color']} {row['storage']} near {row['city']}", 'body':f"<!-- pickup:{key} -->\nT-Mobile's pickup selector reported an enabled pickup option.\n\n{store}\n\nConfiguration: {row['color']} {row['storage']}\nSearch: {row['zip']} (20 miles)\nChecked: {row['checked_at']}\n\nVerify and reserve on {URL}. This check does not reserve inventory.", 'labels':[label], 'assignees':[os.environ['GITHUB_REPOSITORY'].split('/')[0]]})

if __name__=='__main__':
    target=Path('data/tmobile-pickup.json');target.parent.mkdir(exist_ok=True)
    try: data=collect()
    except Exception as ex:
        data={'checked_at':now(),'source':'pickup_selector','error':str(ex)[:300],'results':[]}
    target.write_text(json.dumps(data,indent=2)+'\n')
    update_alerts(data)
