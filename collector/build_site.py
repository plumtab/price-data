#!/usr/bin/env python3
"""Turn raw daily price files into compact static history files the extension can fetch.

Input:  data/prices/YYYY/MM/DD/<shop>-HHMM.jsonl.gz  (+ collector/catalog/<shop>.jsonl for names/EAN/URL)
Output: <out>/v2/<shop>/<shard>.json   (extension >= 0.4) run-length history, only changes are stored:
        { "<sku>": {"n": name, "e": ean, "l": last_day_seen, "h": [[ first_day_of_run, price, list_price_or_null, avail ], ...],
                    "x": [days without an observation, only if any] } }
        <out>/v2/ean/<shard>.json, <out>/v2/meta.json, <out>/v2/index.json   (same as v1)
        <out>/v1/...  LEGACY daily format for extension 0.3 (remove once 0.4 is live, before 2026-11-01)
        <out>/v1/<shop>/<shard>.json   shard = first 2 hex chars of sha1(sku)
        { "<sku>": {"n": name, "e": ean, "h": [[ "YYYY-MM-DD", price, list_price_or_null, avail_code ], ...]} }
        <out>/v1/ean/<shard>.json        shard = first 2 hex chars of sha1(ean)
        { "<ean>": [[shop, sku, latest_price, date, avail_code, url], ...] }   (only EANs at 2+ shops)
        <out>/v1/meta.json               { "built": iso, "first_day": ..., "last_day": ..., "shops": {...} }
        <out>/v1/index.json              Førpris index (descriptive): per shop per day, how many tracked products
                                         had a price and how many showed a before-price (list price above price).

One observation per product per day: the lowest price seen that day (a conservative choice:
it can only make a shop's before-price look *more* justified, never less).
avail_code: 1 = in stock, 0 = not in stock / unknown.

Usage: python collector/build_site.py [--out site]
"""
import argparse
import collections
import datetime as dt
import glob
import gzip
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_STOCK = {"InStock", "LimitedAvailability", "OnlineOnly", "InStoreOnly", "PreOrder", "BackOrder"}


# D-024: until the collector fix (first fixed run Oct 7), Imerco's conditional member prices ("Medlemspris*", e.g. 25 %
# off when a member buys 2) were recorded as offers: the member price as the price, the normal price as the
# before-price. Afterwards they can't be told apart from real sales. A second layout ("Ikke medlem") recorded the
# member price as the general price with no before-price at all, so a row without one isn't safe either (found
# 2026-10-07: 11 false watch-list "raises" at Imerco). The site leaves out every Imerco row from before the fix, with
# or without a before-price (that day counts as not observed for the product), and the index gives no before-price
# count for Imerco's days before the fix. Raw data stays as recorded. Same rule as tools/analysis/blackweek.py in the project repo.
IMERCO_MEMBER_FIX = "2026-10-07"


def trusted(shop, day, r):
    """False for a raw row the site leaves out (see IMERCO_MEMBER_FIX)."""
    return not (shop == "imerco" and day < IMERCO_MEMBER_FIX)


def shard(key):
    return hashlib.sha1(key.encode()).hexdigest()[:2]


def missing_days(days):
    """Days between the first and last observation that have no observation (shop not collected, or page failed).

    The v2 run-length history would otherwise silently carry a price across those days."""
    if not days:
        return []
    ds = sorted(days)
    have = set(ds)
    out, d = [], dt.date.fromisoformat(ds[0])
    end = dt.date.fromisoformat(ds[-1])
    while d < end:
        if d.isoformat() not in have:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "site"))
    args = ap.parse_args()

    # Catalog (names, EAN, URL) from the append-only catalog files; daily rows since 2026-10-04 don't repeat them.
    catalog = {}
    for path in glob.glob(os.path.join(ROOT, "collector", "catalog", "*.jsonl")):
        shop = os.path.basename(path)[: -len(".jsonl")]
        with open(path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                catalog[(shop, r["s"])] = r

    # (shop, sku) -> {"n","e","u", days: {day: [price, lp, avail]}}
    products = {}
    # (shop, day) -> [priced, with_before_price]
    daily = collections.defaultdict(lambda: [0, set()])  # [unused, {(sku, has_before_price)}]
    days_seen = set()
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "prices", "*", "*", "*", "*.jsonl.gz"))):
        parts = path.split(os.sep)
        day = "-".join(parts[-4:-1])
        shop = os.path.basename(path).rsplit("-", 1)[0]
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if "p" not in r or not r.get("s"):
                    continue
                days_seen.add(day)
                daily[(shop, day)][1].add((r["s"], bool(r.get("lp") and r["lp"] > r["p"] + 0.5)))
                if not trusted(shop, day, r):
                    continue
                key = (shop, r["s"])
                prod = products.setdefault(key, {"n": r.get("n"), "e": r.get("e"), "u": r.get("u"), "days": {}})
                prod["n"], prod["e"], prod["u"] = r.get("n") or prod["n"], r.get("e") or prod["e"], r.get("u") or prod["u"]
                a = r.get("a")
                avail = a if isinstance(a, int) else (1 if a in IN_STOCK else 0)
                obs = [r["p"], r.get("lp"), avail, r.get("v")]
                cur = prod["days"].get(day)
                # Lowest price of the day wins; at the same price, prefer the reading that has a before-price.
                if cur is None or obs[0] < cur[0] or (obs[0] == cur[0] and obs[1] and not cur[1]):
                    prod["days"][day] = obs

    # Catalog entries win for names/EAN/URL (they're the latest known values).
    for key, prod in products.items():
        c = catalog.get(key)
        if c:
            prod["n"], prod["e"], prod["u"] = c.get("n") or prod["n"], c.get("e") or prod["e"], c.get("u") or prod["u"]

    shards_v1 = collections.defaultdict(dict)
    shards_v2 = collections.defaultdict(dict)
    by_ean = collections.defaultdict(list)
    shop_counts = collections.Counter()
    for (shop, sku), prod in products.items():
        # Size variants (Magasin): keep only days of the size the page shows now. Untagged rows (before Oct 5) stay.
        cur_v = prod["days"][max(prod["days"])][3]
        if cur_v:
            prod["days"] = {d: o for d, o in prod["days"].items() if o[3] in (None, cur_v)}
        hist = [[d] + prod["days"][d][:3] for d in sorted(prod["days"])]
        runs = []
        for h in hist:
            if not runs or runs[-1][1:] != h[1:]:
                runs.append(h)
        shards_v1[(shop, shard(sku))][sku] = {"n": prod["n"], "e": prod["e"], "h": hist}
        entry = {"n": prod["n"], "e": prod["e"], "l": hist[-1][0], "h": runs}
        gaps = missing_days(prod["days"])
        if gaps:
            entry["x"] = gaps  # days we did not observe; extension >= 0.4.1 leaves them out
        shards_v2[(shop, shard(sku))][sku] = entry
        shop_counts[shop] += 1
        if prod["e"]:
            last = hist[-1]
            by_ean[prod["e"]].append([shop, sku, last[1], last[0], last[3], prod["u"]])

    for version, shards in (("v1", shards_v1), ("v2", shards_v2)):
        for (shop, sh), data in shards.items():
            d = os.path.join(args.out, version, shop)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, f"{sh}.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    out = os.path.join(args.out, "v1")

    ean_shards = collections.defaultdict(dict)
    for ean, offers in by_ean.items():
        if len({o[0] for o in offers}) >= 2:
            ean_shards[shard(ean)][ean] = offers
    os.makedirs(os.path.join(out, "ean"), exist_ok=True)
    for sh, data in ean_shards.items():
        with open(os.path.join(out, "ean", f"{sh}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    # Index: count unique products per shop/day; a product counts as "with before-price" if any observation that day had one.
    index = collections.defaultdict(dict)
    for (shop, day), cell in sorted(daily.items()):
        seen = {}
        for sku, has_lp in cell[1]:
            seen[sku] = seen.get(sku, False) or has_lp
        # Imerco before the member-price fix: how many products we followed is known, how many showed a real
        # before-price is not (D-024). null = unknown; the front page shows "–" for it.
        index[shop][day] = [len(seen), None if shop == "imerco" and day < IMERCO_MEMBER_FIX else sum(seen.values())]
    from shops import SHOPS
    not_measured = sorted(n for n, c in SHOPS.items() if c.get("measures_before_price") is False)
    with open(os.path.join(out, "index.json"), "w") as f:
        json.dump({"days": sorted(days_seen), "shops": index, "before_price_not_measured": not_measured}, f, separators=(",", ":"))

    meta = {"built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "first_day": min(days_seen) if days_seen else None, "last_day": max(days_seen) if days_seen else None,
            "shops": dict(shop_counts)}
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    # v2 shares the EAN index, index and meta with v1.
    import shutil
    for name in ("meta.json", "index.json"):
        shutil.copy(os.path.join(out, name), os.path.join(args.out, "v2", name))
    shutil.copytree(os.path.join(out, "ean"), os.path.join(args.out, "v2", "ean"), dirs_exist_ok=True)
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
