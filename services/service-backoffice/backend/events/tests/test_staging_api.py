"""
Test suite per le API Staging Events (/api/external/staging/).

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

from events.models import StagingEvent


# ---------------------------------------------------------------------------
# Client che traccia le chiamate API per il report tabellare
# ---------------------------------------------------------------------------

class TrackingAPIClient(APIClient):
    """APIClient che registra ogni richiesta HTTP in test._api_calls."""

    def __init__(self, test_instance=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._test = test_instance

    def generic(self, method, path, *args, **kwargs):
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
        self._api_calls = []
        self.client = TrackingAPIClient(test_instance=self)

    # -- shortcut autenticazione --
    def auth_read(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer test-read-token')

    def auth_write(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer test-write-token')

    def auth_none(self):
        self.client.credentials()

    # -- helper per creare un evento in DB --
    def create_event(self, **overrides):
        defaults = {
            'uuid': 'test-uuid-001',
            'source': 'test_source',
            'title': 'Evento di test',
        }
        defaults.update(overrides)
        return StagingEvent.objects.create(**defaults)


# ===========================================================================
# 1. Test validità schema OpenAPI
# ===========================================================================

class OpenAPISchemaTest(TestCase):
    """Verifica che lo schema OpenAPI contenga i path e gli esempi attesi."""

    @classmethod
    def setUpTestData(cls):
        cls.schema = get_openapi_schema()

    def test_schema_has_staging_paths(self):
        paths = self.schema.get('paths', {})
        self.assertIn('/api/external/staging/', paths)
        self.assertIn('/api/external/staging/{id}/', paths)
        self.assertIn('/api/external/staging/bulk/', paths)
        self.assertIn('/api/external/staging/clear_source/', paths)

    def test_create_endpoint_has_examples(self):
        examples = extract_examples(
            self.schema, '/api/external/staging/', 'post',
        )
        self.assertGreaterEqual(len(examples), 1, 'POST /staging/ deve avere almeno 1 esempio')
        names = [e['name'] for e in examples]
        self.assertIn('EventoCompleto', names)
        self.assertIn('EventoMinimo', names)

    def test_bulk_endpoint_has_examples(self):
        examples = extract_examples(
            self.schema, '/api/external/staging/bulk/', 'post',
        )
        self.assertGreaterEqual(len(examples), 1, 'POST /staging/bulk/ deve avere almeno 1 esempio')

    def test_create_example_has_required_fields(self):
        examples = extract_examples(
            self.schema, '/api/external/staging/', 'post',
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
        info = self.schema.get('info', {})
        self.assertEqual(info.get('title'), 'Events Backoffice API')
        self.assertEqual(info.get('version'), '1.0.0')


# ===========================================================================
# 2. Test CREATE singolo con esempi dallo schema
# ===========================================================================

class StagingEventCreateFromSchemaTest(StagingAPIBaseTestCase):
    """
    POST /api/external/staging/ con ogni esempio trovato nello schema.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.schema = get_openapi_schema()
        cls.examples = extract_examples(
            cls.schema, '/api/external/staging/', 'post',
        )

    def test_examples_found(self):
        self.assertGreaterEqual(
            len(self.examples), 1,
            'Nessun esempio trovato nello schema per POST /api/external/staging/',
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
                    '/api/external/staging/',
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
            '/api/external/staging/',
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

class StagingEventBulkFromSchemaTest(StagingAPIBaseTestCase):
    """
    POST /api/external/staging/bulk/ con ogni esempio trovato nello schema.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.schema = get_openapi_schema()
        cls.examples = extract_examples(
            cls.schema, '/api/external/staging/bulk/', 'post',
        )

    def test_examples_found(self):
        self.assertGreaterEqual(
            len(self.examples), 1,
            'Nessun esempio trovato nello schema per POST /api/external/staging/bulk/',
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
            '/api/external/staging/bulk/',
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
            '/api/external/staging/bulk/',
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
                    '/api/external/staging/bulk/',
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
            '/api/external/staging/bulk/',
            data={'events': []},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_no_events_key_returns_400(self):
        """POST bulk senza chiave 'events' -> 400."""
        self.auth_write()
        response = self.client.post(
            '/api/external/staging/bulk/',
            data={'data': []},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ===========================================================================
# 4. Test CRUD completo
# ===========================================================================

class StagingEventCRUDTest(StagingAPIBaseTestCase):
    """Test ciclo completo: create, list, retrieve, update, partial_update, delete."""

    def test_list_events(self):
        self.create_event(uuid='list-001')
        self.create_event(uuid='list-002', title='Evento 2')
        self.auth_read()

        response = self.client.get('/api/external/staging/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 2)

    def test_retrieve_event(self):
        event = self.create_event(uuid='retrieve-001')
        self.auth_read()

        response = self.client.get(f'/api/external/staging/{event.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['uuid'], 'retrieve-001')

    def test_create_event(self):
        self.auth_write()
        payload = {
            'uuid': 'crud-create-001',
            'source': 'test_source',
            'title': 'Nuovo evento CRUD',
            'city': 'roma',
            'date_start': '2026-03-15',
        }
        response = self.client.post(
            '/api/external/staging/', data=payload, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(StagingEvent.objects.filter(uuid='crud-create-001').exists())

    def test_update_event(self):
        event = self.create_event(uuid='crud-update-001')
        self.auth_write()

        payload = {
            'uuid': 'crud-update-001',
            'source': 'test_source',
            'title': 'Titolo aggiornato',
        }
        response = self.client.put(
            f'/api/external/staging/{event.pk}/',
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event.refresh_from_db()
        self.assertEqual(event.title, 'Titolo aggiornato')

    def test_partial_update_event(self):
        event = self.create_event(uuid='crud-patch-001', city='milano')
        self.auth_write()

        response = self.client.patch(
            f'/api/external/staging/{event.pk}/',
            data={'city': 'napoli'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event.refresh_from_db()
        self.assertEqual(event.city, 'napoli')

    def test_delete_event(self):
        event = self.create_event(uuid='crud-delete-001')
        self.auth_write()

        response = self.client.delete(f'/api/external/staging/{event.pk}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(StagingEvent.objects.filter(pk=event.pk).exists())

    def test_create_missing_required_fields(self):
        """POST senza campi obbligatori -> 400."""
        self.auth_write()
        response = self.client.post(
            '/api/external/staging/',
            data={'city': 'roma'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('uuid', response.data)
        self.assertIn('source', response.data)
        self.assertIn('title', response.data)

    def test_list_filter_by_source(self):
        self.create_event(uuid='filter-001', source='source_a')
        self.create_event(uuid='filter-002', source='source_b')
        self.auth_read()

        response = self.client.get('/api/external/staging/?source=source_a')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for event in response.data['results']:
            self.assertEqual(event['source'], 'source_a')

    def test_list_search(self):
        self.create_event(uuid='search-001', title='Concerto Jazz')
        self.create_event(uuid='search-002', title='Mostra Caravaggio')
        self.auth_read()

        response = self.client.get('/api/external/staging/?search=Jazz')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['title'], 'Concerto Jazz')


# ===========================================================================
# 5. Test CLEAR SOURCE
# ===========================================================================

class StagingEventClearSourceTest(StagingAPIBaseTestCase):
    """DELETE /api/external/staging/clear_source/?source=xxx"""

    def test_clear_source_deletes_matching(self):
        self.create_event(uuid='clear-001', source='to_delete')
        self.create_event(uuid='clear-002', source='to_delete')
        self.create_event(uuid='clear-003', source='keep_this')
        self.auth_write()

        response = self.client.delete(
            '/api/external/staging/clear_source/?source=to_delete',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted'], 2)
        self.assertEqual(response.data['source'], 'to_delete')
        # L'evento dell'altra sorgente non deve essere toccato
        self.assertTrue(StagingEvent.objects.filter(source='keep_this').exists())

    def test_clear_source_without_param(self):
        """DELETE clear_source senza parametro -> 400."""
        self.auth_write()
        response = self.client.delete('/api/external/staging/clear_source/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_clear_source_nonexistent(self):
        """DELETE clear_source con sorgente inesistente -> 200, deleted=0."""
        self.auth_write()
        response = self.client.delete(
            '/api/external/staging/clear_source/?source=nonexistent',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted'], 0)


# ===========================================================================
# 6. Test AUTENTICAZIONE e PERMESSI
# ===========================================================================

class StagingEventAuthTest(StagingAPIBaseTestCase):
    """Verifica che autenticazione e scopes siano rispettati."""

    def test_no_token_returns_401(self):
        """Richiesta senza token -> 401."""
        self.auth_none()
        response = self.client.get('/api/external/staging/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token_returns_401(self):
        """Token non valido -> 401."""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid-token-xyz')
        response = self.client.get('/api/external/staging/')
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
        response = self.client.get('/api/external/staging/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_read_token_cannot_create(self):
        """Token con solo scope 'read' non puo' creare -> 403."""
        self.auth_read()
        response = self.client.post(
            '/api/external/staging/',
            data={'uuid': 'x', 'source': 'x', 'title': 'x'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_read_token_cannot_delete(self):
        """Token con solo scope 'read' non puo' eliminare -> 403."""
        event = self.create_event(uuid='auth-del-001')
        self.auth_read()
        response = self.client.delete(f'/api/external/staging/{event.pk}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_read_token_can_list(self):
        """Token con scope 'read' puo' listare -> 200."""
        self.auth_read()
        response = self.client.get('/api/external/staging/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_write_token_can_read(self):
        """Token con scope 'read write' puo' anche leggere -> 200."""
        self.create_event(uuid='auth-rw-001')
        self.auth_write()
        response = self.client.get('/api/external/staging/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
