# Copyright (c) 2025
# Maya Shaked <mshaked@mit.edu>

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

import random
from bs4 import BeautifulSoup


def change_stock(original_html, num_left=None):
    soup = BeautifulSoup(original_html, "lxml")

    if num_left is None:
        num_left = random.randint(1, 100)

    product_info_div = soup.find(class_="product-info-stock-sku")
    if product_info_div:
        stock_div = product_info_div.find(class_="stock available")
        if stock_div:
            if int(num_left) == 0:
                stock_div.string = "SOLD OUT"
            else:
                new_info = soup.new_tag("div", **{"class": "stock-info"})
                new_info.string = f"only {num_left} left"
                stock_div.append(new_info)

    return str(soup)


def display_num_in_cart(original_html, num_left, num_in_cart=None):
    """
    Displays how many people currently have the item in the cart. Can be
    configured to always be greater than or always be less than num_left.
    """
    soup = BeautifulSoup(original_html, "lxml")

    if int(num_left) > 0:
        add_form_div = soup.find(class_="product-add-form")
        if add_form_div:
            if num_in_cart is None:
                num_left = int(num_left)
                num_in_cart = random.randint(0, max(0, num_left))

            cart_info = soup.new_tag(
                "div",
                **{
                    "class": "cart-info",
                    "style": "font-size: 18px; color: red; margin-top: 15px;",
                },
            )
            cart_info.string = f" {num_in_cart} shoppers have this item in their cart"
            add_form_div.insert_before(cart_info)

    return str(soup)
