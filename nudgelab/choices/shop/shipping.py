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
import copy

def add_shipping(original_html, shipping_options):
    """
    shipping_options: list of lists of (arrival time in days (str), shipping price (str), url to new page)
    ex. [["3", "Free", "[url]"], ["1", "$25", "[url]"]]
    """
    soup = BeautifulSoup(original_html, 'lxml')

    #create shipping options
    shipping = soup.new_tag("label",{"class":"label"})
    shipping.string = "Choose Shipping Option:"

    for arrival_time, price, url in shipping_options:
        option = soup.new_tag("div",{"class":"shipping-option"})

        link = soup.new_tag("a", {"class":"shipping-button"}, href=url)

        unit = "day" if arrival_time == "1" else "days"
        link.string = f"{price} Shipping - Arrives in {arrival_time} {unit}."

        option.append(link)

        shipping.append(option)

    #insert shipping options
    add_to_cart = soup.find("div",{"class":"box-tocart"})
    add_to_cart.insert_before(shipping)

    modified_html = str(soup)
    return modified_html

def new_shipping_pages(original_html, shipping_price, arrival_time, product_id):
    """
    shipping_price: cost of shipping (float)
    arrival_time: number of days to ship (int)
    """
    soup = BeautifulSoup(original_html, 'lxml')

    #change price to include shipping cost
    price_element = soup.find(id=f'product-price-{product_id}')

    old_price = float(price_element['data-price-amount'])

    if price_element and price_element.has_attr('data-price-amount'):
        price_element['data-price-amount'] = str(old_price+shipping_price)
        price_text_element = price_element.find('span', class_='price')
        if price_text_element:
            price_text_element.string = f'${float(old_price+shipping_price):.2f}'

    meta_price_element = soup.find('meta', {'itemprop': 'price'})
    if meta_price_element:
        meta_price_element['content'] = str(old_price+shipping_price)

    #label with shipping option selected
    shipping = soup.new_tag("label",{"class":"label"})
    unit = "day" if arrival_time == 1 else "days" #says "day" instead of "days" if shipping time is 1 day
    shipping_price = "Free" if shipping_price == 0 else f"${shipping_price}" #says "Free" if shipping price is $0
    shipping.string = shipping_price + f" Shipping Included - Arrives in {arrival_time} {unit}."

    add_to_cart = soup.find("div",{"class":"box-tocart"})
    add_to_cart.insert_before(shipping)

    modified_html = str(soup)
    return modified_html
