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
This module contains interventions to modify arbitrary pages from config files.
"""

import logging
from bs4 import BeautifulSoup


def subtitle(
    original_html: bytes,
    value: str,
    elem_id: str = "title",
    insert_elem_type: str = "h2"
) -> tuple[str, dict]:
    """Inserts a subtitle below the product title."""

    soup = BeautifulSoup(original_html, "lxml")

    element = soup.find(attrs={"id": elem_id})

    logging.info(f"Found element: {element}")

    span_tag = soup.new_tag(
        insert_elem_type,
        attrs={"class":"product-title-details", "visible":""}
    )

    span_tag["style"] = (
        "display: inline-block; "
        "padding: 4px 8px; "
        "border: 1px solid rgb(30, 109, 182); "
        "border-radius: 12px; "
        "color: rgb(30, 109, 182); "
        "font-size: 1em;"
    )
    span_tag.string = value

    if element:
        element.insert_after(span_tag)
    else:
        logging.warning(f"Element with class {elem_id} not found.")

    modified_html = str(soup)
    return modified_html, {}
