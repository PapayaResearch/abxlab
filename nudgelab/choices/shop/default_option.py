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

import re
from bs4 import BeautifulSoup

def replace(original_html, elem_id, attribute, value):
    soup = BeautifulSoup(original_html, "lxml")
    element_to_replace = soup.find(id=elem_id)
    if element_to_replace and element_to_replace.has_attr(attribute):
        element_to_replace[attribute] = value

    modified_html = str(soup)
    return modified_html

def update_rating(original_html, elem_id, rating):
    # TODO: This isn't working anymore
    soup = BeautifulSoup(original_html, "lxml")

    # Find the <script> tag containing the JavaScript
    script_tag = soup.find("script", text=re.compile(elem_id))
    old_rating = script_tag.text.split("width = '")[1].split("%'")[0]

    if script_tag:
        # Modify the JavaScript code to set the new width
        updated_script = script_tag.string.replace(f"element.style.width = '{old_rating}%';",
                                                   f"element.style.width = '{rating}%';")
        script_tag.string.replace_with(updated_script)

    # Use regex to find the div with id matching 'rating-result_*'
    pattern = re.compile(r"rating-result_\d+")
    rating_div = soup.find("div", {"id": pattern})

    # Modify the content if the element is found
    if rating_div:
        # Update the title attribute
        rating_div["title"] = f"{rating}%"

        # Find the nested span with 'ratingValue' and modify its content
        rating_value_span = rating_div.find("span", {"itemprop": "ratingValue"})
        if rating_value_span:
            rating_value_span.string = str(rating)

    modified_html = str(soup)
    return modified_html

def update_reviews(original_html):
    soup = BeautifulSoup(original_html, "lxml")

    # Find all reviews
    reviews = soup.find_all("li", class_="item review-item")

    # Extract relevant details
    parsed_reviews = []
    for review in reviews:
        title = review.find("div", class_="review-title").get_text(strip=True)
        rating = review.find("span", itemprop="ratingValue").get_text(strip=True)
        author = review.find("strong", class_="review-details-value").get_text(strip=True)
        content = review.find("div", class_="review-content").get_text(strip=True)
        date = review.find("time", class_="review-details-value").get_text(strip=True)

        parsed_reviews.append({
            "title": title,
            "rating": int(rating.replace('%', '')),
            "author": author,
            "content": content,
            "date": date,
            "element": review  # Store original element for modification
        })

    # Modify Reviews
    # Example: Sort reviews by rating (highest first)
    parsed_reviews.sort(key=lambda x: x["rating"], reverse=True)

    # Example: Rename an author
    for review in parsed_reviews:
        if review["author"] == "Maria A.":
            review["author"] = "Anonymous User"
            review["element"].find("strong", class_="review-details-value").string.replace_with("Anonymous User")

    # Replace old reviews with modified ones
    modified_reviews = [review["element"] for review in parsed_reviews]
    review_list = soup.find("ol", class_="items review-items")
    review_list.clear()  # Clear existing reviews
    for review in modified_reviews:
        review_list.append(review)  # Add modified reviews

    modified_html = str(soup)
    return modified_html
