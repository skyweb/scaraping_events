#!/usr/bin/env python
"""Script per eseguire lo spider degli eventi di *Today.it"""

import os
import sys
from datetime import datetime

# Aggiungi il path del progetto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from events.spiders.events_spider import EventsSpider, CITIES, PERIODI

# Città disponibili
AVAILABLE_CITIES = list(CITIES.keys())


def show_help():
    """Mostra le città e periodi disponibili"""
    print("\n" + "=" * 55)
    print("CITY TODAY SCRAPER - Eventi da *Today.it")
    print("=" * 55)
    print("\nCittà disponibili:")
    for city in AVAILABLE_CITIES:
        print(f"  - {city}")
    print("\nPeriodi disponibili:")
    for periodo in PERIODI:
        default = " (default)" if periodo == "questa-settimana" else ""
        print(f"  - {periodo}{default}")
    print("\nUtilizzo:")
    print("  python run_spider.py <città> [città2] [--periodo=PERIODO]")
    print("\nEsempi:")
    print("  python run_spider.py milano")
    print("  python run_spider.py roma napoli")
    print("  python run_spider.py milano --periodo=prossima-settimana")
    print("  python run_spider.py roma bologna --periodo=questo-mese")
    print("=" * 55 + "\n")


def main():
    # Se nessun parametro, mostra help
    if len(sys.argv) < 2:
        show_help()
        return

    # Separa città da opzioni
    requested_cities = []
    periodo = "questa-settimana"  # default

    for arg in sys.argv[1:]:
        if arg.startswith("--periodo="):
            periodo = arg.split("=", 1)[1].lower()
        else:
            requested_cities.append(arg.lower())

    # Se nessuna città specificata, mostra help
    if not requested_cities:
        show_help()
        return

    # Valida le città
    invalid_cities = [c for c in requested_cities if c not in AVAILABLE_CITIES]
    if invalid_cities:
        print(f"\nErrore: città non valide: {', '.join(invalid_cities)}")
        show_help()
        return

    # Valida il periodo
    if periodo not in PERIODI:
        print(f"\nErrore: periodo non valido: {periodo}")
        show_help()
        return

    # Genera nome file con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Crea cartella output se non esiste
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)

    # Nome file basato sulle città e periodo
    if len(requested_cities) == 1:
        output_file = os.path.join(output_dir, f"eventi_{requested_cities[0]}_{periodo}_{timestamp}.json")
    else:
        output_file = os.path.join(output_dir, f"eventi_today_{periodo}_{timestamp}.json")

    print(f"\nAvvio scraping per: {', '.join([c.capitalize() for c in requested_cities])}")
    print(f"Periodo: {periodo}")

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

    # Crea e avvia il crawler
    process = CrawlerProcess(settings)

    # Passa le città e il periodo
    process.crawl(EventsSpider, cities=requested_cities, periodo=periodo)

    print(f"Output file: {output_file}")

    process.start()

    # Recupera statistiche
    try:
        crawler = list(process.crawlers)[0]
        stats = crawler.stats
        total_count = stats.get_value('item_scraped_count', 0)

        print(f"\n" + "=" * 40)
        print(f"{'REPORT SCRAPING':^40}")
        print("=" * 40)
        print(f"Periodo: {periodo}")
        print("-" * 40)
        print(f"{'Città':<25} | {'Eventi':>10}")
        print("-" * 40)

        all_stats = stats.get_stats()
        city_stats = []
        for key, value in all_stats.items():
            if key.startswith("items_per_city/"):
                city_stats.append((key.split("/")[-1], value))

        city_stats.sort(key=lambda x: x[1], reverse=True)

        for c_name, count in city_stats:
            print(f"{c_name:<25} | {count:>10}")

        if not city_stats and total_count > 0:
            print(f"{'Dettaglio non disponibile':<25} | {total_count:>10}")

        print("-" * 40)
        print(f"{'TOTALE':<25} | {total_count:>10}")

        print("-" * 40)
        print(f"File: {output_file}")
        print("=" * 40 + "\n")
    except (IndexError, AttributeError):
        print(f"\nScraping completato. File: {output_file}\n")


if __name__ == "__main__":
    main()
