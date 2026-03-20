# -*- coding: utf-8 -*-
"""
Middleware per Events Scraper.

Middleware disponibili:
- RandomUserAgentMiddleware: Ruota User-Agent casuali
- RotatingProxyMiddleware: Ruota proxy HTTP/SOCKS (abilitabile via settings/env)
- CustomRetryMiddleware: Gestione retry personalizzata
"""

import logging
import random
from typing import List, Optional

from scrapy import signals
from scrapy.downloadermiddlewares.retry import RetryMiddleware as ScrapyRetryMiddleware
from scrapy.exceptions import NotConfigured
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


class RotatingProxyMiddleware:
    """
    Middleware per ruotare proxy ad ogni richiesta.

    Attivazione (disabilitato di default):
        PROXY_ENABLED=true  (env var o settings.py)

    Configurazione proxy:
        # Singolo proxy (es. servizio rotating come ScraperAPI, Bright Data)
        PROXY_LIST=http://user:pass@proxy.example.com:8080

        # Multipli proxy in rotazione (separati da virgola)
        PROXY_LIST=http://proxy1:8080,http://proxy2:8080,socks5://proxy3:1080

        # File con un proxy per riga
        PROXY_LIST_FILE=/path/to/proxies.txt

    Formati supportati:
        http://host:port
        http://user:pass@host:port
        socks5://host:port
        socks5://user:pass@host:port

    Per-spider override:
        class MySpider(scrapy.Spider):
            custom_settings = {'PROXY_ENABLED': True}

    Per-request skip:
        yield Request(url, meta={'no_proxy': True})
    """

    def __init__(self, proxy_list: list[str]):
        self.proxies = proxy_list
        self.failed_proxies: dict[str, int] = {}
        # Soglia massima di errori consecutivi prima di rimuovere un proxy
        self.max_failures = 5

    @classmethod
    def from_crawler(cls, crawler) -> "RotatingProxyMiddleware":
        enabled = crawler.settings.getbool("PROXY_ENABLED", False)
        if not enabled:
            raise NotConfigured("PROXY_ENABLED non attivo")

        proxies: list[str] = []

        # 1. Da settings/env: lista separata da virgola
        proxy_list = crawler.settings.get("PROXY_LIST", "")
        if proxy_list:
            proxies = [p.strip() for p in proxy_list.split(",") if p.strip()]

        # 2. Da file (un proxy per riga)
        proxy_file = crawler.settings.get("PROXY_LIST_FILE", "")
        if proxy_file:
            try:
                with open(proxy_file, "r") as f:
                    file_proxies = [
                        line.strip() for line in f if line.strip() and not line.startswith("#")
                    ]
                    proxies.extend(file_proxies)
            except FileNotFoundError:
                logger.warning(f"File proxy non trovato: {proxy_file}")

        if not proxies:
            raise NotConfigured("PROXY_ENABLED=true ma nessun proxy configurato (PROXY_LIST / PROXY_LIST_FILE)")

        logger.info(f"Proxy rotation attiva: {len(proxies)} proxy configurati")
        return cls(proxy_list=proxies)

    def _get_proxy(self) -> Optional[str]:
        """Seleziona un proxy random, escludendo quelli con troppi errori."""
        available = [p for p in self.proxies if self.failed_proxies.get(p, 0) < self.max_failures]
        if not available:
            # Reset contatori e riprova con tutti
            logger.warning("Tutti i proxy hanno superato la soglia errori, reset contatori")
            self.failed_proxies.clear()
            available = self.proxies
        return random.choice(available)

    def process_request(self, request, spider):
        """Imposta proxy casuale per ogni richiesta."""
        if request.meta.get("no_proxy", False):
            return None

        proxy = self._get_proxy()
        request.meta["proxy"] = proxy
        # Log solo a livello DEBUG per non riempire i log
        logger.debug(f"Proxy: {proxy.split('@')[-1] if '@' in proxy else proxy}")
        return None

    def process_exception(self, request, exception, spider):
        """Segna il proxy come fallito in caso di errore di connessione."""
        proxy = request.meta.get("proxy", "")
        if proxy:
            self.failed_proxies[proxy] = self.failed_proxies.get(proxy, 0) + 1
            failures = self.failed_proxies[proxy]
            logger.warning(
                f"Proxy {proxy.split('@')[-1] if '@' in proxy else proxy} "
                f"errore ({failures}/{self.max_failures}): {exception.__class__.__name__}"
            )


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
