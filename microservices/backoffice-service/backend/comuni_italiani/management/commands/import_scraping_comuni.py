"""
Management command per importare i JSON generati dallo scraping
(data/output/) nelle tabelle relazionali: Regione, Provincia, Comune + figlie.

Uso:
    python manage.py import_scraping_comuni /path/to/data/output
    python manage.py import_scraping_comuni /path/to/data/output --flush
"""
import json
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from comuni_italiani.models import (
    Regione, Provincia, Comune,
    ComuneFrazione, ComuneConfinante, ComuneAppartenenza,
    ComunePuntoInteresse, ComuneEvento, ComuneGemellaggio,
    ComuneCittadinoIllustre,
)

# Mappa campi JSON → (modello, campo)
POI_MAP = {
    'musei': 'museo',
    'chiese': 'chiesa',
    'ville_palazzi': 'villa_palazzo',
    'castelli_fortificazioni': 'castello_fortificazione',
    'fontane': 'fontana',
    'giardini_orti_botanici': 'giardino_orto_botanico',
    'luoghi_interesse': 'luogo_interesse',
    'teatri': 'teatro',
    'stadi': 'stadio',
}


class Command(BaseCommand):
    help = 'Importa i JSON dallo scraping comuni nelle tabelle relazionali'

    def add_arguments(self, parser):
        parser.add_argument(
            'data_dir',
            type=str,
            help='Percorso alla directory data/output con i JSON delle regioni',
        )
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Cancella tutti i dati esistenti prima di importare',
        )

    def handle(self, *args, **options):
        data_dir = options['data_dir']
        if not os.path.isdir(data_dir):
            raise CommandError(f"Directory non trovata: {data_dir}")

        if options['flush']:
            self.stdout.write(self.style.WARNING("Cancellazione dati esistenti..."))
            # CASCADE elimina automaticamente province, comuni e tabelle figlie
            Regione.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("  Dati cancellati."))

        # Trova le cartelle regione (es. 01_piemonte, 02_valle_d_aosta, ...)
        regione_dirs = sorted([
            d for d in os.listdir(data_dir)
            if os.path.isdir(os.path.join(data_dir, d)) and d[0].isdigit()
        ])

        if not regione_dirs:
            raise CommandError(f"Nessuna cartella regione trovata in {data_dir}")

        tot_regioni = 0
        tot_province = 0
        tot_comuni = 0

        with transaction.atomic():
            for reg_dir in regione_dirs:
                reg_path = os.path.join(data_dir, reg_dir)
                regione_obj, n_prov, n_comuni = self._import_regione(reg_path)
                if regione_obj:
                    tot_regioni += 1
                    tot_province += n_prov
                    tot_comuni += n_comuni

        self.stdout.write(self.style.SUCCESS(
            f"\nImportazione completata: "
            f"{tot_regioni} regioni, {tot_province} province, {tot_comuni} comuni"
        ))

    def _find_json(self, directory, exclude_suffix='_comuni'):
        """Trova il singolo file JSON (non _comuni) in una directory."""
        for f in os.listdir(directory):
            if f.endswith('.json') and exclude_suffix not in f:
                return os.path.join(directory, f)
        return None

    def _find_comuni_json(self, directory):
        """Trova il file *_comuni.json in una directory."""
        for f in os.listdir(directory):
            if f.endswith('_comuni.json'):
                return os.path.join(directory, f)
        return None

    def _load_json(self, filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _import_regione(self, reg_path):
        """Importa una regione e tutte le sue province/comuni."""
        # Carica JSON regione
        reg_json_path = self._find_json(reg_path)
        if not reg_json_path:
            self.stderr.write(f"  Nessun JSON regione in {reg_path}, salto.")
            return None, 0, 0

        data = self._load_json(reg_json_path)
        regione, created = Regione.objects.update_or_create(
            codice_istat=data['codice_istat'],
            defaults={
                'nome': data['nome'],
                'popolazione': data.get('popolazione'),
                'popolazione_maschi': data.get('popolazione_maschi'),
                'popolazione_femmine': data.get('popolazione_femmine'),
                'superficie_kmq': data.get('superficie_kmq'),
                'densita': data.get('densita'),
                'num_province': data.get('num_province'),
                'num_comuni': data.get('num_comuni'),
                'capoluogo': data.get('capoluogo'),
                'iso_3166_2': data.get('iso_3166_2'),
                'nuts': data.get('nuts'),
            }
        )
        action = "creata" if created else "aggiornata"
        self.stdout.write(f"[REGIONE] {regione.nome} ({regione.codice_istat}) - {action}")

        # Trova e importa province
        prov_dirs = sorted([
            d for d in os.listdir(reg_path)
            if os.path.isdir(os.path.join(reg_path, d)) and d[0].isdigit()
        ])

        n_prov = 0
        n_comuni = 0
        for prov_dir in prov_dirs:
            prov_path = os.path.join(reg_path, prov_dir)
            provincia_obj, count = self._import_provincia(prov_path, regione)
            if provincia_obj:
                n_prov += 1
                n_comuni += count

        return regione, n_prov, n_comuni

    def _import_provincia(self, prov_path, regione):
        """Importa una provincia e i suoi comuni."""
        prov_json_path = self._find_json(prov_path)
        if not prov_json_path:
            self.stderr.write(f"  Nessun JSON provincia in {prov_path}, salto.")
            return None, 0

        data = self._load_json(prov_json_path)
        provincia, created = Provincia.objects.update_or_create(
            codice_istat=data['codice_istat'],
            defaults={
                'regione': regione,
                'nome': data['nome'],
                'sigla': data.get('sigla'),
                'zona': data.get('zona'),
                'popolazione': data.get('popolazione'),
                'popolazione_maschi': data.get('popolazione_maschi'),
                'popolazione_femmine': data.get('popolazione_femmine'),
                'superficie_kmq': data.get('superficie_kmq'),
                'densita': data.get('densita'),
                'num_comuni': data.get('num_comuni'),
                'capoluogo': data.get('capoluogo'),
                'iso_3166_2': data.get('iso_3166_2'),
                'nuts': data.get('nuts'),
            }
        )
        action = "creata" if created else "aggiornata"
        self.stdout.write(f"  [PROVINCIA] {provincia.nome} ({provincia.sigla}) - {action}")

        # Importa comuni
        comuni_json_path = self._find_comuni_json(prov_path)
        count = 0
        if comuni_json_path:
            comuni_data = self._load_json(comuni_json_path)
            count = self._import_comuni(comuni_data, provincia)
            self.stdout.write(f"    [COMUNI] {count} importati")

        return provincia, count

    def _import_comuni(self, comuni_data, provincia):
        """Importa una lista di comuni con tutte le tabelle figlie."""
        count = 0
        for c in comuni_data:
            comune, created = Comune.objects.update_or_create(
                codice_istat=c['codice_istat'],
                defaults={
                    'provincia': provincia,
                    'nome': c['nome'],
                    'codice_catastale': c.get('codice_catastale'),
                    'zona': c.get('zona'),
                    'popolazione': c.get('popolazione'),
                    'superficie_kmq': c.get('superficie_kmq'),
                    'densita': c.get('densita'),
                    'cap': c.get('cap'),
                    'prefisso_telefonico': c.get('prefisso_telefonico'),
                    'patrono': c.get('patrono'),
                    'festa_patronale': c.get('festa_patronale'),
                    'demonimo': c.get('demonimo'),
                    'etimologia': c.get('etimologia'),
                    'il_comune_e': c.get('il_comune_e'),
                }
            )

            # Per update: cancella le tabelle figlie e ricrea
            if not created:
                comune.frazioni.all().delete()
                comune.confinanti.all().delete()
                comune.appartenenze.all().delete()
                comune.punti_interesse.all().delete()
                comune.eventi.all().delete()
                comune.gemellaggi.all().delete()
                comune.cittadini_illustri.all().delete()

            self._import_child_tables(comune, c)
            count += 1

        return count

    def _import_child_tables(self, comune, data):
        """Importa tutte le tabelle figlie di un comune."""
        # Frazioni
        items = data.get('localita_frazioni') or []
        if items:
            ComuneFrazione.objects.bulk_create([
                ComuneFrazione(comune=comune, nome=nome, ordine=i)
                for i, nome in enumerate(items)
            ])

        # Confinanti
        items = data.get('comuni_confinanti') or []
        if items:
            ComuneConfinante.objects.bulk_create([
                ComuneConfinante(comune=comune, descrizione=desc, ordine=i)
                for i, desc in enumerate(items)
            ])

        # Appartenenze (fa_parte_di)
        items = data.get('fa_parte_di') or []
        if items:
            ComuneAppartenenza.objects.bulk_create([
                ComuneAppartenenza(comune=comune, nome=nome, ordine=i)
                for i, nome in enumerate(items)
            ])

        # Punti di interesse
        poi_objects = []
        for json_key, tipo_value in POI_MAP.items():
            items = data.get(json_key) or []
            for i, nome in enumerate(items):
                poi_objects.append(
                    ComunePuntoInteresse(comune=comune, tipo=tipo_value, nome=nome, ordine=i)
                )
        if poi_objects:
            ComunePuntoInteresse.objects.bulk_create(poi_objects)

        # Eventi
        items = data.get('eventi_feste_sagre') or []
        if items:
            ComuneEvento.objects.bulk_create([
                ComuneEvento(comune=comune, nome=nome, ordine=i)
                for i, nome in enumerate(items)
            ])

        # Gemellaggi
        items = data.get('gemellaggi') or []
        if items:
            ComuneGemellaggio.objects.bulk_create([
                ComuneGemellaggio(comune=comune, citta=citta, ordine=i)
                for i, citta in enumerate(items)
            ])

        # Cittadini illustri
        items = data.get('cittadini_illustri') or []
        if items:
            ComuneCittadinoIllustre.objects.bulk_create([
                ComuneCittadinoIllustre(comune=comune, nome=nome, ordine=i)
                for i, nome in enumerate(items)
            ])
