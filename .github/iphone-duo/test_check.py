"""Tests built from the inspected 2026-10-26 live store-row DOM format."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("checker", Path(__file__).with_name("check.py"))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

def fixture(available=None, invalid=False):
    available = available or set()
    rows = []
    for store in sorted(checker.NEARBY_STORES):
        cells = []
        for c, color in checker.COLORS.items():
            for s, size in checker.STORAGE.items():
                is_up = (store, c, s) in available
                state = "Available" if is_up else "Unavailable"
                klass = "sq-unavailable" if (invalid or not is_up) else "sq-available"
                cells.append(f'<td data-color="{c}" data-storage="{s}">'
                             f'<span class="sq {klass}" title="{color} {size}: {state}"></span></td>')
        rows.append('<tr data-store="" data-state="NC"><th scope="row">'
                    f'<a href="https://duo-checker.on-forge.com/stores/R116">{store}</a>'
                    f'<small>Nearby</small></th>{"".join(cells)}</tr>')
    for n in range(200):
        rows.append(f'<tr data-store=""><th scope="row">'
                    f'<a href="/stores/OTHER{n}">Other{n}</a></th></tr>')
    return '<h1>iPhone Duo pickup availability</h1><table>' + "".join(rows) + '</table>'

class TestInventory(unittest.TestCase):
    def test_unavailable_is_not_available(self):
        found, count = checker.parse_inventory(fixture())
        self.assertEqual(found, [])
        self.assertEqual(count, 200 + len(checker.NEARBY_STORES))
    def test_one_positive_store_sku(self):
        found, _ = checker.parse_inventory(fixture({("Southpoint", "night-sky", "512")}))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["store"], "Southpoint")
        self.assertEqual(found[0]["color"], "Night Sky")
        self.assertEqual(found[0]["storage"], "512GB")
    def test_mismatched_status_class_is_rejected(self):
        with self.assertRaises(checker.ParseError):
            checker.parse_inventory(fixture({("Southpoint", "night-sky", "512")}, invalid=True))
    def test_incomplete_table_is_rejected(self):
        with self.assertRaises(checker.ParseError):
            checker.parse_inventory('<h1>iPhone Duo pickup availability</h1><table></table>')
    def test_wrong_product_is_rejected(self):
        with self.assertRaises(checker.ParseError):
            checker.parse_inventory(fixture().replace("iPhone Duo", "iPhone Other"))
    def test_remote_inventory_is_ignored(self):
        found, _ = checker.parse_inventory(fixture())
        self.assertEqual(found, [])

if __name__ == "__main__":
    unittest.main()

