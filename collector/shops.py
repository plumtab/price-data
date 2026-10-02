"""Shop configurations. Each shop: product sitemaps + which categories (URL path prefixes) we track.

We track Black Friday-relevant categories only, to stay polite and within free CI minutes.
Category prefixes are matched against the URL path.
"""

SHOPS = {
    "power": {
        "base": "https://www.power.dk",
        "sitemap_index": "https://www.power.dk/services/sitemap.xml",
        "product_sitemap_hint": "products",
        "categories": [
            "/tv-og-lyd/tv/", "/tv-og-lyd/hovedtelefoner/", "/tv-og-lyd/traadloese-hoejtalere/",
            "/mobil-og-foto/mobiltelefoner/", "/mobil-og-foto/smartwatches-og-wearables/", "/mobil-og-foto/kameraer/",
            "/computere-og-tablets/computere/", "/computere-og-tablets/tablets-og-tilbehoer/",
            "/computere-og-tablets/monitorer-og-skaerme/",
            "/gaming-og-underholdning/playstation/", "/gaming-og-underholdning/nintendo/", "/gaming-og-underholdning/xbox/",
            "/hus-og-outdoor/rengoering-og-stoevsugning/",
            "/koekken-og-madlavning/kaffe-og-te/", "/koekken-og-madlavning/koekkenmaskiner-og-miksere/",
            "/koekken-og-madlavning/madlavningsapparater/",
            "/skoenhed-og-velvaere/", "/hvidevarer/opvaskemaskiner-og-tilbehoer/", "/hvidevarer/toejvask/",
        ],
        "cap": 9000,
        "workers": 4,
        "delay": 0,
    },
    "elgiganten": {
        "base": "https://www.elgiganten.dk",
        "sitemap_index": "https://www.elgiganten.dk/sitemaps/OCDKELG.pdp.index.sitemap.xml",
        "product_sitemap_hint": "pdp",
        "categories": [
            "/product/tv-lyd-smart-home/tv-tilbehor/tv/",
            "/product/tv-lyd-smart-home/horetelefoner-tilbehor/horetelefoner/",
            "/product/tv-lyd-smart-home/hojtalere-hi-fi/soundbar/",
            "/product/mobil-tablet-smartwatch/smartwatch/",
            "/product/computer-kontor/computere/barbar-computer/",
            "/product/computer-kontor/computere/stationar-pc/",
            "/product/hjem-rengoring-kokkenudstyr/kaffe-te/espressomaskine/",
            "/product/hjem-rengoring-kokkenudstyr/kaffe-te/kaffemaskine/",
            "/product/hjem-rengoring-kokkenudstyr/kaffe-te/kapselmaskine/",
            "/product/hjem-rengoring-kokkenudstyr/rengoring/robotstovsuger/",
            "/product/hjem-rengoring-kokkenudstyr/rengoring/ledningsfri-stovsuger/",
            "/product/hjem-rengoring-kokkenudstyr/rengoring/stovsuger/",
            "/product/hjem-rengoring-kokkenudstyr/rengoring/handstovsuger/",
            "/product/personlig-pleje-skonhed-velvare/harpleje-styling/glattejern/",
            "/product/personlig-pleje-skonhed-velvare/harpleje-styling/hartorrer/",
            "/product/personlig-pleje-skonhed-velvare/harpleje-styling/krollejern/",
            "/product/personlig-pleje-skonhed-velvare/harpleje-styling/multistyler-glattejern-og-krolletang-i-et/",
            "/product/computer-kontor/netvark/mesh-netvark/",
            "/product/computer-kontor/netvark/router/",
        ],
        "cap": 6000,
        # Elgiganten rate-limits cloud IPs (HTTP 429 at 4 parallel requests from GitHub runners),
        # so we go one request at a time with a pause.
        "workers": 1,
        "delay": 2.0,
        # Blocked from GitHub runners even at that pace (12/12 HTTP 429 on 2026-10-02).
        # Collected from Claude's session environment instead; skipped in CI.
        "ci": False,
    },
    # The shops below have no category in their URLs, so "categories" are keywords in the URL slug.
    "bilka": {
        "base": "https://www.bilka.dk",
        "sitemap_index": "https://bilka.dk/sitemap/sitemap-index.xml",
        "product_sitemap_hint": "sitemap",
        "url_must_contain": "/produkter/",
        "categories": ["lego-", "-tv-", "airfryer", "kaffemaskine", "espresso", "robotst", "stoevsuger",
                       "hoeretelefon", "hovedtelefon", "playstation", "nintendo", "galaxy", "dyson", "philips",
                       "kitchenaid", "smartwatch", "barbie", "oral-b", "eau-de"],
        "cap": 3000,
        "workers": 3,
        "delay": 0,
    },
    "imerco": {
        "base": "https://www.imerco.dk",
        "sitemap_index": "https://www.imerco.dk/sitemap.xml",
        "product_sitemap_hint": "products",
        "categories": ["airfryer", "kaffemaskine", "espresso", "robotst", "stoevsuger", "kitchenaid", "moccamaster",
                       "nespresso", "blender", "stavblender", "knivsaet", "gryde", "pande", "oral-b", "lego-"],
        "cap": 2500,
        "workers": 3,
        "delay": 0,
    },
    "magasin": {
        "base": "https://www.magasin.dk",
        "sitemap_index": "https://www.magasin.dk/sitemap_index.xml",
        "product_sitemap_hint": "product",
        "categories": ["eau-de", "serum", "creme", "dyson", "kitchenaid", "espresso", "philips", "barbie", "moccamaster"],
        "cap": 2500,
        "workers": 3,
        "delay": 0,
    },
}

# Max products per category prefix, so one huge category can't crowd out the rest.
PER_CATEGORY_CAP = 700  # keyword categories use the same cap
