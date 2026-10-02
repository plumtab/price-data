"""Shared helpers for the price collector: polite HTTP fetching and JSON-LD offer parsing."""
import gzip
import html as htmllib
import json
import re
import time
import urllib.request
import urllib.error

USER_AGENT = "PlumtabPriceBot/0.1 (+https://plumtab.github.io/price-data/bot.html; plumtab.studio@gmail.com)"
TIMEOUT = 30


def fetch(url, retries=2):
    """GET a URL and return (status, text). Retries on network errors and 5xx/429 with backoff."""
    last = (0, "")
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept-Encoding": "gzip",
            "Accept-Language": "da-DK,da;q=0.9,en;q=0.5",
        })
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                body = r.read()
                if r.headers.get("Content-Encoding") == "gzip" or body[:2] == b"\x1f\x8b":
                    body = gzip.decompress(body)
                return r.status, body.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last = (e.code, "")
            if e.code not in (429, 500, 502, 503, 504):
                return last
            retry_after = e.headers.get("Retry-After") if e.headers else None
            if retry_after and retry_after.isdigit():
                time.sleep(min(int(retry_after), 60))
                continue
        except Exception:
            last = (0, "")
        time.sleep(5 * (attempt + 1))
    return last


def sitemap_locs(xml):
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)


_LD_RE = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S)


def _num(x):
    try:
        return round(float(str(x).replace(",", ".")), 2)
    except (TypeError, ValueError):
        return None


_STRIKE_RE = re.compile(r'class="strike-through list[^"]*".{0,400}?content="([\d.]+)"', re.S)
_SALEDATE_RE = re.compile(r'(?:saledateinfo">\s*Gælder|Tilbud(?:det)? gælder fra(?: d\.)?)\s*(\d{1,2})/(\d{1,2})')


def parse_html_extras(html):
    """Shop-rendered details not in JSON-LD: a strikethrough list price (Magasin) and a printed offer start ("dd/mm")."""
    out = {}
    m = _STRIKE_RE.search(html)
    if m:
        out["list_price"] = _num(m.group(1))
    m = _SALEDATE_RE.search(html)
    if m:
        out["sale_from"] = f"{int(m.group(1)):02d}/{int(m.group(2)):02d}"
    return out


def parse_product(html):
    """Extract the first schema.org Product with an Offer from JSON-LD.

    Returns dict(name, price, currency, ean, availability, list_price) or None.
    list_price is the shop's own strikethrough / "before" price when published
    (priceSpecification with priceType StrikethroughPrice/ListPrice).
    """
    for m in _LD_RE.finditer(html):
        try:
            data = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
                continue
            if not isinstance(node, dict):
                continue
            offers = node.get("offers")
            if offers is not None:
                offer = offers[0] if isinstance(offers, list) and offers else offers
                if isinstance(offer, dict):
                    price = _num(offer.get("price") or offer.get("lowPrice"))
                    if price is not None:
                        list_price = None
                        specs = offer.get("priceSpecification") or []
                        for spec in specs if isinstance(specs, list) else [specs]:
                            if isinstance(spec, dict) and str(spec.get("priceType", "")).endswith(("StrikethroughPrice", "ListPrice")):
                                list_price = _num(spec.get("price"))
                        ean = node.get("gtin13") or node.get("gtin") or node.get("gtin12") or node.get("gtin14") or node.get("ean")
                        avail = str(offer.get("availability", "")).rsplit("/", 1)[-1] or None
                        extras = parse_html_extras(html)
                        if list_price is None and extras.get("list_price") and extras["list_price"] > price:
                            list_price = extras["list_price"]
                        return {
                            "name": htmllib.unescape(node.get("name") or "")[:200],
                            "price": price,
                            "currency": offer.get("priceCurrency"),
                            "ean": str(ean) if ean else None,
                            "sku": str(node.get("sku")) if node.get("sku") else None,
                            "availability": avail,
                            "list_price": list_price,
                            "sale_from": extras.get("sale_from"),
                        }
            stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
    return None
