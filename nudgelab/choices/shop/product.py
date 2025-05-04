# Copyright (c) 2025
# Manuel Cherep <mcherep@mit.edu>

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

from bs4 import BeautifulSoup


def subtitle(
    original_html: bytes,
    value: str,
    elem_id: str = "page-title-wrapper product"
) -> str:
    soup = BeautifulSoup(original_html, "lxml")

    element = soup.find("div", class_=elem_id)

    span_tag = soup.new_tag("span", attrs={"class":"product-title-details"})
    span_tag["style"] = (
        "display: inline-block; "
        "padding: 4px 8px; "
        "border: 1px solid rgb(30, 109, 182); "
        "border-radius: 12px; "
        "color: rgb(30, 109, 182); "
        "font-size: 0.9em;"
    )
    span_tag.string = value

    element.insert_after(span_tag)

    modified_html = str(soup)
    return modified_html


def stock(
    original_html: bytes,
    value: str,
    elem_id: str = "product-info-stock-sku"
) -> str:
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
    return modified_html


def rating(
    original_html: bytes,
    elem_id: str = "rating-summary"
) -> str:
    soup = BeautifulSoup(original_html, "lxml")

    rating = soup.find("div", class_="rating-result")["title"]
    element = soup.find("div", class_=elem_id)

    span_tag = soup.new_tag("span", attrs={"class":"product-rating-details"})
    span_tag["style"] = (
        "display: inline-block; "
        "margin-top: 4px; "
        "margin-right: 10px; "
        "color: rgb(251, 79, 31); "
    )
    span_tag.string = "(" + rating + ")"

    element.insert_after(span_tag)

    modified_html = str(soup)
    return modified_html
