# Copyright (c) 2025
# Abigail Xu <agxu@mit.edu>

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
import random
import re

def add_bestseller_tag_random(original_html):
    """
    Labels random product with "best seller" tag
    OR labels product specified by its placement on browsing page (e.g., first product on page)
    """
    soup = BeautifulSoup(original_html, 'lxml')

    products = soup.find_all("div",{"class":"product details product-item-details"})

    # number = random.randint(0, len(products)-1)
    number = 0 #first product on page

    bestseller = products[number]

    span_tag = soup.new_tag("span",attrs={"class":"bestseller"})
    span_tag['style'] = "color: red;"
    span_tag.string = "BEST SELLER"

    bestseller.insert(0,span_tag)

    modified_html = str(soup)
    return modified_html

def add_bestseller_tag_name(original_html, product_name):
    """
    Labels specified product with "best seller" tag
    Product identified by product name
    """
    soup = BeautifulSoup(original_html, 'lxml')

    products = soup.find_all("a",{"class":"product-item-link"})

    bestseller = None
    for product in products:
        if product_name in product.string:
            bestseller = product
            break

    span_tag = soup.new_tag("span",attrs={"class":"bestseller"})
    span_tag['style'] = "color: red;"
    span_tag.string = "BEST SELLER"

    bestseller.insert_before(span_tag)

    modified_html = str(soup)
    return modified_html

def add_bestseller_tag_url(original_html, url):
    """
    Labels specified product with "best seller" tag
    Product identified by product url
    """
    soup = BeautifulSoup(original_html, 'lxml')

    bestseller = soup.find("a",{"href":url})

    span_tag = soup.new_tag("span",attrs={"class":"bestseller"})
    span_tag['style'] = "color: red;"
    span_tag.string = "BEST SELLER"

    bestseller.insert_after(span_tag)

    modified_html = str(soup)
    return modified_html

def add_number_sold(original_html):
    """
    Labels all products with {random number} sold in past month
    Labels product with most sold as 'best seller'
    """
    soup = BeautifulSoup(original_html, 'lxml')

    products = soup.find_all("div",{"class":"product details product-item-details"})

    most = float("-inf")
    bestsellers = []

    #label num sold in past month
    for product in products:
        number_sold_tag = soup.new_tag("span",attrs={"class":"number-sold"})
        number_sold_tag['style'] = "font-style:italic;"

        number = random.randint(0,100)
        number_sold_tag.string = f"{number} sold in the past month"

        product.find("div",{"class":"price-box price-final_price"}).insert_before(number_sold_tag)

        if number > most:
            bestsellers = [product]
            most = number
        elif number == most:
            bestsellers.append(product)

    #label bestseller
    for bestseller in bestsellers:
        span_tag = soup.new_tag("span",attrs={"class":"bestseller"})
        span_tag['style'] = "color: red; font-size: 15px"
        span_tag.string = "BEST SELLER"

        bestseller.insert(0,span_tag)


    modified_html = str(soup)
    return modified_html
