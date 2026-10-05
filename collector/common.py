"""Shared helpers for the price collector: polite HTTP fetching and JSON-LD offer parsing."""
import gzip
import html as htmllib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "ForprisBot/0.1 (+https://plumtab.github.io/price-data/bot.html; plumtab.studio@gmail.com)"
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


# Magasin writes the classes in either order ("strike-through list b-price__el-type" or "b-price__el-type strike-through
# list"); until Oct 5 only the first was read, which missed ~70 % of its Sep 23 - Oct 4 campaign. Pages without an offer
# have no strike-through at all (checked), so recommendations can't leak in.
_STRIKE_RE = re.compile(r'class="[^"]*\bstrike-through list\b[^"]*".{0,400}?content="([\d.]+)"', re.S)
_SALEDATE_RE = re.compile(r'(?:saledateinfo">\s*Gælder|Tilbud(?:det)? gælder fra(?: d\.)?)\s*(\d{1,2})/(\d{1,2})')


_NUXT_RE = re.compile(r"window\.__NUXT__=function\(([^)]*)\)\{")
_JS_LIT = {"null": None, "!0": True, "!1": False, "void 0": None}


def _js_args(s):
    """Split a JS argument list at top-level commas (strings, arrays and objects kept whole)."""
    out, cur, depth, q, esc = [], "", 0, None, False
    for ch in s:
        if q:
            cur += ch
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch
        elif ch in "[{(":
            depth += 1
        elif ch in "]})":
            depth -= 1
        elif ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
            continue
        cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def salling_promotion(html):
    """Bilka/Føtex (Salling Group) keep price data in a Nuxt payload, not in JSON-LD.

    Returns {"list_price": float, "start": "YYYY-MM-DD"} only when the page shows a before-price, else None.
    Checked against the live pages (Oct 5): a time-limited campaign shows "Spar 30% · Før 1.300,-"; an all-year
    campaign shows "SKARP PRIS" with no before-price. Member prices and "always low price" are left out (D-015).
    """
    m = _NUXT_RE.search(html)
    if not m:
        return None
    end = html.find("</script>", m.end())
    body = html[m.end():end]
    k = body.rfind("}(")
    if k < 0:
        return None
    values = dict(zip(m.group(1).split(","), (_JS_LIT.get(a, a) for a in _js_args(body[k + 2: body.rfind(")")]))))
    body = body[:k]

    def field(name):
        f = re.search(r"[,{]" + name + r":(\"(?:[^\"\\\\]|\\\\.)*\"|[^,}\]]+)", body)
        if not f:
            return None
        raw = f.group(1)
        v = values.get(raw, _JS_LIT.get(raw, raw)) if re.fullmatch(r"[A-Za-z_$]{1,3}|!0|!1|null|void 0", raw) else raw
        return v.strip('"') if isinstance(v, str) else v

    lp, sp = _num(field("list_price")), _num(field("sales_price_generated"))
    start, stop = field("promotion_start_date"), field("promotion_end_date")
    if lp is None or sp is None or lp <= sp + 0.5 or not start or not stop:
        return None
    if field("is_always_low_price") is True or field("has_membership_promotion") is True:
        return None
    try:
        import datetime as _dt
        span = (_dt.date.fromisoformat(stop) - _dt.date.fromisoformat(start)).days
    except ValueError:
        return None
    if span > 62:  # all-year "skarp pris": no before-price is shown
        return None
    return {"list_price": lp, "start": start}


def jysk_promotion(html, url):
    """Jysk (Next.js) puts the product's price block in the page data, with explicit display flags:
    formatted.beforePricePrimary + beforePricePrimaryShow + beforePricePrimaryTextIndicator ("lowestPrice" =
    Jysk's own "Laveste pris 30 dage: …", "normalPrice" = "Normalpris: …"). Only a shown before-price counts, and
    never a club (membership) price. Returns the shown before-price, or None."""
    page = _path(url)
    if not page:
        return None
    h = html.replace('\\"', '"')
    i = h.find('"url":"' + page + '","title":')
    if i < 0:
        i = h.lower().find('"url":"' + page)
    if i < 0:
        return None
    m = re.search(r'"price":\{"unformatted":(\{[^{}]*\}),"formatted":(\{[^{}]*\})', h[i:i + 3000])
    if not m:
        return None
    try:
        unf, fmt = json.loads(m.group(1)), json.loads(m.group(2))
    except json.JSONDecodeError:
        return None
    if not fmt.get("beforePricePrimaryShow") or unf.get("membership") is not None or fmt.get("membership") is not None:
        return None
    n = re.match(r"\s*([\d.]+(?:,\d+)?)", fmt.get("beforePricePrimary") or "")
    return _num(n.group(1).replace(".", "")) if n else None


def parse_html_extras(html, url=None):
    """Shop-rendered details not in JSON-LD: a strikethrough list price (Magasin) and a printed offer start ("dd/mm")."""
    out = {}
    m = _STRIKE_RE.search(html)
    if m:
        out["list_price"] = _num(m.group(1))
    m = _SALEDATE_RE.search(html)
    if m:
        out["sale_from"] = f"{int(m.group(1)):02d}/{int(m.group(2)):02d}"
    # Føtex only: Bilka keeps a list_price in the same data but doesn't show it (helper checked the live pages,
    # Oct 5: a 2–8 Oct campaign on bilka.dk shows "SE HER", no "Før"; foetex.dk shows "Spar 30% · Før 1.300,-").
    if url and "jysk.dk" in url:
        jp = jysk_promotion(html, url)
        if jp:
            out["list_price"] = jp
    sp = salling_promotion(html) if url and "foetex.dk" in url else None
    if sp:
        out["list_price"] = sp["list_price"]
        out["sale_from"] = f"{sp['start'][8:10]}/{sp['start'][5:7]}"
    return out


def _offer_nodes(node):
    """Yield every JSON-LD node that has offers, in document order (a ProductGroup's variants included)."""
    if isinstance(node, list):
        for x in node:
            yield from _offer_nodes(x)
    elif isinstance(node, dict):
        if node.get("offers") is not None:
            yield node
        for v in node.values():
            if isinstance(v, (dict, list)):
                yield from _offer_nodes(v)


def _path(u, base=None):
    """URL path for matching a variant to the page: no query, no trailing slash, lower case."""
    if not u:
        return None
    return urllib.parse.urlsplit(urllib.parse.urljoin(base or "", str(u))).path.rstrip("/").lower() or "/"


def parse_product(html, url=None):
    """Extract the schema.org Product with an Offer from JSON-LD.

    Pages with several variants (a ProductGroup, e.g. Matas sizes) list one Product per variant. We take
    the variant whose own URL is the page URL, else the first product in document order.

    Returns dict(name, price, currency, ean, sku, availability, list_price, sale_from) or None.
    list_price is the shop's own strikethrough / "before" price when published
    (priceSpecification with priceType StrikethroughPrice/ListPrice).
    """
    page = _path(url)
    candidates = []
    for m in _LD_RE.finditer(html):
        try:
            data = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            continue
        for node in _offer_nodes(data):
            offers = node["offers"]
            offer = offers[0] if isinstance(offers, list) and offers else offers
            if not isinstance(offer, dict):
                continue
            price = _num(offer.get("price") or offer.get("lowPrice"))
            if price is None:
                continue
            match = page is not None and page in (_path(node.get("url"), url), _path(offer.get("url"), url))
            candidates.append((match, node, offer, price))
    if not candidates:
        return None
    match, node, offer, price = next((c for c in candidates if c[0]), candidates[0])
    list_price = None
    specs = offer.get("priceSpecification") or []
    for spec in specs if isinstance(specs, list) else [specs]:
        if isinstance(spec, dict) and str(spec.get("priceType", "")).endswith(("StrikethroughPrice", "ListPrice")):
            list_price = _num(spec.get("price"))
    ean = node.get("gtin13") or node.get("gtin") or node.get("gtin12") or node.get("gtin14") or node.get("ean")
    avail = str(offer.get("availability", "")).rsplit("/", 1)[-1] or None
    extras = parse_html_extras(html, url)
    if list_price is None and extras.get("list_price") and extras["list_price"] > price:
        list_price = extras["list_price"]
    # Magasin-style pages: one Product, but the offer is for a specific size whose own URL differs from the page.
    # Record that size, so a size switch is never mistaken for a price change.
    variant = None
    offer_path = _path(offer.get("url"), url)
    if page and offer_path and offer_path != page:
        variant = offer_path.rsplit("/", 1)[-1].split(".")[0][:40] or None
    return {
        "name": htmllib.unescape(node.get("name") or "")[:200],
        "price": price,
        "currency": offer.get("priceCurrency"),
        "ean": str(ean) if ean else None,
        "sku": str(node.get("sku")) if node.get("sku") else None,
        "availability": avail,
        "list_price": list_price,
        "sale_from": extras.get("sale_from"),
        "variant": variant,
    }
