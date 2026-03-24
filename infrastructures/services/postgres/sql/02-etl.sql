-- =============================================================================
-- TABELLA TRACKING: log delle esecuzioni ETL
-- =============================================================================
CREATE TABLE IF NOT EXISTS events_data.etl_runs (
    id SERIAL PRIMARY KEY,
    run_type VARCHAR(50) NOT NULL,  -- 'daily', 'weekly', 'monthly', 'manual'
    source VARCHAR(50),
    cities TEXT[],
    periodo VARCHAR(50),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    staging_completed_at TIMESTAMP WITH TIME ZONE,
    upsert_completed_at TIMESTAMP WITH TIME ZONE,
    staging_count INTEGER DEFAULT 0,
    inserted_count INTEGER DEFAULT 0,
    updated_count INTEGER DEFAULT 0,
    unchanged_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'running',
    error_message TEXT
);

-- =============================================================================
-- TABELLA ERRORI: log dei record problematici
-- =============================================================================
CREATE TABLE IF NOT EXISTS events_data.etl_errors (
    id SERIAL PRIMARY KEY,
    error_type VARCHAR(50) NOT NULL,  -- 'missing_required_fields', 'invalid_json', 'db_insert_error'
    source VARCHAR(50),               -- 'city_today', 'zero_eu'
    json_file VARCHAR(255),           -- nome del file JSON
    record_data JSONB,                -- dati del record problematico
    error_message TEXT,               -- messaggio di errore
    dag_run_id VARCHAR(255),          -- ID del DAG run
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_etl_errors_type ON events_data.etl_errors(error_type);
CREATE INDEX IF NOT EXISTS idx_etl_errors_source ON events_data.etl_errors(source);
CREATE INDEX IF NOT EXISTS idx_etl_errors_created ON events_data.etl_errors(created_at);

-- =============================================================================
-- FUNZIONE: Truncate staging
-- =============================================================================
CREATE OR REPLACE FUNCTION events_data.truncate_staging()
RETURNS void AS $$
BEGIN
    TRUNCATE TABLE events_data.staging_events;
    RAISE NOTICE 'Staging table truncated';
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- FUNZIONE: Marca eventi non più presenti come inattivi
-- (opzionale, per eventi scaduti non più nello scraping)
-- =============================================================================
CREATE OR REPLACE FUNCTION events_data.mark_missing_inactive(p_source VARCHAR, p_city VARCHAR DEFAULT NULL)
RETURNS INT AS $$
DECLARE
    v_count INT;
BEGIN
    UPDATE events_data.events p
    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
    WHERE p.source = p_source
      AND p.status = 'published'
      AND (p_city IS NULL OR p.city = p_city)
      AND p.is_active = TRUE
      AND NOT EXISTS (
          SELECT 1 FROM events_data.events s
          WHERE s.uuid = p.uuid AND s.status = 'staging'
      );

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE 'Marked % events as inactive for source % city %', v_count, p_source, COALESCE(p_city, 'ALL');

    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- VIEW: Statistiche ETL
-- =============================================================================
CREATE OR REPLACE VIEW events_data.etl_stats AS
SELECT
    run_type,
    source,
    DATE(started_at) as run_date,
    staging_count,
    inserted_count,
    updated_count,
    unchanged_count,
    status,
    EXTRACT(EPOCH FROM (upsert_completed_at - started_at)) as duration_seconds
FROM events_data.etl_runs
ORDER BY started_at DESC;
