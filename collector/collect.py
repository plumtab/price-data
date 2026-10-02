#!/usr/bin/env python3
"""Fetch every target product page, parse the price from JSON-LD, and store one JSONL.gz per shop per run.

Output: data/prices/YYYY/MM/DD/<shop>-<HHMM>.jsonl.gz
Each line: {"t": iso_utc, "u": url, "n": name, "p": price, "lp": list_price (shop's own before-price),
            "c": currency, "e": ean, "s": sku, "a": availability, "sf": "dd/mm" offer start printed by the shop (optional)}
A line with "err" instead of a price records a failed fetch/parse (so gaps are visible, not silent).

Politeness: per-shop concurrency and delay (see shops.py), honest User-Agent with contact address.
Usage: python collector/collect.py [--limit N] [shop ...]
"""
import argparse
import datetime as dt
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


def scrape(url, delay=0):
    if delay:
        time.sleep(delay)
    status, html = fetch(url)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if status != 200:
        return {"t": now, "u": url, "err": f"http {status}"}
    prod = parse_product(html)
    if not prod:
        return {"t": now, "u": url, "err": "no-offer"}
    return {"t": now, "u": url, "n": prod["name"], "p": prod["price"], "lp": prod["list_price"],
            "c": prod["currency"], "e": prod["ean"], "s": prod["sku"], "a": prod["availability"],
            **({"sf": prod["sale_from"]} if prod.get("sale_from") else {})}


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
    with gzip.open(out, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
    ok = sum(1 for r in rows if "p" in r)
    with_lp = sum(1 for r in rows if r.get("lp"))
    errs = {}
    for r in rows:
        if "err" in r:
            errs[r["err"]] = errs.get(r["err"], 0) + 1
    summary = {"shop": name, "targets": len(urls), "ok": ok, "with_list_price": with_lp,
               "errors": errs, "seconds": round(time.time() - started), "file": os.path.relpath(out, ROOT)}
    print(json.dumps(summary))
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=None, help="override per-shop concurrency")
    ap.add_argument("--delay", type=float, default=None, help="override per-shop delay (seconds)")
    ap.add_argument("shops", nargs="*")
    args = ap.parse_args()
    in_ci = os.environ.get("CI") == "true"
    names = args.shops or [n for n, c in SHOPS.items() if not (in_ci and c.get("ci") is False)]
    with ThreadPoolExecutor(len(names)) as pool:
        results = list(pool.map(lambda n: run_shop(n, args.limit, args.workers, args.delay), names))
    # Fail the CI run only if *every* shop came back empty (something is badly wrong).
    if all(r["ok"] == 0 for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
