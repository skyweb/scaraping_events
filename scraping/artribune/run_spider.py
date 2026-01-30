#!/usr/bin/env python3
import os
import sys
import argparse
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from datetime import datetime

# Aggiungi la directory corrente al path per trovare il modulo events
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(description='Artribune Events Scraper')
    parser.add_argument('cities', nargs='*', help='Lista di città da scaricare (opzionale, altrimenti tutte)')
    args = parser.parse_args()

    # Setup Scrapy settings
    os.environ.setdefault('SCRAPY_SETTINGS_MODULE', 'artribune_scraper.settings')
    settings = get_project_settings()
    
    # Configura output file con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
    os.makedirs(output_dir, exist_ok=True)
    
    city_suffix = f"_{'_'.join(args.cities)}" if args.cities else ""
    output_file = os.path.join(output_dir, f'eventi_artribune{city_suffix}_{timestamp}.json')
    
    settings.set('FEEDS', {
        output_file: {
            'format': 'json',
            'encoding': 'utf8',
            'indent': 4,
        }
    })

    process = CrawlerProcess(settings)
    
    # Passa argomenti allo spider
    spider_args = {}
    if args.cities:
        spider_args['cities'] = args.cities
        
    process.crawl('artribune', **spider_args)
    process.start()

    print(f"\n" + "=" * 40)
    print(f"{ 'REPORT SCRAPING':^40}")
    print("=" * 40)
    if args.cities:
        print(f"Città richieste: {', '.join(args.cities)}")
    else:
        print("Scraping completo (tutte le città)")
    print("-" * 40)
    print(f"File output: {output_file}")
    print("=" * 40 + "\n")


if __name__ == "__main__":
    main()
