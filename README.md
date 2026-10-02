# price-data

Daily price history for products at Danish webshops, collected by **PlumtabPriceBot**.
It powers **Førpris**, a free browser extension that shows whether a shop's "before" price (førpris)
holds up against the lowest price of the previous 30 days, as Danish and EU price-marking rules require.

- Published data: `https://plumtab.github.io/price-data/v1/` (static JSON, see `collector/build_site.py`)
- Raw observations: `data/prices/YYYY/MM/DD/<shop>-HHMM.jsonl.gz`

## How the bot behaves

- Visits only product pages that the shop's `robots.txt` allows, found via the shop's public sitemaps.
- Once a day, a few requests at a time, with an honest User-Agent:
  `PlumtabPriceBot/0.1 (+https://plumtab.github.io/price-data/bot.html; plumtab.studio@gmail.com)`
- Stores only public facts shown on the page: product name, price, before-price, EAN, availability.

**Shops:** if you would like us to stop or slow down, email **plumtab.studio@gmail.com** and we will act on it.

## Layout

- `collector/`: target selection (`targets.py`), collection (`collect.py`), static build (`build_site.py`)
- `.github/workflows/daily.yml`: collect daily, then build and publish to GitHub Pages
- `site-src/`: the small public website (about, privacy, bot info)

A project by Plumtab.
