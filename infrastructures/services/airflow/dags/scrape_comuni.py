"""
DAG per ETL comuni ISTAT

Pipeline:
1. Scraping via DockerOperator → genera JSON su disco locale o MinIO
2. Ingestion via PythonOperator → POST bulk all'API backoffice

Storage backend (Variable STORAGE_BACKEND o env):
- "local" (default): JSON su disco, montato via Docker volume
- "minio": JSON su MinIO bucket "comuni-italiani"

Schedule: None (trigger manuale)
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.models import Variable
from docker.types import Mount

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=1),
}

# Configurazione
SCRAPY_IMAGE = os.getenv('SCRAPY_IMAGE_COMUNI', 'registry.127.0.0.1.nip.io/today-events/scraping-comuni:latest')
REGISTRY_CONN_ID = os.getenv('REGISTRY_CONN_ID', 'harbor_registry')
COMUNI_DATA_PATH = Variable.get(
    'COMUNI_DATA_PATH',
    default_var=os.getenv('COMUNI_DATA_PATH', '/opt/today_events/data/comuni-istat'),
)
API_BASE_URL = Variable.get(
    'API_BASE_URL',
    default_var=os.getenv('API_BASE_URL', 'http://backoffice:8000'),
)
BULK_ENDPOINT = f'{API_BASE_URL}/api/comuni-istat/ingestion/bulk/'
BATCH_SIZE = 500

# Storage backend: "local" o "minio"
STORAGE_BACKEND = Variable.get(
    'STORAGE_BACKEND',
    default_var=os.getenv('STORAGE_BACKEND', 'local'),
)

# MinIO config
MINIO_ENDPOINT = Variable.get('MINIO_ENDPOINT', default_var=os.getenv('MINIO_ENDPOINT', 'minio:9000'))
MINIO_ACCESS_KEY = Variable.get('MINIO_ACCESS_KEY', default_var=os.getenv('MINIO_ACCESS_KEY', 'minioadmin'))
MINIO_SECRET_KEY = Variable.get('MINIO_SECRET_KEY', default_var=os.getenv('MINIO_SECRET_KEY', ''))
MINIO_BUCKET = Variable.get('MINIO_BUCKET', default_var=os.getenv('MINIO_BUCKET', 'comuni-italiani'))
MINIO_USE_SSL = Variable.get('MINIO_USE_SSL', default_var=os.getenv('MINIO_USE_SSL', 'false'))


# =============================================================================
# Helper: OAuth2
# =============================================================================

def get_oauth_token():
    """Ottiene token JWT da Keycloak per chiamare l'API di ingestion"""
    client_id = Variable.get('API_CLIENT_ID', default_var=os.getenv('API_CLIENT_ID', ''))
    client_secret = Variable.get('API_CLIENT_SECRET', default_var=os.getenv('API_CLIENT_SECRET', ''))
    token_url = Variable.get(
        'KEYCLOAK_TOKEN_URL',
        default_var=os.getenv(
            'KEYCLOAK_TOKEN_URL',
            'http://keycloak:8080/realms/today-events/protocol/openid-connect/token'
        )
    )

    resp = requests.post(
        token_url,
        data={
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': 'openid read write',
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()['access_token']


def _get_auth_headers():
    """Restituisce headers con Bearer token"""
    token = get_oauth_token()
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }


# =============================================================================
# Helper: Client S3/MinIO (lazy)
# =============================================================================

def _get_s3_client():
    """Crea un client boto3 S3 per MinIO."""
    import boto3
    scheme = "https" if MINIO_USE_SSL.lower() == "true" else "http"
    return boto3.client(
        "s3",
        endpoint_url=f"{scheme}://{MINIO_ENDPOINT}",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    )


# =============================================================================
# Helper: Lettura file JSON da disco locale
# =============================================================================

def _find_json_files(data_path, tipo):
    """Trova i file JSON per tipo nella struttura output.

    Struttura:
        data/output/
        ├── 01_piemonte/
        │   ├── piemonte.json              ← regione
        │   ├── 001_torino/
        │   │   ├── torino.json            ← provincia
        │   │   └── torino_comuni.json     ← comuni
    """
    root = Path(data_path)
    files = []

    if tipo == 'regione':
        for reg_dir in sorted(root.iterdir()):
            if not reg_dir.is_dir():
                continue
            for f in reg_dir.iterdir():
                if f.is_file() and f.suffix == '.json' and '_comuni' not in f.name:
                    files.append(f)
    elif tipo == 'provincia':
        for reg_dir in sorted(root.iterdir()):
            if not reg_dir.is_dir():
                continue
            for prov_dir in sorted(reg_dir.iterdir()):
                if not prov_dir.is_dir():
                    continue
                for f in prov_dir.iterdir():
                    if f.is_file() and f.suffix == '.json' and '_comuni' not in f.name:
                        files.append(f)
    elif tipo == 'comune':
        for f in sorted(root.rglob('*_comuni.json')):
            files.append(f)

    return files


def _load_items_from_files(files, tipo):
    """Carica gli item dai file JSON locali.

    Per regioni e province: ogni file è un singolo oggetto JSON.
    Per comuni: ogni file è una lista di oggetti JSON.
    """
    items = []
    for f in files:
        with open(f, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        if tipo == 'comune':
            if isinstance(data, list):
                items.extend(data)
            else:
                items.append(data)
        else:
            items.append(data)
    return items


# =============================================================================
# Helper: Lettura file JSON da MinIO
# =============================================================================

def _find_minio_keys(s3, tipo):
    """Trova le chiavi S3 per tipo nel bucket MinIO.

    Stessa struttura gerarchica del disco locale:
        01_piemonte/piemonte.json                        ← regione (livello 1, no _comuni)
        01_piemonte/001_torino/torino.json               ← provincia (livello 2, no _comuni)
        01_piemonte/001_torino/torino_comuni.json        ← comuni (_comuni.json)
    """
    paginator = s3.get_paginator('list_objects_v2')
    keys = []

    for page in paginator.paginate(Bucket=MINIO_BUCKET):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if not key.endswith('.json'):
                continue
            parts = key.split('/')
            if tipo == 'regione':
                # livello 1: regione/regione.json (2 parti, no _comuni)
                if len(parts) == 2 and '_comuni' not in key:
                    keys.append(key)
            elif tipo == 'provincia':
                # livello 2: regione/provincia/provincia.json (3 parti, no _comuni)
                if len(parts) == 3 and '_comuni' not in key:
                    keys.append(key)
            elif tipo == 'comune':
                # _comuni.json a qualsiasi livello
                if key.endswith('_comuni.json'):
                    keys.append(key)

    return sorted(keys)


def _load_items_from_minio(s3, keys, tipo):
    """Carica gli item JSON da MinIO."""
    items = []
    for key in keys:
        resp = s3.get_object(Bucket=MINIO_BUCKET, Key=key)
        data = json.loads(resp['Body'].read().decode('utf-8'))
        if tipo == 'comune':
            if isinstance(data, list):
                items.extend(data)
            else:
                items.append(data)
        else:
            items.append(data)
    return items


# =============================================================================
# Task: Ingestion
# =============================================================================

def _ingest(tipo, **context):
    """Ingestisce i dati di un tipo (regione/provincia/comune) via API bulk.

    Legge da disco locale o da MinIO in base a STORAGE_BACKEND.
    """
    if STORAGE_BACKEND == 'minio':
        s3 = _get_s3_client()
        keys = _find_minio_keys(s3, tipo)
        print(f"[{tipo}] Trovati {len(keys)} file JSON su MinIO ({MINIO_BUCKET})")
        if not keys:
            print(f"[{tipo}] Nessun file trovato, skip")
            return {'tipo': tipo, 'created': 0}
        items = _load_items_from_minio(s3, keys, tipo)
    else:
        data_path = COMUNI_DATA_PATH
        files = _find_json_files(data_path, tipo)
        print(f"[{tipo}] Trovati {len(files)} file JSON in {data_path}")
        if not files:
            print(f"[{tipo}] Nessun file trovato, skip")
            return {'tipo': tipo, 'created': 0}
        items = _load_items_from_files(files, tipo)

    print(f"[{tipo}] Totale item da ingestire: {len(items)}")

    if not items:
        return {'tipo': tipo, 'created': 0}

    headers = _get_auth_headers()
    total_created = 0

    # Invio a batch
    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i:i + BATCH_SIZE]
        payload = {'tipo': tipo, 'items': batch}

        resp = requests.post(BULK_ENDPOINT, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()

        result = resp.json()
        created = result.get('created', 0)
        total_created += created
        print(f"[{tipo}] Batch {i // BATCH_SIZE + 1}: {created} record creati")

    print(f"[{tipo}] Ingestion completata: {total_created} record totali")
    return {'tipo': tipo, 'created': total_created}


def ingest_regioni(**context):
    return _ingest('regione', **context)


def ingest_province(**context):
    return _ingest('provincia', **context)


def ingest_comuni(**context):
    return _ingest('comune', **context)


# =============================================================================
# DAG
# =============================================================================

with DAG(
    'etl_comuni_istat',
    default_args=default_args,
    description='ETL comuni ISTAT - scraping + ingestion',
    schedule_interval=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['comuni', 'etl', 'one-shot'],
) as dag:

    # Env vars per lo spider: storage backend + credenziali MinIO
    scraper_env = {'STORAGE_BACKEND': STORAGE_BACKEND}
    scraper_mounts = []

    if STORAGE_BACKEND == 'minio':
        scraper_env.update({
            'MINIO_ENDPOINT': MINIO_ENDPOINT,
            'MINIO_ACCESS_KEY': MINIO_ACCESS_KEY,
            'MINIO_SECRET_KEY': MINIO_SECRET_KEY,
            'MINIO_BUCKET': MINIO_BUCKET,
            'MINIO_USE_SSL': MINIO_USE_SSL,
        })
    else:
        scraper_mounts.append(
            Mount(source=COMUNI_DATA_PATH, target='/data/output', type='bind'),
        )

    scrape_comuni = DockerOperator(
        task_id='scrape_comuni',
        image=SCRAPY_IMAGE,
        environment=scraper_env,
        network_mode='dev-network',
        auto_remove=True,
        force_pull=True,
        docker_url='unix://var/run/docker.sock',
        docker_conn_id=REGISTRY_CONN_ID,
        mounts=scraper_mounts or None,
    )

    ingest_regioni_task = PythonOperator(
        task_id='ingest_regioni',
        python_callable=ingest_regioni,
    )

    ingest_province_task = PythonOperator(
        task_id='ingest_province',
        python_callable=ingest_province,
    )

    ingest_comuni_task = PythonOperator(
        task_id='ingest_comuni',
        python_callable=ingest_comuni,
    )

    scrape_comuni >> ingest_regioni_task >> ingest_province_task >> ingest_comuni_task
