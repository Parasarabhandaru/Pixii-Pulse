"""Amazon listing scraper. Best-effort BeautifulSoup parser.

Called only by agents/scanner.py. On any failure, scanner falls back to
data/sample_data.json — so this module is allowed to raise.
"""
from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

TIMEOUT = 10


def _text(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _parse_float(s: str) -> float:
    m = re.search(r"[\d]+\.?[\d]*", s.replace(",", ""))
    return float(m.group()) if m else 0.0


def _parse_int(s: str) -> int:
    m = re.search(r"[\d,]+", s)
    return int(m.group().replace(",", "")) if m else 0


def scrape_product(url: str) -> dict:
    """Return a product dict matching the schema in data/sample_data.json.

    Raises on any HTTP / parse failure so the caller can fall back.
    """
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code} for {url}")

    soup = BeautifulSoup(resp.text, "html.parser")

    title_node = soup.select_one("#productTitle")
    title = _text(title_node)
    if not title:
        raise RuntimeError("title not found — likely blocked or CAPTCHA")

    bullet_nodes = soup.select("#feature-bullets ul li span.a-list-item")
    bullets = [_text(b) for b in bullet_nodes if _text(b)][:5]
    while len(bullets) < 5:
        bullets.append("")

    desc_node = soup.select_one("#productDescription") or soup.select_one(
        "#aplus, #aplus3p_feature_div"
    )
    description = _text(desc_node)

    price_node = (
        soup.select_one("span.a-price span.a-offscreen")
        or soup.select_one("#priceblock_ourprice")
        or soup.select_one("#priceblock_dealprice")
    )
    price = _parse_float(_text(price_node))

    rating_node = soup.select_one("span[data-hook='rating-out-of-text']") or soup.select_one(
        "i[data-hook='average-star-rating'] span"
    )
    rating = _parse_float(_text(rating_node))

    review_count_node = soup.select_one("#acrCustomerReviewText")
    review_count = _parse_int(_text(review_count_node))

    review_nodes = soup.select("span[data-hook='review-body'] span")
    reviews = [_text(r) for r in review_nodes if _text(r)][:20]
    while len(reviews) < 20:
        reviews.append("")

    return {
        "title": title,
        "bullets": bullets,
        "description": description,
        "price": price,
        "rating": rating,
        "review_count": review_count,
        "reviews": reviews,
    }
