# -*- coding: utf-8 -*-
"""
Events Scraper - Progetto Scrapy unificato per scraping eventi.

Questo pacchetto contiene spider per diverse fonti:
- zero_eu: Eventi da zero.eu
- city_today: Eventi dalla rete *Today.it (50+ città italiane)
- artribune: Eventi culturali da artribune.com

Utilizzo con Scrapyd:
    curl http://localhost:6800/schedule.json \
        -d project=events_scraper \
        -d spider=city_today \
        -d cities=milano,roma \
        -d periodo=questa-settimana
"""

__version__ = "1.0.0"
__author__ = "Events Scraping Team"
