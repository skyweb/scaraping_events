-- Inizializzazione database PostgreSQL con PostGIS
-- Strategia ETL con Staging Table

-- Abilita estensioni
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder;

-- Crea schema per gli eventi
CREATE SCHEMA IF NOT EXISTS events;

-- =============================================================================
-- TABELLA PRODUCTION: eventi finali validati
-- =============================================================================
CREATE TABLE IF NOT EXISTS events.production_events (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(16) UNIQUE NOT NULL,
    content_hash VARCHAR(16),
    source VARCHAR(50) NOT NULL,
    url TEXT,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT[],
    image_url TEXT,
    city VARCHAR(100),
    location_name VARCHAR(255),
    location_address TEXT,
    location_coords GEOMETRY(Point, 4326),
    price VARCHAR(100),
    website TEXT,
    date_start DATE,
    date_end DATE,
    time_start TIME,
    time_end TIME,
    time_info TEXT,
    schedule TEXT,
    weekdays TEXT,
    raw_data JSONB,
    scraped_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Indici production
CREATE INDEX IF NOT EXISTS idx_prod_uuid ON events.production_events(uuid);
CREATE INDEX IF NOT EXISTS idx_prod_city ON events.production_events(city);
CREATE INDEX IF NOT EXISTS idx_prod_date_start ON events.production_events(date_start);
CREATE INDEX IF NOT EXISTS idx_prod_date_end ON events.production_events(date_end);
CREATE INDEX IF NOT EXISTS idx_prod_source ON events.production_events(source);
CREATE INDEX IF NOT EXISTS idx_prod_active ON events.production_events(is_active);
CREATE INDEX IF NOT EXISTS idx_prod_coords ON events.production_events USING GIST(location_coords);
CREATE INDEX IF NOT EXISTS idx_prod_category ON events.production_events USING GIN(category);

-- =============================================================================
-- TABELLA STAGING: eventi temporanei dallo scraping
-- =============================================================================
CREATE TABLE IF NOT EXISTS events.staging_events (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(16) NOT NULL,
    content_hash VARCHAR(16),
    source VARCHAR(50) NOT NULL,
    url TEXT,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT[],
    image_url TEXT,
    city VARCHAR(100),
    location_name VARCHAR(255),
    location_address TEXT,
    location_coords GEOMETRY(Point, 4326),
    price VARCHAR(100),
    website TEXT,
    date_start DATE,
    date_end DATE,
    time_start TIME,
    time_end TIME,
    time_info TEXT,
    schedule TEXT,
    weekdays TEXT,
    raw_data JSONB,
    scraped_at TIMESTAMP WITH TIME ZONE,
    loaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indice staging per performance upsert
CREATE INDEX IF NOT EXISTS idx_staging_uuid ON events.staging_events(uuid);

-- =============================================================================
-- TABELLA TRACKING: log delle esecuzioni ETL
-- =============================================================================
CREATE TABLE IF NOT EXISTS events.etl_runs (
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
-- FUNZIONE: Truncate staging
-- =============================================================================
CREATE OR REPLACE FUNCTION events.truncate_staging()
RETURNS void AS $$
BEGIN
    TRUNCATE TABLE events.staging_events;
    RAISE NOTICE 'Staging table truncated';
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- FUNZIONE: Upsert da staging a production
-- Confronta content_hash per aggiornare solo se cambiato
-- =============================================================================
CREATE OR REPLACE FUNCTION events.upsert_from_staging()
RETURNS TABLE(inserted INT, updated INT, unchanged INT) AS $$
DECLARE
    v_inserted INT := 0;
    v_updated INT := 0;
    v_unchanged INT := 0;
    v_total INT := 0;
BEGIN
    -- Conta totale staging
    SELECT COUNT(*) INTO v_total FROM events.staging_events;

    -- UPSERT con confronto hash
    WITH upsert_result AS (
        INSERT INTO events.production_events (
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
        FROM events.staging_events s
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
        WHERE events.production_events.content_hash IS DISTINCT FROM EXCLUDED.content_hash
        RETURNING
            (xmax = 0) AS is_insert  -- TRUE se INSERT, FALSE se UPDATE
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
CREATE OR REPLACE FUNCTION events.mark_missing_inactive(p_source VARCHAR, p_city VARCHAR DEFAULT NULL)
RETURNS INT AS $$
DECLARE
    v_count INT;
BEGIN
    UPDATE events.production_events p
    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
    WHERE p.source = p_source
      AND (p_city IS NULL OR p.city = p_city)
      AND p.is_active = TRUE
      AND NOT EXISTS (
          SELECT 1 FROM events.staging_events s
          WHERE s.uuid = p.uuid
      );

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE 'Marked % events as inactive for source % city %', v_count, p_source, COALESCE(p_city, 'ALL');

    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- TRIGGER: updated_at automatico
-- =============================================================================
CREATE OR REPLACE FUNCTION events.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_prod_updated_at ON events.production_events;
CREATE TRIGGER trigger_prod_updated_at
    BEFORE UPDATE ON events.production_events
    FOR EACH ROW
    EXECUTE FUNCTION events.update_updated_at();

-- =============================================================================
-- VIEW: Eventi attivi (comoda per le query)
-- =============================================================================
CREATE OR REPLACE VIEW events.active_events AS
SELECT * FROM events.production_events WHERE is_active = TRUE;

-- =============================================================================
-- VIEW: Statistiche ETL
-- =============================================================================
CREATE OR REPLACE VIEW events.etl_stats AS
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
FROM events.etl_runs
ORDER BY started_at DESC;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA events TO events;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA events TO events;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA events TO events;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA events TO events;
