# Copyright (c) 2025
# Gautam Jajoo <f20201638@pilani.bits-pilani.ac.in>

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

def duplicate_element(original_html, child_id, new_id=None, attributes={}):
    """
    Duplicates an element in an HTML string based on its child's ID

    Args:
        original_html: The original HTML string.
        child_id: The ID of the child element used to identify the element to duplicate.
        new_id: The new ID for the duplicated element (optional).
        attributes: A dictionary of attributes to modify in the duplicated element.

    Returns:
        The modified HTML string with the duplicated element.
    """
    soup = BeautifulSoup(original_html, 'lxml')
    child_element = soup.find(id=child_id)
    if child_element:
        element_to_duplicate = child_element.parent
        if element_to_duplicate:
            duplicated_element = copy.copy(element_to_duplicate)
            if new_id:
                duplicated_element['id'] = new_id
            for attribute, value in attributes.items():
                duplicated_element[attribute] = value
            element_to_duplicate.insert_after(duplicated_element)

    modified_html = str(soup)
    return modified_html
