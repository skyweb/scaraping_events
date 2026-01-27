#!/usr/bin/env python
"""Script per eseguire lo spider degli eventi di Zero.eu"""

import os
import sys
from datetime import datetime

# Aggiungi il path del progetto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from zero_scraper.spiders.events_spider import EventsSpider

# Città disponibili con i loro ID
AVAILABLE_CITIES = {
    "milano": 2,
    "roma": 3,
    "torino": 12,
    "bologna": 13,
    "firenze": 14,
    "venezia": 15,
    "napoli": 16
}


def show_help():
    """Mostra le città disponibili"""
    print("\n" + "=" * 50)
    print("ZERO.EU SCRAPER - Eventi da Zero.eu")
    print("=" * 50)
    print("\nCittà disponibili:")
    for city in AVAILABLE_CITIES.keys():
        print(f"  - {city}")
    print("\nUtilizzo:")
    print("  python run_spider.py <città1> [città2] [città3] ...")
    print("\nEsempi:")
    print("  python run_spider.py roma napoli")
    print("=" * 50 + "\n")


def main():
    # Se nessun parametro, mostra help
    if len(sys.argv) < 2:
        show_help()
        return

    # Recupera le città dai parametri
    requested_cities = [c.lower() for c in sys.argv[1:]]

    # Valida le città
    invalid_cities = [c for c in requested_cities if c not in AVAILABLE_CITIES]
    if invalid_cities:
        print(f"\nErrore: città non valide: {', '.join(invalid_cities)}")
        show_help()
        return

    # Assicura che la cartella output esista
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)

    # Genera nome file con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Nome file basato sulle città
    if len(requested_cities) == 1:
        output_file = os.path.join(output_dir, f"eventi_zero_{requested_cities[0]}_{timestamp}.json")
    else:
        output_file = os.path.join(output_dir, f"eventi_zero_{timestamp}.json")

    print(f"\nAvvio scraping Zero.eu per: {', '.join([c.capitalize() for c in requested_cities])}")

    # Carica settings del progetto
    settings = get_project_settings()

    # Configura output JSON
    settings.set(
        "FEEDS",
        {
            output_file: {
                "format": "json",
                "encoding": "utf-8",
                "indent": 2,
            }
        },
    )

    # Crea e avvia il crawler per ogni città
    process = CrawlerProcess(settings)

    for city in requested_cities:
        process.crawl(EventsSpider, city=city)

    print(f"Output file: {output_file}")

    process.start()

    print(f"\n" + "=" * 40)
    print(f"{'REPORT SCRAPING':^40}")
    print("=" * 40)
    print(f"Città scaricate: {', '.join([c.capitalize() for c in requested_cities])}")
    print(f"File: {output_file}")
    print("=" * 40 + "\n")


if __name__ == "__main__":
    main()
