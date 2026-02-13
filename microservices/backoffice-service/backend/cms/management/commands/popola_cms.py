"""
Management command per popolare il CMS con dati di esempio dal frontend.
"""
from django.core.management.base import BaseCommand

from cms.models import PaginaCitta, TabNavigazione, SezionePagina, ArticoloSezione


class Command(BaseCommand):
    help = 'Popola il CMS con dati di esempio presi dal frontend'

    def handle(self, *args, **options):
        # Pulizia dati esistenti
        ArticoloSezione.objects.all().delete()
        SezionePagina.objects.all().delete()
        TabNavigazione.objects.all().delete()
        PaginaCitta.objects.all().delete()
        self.stdout.write('Dati CMS precedenti eliminati.')

        # =====================================================================
        # Pagina Roma
        # =====================================================================
        roma = PaginaCitta.objects.create(nome='Roma', slug='roma', ordine=0)
        self.stdout.write(f'Creata pagina: {roma}')

        # Tab navigazione (da local-news.json)
        nav_items = [
            ('Notizie', '/roma/notizie'),
            ('Eventi', '/roma/eventi'),
            ('Farmacie', '/roma/farmacie'),
            ('Aziende', '/roma/aziende'),
            ('Magazine', '/roma/magazine'),
            ('Mappa', '/roma/mappa'),
            ('Previsioni', '/roma/previsioni'),
        ]
        for i, (label, url) in enumerate(nav_items):
            TabNavigazione.objects.create(pagina=roma, label=label, url=url, ordine=i)
        self.stdout.write(f'  {len(nav_items)} tab navigazione creati')

        # -----------------------------------------------------------------
        # Sezione: Notizie Locali (da local-news.json)
        # -----------------------------------------------------------------
        sez_locali = SezionePagina.objects.create(
            pagina=roma, titolo='Notizie Locali', colore='blue',
            link_vedi_tutti='/roma/notizie', ordine=0,
        )
        articoli_locali = [
            {
                'titolo': 'Quanto valgono le medaglie delle Olimpiadi di Milano Cortina',
                'immagine_url': 'https://picsum.photos/seed/roma1/302/170',
                'categoria': 'SPORT', 'colore_categoria': 'red',
                'url': '/articolo/medaglie-olimpiadi-milano-cortina',
            },
            {
                'titolo': 'Le 10 città più accoglienti al mondo per il 2026: una è in Italia',
                'immagine_url': 'https://picsum.photos/seed/roma2/302/170',
                'categoria': 'ECCELLENZE', 'colore_categoria': 'blue',
                'url': '/articolo/citta-accoglienti-2026',
            },
            {
                'titolo': 'Alligatore avvistato in un canale in Italia, la Polizia: "Attendibile"',
                'immagine_url': 'https://picsum.photos/seed/roma3/302/170',
                'categoria': 'TERRITORIO', 'colore_categoria': 'red',
                'url': '/articolo/alligatore-canale-italia',
            },
            {
                'titolo': 'Smog, queste sono le città più inquinate d\'Italia: la nuova classifica',
                'immagine_url': 'https://picsum.photos/seed/roma4/302/170',
                'categoria': 'TERRITORIO', 'colore_categoria': 'blue',
                'url': '/articolo/citta-inquinate-classifica',
            },
        ]
        for i, art in enumerate(articoli_locali):
            ArticoloSezione.objects.create(sezione=sez_locali, ordine=i, **art)
        self.stdout.write(f'  Sezione "{sez_locali.titolo}": {len(articoli_locali)} articoli')

        # -----------------------------------------------------------------
        # Sezione: Notizie (MainFeed newsItems)
        # -----------------------------------------------------------------
        sez_notizie = SezionePagina.objects.create(
            pagina=roma, titolo='Notizie', colore='blue',
            link_vedi_tutti='/roma/notizie', ordine=1,
        )
        articoli_notizie = [
            {
                'titolo': 'Allerta meteo in diverse regioni: piogge intense previste per domani',
                'immagine_url': 'https://picsum.photos/seed/n1/480/300',
                'categoria': 'CRONACA', 'colore_categoria': 'red',
                'url': '/articolo/allerta-meteo-regioni',
            },
            {
                'titolo': 'Governo, tensioni nella maggioranza: vertice a Palazzo Chigi',
                'immagine_url': 'https://picsum.photos/seed/n2/480/300',
                'categoria': 'POLITICA', 'colore_categoria': 'blue',
                'url': '/articolo/governo-tensioni-maggioranza',
            },
            {
                'titolo': 'USA, la Fed lascia i tassi invariati: Wall Street reagisce positivamente',
                'immagine_url': 'https://picsum.photos/seed/n3/480/300',
                'categoria': 'ESTERI', 'colore_categoria': 'red',
                'url': '/articolo/fed-tassi-invariati',
            },
            {
                'titolo': 'Inflazione in calo: i dati Istat confermano il trend positivo',
                'immagine_url': 'https://picsum.photos/seed/n4/480/300',
                'categoria': 'ECONOMIA', 'colore_categoria': 'blue',
                'url': '/articolo/inflazione-calo-istat',
            },
            {
                'titolo': 'Terremoto in Emilia: scossa di magnitudo 3.2, nessun danno',
                'immagine_url': 'https://picsum.photos/seed/n5/480/300',
                'categoria': 'CRONACA', 'colore_categoria': 'red',
                'url': '/articolo/terremoto-emilia',
            },
            {
                'titolo': 'Riforma pensioni, le novità per il 2026: chi ci guadagna',
                'immagine_url': 'https://picsum.photos/seed/n6/480/300',
                'categoria': 'POLITICA', 'colore_categoria': 'blue',
                'url': '/articolo/riforma-pensioni-2026',
            },
        ]
        for i, art in enumerate(articoli_notizie):
            ArticoloSezione.objects.create(sezione=sez_notizie, ordine=i, **art)
        self.stdout.write(f'  Sezione "{sez_notizie.titolo}": {len(articoli_notizie)} articoli')

        # -----------------------------------------------------------------
        # Sezione: Sport (MainFeed sportItems)
        # -----------------------------------------------------------------
        sez_sport = SezionePagina.objects.create(
            pagina=roma, titolo='Sport', colore='green',
            link_vedi_tutti='/roma/sport', ordine=2,
        )
        articoli_sport = [
            {
                'titolo': 'Serie A, 25ª giornata: risultati, classifica e marcatori',
                'immagine_url': 'https://picsum.photos/seed/s1/480/300',
                'categoria': 'CALCIO', 'colore_categoria': 'red',
                'url': '/articolo/serie-a-25-giornata',
            },
            {
                'titolo': 'Juve-Real Madrid, Thiago Motta: "Ce la giocheremo al massimo"',
                'immagine_url': 'https://picsum.photos/seed/s2/480/300',
                'categoria': 'CHAMPIONS', 'colore_categoria': 'blue',
                'url': '/articolo/juve-real-madrid-champions',
            },
            {
                'titolo': 'Test Bahrain: Ferrari velocissima, Leclerc primo nel Day 2',
                'immagine_url': 'https://picsum.photos/seed/s3/480/300',
                'categoria': 'FORMULA 1', 'colore_categoria': 'red',
                'url': '/articolo/test-bahrain-ferrari',
            },
            {
                'titolo': 'Sinner vince in due set e vola ai quarti del torneo di Dubai',
                'immagine_url': 'https://picsum.photos/seed/s4/480/300',
                'categoria': 'TENNIS', 'colore_categoria': 'blue',
                'url': '/articolo/sinner-quarti-dubai',
            },
            {
                'titolo': 'Calciomercato: le trattative dell\'ultimo giorno di sessione',
                'immagine_url': 'https://picsum.photos/seed/s5/480/300',
                'categoria': 'CALCIO', 'colore_categoria': 'red',
                'url': '/articolo/calciomercato-ultimo-giorno',
            },
            {
                'titolo': 'Eurolega: Olimpia Milano batte il Barcellona in trasferta',
                'immagine_url': 'https://picsum.photos/seed/s6/480/300',
                'categoria': 'BASKET', 'colore_categoria': 'blue',
                'url': '/articolo/eurolega-olimpia-barcellona',
            },
        ]
        for i, art in enumerate(articoli_sport):
            ArticoloSezione.objects.create(sezione=sez_sport, ordine=i, **art)
        self.stdout.write(f'  Sezione "{sez_sport.titolo}": {len(articoli_sport)} articoli')

        # -----------------------------------------------------------------
        # Sezione: Tecnologia (MainFeed techItems)
        # -----------------------------------------------------------------
        sez_tech = SezionePagina.objects.create(
            pagina=roma, titolo='Tecnologia', colore='orange',
            link_vedi_tutti='/roma/tecnologia', ordine=3,
        )
        articoli_tech = [
            {
                'titolo': 'ChatGPT compie 3 anni: come ha cambiato il modo di lavorare',
                'immagine_url': 'https://picsum.photos/seed/t1/480/300',
                'categoria': 'AI', 'colore_categoria': 'blue',
                'url': '/articolo/chatgpt-3-anni',
            },
            {
                'titolo': 'Samsung Galaxy S26: prime immagini e specifiche trapelate',
                'immagine_url': 'https://picsum.photos/seed/t2/480/300',
                'categoria': 'SMARTPHONE', 'colore_categoria': 'red',
                'url': '/articolo/samsung-galaxy-s26',
            },
            {
                'titolo': 'Auto elettriche 2026: i modelli più attesi sotto i 30mila euro',
                'immagine_url': 'https://picsum.photos/seed/t3/480/300',
                'categoria': 'AUTO', 'colore_categoria': 'blue',
                'url': '/articolo/auto-elettriche-2026',
            },
            {
                'titolo': 'Attenzione alla nuova truffa via SMS: come riconoscerla',
                'immagine_url': 'https://picsum.photos/seed/t4/480/300',
                'categoria': 'CYBERSECURITY', 'colore_categoria': 'red',
                'url': '/articolo/truffa-sms-come-riconoscerla',
            },
            {
                'titolo': 'GTA 6: Rockstar conferma la data di uscita per ottobre 2026',
                'immagine_url': 'https://picsum.photos/seed/t5/480/300',
                'categoria': 'GAMING', 'colore_categoria': 'blue',
                'url': '/articolo/gta-6-data-uscita',
            },
            {
                'titolo': 'SpaceX: il razzo Starship completa con successo il sesto volo',
                'immagine_url': 'https://picsum.photos/seed/t6/480/300',
                'categoria': 'SPAZIO', 'colore_categoria': 'red',
                'url': '/articolo/spacex-starship-sesto-volo',
            },
        ]
        for i, art in enumerate(articoli_tech):
            ArticoloSezione.objects.create(sezione=sez_tech, ordine=i, **art)
        self.stdout.write(f'  Sezione "{sez_tech.titolo}": {len(articoli_tech)} articoli')

        # -----------------------------------------------------------------
        # Sezione: Spettacoli (MainFeed spettacoliItems)
        # -----------------------------------------------------------------
        sez_spett = SezionePagina.objects.create(
            pagina=roma, titolo='Spettacoli', colore='red',
            link_vedi_tutti='/roma/spettacoli', ordine=4,
        )
        articoli_spett = [
            {
                'titolo': 'Oscar 2026: le previsioni sui favoriti e le sorprese attese',
                'immagine_url': 'https://picsum.photos/seed/sp1/480/300',
                'categoria': 'CINEMA', 'colore_categoria': 'blue',
                'url': '/articolo/oscar-2026-previsioni',
            },
            {
                'titolo': 'Ascolti TV ieri: chi ha vinto la prima serata di lunedì',
                'immagine_url': 'https://picsum.photos/seed/sp2/480/300',
                'categoria': 'TV', 'colore_categoria': 'red',
                'url': '/articolo/ascolti-tv-prima-serata',
            },
            {
                'titolo': 'Sanremo 2026: i nomi dei big in gara e le prime anticipazioni',
                'immagine_url': 'https://picsum.photos/seed/sp3/480/300',
                'categoria': 'MUSICA', 'colore_categoria': 'blue',
                'url': '/articolo/sanremo-2026-big-gara',
            },
            {
                'titolo': "La coppia dell'anno si è lasciata: l'annuncio sui social",
                'immagine_url': 'https://picsum.photos/seed/sp4/480/300',
                'categoria': 'GOSSIP', 'colore_categoria': 'red',
                'url': '/articolo/coppia-anno-lasciata',
            },
            {
                'titolo': 'Le serie TV da vedere a febbraio: la guida completa',
                'immagine_url': 'https://picsum.photos/seed/sp5/480/300',
                'categoria': 'SERIE TV', 'colore_categoria': 'blue',
                'url': '/articolo/serie-tv-febbraio-guida',
            },
            {
                'titolo': 'I libri più venduti della settimana: la classifica aggiornata',
                'immagine_url': 'https://picsum.photos/seed/sp6/480/300',
                'categoria': 'LIBRI', 'colore_categoria': 'red',
                'url': '/articolo/libri-piu-venduti-settimana',
            },
        ]
        for i, art in enumerate(articoli_spett):
            ArticoloSezione.objects.create(sezione=sez_spett, ordine=i, **art)
        self.stdout.write(f'  Sezione "{sez_spett.titolo}": {len(articoli_spett)} articoli')

        # =====================================================================
        # Riepilogo
        # =====================================================================
        tot_sez = SezionePagina.objects.count()
        tot_art = ArticoloSezione.objects.count()
        tot_tab = TabNavigazione.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f'\nCMS popolato: 1 città, {tot_tab} tab, {tot_sez} sezioni, {tot_art} articoli'
        ))
