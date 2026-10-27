import unittest
from pickup import classify, NO_PICKUP
class PickupTests(unittest.TestCase):
    def test_negative(self): self.assertEqual(classify(NO_PICKUP,[])[0],'unavailable')
    def test_loading_is_unknown(self): self.assertEqual(classify('Pick up here',[])[0],'unknown')
    def test_shipping_not_pickup(self): self.assertEqual(classify('In stock. Shipping today.',[])[0],'unknown')
    def test_disabled_positive(self): self.assertEqual(classify('',[{'text':'Store A available for pickup','enabled':False}])[0],'unknown')
    def test_negative_option(self): self.assertEqual(classify('',[{'text':'Store A not available for pickup','enabled':True}])[0],'unknown')
    def test_positive(self): self.assertEqual(classify('',[{'text':'Store A available for pickup','enabled':True}]),('available',['Store A available for pickup']))
if __name__=='__main__': unittest.main()
