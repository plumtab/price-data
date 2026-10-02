#!/usr/bin/env python3
"""Turn raw daily price files into compact static history files the extension can fetch.

Input:  data/prices/YYYY/MM/DD/<shop>-HHMM.jsonl.gz
Output: <out>/v1/<shop>/<shard>.json   shard = first 2 hex chars of sha1(sku)
        { "<sku>": {"n": name, "e": ean, "h": [[ "YYYY-MM-DD", price, list_price_or_null, avail_code ], ...]} }
        <out>/v1/ean/<shard>.json        shard = first 2 hex chars of sha1(ean)
        { "<ean>": [[shop, sku, latest_price, date, avail_code, url], ...] }   (only EANs at 2+ shops)
        <out>/v1/meta.json               { "built": iso, "first_day": ..., "last_day": ..., "shops": {...} }

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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_STOCK = {"InStock", "LimitedAvailability", "OnlineOnly", "InStoreOnly", "PreOrder", "BackOrder"}


def shard(key):
    return hashlib.sha1(key.encode()).hexdigest()[:2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "site"))
    args = ap.parse_args()

    # (shop, sku) -> {"n","e", days: {day: [price, lp, avail]}}
    products = {}
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
                key = (shop, r["s"])
                prod = products.setdefault(key, {"n": r.get("n"), "e": r.get("e"), "u": r.get("u"), "days": {}})
                prod["n"], prod["e"], prod["u"] = r.get("n") or prod["n"], r.get("e") or prod["e"], r.get("u") or prod["u"]
                avail = 1 if r.get("a") in IN_STOCK else 0
                obs = [r["p"], r.get("lp"), avail]
                cur = prod["days"].get(day)
                if cur is None or obs[0] < cur[0]:
                    prod["days"][day] = obs

    out = os.path.join(args.out, "v1")
    shards = collections.defaultdict(dict)
    by_ean = collections.defaultdict(list)
    shop_counts = collections.Counter()
    for (shop, sku), prod in products.items():
        hist = [[d] + prod["days"][d] for d in sorted(prod["days"])]
        shards[(shop, shard(sku))][sku] = {"n": prod["n"], "e": prod["e"], "h": hist}
        shop_counts[shop] += 1
        if prod["e"]:
            last = hist[-1]
            by_ean[prod["e"]].append([shop, sku, last[1], last[0], last[3], prod["u"]])

    for (shop, sh), data in shards.items():
        d = os.path.join(out, shop)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{sh}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    ean_shards = collections.defaultdict(dict)
    for ean, offers in by_ean.items():
        if len({o[0] for o in offers}) >= 2:
            ean_shards[shard(ean)][ean] = offers
    os.makedirs(os.path.join(out, "ean"), exist_ok=True)
    for sh, data in ean_shards.items():
        with open(os.path.join(out, "ean", f"{sh}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    meta = {"built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "first_day": min(days_seen) if days_seen else None, "last_day": max(days_seen) if days_seen else None,
            "shops": dict(shop_counts)}
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
