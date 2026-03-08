import json
import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Import dati ISTAT ufficiali 2026 (codice catastale) nei comuni geo'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            help='Path al file comuni_istat_2026.json',
        )

    def handle(self, *args, **options):
        base_dir = str(settings.BASE_DIR)
        json_file = options.get('file') or os.path.join(
            base_dir, 'fixtures', 'comuni_json', 'comuni_istat_2026.json'
        )

        if not os.path.exists(json_file):
            raise CommandError(f"File JSON non trovato: {json_file}")

        # 1. Carica JSON
        self.stdout.write(self.style.WARNING(f"[1/2] Caricamento JSON da {json_file}..."))
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        comuni_data = data.get('resultset', [])
        self.stdout.write(f"  Caricati {len(comuni_data)} comuni")

        # 2. Aggiorna tabella comuni con codice catastale ISTAT
        self.stdout.write(self.style.WARNING("\n[2/2] Aggiornamento comuni con dati ISTAT 2026..."))
        updated = 0
        skipped = 0

        with connection.cursor() as cursor:
            for comune in comuni_data:
                pro_com_t = str(comune.get('PRO_COM_T', '')).strip()
                cod_catasto = str(comune.get('COD_CATASTO', '')).strip()

                if not pro_com_t or not cod_catasto:
                    skipped += 1
                    continue

                cursor.execute(
                    """UPDATE comuni_istat.comuni
                       SET codice_catastale = %s
                       WHERE pro_com_t = %s
                         AND (codice_catastale IS NULL OR codice_catastale != %s)
                    """,
                    [cod_catasto, pro_com_t, cod_catasto]
                )
                updated += cursor.rowcount

        self.stdout.write(f"  Aggiornati: {updated} comuni")
        if skipped:
            self.stdout.write(f"  Saltati (dati mancanti): {skipped}")

        self.stdout.write(self.style.SUCCESS("\nImport ISTAT 2026 completato!"))
