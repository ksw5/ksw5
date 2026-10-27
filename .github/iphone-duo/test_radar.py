import unittest,json
import radar
NOW=1800000000
class RadarTests(unittest.TestCase):
 def fixture(self):
  parts={f'p{s}{c}':[s,c,0] for s in ['256gb','512gb','1tb','2tb'] for c in ['nightsky','starwhite']}
  stores=[[str(i),n,'City'] for i,n in enumerate(radar.STORE_META)]
  return {'cc':'us','family':'iphoneduo','cf':{'parts':parts},'stores':stores,'snap':{'cc':'us','family':'iphoneduo','stores':{r[0]:{'c':NOW,'a':[]} for r in stores}}}
 def parse(self,d):
  return radar.parse_inventory('<script type="application/json" id="page-data">'+json.dumps(d)+'</script>',True,now=NOW)[0]
 def test_sold_out(self):
  rows=self.parse(self.fixture());self.assertEqual(len(rows),56);self.assertTrue(all(r['state']=='unavailable' for r in rows))
 def test_positive_exact_sku(self):
  d=self.fixture();d['snap']['stores']['0']['a']=[['p256gbnightsky',NOW]]
  yes=[r for r in self.parse(d) if r['state']=='available'];self.assertEqual(len(yes),1);self.assertEqual((yes[0]['color'],yes[0]['storage']),('Night Sky','256GB'))
 def test_stale_rejected(self):
  d=self.fixture();d['snap']['stores']['0']['c']=NOW-301
  with self.assertRaises(radar.ParseError):self.parse(d)
 def test_missing_store(self):
  d=self.fixture();d['stores'].pop()
  with self.assertRaises(radar.ParseError):self.parse(d)
 def test_wrong_model(self):
  d=self.fixture();d['family']='iphone18pro'
  with self.assertRaises(radar.ParseError):self.parse(d)
 def test_unknown_sku(self):
  d=self.fixture();d['snap']['stores']['0']['a']=[['bad',NOW]]
  with self.assertRaises(radar.ParseError):self.parse(d)
if __name__=='__main__':unittest.main()
