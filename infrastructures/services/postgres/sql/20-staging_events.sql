-- =============================================================================
-- TABELLA STAGING: eventi temporanei dallo scraping
-- =============================================================================
DROP TABLE IF EXISTS events_data.staging_events CASCADE;

CREATE TABLE IF NOT EXISTS events_data.staging_events (
    id SERIAL PRIMARY KEY,

    -- ID e Hashing
    event_id VARCHAR(255),             -- ID originale della fonte (slug dall'URL)
    uuid VARCHAR(16) UNIQUE NOT NULL,  -- Hash interno (titolo + data + location)
    content_hash VARCHAR(16),          -- Hash del contenuto per rilevare modifiche

    -- Metadati Fonte
    source VARCHAR(50) NOT NULL,       -- Es: "city_today", "zero_eu"
    url TEXT,                          -- URL originale dell'evento

    -- Contenuto Core
    title TEXT NOT NULL,
    description TEXT,
    category TEXT[],                   -- Array di stringhe (es: {Musica, Live})
    image_url TEXT,                    -- Immagine locandina evento

    -- Location
    city VARCHAR(100),                 -- Nome città
    city_id INTEGER,                   -- FK a comuni_italiani.comuni(id)
    location_name VARCHAR(255),
    location_address TEXT,
    location_coords GEOMETRY(Point, 4326), -- Coordinate PostGIS (Long/Lat)

    -- Dettagli
    price TEXT,                        -- Testo libero prezzo
    website TEXT,                      -- Sito ufficiale dell'organizzatore

    -- Date
    date_start DATE,                   -- Data inizio
    date_end DATE,                     -- Data fine
    date_display TEXT,                 -- Testo leggibile (es: "dal 31 gennaio al 1 febbraio")

    -- Dati Tecnici
    raw_data JSONB,                    -- JSON originale completo
    scraped_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,

    -- Foreign Key
    CONSTRAINT fk_staging_city FOREIGN KEY (city_id)
        REFERENCES comuni_italiani.comuni(id) ON DELETE SET NULL
);

-- Commenti
COMMENT ON TABLE events_data.staging_events IS 'Tabella staging per eventi temporanei dallo scraping, prima della validazione.';
COMMENT ON COLUMN events_data.staging_events.event_id IS 'ID originale dalla fonte (es. slug dall URL).';
COMMENT ON COLUMN events_data.staging_events.uuid IS 'Hash univoco interno (titolo + data_start + location_name).';
COMMENT ON COLUMN events_data.staging_events.content_hash IS 'Hash del contenuto per rilevare modifiche.';
COMMENT ON COLUMN events_data.staging_events.source IS 'Codice della fonte dati (es. city_today).';
COMMENT ON COLUMN events_data.staging_events.category IS 'Array di categorie (TEXT[]).';
COMMENT ON COLUMN events_data.staging_events.city_id IS 'FK a comuni_italiani.comuni per join geografici.';
COMMENT ON COLUMN events_data.staging_events.location_coords IS 'Coordinate PostGIS (SRID 4326). Usare ST_SetSRID(ST_MakePoint(lng, lat), 4326).';
COMMENT ON COLUMN events_data.staging_events.date_display IS 'Rappresentazione testuale della data (es. "dal 31 gennaio al 1 febbraio").';
COMMENT ON COLUMN events_data.staging_events.raw_data IS 'Dump completo del JSON scaricato dalla fonte.';

-- Indici staging
CREATE INDEX IF NOT EXISTS idx_staging_uuid ON events_data.staging_events(uuid);
CREATE INDEX IF NOT EXISTS idx_staging_city ON events_data.staging_events(city);
CREATE INDEX IF NOT EXISTS idx_staging_city_id ON events_data.staging_events(city_id);
CREATE INDEX IF NOT EXISTS idx_staging_date_start ON events_data.staging_events(date_start);
CREATE INDEX IF NOT EXISTS idx_staging_date_end ON events_data.staging_events(date_end);
CREATE INDEX IF NOT EXISTS idx_staging_source ON events_data.staging_events(source);
CREATE INDEX IF NOT EXISTS idx_staging_active ON events_data.staging_events(is_active);
CREATE INDEX IF NOT EXISTS idx_staging_coords ON events_data.staging_events USING GIST(location_coords);
CREATE INDEX IF NOT EXISTS idx_staging_category ON events_data.staging_events USING GIN(category);

-- Trigger updated_at
CREATE OR REPLACE FUNCTION events_data.update_staging_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_staging_updated_at ON events_data.staging_events;
CREATE TRIGGER trigger_staging_updated_at
    BEFORE UPDATE ON events_data.staging_events
    FOR EACH ROW
    EXECUTE FUNCTION events_data.update_staging_updated_at();
