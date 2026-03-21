"""
Test suite per le API Staging Events (/api/v1/events/).

Legge gli esempi JSON dallo schema OpenAPI generato da drf-spectacular
e li usa per testare tutti gli endpoint.

Eseguire con:
    # Output standard
    docker exec -w /app/backend events-backoffice \
      python manage.py test events.tests.test_staging_api -v2

    # Output tabellare
    docker exec -w /app/backend events-backoffice \
      python manage.py test events.tests.test_staging_api \
      --testrunner events.tests.runner.TableTestRunner
"""
import json
from datetime import timedelta
from datetime import datetime as dt

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from oauth2_provider.models import Application, AccessToken
from drf_spectacular.generators import SchemaGenerator

from events.models import Event


# ---------------------------------------------------------------------------
# Client che traccia le chiamate API per il report tabellare
# ---------------------------------------------------------------------------

class TrackingAPIClient(APIClient):
    """APIClient che registra ogni richiesta HTTP in test._api_calls."""

    def __init__(self, test_instance=None, *args, **kwargs):
        """Inizializza il client con un riferimento al test per registrare le chiamate."""
        super().__init__(*args, **kwargs)
        self._test = test_instance

    def generic(self, method, path, *args, **kwargs):
        """Intercetta ogni richiesta HTTP e la registra in test._api_calls."""
        response = super().generic(method, path, *args, **kwargs)
        if self._test and hasattr(self._test, '_api_calls'):
            self._test._api_calls.append({
                'method': method.upper(),
                'path': path.split('?')[0],
                'status_code': response.status_code,
            })
        return response


# ---------------------------------------------------------------------------
# Helper: genera lo schema OpenAPI e ne estrae gli esempi
# ---------------------------------------------------------------------------

def get_openapi_schema():
    """Genera lo schema OpenAPI tramite drf-spectacular."""
    generator = SchemaGenerator()
    return generator.get_schema(request=None, public=True)


def extract_examples(schema, path, method):
    """
    Estrae gli esempi di request dallo schema OpenAPI per un dato path/method.
    Restituisce una lista di dict: [{'name': ..., 'summary': ..., 'value': ...}]
    """
    path_item = schema.get('paths', {}).get(path, {})
    operation = path_item.get(method, {})
    request_body = operation.get('requestBody', {})
    content = request_body.get('content', {}).get('application/json', {})

    examples = []
    for name, data in content.get('examples', {}).items():
        examples.append({
            'name': name,
            'summary': data.get('summary', ''),
            'value': data.get('value'),
        })
    return examples


# ===========================================================================
# Base class con setup OAuth2
# ===========================================================================

class StagingAPIBaseTestCase(TestCase):
    """Base con creazione utente, app OAuth2 e token read/write."""

    @classmethod
    def setUpTestData(cls):
        """Crea utente, app OAuth2 e token read/write per i test."""
        cls.user = User.objects.create_user(
            username='testapi', password='testpass123',
        )
        cls.application = Application.objects.create(
            name='test-app',
            user=cls.user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )
        cls.read_token = AccessToken.objects.create(
            user=cls.user,
            token='test-read-token',
            application=cls.application,
            expires=timezone.now() + timedelta(hours=1),
            scope='read',
        )
        cls.write_token = AccessToken.objects.create(
            user=cls.user,
            token='test-write-token',
            application=cls.application,
            expires=timezone.now() + timedelta(hours=1),
            scope='read write',
        )

    def setUp(self):
        """Inizializza il client di test con tracking delle chiamate API."""
        self._api_calls = []
        self.client = TrackingAPIClient(test_instance=self)

    # -- shortcut autenticazione --
    def auth_read(self):
        """Imposta il token con scope 'read'."""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer test-read-token')

    def auth_write(self):
        """Imposta il token con scope 'read write'."""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer test-write-token')

    def auth_none(self):
        """Rimuove le credenziali di autenticazione."""
        self.client.credentials()

    # -- helper per creare un evento in DB --
    def create_event(self, **overrides):
        """Crea un Event nel DB con valori di default sovrascrivibili."""
        defaults = {
            'uuid': 'test-uuid-001',
            'source': 'test_source',
            'title': 'Evento di test',
        }
        defaults.update(overrides)
        return Event.objects.create(**defaults)


# ===========================================================================
# 1. Test validità schema OpenAPI
# ===========================================================================

class OpenAPISchemaTest(TestCase):
    """Verifica che lo schema OpenAPI contenga i path e gli esempi attesi."""

    @classmethod
    def setUpTestData(cls):
        """Genera lo schema OpenAPI una sola volta per tutti i test."""
        cls.schema = get_openapi_schema()

    def test_schema_has_staging_paths(self):
        """Lo schema OpenAPI contiene tutti i path degli staging events."""
        paths = self.schema.get('paths', {})
        self.assertIn('/api/v1/events/', paths)
        self.assertIn('/api/v1/events/{id}/', paths)
        self.assertIn('/api/v1/events/bulk/', paths)
        self.assertIn('/api/v1/events/clear_source/', paths)

    def test_create_endpoint_has_examples(self):
        """POST /staging/ ha almeno un esempio con EventoCompleto e EventoMinimo."""
        examples = extract_examples(
            self.schema, '/api/v1/events/', 'post',
        )
        self.assertGreaterEqual(len(examples), 1, 'POST /staging/ deve avere almeno 1 esempio')
        names = [e['name'] for e in examples]
        self.assertIn('EventoCompleto', names)
        self.assertIn('EventoMinimo', names)

    def test_bulk_endpoint_has_examples(self):
        """POST /staging/bulk/ ha almeno un esempio nello schema."""
        examples = extract_examples(
            self.schema, '/api/v1/events/bulk/', 'post',
        )
        self.assertGreaterEqual(len(examples), 1, 'POST /staging/bulk/ deve avere almeno 1 esempio')

    def test_create_example_has_required_fields(self):
        """Ogni esempio di POST /staging/ contiene uuid, source e title."""
        examples = extract_examples(
            self.schema, '/api/v1/events/', 'post',
        )
        required = {'uuid', 'source', 'title'}
        for ex in examples:
            value = ex['value']
            for field in required:
                self.assertIn(
                    field, value,
                    f"Esempio '{ex['name']}' manca il campo obbligatorio '{field}'",
                )

    def test_schema_info(self):
        """Lo schema ha titolo 'Events Backoffice API' e versione '1.0.0'."""
        info = self.schema.get('info', {})
        self.assertEqual(info.get('title'), 'Events Backoffice API')
        self.assertEqual(info.get('version'), '1.0.0')


# ===========================================================================
# 2. Test CREATE singolo con esempi dallo schema
# ===========================================================================

class EventCreateFromSchemaTest(StagingAPIBaseTestCase):
    """
    POST /api/v1/events/ con ogni esempio trovato nello schema.
    """

    @classmethod
    def setUpTestData(cls):
        """Prepara schema OpenAPI ed estrae gli esempi per POST /staging/."""
        super().setUpTestData()
        cls.schema = get_openapi_schema()
        cls.examples = extract_examples(
            cls.schema, '/api/v1/events/', 'post',
        )

    def test_examples_found(self):
        """Verifica che ci sia almeno un esempio nello schema per il create."""
        self.assertGreaterEqual(
            len(self.examples), 1,
            'Nessun esempio trovato nello schema per POST /api/v1/events/',
        )

    def test_create_with_each_schema_example(self):
        """Per ogni esempio OpenAPI, crea un evento e verifica la risposta."""
        self.auth_write()

        for idx, example in enumerate(self.examples):
            with self.subTest(example=example['name']):
                # Rendi uuid unico per ogni subtest
                payload = dict(example['value'])
                payload['uuid'] = f"schema-test-{idx:03d}"

                response = self.client.post(
                    '/api/v1/events/',
                    data=payload,
                    format='json',
                )
                self.assertEqual(
                    response.status_code, status.HTTP_201_CREATED,
                    f"Esempio '{example['name']}' fallito: {response.data}",
                )
                # Verifica che i campi obbligatori siano presenti nella risposta
                self.assertEqual(response.data['uuid'], payload['uuid'])
                self.assertEqual(response.data['source'], payload['source'])
                self.assertEqual(response.data['title'], payload['title'])

    def test_create_evento_completo_fields(self):
        """Verifica che tutti i campi dell'esempio completo siano salvati."""
        self.auth_write()

        completo = next(
            (e for e in self.examples if e['name'] == 'EventoCompleto'), None,
        )
        if not completo:
            self.skipTest('Esempio EventoCompleto non trovato nello schema')

        payload = dict(completo['value'])
        payload['uuid'] = 'vfy-fld-001'

        response = self.client.post(
            '/api/v1/events/',
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Controlla ogni campo presente nel payload
        for key, expected in payload.items():
            if key not in response.data:
                continue
            actual = response.data[key]
            if key in ('raw_data',):
                self.assertEqual(actual, expected)
            elif key in ('category',):
                self.assertEqual(list(actual), list(expected))
            elif key in ('scraped_at',):
                # Confronta datetime ignorando la rappresentazione timezone
                from django.utils.dateparse import parse_datetime
                actual_dt = parse_datetime(str(actual))
                expected_dt = parse_datetime(str(expected))
                if actual_dt and expected_dt:
                    self.assertEqual(
                        actual_dt.utctimetuple()[:6],
                        expected_dt.utctimetuple()[:6],
                        f"Campo '{key}': atteso {expected}, ottenuto {actual}",
                    )
            else:
                self.assertEqual(
                    str(actual), str(expected),
                    f"Campo '{key}': atteso {expected}, ottenuto {actual}",
                )


# ===========================================================================
# 3. Test BULK CREATE con esempi dallo schema
# ===========================================================================

class EventBulkFromSchemaTest(StagingAPIBaseTestCase):
    """
    POST /api/v1/events/bulk/ con ogni esempio trovato nello schema.
    """

    @classmethod
    def setUpTestData(cls):
        """Prepara schema OpenAPI ed estrae gli esempi per POST /staging/bulk/."""
        super().setUpTestData()
        cls.schema = get_openapi_schema()
        cls.examples = extract_examples(
            cls.schema, '/api/v1/events/bulk/', 'post',
        )

    def test_examples_found(self):
        """Verifica che ci sia almeno un esempio nello schema per il bulk create."""
        self.assertGreaterEqual(
            len(self.examples), 1,
            'Nessun esempio trovato nello schema per POST /api/v1/events/bulk/',
        )

    def test_bulk_create_all_valid(self):
        """Testa il bulk create con un esempio di eventi tutti validi."""
        self.auth_write()

        # Prendi il primo esempio che ha tutti eventi con 'title' (tutti validi)
        valid_example = next(
            (e for e in self.examples if all(
                'title' in ev for ev in e['value'].get('events', [])
            )),
            None,
        )
        if not valid_example:
            self.skipTest('Nessun esempio con tutti eventi validi')

        payload = valid_example['value']
        # Rendi gli uuid unici
        for i, ev in enumerate(payload['events']):
            ev['uuid'] = f"bulk-valid-{i:03d}"

        response = self.client.post(
            '/api/v1/events/bulk/?sync=true',
            data=payload,
            format='json',
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_200_OK],
            f"Bulk create fallito: {response.data}",
        )
        self.assertEqual(response.data['failed_count'], 0)
        self.assertEqual(
            response.data['created_count'], len(payload['events']),
        )

    def test_bulk_create_partial_valid(self):
        """Testa il bulk create con un esempio che ha eventi parzialmente validi."""
        self.auth_write()

        partial_example = next(
            (e for e in self.examples
             if 'parzialmente' in e.get('summary', '').lower()
             or 'parzialmente' in e.get('name', '').lower()),
            None,
        )
        if not partial_example:
            self.skipTest('Nessun esempio con eventi parzialmente validi')

        payload = partial_example['value']
        # Rendi gli uuid unici
        for i, ev in enumerate(payload['events']):
            ev['uuid'] = f"bulk-partial-{i:03d}"

        response = self.client.post(
            '/api/v1/events/bulk/?sync=true',
            data=payload,
            format='json',
        )
        # Partial success -> 200
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data['created_count'], 0)
        self.assertGreater(response.data['failed_count'], 0)
        # Verifica che i failed abbiano errori dettagliati
        for failed in response.data['failed_events']:
            self.assertIn('errors', failed)
            self.assertIn('index', failed)
            self.assertIn('original_data', failed)

    def test_bulk_create_with_each_schema_example(self):
        """Testa ogni esempio di bulk nello schema."""
        self.auth_write()

        for idx, example in enumerate(self.examples):
            with self.subTest(example=example['name']):
                payload = example['value']
                # Rendi gli uuid unici
                for i, ev in enumerate(payload.get('events', [])):
                    ev['uuid'] = f"bulk-all-{idx}-{i:03d}"

                response = self.client.post(
                    '/api/v1/events/bulk/?sync=true',
                    data=payload,
                    format='json',
                )
                self.assertIn(
                    response.status_code,
                    [status.HTTP_200_OK, status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST],
                    f"Esempio '{example['name']}': status inatteso {response.status_code}",
                )
                # La risposta deve avere la struttura attesa
                self.assertIn('created_count', response.data)
                self.assertIn('failed_count', response.data)
                self.assertIn('successful_events', response.data)
                self.assertIn('failed_events', response.data)

    def test_bulk_empty_events_returns_400(self):
        """POST bulk con lista eventi vuota -> 400."""
        self.auth_write()
        response = self.client.post(
            '/api/v1/events/bulk/?sync=true',
            data={'events': []},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_no_events_key_returns_400(self):
        """POST bulk senza chiave 'events' -> 400."""
        self.auth_write()
        response = self.client.post(
            '/api/v1/events/bulk/?sync=true',
            data={'data': []},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ===========================================================================
# 4. Test CRUD completo
# ===========================================================================

class EventCRUDTest(StagingAPIBaseTestCase):
    """Test ciclo completo: create, list, retrieve, update, partial_update, delete."""

    def test_list_events(self):
        """GET /staging/ restituisce la lista paginata degli eventi."""
        self.create_event(uuid='list-001')
        self.create_event(uuid='list-002', title='Evento 2')
        self.auth_read()

        response = self.client.get('/api/v1/events/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 2)

    def test_retrieve_event(self):
        """GET /staging/{id}/ restituisce il dettaglio dell'evento."""
        event = self.create_event(uuid='retrieve-001')
        self.auth_read()

        response = self.client.get(f'/api/v1/events/{event.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['uuid'], 'retrieve-001')

    def test_create_event(self):
        """POST /staging/ crea un nuovo evento e lo salva nel DB."""
        self.auth_write()
        payload = {
            'uuid': 'crud-create-001',
            'source': 'test_source',
            'title': 'Nuovo evento CRUD',
            'city': 'roma',
            'date_start': '2026-03-15',
        }
        response = self.client.post(
            '/api/v1/events/', data=payload, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Event.objects.filter(uuid='crud-create-001').exists())

    def test_update_event(self):
        """PUT /staging/{id}/ aggiorna completamente l'evento."""
        event = self.create_event(uuid='crud-update-001')
        self.auth_write()

        payload = {
            'uuid': 'crud-update-001',
            'source': 'test_source',
            'title': 'Titolo aggiornato',
        }
        response = self.client.put(
            f'/api/v1/events/{event.pk}/',
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event.refresh_from_db()
        self.assertEqual(event.title, 'Titolo aggiornato')

    def test_partial_update_event(self):
        """PATCH /staging/{id}/ aggiorna parzialmente l'evento."""
        event = self.create_event(uuid='crud-patch-001', city='milano')
        self.auth_write()

        response = self.client.patch(
            f'/api/v1/events/{event.pk}/',
            data={'city': 'napoli'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event.refresh_from_db()
        self.assertEqual(event.city, 'napoli')

    def test_delete_event(self):
        """DELETE /staging/{id}/ elimina l'evento dal DB."""
        event = self.create_event(uuid='crud-delete-001')
        self.auth_write()

        response = self.client.delete(f'/api/v1/events/{event.pk}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())

    def test_create_missing_required_fields(self):
        """POST senza campi obbligatori -> 400."""
        self.auth_write()
        response = self.client.post(
            '/api/v1/events/',
            data={'city': 'roma'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('uuid', response.data)
        self.assertIn('source', response.data)
        self.assertIn('title', response.data)

    def test_list_filter_by_source(self):
        """GET /staging/?source=X filtra gli eventi per sorgente."""
        self.create_event(uuid='filter-001', source='source_a')
        self.create_event(uuid='filter-002', source='source_b')
        self.auth_read()

        response = self.client.get('/api/v1/events/?source=source_a')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for event in response.data['results']:
            self.assertEqual(event['source'], 'source_a')

    def test_list_search(self):
        """GET /staging/?search=X cerca per titolo e descrizione."""
        self.create_event(uuid='search-001', title='Concerto Jazz')
        self.create_event(uuid='search-002', title='Mostra Caravaggio')
        self.auth_read()

        response = self.client.get('/api/v1/events/?search=Jazz')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['title'], 'Concerto Jazz')


# ===========================================================================
# 5. Test CLEAR SOURCE
# ===========================================================================

class EventClearSourceTest(StagingAPIBaseTestCase):
    """DELETE /api/v1/events/clear_source/?source=xxx"""

    def test_clear_source_deletes_matching(self):
        """DELETE clear_source elimina solo gli eventi della sorgente specificata."""
        self.create_event(uuid='clear-001', source='to_delete')
        self.create_event(uuid='clear-002', source='to_delete')
        self.create_event(uuid='clear-003', source='keep_this')
        self.auth_write()

        response = self.client.delete(
            '/api/v1/events/clear_source/?source=to_delete',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted'], 2)
        self.assertEqual(response.data['source'], 'to_delete')
        # L'evento dell'altra sorgente non deve essere toccato
        self.assertTrue(Event.objects.filter(source='keep_this').exists())

    def test_clear_source_without_param(self):
        """DELETE clear_source senza parametro -> 400."""
        self.auth_write()
        response = self.client.delete('/api/v1/events/clear_source/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_clear_source_nonexistent(self):
        """DELETE clear_source con sorgente inesistente -> 200, deleted=0."""
        self.auth_write()
        response = self.client.delete(
            '/api/v1/events/clear_source/?source=nonexistent',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted'], 0)


# ===========================================================================
# 6. Test AUTENTICAZIONE e PERMESSI
# ===========================================================================

class EventAuthTest(StagingAPIBaseTestCase):
    """Verifica che autenticazione e scopes siano rispettati."""

    def test_no_token_returns_401(self):
        """Richiesta senza token -> 401."""
        self.auth_none()
        response = self.client.get('/api/v1/events/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token_returns_401(self):
        """Token non valido -> 401."""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid-token-xyz')
        response = self.client.get('/api/v1/events/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_token_returns_401(self):
        """Token scaduto -> 401."""
        expired_token = AccessToken.objects.create(
            user=self.user,
            token='expired-token',
            application=self.application,
            expires=timezone.now() - timedelta(hours=1),
            scope='read write',
        )
        self.client.credentials(HTTP_AUTHORIZATION='Bearer expired-token')
        response = self.client.get('/api/v1/events/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_read_token_cannot_create(self):
        """Token con solo scope 'read' non puo' creare -> 403."""
        self.auth_read()
        response = self.client.post(
            '/api/v1/events/',
            data={'uuid': 'x', 'source': 'x', 'title': 'x'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_read_token_cannot_delete(self):
        """Token con solo scope 'read' non puo' eliminare -> 403."""
        event = self.create_event(uuid='auth-del-001')
        self.auth_read()
        response = self.client.delete(f'/api/v1/events/{event.pk}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_read_token_can_list(self):
        """Token con scope 'read' puo' listare -> 200."""
        self.auth_read()
        response = self.client.get('/api/v1/events/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_write_token_can_read(self):
        """Token con scope 'read write' puo' anche leggere -> 200."""
        self.create_event(uuid='auth-rw-001')
        self.auth_write()
        response = self.client.get('/api/v1/events/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# ===========================================================================
# 7. Test BULK ASYNC
# ===========================================================================

class EventBulkAsyncTest(StagingAPIBaseTestCase):
    """Test per il bulk create asincrono via Celery."""

    def test_async_bulk_returns_202_with_task_id(self):
        """POST bulk senza ?sync=true -> 202 Accepted con task_id."""
        from unittest.mock import patch, MagicMock

        mock_result = MagicMock()
        mock_result.id = 'fake-task-id-001'

        self.auth_write()
        payload = {
            'events': [
                {
                    'uuid': 'async-001',
                    'source': 'test_source',
                    'title': 'Evento Async 1',
                    'city': 'milano',
                },
                {
                    'uuid': 'async-002',
                    'source': 'test_source',
                    'title': 'Evento Async 2',
                    'city': 'roma',
                },
            ]
        }
        with patch('events.tasks.process_bulk_events') as mock_task:
            mock_task.delay.return_value = mock_result
            response = self.client.post(
                '/api/v1/events/bulk/',
                data=payload,
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['task_id'], 'fake-task-id-001')
        self.assertEqual(response.data['status'], 'PENDING')
        self.assertIn('message', response.data)

    def test_bulk_status_endpoint_success(self):
        """GET bulk-status/{task_id} ritorna SUCCESS con risultato."""
        from unittest.mock import patch, MagicMock

        mock_async_result = MagicMock()
        mock_async_result.status = 'SUCCESS'
        mock_async_result.ready.return_value = True
        mock_async_result.successful.return_value = True
        mock_async_result.result = {'created_count': 5, 'failed_count': 0, 'failed_events': []}

        self.auth_read()
        with patch('events.views.AsyncResult', return_value=mock_async_result):
            response = self.client.get(
                '/api/v1/events/bulk-status/fake-task-id-001/',
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['task_id'], 'fake-task-id-001')
        self.assertEqual(response.data['status'], 'SUCCESS')
        self.assertEqual(response.data['result']['created_count'], 5)

    def test_bulk_status_endpoint_pending(self):
        """GET bulk-status/{task_id} ritorna PENDING quando il task non e' ancora completato."""
        from unittest.mock import patch, MagicMock

        mock_async_result = MagicMock()
        mock_async_result.status = 'PENDING'
        mock_async_result.ready.return_value = False

        self.auth_read()
        with patch('events.views.AsyncResult', return_value=mock_async_result):
            response = self.client.get(
                '/api/v1/events/bulk-status/fake-task-id-002/',
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'PENDING')
        self.assertIsNone(response.data['result'])

    def test_bulk_status_endpoint_failure(self):
        """GET bulk-status/{task_id} ritorna FAILURE con dettaglio errore."""
        from unittest.mock import patch, MagicMock

        mock_async_result = MagicMock()
        mock_async_result.status = 'FAILURE'
        mock_async_result.ready.return_value = True
        mock_async_result.successful.return_value = False
        mock_async_result.result = Exception('DB connection lost')

        self.auth_read()
        with patch('events.views.AsyncResult', return_value=mock_async_result):
            response = self.client.get(
                '/api/v1/events/bulk-status/fake-task-id-003/',
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'FAILURE')
        self.assertIn('DB connection lost', response.data['result'])

    def test_bulk_status_unknown_task(self):
        """GET bulk-status con task_id sconosciuto -> 200 con status PENDING."""
        from unittest.mock import patch, MagicMock

        mock_async_result = MagicMock()
        mock_async_result.status = 'PENDING'
        mock_async_result.ready.return_value = False

        self.auth_read()
        with patch('events.views.AsyncResult', return_value=mock_async_result):
            response = self.client.get(
                '/api/v1/events/bulk-status/nonexistent-task-id/',
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'PENDING')

    def test_sync_true_returns_201(self):
        """POST bulk?sync=true mantiene il comportamento sincrono -> 201."""
        self.auth_write()
        payload = {
            'events': [
                {
                    'uuid': 'sync-compat-001',
                    'source': 'test_source',
                    'title': 'Evento Sync Compat',
                    'city': 'firenze',
                },
            ]
        }
        response = self.client.post(
            '/api/v1/events/bulk/?sync=true',
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('created_count', response.data)
        self.assertEqual(response.data['created_count'], 1)
        # Verifica che l'evento e' stato effettivamente creato nel DB
        self.assertTrue(Event.objects.filter(uuid='sync-compat-001').exists())

    def test_async_empty_events_returns_400(self):
        """POST bulk async con lista vuota -> 400 (validato prima del dispatch)."""
        self.auth_write()
        response = self.client.post(
            '/api/v1/events/bulk/',
            data={'events': []},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_process_bulk_events_task_directly(self):
        """Test diretto del task Celery (senza broker)."""
        from events.tasks import process_bulk_events
        events_data = [
            {
                'uuid': 'task-direct-001',
                'source': 'test_source',
                'title': 'Evento Task Diretto 1',
                'city': 'milano',
            },
            {
                'uuid': 'task-direct-002',
                'source': 'test_source',
                'title': 'Evento Task Diretto 2',
                'city': 'roma',
            },
            {
                # Invalid: missing title
                'uuid': 'task-direct-003',
                'source': 'test_source',
                'city': 'napoli',
            },
        ]
        result = process_bulk_events(events_data)
        self.assertEqual(result['created_count'], 2)
        self.assertEqual(result['failed_count'], 1)
        self.assertEqual(len(result['failed_events']), 1)
        self.assertEqual(result['failed_events'][0]['index'], 2)
        # Verify in DB
        self.assertTrue(Event.objects.filter(uuid='task-direct-001').exists())
        self.assertTrue(Event.objects.filter(uuid='task-direct-002').exists())
        self.assertFalse(Event.objects.filter(uuid='task-direct-003').exists())
