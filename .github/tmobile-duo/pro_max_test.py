"""Control test for T-Mobile pickup, using the same collector as the Duo monitor."""
import json
from pathlib import Path
import pickup
pickup.MODEL = 'iPhone 18 Pro Max'
pickup.URL = 'https://www.t-mobile.com/cell-phone/apple-iphone-18-pro-max'
pickup.COLORS = ['Burgundy','Silver','Glacier','Black']
pickup.SIZES = ['256GB']
if __name__ == '__main__':
    try:
        data = pickup.collect()
    except Exception as ex:
        data = {'checked_at':pickup.now(),'results':[],'error':str(ex)[:1500]}
    data.update(product=pickup.MODEL,test_mode=True,source='automated_pickup_selector',scope='256GB in all four colors; 20 miles around 27889 and 28202',alerts_enabled=False)
    p=Path('data/tmobile-pro-max-test.json')
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(data,indent=2)+'\n')
