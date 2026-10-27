"""Control test: Pro Max first, then Pro if no positive pickup was found."""
import json
from pathlib import Path
import pickup
pickup.COLORS = ['Burgundy','Silver','Glacier','Black']
pickup.SIZES = ['256GB']
def run_model(model,slug):
    pickup.MODEL=model
    pickup.URL='https://www.t-mobile.com/cell-phone/'+slug
    try:
        data=pickup.collect()
    except Exception as ex:
        data={'checked_at':pickup.now(),'results':[],'error':str(ex)[:1500]}
    for row in data['results']: row['product']=model
    return data
if __name__ == '__main__':
    data=run_model('iPhone 18 Pro Max','apple-iphone-18-pro-max')
    data['fallback_used']=not any(r['state']=='available' for r in data['results'])
    if data['fallback_used']:
        fallback=run_model('iPhone 18 Pro','apple-iphone-18-pro')
        data['results'].extend(fallback['results'])
        if fallback.get('error'): data['fallback_error']=fallback['error']
    data.update(checked_at=pickup.now(),product='iPhone 18 Pro Max / Pro control test',test_mode=True,source='automated_pickup_selector',scope='256GB in all four colors; 20 miles around 27889 and 28202',alerts_enabled=False)
    p=Path('data/tmobile-pro-max-test.json');p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(data,indent=2)+'\n')
