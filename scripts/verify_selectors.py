#!/usr/bin/env python3
"""A1 Phase 1: verify data_quality.py selectors against the live store.

Fetches product pages from our WebArena shopping deployment and checks that
every CSS target used by abxlab/choices/shop/data_quality.py exists in this
Magento build, then dry-runs each intervention function and reports its
"applied" metadata plus a sanity diff.

Usage:
    python scripts/verify_selectors.py http://<PUBLIC_IP>:7770/ [product_url ...]

If no product URLs are given, a few are discovered from the homepage.
"""

import sys
import re
import json
import urllib.request

sys.path.insert(0, ".")  # run from repo root
from bs4 import BeautifulSoup
from abxlab.choices.shop import data_quality


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def discover_products(base_url: str, n: int = 3) -> list[str]:
    """Pull product URLs from the homepage (product links end in .html)."""
    html = fetch(base_url)
    soup = BeautifulSoup(html, "lxml")
    urls, seen = [], set()
    for a in soup.find_all("a", href=re.compile(r"\.html$")):
        href = a["href"]
        if href not in seen and "/catalogsearch" not in href:
            seen.add(href)
            urls.append(href)
        if len(urls) >= n:
            break
    return urls


def check_page(url: str) -> None:
    print(f"\n=== {url}")
    html = fetch(url)
    soup = BeautifulSoup(html, "lxml")

    checks = {
        "attribute table (#productDetails_detailBullets_sections1 or Luma class)":
            soup.find("table", id="productDetails_detailBullets_sections1")
            or soup.find("table", class_="data table additional-attributes"),
        "description block (div.product.attribute.description)":
            soup.find("div", class_="product attribute description"),
        "gallery init (script x-magento-init w/ mage/gallery/gallery)":
            next((s for s in soup.find_all("script", type="text/x-magento-init")
                  if s.string and "mage/gallery/gallery" in s.string), None),
        "JSON-LD (script application/ld+json)":
            soup.find("script", type="application/ld+json"),
        "microdata (any itemprop)":
            soup.find(attrs={"itemprop": True}),
        "price box (span.price)":
            soup.find("span", class_="price"),
        "reviews summary (div.product-reviews-summary)":
            soup.find("div", class_="product-reviews-summary"),
    }
    for label, found in checks.items():
        print(f"  [{'OK ' if found else 'MISS'}] {label}")

    print("  --- dry-running interventions ---")
    runs = [
        ("attributes keep=3", data_quality.attributes, {"keep": 3}),
        ("attributes keep=0", data_quality.attributes, {"keep": 0}),
        ("structured_data strip", data_quality.structured_data, {"mode": "strip"}),
        ("description remove", data_quality.description, {"mode": "remove"}),
        ("description replace", data_quality.description,
         {"mode": "replace", "value": "Test description.\n\nSecond paragraph."}),
        ("images keep=1", data_quality.images, {"keep": 1}),
    ]
    for label, func, args in runs:
        try:
            out, meta = func(html, **args)
            delta = len(str(html)) - len(out)
            print(f"  [{'OK ' if meta.get('applied') else 'NOOP'}] {label}: "
                  f"meta={json.dumps(meta)} bytes_delta={delta}")
        except Exception as e:
            print(f"  [ERR ] {label}: {type(e).__name__}: {e}")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    base_url = sys.argv[1].rstrip("/") + "/"
    product_urls = sys.argv[2:]

    print(f"Store: {base_url}")
    code = urllib.request.urlopen(
        urllib.request.Request(base_url, headers={"User-Agent": "Mozilla/5.0"}),
        timeout=30).status
    print(f"Homepage HTTP {code}")

    if not product_urls:
        product_urls = discover_products(base_url)
        print(f"Discovered {len(product_urls)} product pages")

    for url in product_urls:
        check_page(url)

    print("\nDone. Every selector row should be OK and every dry-run 'applied'.")
    print("MISS/NOOP rows mean data_quality.py defaults need adjusting for this build.")


if __name__ == "__main__":
    main()
