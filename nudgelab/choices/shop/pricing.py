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

from bs4 import BeautifulSoup

def replace_price(original_html, product_id, new_price):
    soup = BeautifulSoup(original_html, 'lxml')
    price_element = soup.find(id=f'product-price-{product_id}')

    if price_element and price_element.has_attr('data-price-amount'):
        price_element['data-price-amount'] = str(new_price)
        price_text_element = price_element.find('span', class_='price')
        if price_text_element:
            price_text_element.string = f'${float(new_price):.2f}'

    meta_price_element = soup.find('meta', {'itemprop': 'price'})
    if meta_price_element:
        meta_price_element['content'] = str(new_price)

    modified_html = str(soup)
    return modified_html

def add_price_descriptor(original_html, product_id, sale_indicator):
    #inserts StaticText next to price. Can be used to indicate sales, "Buy One Get One Free", "Was $100", delivery time, free delivery, etc.

    soup = BeautifulSoup(original_html, 'lxml')

    existing_input = soup.find('span', {'id': f'product-price-{product_id}'})

    if existing_input:
        new_span = soup.new_tag('span')
        new_span.string = sale_indicator
        existing_input.insert_after(new_span)

    return str(soup)
