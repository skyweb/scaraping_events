"""
Test suite per l'endpoint bulk (/api/v1/events/bulk/).

Organizzata in tre livelli:
  1. Unit test — serializer e validazione (nessuna richiesta HTTP)
  2. Test di integrazione — task Celery eseguito direttamente (nessun broker)
  3. Test funzionali — richieste HTTP end-to-end via APIClient

Eseguire con:
    docker exec -w /app/backend dev-backoffice \
      python manage.py test events.tests.test_bulk_endpoint -v2

    # Output tabellare
    docker exec -w /app/backend dev-backoffice \
      python manage.py test events.tests.test_bulk_endpoint \
      --testrunner events.tests.runner.TableTestRunner
"""
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from oauth2_provider.models import Application, AccessToken

from events.models import Event
from events.serializers import (
    EventScrapingSerializer,
    EventLegacySerializer,
)


# ---------------------------------------------------------------------------
# Dati di test riutilizzabili
# ---------------------------------------------------------------------------

def _evento_scraping(**overrides):
    """Evento nel formato scraping (con city/dates nested)."""
    data = {
        'uuid': 'bulk-test-001',
        'content_hash': 'hash001',
        'source': 'test_spider',
        'title': 'Concerto Jazz',
        'category': ['musica', 'jazz'],
        'city': {
            'city_name': 'Milano',
            'location_name': 'Blue Note',
            'location_address': 'Via Borsieri 37',
            'location_coordinates': {'lat': '45.4942', 'lng': '9.1970'},
        },
        'dates': {
            'date_start': '2026-06-15',
            'date_end': '2026-06-15',
            'time_start': '21:00',
            'time_end': '23:30',
            'time_info': 'Apertura porte ore 19:30',
        },
        'url': 'https://example.com/concerto',
        'description': 'Serata jazz dal vivo.',
        'image_url': 'https://example.com/img.jpg',
        'price': '25 EUR',
        'scraped_at': '2026-06-01T10:00:00Z',
    }
    data.update(overrides)
    return data


def _evento_legacy(**overrides):
    """Evento nel formato legacy (con details nested)."""
    data = {
        'title': 'Mostra Caravaggio',
        'source': 'test_legacy',
        'source_url': 'https://example.com/mostra',
        'scraped_at': '2026-06-01T10:00:00Z',
        'list': {
            'image': 'https://example.com/caravaggio.jpg',
            'category': ['arte', 'mostre'],
            'location_name': 'Palazzo Reale',
        },
        'details': {
            'where': {
                'name': 'Palazzo Reale',
                'location_address': 'Piazza Duomo 12, Milano',
                'location_coords': {'lat': '45.4637', 'lng': '9.1912'},
            },
            'image': 'https://example.com/caravaggio-detail.jpg',
            'price': '15 EUR',
            'when': {
                'date_start': '2026-06-01',
                'date_end': '2026-08-31',
                'raw_text': 'Da martedi a domenica, 10:00-19:00',
            },
            'description': 'Esposizione delle opere di Caravaggio.',
            'informations': {
                'website': 'https://palazzoreale.it',
                'raw_text': 'Info: 02-12345678',
            },
        },
    }
    data.update(overrides)
    return data


def _evento_minimo(**overrides):
    """Evento con solo i campi obbligatori."""
    data = {
        'uuid': 'bulk-min-001',
        'source': 'test_spider',
        'title': 'Evento Minimo',
    }
    data.update(overrides)
    return data


# ===========================================================================
# 1. UNIT TEST — Serializer
# ===========================================================================

class EventScrapingSerializerTest(TestCase):
    """Test di validazione e trasformazione del EventScrapingSerializer."""

    def test_campi_obbligatori_presenti(self):
        """uuid, source, title sono obbligatori."""
        ser = EventScrapingSerializer(data={})
        self.assertFalse(ser.is_valid())
        self.assertIn('uuid', ser.errors)
        self.assertIn('source', ser.errors)
        self.assertIn('title', ser.errors)

    def test_campi_obbligatori_mancanti_singoli(self):
        """Ogni campo obbligatorio mancante genera errore specifico."""
        for campo in ('uuid', 'source', 'title'):
            data = _evento_minimo()
            del data[campo]
            ser = EventScrapingSerializer(data=data)
            self.assertFalse(ser.is_valid(), f"Dovrebbe fallire senza '{campo}'")
            self.assertIn(campo, ser.errors)

    def test_evento_minimo_valido(self):
        """Evento con solo i campi obbligatori e' valido."""
        ser = EventScrapingSerializer(data=_evento_minimo())
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_evento_completo_valido(self):
        """Evento con tutti i campi compilati e' valido."""
        ser = EventScrapingSerializer(data=_evento_scraping())
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_flatten_city_nested(self):
        """Il campo nested 'city' viene appiattito in city_name, location_name, ecc."""
        ser = EventScrapingSerializer(data=_evento_scraping())
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        self.assertEqual(vd['city_name'], 'Milano')
        self.assertEqual(vd['location_name'], 'Blue Note')
        self.assertEqual(vd['location_address'], 'Via Borsieri 37')

    def test_flatten_dates_nested(self):
        """Il campo nested 'dates' viene appiattito in date_start, time_start, ecc."""
        ser = EventScrapingSerializer(data=_evento_scraping())
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        self.assertEqual(str(vd['date_start']), '2026-06-15')
        self.assertEqual(str(vd['date_end']), '2026-06-15')
        # Il serializer passa le stringhe come ricevute (senza secondi se non forniti)
        self.assertIn('21:00', str(vd['time_start']))
        self.assertIn('23:30', str(vd['time_end']))
        self.assertEqual(vd['time_info'], 'Apertura porte ore 19:30')

    def test_coordinate_parsate_correttamente(self):
        """Le coordinate vengono convertite in Point GeoDjango."""
        ser = EventScrapingSerializer(data=_evento_scraping())
        ser.is_valid(raise_exception=True)
        point = ser.validated_data['location_coordinates']
        self.assertIsNotNone(point)
        self.assertAlmostEqual(point.y, 45.4942, places=3)  # lat
        self.assertAlmostEqual(point.x, 9.1970, places=3)   # lng

    def test_coordinate_invalide_restituiscono_none(self):
        """Coordinate non valide non bloccano la validazione."""
        data = _evento_scraping()
        data['city']['location_coordinates'] = {'lat': 'invalid', 'lng': 'abc'}
        ser = EventScrapingSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertIsNone(ser.validated_data['location_coordinates'])

    def test_coordinate_assenti_restituiscono_none(self):
        """Coordinate assenti nel payload restituiscono None nel validated_data."""
        data = _evento_scraping()
        del data['city']['location_coordinates']
        ser = EventScrapingSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertIsNone(ser.validated_data['location_coordinates'])

    def test_category_none_accettata(self):
        """category=None e' accettata e resta None."""
        data = _evento_minimo(category=None)
        ser = EventScrapingSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertIsNone(ser.validated_data['category'])

    def test_category_lista_valida(self):
        """Lista di category valide viene mantenuta."""
        data = _evento_minimo(category=['musica', 'jazz'])
        ser = EventScrapingSerializer(data=data)
        ser.is_valid(raise_exception=True)
        self.assertEqual(ser.validated_data['category'], ['musica', 'jazz'])

    def test_raw_data_contiene_payload_originale(self):
        """raw_data contiene una copia del JSON originale inviato."""
        data = _evento_scraping()
        ser = EventScrapingSerializer(data=data)
        ser.is_valid(raise_exception=True)
        raw = ser.validated_data['raw_data']
        self.assertEqual(raw['uuid'], data['uuid'])
        self.assertEqual(raw['title'], data['title'])

    def test_campi_opzionali_vuoti_diventano_none(self):
        """Campi opzionali con stringa vuota diventano None."""
        data = _evento_minimo(url='', description='', image_url='', price='')
        ser = EventScrapingSerializer(data=data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        self.assertIsNone(vd['url'])
        self.assertIsNone(vd['description'])
        self.assertIsNone(vd['image_url'])
        self.assertIsNone(vd['price'])

    def test_city_none_non_blocca(self):
        """city=None non causa errore."""
        data = _evento_minimo(city=None)
        ser = EventScrapingSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertIsNone(ser.validated_data['city_name'])

    def test_dates_none_non_blocca(self):
        """dates=None non causa errore."""
        data = _evento_minimo(dates=None)
        ser = EventScrapingSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertIsNone(ser.validated_data['date_start'])

    def test_create_upsert(self):
        """Il serializer fa upsert: se uuid esiste, aggiorna invece di duplicare."""
        data = _evento_minimo(uuid='upsert-001', title='Versione 1')
        ser1 = EventScrapingSerializer(data=data)
        ser1.is_valid(raise_exception=True)
        ser1.save()
        self.assertEqual(Event.objects.filter(uuid='upsert-001').count(), 1)

        data['title'] = 'Versione 2'
        ser2 = EventScrapingSerializer(data=data)
        ser2.is_valid(raise_exception=True)
        ser2.save()
        self.assertEqual(Event.objects.filter(uuid='upsert-001').count(), 1)
        self.assertEqual(
            Event.objects.get(uuid='upsert-001').title,
            'Versione 2',
        )


class EventLegacySerializerTest(TestCase):
    """Test di validazione e trasformazione del EventLegacySerializer."""

    def test_evento_legacy_valido(self):
        """Evento nel formato legacy con tutti i campi e' valido."""
        ser = EventLegacySerializer(data=_evento_legacy())
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_uuid_generato_automaticamente(self):
        """Il formato legacy genera uuid da hash(title + date_start + location_name)."""
        ser = EventLegacySerializer(data=_evento_legacy())
        ser.is_valid(raise_exception=True)
        self.assertIsNotNone(ser.validated_data['uuid'])
        self.assertEqual(len(ser.validated_data['uuid']), 16)

    def test_content_hash_generato(self):
        """content_hash viene generato da hash(description + price)."""
        ser = EventLegacySerializer(data=_evento_legacy())
        ser.is_valid(raise_exception=True)
        self.assertIsNotNone(ser.validated_data['content_hash'])
        self.assertEqual(len(ser.validated_data['content_hash']), 16)

    def test_uuid_deterministico(self):
        """Lo stesso input produce sempre lo stesso uuid."""
        data = _evento_legacy()
        ser1 = EventLegacySerializer(data=data)
        ser1.is_valid(raise_exception=True)
        ser2 = EventLegacySerializer(data=data)
        ser2.is_valid(raise_exception=True)
        self.assertEqual(ser1.validated_data['uuid'], ser2.validated_data['uuid'])

    def test_flatten_details_where(self):
        """I dati nested di details.where vengono appiattiti."""
        ser = EventLegacySerializer(data=_evento_legacy())
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        self.assertEqual(vd['location_name'], 'Palazzo Reale')
        self.assertEqual(vd['location_address'], 'Piazza Duomo 12, Milano')

    def test_flatten_details_when(self):
        """I dati nested di details.when vengono appiattiti."""
        ser = EventLegacySerializer(data=_evento_legacy())
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        self.assertEqual(str(vd['date_start']), '2026-06-01')
        self.assertEqual(str(vd['date_end']), '2026-08-31')

    def test_coordinate_legacy_parsate(self):
        """Le coordinate nel formato legacy vengono convertite in Point GeoDjango."""
        ser = EventLegacySerializer(data=_evento_legacy())
        ser.is_valid(raise_exception=True)
        point = ser.validated_data['location_coordinates']
        self.assertIsNotNone(point)
        self.assertAlmostEqual(point.y, 45.4637, places=3)

    def test_category_stringa_csv(self):
        """Category come stringa CSV viene convertita in lista."""
        data = _evento_legacy()
        data['list']['category'] = 'arte, mostre, cultura'
        ser = EventLegacySerializer(data=data)
        ser.is_valid(raise_exception=True)
        self.assertEqual(ser.validated_data['category'], ['arte', 'mostre', 'cultura'])

    def test_image_fallback_da_list(self):
        """Se details.image e' vuoto, usa list.image."""
        data = _evento_legacy()
        data['details']['image'] = ''
        data['list']['image'] = 'https://example.com/fallback.jpg'
        ser = EventLegacySerializer(data=data)
        ser.is_valid(raise_exception=True)
        self.assertEqual(ser.validated_data['image_url'], 'https://example.com/fallback.jpg')

    def test_campi_obbligatori_legacy(self):
        """title e source sono obbligatori nel formato legacy."""
        ser = EventLegacySerializer(data={})
        self.assertFalse(ser.is_valid())
        self.assertIn('title', ser.errors)
        self.assertIn('source', ser.errors)


# ===========================================================================
# 2. TEST DI INTEGRAZIONE — Task Celery (senza broker)
# ===========================================================================

class ProcessBulkEventsTaskTest(TestCase):
    """Test diretto del task process_bulk_events (invocato come funzione)."""

    def test_batch_tutti_validi(self):
        """Tutti gli eventi validi vengono creati."""
        from events.tasks import process_bulk_events
        events = [
            _evento_minimo(uuid=f'task-ok-{i}', title=f'Evento {i}')
            for i in range(5)
        ]
        result = process_bulk_events(events, spider_name='test_spider')
        self.assertEqual(result['created_count'], 5)
        self.assertEqual(result['failed_count'], 0)
        self.assertEqual(result['spider_name'], 'test_spider')
        self.assertEqual(Event.objects.filter(source='test_spider').count(), 5)

    def test_batch_tutti_invalidi(self):
        """Nessun evento valido: created_count=0."""
        from events.tasks import process_bulk_events
        events = [
            {'uuid': 'no-title-1', 'source': 'x'},
            {'uuid': 'no-title-2', 'source': 'x'},
        ]
        result = process_bulk_events(events)
        self.assertEqual(result['created_count'], 0)
        self.assertEqual(result['failed_count'], 2)

    def test_batch_misto_validi_invalidi(self):
        """Mix di eventi validi e invalidi."""
        from events.tasks import process_bulk_events
        events = [
            _evento_minimo(uuid='mix-ok-1', title='Valido 1'),
            {'uuid': 'mix-fail-1', 'source': 'x'},  # manca title
            _evento_minimo(uuid='mix-ok-2', title='Valido 2'),
            {'source': 'x', 'title': 'No UUID'},     # manca uuid
        ]
        result = process_bulk_events(events)
        self.assertEqual(result['created_count'], 2)
        self.assertEqual(result['failed_count'], 2)
        # Verifica indici dei falliti
        failed_indices = [f['index'] for f in result['failed_events']]
        self.assertEqual(failed_indices, [1, 3])

    def test_batch_vuoto(self):
        """Lista vuota: nessun evento creato ne' fallito."""
        from events.tasks import process_bulk_events
        result = process_bulk_events([])
        self.assertEqual(result['created_count'], 0)
        self.assertEqual(result['failed_count'], 0)

    def test_failed_events_contengono_errori(self):
        """Ogni evento fallito ha errors, index e original_data."""
        from events.tasks import process_bulk_events
        events = [{'uuid': 'err-1', 'source': 'x'}]
        result = process_bulk_events(events)
        failed = result['failed_events'][0]
        self.assertIn('errors', failed)
        self.assertIn('index', failed)
        self.assertIn('original_data', failed)
        self.assertEqual(failed['index'], 0)

    def test_formato_scraping_nested(self):
        """Il task gestisce correttamente il formato scraping con city/dates nested."""
        from events.tasks import process_bulk_events
        events = [_evento_scraping(uuid='task-nested-001')]
        result = process_bulk_events(events)
        self.assertEqual(result['created_count'], 1)
        ev = Event.objects.get(uuid='task-nested-001')
        self.assertEqual(ev.city_name, 'Milano')
        self.assertEqual(ev.location_name, 'Blue Note')
        self.assertEqual(str(ev.date_start), '2026-06-15')

    def test_batch_grande(self):
        """Batch con molti eventi (100) viene processato correttamente."""
        from events.tasks import process_bulk_events
        events = [
            _evento_minimo(uuid=f'big-{i:04d}', title=f'Evento Batch {i}')
            for i in range(100)
        ]
        result = process_bulk_events(events)
        self.assertEqual(result['created_count'], 100)
        self.assertEqual(result['failed_count'], 0)
        self.assertEqual(Event.objects.filter(uuid__startswith='big-').count(), 100)

    def test_fallback_su_errore_bulk_create(self):
        """Se bulk_create fallisce con errore generico, il task usa il fallback save singoli."""
        from events.tasks import process_bulk_events
        events = [_evento_minimo(uuid='fallback-001', title='Fallback Test')]
        with patch.object(
            Event.objects, 'bulk_create',
            side_effect=Exception('Simulated bulk failure'),
        ):
            result = process_bulk_events(events)
        # Il fallback dovrebbe comunque creare l'evento
        self.assertEqual(result['created_count'], 1)
        self.assertTrue(Event.objects.filter(uuid='fallback-001').exists())

    def test_retry_su_operational_error(self):
        """OperationalError causa un retry del task."""
        from events.tasks import process_bulk_events
        from django.db import OperationalError

        events = [_evento_minimo(uuid='retry-001')]
        with patch.object(
            Event.objects, 'bulk_create',
            side_effect=OperationalError('connection lost'),
        ):
            with self.assertRaises(Exception):
                # Il task e' decorato con bind=True e max_retries=3,
                # chiamato direttamente (non via .delay) rilancia l'eccezione
                process_bulk_events(events)


# ===========================================================================
# 3. TEST FUNZIONALI — Endpoint HTTP end-to-end
# ===========================================================================

class BulkEndpointBaseTestCase(TestCase):
    """Base con setup OAuth2 per i test funzionali del bulk endpoint."""

    BULK_URL = '/api/v1/events/bulk/'
    BULK_STATUS_URL = '/api/v1/events/bulk-status/'

    @classmethod
    def setUpTestData(cls):
        """Crea utente, app OAuth2 e token read/write per i test funzionali."""
        cls.user = User.objects.create_user(
            username='bulktest', password='testpass123',
        )
        cls.application = Application.objects.create(
            name='bulk-test-app',
            user=cls.user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )
        cls.read_token = AccessToken.objects.create(
            user=cls.user,
            token='bulk-read-token',
            application=cls.application,
            expires=timezone.now() + timedelta(hours=1),
            scope='read',
        )
        cls.write_token = AccessToken.objects.create(
            user=cls.user,
            token='bulk-write-token',
            application=cls.application,
            expires=timezone.now() + timedelta(hours=1),
            scope='read write',
        )

    def setUp(self):
        """Inizializza il client API per i test funzionali."""
        self.client = APIClient()

    def auth_read(self):
        """Imposta il token con scope 'read'."""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer bulk-read-token')

    def auth_write(self):
        """Imposta il token con scope 'read write'."""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer bulk-write-token')

    def auth_none(self):
        """Rimuove le credenziali di autenticazione."""
        self.client.credentials()


class BulkSyncEndpointTest(BulkEndpointBaseTestCase):
    """Test funzionali: POST /api/v1/events/bulk/?sync=true"""

    def _post_bulk_sync(self, payload, **kwargs):
        """Shortcut per POST al bulk endpoint in modalita' sincrona."""
        return self.client.post(
            f'{self.BULK_URL}?sync=true',
            data=payload,
            format='json',
            **kwargs,
        )

    # --- Autenticazione ---

    def test_no_token_returns_401(self):
        """Richiesta senza token -> 401 Unauthorized."""
        self.auth_none()
        resp = self._post_bulk_sync({'events': [_evento_minimo()]})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_read_token_returns_403(self):
        """Token con solo scope 'read' non puo' fare bulk create -> 403."""
        self.auth_read()
        resp = self._post_bulk_sync({'events': [_evento_minimo()]})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # --- Validazione input ---

    def test_payload_senza_chiave_events(self):
        """Payload senza la chiave 'events' -> 400."""
        self.auth_write()
        resp = self._post_bulk_sync({'data': []})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', resp.data)

    def test_events_lista_vuota(self):
        """Lista eventi vuota -> 400."""
        self.auth_write()
        resp = self._post_bulk_sync({'events': []})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_payload_vuoto(self):
        """Payload completamente vuoto -> 400."""
        self.auth_write()
        resp = self._post_bulk_sync({})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Creazione eventi ---

    def test_singolo_evento_valido(self):
        """Un singolo evento valido viene creato con successo -> 201."""
        self.auth_write()
        resp = self._post_bulk_sync({
            'events': [_evento_minimo(uuid='func-single-001')],
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['created_count'], 1)
        self.assertEqual(resp.data['failed_count'], 0)
        self.assertTrue(Event.objects.filter(uuid='func-single-001').exists())

    def test_multipli_eventi_validi(self):
        """Multipli eventi validi vengono tutti creati con successo -> 201."""
        self.auth_write()
        events = [
            _evento_minimo(uuid=f'func-multi-{i}', title=f'Evento {i}')
            for i in range(3)
        ]
        resp = self._post_bulk_sync({'events': events})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['created_count'], 3)
        self.assertEqual(resp.data['failed_count'], 0)
        self.assertEqual(len(resp.data['successful_events']), 3)

    def test_evento_completo_con_nested(self):
        """Evento completo con city/dates nested viene salvato correttamente."""
        self.auth_write()
        resp = self._post_bulk_sync({
            'events': [_evento_scraping(uuid='func-nested-001')],
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        ev = Event.objects.get(uuid='func-nested-001')
        self.assertEqual(ev.city_name, 'Milano')
        self.assertEqual(ev.location_name, 'Blue Note')
        self.assertEqual(str(ev.date_start), '2026-06-15')
        self.assertIsNotNone(ev.location_coordinates)

    # --- Mix validi/invalidi ---

    def test_mix_validi_e_invalidi_returns_200(self):
        """Mix di eventi: status 200 (partial success)."""
        self.auth_write()
        resp = self._post_bulk_sync({
            'events': [
                _evento_minimo(uuid='func-mix-ok', title='Valido'),
                {'uuid': 'func-mix-fail', 'source': 'x'},  # manca title
            ],
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['created_count'], 1)
        self.assertEqual(resp.data['failed_count'], 1)

    def test_tutti_invalidi_returns_400(self):
        """Tutti gli eventi invalidi -> 400 con created_count=0."""
        self.auth_write()
        resp = self._post_bulk_sync({
            'events': [
                {'uuid': 'fail-1', 'source': 'x'},
                {'uuid': 'fail-2', 'source': 'x'},
            ],
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['created_count'], 0)
        self.assertEqual(resp.data['failed_count'], 2)

    def test_failed_events_struttura(self):
        """Ogni evento fallito contiene errors, index e original_data."""
        self.auth_write()
        resp = self._post_bulk_sync({
            'events': [
                _evento_minimo(uuid='ok-1'),
                {'uuid': 'bad-1', 'source': 'x'},  # index 1
            ],
        })
        failed = resp.data['failed_events']
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]['index'], 1)
        self.assertIn('errors', failed[0])
        self.assertIn('original_data', failed[0])

    # --- Upsert ---

    def test_upsert_aggiorna_evento_esistente(self):
        """Bulk sync con uuid gia' esistente aggiorna invece di duplicare."""
        self.auth_write()
        self._post_bulk_sync({
            'events': [_evento_minimo(uuid='upsert-001', title='V1')],
        })
        self._post_bulk_sync({
            'events': [_evento_minimo(uuid='upsert-001', title='V2')],
        })
        self.assertEqual(Event.objects.filter(uuid='upsert-001').count(), 1)
        self.assertEqual(
            Event.objects.get(uuid='upsert-001').title, 'V2',
        )

    # --- Formato legacy ---

    def test_formato_legacy_rilevato(self):
        """Il bulk sync rileva automaticamente il formato legacy (con 'details')."""
        self.auth_write()
        resp = self._post_bulk_sync({
            'events': [_evento_legacy()],
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['created_count'], 1)
        ev = resp.data['successful_events'][0]
        self.assertEqual(ev['location_name'], 'Palazzo Reale')

    def test_mix_formato_scraping_e_legacy(self):
        """Il bulk sync gestisce un mix di formati nella stessa richiesta."""
        self.auth_write()
        resp = self._post_bulk_sync({
            'events': [
                _evento_scraping(uuid='mix-new-001'),
                _evento_legacy(title='Evento Legacy Mix'),
            ],
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['created_count'], 2)

    # --- Struttura risposta ---

    def test_risposta_contiene_tutti_i_campi(self):
        """La risposta bulk contiene successful_events, failed_events e conteggi."""
        self.auth_write()
        resp = self._post_bulk_sync({
            'events': [_evento_minimo(uuid='resp-001')],
        })
        self.assertIn('successful_events', resp.data)
        self.assertIn('failed_events', resp.data)
        self.assertIn('created_count', resp.data)
        self.assertIn('failed_count', resp.data)

    def test_successful_events_serializzati_completi(self):
        """Gli eventi nella risposta contengono tutti i campi del EventSerializer."""
        self.auth_write()
        resp = self._post_bulk_sync({
            'events': [_evento_scraping(uuid='ser-001')],
        })
        ev = resp.data['successful_events'][0]
        self.assertIn('id', ev)
        self.assertIn('uuid', ev)
        self.assertIn('source', ev)
        self.assertIn('title', ev)
        self.assertIn('city_name', ev)
        self.assertIn('created_at', ev)


class BulkAsyncEndpointTest(BulkEndpointBaseTestCase):
    """Test funzionali: POST /api/v1/events/bulk/ (async, default)."""

    def test_async_returns_202(self):
        """POST bulk senza ?sync=true -> 202 Accepted."""
        mock_result = MagicMock()
        mock_result.id = 'async-task-001'

        self.auth_write()
        with patch('events.tasks.process_bulk_events.apply_async', return_value=mock_result):
            resp = self.client.post(
                self.BULK_URL,
                data={'events': [_evento_minimo(uuid='async-001')]},
                format='json',
            )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('task_id', resp.data)
        self.assertEqual(resp.data['status'], 'PENDING')
        self.assertIn('message', resp.data)

    def test_async_con_spider_name(self):
        """Il campo spider viene passato al task."""
        mock_result = MagicMock()
        mock_result.id = 'async-spider-001'

        self.auth_write()
        with patch('events.tasks.process_bulk_events.apply_async', return_value=mock_result) as mock_apply:
            resp = self.client.post(
                self.BULK_URL,
                data={
                    'events': [_evento_minimo(uuid='spider-001')],
                    'spider': 'puglia_culture',
                },
                format='json',
            )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(resp.data['spider'], 'puglia_culture')
        # Verifica che spider_name sia passato come kwarg
        call_kwargs = mock_apply.call_args
        self.assertEqual(call_kwargs[1]['kwargs']['spider_name'], 'puglia_culture')

    def test_async_empty_events_returns_400(self):
        """Anche in async, lista vuota -> 400 (validato prima del dispatch)."""
        self.auth_write()
        resp = self.client.post(
            self.BULK_URL,
            data={'events': []},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sync_true_bypassa_celery(self):
        """?sync=true non chiama apply_async."""
        self.auth_write()
        with patch('events.tasks.process_bulk_events.apply_async') as mock_apply:
            resp = self.client.post(
                f'{self.BULK_URL}?sync=true',
                data={'events': [_evento_minimo(uuid='no-celery-001')]},
                format='json',
            )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        mock_apply.assert_not_called()

    def test_sync_varianti_parametro(self):
        """sync=1, sync=yes, sync=TRUE sono tutti accettati."""
        for value in ('1', 'yes', 'TRUE', 'True'):
            self.auth_write()
            with patch('events.tasks.process_bulk_events.apply_async') as mock_apply:
                resp = self.client.post(
                    f'{self.BULK_URL}?sync={value}',
                    data={'events': [_evento_minimo(uuid=f'sync-var-{value}')]},
                    format='json',
                )
            self.assertIn(
                resp.status_code,
                [status.HTTP_200_OK, status.HTTP_201_CREATED],
                f"sync={value} dovrebbe essere sincrono",
            )
            mock_apply.assert_not_called()


class BulkStatusEndpointTest(BulkEndpointBaseTestCase):
    """Test funzionali: GET /api/v1/events/bulk-status/{task_id}/"""

    def test_status_pending(self):
        """GET bulk-status con task in attesa -> status PENDING, result None."""
        mock_result = MagicMock()
        mock_result.status = 'PENDING'
        mock_result.ready.return_value = False

        self.auth_read()
        with patch('events.views.AsyncResult', return_value=mock_result):
            resp = self.client.get(f'{self.BULK_STATUS_URL}task-123/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'PENDING')
        self.assertEqual(resp.data['task_id'], 'task-123')
        self.assertIsNone(resp.data['result'])

    def test_status_success(self):
        """GET bulk-status con task completato -> status SUCCESS con risultato."""
        mock_result = MagicMock()
        mock_result.status = 'SUCCESS'
        mock_result.ready.return_value = True
        mock_result.successful.return_value = True
        mock_result.result = {
            'created_count': 10,
            'failed_count': 2,
            'failed_events': [{'index': 3, 'errors': {'title': ['required']}}],
        }

        self.auth_read()
        with patch('events.views.AsyncResult', return_value=mock_result):
            resp = self.client.get(f'{self.BULK_STATUS_URL}task-success/')
        self.assertEqual(resp.data['status'], 'SUCCESS')
        self.assertEqual(resp.data['result']['created_count'], 10)

    def test_status_failure(self):
        """GET bulk-status con task fallito -> status FAILURE con messaggio errore."""
        mock_result = MagicMock()
        mock_result.status = 'FAILURE'
        mock_result.ready.return_value = True
        mock_result.successful.return_value = False
        mock_result.result = Exception('DB down')

        self.auth_read()
        with patch('events.views.AsyncResult', return_value=mock_result):
            resp = self.client.get(f'{self.BULK_STATUS_URL}task-fail/')
        self.assertEqual(resp.data['status'], 'FAILURE')
        self.assertIn('DB down', resp.data['result'])

    def test_status_richiede_autenticazione(self):
        """GET bulk-status senza token -> 401 Unauthorized."""
        self.auth_none()
        resp = self.client.get(f'{self.BULK_STATUS_URL}task-xyz/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_status_con_read_token_ok(self):
        """bulk-status richiede scope read, non write."""
        mock_result = MagicMock()
        mock_result.status = 'PENDING'
        mock_result.ready.return_value = False

        self.auth_read()
        with patch('events.views.AsyncResult', return_value=mock_result):
            resp = self.client.get(f'{self.BULK_STATUS_URL}task-read/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)