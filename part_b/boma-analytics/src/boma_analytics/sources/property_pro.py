from __future__ import annotations
import logging
import re
import time
from dataclasses import dataclass
from typing import Iterator
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DEFAULT_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class PropertyProConfig:
    domain_url: str = "https://www.propertypro.co.ke"
    search_path: str = "/property-for-sale/house"
    request_timeout: int = 15
    request_delay_seconds: float = 0.0
    user_agent: str = (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    max_pages: int | None = None


class PropertyPro:
    def __init__(self, config: PropertyProConfig = PropertyProConfig()) -> None:
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
        return urljoin(self.config.domain_url, self.config.search_path)

    def _get(self, url: str) -> BeautifulSoup:
        if self.config.request_delay_seconds > 0:
            time.sleep(self.config.request_delay_seconds)

        response = self.session.get(
            url,
            timeout=self.config.request_timeout
        )
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')

    def get_total_pages(self, soup: BeautifulSoup, items_per_page: int = 20) -> int:
        target_div = soup.select_one(
            'div.onpage-filters.d-flex.justify-content-between.align-items-center')

        if not target_div:
            return 0

        # 1. Find the strong tag containing the total items count directly from the target_div
        strong_tag = target_div.find('strong')
        if not strong_tag:
            return 0

        # Clean the text (remove commas if numbers look like 24,300)
        total_items_text = re.sub(r'\D', '', strong_tag.text)
        total_items = int(total_items_text)

        total_pages = (total_items + items_per_page - 1) // items_per_page

        return total_pages

    def scrape_all(self) -> Iterator[str]:
        soup = self._get(self.search_url)
        total_pages = self.get_total_pages(soup)
        if self.config.max_pages is not None:
            total_pages = min(total_pages, self.config.max_pages)
        for page in range(1, total_pages + 1):
            url = f"{self.search_url}?page={page}"
            logger.info(f"Scraping page {page} of {total_pages}...")
            soup_page = self._get(url)
            cards = soup_page.select(".property-listing")

            for card in cards:
                title_link = card.select_one('.pl-title h3 a')
                if not title_link:
                    continue

                relative_link = title_link['href']
                full_link = urljoin(self.config.domain_url, relative_link)

                card_soup = self._get(full_link)
                description = card_soup.select(
                    ".des-inner.font-16.line-paragraph")

                if description:
                    yield str(description[0])
