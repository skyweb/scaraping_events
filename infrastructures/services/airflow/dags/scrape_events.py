"""
DAG per lo scraping degli eventi - Strategia ETL con ApiPipeline

Pipeline:
1. Scraping (DockerOperator/KubernetesPodOperator) → ApiPipeline → Django API → staging_events
2. Log ETL run

Ambienti:
- SCRAPER_EXECUTOR=docker  → DockerOperator (dev locale)
- SCRAPER_EXECUTOR=k8s     → KubernetesPodOperator (produzione K8s)

Tracing distribuito:
- Ogni DAG run genera un trace context (TRACEPARENT)
- Il context viene propagato ai container Scrapy via env var
- Scrapy lo usa come parent span → trace end-to-end visibile in Grafana Tempo
"""

import os
import random
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule
from airflow.exceptions import AirflowSkipException
from airflow.models import Variable

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=2),
}

# Configurazione
SCRAPY_IMAGE = os.getenv('SCRAPY_IMAGE', 'today-events/scrapyd-dev:latest')
POSTGRES_CONN_ID = 'events_postgres'

# Ambiente: 'docker' (dev locale) o 'k8s' (produzione Kubernetes)
SCRAPER_EXECUTOR = os.getenv('SCRAPER_EXECUTOR', 'docker')

# K8s config (usato solo se SCRAPER_EXECUTOR=k8s)
K8S_NAMESPACE = os.getenv('K8S_SCRAPER_NAMESPACE', 'scraping')
K8S_SERVICE_ACCOUNT = os.getenv('K8S_SCRAPER_SA', 'default')
K8S_IMAGE_PULL_POLICY = os.getenv('K8S_IMAGE_PULL_POLICY', 'Always')

# Docker config (usato solo se SCRAPER_EXECUTOR=docker)
DOCKER_NETWORK = os.getenv('DOCKER_NETWORK', 'dev-network')
DOCKER_URL = os.getenv('DOCKER_URL', 'unix://var/run/docker.sock')
# Volume mount per codice sorgente Scrapy (dev: codice montato, prod: incluso nell'immagine)
SCRAPY_SRC_PATH = os.getenv('SCRAPY_SRC_PATH', '')  # es. /Users/.../scraping-service/src
# Volume mount per output dati (batch JSON, log)
SCRAPY_DATA_PATH = os.getenv('SCRAPY_DATA_PATH', '')  # es. /Users/.../scraping-service/data

CITIES_TODAY = [
    'milano', 'torino', 'genova', 'venezia', 'bologna', 'verona', 'treviso', 'trento', 'udine', 'pordenone',
    'vicenza', 'padova', 'monza', 'lecco', 'sondrio', 'novara', 'brescia', 'parma', 'rimini', 'ravenna',
    'forli', 'cesena', 'como', 'piacenza', 'trieste', 'roma', 'firenze', 'pisa', 'livorno', 'perugia',
    'terni', 'ancona', 'latina', 'frosinone', 'viterbo', 'arezzo', 'pescara', 'napoli', 'palermo',
    'catania', 'messina', 'bari', 'foggia', 'salerno', 'avellino', 'reggio-calabria', 'lecce', 'brindisi',
    'agrigento', 'caserta'
]
CITIES_ZERO = ['milano', 'roma', 'bologna', 'napoli', 'firenze', 'venezia', 'torino']

# Spider portali turistici istituzionali per città
CITIES_TOURISM = {
    'torino': {'spider': 'turismo_torino', 'args': ['-a', 'max_pages=10']},
    'milano': {'spider': 'yes_milano', 'args': ['-a', 'max_pages=10']},
    'verona': {'spider': 'visit_verona', 'args': ['-a', 'max_pages=10']},
    'venezia': {'spider': 'venezia_unica', 'args': ['-a', 'max_pages=10']},
    'modena': {'spider': 'visit_modena', 'args': ['-a', 'max_pages=5']},
    'pisa': {'spider': 'turismo_pisa', 'args': ['-a', 'max_pages=10']},
    'siena': {'spider': 'siena_comunica', 'args': ['-a', 'max_pages=5']},
    'lucca': {'spider': 'comune_lucca', 'args': ['-a', 'max_pages=10']},
    'firenze': {'spider': 'feel_florence', 'args': ['-a', 'max_pages=10']},
    'roma': {'spider': 'turismo_roma', 'args': ['-a', 'max_pages=5']},
    'napoli': {'spider': 'visit_naples', 'args': ['-a', 'max_pages=5']},
}

ALL_CITIES = sorted(list(set(CITIES_TODAY + CITIES_ZERO + list(CITIES_TOURISM.keys()))))


# =============================================================================
# Env vars per container Scrapy
# =============================================================================

def get_scrapy_env():
    """Ottiene le credenziali API da Airflow Variables o env vars"""
    return {
        'API_BASE_URL': Variable.get('API_BASE_URL', default_var=os.getenv('API_BASE_URL', 'http://backoffice:8000')),
        'API_CLIENT_ID': Variable.get('API_CLIENT_ID', default_var=os.getenv('API_CLIENT_ID', '')),
        'API_CLIENT_SECRET': Variable.get('API_CLIENT_SECRET', default_var=os.getenv('API_CLIENT_SECRET', '')),
        'KEYCLOAK_TOKEN_URL': Variable.get(
            'KEYCLOAK_TOKEN_URL',
            default_var=os.getenv(
                'KEYCLOAK_TOKEN_URL',
                'http://keycloak:8080/realms/today-events/protocol/openid-connect/token'
            )
        ),
        'OTEL_ENABLED': 'true',
        'OTEL_SERVICE_NAME': 'scraping-service',
        'OTEL_EXPORTER_OTLP_ENDPOINT': Variable.get(
            'OTEL_EXPORTER_OTLP_ENDPOINT',
            default_var=os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://otel-collector:4317')
        ),
    }


# =============================================================================
# Tracing distribuito
# =============================================================================

def generate_traceparent(dag_id, run_id):
    """Genera un traceparent W3C deterministico per DAG run."""
    import hashlib
    trace_id = hashlib.md5(f"{dag_id}:{run_id}".encode()).hexdigest()
    span_id = '%016x' % random.getrandbits(64)
    return f"00-{trace_id}-{span_id}-01"


# =============================================================================
# Operator factory: Docker locale / K8s produzione
# =============================================================================

class FilterableDockerOperator(DockerOperator):
    """
    DockerOperator con filtro città e iniezione TRACEPARENT.

    Skippa il task se la città non è nella conf della DAG run.
    Conf supportate: {"city": "milano"} o {"cities_today": "milano,roma"}.
    """
    def __init__(self, filter_key, city_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filter_key = filter_key
        self.city_name = city_name

    def execute(self, context):
        dag_run = context['dag_run']
        conf = dag_run.conf or {}

        should_run = True
        skip_reason = ""

        if 'city' in conf:
            target_city = conf['city'].lower().strip()
            if self.city_name.lower() != target_city:
                should_run = False
                skip_reason = f"Global 'city' filter set to {target_city}"
        elif self.filter_key in conf:
            allowed_cities = conf.get(self.filter_key)
            if isinstance(allowed_cities, str):
                allowed_cities = allowed_cities.split(',')
            allowed_cities = [c.lower().strip() for c in allowed_cities]
            if self.city_name.lower() not in allowed_cities:
                should_run = False
                skip_reason = f"Not in {self.filter_key} list"

        if not should_run:
            print(f"Skipping {self.city_name}. Reason: {skip_reason}")
            raise AirflowSkipException(f"Skipped: {skip_reason}")

        # Inietta TRACEPARENT + DAG context per organizzare output per run
        traceparent = generate_traceparent(dag_run.dag_id, dag_run.run_id)
        self.environment = {
            **(self.environment or {}),
            'TRACEPARENT': traceparent,
            'DAG_ID': dag_run.dag_id,
            'DAG_RUN_ID': dag_run.run_id,
        }

        return super().execute(context)


def _create_k8s_operator(task_id, filter_key, city_name, command, env, dag_obj):
    """Crea KubernetesPodOperator con filtro città (lazy import)."""
    from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
    from kubernetes.client import models as k8s

    # Aggiungi DAG context per organizzare output per run
    env_with_dag = {
        **env,
        'DAG_ID': '{{ dag.dag_id }}',
        'DAG_RUN_ID': '{{ run_id }}',
    }
    env_vars = [k8s.V1EnvVar(name=k, value=v) for k, v in env_with_dag.items()]

    return KubernetesPodOperator(
        task_id=task_id,
        name=f'scrapy-{city_name}-{task_id}',
        namespace=K8S_NAMESPACE,
        image=SCRAPY_IMAGE,
        cmds=['scrapy', 'crawl'],
        arguments=command,
        env_vars=env_vars,
        service_account_name=K8S_SERVICE_ACCOUNT,
        image_pull_policy=K8S_IMAGE_PULL_POLICY,
        is_delete_operator_pod=True,
        get_logs=True,
        dag=dag_obj,
    )


def create_scraper_operator(task_id, filter_key, city_name, spider, spider_args, env, dag_obj):
    """Factory: crea DockerOperator (dev) o KubernetesPodOperator (k8s)."""
    command = ['scrapy', 'crawl', spider] + spider_args

    if SCRAPER_EXECUTOR == 'k8s':
        return _create_k8s_operator(task_id, filter_key, city_name, command, env, dag_obj)

    # Docker: volume mount per codice sorgente e output dati in dev
    from docker.types import Mount
    mounts = []
    if SCRAPY_SRC_PATH:
        mounts.append(Mount(target='/app/events_scraper', source=SCRAPY_SRC_PATH, type='bind'))
    if SCRAPY_DATA_PATH:
        mounts.append(Mount(target='/data', source=SCRAPY_DATA_PATH, type='bind'))

    return FilterableDockerOperator(
        task_id=task_id,
        filter_key=filter_key,
        city_name=city_name,
        image=SCRAPY_IMAGE,
        command=command,
        environment=env,
        working_dir='/app/events_scraper',
        network_mode=DOCKER_NETWORK,
        mounts=mounts or None,
        auto_remove=True,
        force_pull=False,
        docker_url=DOCKER_URL,
        dag=dag_obj,
    )


# =============================================================================
# ETL: Log run
# =============================================================================

def log_etl_run(**context):
    """Registra l'esecuzione ETL (staging_count letto direttamente dal DB)"""
    dag_run = context['dag_run']

    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    conn = hook.get_conn()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM events_data."staging_events"')
    staging_count = cursor.fetchone()[0]

    cursor.execute("""
        INSERT INTO public.etl_runs (
            run_type, staging_count, inserted_count, updated_count,
            status, started_at, staging_completed_at
        ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    """, (
        dag_run.dag_id,
        staging_count,
        0, 0,
        'completed',
        dag_run.start_date,
    ))

    conn.commit()
    cursor.close()
    conn.close()

    print(f"ETL Run logged: staging={staging_count}")


def create_log_task(dag_obj):
    """Crea il task di log ETL per il DAG"""
    return PythonOperator(
        task_id='log_etl_run',
        python_callable=log_etl_run,
        trigger_rule=TriggerRule.NONE_FAILED,
        dag=dag_obj,
    )


# =============================================================================
# Generazione task per città
# =============================================================================

def generate_city_tasks(dag_obj, periodo, include_zero=False):
    """Genera TaskGroup per ogni città con operator adatto all'ambiente."""
    city_groups = []
    env = get_scrapy_env()

    for city in ALL_CITIES:
        has_today = city in CITIES_TODAY
        has_zero = include_zero and (city in CITIES_ZERO)
        has_tourism = city in CITIES_TOURISM

        if not has_today and not has_zero and not has_tourism:
            continue

        with TaskGroup(group_id=f'process_{city}', dag=dag_obj) as city_group:

            if has_today:
                create_scraper_operator(
                    task_id='scrape_city_today',
                    filter_key='cities_today',
                    city_name=city,
                    spider='city_today',
                    spider_args=['-a', f'cities={city}', '-a', f'periodo={periodo}'],
                    env=env,
                    dag_obj=dag_obj,
                )

            if has_zero:
                create_scraper_operator(
                    task_id='scrape_zero_eu',
                    filter_key='cities_zero',
                    city_name=city,
                    spider='zero_eu',
                    spider_args=['-a', f'city={city}'],
                    env=env,
                    dag_obj=dag_obj,
                )

            if has_tourism:
                tourism = CITIES_TOURISM[city]
                create_scraper_operator(
                    task_id=f'scrape_{tourism["spider"]}',
                    filter_key='cities_tourism',
                    city_name=city,
                    spider=tourism['spider'],
                    spider_args=tourism['args'],
                    env=env,
                    dag_obj=dag_obj,
                )

        city_groups.append(city_group)

    return city_groups


# =============================================================================
# Spider regionali (non legati a città specifiche)
# =============================================================================

REGIONAL_SPIDERS = {
    # Nazionale
    'nazionale': [
        {'spider': 'artribune', 'args': ['-a', 'max_pages=10']},
    ],
    # Nord
    'valle_d_aosta': [
        {'spider': 'love_vda', 'args': ['-a', 'max_pages=5']},
    ],
    'lombardia': [
        {'spider': 'in_lombardia', 'args': ['-a', 'max_pages=10']},
    ],
    'trentino': [
        {'spider': 'visit_trentino', 'args': ['-a', 'max_pages=10']},
    ],
    'alto_adige': [
        {'spider': 'suedtirol', 'args': ['-a', 'max_pages=5']},
    ],
    'veneto': [
        {'spider': 'veneto_eu', 'args': ['-a', 'max_pages=10']},
    ],
    'friuli_venezia_giulia': [
        {'spider': 'turismo_fvg', 'args': ['-a', 'max_pages=10']},
    ],
    'liguria': [
        {'spider': 'la_mia_liguria', 'args': ['-a', 'max_pages=10']},
    ],
    # Centro
    'toscana': [
        {'spider': 'visit_tuscany', 'args': ['-a', 'max_pages=15']},
    ],
    'umbria': [
        {'spider': 'umbria_tourism', 'args': ['-a', 'max_pages=5']},
    ],
    'marche': [
        {'spider': 'lets_marche', 'args': ['-a', 'max_pages=10']},
    ],
    'lazio': [
        {'spider': 'visit_lazio', 'args': ['-a', 'max_pages=5']},
    ],
    # Sud
    'abruzzo': [
        {'spider': 'abruzzo_turismo', 'args': ['-a', 'max_pages=10']},
    ],
    # 'molise': [  # Disattivato: Liferay incompatibile con Scrapy Twisted (body vuoto)
    #     {'spider': 'visit_molise', 'args': ['-a', 'max_pages=3']},
    # ],
    'campania': [
        {'spider': 'in_campania', 'args': ['-a', 'max_pages=10']},
    ],
    'puglia': [
        {'spider': 'puglia_culture', 'args': ['-a', 'max_pages=10']},
        {'spider': 'viaggiare_in_puglia', 'args': ['-a', 'max_pages=5']},
    ],
    'basilicata': [
        {'spider': 'basilicata_turistica', 'args': ['-a', 'max_pages=5']},
    ],
    # Isole
    'sicilia': [
        {'spider': 'visit_sicily', 'args': ['-a', 'max_pages=5']},
    ],
    'sardegna': [
        {'spider': 'sardegna_turismo', 'args': ['-a', 'max_pages=5']},
    ],
}


def generate_regional_tasks(dag_obj):
    """Genera TaskGroup 'regionali' con sotto-gruppi per regione."""
    env = get_scrapy_env()

    with TaskGroup(group_id='regionali', dag=dag_obj) as regional_group:
        for regione, spiders in REGIONAL_SPIDERS.items():
            with TaskGroup(group_id=regione, dag=dag_obj):
                for spider_conf in spiders:
                    create_scraper_operator(
                        task_id=f'scrape_{spider_conf["spider"]}',
                        filter_key=spider_conf['spider'],
                        city_name=spider_conf['spider'],
                        spider=spider_conf['spider'],
                        spider_args=spider_conf['args'],
                        env=env,
                        dag_obj=dag_obj,
                    )

    return regional_group


# =============================================================================
# DAG: Scraping giornaliero - questa settimana
# =============================================================================
with DAG(
    'etl_events_daily',
    default_args=default_args,
    description='ETL giornaliero eventi - questa settimana',
    schedule_interval='0 6 * * *',
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['events', 'etl', 'daily'],
) as dag_daily:

    log = create_log_task(dag_daily)
    city_groups = generate_city_tasks(dag_daily, 'questa-settimana', include_zero=True)
    regional = generate_regional_tasks(dag_daily)
    city_groups >> log
    regional >> log


# =============================================================================
# DAG: Scraping settimanale - prossima settimana
# =============================================================================
with DAG(
    'etl_events_weekly',
    default_args=default_args,
    description='ETL settimanale eventi - prossima settimana',
    schedule_interval='0 8 * * 0',
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['events', 'etl', 'weekly'],
) as dag_weekly:

    log_w = create_log_task(dag_weekly)
    city_groups_w = generate_city_tasks(dag_weekly, 'prossima-settimana', include_zero=False)
    regional_w = generate_regional_tasks(dag_weekly)
    city_groups_w >> log_w
    regional_w >> log_w


# =============================================================================
# DAG: Scraping mensile - questo mese
# =============================================================================
with DAG(
    'etl_events_monthly',
    default_args=default_args,
    description='ETL mensile eventi - questo mese',
    schedule_interval='0 4 1 * *',
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['events', 'etl', 'monthly'],
) as dag_monthly:

    log_m = create_log_task(dag_monthly)
    city_groups_m = generate_city_tasks(dag_monthly, 'questo-mese', include_zero=False)
    regional_m = generate_regional_tasks(dag_monthly)
    city_groups_m >> log_m
    regional_m >> log_m
