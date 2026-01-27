import scrapy
import json
import re
from datetime import datetime
from zero_scraper.items import EventItem

class EventsSpider(scrapy.Spider):
    name = "events"
    allowed_domains = ["zero.eu"]
    
    custom_settings = {
        "USER_AGENT": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "ROBOTSTXT_OBEY": False, # API often blocked by robots.txt
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.5,
    }

    def __init__(self, city="milano", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_city_slug = city.lower()
        self.target_city_id = None
        self.cities_map = {}

    def start_requests(self):
        # Step 1: Fetch cities to map slug to ID
        yield scrapy.Request(
            url="https://zero.eu/api/wp/v2/citta?per_page=100", # Fetch plenty of cities
            callback=self.parse_cities
        )

    def parse_cities(self, response):
        cities = response.json()
        for city in cities:
            slug = city.get("slug")
            c_id = city.get("id")
            if slug and c_id:
                self.cities_map[slug] = c_id
                # Check for sub-cities if structure allows? 
                # API doesn't list sub-cities recursively here effectively without parent param.
                # But typically main cities are returned in the first page of results.
        
        # Check if we need more pages of cities? (Header X-WP-TotalPages)
        # For now assume main cities are in the first 100.
        
        if self.target_city_slug in self.cities_map:
            self.target_city_id = self.cities_map[self.target_city_slug]
            self.logger.info(f"Found city ID for '{self.target_city_slug}': {self.target_city_id}")
            
            # Start fetching events with city filter
            yield scrapy.Request(
                url=f"https://zero.eu/api/v2/events?per_page=100&citta={self.target_city_id}&_embed=true", 
                callback=self.parse_events,
                meta={"page": 1}
            )
        else:
            self.logger.error(f"City '{self.target_city_slug}' not found in API.")
            # Fallback IDs
            fallback_ids = {
                "milano": 2,
                "bologna": 13,
                "roma": 3,
                "torino": 12,
                "firenze": 14,
                "venezia": 15,
                "napoli": 16
            }
            if self.target_city_slug in fallback_ids:
                self.target_city_id = fallback_ids[self.target_city_slug]
                self.logger.info(f"Using fallback ID for '{self.target_city_slug}': {self.target_city_id}")
                yield scrapy.Request(
                    url=f"https://zero.eu/api/v2/events?per_page=100&citta={self.target_city_id}&_embed=true",
                    callback=self.parse_events,
                    meta={"page": 1}
                )

    def parse_events(self, response):
        events = response.json()
        
        # If empty list, stop
        if not events:
            return

        for event in events:
            # Filter checks are redundant if API works but safe to keep
            event_cities = event.get("citta", [])
            # We check if target_city_id is in the list OR if we filtered by API (trust result)
            # Some events might return city list slightly differently, so trusting the API filter is better if used
            yield from self._parse_single_event(event)
        
        # Pagination
        current_page = response.meta.get("page", 1)
        total_pages = int(response.headers.get("X-WP-TotalPages", 0))
        
        if current_page < total_pages:
            next_page = current_page + 1
            yield scrapy.Request(
                url=f"https://zero.eu/api/v2/events?per_page=100&citta={self.target_city_id}&page={next_page}&_embed=true",
                callback=self.parse_events,
                meta={"page": next_page}
            )

    def _parse_single_event(self, data):
        item = EventItem()
        item["id"] = data.get("id")
        item["url"] = data.get("link")
        item["slug"] = data.get("slug")
        
        # Title
        title = data.get("name", {}).get("plain")
        item["title"] = self._clean_text(title)
        
        # Description
        content = data.get("content", {}).get("rendered")
        item["description"] = self._clean_html(content)
        
        # Category (as list)
        cats = data.get("category", [])
        if cats:
             item["category"] = [c.strip() for cat in cats for c in cat.split(",")]
            
        # Image
        featured_media = data.get("featured_image", {})
        if featured_media and "sizes" in featured_media:
            sizes = featured_media["sizes"]
            if "full" in sizes:
                item["image_url"] = sizes["full"].get("source_url") or sizes["full"].get("file")
            elif "large" in sizes:
                item["image_url"] = sizes["large"].get("source_url") or sizes["large"].get("file")
        
        # Luogo
        item["city"] = self.target_city_slug.capitalize()
        item["location_name"] = data.get("venue_name")
        item["location_coords"] = data.get("venue_coords")
        
        # Address extraction
        # Prima cerchiamo nei dati già presenti
        item["location_address"] = data.get("venue_address")
        venue_id = None
        
        if "_embedded" in data and "venue" in data["_embedded"]:
            venue_list = data["_embedded"]["venue"]
            if venue_list:
                venue = venue_list[0]
                venue_id = venue.get("id")
                
                # Try to find a more complete address in embedded
                full_addr = venue.get("plain_address") or venue.get("address_full")
                if full_addr:
                    item["location_address"] = full_addr
                elif isinstance(venue.get("address"), str) and len(venue.get("address")) > len(str(item["location_address"] or "")):
                     item["location_address"] = venue.get("address")

        # Price
        item["price"] = data.get("price")
        
        # Dates
        item["date_start"] = data.get("start_date")
        item["date_end"] = data.get("end_date")
        
        # Human readable dates
        item["date_display"] = data.get("date_string") or data.get("human_date")
        
        item["time_start"] = data.get("start_time")
        item["time_end"] = data.get("end_time")
        item["date_scope"] = data.get("date_scope")
        
        item["scraped_at"] = datetime.now().isoformat()
        
        # Visit the event page to get full address and formatted dates (HTML scraping)
        if item["url"]:
            # Force Italian language to get correct date format (martedì vs Tuesday)
            # The site redirects /it/ to /en/ based on headers/IP, so we must be explicit
            yield scrapy.Request(
                url=item["url"],
                callback=self.parse_event_page,
                meta={"item": item},
                headers={
                    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Cookie": "pll_language=it; wp-wpml_current_language=it" # Try common WP language cookies
                },
                dont_filter=True
            )
        else:
            yield item

    def parse_event_page(self, response):
        item = response.meta["item"]
        
        # 1. Scrape full address from p.venue
        address_parts = response.xpath('//p[contains(@class, "venue")]/text()').getall()
        full_address = " ".join([p.strip() for p in address_parts if p.strip()]).strip()
        
        if full_address:
             full_address = full_address.strip(" ,-")
             item["location_address"] = full_address
        
        # 2. Scrape formatted date ("when")
        # Primary: Look for the "When" / "Quando" section in resume details
        # Structure: <div class="resume-detail"><h2>When</h2><p>Date text<br>Time</p></div>
        
        # We look for h2 containing "When" or "Quando"
        # XPath to get the <p> following the h2
        when_text = response.xpath(
            '''
            //div[contains(@class, "resume-detail")]
            /h2[contains(text(), "When") or contains(text(), "Quando")]
            /following-sibling::p/text()
            '''
        ).get()
        
        # Fallback: p.date in header (often abbreviated)
        if not when_text:
            when_text = response.css(".single-page-header .date::text").get()
            
        if when_text:
            cleaned_date = " ".join(when_text.strip().split())
            item["date_display"] = cleaned_date
            
        yield item

    def _clean_text(self, text):
        if text:
            return " ".join(text.split()).strip()
        return None

    def _clean_text(self, text):
        if text:
            return " ".join(text.split()).strip()
        return None

    def _clean_html(self, html_text):
        if not html_text:
            return None
        # Remove HTML tags using regex
        clean = re.sub(r'<[^>]+>', '', html_text)
        return self._clean_text(clean)
