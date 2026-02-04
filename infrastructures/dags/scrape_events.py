"""
DAG per lo scraping degli eventi - Strategia ETL con Staging Table

Pipeline:
1. Truncate staging
2. Scraping (DockerOperator) → JSON files (Parallel execution per city)
3. Load JSON → staging_events
4. Upsert staging → production_events (con confronto hash)
5. Log ETL run
"""

import json
import os
import glob
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule
from airflow.exceptions import AirflowSkipException
from docker.types import Mount

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,  # Increased retries for robustness
    'retry_delay': timedelta(minutes=2),
}

# Configurazione
SCRAPY_IMAGE = 'scrapy-events:latest'
POSTGRES_CONN_ID = 'events_postgres'
DATA_DIR = '/data'

CITIES_TODAY = [
    'milano', 'torino', 'genova', 'venezia', 'bologna', 'verona', 'treviso', 'trento', 'udine', 'pordenone',
    'vicenza', 'padova', 'monza', 'lecco', 'sondrio', 'novara', 'brescia', 'parma', 'rimini', 'ravenna',
    'forli', 'cesena', 'como', 'piacenza', 'trieste', 'roma', 'firenze', 'pisa', 'livorno', 'perugia',
    'terni', 'ancona', 'latina', 'frosinone', 'viterbo', 'arezzo', 'pescara', 'napoli', 'palermo',
    'catania', 'messina', 'bari', 'foggia', 'salerno', 'avellino', 'reggio-calabria', 'lecce', 'brindisi',
    'agrigento', 'caserta'
]
CITIES_ZERO = ['milano', 'roma', 'bologna', 'napoli', 'firenze', 'venezia', 'torino']

# Unione di tutte le città univoche per l'iterazione
ALL_CITIES = sorted(list(set(CITIES_TODAY + CITIES_ZERO)))


class FilterableDockerOperator(DockerOperator):
    """
    DockerOperator that skips execution if the city is not in the configuration.
    Expects 'filter_key' (e.g., 'cities_today', 'cities_zero') and 'city_name' in kwargs.
    
    Logic:
    1. If 'city' is in conf (Global Override): Run ONLY if city_name matches conf['city'].
    2. Else if 'filter_key' is in conf: Run ONLY if city_name is in conf[filter_key].
    3. Else: Run all (Default).
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

        # Check Global City Override first (e.g., {"city": "milano"})
        if 'city' in conf:
            target_city = conf['city'].lower().strip()
            if self.city_name.lower() != target_city:
                should_run = False
                skip_reason = f"Global 'city' filter set to {target_city}"
        
        # Check Specific Filter (e.g., {"cities_zero": "milano,roma"})
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
        
        return super().execute(context)


# =============================================================================
# FUNZIONI ETL
# =============================================================================

def log_etl_error(cursor, error_type, source, json_file, record_data, error_message, dag_run_id):
    """Helper per loggare errori nella tabella etl_errors"""
    try:
        cursor.execute("""
            INSERT INTO events_data.etl_errors (error_type, source, json_file, record_data, error_message, dag_run_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (error_type, source, os.path.basename(json_file), json.dumps(record_data) if record_data else None, error_message, dag_run_id))
    except Exception as e:
        print(f"Warning: Could not log error to etl_errors: {e}")


def load_json_to_staging(**context):
    """
    STEP 3: Carica i JSON files nella tabella staging_events
    Logga record problematici nella tabella etl_errors
    """
    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    conn = hook.get_conn()
    cursor = conn.cursor()

    dag_run_id = context['dag_run'].run_id

    json_files = glob.glob(f'{DATA_DIR}/*.json')
    loaded_count = 0
    skipped_count = 0
    error_count = 0

    for json_file in json_files:
        filename = os.path.basename(json_file).lower()
        source = 'zero_eu' if 'zero' in filename else 'city_today'

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                events = json.load(f)

            for event in events:
                # Validazione campi obbligatori
                missing_fields = []
                if not event.get('uuid'):
                    missing_fields.append('uuid')
                if not event.get('title'):
                    missing_fields.append('title')

                if missing_fields:
                    skipped_count += 1
                    error_count += 1
                    log_etl_error(
                        cursor,
                        error_type='missing_required_fields',
                        source=source,
                        json_file=json_file,
                        record_data=event,
                        error_message=f"Missing fields: {', '.join(missing_fields)}",
                        dag_run_id=dag_run_id
                    )
                    continue

                # Normalizza category come array
                category = event.get('category')
                if category and not isinstance(category, list):
                    category = [category]

                try:
                    cursor.execute("""
                        INSERT INTO events_data.staging_events (
                            uuid, content_hash, source, url, title, description,
                            category, image_url, city, location_name, location_address,
                            price, website, date_start, date_end, time_info,
                            schedule, weekdays, raw_data, scraped_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s
                        )
                    """, (
                        event.get('uuid'),
                        event.get('content_hash'),
                        source,
                        event.get('url'),
                        event.get('title'),
                        event.get('description'),
                        category,
                        event.get('image_url'),
                        event.get('city'),
                        event.get('location_name'),
                        event.get('location_address'),
                        event.get('price'),
                        event.get('website'),
                        event.get('date_start'),
                        event.get('date_end'),
                        event.get('time_info'),
                        event.get('schedule'),
                        event.get('weekdays'),
                        json.dumps(event),
                        event.get('scraped_at')
                    ))
                    loaded_count += 1
                except Exception as db_err:
                    error_count += 1
                    log_etl_error(
                        cursor,
                        error_type='db_insert_error',
                        source=source,
                        json_file=json_file,
                        record_data=event,
                        error_message=str(db_err),
                        dag_run_id=dag_run_id
                    )
                    conn.rollback()

            conn.commit()

            # Archivia il file processato
            archive_path = json_file.replace('.json', f'.{datetime.now().strftime("%Y%m%d%H%M%S")}.processed')
            os.rename(json_file, archive_path)

        except json.JSONDecodeError as e:
            error_count += 1
            log_etl_error(
                cursor,
                error_type='invalid_json',
                source=source,
                json_file=json_file,
                record_data=None,
                error_message=str(e),
                dag_run_id=dag_run_id
            )
            conn.commit()
            print(f"Logged corrupted JSON file {json_file}: {e}")
            continue
        except Exception as e:
            print(f"Errore processando {json_file}: {e}")
            conn.rollback()
            raise

    cursor.close()
    conn.close()

    # Push count per XCom
    context['ti'].xcom_push(key='staging_count', value=loaded_count)
    context['ti'].xcom_push(key='error_count', value=error_count)
    print(f"Loaded {loaded_count} events to staging (skipped {skipped_count}, errors logged: {error_count})")
    return loaded_count


def upsert_to_production(**context):
    """
    STEP 4: Upsert da staging a production usando la funzione SQL
    """
    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    conn = hook.get_conn()
    cursor = conn.cursor()

    # Chiama la funzione upsert
    cursor.execute("SELECT * FROM events_data.upsert_from_staging()")
    result = cursor.fetchone()

    inserted, updated, unchanged = result if result else (0, 0, 0)

    conn.commit()
    cursor.close()
    conn.close()

    # Push results per XCom
    context['ti'].xcom_push(key='inserted_count', value=inserted)
    context['ti'].xcom_push(key='updated_count', value=updated)
    context['ti'].xcom_push(key='unchanged_count', value=unchanged)

    print(f"Upsert completed: {inserted} inserted, {updated} updated, {unchanged} unchanged")
    return {'inserted': inserted, 'updated': updated, 'unchanged': unchanged}


def log_etl_run(**context):
    """
    STEP 5: Registra l'esecuzione ETL
    """
    ti = context['ti']
    dag_run = context['dag_run']

    staging_count = ti.xcom_pull(key='staging_count', task_ids='load_to_staging') or 0
    inserted = ti.xcom_pull(key='inserted_count', task_ids='upsert_to_production') or 0
    updated = ti.xcom_pull(key='updated_count', task_ids='upsert_to_production') or 0
    unchanged = ti.xcom_pull(key='unchanged_count', task_ids='upsert_to_production') or 0

    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    conn = hook.get_conn()
    cursor = conn.cursor()

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


def cleanup_old_files(**context):
    """
    Pulisce i file processati più vecchi di 7 giorni
    """
    import time
    cutoff = time.time() - (7 * 24 * 60 * 60)  # 7 giorni

    for f in glob.glob(f'{DATA_DIR}/*.processed'):
        if os.path.getmtime(f) < cutoff:
            os.remove(f)
            print(f"Removed old file: {f}")


# =============================================================================
# Helper Function to Build Tasks by City
# =============================================================================
def create_common_tasks(dag_obj):
    """Creates common tasks for all DAGs"""
    load = PythonOperator(
        task_id='load_to_staging',
        python_callable=load_json_to_staging,
        trigger_rule=TriggerRule.NONE_FAILED,
        dag=dag_obj,
    )
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
    return load, upsert, log


def generate_city_tasks(dag_obj, periodo, include_zero=False):
    """
    Generates TaskGroups for each city.
    Inside each city group, creates tasks for supported sources.
    """
    city_groups = []
    
    for city in ALL_CITIES:
        # Check if city is relevant for this run
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
                    mounts=[
                        Mount(source='/Users/skyweb/Sites/today_events/infrastructures/data',
                              target='/data/output', type='bind')
                    ],
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
                    mounts=[
                        Mount(source='/Users/skyweb/Sites/today_events/infrastructures/data',
                              target='/data/output', type='bind')
                    ],
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

    load, upsert, log = create_common_tasks(dag_daily)
    cleanup = PythonOperator(
        task_id='cleanup_old_files',
        python_callable=cleanup_old_files,
        trigger_rule=TriggerRule.NONE_FAILED,
        dag=dag_daily
    )

    # Generate groups for all cities (Both sources)
    city_groups = generate_city_tasks(dag_daily, 'questa-settimana', include_zero=True)

    # Pipeline
    truncate_staging >> city_groups >> load >> upsert >> log >> cleanup


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

    load_w, upsert_w, log_w = create_common_tasks(dag_weekly)
    
    # Only City Today
    city_groups_w = generate_city_tasks(dag_weekly, 'prossima-settimana', include_zero=False)

    truncate_staging_w >> city_groups_w >> load_w >> upsert_w >> log_w


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

    load_m, upsert_m, log_m = create_common_tasks(dag_monthly)

    # Only City Today
    city_groups_m = generate_city_tasks(dag_monthly, 'questo-mese', include_zero=False)

    truncate_staging_m >> city_groups_m >> load_m >> upsert_m >> log_m
