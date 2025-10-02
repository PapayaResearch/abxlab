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
This script scrapes product information from the shopping website.
"""

import os
import io
import csv
import logging
import re
import argparse
import concurrent.futures
import threading
import yaml
import dotenv
dotenv.load_dotenv()
import page_utils
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from tqdm.auto import tqdm



logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
csv_writer_lock = threading.Lock()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_url", default=os.environ.get("BASE_WEB_AGENT_URL"), help="The base URL of the shopping website.")
    parser.add_argument("--output_file", default=os.environ.get("OUTPUT_FILE", "products.csv"), help="The path to the output CSV file.")
    parser.add_argument("--max_workers", type=int, default=os.environ.get("MAX_WORKERS", 20), help="The maximum number of concurrent workers for scraping.")
    parser.add_argument("--category_file", default="categories.yaml", help="The YAML file with the list of categories to scrape.")
    parser.add_argument("--replace_base_url_with", default="${env.abxlab_url}", help="String to replace the base URL in product links for portability.")
    args = parser.parse_args()

    with open(args.category_file) as yaml_file:
        category_config = yaml.safe_load(yaml_file)
        category_urls = category_config.get("CATEGORIES", [])

    if not category_urls:
        home_html = page_utils.get_html(args.base_url)
        home_soup = page_utils.get_soup(home_html)
        category_urls = get_all_category_links(home_soup)

    existing_urls = get_existing_product_urls(args.output_file)
    logging.info(f"Found {len(existing_urls)} existing products. They will be skipped.")

    fieldnames = ["category", "product_name", "product_url", "price", "rating", "reviews", "has_options"]
    with open(args.output_file, "a", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        if not os.path.exists(args.output_file) or csv_file.tell() == 0:
            writer.writeheader()

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            page_futures = {}
            for category_url in tqdm(category_urls, desc="Processing categories"):
                future = executor.submit(
                    process_category,
                    args.base_url,
                    category_url,
                    existing_urls,
                    writer,
                    csv_file,
                    args.replace_base_url_with
                )
                page_futures[future] = category_url

            for future in tqdm(
                concurrent.futures.as_completed(page_futures),
                total=len(page_futures),
                desc="Scraping pages"
            ):
                try:
                    future.result()
                except Exception as error:
                    logging.error(f"A category page processing generated an exception: {error}")

    logging.info("Scraping finished successfully.")


def process_category(
    base_url: str,
    category_url: str,
    existing_urls: set[str],
    writer: csv.DictWriter,
    csv_file: io.TextIOWrapper,
    replace_base_url_with: str | None = None
) -> None:
    current_page_url = urljoin(base_url, category_url)
    while current_page_url:
        try:
            category_html = page_utils.get_html(current_page_url)
            category_soup = page_utils.get_soup(category_html)
            category_name_element = category_soup.select_one("h1.page-title .base")
            category_name = category_name_element.text.strip() if category_name_element else "Unknown Category"

            product_links = page_utils.get_all_product_links(current_page_url)
            for product_link in product_links:
                product_full_url = urljoin(base_url, product_link)
                if product_full_url not in existing_urls:
                    product_data = scrape_product(product_full_url, category_name)
                    if product_data:
                        if replace_base_url_with:
                            product_data["product_url"] = product_data["product_url"].replace(base_url, replace_base_url_with)
                        with csv_writer_lock:
                            writer.writerow(product_data)
                            csv_file.flush()
                    existing_urls.add(product_full_url)

            next_page_anchor = category_soup.select_one("a.action.next")
            current_page_url = next_page_anchor["href"] if next_page_anchor and next_page_anchor.has_attr("href") else None
        except Exception as error:
            logging.error(f"Failed to process page at {current_page_url}: {error}")
            current_page_url = None


def get_all_category_links(soup: BeautifulSoup) -> list[str]:
    nav = soup.find("nav", class_="navigation")
    if not nav:
        return []
    links = {a["href"] for a in nav.find_all("a", href=True) if a.has_attr("href")}
    links = [link for link in links if not link.startswith("#")]
    logging.info(f"Found {len(links)} unique category links.")
    return list(links)


def get_existing_product_urls(file_path: str) -> set[str]:
    if not os.path.exists(file_path):
        return set()

    urls = set()
    with open(file_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
            product_url_index = header.index("product_url")
            for row in reader:
                try:
                    if len(row) > product_url_index:
                        urls.add(row[product_url_index])
                except:
                    logging.warning(f"Skipping malformed row in {file_path}: {row}")
                    continue
        except Exception as error:
            logging.warning(f"Could not read header from {file_path}: {error}")
            pass
    return urls


def scrape_product(product_url: str, category_name: str) -> dict | None:
    """Scrapes a single product's details with comprehensive error handling."""
    try:
        name = page_utils.get_name_for_product(product_url)
        price = page_utils.get_price_for_product(product_url)
        rating, reviews = get_product_reviews(product_url)
        has_options = page_utils.has_multiple_options(product_url)

        return {
            "category": category_name,
            "product_name": name,
            "product_url": product_url,
            "price": price,
            "rating": rating,
            "reviews": reviews,
            "has_options": has_options
        }
    except Exception as error:
        logging.error(f"Failed to scrape product at {product_url}: {error}")
        return None


@page_utils.with_soup
def get_product_reviews(soup: BeautifulSoup) -> tuple[str | None, int | None]:
    try:
        rating_summary = soup.select_one(".product-reviews-summary")
        if not rating_summary:
            return None, None

        reviews_link = rating_summary.select_one(".action.view")
        reviews_count = 0
        if reviews_link:
            reviews_count_text = reviews_link.get_text(strip=True)
            match = re.search(r"\d+", reviews_count_text)
            if match:
                reviews_count = int(match.group(0))

        rating_result = soup.find("div", class_="rating-result")
        rating = rating_result["title"] if rating_result and "title" in rating_result.attrs else None

        return rating, reviews_count
    except (ValueError, IndexError, TypeError) as error:
        logging.error(f"Could not parse reviews count: {error}")
        return None, 0


if __name__ == "__main__":
    main()
