#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Amazon Japan page-snapshot price fetch (the Skill's 4th data source, replacing the abandoned PA-API).

Why: direct Amazon JP product pages return HTTP 200 but only a ~3.8KB anti-bot shell (no title, no price).
This script uses local proxy + browser UA + English `/-/en/` path + destination-site cookies to retrieve
the full page (~370KB) and parse it.

Usage:
  python3 amazon_jp_snapshot.py --asin B0G56GGKKK
  python3 amazon_jp_snapshot.py --url "https://www.amazon.co.jp/-/en/dp/B0G56GGKKK"
  python3 amazon_jp_snapshot.py --bestsellers toys --limit 5     # random/bestseller sampling
  python3 amazon_jp_snapshot.py --asin B0GGRD4729 --no-proxy     # skip proxy

Output JSON: status (current/empty/unavailable) + code + price/title/rating/rank/stock.
"""
import argparse
import json
import re

from _common import JsbError, http_request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
    "Accept-Encoding": "identity",
    "Cache-Control": "no-cache",
    "Connection": "close",
    # render as the Japan site (JPY pricing; Japanese/English titles both fine)
    "Cookie": "lc-acbjp=en_US; i18n-prefs=JPY; sp-cdn=\"L5Z9:JP\"",
}

ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})")


def _text(html, pattern, group=1, flags=re.S):
    m = re.search(pattern, html, flags)
    if not m:
        return None
    return " ".join(m.group(group).split())


def parse_price(html):
    """Find the price only inside the main buy-box scope; never pass off any a-price elsewhere on the page.

    Amazon JP pages mix in many carousel/recommendation prices (a real page had ¥2,021 / ¥3,313 / ¥8,716);
    a global first-match regex would yield a fake price unrelated to the item — exactly what the
    provenance constraint is meant to prevent.
    """
    # 1) apex_desktop: the block containing the main buy-box price (most trustworthy)
    i = html.find('id="apex_desktop"')
    scope = html[i:i + 12000] if i > 0 else ""
    m = re.search(r'a-offscreen">\s*(?:¥|￥|JPY\s*)\s*([\d,]{3,})', scope)
    if m:
        return int(m.group(1).replace(",", "")), "apex_desktop"

    # 2) corePrice block
    block = re.search(r'id="corePrice[^"]*"(.*?)id="availability"', html, re.S)
    if block:
        m = re.search(r'a-offscreen">\s*(?:¥|￥|JPY\s*)\s*([\d,]{3,})', block.group(1))
        if m:
            return int(m.group(1).replace(",", "")), "core_price_block"

    # 3) page-embedded JSON (present in some variants)
    m = re.search(r'"priceAmount"\s*:\s*(\d+)', html)
    if m:
        return int(m.group(1)), "priceAmount_json"

    return None, None


def parse_item(html, asin):
    price, price_src = parse_price(html)
    return {
        "asin": asin,
        "title": _text(html, r'id="productTitle"[^>]*>(.*?)</span>'),
        "price_jpy": price,
        "price_source": price_src,
        "rating": _text(html, r'"ratingValue"\s*:\s*"?([0-9.]+)')
                  or _text(html, r'a-icon-alt">\s*([0-9.]+) out of 5'),
        "reviews": _text(html, r'"reviewCount"\s*:\s*(\d+)')
                   or _text(html, r'id="acrCustomerReviewText"[^>]*>([\d,]+)'),
        "availability": _text(html, r'id="availability".*?<span[^>]*>(.*?)</span>'),
        "best_seller_rank": _text(html, r'Best Sellers Rank.*?#([\d,]+) in ([^<(]+)', group=0),
        "seller": _text(html, r'id="sellerProfileTriggerId"[^>]*>(.*?)</a>'),
        "condition": "New (Amazon JP main buy-box price)",
        "url": f"https://www.amazon.co.jp/dp/{asin}/",
        "source": "amazon_jp_page_snapshot",
    }


def snapshot(asin, no_proxy=False):
    url = f"https://www.amazon.co.jp/-/en/dp/{asin}/"
    try:
        status, html = http_request("GET", url, headers=HEADERS, use_proxy=not no_proxy, timeout=25)
    except JsbError as e:
        return {"status": "unavailable", "code": "NET_UNREACHABLE", "asin": asin,
                "reason": str(e), "hint": "Check that local proxy 127.0.0.1:7890 is up"}

    if status != 200:
        return {"status": "unavailable", "code": "HTTP_ERROR", "asin": asin,
                "http_status": status, "reason": html[:120]}

    if len(html) < 50000:
        return {"status": "unavailable", "code": "ANTIBOT_SHELL", "asin": asin,
                "page_bytes": len(html),
                "reason": "hit an anti-bot shell page (<50KB), no valid item info",
                "hint": "make sure the proxy works and UA + /-/en/ path take effect; or retry later"}

    item = parse_item(html, asin)
    item["status"] = "current" if item["price_jpy"] else "empty"
    item["code"] = None if item["price_jpy"] else "PRICE_MISSING"
    item["page_bytes"] = len(html)
    if not item["price_jpy"]:
        item["reason"] = ("page fetched but the main buy-box price is injected by front-end JS (server HTML is a skeleton); "
                          "HTTP snapshot cannot get it — have the Agent render the page in a browser to read the price, "
                          "or compare via Rakuten RWS instead. Title/rating/rank metadata are still usable.")
    return item


def bestsellers(category="toys", limit=5, no_proxy=False):
    """Pull some ASINs from Amazon JP bestsellers for random sampling tests."""
    url = f"https://www.amazon.co.jp/-/en/gp/bestsellers/{category}/"
    try:
        status, html = http_request("GET", url, headers=HEADERS, use_proxy=not no_proxy, timeout=25)
    except JsbError as e:
        return {"status": "unavailable", "code": "NET_UNREACHABLE", "reason": str(e)}
    if status != 200 or len(html) < 50000:
        return {"status": "unavailable", "code": "ANTIBOT_SHELL" if status == 200 else "HTTP_ERROR",
                "http_status": status, "page_bytes": len(html)}

    seen, out = set(), []
    for asin in ASIN_RE.findall(html):
        if asin in seen:
            continue
        seen.add(asin)
        out.append(asin)
        if len(out) >= limit:
            break
    return {"status": "current" if out else "empty", "category": category,
            "asins": out, "page_bytes": len(html)}


def main():
    ap = argparse.ArgumentParser(description="Amazon Japan page-snapshot price fetch")
    ap.add_argument("--asin")
    ap.add_argument("--url")
    ap.add_argument("--bestsellers", help="category, e.g. toys / electronics / kitchen")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--no-proxy", action="store_true")
    args = ap.parse_args()

    if args.bestsellers:
        result = bestsellers(args.bestsellers, args.limit, args.no_proxy)
    else:
        asin = args.asin
        if not asin and args.url:
            m = ASIN_RE.search(args.url)
            asin = m.group(1) if m else None
        if not asin:
            print(json.dumps({"status": "error", "code": "BAD_INPUT",
                              "error": "one of --asin / --url / --bestsellers is required"},
                             ensure_ascii=False, indent=2))
            raise SystemExit(1)
        result = snapshot(asin, args.no_proxy)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
