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
-- FUNZIONE: Upsert da staging a production
-- Confronta content_hash per aggiornare solo se cambiato
-- =============================================================================
CREATE OR REPLACE FUNCTION events_data.upsert_from_staging()
RETURNS TABLE(inserted INT, updated INT, unchanged INT) AS $$
DECLARE
    v_inserted INT := 0;
    v_updated INT := 0;
    v_unchanged INT := 0;
    v_total INT := 0;
BEGIN
    -- Conta totale staging (deduplicati)
    SELECT COUNT(DISTINCT uuid) INTO v_total FROM events_data.staging_events;

    -- UPSERT con confronto hash (usando DISTINCT ON per deduplicare)
    WITH deduplicated AS (
        SELECT DISTINCT ON (uuid) *
        FROM events_data.staging_events
        ORDER BY uuid, scraped_at DESC NULLS LAST
    ),
    upsert_result AS (
        INSERT INTO events_data.production_events (
            uuid, content_hash, source, url, title, description,
            category, image_url, city, location_name, location_address,
            location_coords, price, website, date_start, date_end,
            time_start, time_end, time_info, schedule, weekdays,
            raw_data, scraped_at, is_active
        )
        SELECT
            s.uuid, s.content_hash, s.source, s.url, s.title, s.description,
            s.category, s.image_url, s.city, s.location_name, s.location_address,
            s.location_coords, s.price, s.website, s.date_start, s.date_end,
            s.time_start, s.time_end, s.time_info, s.schedule, s.weekdays,
            s.raw_data, s.scraped_at, TRUE
        FROM deduplicated s
        ON CONFLICT (uuid)
        DO UPDATE SET
            content_hash = EXCLUDED.content_hash,
            description = EXCLUDED.description,
            category = EXCLUDED.category,
            image_url = EXCLUDED.image_url,
            price = EXCLUDED.price,
            website = EXCLUDED.website,
            time_info = EXCLUDED.time_info,
            schedule = EXCLUDED.schedule,
            raw_data = EXCLUDED.raw_data,
            scraped_at = EXCLUDED.scraped_at,
            updated_at = CURRENT_TIMESTAMP,
            is_active = TRUE
        WHERE events_data.production_events_data.content_hash IS DISTINCT FROM EXCLUDED.content_hash
        RETURNING
            (xmax = 0) AS is_insert
    )
    SELECT
        COUNT(*) FILTER (WHERE is_insert = TRUE),
        COUNT(*) FILTER (WHERE is_insert = FALSE)
    INTO v_inserted, v_updated
    FROM upsert_result;

    -- Calcola unchanged
    v_unchanged := v_total - v_inserted - v_updated;

    RAISE NOTICE 'Upsert completed: % inserted, % updated, % unchanged',
                 v_inserted, v_updated, v_unchanged;

    RETURN QUERY SELECT v_inserted, v_updated, v_unchanged;
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
    UPDATE events_data.production_events p
    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
    WHERE p.source = p_source
      AND (p_city IS NULL OR p.city = p_city)
      AND p.is_active = TRUE
      AND NOT EXISTS (
          SELECT 1 FROM events_data.staging_events s
          WHERE s.uuid = p.uuid
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
