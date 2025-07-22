import functools
import requests
import lzma
import base64
from bs4 import BeautifulSoup
from enum import Enum

# ============================================
# Utilities and Helper Functions
# ===========================================

class PageType(Enum):
    PRODUCT = "product"
    CATEGORY = "category"
    HOME = "home"
    OTHER = "other"


@functools.lru_cache(maxsize=128)
def get_html(url: str) -> str:
    # Fetch HTML content of the page, avoiding redundant repeated requests by caching the result
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch the page: {response.status_code}")
    return response.text


def get_soup(html: str) -> BeautifulSoup:
    # Parse content using BeautifulSoup
    return BeautifulSoup(html, "html.parser")


def get_pagetype(soup: BeautifulSoup) -> PageType:
    # Switch for page-type detection
    if soup.find("meta", property="og:type", content="product"):
        return PageType.PRODUCT

    if soup.select_one("div.sidebar-main div.filter"):
        return PageType.CATEGORY

    if soup.title and soup.title.string.strip() == "One Stop Market":
        return PageType.HOME

    return PageType.OTHER


def with_soup(func):
    # Decorator to fetch HTML and parse it into a BeautifulSoup object before passing it to a given function
    @functools.wraps(func)
    def wrapper(url: str, *args, **kwargs):
        html = get_html(url)
        soup = get_soup(html)
        return func(soup, *args, **kwargs)

    return wrapper


# ============================================
# Product Page Metadata-Extraction Functions
# ============================================

@with_soup
def get_price_for_product(soup: BeautifulSoup) -> str:
    if get_pagetype(soup) != PageType.PRODUCT:
        raise Exception("Not a product page")

    price = soup.find("span", class_="price")
    if price:
        return price.get_text(strip=True)
    else:
        raise Exception("Price not found on specified page")


@with_soup
def get_rating_for_product(soup: BeautifulSoup) -> str:
    if get_pagetype(soup) != PageType.PRODUCT:
        raise Exception("Not a product page")

    rating = soup.find("div", class_="rating-result")["title"]

    if rating:
        return rating
    else:
        raise Exception("Rating not found on specified page")


@with_soup
def get_name_for_product(soup: BeautifulSoup) -> str:
    if get_pagetype(soup) != PageType.PRODUCT:
        raise Exception("Not a product page")

    name = soup.find("h1", class_="page-title")
    if name:
        return name.get_text(strip=True)
    else:
        raise Exception("Product name not found on specified page")


@with_soup
def get_all_product_metadata(soup: BeautifulSoup) -> dict:
    if get_pagetype(soup) != PageType.PRODUCT:
        raise Exception("Not a product page")

    metadata = {
        "name": get_name_for_product(soup),
        "price": get_price_for_product(soup),
        "rating": get_rating_for_product(soup),
        "has_options": has_multiple_options(soup),
    }

    return metadata


@with_soup
def has_multiple_options(soup: BeautifulSoup) -> bool:
    """
    Check if a product has multiple options.
    """
    return soup.select_one("div.product-options-wrapper") is not None


@with_soup
def get_all_product_links(soup: BeautifulSoup) -> list:
    if get_pagetype(soup) != PageType.CATEGORY:
        raise Exception("Not a category page")

    product_links = []

    for item in soup.select("li.item.product.product-item"):
        link = item.find("a", class_="product-item-link")
        if link:
            product_links.append(link["href"])
        else:
            raise Exception("Product link not found")

    return product_links


@with_soup
def get_all_category_metadata(soup: BeautifulSoup) -> list:
    if get_pagetype(soup) != PageType.CATEGORY:
        raise Exception("Not a category page")

    metadata = []
    product_links = get_all_product_links(soup)

    for link in product_links:
        metadata.append(get_all_product_metadata(link))

    return metadata

# ============================================
# Functions for HTML Compression & Decompression
# ============================================

def compress_html(html_content: str) -> str:
    """Compress HTML content and return base64 encoded string."""
    html_bytes = html_content.encode("utf-8")
    compressed = lzma.compress(html_bytes, preset=9)
    return base64.b64encode(compressed).decode("ascii")

def decompress_html(compressed_data: str) -> str:
    """Decompress base64 encoded compressed HTML."""
    compressed_bytes = base64.b64decode(compressed_data.encode("ascii"))
    html_bytes = lzma.decompress(compressed_bytes)
    return html_bytes.decode("utf-8")
