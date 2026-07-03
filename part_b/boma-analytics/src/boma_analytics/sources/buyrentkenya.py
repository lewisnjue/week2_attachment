"""BuyRentKenya source-specific ingestion logic."""
from __future__ import annotations
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Iterator
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class BuyRentKenyaConfig:
    base_url: str = "https://www.buyrentkenya.com"
    search_path: str = "/houses-for-sale"
    request_timeout: int = 15
    # Set to 0 since your experiments show no rate limits
    request_delay_seconds: float = 0.0
    user_agent: str = (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    max_pages: int | None = None


class BuyRentKenyaClient:
    def __init__(self, config: BuyRentKenyaConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                **DEFAULT_HEADERS,
                "User-Agent": config.user_agent,
            }
        )

    @property
    def search_url(self) -> str:
        return urljoin(self.config.base_url, self.config.search_path)

    def _get(self, url: str) -> BeautifulSoup:
        # Respect any configured delay, even if 0
        if self.config.request_delay_seconds > 0:
            time.sleep(self.config.request_delay_seconds)

        response = self.session.get(url, timeout=self.config.request_timeout)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    def fetch_search_page(self, page: int = 1) -> BeautifulSoup:
        # Fixed the multiline formatting issue here to avoid syntax errors
        url = self.search_url if page <= 1 else f"{
            self.search_url}?page={page}"
        logger.info("Fetching search page %s: %s", page, url)
        return self._get(url)

    def get_total_pages(self, soup: BeautifulSoup) -> int:
        nav = soup.select_one(".pagination-page-nav")
        if not nav:
            return 1

        page_numbers = [
            int(item) for item in nav.stripped_strings if item.isdigit()
        ]
        return page_numbers[-1] if page_numbers else 1

    def scrape_all(self) -> Iterator[dict[str, Any]]:
        """Scrapes all pages and yields each validated property listing one by one."""
        # 1. Fetch first page to get metadata and total pages
        logger.info("Initializing scrape sequence...")
        first_page_soup = self.fetch_search_page(page=1)
        total_pages = self.get_total_pages(first_page_soup)

        # Override if max_pages config limit is set
        if self.config.max_pages:
            total_pages = min(total_pages, self.config.max_pages)

        # 2. Iterate through pages smoothly
        for page_num in range(1, total_pages + 1):
            # Optimization: Re-use the soup we already fetched for page 1
            if page_num == 1:
                page_data = first_page_soup
            else:
                page_data = self.fetch_search_page(page_num)

            cards = page_data.select(".listing-card")
            logger.info("Found %d listings on page %d", len(cards), page_num)

            for card in cards:
                card_data = self.extract_listing_features(card)
                # Keep records only if they have a target variable (price)
                if card_data.get("price"):
                    yield card_data

    def extract_listing_features(self, card: Any) -> dict[str, Any]:
        features = {}

        # 1. Base Unique Identifier
        features["listing_id"] = card.get("id", "").replace("listing-", "")

        # 2. Extract basic info from data attributes
        bi_element = card.find(attrs={"data-bi-listing-price": True})
        if bi_element:
            features["price"] = int(bi_element.get("data-bi-listing-price", 0))
            features["property_type"] = bi_element.get(
                "data-bi-listing-category")
        else:
            features["price"] = None
            features["property_type"] = None

        # 3. Extract Bedrooms from DOM badge
        beds_span = card.find(attrs={"data-cy": "card-bedroom_count"})
        if beds_span:
            beds_match = re.search(r"\d+", beds_span.text)
            features["bedrooms"] = int(
                beds_match.group()) if beds_match else None
        else:
            features["bedrooms"] = None

        # 4. Extract detailed features from embedded Alpine/GA4 JSON
        x_init_attr = card.get("x-init", "")
        json_match = re.search(r"JSON\.parse\('(.*?)'\)", x_init_attr)

        if json_match:
            try:
                clean_json_str = json_match.group(1).replace(r"\u0022", '"')
                ga4_data = json.loads(clean_json_str)

                # ML Feature Fields
                features["county"] = ga4_data.get("propertyCounty")
                features["city"] = ga4_data.get("propertyCity")
                features["area"] = ga4_data.get("propertyArea")
                features["days_on_market"] = ga4_data.get(
                    "propertyDaysInMarket")
                features["seller_type"] = ga4_data.get("sellerType")

            except (json.JSONDecodeError, IndexError):
                features["county"] = None
                features["city"] = None
                features["area"] = None
                features["days_on_market"] = None
                features["seller_type"] = None
        else:
            features["county"] = None
            features["city"] = None
            features["area"] = None
            features["days_on_market"] = None
            features["seller_type"] = None

        return features
