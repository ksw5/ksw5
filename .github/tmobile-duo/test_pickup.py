import unittest
from pickup import classify, NO_PICKUP
class PickupTests(unittest.TestCase):
    def test_negative(self): self.assertEqual(classify(NO_PICKUP,[])[0],'unavailable')
    def test_loading_is_unknown(self): self.assertEqual(classify('Pick up here',[])[0],'unknown')
    def test_shipping_not_pickup(self): self.assertEqual(classify('In stock. Shipping today.',[])[0],'unknown')
    def test_disabled_positive(self): self.assertEqual(classify('',[{'text':'Store A available for pickup','enabled':False}])[0],'unknown')
    def test_negative_option(self): self.assertEqual(classify('',[{'text':'Store A not available for pickup','enabled':True}])[0],'unknown')
    def test_live_store_label(self): self.assertEqual(classify('Search results available below.',[{'text':"The Shoppes at Univ Place (7.9 mi)\n8944 Jm Keynes Drive Suite 310, Charlotte, NC, 28262\nToday’s hours: 10am - 8pm\nIn Stock",'enabled':True}])[0],'available')
    def test_positive(self): self.assertEqual(classify('',[{'text':'Store A available for pickup','enabled':True}]),('available',['Store A available for pickup']))
if __name__=='__main__': unittest.main()
