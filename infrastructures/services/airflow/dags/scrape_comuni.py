"""
DAG per ETL comuni ISTAT

Pipeline:
1. Scraping via DockerOperator → genera JSON su disco (regioni, province, comuni)
2. Ingestion via PythonOperator → POST bulk all'API backoffice

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
SCRAPY_IMAGE = 'today-events/scraping-comuni:latest'
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


# =============================================================================
# Helper: OAuth2
# =============================================================================

def get_oauth_token():
    """Ottiene token OAuth2 per chiamare l'API di ingestion"""
    client_id = Variable.get('API_CLIENT_ID', default_var=os.getenv('API_CLIENT_ID', ''))
    client_secret = Variable.get('API_CLIENT_SECRET', default_var=os.getenv('API_CLIENT_SECRET', ''))

    resp = requests.post(
        f'{API_BASE_URL}/oauth/token/',
        data={
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
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
# Helper: Lettura file JSON da disco
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
        # File JSON al primo livello dentro ogni cartella regione
        for reg_dir in sorted(root.iterdir()):
            if not reg_dir.is_dir():
                continue
            for f in reg_dir.iterdir():
                if f.is_file() and f.suffix == '.json' and '_comuni' not in f.name:
                    # Verifica che non sia dentro una sotto-cartella provincia
                    # (i file regione sono direttamente nella cartella regione)
                    files.append(f)
    elif tipo == 'provincia':
        # File JSON al secondo livello (dentro cartelle provincia)
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
        # File che finiscono con _comuni.json
        for f in sorted(root.rglob('*_comuni.json')):
            files.append(f)

    return files


def _load_items_from_files(files, tipo):
    """Carica gli item dai file JSON.

    Per regioni e province: ogni file è un singolo oggetto JSON.
    Per comuni: ogni file è una lista di oggetti JSON.
    """
    items = []
    for f in files:
        with open(f, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        if tipo == 'comune':
            # Il file _comuni.json contiene una lista
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
    """Ingestisce i dati di un tipo (regione/provincia/comune) via API bulk."""
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

    scrape_comuni = DockerOperator(
        task_id='scrape_comuni',
        image=SCRAPY_IMAGE,
        network_mode='events-network',
        auto_remove=True,
        force_pull=False,
        docker_url='unix://var/run/docker.sock',
        mounts=[
            Mount(
                source=COMUNI_DATA_PATH,
                target='/data/output',
                type='bind',
            ),
        ],
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
