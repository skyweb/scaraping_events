"""
DAG per lo scraping degli eventi - Strategia ETL con ApiPipeline

Pipeline:
1. Truncate staging
2. Scraping (DockerOperator) → ApiPipeline → Django API → staging_events
3. Upsert staging → production_events (con confronto hash)
4. Log ETL run

Tracing distribuito:
- Ogni DAG run genera un trace context (TRACEPARENT)
- Il context viene propagato ai container Scrapy via env var
- Scrapy lo usa come parent span → trace end-to-end visibile in Jaeger
"""

import os
import random
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
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
SCRAPY_IMAGE = 'events-scrapy:latest'
POSTGRES_CONN_ID = 'events_postgres'

CITIES_TODAY = [
    'milano', 'torino', 'genova', 'venezia', 'bologna', 'verona', 'treviso', 'trento', 'udine', 'pordenone',
    'vicenza', 'padova', 'monza', 'lecco', 'sondrio', 'novara', 'brescia', 'parma', 'rimini', 'ravenna',
    'forli', 'cesena', 'como', 'piacenza', 'trieste', 'roma', 'firenze', 'pisa', 'livorno', 'perugia',
    'terni', 'ancona', 'latina', 'frosinone', 'viterbo', 'arezzo', 'pescara', 'napoli', 'palermo',
    'catania', 'messina', 'bari', 'foggia', 'salerno', 'avellino', 'reggio-calabria', 'lecce', 'brindisi',
    'agrigento', 'caserta'
]
CITIES_ZERO = ['milano', 'roma', 'bologna', 'napoli', 'firenze', 'venezia', 'torino']

ALL_CITIES = sorted(list(set(CITIES_TODAY + CITIES_ZERO)))

# Env vars passate ai container Scrapy per ApiPipeline
# Usa Airflow Variables (modificabili da UI: Admin > Variables) con fallback su env vars
def get_scrapy_env():
    """Ottiene le credenziali API da Airflow Variables o env vars"""
    return {
        'API_BASE_URL': Variable.get('API_BASE_URL', default_var=os.getenv('API_BASE_URL', 'http://backoffice:8000')),
        'API_CLIENT_ID': Variable.get('API_CLIENT_ID', default_var=os.getenv('API_CLIENT_ID', '')),
        'API_CLIENT_SECRET': Variable.get('API_CLIENT_SECRET', default_var=os.getenv('API_CLIENT_SECRET', '')),
        # OTel configurazione per i container Scrapy
        'OTEL_ENABLED': 'true',
        'OTEL_SERVICE_NAME': 'scraping-service',
        'OTEL_EXPORTER_OTLP_ENDPOINT': Variable.get(
            'OTEL_EXPORTER_OTLP_ENDPOINT',
            default_var=os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://otel-collector:4317')
        ),
    }


def generate_traceparent(dag_id, run_id):
    """Genera un traceparent W3C deterministico per DAG run.

    Il trace_id è derivato da dag_id + run_id → stesso trace per tutti i container della stessa run.
    Lo span_id è random per ogni container (generato nel template).
    """
    import hashlib
    trace_id = hashlib.md5(f"{dag_id}:{run_id}".encode()).hexdigest()
    span_id = '%016x' % random.getrandbits(64)
    return f"00-{trace_id}-{span_id}-01"


class FilterableDockerOperator(DockerOperator):
    """
    DockerOperator that skips execution if the city is not in the configuration.
    Expects 'filter_key' (e.g., 'cities_today', 'cities_zero') and 'city_name' in kwargs.

    Inietta TRACEPARENT nell'env del container per propagare il trace context
    della DAG run ai container Scrapy (tracing distribuito Airflow → Scrapy).
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

        # Inietta TRACEPARENT deterministico (stesso trace_id per tutta la DAG run)
        traceparent = generate_traceparent(dag_run.dag_id, dag_run.run_id)
        self.environment = {**(self.environment or {}), 'TRACEPARENT': traceparent}

        return super().execute(context)


# =============================================================================
# FUNZIONI ETL
# =============================================================================

def upsert_to_production(**context):
    """Upsert da staging a production usando la funzione SQL"""
    dag_run = context['dag_run']
    traceparent = generate_traceparent(dag_run.dag_id, dag_run.run_id)
    print(f"[OTEL] traceparent={traceparent} (upsert_to_production)")

    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    conn = hook.get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM events_data.upsert_from_staging()")
    result = cursor.fetchone()

    inserted, updated, unchanged = result if result else (0, 0, 0)

    conn.commit()
    cursor.close()
    conn.close()

    context['ti'].xcom_push(key='inserted_count', value=inserted)
    context['ti'].xcom_push(key='updated_count', value=updated)
    context['ti'].xcom_push(key='unchanged_count', value=unchanged)

    print(f"Upsert completed: {inserted} inserted, {updated} updated, {unchanged} unchanged")
    return {'inserted': inserted, 'updated': updated, 'unchanged': unchanged}


def log_etl_run(**context):
    """Registra l'esecuzione ETL (staging_count letto direttamente dal DB)"""
    ti = context['ti']
    dag_run = context['dag_run']

    inserted = ti.xcom_pull(key='inserted_count', task_ids='upsert_to_production') or 0
    updated = ti.xcom_pull(key='updated_count', task_ids='upsert_to_production') or 0
    unchanged = ti.xcom_pull(key='unchanged_count', task_ids='upsert_to_production') or 0

    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    conn = hook.get_conn()
    cursor = conn.cursor()

    # Staging count dal DB (popolato da ApiPipeline via Django API)
    cursor.execute("SELECT COUNT(*) FROM events_data.staging_events")
    staging_count = cursor.fetchone()[0]

    cursor.execute("""
        INSERT INTO events_data.etl_runs (
            run_type, staging_count, inserted_count, updated_count,
            unchanged_count, status, upsert_completed_at
        ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    """, (
        dag_run.dag_id,
        staging_count,
        inserted,
        updated,
        unchanged,
        'completed'
    ))

    conn.commit()
    cursor.close()
    conn.close()

    print(f"ETL Run logged: staging={staging_count}, inserted={inserted}, updated={updated}, unchanged={unchanged}")


# =============================================================================
# Helper Functions
# =============================================================================

def create_common_tasks(dag_obj):
    """Creates upsert + log tasks for all DAGs"""
    upsert = PythonOperator(
        task_id='upsert_to_production',
        python_callable=upsert_to_production,
        trigger_rule=TriggerRule.NONE_FAILED,
        dag=dag_obj,
    )
    log = PythonOperator(
        task_id='log_etl_run',
        python_callable=log_etl_run,
        trigger_rule=TriggerRule.NONE_FAILED,
        dag=dag_obj,
    )
    return upsert, log


def generate_city_tasks(dag_obj, periodo, include_zero=False):
    """Generates TaskGroups for each city with ApiPipeline env vars."""
    city_groups = []

    for city in ALL_CITIES:
        has_today = city in CITIES_TODAY
        has_zero = include_zero and (city in CITIES_ZERO)

        if not has_today and not has_zero:
            continue

        with TaskGroup(group_id=f'process_{city}', dag=dag_obj) as city_group:

            if has_today:
                FilterableDockerOperator(
                    task_id='scrape_city_today',
                    filter_key='cities_today',
                    city_name=city,
                    image=SCRAPY_IMAGE,
                    command=['city_today', city, f'--periodo={periodo}'],
                    environment=get_scrapy_env(),
                    network_mode='events-network',
                    auto_remove=True,
                    force_pull=False,
                    docker_url='unix://var/run/docker.sock',
                    dag=dag_obj,
                )

            if has_zero:
                FilterableDockerOperator(
                    task_id='scrape_zero_eu',
                    filter_key='cities_zero',
                    city_name=city,
                    image=SCRAPY_IMAGE,
                    command=['zero_eu', city],
                    environment=get_scrapy_env(),
                    network_mode='events-network',
                    auto_remove=True,
                    force_pull=False,
                    docker_url='unix://var/run/docker.sock',
                    dag=dag_obj,
                )

        city_groups.append(city_group)

    return city_groups


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

    truncate_staging = PostgresOperator(
        task_id='truncate_staging',
        postgres_conn_id=POSTGRES_CONN_ID,
        sql="SELECT events_data.truncate_staging();",
    )

    upsert, log = create_common_tasks(dag_daily)

    city_groups = generate_city_tasks(dag_daily, 'questa-settimana', include_zero=True)

    truncate_staging >> city_groups >> upsert >> log


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

    truncate_staging_w = PostgresOperator(
        task_id='truncate_staging',
        postgres_conn_id=POSTGRES_CONN_ID,
        sql="SELECT events_data.truncate_staging();",
    )

    upsert_w, log_w = create_common_tasks(dag_weekly)

    city_groups_w = generate_city_tasks(dag_weekly, 'prossima-settimana', include_zero=False)

    truncate_staging_w >> city_groups_w >> upsert_w >> log_w


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

    truncate_staging_m = PostgresOperator(
        task_id='truncate_staging',
        postgres_conn_id=POSTGRES_CONN_ID,
        sql="SELECT events_data.truncate_staging();",
    )

    upsert_m, log_m = create_common_tasks(dag_monthly)

    city_groups_m = generate_city_tasks(dag_monthly, 'questo-mese', include_zero=False)

    truncate_staging_m >> city_groups_m >> upsert_m >> log_m
