-- ============================================================================
-- Schema: comuni_istat
-- DDL PostgreSQL per i dati scraping comuni ISTAT
-- ============================================================================

BEGIN;

-- ── Tabella regioni ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS regioni (
    id              SERIAL PRIMARY KEY,
    nome            VARCHAR(100) NOT NULL UNIQUE,
    codice_istat    VARCHAR(5)   NOT NULL UNIQUE,
    popolazione     INTEGER,
    popolazione_maschi   INTEGER,
    popolazione_femmine  INTEGER,
    superficie_kmq  NUMERIC(10,2),
    densita         NUMERIC(10,2),
    num_province    SMALLINT,
    num_comuni      SMALLINT,
    capoluogo       VARCHAR(100),
    iso_3166_2      VARCHAR(10),
    nuts            VARCHAR(10),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_regioni_codice ON regioni (codice_istat);

-- ── Tabella province ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS province (
    id              SERIAL PRIMARY KEY,
    regione_id      INTEGER      NOT NULL REFERENCES regioni(id) ON DELETE CASCADE,
    nome            VARCHAR(100) NOT NULL,
    sigla           VARCHAR(5),
    codice_istat    VARCHAR(5)   NOT NULL UNIQUE,
    zona            VARCHAR(100),
    popolazione     INTEGER,
    popolazione_maschi   INTEGER,
    popolazione_femmine  INTEGER,
    superficie_kmq  NUMERIC(10,2),
    densita         NUMERIC(10,2),
    num_comuni      SMALLINT,
    capoluogo       VARCHAR(100),
    iso_3166_2      VARCHAR(10),
    nuts            VARCHAR(10),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (regione_id, nome)
);

CREATE INDEX idx_province_regione ON province (regione_id);
CREATE INDEX idx_province_sigla   ON province (sigla);
CREATE INDEX idx_province_codice  ON province (codice_istat);

-- ── Tabella comuni ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS comuni (
    id                  SERIAL PRIMARY KEY,
    provincia_id        INTEGER      NOT NULL REFERENCES province(id) ON DELETE CASCADE,
    nome                VARCHAR(200) NOT NULL,
    codice_istat        VARCHAR(10)  NOT NULL UNIQUE,
    codice_catastale    VARCHAR(10)  UNIQUE,
    zona                VARCHAR(100),
    popolazione         INTEGER,
    superficie_kmq      NUMERIC(10,2),
    densita             NUMERIC(10,2),
    cap                 VARCHAR(10),
    prefisso_telefonico VARCHAR(10),
    patrono             VARCHAR(200),
    festa_patronale     VARCHAR(100),
    demonimo            VARCHAR(200),
    etimologia          TEXT,
    il_comune_e         TEXT[],
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_comuni_provincia ON comuni (provincia_id);
CREATE INDEX idx_comuni_codice    ON comuni (codice_istat);
CREATE INDEX idx_comuni_nome      ON comuni (nome);
CREATE INDEX idx_comuni_cap       ON comuni (cap);

-- ── Tabelle array → relazionali ──────────────────────────────────────────────
-- I campi array del JSON diventano tabelle figlie con FK al comune.
-- Ogni tabella ha un tipo (discriminatore) per i campi che condividono struttura.

-- Frazioni e località
CREATE TABLE IF NOT EXISTS comune_frazioni (
    id          SERIAL PRIMARY KEY,
    comune_id   INTEGER      NOT NULL REFERENCES comuni(id) ON DELETE CASCADE,
    nome        VARCHAR(300) NOT NULL,
    ordine      SMALLINT     NOT NULL DEFAULT 0
);

CREATE INDEX idx_frazioni_comune ON comune_frazioni (comune_id);

-- Comuni confinanti
CREATE TABLE IF NOT EXISTS comune_confinanti (
    id          SERIAL PRIMARY KEY,
    comune_id   INTEGER      NOT NULL REFERENCES comuni(id) ON DELETE CASCADE,
    descrizione VARCHAR(500) NOT NULL,
    ordine      SMALLINT     NOT NULL DEFAULT 0
);

CREATE INDEX idx_confinanti_comune ON comune_confinanti (comune_id);

-- Appartenenze (fa_parte_di): comunità montane, parchi, associazioni
CREATE TABLE IF NOT EXISTS comune_appartenenze (
    id          SERIAL PRIMARY KEY,
    comune_id   INTEGER      NOT NULL REFERENCES comuni(id) ON DELETE CASCADE,
    nome        VARCHAR(500) NOT NULL,
    ordine      SMALLINT     NOT NULL DEFAULT 0
);

CREATE INDEX idx_appartenenze_comune ON comune_appartenenze (comune_id);

-- Punti di interesse (musei, chiese, ville, castelli, fontane, teatri, stadi, ecc.)
CREATE TABLE IF NOT EXISTS comune_punti_interesse (
    id          SERIAL PRIMARY KEY,
    comune_id   INTEGER      NOT NULL REFERENCES comuni(id) ON DELETE CASCADE,
    tipo        VARCHAR(50)  NOT NULL,
    nome        VARCHAR(500) NOT NULL,
    ordine      SMALLINT     NOT NULL DEFAULT 0,

    CONSTRAINT chk_poi_tipo CHECK (tipo IN (
        'museo', 'chiesa', 'villa_palazzo', 'castello_fortificazione',
        'fontana', 'giardino_orto_botanico', 'luogo_interesse',
        'teatro', 'stadio'
    ))
);

CREATE INDEX idx_poi_comune ON comune_punti_interesse (comune_id);
CREATE INDEX idx_poi_tipo   ON comune_punti_interesse (tipo);

-- Eventi, feste, sagre
CREATE TABLE IF NOT EXISTS comune_eventi (
    id          SERIAL PRIMARY KEY,
    comune_id   INTEGER      NOT NULL REFERENCES comuni(id) ON DELETE CASCADE,
    nome        VARCHAR(500) NOT NULL,
    ordine      SMALLINT     NOT NULL DEFAULT 0
);

CREATE INDEX idx_eventi_comune ON comune_eventi (comune_id);

-- Gemellaggi
CREATE TABLE IF NOT EXISTS comune_gemellaggi (
    id          SERIAL PRIMARY KEY,
    comune_id   INTEGER      NOT NULL REFERENCES comuni(id) ON DELETE CASCADE,
    citta       VARCHAR(300) NOT NULL,
    ordine      SMALLINT     NOT NULL DEFAULT 0
);

CREATE INDEX idx_gemellaggi_comune ON comune_gemellaggi (comune_id);

-- Cittadini illustri
CREATE TABLE IF NOT EXISTS comune_cittadini_illustri (
    id          SERIAL PRIMARY KEY,
    comune_id   INTEGER      NOT NULL REFERENCES comuni(id) ON DELETE CASCADE,
    nome        VARCHAR(500) NOT NULL,
    ordine      SMALLINT     NOT NULL DEFAULT 0
);

CREATE INDEX idx_cittadini_comune ON comune_cittadini_illustri (comune_id);

-- ── Funzione trigger: aggiorna updated_at ────────────────────────────────────

CREATE OR REPLACE FUNCTION fn_aggiorna_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_regioni_updated_at
    BEFORE UPDATE ON regioni
    FOR EACH ROW EXECUTE FUNCTION fn_aggiorna_updated_at();

CREATE TRIGGER trg_province_updated_at
    BEFORE UPDATE ON province
    FOR EACH ROW EXECUTE FUNCTION fn_aggiorna_updated_at();

CREATE TRIGGER trg_comuni_updated_at
    BEFORE UPDATE ON comuni
    FOR EACH ROW EXECUTE FUNCTION fn_aggiorna_updated_at();

-- ── Funzione: upsert comune con tutti i dati ─────────────────────────────────
-- Inserisce o aggiorna un comune dato codice_istat, gestendo il conflitto.

CREATE OR REPLACE FUNCTION fn_upsert_comune(
    p_codice_istat      VARCHAR,
    p_codice_catastale  VARCHAR,
    p_nome              VARCHAR,
    p_provincia_codice  VARCHAR,
    p_zona              VARCHAR,
    p_popolazione       INTEGER,
    p_superficie_kmq    NUMERIC,
    p_densita           NUMERIC,
    p_cap               VARCHAR,
    p_prefisso          VARCHAR,
    p_patrono           VARCHAR,
    p_festa_patronale   VARCHAR,
    p_demonimo          VARCHAR,
    p_etimologia        TEXT,
    p_il_comune_e       TEXT[]
)
RETURNS INTEGER AS $$
DECLARE
    v_provincia_id INTEGER;
    v_comune_id    INTEGER;
BEGIN
    SELECT id INTO v_provincia_id FROM province WHERE codice_istat = p_provincia_codice;
    IF v_provincia_id IS NULL THEN
        RAISE EXCEPTION 'Provincia con codice_istat % non trovata', p_provincia_codice;
    END IF;

    INSERT INTO comuni (
        provincia_id, nome, codice_istat, codice_catastale, zona,
        popolazione, superficie_kmq, densita, cap, prefisso_telefonico,
        patrono, festa_patronale, demonimo, etimologia, il_comune_e
    ) VALUES (
        v_provincia_id, p_nome, p_codice_istat, p_codice_catastale, p_zona,
        p_popolazione, p_superficie_kmq, p_densita, p_cap, p_prefisso,
        p_patrono, p_festa_patronale, p_demonimo, p_etimologia, p_il_comune_e
    )
    ON CONFLICT (codice_istat) DO UPDATE SET
        nome              = EXCLUDED.nome,
        codice_catastale  = EXCLUDED.codice_catastale,
        zona              = EXCLUDED.zona,
        popolazione       = EXCLUDED.popolazione,
        superficie_kmq    = EXCLUDED.superficie_kmq,
        densita           = EXCLUDED.densita,
        cap               = EXCLUDED.cap,
        prefisso_telefonico = EXCLUDED.prefisso_telefonico,
        patrono           = EXCLUDED.patrono,
        festa_patronale   = EXCLUDED.festa_patronale,
        demonimo          = EXCLUDED.demonimo,
        etimologia        = EXCLUDED.etimologia,
        il_comune_e       = EXCLUDED.il_comune_e
    RETURNING id INTO v_comune_id;

    RETURN v_comune_id;
END;
$$ LANGUAGE plpgsql;

-- ── Funzione: statistiche per regione ────────────────────────────────────────

CREATE OR REPLACE FUNCTION fn_statistiche_regione(p_regione_nome VARCHAR)
RETURNS TABLE (
    regione         VARCHAR,
    tot_province    BIGINT,
    tot_comuni      BIGINT,
    tot_popolazione BIGINT,
    tot_superficie  NUMERIC,
    tot_poi         BIGINT,
    tot_eventi      BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        r.nome::VARCHAR,
        COUNT(DISTINCT p.id),
        COUNT(DISTINCT c.id),
        SUM(c.popolazione)::BIGINT,
        SUM(c.superficie_kmq),
        (SELECT COUNT(*) FROM comune_punti_interesse poi
         JOIN comuni c2 ON poi.comune_id = c2.id
         JOIN province p2 ON c2.provincia_id = p2.id
         WHERE p2.regione_id = r.id),
        (SELECT COUNT(*) FROM comune_eventi ev
         JOIN comuni c3 ON ev.comune_id = c3.id
         JOIN province p3 ON c3.provincia_id = p3.id
         WHERE p3.regione_id = r.id)
    FROM regioni r
    LEFT JOIN province p ON p.regione_id = r.id
    LEFT JOIN comuni c ON c.provincia_id = p.id
    WHERE r.nome = p_regione_nome
    GROUP BY r.id, r.nome;
END;
$$ LANGUAGE plpgsql;

COMMIT;
