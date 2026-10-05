#!/usr/bin/env python3
"""Fetch every target product page, parse the price from JSON-LD, and store one JSONL.gz per shop per run.

Output (slim, since 2026-10-04):
  data/prices/YYYY/MM/DD/<shop>-<HHMM>.jsonl.gz, one line per target:
      {"s": sku, "p": price, "lp": shop's own before-price (optional), "a": 1 in stock / 0 not, "sf": "dd/mm" (optional)}
      or {"u": url, "err": "..."} for a failed fetch/parse (gaps stay visible, not silent).
  collector/catalog/<shop>.jsonl, append-only: {"s": sku, "n": name, "e": ean, "u": url}, written when a product
      is new or its name/EAN/URL changed. Keeps daily files small (names and URLs aren't repeated every day).
Older daily files (before 2026-10-04) carry n/e/u/t inline; readers handle both.

Politeness: per-shop concurrency and delay (see shops.py), honest User-Agent with contact address.
Usage: python collector/collect.py [--limit N] [shop ...]
"""
import argparse
import datetime as dt
import glob
import gzip
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from common import fetch, parse_product
from shops import SHOPS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


IN_STOCK = {"InStock", "LimitedAvailability", "OnlineOnly", "InStoreOnly", "PreOrder", "BackOrder"}


def scrape(url, delay=0):
    if delay:
        time.sleep(delay)
    status, html = fetch(url)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if status != 200:
        return {"t": now, "u": url, "err": f"http {status}"}
    prod = parse_product(html, url)
    if not prod:
        return {"t": now, "u": url, "err": "no-offer"}
    row = {"s": prod["sku"], "p": prod["price"], "a": 1 if prod["availability"] in IN_STOCK else 0}
    if prod["list_price"]:
        row["lp"] = prod["list_price"]
    if prod.get("sale_from"):
        row["sf"] = prod["sale_from"]
    if prod.get("variant"):
        row["v"] = prod["variant"]
    row["_meta"] = {"n": prod["name"], "e": prod["ean"], "u": url}
    return row


def load_catalog(name):
    path = os.path.join(HERE, "catalog", f"{name}.jsonl")
    cat = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                cat[r["s"]] = r
    return cat


def update_catalog(name, rows):
    """Append products that are new or whose name/EAN/URL changed."""
    cat = load_catalog(name)
    os.makedirs(os.path.join(HERE, "catalog"), exist_ok=True)
    added = 0
    with open(os.path.join(HERE, "catalog", f"{name}.jsonl"), "a", encoding="utf-8") as f:
        for r in rows:
            m = r.get("_meta")
            if not m:
                continue
            entry = {"s": r["s"], "n": m["n"], "e": m["e"], "u": m["u"]}
            old = cat.get(r["s"])
            if not old or any(old.get(k) != entry[k] for k in ("n", "e", "u")):
                f.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
                cat[r["s"]] = entry
                added += 1
    return added


def run_shop(name, limit=None, workers=None, delay=None):
    path = os.path.join(HERE, "targets", f"{name}.txt")
    urls = [u.strip() for u in open(path) if u.strip()]
    if limit:
        urls = urls[:limit]
    started = time.time()
    cfg = SHOPS[name]
    workers = workers or cfg.get("workers", 4)
    delay = cfg.get("delay", 0) if delay is None else delay
    with ThreadPoolExecutor(workers) as pool:
        rows = list(pool.map(lambda u: scrape(u, delay), urls))
    now = dt.datetime.now(dt.timezone.utc)
    out_dir = os.path.join(ROOT, "data", "prices", now.strftime("%Y/%m/%d"))
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{name}-{now.strftime('%H%M')}.jsonl.gz")
    catalog_added = update_catalog(name, rows)
    with gzip.open(out, "wt", encoding="utf-8") as f:
        for r in rows:
            r = {k: v for k, v in r.items() if k != "_meta"}
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
    ok = sum(1 for r in rows if "p" in r)
    with_lp = sum(1 for r in rows if r.get("lp"))
    errs = {}
    for r in rows:
        if "err" in r:
            errs[r["err"]] = errs.get(r["err"], 0) + 1
    summary = {"shop": name, "targets": len(urls), "ok": ok, "with_list_price": with_lp, "catalog_added": catalog_added,
               "errors": errs, "seconds": round(time.time() - started), "file": os.path.relpath(out, ROOT)}
    print(json.dumps(summary))
    return summary


def collected_today(name, min_share=0.8):
    """True if today's files for this shop already cover most of its targets."""
    day = dt.datetime.now(dt.timezone.utc).strftime("%Y/%m/%d")
    targets = sum(1 for _ in open(os.path.join(HERE, "targets", f"{name}.txt")))
    best = 0
    for path in glob.glob(os.path.join(ROOT, "data", "prices", day, f"{name}-*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            best = max(best, sum(1 for _ in f))
    return best >= min_share * targets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=None, help="override per-shop concurrency")
    ap.add_argument("--delay", type=float, default=None, help="override per-shop delay (seconds)")
    ap.add_argument("--skip-existing", action="store_true",
                    help="skip shops that already have a full collection for today (backup runs only fill gaps)")
    ap.add_argument("shops", nargs="*")
    args = ap.parse_args()
    in_ci = os.environ.get("CI") == "true"
    names = args.shops or [n for n, c in SHOPS.items() if not (in_ci and c.get("ci") is False)]
    if args.skip_existing:
        names = [n for n in names if not collected_today(n)]
        print(json.dumps({"skip_existing": True, "to_collect": names}))
        if not names:
            return
    with ThreadPoolExecutor(len(names)) as pool:
        results = list(pool.map(lambda n: run_shop(n, args.limit, args.workers, args.delay), names))
    # Fail the CI run only if *every* shop came back empty (something is badly wrong).
    if all(r["ok"] == 0 for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
