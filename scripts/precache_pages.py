import os
import glob
import yaml
import requests
import dotenv
dotenv.load_dotenv()
from pathlib import Path
from urllib.parse import quote_plus
from tqdm.auto import tqdm


# Define the cache directory
CACHE_DIR = Path(".cache")
CACHE_DIR.mkdir(exist_ok=True)

URL_SUBLIST = {
    "${env.wa_shopping_url}": os.environ.get("WA_SHOPPING_URL", "http://matlaber12.media.mit.edu:7770/"),
}


def main():
    urls = get_all_urls_from_configs()
    print(f"Found {len(urls)} unique URLs to cache.")

    for sub, replacement in URL_SUBLIST.items():
        urls = {url.replace(sub, replacement) for url in urls}

    for url in tqdm(urls, desc="Caching URLs"):
        download_and_cache_url(url)
    print("Pre-caching complete.")


def sanitize_url(url):
    """Sanitize a URL to be used as a filename."""
    return quote_plus(url)


def get_all_urls_from_configs():
    """Scan all yaml configs and return a set of unique URLs."""
    urls = set()
    config_files = glob.glob("conf/experiment/exp*.yaml")

    for config_file in tqdm(config_files, desc="Scanning all config files"):
        with open(config_file) as yaml_file:
            config = yaml.safe_load(yaml_file)
            urls_exp = config["task"]["config"]["start_urls"]
            assert isinstance(urls_exp, list), "start_urls should be list"
            urls.update(urls_exp)

    return urls

def download_and_cache_url(url):
    """Download a URL and save its content to the cache."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # Raise an exception for bad status codes
        content = response.text
        sanitized = sanitize_url(url)
        cache_path = CACHE_DIR / f"{sanitized}.html"
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Cached {url} to {cache_path}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to download {url}: {e}")


if __name__ == "__main__":
    main()
