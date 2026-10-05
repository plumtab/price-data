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

    def test_salling_before_price_only_for_time_limited_campaigns(self):
        def nuxt(lp, sp, start, end, always="a", member="a"):
            return ('<script>window.__NUXT__=function(e,a,r){return{data:[{product:{list_price:%s,sales_price_generated:%s,'
                    'promotion_start_date:%s,promotion_end_date:%s,is_always_low_price:%s,has_membership_promotion:%s}}]}}'
                    '(null,!1,!0)</script>' % (lp, sp, start, end, always, member))
        doc = {"@type": "Product", "sku": "200161340", "offers": {"price": 910}}
        week = page(doc) + nuxt(1300, 910, '"2026-10-02"', '"2026-10-08"')
        p = parse_product(week, "https://www.foetex.dk/produkter/x/200161340/")
        self.assertEqual((p["list_price"], p["sale_from"]), (1300, "02/10"))
        all_year = page(doc) + nuxt(5999, 910, '"2026-01-01"', '"2026-12-31"')  # "SKARP PRIS", no before-price shown
        self.assertIsNone(parse_product(all_year, "https://www.foetex.dk/produkter/x/1/")["list_price"])
        self.assertIsNone(parse_product(week, "https://www.bilka.dk/produkter/x/1/")["list_price"])  # Bilka doesn't show it
        member = page(doc) + nuxt(1300, 910, '"2026-10-02"', '"2026-10-08"', member="r")
        self.assertIsNone(parse_product(member, "https://www.foetex.dk/produkter/x/1/")["list_price"])
        no_promo = page(doc) + nuxt(910, 910, "e", "e")
        self.assertIsNone(parse_product(no_promo, "https://www.foetex.dk/produkter/x/1/")["list_price"])

    def test_magasin_strikethrough_in_either_class_order(self):
        doc = {"@type": "Product", "sku": "BSID15", "offers": {"price": "599.00"}}
        for cls in ("strike-through list b-price__el-type", "b-price__el-type strike-through list"):
            html = page(doc) + ('<span class="b-price__el-type sales -list"><span class="b-price__value value" content="599.00">599 kr.</span></span>'
                                '<span class="%s"> <span class="b-price__value value" content="1199.00">1.199 kr.</span></span>'
                                '<div class="pdp__saledateinfo">Gælder 28/09 - 25/10</div>' % cls)
            p = parse_product(html, "https://www.magasin.dk/x/BSID15-0008.html")
            self.assertEqual((p["list_price"], p["sale_from"]), (1199, "28/09"))
        self.assertIsNone(parse_product(page(doc), "https://www.magasin.dk/x/BSID15-0008.html")["list_price"])

    def test_jysk_before_price_only_when_shown(self):
        def rsc(path, before, show="true", membership="null"):
            block = ('{"url":"%s","title":"Springmadras","price":{"unformatted":{"gross":2649,"membership":%s,"minSingle":1600},'
                     '"formatted":{"gross":"1600,-","membership":%s,"beforePricePrimary":"%s",'
                     '"beforePricePrimaryTextIndicator":"lowestPrice","beforePricePrimaryShow":%s},"discount":{"percentage":40}}}'
                     % (path, membership, membership, before, show))
            return '<script>self.__next_f.push([1,"%s"])</script>' % block.replace('"', '\\"')
        doc = {"@type": "Product", "sku": "3264381", "offers": {"price": 1600}}
        url = "https://jysk.dk/sovevaerelse/madrasser/springmadrasser/springmadras-stria"
        path = "/sovevaerelse/madrasser/springmadrasser/springmadras-stria"
        other = rsc("/sovevaerelse/madrasser/andet", "9.149,- /stk.")  # a recommended product listed first
        self.assertEqual(parse_product(page(doc) + other + rsc(path, "2.649,- /stk."), url)["list_price"], 2649)
        self.assertIsNone(parse_product(page(doc) + rsc(path, "2.649,- /stk.", show="false"), url)["list_price"])
        self.assertIsNone(parse_product(page(doc) + rsc(path, "2.649,- /stk.", membership="1600"), url)["list_price"])
        self.assertIsNone(parse_product(page(doc) + other, url)["list_price"])

    def test_no_offer(self):
        self.assertIsNone(parse_product(page({"@type": "WebPage"})))


if __name__ == "__main__":
    unittest.main()
