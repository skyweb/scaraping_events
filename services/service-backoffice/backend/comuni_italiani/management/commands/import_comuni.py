import json
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Import comuni data from comuni-json (CAP, codice catastale, popolazione)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            help='Path to comuni.json file',
        )

    def handle(self, *args, **options):
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        json_file = options.get('file') or os.path.join(app_dir, 'data', 'comuni.json')

        if not os.path.exists(json_file):
            raise CommandError(f"JSON file not found: {json_file}")

        self.stdout.write(self.style.WARNING(f"[1/3] Loading JSON from {json_file}..."))
        with open(json_file, 'r', encoding='utf-8') as f:
            comuni_data = json.load(f)
        self.stdout.write(f"  Loaded {len(comuni_data)} comuni")

        # 2. Insert into staging table
        self.stdout.write(self.style.WARNING("\n[2/3] Loading into staging table..."))
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE comuni_italiani.comuni_json_staging")

            for comune in comuni_data:
                codice = comune.get('codice', '')
                nome = comune.get('nome', '')
                codice_catastale = comune.get('codiceCatastale', '')
                cap_list = comune.get('cap', [])
                popolazione = comune.get('popolazione', None)

                cursor.execute(
                    """INSERT INTO comuni_italiani.comuni_json_staging
                       (codice, nome, codice_catastale, cap, popolazione)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (codice) DO UPDATE SET
                           nome = EXCLUDED.nome,
                           codice_catastale = EXCLUDED.codice_catastale,
                           cap = EXCLUDED.cap,
                           popolazione = EXCLUDED.popolazione
                    """,
                    [codice, nome, codice_catastale, cap_list, popolazione]
                )

        self.stdout.write(self.style.SUCCESS("  Staging table loaded"))

        # 3. Update comuni table from staging
        self.stdout.write(self.style.WARNING("\n[3/3] Updating comuni from staging..."))
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE comuni_italiani.comuni c
                SET
                    codice_catastale = s.codice_catastale,
                    cap = s.cap,
                    popolazione = s.popolazione
                FROM comuni_italiani.comuni_json_staging s
                WHERE c.pro_com_t = s.codice
            """)
            updated = cursor.rowcount
            self.stdout.write(f"  Updated {updated} comuni")

        self.stdout.write(self.style.SUCCESS("\nImport completed successfully!"))
