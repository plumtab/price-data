"""Run: python3 -m unittest discover collector"""
import json
import unittest

from common import parse_product


def page(*docs):
    return "".join(f'<script type="application/ld+json">{json.dumps(d)}</script>' for d in docs)


GROUP = {
    "@type": "ProductGroup",
    "name": "Fiskeolie",
    "hasVariant": [
        {"@type": "Product", "sku": "761315", "gtin13": "5719801008454", "name": "120 kaps",
         "url": "https://www.matas.dk/fiskeolie-120-kaps", "offers": {"price": "160.95", "url": "/fiskeolie-120-kaps"}},
        {"@type": "Product", "sku": "761316", "gtin13": "5719801008447", "name": "140 kaps",
         "url": "https://www.matas.dk/fiskeolie-140-kaps", "offers": {"price": "249.95", "url": "/fiskeolie-140-kaps"}},
        {"@type": "Product", "sku": "761317", "gtin13": "5719801008430", "name": "180 kaps",
         "url": "https://www.matas.dk/fiskeolie-180-kaps", "offers": {"price": "299.95", "url": "/fiskeolie-180-kaps"}},
    ],
}


class ParseProduct(unittest.TestCase):
    def test_variant_matching_page_url(self):
        p = parse_product(page(GROUP), "https://www.matas.dk/fiskeolie-120-kaps")
        self.assertEqual((p["sku"], p["price"], p["ean"]), ("761315", 160.95, "5719801008454"))
        p = parse_product(page(GROUP), "https://www.matas.dk/fiskeolie-180-kaps/")
        self.assertEqual(p["sku"], "761317")

    def test_no_match_takes_first(self):
        self.assertEqual(parse_product(page(GROUP), "https://www.matas.dk/other")["sku"], "761315")
        self.assertEqual(parse_product(page(GROUP))["sku"], "761315")

    def test_single_product_with_list_price(self):
        doc = {"@type": "Product", "sku": "1", "offers": [{"price": 4888, "priceCurrency": "DKK",
               "availability": "https://schema.org/InStock",
               "priceSpecification": [{"priceType": "https://schema.org/StrikethroughPrice", "price": 7999}]}]}
        p = parse_product(page({"@type": "BreadcrumbList"}, doc), "https://www.power.dk/x/p-1/")
        self.assertEqual((p["price"], p["list_price"], p["availability"]), (4888, 7999, "InStock"))

    def test_size_variant_recorded(self):
        doc = {"@type": "Product", "sku": "BOIX24", "offers": {"price": "910", "url": "https://www.magasin.dk/x/S14935921.html"}}
        p = parse_product(page(doc), "https://www.magasin.dk/eau-de-grey-vetiver-eau-de-toilette/BOIX24.html")
        self.assertEqual((p["sku"], p["variant"]), ("BOIX24", "s14935921"))
        self.assertIsNone(parse_product(page(GROUP), "https://www.matas.dk/fiskeolie-120-kaps")["variant"])

    def test_no_offer(self):
        self.assertIsNone(parse_product(page({"@type": "WebPage"})))


if __name__ == "__main__":
    unittest.main()
