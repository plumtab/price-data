"""Shop configurations. Each shop: product sitemaps + which categories (URL path prefixes) we track.

We track Black Friday-relevant categories only, to stay polite and within free CI minutes.
Category prefixes are matched against the URL path.
"""

SHOPS = {
    "power": {
        "base": "https://www.power.dk",
        "sitemap_index": "https://www.power.dk/services/sitemap.xml",
        "product_sitemap_hint": "products",
        # Whole catalog (~29k). Public repo = unlimited Actions minutes.
        "categories": ["power.dk/"],
        "per_category_cap": 40000,
        "cap": 40000,
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
        # Elgiganten rate-limits GitHub runners (HTTP 429 even at 1 request with a pause). From the session
        # environment 4 parallel requests ran cleanly (Oct 4: 5,236 pages, no 429). 3 at a time with a short
        # pause keeps it polite (~2 requests/s, ~40 min a day) instead of ~4 hours at 1 with a 2 s pause.
        "workers": 3,
        "delay": 0.5,
        # Blocked from GitHub runners even at that pace (12/12 HTTP 429 on 2026-10-02).
        # Collected from Claude's session environment instead; skipped in CI.
        "ci": False,
    },
    # The shops below have no category in their URLs, so "categories" are keywords in the URL slug.
    "bilka": {
        # Bilka shows no before-prices in its HTML/JSON-LD: excluded from before-price statistics.
        "measures_before_price": False,
        "base": "https://www.bilka.dk",
        "sitemap_index": "https://bilka.dk/sitemap/sitemap-index.xml",
        "product_sitemap_hint": "sitemap",
        "url_must_contain": "/produkter/",
        "categories": ["/produkter/"],
        "per_category_cap": 70000,
        "cap": 70000,
        "workers": 3,
        "delay": 0,
    },
    "imerco": {
        "base": "https://www.imerco.dk",
        "sitemap_index": "https://www.imerco.dk/sitemap.xml",
        "product_sitemap_hint": "products",
        "categories": ["airfryer", "kaffemaskine", "espresso", "robotst", "stoevsuger", "kitchenaid", "moccamaster",
                       "nespresso", "blender", "stavblender", "knivsaet", "gryde", "pande", "oral-b", "lego-"],
        "per_category_cap": 1500,
        "cap": 8000,
        "workers": 3,
        "delay": 0,
    },
    "magasin": {
        "base": "https://www.magasin.dk",
        "sitemap_index": "https://www.magasin.dk/sitemap_index.xml",
        "product_sitemap_hint": "product",
        "categories": ["eau-de", "serum", "creme", "dyson", "kitchenaid", "espresso", "philips", "barbie", "moccamaster"],
        "per_category_cap": 1500,
        "cap": 8000,
        "workers": 3,
        "delay": 0,
    },
    # Added 2026-10-04. Matas, Føtex and Harald Nyborg render before-prices only in page HTML/JS we don't parse yet.
    "matas": {
        "base": "https://www.matas.dk",
        "sitemap_index": "https://www.matas.dk/sitemap",
        "product_sitemap_hint": r"/sitemap/product$",
        "categories": ["matas.dk/"],
        "per_category_cap": 80000,
        "cap": 80000,
        "workers": 3,
        "delay": 0,
        "measures_before_price": False,
    },
    "coolshop": {
        "base": "https://www.coolshop.dk",
        "sitemap_index": "https://www.coolshop.dk/sitemap.xml",
        "product_sitemap_hint": r"sitemap-\d+",
        "url_must_contain": "/produkt/",
        "categories": ["/produkt/"],
        "per_category_cap": 60000,
        "cap": 60000,
        "workers": 3,
        "delay": 0,
    },
    "fotex": {
        "base": "https://www.foetex.dk",
        "sitemap_index": "https://www.foetex.dk/sitemap/sitemap-index.xml",
        "product_sitemap_hint": r"sitemap-\d+",
        "url_must_contain": "/produkter/",
        "categories": ["/produkter/"],
        "per_category_cap": 60000,
        "cap": 60000,
        "workers": 3,
        "delay": 0,
    },
    "harald-nyborg": {
        "base": "https://www.harald-nyborg.dk",
        "sitemap_index": "https://www.harald-nyborg.dk/sitemap-index.xml",
        "product_sitemap_hint": r"sitemap-products",
        "categories": ["harald-nyborg.dk/"],
        "per_category_cap": 30000,
        "cap": 30000,
        "workers": 3,
        "delay": 0,
        "measures_before_price": False,
    },
}

# Max products per category prefix, so one huge category can't crowd out the rest.
PER_CATEGORY_CAP = 700  # keyword categories use the same cap
