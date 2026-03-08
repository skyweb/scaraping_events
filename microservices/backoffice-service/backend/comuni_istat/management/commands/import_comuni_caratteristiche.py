import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Import caratteristiche ISTAT 2026 (altitudine, zona, ecoregione) nei comuni geo'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, help='Path al file JSON')

    def handle(self, *args, **options):
        base_dir = str(settings.BASE_DIR)
        json_file = options.get('file') or os.path.join(
            base_dir, 'fixtures', 'comuni_json', 'comuni_caratteristiche_2026.json'
        )

        if not os.path.exists(json_file):
            raise CommandError(f"File non trovato: {json_file}")

        self.stdout.write(self.style.WARNING(f"[1/2] Caricamento JSON da {json_file}..."))
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        records = data.get('resultset', [])
        self.stdout.write(f"  Caricati {len(records)} comuni")

        self.stdout.write(self.style.WARNING("\n[2/2] Aggiornamento comuni con caratteristiche..."))
        updated = 0

        with connection.cursor() as cursor:
            for record in records:
                pro_com_t = str(record.get('PRO_COM_T', '')).strip()
                if not pro_com_t:
                    continue

                cursor.execute(
                    """UPDATE comuni_istat.comuni
                       SET altitudine = %s,
                           zona_altimetrica = %s,
                           comune_litoraneo = %s,
                           comune_isolano = %s,
                           zona_costiera = %s,
                           grado_urbanizzazione = %s,
                           ecoregione_divisione = %s,
                           ecoregione_provincia = %s,
                           ecoregione_sezione = %s,
                           ecoregione_sottosezione = %s
                       WHERE pro_com_t = %s
                    """,
                    [
                        record.get('ALTITUDINE'),
                        record.get('ZONA_ALT'),
                        bool(record.get('COM_LIT')),
                        bool(record.get('COM_ISO')),
                        record.get('ZONE_COST_2021'),
                        record.get('DEGURBA_2021'),
                        record.get('DEN_ECO_DIV_2018'),
                        record.get('DEN_ECO_PRO_2018'),
                        record.get('DEN_ECO_SEZ_2018'),
                        record.get('DEN_ECO_SSEZ_2018'),
                        pro_com_t,
                    ]
                )
                updated += cursor.rowcount

        self.stdout.write(f"  Aggiornati: {updated} comuni")
        self.stdout.write(self.style.SUCCESS("\nImport completato!"))
