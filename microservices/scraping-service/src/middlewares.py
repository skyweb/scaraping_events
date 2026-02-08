# -*- coding: utf-8 -*-
"""
Middleware per Events Scraper.

Middleware disponibili:
- RandomUserAgentMiddleware: Ruota User-Agent casuali
- RetryMiddleware: Gestione retry personalizzata
"""

import logging
import random
from typing import List

from scrapy import signals
from scrapy.downloadermiddlewares.retry import RetryMiddleware as ScrapyRetryMiddleware
from scrapy.utils.response import response_status_message

logger = logging.getLogger(__name__)


class RandomUserAgentMiddleware:
    """
    Middleware per ruotare User-Agent casuali.

    Configurazione in settings.py:
        DOWNLOADER_MIDDLEWARES = {
            'events_scraper.middlewares.RandomUserAgentMiddleware': 400,
        }

        USER_AGENTS = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...',
        ]
    """

    # User-Agent di default se non configurati
    DEFAULT_USER_AGENTS: List[str] = [
        # Chrome Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Chrome Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Firefox Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        # Firefox Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
        # Safari Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        # Edge Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    ]

    def __init__(self, user_agents: List[str] = None):
        self.user_agents = user_agents or self.DEFAULT_USER_AGENTS

    @classmethod
    def from_crawler(cls, crawler):
        user_agents = crawler.settings.getlist("USER_AGENTS")
        return cls(user_agents=user_agents if user_agents else None)

    def process_request(self, request, spider):
        """Imposta User-Agent casuale per ogni richiesta."""
        user_agent = random.choice(self.user_agents)
        request.headers["User-Agent"] = user_agent
        return None


class CustomRetryMiddleware(ScrapyRetryMiddleware):
    """
    Middleware retry personalizzato con logging migliorato.

    Configurazione in settings.py:
        DOWNLOADER_MIDDLEWARES = {
            'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,
            'events_scraper.middlewares.CustomRetryMiddleware': 550,
        }

        RETRY_TIMES = 3
        RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]
    """

    def process_response(self, request, response, spider):
        """Gestisce la risposta e decide se fare retry."""
        if request.meta.get("dont_retry", False):
            return response

        if response.status in self.retry_http_codes:
            reason = response_status_message(response.status)
            logger.warning(
                f"Retry {request.url} (status: {response.status}, reason: {reason})"
            )
            return self._retry(request, reason, spider) or response

        return response

    def process_exception(self, request, exception, spider):
        """Gestisce eccezioni durante il download."""
        if isinstance(exception, self.EXCEPTIONS_TO_RETRY) and not request.meta.get(
            "dont_retry", False
        ):
            logger.warning(f"Retry {request.url} (exception: {exception.__class__.__name__})")
            return self._retry(request, exception, spider)


class SpiderOpenCloseMiddleware:
    """
    Middleware per logging all'apertura/chiusura spider.

    Utile per setup e cleanup risorse.
    """

    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls()
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware

    def spider_opened(self, spider):
        """Chiamato all'apertura dello spider."""
        logger.info(f"Spider {spider.name} avviato")

    def spider_closed(self, spider, reason):
        """Chiamato alla chiusura dello spider."""
        stats = spider.crawler.stats.get_stats()
        items_scraped = stats.get("item_scraped_count", 0)
        logger.info(f"Spider {spider.name} chiuso ({reason}). Items: {items_scraped}")
