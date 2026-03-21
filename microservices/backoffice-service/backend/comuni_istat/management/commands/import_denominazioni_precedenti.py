import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from comuni_istat.models import Comune, DenominazionePrecedente


class Command(BaseCommand):
    help = 'Import denominazioni precedenti ISTAT e collega al comune attuale via FK'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, help='Path al file JSON')
        parser.add_argument('--flush', action='store_true', help='Svuota la tabella prima di importare')

    def handle(self, *args, **options):
        base_dir = str(settings.BASE_DIR)
        json_file = options.get('file') or os.path.join(
            base_dir, 'fixtures', 'comuni_json', 'comuni_denominazioni_precedenti_2026.json'
        )

        if not os.path.exists(json_file):
            raise CommandError(f"File non trovato: {json_file}")

        self.stdout.write(self.style.WARNING(f"[1/3] Caricamento JSON da {json_file}..."))
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        records = data.get('resultset', [])
        self.stdout.write(f"  Caricati {len(records)} denominazioni")

        if options['flush']:
            DenominazionePrecedente.objects.all().delete()
            self.stdout.write(self.style.WARNING("  Tabella svuotata"))

        self.stdout.write(self.style.WARNING("\n[2/3] Costruzione mappa comuni attuali..."))
        comuni_map = dict(Comune.objects.values_list('pro_com_t', 'id'))
        self.stdout.write(f"  {len(comuni_map)} comuni attuali in mappa")

        self.stdout.write(self.style.WARNING("\n[3/3] Import denominazioni precedenti..."))
        batch = []
        linked = 0
        unlinked = 0

        for record in records:
            pro_com_t_corrente = str(record.get('PRO_COM_T_CORRENTE', '')).strip()
            comune_attuale_id = comuni_map.get(pro_com_t_corrente)

            if comune_attuale_id:
                linked += 1
            else:
                unlinked += 1

            batch.append(DenominazionePrecedente(
                comune_attuale_id=comune_attuale_id,
                pro_com_t=str(record.get('PRO_COM_T', '')).strip(),
                comune=record.get('COMUNE', ''),
                sigla_uts=record.get('SIGLA_UTS', ''),
                cod_den_storico=str(record.get('COD_DEN_STORICO', '')).strip(),
                pro_com_t_corrente=pro_com_t_corrente,
                comune_corrente=record.get('COMUNE_CORRENTE', ''),
                sigla_uts_corrente=record.get('SIGLA_UTS_CORRENTE', ''),
            ))

        DenominazionePrecedente.objects.bulk_create(batch, batch_size=500)

        self.stdout.write(f"  Importate: {len(batch)} denominazioni")
        self.stdout.write(f"  Collegate a comune attuale: {linked}")
        self.stdout.write(f"  Senza comune attuale: {unlinked}")
        self.stdout.write(self.style.SUCCESS("\nImport completato!"))
