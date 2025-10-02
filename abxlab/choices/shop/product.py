# Copyright (c) 2025
# Manuel Cherep <mcherep@mit.edu>
# Nikhil Singh <nikhil.u.singh@dartmouth.edu>

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
This module contains interventions to modify product pages from config files.
"""

from bs4 import BeautifulSoup


def subtitle(
    original_html: bytes,
    value: str,
    elem_id: str = "page-title-wrapper product"
) -> tuple[str, dict]:
    """Inserts a subtitle below the product title."""

    soup = BeautifulSoup(original_html, "lxml")

    element = soup.find("div", class_=elem_id)

    span_tag = soup.new_tag("h2", attrs={"class":"product-title-details",
                                         "visible":""})
    span_tag["style"] = (
        "display: inline-block; "
        "padding: 4px 8px; "
        "border: 1px solid rgb(30, 109, 182); "
        "border-radius: 12px; "
        "color: rgb(30, 109, 182); "
        "font-size: 2em;"
    )
    span_tag.string = value

    element.insert_after(span_tag)

    modified_html = str(soup)
    return modified_html, {}


def stock(
    original_html: bytes,
    value: str,
    elem_id: str = "product-info-stock-sku"
) -> tuple[str, dict]:
    """Replaces stock information for the product."""

    soup = BeautifulSoup(original_html, "lxml")

    element = soup.find("div", class_=elem_id)

    span_tag = soup.new_tag("span", attrs={"class":"product-stock-details"})
    span_tag["style"] = (
        "display: inline-block; "
        "padding: 4px 8px; "
        "margin-top: 10px; "
        "border: 1px solid rgb(30, 109, 182); "
        "border-radius: 2px; "
        "color: rgb(30, 109, 182); "
        "font-size: 0.9em;"
    )
    span_tag.string = value

    element.insert_after(span_tag)

    modified_html = str(soup)
    return modified_html, {}


def price(
    original_html: bytes,
    value: float
) -> str:
    """Replaces the product price."""

    soup = BeautifulSoup(original_html, "lxml")

    # Change price in span
    price = soup.find("span", class_="price")
    price.string = "$" + f"{value:.2f}"

    # Change data-price-amount in price-wrapper
    price_wrapper = soup.find("span", class_="price-wrapper")
    if price_wrapper:
        price_wrapper["data-price-amount"] = f"{value:.2f}"

    modified_html = str(soup)
    return modified_html, {}


def review_count(
    original_html: bytes,
    value: int
) -> str:
    """Replaces the review count for the product."""

    soup = BeautifulSoup(original_html, "lxml")

    # Change review count on the right next to rating
    review_count_ratings = soup.find("span", itemprop="reviewCount")
    if review_count_ratings:
        review_count_ratings.string = str(value)

    # Change review count in the tab at the bottom
    review_count_tab = soup.find("span", class_="counter")
    if review_count_tab:
        review_count_tab.string = str(value)

    modified_html = str(soup)
    return modified_html, {}


################################################################################
# Functions below modify the HTML without returning additional metadata
# These are useful when are called all the time (e.g. ABxLabShopTask in task.py)
################################################################################

def rating(
    original_html: bytes,
    elem_id: str = "rating-summary"
) -> str:
    """Inserts the rating explicitly in percentage to avoid confusion with the stars by default."""

    soup = BeautifulSoup(original_html, "lxml")

    rating = soup.find("div", class_="rating-result")

    if rating:
        element = soup.find("div", class_=elem_id)

        span_tag = soup.new_tag("span", attrs={"class":"product-rating-details"})
        span_tag["style"] = (
            "display: inline-block; "
            "margin-top: 4px; "
            "margin-right: 10px; "
            "color: rgb(251, 79, 31); "
        )
        span_tag.string = "Rating: " + rating["title"]

        element.insert_after(span_tag)

    modified_html = str(soup)
    return modified_html


def ablate(
    original_html: bytes,
    elems: list[str] = ["product-reviews-summary", "price-box price-final_price"]
) -> str:
    """Removes specified elements from the product page."""

    soup = BeautifulSoup(original_html, "lxml")

    for elem in elems:
        element = soup.find("div", class_=elem)
        if element:
            element.decompose()

    modified_html = str(soup)
    return modified_html
