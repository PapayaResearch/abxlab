# A1 intervention functions: product-DATA-QUALITY manipulations.
#
# Drop-in module for the ABxLab fork: place at abxlab/choices/shop/data_quality.py
# and reference from experiment YAML as:
#
#   functions:
#     - module: abxlab.choices.shop.data_quality
#       name: attributes
#       args:
#         keep: 3
#
# Contract (see abxlab/browser.py setup_route_handler): every function takes the
# raw HTML plus kwargs and returns (modified_html, metadata). The metadata dict
# is appended to task.nudge_metadata per trial — we use it to record whether the
# intervention actually applied ("applied": True/False), which feeds the
# pre-registered exclusion rule (exclude trials where the MITM transform found
# no target element).
#
# NOTE: CSS selectors target Magento Luma / WebArena OneStopMarket defaults.
# Verify each against the deployed instance before the pilot (see README
# checklist); override via kwargs if the theme differs.

import json
from bs4 import BeautifulSoup

JSONLD_TYPE = "application/ld+json"


def attributes(
    original_html: bytes,
    keep: int = -1,
    table_id: str = "productDetails_detailBullets_sections1",
    table_class: str = "data table additional-attributes",
    section_id: str = "additional",
) -> tuple[str, dict]:
    """Trims the spec/attribute table to the first `keep` rows.

    Targets the WebArena/OneStopMarket build's Amazon-style details table
    (matched by `table_id`; verified live 2026-07-16) and falls back to the
    stock Magento Luma "More Information" table (`table_class`).

    keep=-1 leaves the table intact (control passthrough, so treatment and
    control runs share an identical config surface); keep=0 removes the whole
    attributes section.
    """
    soup = BeautifulSoup(original_html, "lxml")
    metadata = {"applied": False, "rows_before": 0, "rows_after": 0}

    table = soup.find("table", id=table_id) \
        or soup.find("table", class_=table_class)
    if table is None:
        return str(soup), metadata

    rows = table.find_all("tr")
    metadata["rows_before"] = len(rows)

    if keep < 0:
        metadata.update(applied=True, rows_after=len(rows))
        return str(soup), metadata

    if keep == 0:
        # Remove the enclosing widget/section when present so no empty
        # "Product Details" shell remains visible to the agent.
        section = (table.find_parent("div", class_="celwidget")
                   or soup.find(id=section_id) or table)
        section.decompose()
        metadata.update(applied=True, rows_after=0)
        return str(soup), metadata

    for row in rows[keep:]:
        row.decompose()
    metadata.update(applied=True, rows_after=min(keep, len(rows)))
    return str(soup), metadata


def structured_data(
    original_html: bytes,
    mode: str = "strip",
    product: dict | None = None,
) -> tuple[str, dict]:
    """Adds or removes machine-readable product markup, leaving visible
    content untouched (H2: do agents read markup or the rendered page?).

    mode="strip": remove all JSON-LD blocks and itemprop/itemscope/itemtype
    microdata attributes.
    mode="inject": insert a schema.org Product JSON-LD block built from the
    `product` dict (name, description, sku, price, ratingValue, reviewCount).
    """
    soup = BeautifulSoup(original_html, "lxml")
    metadata = {"applied": False, "mode": mode,
                "jsonld_removed": 0, "microdata_removed": 0}

    if mode == "strip":
        for script in soup.find_all("script", type=JSONLD_TYPE):
            script.decompose()
            metadata["jsonld_removed"] += 1
        for attr in ("itemprop", "itemscope", "itemtype"):
            for el in soup.find_all(attrs={attr: True}):
                del el[attr]
                metadata["microdata_removed"] += 1
        metadata["applied"] = (
            metadata["jsonld_removed"] + metadata["microdata_removed"] > 0
        )
        return str(soup), metadata

    if mode == "inject":
        if not product:
            return str(soup), metadata
        jsonld = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": product.get("name"),
            "description": product.get("description"),
            "sku": product.get("sku"),
            "offers": {
                "@type": "Offer",
                "price": product.get("price"),
                "priceCurrency": product.get("currency", "USD"),
                "availability": "https://schema.org/InStock",
            },
        }
        if "ratingValue" in product:
            jsonld["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": product["ratingValue"],
                "reviewCount": product.get("reviewCount", 0),
            }
        script = soup.new_tag("script", type=JSONLD_TYPE)
        script.string = json.dumps(jsonld)
        (soup.head or soup).append(script)
        metadata["applied"] = True
        return str(soup), metadata

    raise ValueError(f"unknown mode: {mode}")


def description(
    original_html: bytes,
    value: str | None = None,
    mode: str = "replace",
    block_class: str = "product attribute description",
) -> tuple[str, dict]:
    """Replaces or removes the product description block.

    The rich/padded/thin text variants live in the experiment config (args),
    not here — this function is variant-agnostic. `metadata` records the
    before/after character counts so the H3 quantity-vs-richness analysis can
    verify length was held constant across padded/rich variants.
    """
    soup = BeautifulSoup(original_html, "lxml")
    metadata = {"applied": False, "mode": mode,
                "chars_before": 0, "chars_after": 0}

    block = soup.find("div", class_=block_class)
    if block is None:
        return str(soup), metadata

    inner = block.find("div", class_="value") or block
    metadata["chars_before"] = len(inner.get_text(strip=True))

    if mode == "remove":
        block.decompose()
        metadata.update(applied=True, chars_after=0)
        return str(soup), metadata

    if mode == "replace":
        if value is None:
            return str(soup), metadata
        inner.clear()
        for para in value.split("\n\n"):
            p = soup.new_tag("p")
            p.string = para
            inner.append(p)
        metadata.update(applied=True,
                        chars_after=len(inner.get_text(strip=True)))
        return str(soup), metadata

    raise ValueError(f"unknown mode: {mode}")


def images(
    original_html: bytes,
    keep: int = -1,
) -> tuple[str, dict]:
    """Trims the product image gallery to the first `keep` images.

    Magento Luma renders the gallery via a JS config (mage/gallery/gallery)
    embedded in a <script type="text/x-magento-init"> block; the agent's
    browser builds the carousel from that JSON. We trim the "data" array
    there AND remove any <img> fallbacks beyond `keep`.

    keep=-1 is the control passthrough.
    """
    soup = BeautifulSoup(original_html, "lxml")
    metadata = {"applied": False, "images_before": 0, "images_after": 0}

    if keep < 0:
        metadata["applied"] = True
        return str(soup), metadata

    for script in soup.find_all("script", type="text/x-magento-init"):
        if not script.string or "mage/gallery/gallery" not in script.string:
            continue
        try:
            config = json.loads(script.string)
        except json.JSONDecodeError:
            continue
        for selector_conf in config.values():
            gallery = selector_conf.get("mage/gallery/gallery")
            if not gallery:
                continue
            data = gallery.get("data", [])
            metadata["images_before"] = len(data)
            gallery["data"] = data[:keep]
            metadata["images_after"] = len(gallery["data"])
            metadata["applied"] = True
        script.string = json.dumps(config)

    # Fallback <img> tags inside the gallery placeholder (pre-JS render)
    gallery_div = soup.find("div", class_="gallery-placeholder")
    if gallery_div is not None:
        imgs = gallery_div.find_all("img")
        for img in imgs[keep:]:
            img.decompose()

    return str(soup), metadata


# ---------------------------------------------------------------------------
# A3 interventions. Our imported products carry the whole PDP body inside the
# Magento `description` attribute (matching the WebArena stock products):
#   <div id="productDescription"> ...copy... </div>
#   <table id="productDetails_detailBullets_sections1"> ...spec rows... </table>
# so these functions target those inner elements, never the outer wrapper.
# ---------------------------------------------------------------------------

def _text_to_html(soup, value: str):
    """Minimal renderer for authored variant text: '- ' lines become <ul>,
    blank-line-separated blocks become <p>, **bold** becomes <strong>."""
    import re as _re

    def inline(s):
        return _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)

    nodes = []
    for block in value.split("\n\n"):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        if all(ln.lstrip().startswith("- ") for ln in lines):
            ul = soup.new_tag("ul")
            for ln in lines:
                li = soup.new_tag("li")
                li.append(BeautifulSoup(inline(ln.lstrip()[2:]), "html.parser"))
                ul.append(li)
            nodes.append(ul)
        else:
            p = soup.new_tag("p")
            p.append(BeautifulSoup(inline(" ".join(lines)), "html.parser"))
            nodes.append(p)
    return nodes


def copy_variant(
    original_html: bytes,
    value: str | None = None,
    div_id: str = "productDescription",
) -> tuple[str, dict]:
    """F2: swaps the description COPY only (inside #productDescription),
    leaving the spec table and the rest of the PDP untouched.
    value=None is the control passthrough."""
    soup = BeautifulSoup(original_html, "lxml")
    metadata = {"applied": False, "chars_before": 0, "chars_after": 0}

    div = soup.find(id=div_id)
    if div is None:
        return str(soup), metadata
    metadata["chars_before"] = len(div.get_text(strip=True))

    if value is None:
        metadata.update(applied=True,
                        chars_after=metadata["chars_before"])
        return str(soup), metadata

    div.clear()
    for node in _text_to_html(soup, value):
        div.append(node)
    metadata.update(applied=True,
                    chars_after=len(div.get_text(strip=True)))
    return str(soup), metadata


def context_block(
    original_html: bytes,
    value: str | None = None,
    mode: str = "add",
    div_id: str = "contextBlock",
    after_id: str = "productDescription",
) -> tuple[str, dict]:
    """F3: inserts (or removes) the use-case/audience context block as its
    own div right after the description copy."""
    soup = BeautifulSoup(original_html, "lxml")
    metadata = {"applied": False, "mode": mode}

    if mode == "remove":
        div = soup.find(id=div_id)
        if div is not None:
            div.decompose()
            metadata["applied"] = True
        return str(soup), metadata

    if mode == "add":
        if value is None or soup.find(id=div_id) is not None:
            return str(soup), metadata
        anchor = soup.find(id=after_id)
        if anchor is None:
            return str(soup), metadata
        div = soup.new_tag("div", id=div_id)
        for node in _text_to_html(soup, value):
            div.append(node)
        anchor.insert_after(div)
        metadata["applied"] = True
        return str(soup), metadata

    raise ValueError(f"unknown mode: {mode}")


def spec_edit(
    original_html: bytes,
    find: str = "",
    replace: str = "",
    scope_id: str = "productDescription",
) -> tuple[str, dict]:
    """F6: rewrites one spec value inside the description copy (first
    occurrence), creating a contradiction with the spec table (which keeps
    the true value). find/replace are literal strings."""
    soup = BeautifulSoup(original_html, "lxml")
    metadata = {"applied": False, "find": find}

    div = soup.find(id=scope_id)
    if div is None or not find:
        return str(soup), metadata
    for text_node in div.find_all(string=True):
        if find in text_node:
            text_node.replace_with(text_node.replace(find, replace, 1))
            metadata["applied"] = True
            break
    return str(soup), metadata


def attribute_rows(
    original_html: bytes,
    remove_labels: list[str] = [],
    table_id: str = "productDetails_detailBullets_sections1",
) -> tuple[str, dict]:
    """F5: removes specific rows from the spec table by their <th> label
    (e.g. ["GTIN", "MPN"]). Empty remove_labels is the control passthrough."""
    soup = BeautifulSoup(original_html, "lxml")
    metadata = {"applied": False, "removed": []}

    table = soup.find("table", id=table_id)
    if table is None:
        return str(soup), metadata
    if not remove_labels:
        metadata["applied"] = True
        return str(soup), metadata

    for row in table.find_all("tr"):
        th = row.find("th")
        if th and th.get_text(strip=True) in remove_labels:
            metadata["removed"].append(th.get_text(strip=True))
            row.decompose()
    metadata["applied"] = bool(metadata["removed"])
    return str(soup), metadata
