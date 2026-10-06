"""Run: python3 -m unittest discover collector"""
import json
import os
import unittest

from common import parse_product

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return f.read()


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

    def test_imerco_member_price_is_not_an_offer(self):
        """D-024. Fixtures cut from the live pages (Oct 6): the Product's JSON-LD offer, the price list as served and
        the product's price fields from __NEXT_DATA__. Both pages have offers.price + a ListPrice in JSON-LD."""
        member = fixture("imerco-member-100452261.html")  # "249,95 Pris" + "187,46 Medlemspris*" (køb 2, members)
        url = "https://www.imerco.dk/la-rochere-espressoglas-4-stk-10-cl-glas-klar?id=100452261"
        p = parse_product(member, url)
        self.assertEqual((p["sku"], p["price"], p["list_price"]), ("100452261", 249.95, None))
        # Either signal alone is enough: the price list a visitor sees, or the page data.
        list_only = member[:member.index('<script id="__NEXT_DATA__"')]
        self.assertEqual((parse_product(list_only, url)["price"], parse_product(list_only, url)["list_price"]), (249.95, None))
        data_only = member[:member.index("<ul ")] + member[member.index('<script id="__NEXT_DATA__"'):]
        self.assertEqual((parse_product(data_only, url)["price"], parse_product(data_only, url)["list_price"]), (249.95, None))
        # Page data about another product (e.g. a stale payload) doesn't count; the JSON-LD alone reads as before.
        jsonld_only = member[:member.index("<ul ")]
        self.assertEqual(parse_product(jsonld_only, url)["price"], 187.46)
        self.assertEqual(parse_product(data_only.replace('"id": "100452261"', '"id": "1"'), url)["price"], 187.46)
        # Only Imerco pages get this rule.
        self.assertEqual(parse_product(member, "https://www.power.dk/x/p-100452261/")["price"], 187.46)

    def test_imerco_general_sale_stays_an_offer(self):
        sale = fixture("imerco-sale-100051590.html")  # "299,95 Pris" (struck) + "99,95 Tilbud"
        p = parse_product(sale, "https://www.imerco.dk/x?id=100051590")
        self.assertEqual((p["price"], p["list_price"]), (99.95, 299.95))

    def test_imerco_plain_price(self):
        plain = fixture("imerco-plain-100458249.html")  # "99,95 Pris" only
        p = parse_product(plain, "https://www.imerco.dk/kitchenaid-classic-opoeser-l-34-cm-nylon-hvid?id=100458249")
        self.assertEqual((p["price"], p["list_price"]), (99.95, None))

    def test_imerco_other_member_layout_already_has_the_general_price(self):
        # "1149,95 Ikke medlem" + "699,95 Medlemspris" (promotype memberprice): JSON-LD holds 1149.95 and no ListPrice.
        # "Ikke medlem" (not a member) is the price for everyone, so nothing changes here.
        page = fixture("imerco-ikke-medlem-100468874.html")
        p = parse_product(page, "https://www.imerco.dk/x?id=100468874")
        self.assertEqual((p["sku"], p["price"], p["list_price"]), ("100468874", 1149.95, None))

    def test_imerco_member_price_without_a_readable_general_price_is_not_recorded(self):
        member = fixture("imerco-member-100452261.html")
        no_general = member[:member.index('<script id="__NEXT_DATA__"')].replace(
            '<li data-price-type="default"', '<li data-price-type="hidden"').replace(">Pris<", ">Medlemspris<")
        self.assertIsNone(parse_product(no_general, "https://www.imerco.dk/x?id=100452261"))

    def test_no_offer(self):
        self.assertIsNone(parse_product(page({"@type": "WebPage"})))


if __name__ == "__main__":
    unittest.main()
