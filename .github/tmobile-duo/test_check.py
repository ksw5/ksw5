import importlib.util
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

spec=importlib.util.spec_from_file_location("tmobile",Path(__file__).with_name("check.py"))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
URL=m.inventory_url("t-mobile-greenville-nc-27858-9422")
NOW=datetime(2026,10,26,20,0,tzinfo=ZoneInfo("America/New_York"))

def html(status,description,heading="iPhone Duo at T-Mobile Arlington Plaza"):
    return ("<html><h1>"+heading+"</h1><div class='header-stock'>"
            "<span id='stock-description'>"+status+"</span>"
            "<span id='stock-details'>"+description+"</span></div></html>")

class TestTmobileParser(unittest.TestCase):
    def test_positive(self):
        s,d=m.parse(html("In stock","This item is confirmed available for purchase. Last updated on Oct 23"),URL,URL,NOW)
        self.assertEqual(s,"available")
        self.assertIn("Oct 23",d)
    def test_high_demand_is_not_available(self):
        s,_=m.parse(html("High demand","Item may sell out quickly. Visit a store for best availability. Shipping options available."),URL,URL,NOW)
        self.assertEqual(s,"unavailable")
    def test_boilerplate_pickup_option_is_not_stock(self):
        s,_=m.parse(html("High demand","Options: Same Day Delivery, Pickup in store, Shipping"),URL,URL,NOW)
        self.assertNotEqual(s,"available")
    def test_redirect_to_generic_store_page(self):
        s,_=m.parse(html("In stock","This item is confirmed available for purchase. Last updated on Oct 23"),
            "https://www.t-mobile.com/stores/bd/t-mobile-greenville-nc-27858-9422",URL,NOW)
        self.assertEqual(s,"unknown")
    def test_stale_indicator(self):
        s,_=m.parse(html("In stock","This item is confirmed available for purchase. Last updated on Oct 1"),URL,URL,NOW)
        self.assertEqual(s,"unknown")
    def test_non_product_heading(self):
        s,_=m.parse(html("In stock","This item is confirmed available for purchase. Last updated on Oct 23",heading="iPhone 18 Pro at T-Mobile Arlington Plaza"),URL,URL,NOW)
        self.assertEqual(s,"unknown")
    def test_missing_date(self):
        s,_=m.parse(html("In stock","This item is confirmed available for purchase."),URL,URL,NOW)
        self.assertEqual(s,"unknown")
    def test_unfounded_in_stock(self):
        s,_=m.parse(html("In stock","Maybe there is stock somewhere."),URL,URL,NOW)
        self.assertEqual(s,"unknown")

if __name__ == "__main__":
    unittest.main()
