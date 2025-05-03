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

def replace_product_title(original_html, new_path, new_title):
    soup = BeautifulSoup(original_html, "lxml")

    for a_tag in soup.find_all("a", href=True):
        a_tag["href"] = new_path

    old_title = None
    for page_title in soup.find_all("h1", class_="page-title"):
        span_tag = page_title.find("span", class_="base")
        if span_tag:
            old_title = span_tag.string
            span_tag.string = new_title

    if old_title:
        for element in soup.find_all(text=True):
            if old_title in element:
                element.replace_with(element.replace(old_title, new_title))

    modified_html = str(soup)


    return modified_html
