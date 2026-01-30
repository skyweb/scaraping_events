-- =============================================================================
-- SCHEMA: comuni_italiani - Confini amministrativi ISTAT 01/01/2025
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS comuni_italiani;

-- =============================================================================
-- TABELLA: Ripartizioni geografiche (5 aree)
-- =============================================================================
CREATE TABLE IF NOT EXISTS comuni_italiani.ripartizioni (
    id SERIAL PRIMARY KEY,
    cod_rip INTEGER UNIQUE NOT NULL,
    den_rip VARCHAR(50) NOT NULL,
    geom GEOMETRY(MultiPolygon, 4326),
    shape_area DOUBLE PRECISION,
    shape_length DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_ripartizioni_geom ON comuni_italiani.ripartizioni USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_ripartizioni_cod ON comuni_italiani.ripartizioni(cod_rip);

COMMENT ON TABLE comuni_italiani.ripartizioni IS 'Ripartizioni geografiche ISTAT: Nord-Ovest, Nord-Est, Centro, Sud, Isole';

-- =============================================================================
-- TABELLA: Regioni (20)
-- =============================================================================
CREATE TABLE IF NOT EXISTS comuni_italiani.regioni (
    id SERIAL PRIMARY KEY,
    cod_rip INTEGER NOT NULL,
    cod_reg INTEGER UNIQUE NOT NULL,
    den_reg VARCHAR(50) NOT NULL,
    geom GEOMETRY(MultiPolygon, 4326),
    shape_area DOUBLE PRECISION,
    shape_length DOUBLE PRECISION,
    FOREIGN KEY (cod_rip) REFERENCES comuni_italiani.ripartizioni(cod_rip)
);

CREATE INDEX IF NOT EXISTS idx_regioni_geom ON comuni_italiani.regioni USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_regioni_cod ON comuni_italiani.regioni(cod_reg);
CREATE INDEX IF NOT EXISTS idx_regioni_rip ON comuni_italiani.regioni(cod_rip);

COMMENT ON TABLE comuni_italiani.regioni IS 'Regioni italiane con confini geografici ISTAT';

-- =============================================================================
-- TABELLA: Province e Città Metropolitane (107)
-- =============================================================================
CREATE TABLE IF NOT EXISTS comuni_italiani.province (
    id SERIAL PRIMARY KEY,
    cod_rip INTEGER NOT NULL,
    cod_reg INTEGER NOT NULL,
    cod_prov INTEGER NOT NULL,
    cod_cm INTEGER,                    -- Codice città metropolitana (0 se provincia)
    cod_uts INTEGER UNIQUE NOT NULL,   -- Codice unità territoriale sovracomunale
    den_prov VARCHAR(50),              -- Denominazione provincia
    den_cm VARCHAR(50),                -- Denominazione città metropolitana
    den_uts VARCHAR(50) NOT NULL,      -- Denominazione unità territoriale
    sigla VARCHAR(2) NOT NULL,         -- Sigla automobilistica
    tipo_uts VARCHAR(50),              -- Tipo: Provincia o Città metropolitana
    geom GEOMETRY(MultiPolygon, 4326),
    shape_area DOUBLE PRECISION,
    shape_length DOUBLE PRECISION,
    FOREIGN KEY (cod_reg) REFERENCES comuni_italiani.regioni(cod_reg)
);

CREATE INDEX IF NOT EXISTS idx_province_geom ON comuni_italiani.province USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_province_cod ON comuni_italiani.province(cod_uts);
CREATE INDEX IF NOT EXISTS idx_province_sigla ON comuni_italiani.province(sigla);
CREATE INDEX IF NOT EXISTS idx_province_reg ON comuni_italiani.province(cod_reg);
CREATE INDEX IF NOT EXISTS idx_province_prov ON comuni_italiani.province(cod_prov);

COMMENT ON TABLE comuni_italiani.province IS 'Province e Città Metropolitane italiane con confini geografici ISTAT';

-- =============================================================================
-- TABELLA: Comuni (7896)
-- =============================================================================
CREATE TABLE IF NOT EXISTS comuni_italiani.comuni (
    id SERIAL PRIMARY KEY,
    cod_rip INTEGER NOT NULL,
    cod_reg INTEGER NOT NULL,
    cod_prov INTEGER NOT NULL,
    cod_cm INTEGER,
    cod_uts INTEGER NOT NULL,
    pro_com INTEGER UNIQUE NOT NULL,   -- Codice ISTAT numerico progressivo
    pro_com_t VARCHAR(6) NOT NULL,     -- Codice ISTAT testuale (con zeri)
    comune VARCHAR(100) NOT NULL,      -- Nome comune
    comune_a VARCHAR(100),             -- Nome alternativo (minoranze linguistiche)
    cc_uts INTEGER,                    -- Codice capoluogo
    geom GEOMETRY(MultiPolygon, 4326),
    centroid GEOMETRY(Point, 4326),    -- Centroide calcolato
    shape_area DOUBLE PRECISION,
    shape_length DOUBLE PRECISION,
    FOREIGN KEY (cod_uts) REFERENCES comuni_italiani.province(cod_uts)
);

CREATE INDEX IF NOT EXISTS idx_comuni_geom ON comuni_italiani.comuni USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_comuni_centroid ON comuni_italiani.comuni USING GIST(centroid);
CREATE INDEX IF NOT EXISTS idx_comuni_pro_com ON comuni_italiani.comuni(pro_com);
CREATE INDEX IF NOT EXISTS idx_comuni_pro_com_t ON comuni_italiani.comuni(pro_com_t);
CREATE INDEX IF NOT EXISTS idx_comuni_nome ON comuni_italiani.comuni(comune);
CREATE INDEX IF NOT EXISTS idx_comuni_nome_lower ON comuni_italiani.comuni(LOWER(comune));
CREATE INDEX IF NOT EXISTS idx_comuni_uts ON comuni_italiani.comuni(cod_uts);
CREATE INDEX IF NOT EXISTS idx_comuni_prov ON comuni_italiani.comuni(cod_prov);
CREATE INDEX IF NOT EXISTS idx_comuni_reg ON comuni_italiani.comuni(cod_reg);

COMMENT ON TABLE comuni_italiani.comuni IS 'Comuni italiani con confini geografici ISTAT al 01/01/2025';
COMMENT ON COLUMN comuni_italiani.comuni.pro_com IS 'Codice ISTAT progressivo comunale (numerico)';
COMMENT ON COLUMN comuni_italiani.comuni.pro_com_t IS 'Codice ISTAT comunale testuale con zeri iniziali';
COMMENT ON COLUMN comuni_italiani.comuni.comune_a IS 'Nome alternativo per comuni con minoranze linguistiche';
COMMENT ON COLUMN comuni_italiani.comuni.centroid IS 'Centroide del poligono comunale, calcolato automaticamente';

-- =============================================================================
-- GRANT: Permessi
-- =============================================================================
GRANT ALL PRIVILEGES ON SCHEMA comuni_italiani TO events;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA comuni_italiani TO events;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA comuni_italiani TO events;
