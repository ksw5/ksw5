import unittest
from pickup import classify, NO_PICKUP, validate_area
class PickupTests(unittest.TestCase):
    def test_negative(self): self.assertEqual(classify(NO_PICKUP,[])[0],'unavailable')
    def test_loading_is_unknown(self): self.assertEqual(classify('Pick up here',[])[0],'unknown')
    def test_shipping_not_pickup(self): self.assertEqual(classify('In stock. Shipping today.',[])[0],'unknown')
    def test_disabled_positive(self): self.assertEqual(classify('',[{'text':'Store A available for pickup','enabled':False}])[0],'unknown')
    def test_negative_option(self): self.assertEqual(classify('',[{'text':'Store A not available for pickup','enabled':True}])[0],'unknown')
    def test_live_store_label(self): self.assertEqual(classify('Search results available below.',[{'text':"The Shoppes at Univ Place (7.9 mi)\n8944 Jm Keynes Drive Suite 310, Charlotte, NC, 28262\nToday’s hours: 10am - 8pm\nIn Stock",'enabled':True}])[0],'available')
    def test_positive(self): self.assertEqual(classify('',[{'text':'Store A available for pickup','enabled':True}]),('available',['Store A available for pickup']))
    def test_reject_default_virginia_location(self):
        self.assertFalse(validate_area(['22000 Dulles Retail Plaza, Sterling, VA, 20166'], '27889'))
    def test_reject_charlotte_from_washington_search(self):
        self.assertFalse(validate_area(['8944 Jm Keynes Drive, Charlotte, NC, 28262'], '27889'))
    def test_allow_greenville_from_washington_search(self):
        self.assertTrue(validate_area(['600-C SE Greenville Blvd, Greenville, NC, 27858'], '27889'))
    def test_allow_charlotte_search(self):
        self.assertTrue(validate_area(['8944 Jm Keynes Drive, Charlotte, NC, 28262'], '28202'))
if __name__=='__main__': unittest.main()
