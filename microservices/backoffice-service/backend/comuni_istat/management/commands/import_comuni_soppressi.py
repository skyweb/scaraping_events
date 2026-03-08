import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from comuni_istat.models import ComuneItaliano, ComuneSoppresso


class Command(BaseCommand):
    help = 'Import comuni soppressi ISTAT e collega al comune attuale via FK'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            help='Path al file comuni_soppressi_2026.json',
        )
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Svuota la tabella prima di importare',
        )

    def handle(self, *args, **options):
        base_dir = str(settings.BASE_DIR)
        json_file = options.get('file') or os.path.join(
            base_dir, 'fixtures', 'comuni_json', 'comuni_soppressi_2026.json'
        )

        if not os.path.exists(json_file):
            raise CommandError(f"File non trovato: {json_file}")

        # 1. Carica JSON
        self.stdout.write(self.style.WARNING(f"[1/3] Caricamento JSON da {json_file}..."))
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        records = data.get('resultset', [])
        self.stdout.write(f"  Caricati {len(records)} comuni soppressi")

        # 2. Flush se richiesto
        if options['flush']:
            ComuneSoppresso.objects.all().delete()
            self.stdout.write(self.style.WARNING("  Tabella svuotata"))

        # 3. Mappa pro_com_t → id di ComuneItaliano per il collegamento FK
        self.stdout.write(self.style.WARNING("\n[2/3] Costruzione mappa comuni attuali..."))
        comuni_map = dict(
            ComuneItaliano.objects.values_list('pro_com_t', 'id')
        )
        self.stdout.write(f"  {len(comuni_map)} comuni attuali in mappa")

        # 4. Import
        self.stdout.write(self.style.WARNING("\n[3/3] Import comuni soppressi..."))
        batch = []
        linked = 0
        unlinked = 0

        for record in records:
            pro_com_t_rel = str(record.get('PRO_COM_T_REL', '')).strip()
            comune_attuale_id = comuni_map.get(pro_com_t_rel)

            if comune_attuale_id:
                linked += 1
            else:
                unlinked += 1

            batch.append(ComuneSoppresso(
                comune_attuale_id=comune_attuale_id,
                anno=record.get('ANNO', 0),
                pro_com_t=str(record.get('PRO_COM_T', '')).strip(),
                comune=record.get('COMUNE', ''),
                sigla_uts=record.get('SIGLA_UTS', ''),
                cod_variazione=record.get('COD_VARIAZIONE', ''),
                data_inizio=record.get('DATA_INIZIO_AMMINISTRATIVA', ''),
                pro_com_t_rel=pro_com_t_rel,
                comune_rel=record.get('COMUNE_REL', ''),
                sigla_uts_rel=record.get('SIGLA_UTS_REL', ''),
            ))

        ComuneSoppresso.objects.bulk_create(batch, batch_size=500)

        self.stdout.write(f"  Importati: {len(batch)} comuni soppressi")
        self.stdout.write(f"  Collegati a comune attuale: {linked}")
        self.stdout.write(f"  Senza comune attuale (storico): {unlinked}")
        self.stdout.write(self.style.SUCCESS("\nImport completato!"))
