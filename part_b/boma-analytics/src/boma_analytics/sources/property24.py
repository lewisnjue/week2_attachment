"""Property24 source-specific ingestion logic."""
from __future__ import annotations
from dataclasses import dataclass
import math
from bs4 import BeautifulSoup
import requests
import logging
import time
from typing import Iterator, Any

logger = logging.getLogger(__name__)


@dataclass
class Property24Config:
    base_url: str = "https://www.property24.co.ke/"
    request_delay_seconds: int = 0
    request_timeout: int = 100
    user_agent: str = (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    max_pages: int | None = None


DEFAULT_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
}


class Property24Client:
    def __init__(self, config: Property24Config = None) -> None:
        self.config = config or Property24Config()
        self.session = requests.Session()
        """
        self.session.headers.update(
            {
                **DEFAULT_HEADERS,
                "User-Agent": self.config.user_agent,
            }
        )
        """

    def _get(self, url: str) -> BeautifulSoup:
        if self.config.request_delay_seconds > 0:
            time.sleep(self.config.request_delay_seconds)

        response = self.session.get(url, timeout=self.config.request_timeout)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    def fetch_search_page(self, url: str, page: int = 1) -> BeautifulSoup:
        paginated_url = f"{url}?page={page}"
        logger.info("Fetching search page %s: %s", page, paginated_url)
        return self._get(paginated_url)

    def get_locations_url(self) -> list[dict[str, str]]:
        soup = self._get(self.config.base_url)
        location_elements = soup.select(".col-xs-6 ul li a")

        locations = [
            {
                "name": link.get_text(strip=True),
                "url": f"{self.config.base_url.rstrip('/')}{link.get('href')}"
            }
            for link in location_elements
        ]
        return locations

    def get_total_pages(self, soup: BeautifulSoup) -> int:
        pager_tags = soup.select(".sc_searchResultsPagerTop .sc_pageText b")
        if len(pager_tags) >= 2:
            raw_listings_count = pager_tags[1].get_text(strip=True)
            total_listings = int(raw_listings_count.replace(",", ""))
            listings_per_page = 20
            total_pages = math.ceil(total_listings / listings_per_page)
            return total_pages
        else:
            raise ValueError("Could not locate pagination tags.")

    def fetch_detail_page(self, single_page_soup: BeautifulSoup) -> list[dict[str, Any]]:
        listings = single_page_soup.find_all('div', class_='js_listingTile')
        scraped_data = []
        for listing in listings:
            title_elem = listing.find('span', class_='p24_propertyTitle')
            title = title_elem.text.strip() if title_elem else "N/A"

            price_elem = listing.find('span', class_='p24_price')
            price = price_elem['content'] if price_elem and 'content' in price_elem.attrs else "N/A"

            location_elem = listing.find('span', class_='p24_location')
            location = location_elem.text.strip() if location_elem else "N/A"

            address_elem = listing.find('span', class_='p24_address')
            address = address_elem.text.strip() if address_elem else "N/A"

            bed_elem = listing.find('span', title='Bedrooms')
            bedrooms = bed_elem.find(
                'span').text.strip() if bed_elem else "N/A"

            bath_elem = listing.find('span', title='Bathrooms')
            bathrooms = bath_elem.find(
                'span').text.strip() if bath_elem else "N/A"

            park_elem = listing.find('span', title='Parking Spaces')
            parking = park_elem.find(
                'span').text.strip() if park_elem else "N/A"

            size_elem = listing.find('span', title='Floor Size')
            floor_size = size_elem.find(
                'span').text.strip() if size_elem else "N/A"

            scraped_data.append({
                'Title': title,
                'Price (KSh)': price,
                'Location': location,
                'Address': address,
                'Bedrooms': bedrooms,
                'Bathrooms': bathrooms,
                'Parking': parking,
                'Floor Size': floor_size
            })

        return scraped_data

    def scrape_all(self) -> Iterator[dict[str, Any]]:
        """Iterates through all regional URLs and layout pages, yielding items sequentially."""
        locations = self.get_locations_url()

        for location in locations:
            loc_name = location['name']
            loc_url = location['url']

            try:
                soup = self._get(loc_url)
                total_pages = self.get_total_pages(soup)
            except (ValueError, requests.exceptions.RequestException) as e:
                logger.warning(f"Skipping {loc_name} due to error: {e}")
                continue

            # Respect the max_pages config if set
            if self.config.max_pages:
                total_pages = min(total_pages, self.config.max_pages)

            for page in range(1, total_pages + 1):
                try:
                    soup_page = self.fetch_search_page(loc_url, page)
                    page_listings = self.fetch_detail_page(soup_page)

                    for listing in page_listings:
                        # Add tracking metadata for regional grouping context
                        listing['Location_Group'] = loc_name
                        yield listing

                except requests.exceptions.RequestException as e:
                    logger.error(f"Error fetching page {
                                 page} for {loc_name}: {e}")
                    continue
