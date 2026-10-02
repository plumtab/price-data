#!/usr/bin/env python3
"""Build the list of product URLs to track per shop, from the shops' public sitemaps.

The selection is *stable*: within each category we order URLs by a hash of the URL,
so the same products are tracked day after day (that's what makes price history work).
Re-run weekly to pick up new products; already-tracked products stay selected as long as they exist.

Usage: python collector/targets.py [shop ...]   -> writes collector/targets/<shop>.txt
"""
import hashlib
import os
import sys
import time
import urllib.robotparser

from common import USER_AGENT, fetch, sitemap_locs
from shops import SHOPS, PER_CATEGORY_CAP

HERE = os.path.dirname(os.path.abspath(__file__))


def product_urls(cfg):
    status, xml = fetch(cfg["sitemap_index"])
    if status != 200:
        raise RuntimeError(f"sitemap index {status}")
    subs = [u for u in sitemap_locs(xml) if cfg["product_sitemap_hint"] in u] if "<sitemapindex" in xml else [cfg["sitemap_index"]]
    urls = []
    for sub in subs:
        st, body = fetch(sub)
        if st == 200:
            urls.extend(sitemap_locs(body))
        time.sleep(0.5)
    return urls


def robots_filter(urls, cfg):
    """Drop any URL the shop's robots.txt disallows for our user agent."""
    status, txt = fetch(cfg["base"] + "/robots.txt")
    if status != 200:
        return urls
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(txt.splitlines())
    agent = USER_AGENT.split("/")[0]
    return [u for u in urls if rp.can_fetch(agent, u)]


def select(urls, cfg, previous=()):
    """Keep previously tracked products that still exist (continuity of history), then fill up with new ones."""
    key = lambda u: hashlib.sha1(u.encode()).hexdigest()
    if cfg.get("url_must_contain"):
        urls = [u for u in urls if cfg["url_must_contain"] in u]
    alive = set(urls)
    chosen = []
    for prefix in cfg["categories"]:
        kept = [u for u in previous if prefix in u and u in alive]
        new = sorted((u for u in urls if prefix in u and u not in set(kept)), key=key)
        chosen.extend((kept + new)[: cfg.get("per_category_cap", PER_CATEGORY_CAP)])
    seen, out = set(), []
    for u in chosen:
        if u not in seen:
            seen.add(u)
            out.append(u)
    if len(out) > cfg["cap"]:
        # Over the global cap: keep already-tracked products first, then the newest additions.
        prev = set(previous)
        out = [u for u in out if u in prev] + [u for u in out if u not in prev]
        out = out[: cfg["cap"]]
    return out


def main(names):
    os.makedirs(os.path.join(HERE, "targets"), exist_ok=True)
    for name in names or SHOPS:
        cfg = SHOPS[name]
        urls = robots_filter(product_urls(cfg), cfg)
        path = os.path.join(HERE, "targets", f"{name}.txt")
        previous = [u.strip() for u in open(path)] if os.path.exists(path) else []
        chosen = select(urls, cfg, previous)
        with open(path, "w") as f:
            f.write("\n".join(chosen) + "\n")
        print(f"{name}: {len(urls)} sitemap urls -> {len(chosen)} targets")


if __name__ == "__main__":
    main(sys.argv[1:])
