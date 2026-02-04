-- =============================================================================
-- ESTENSIONE: Colonne aggiuntive per comuni (CAP, codice catastale, popolazione)
-- Fonte: comuni-json (https://github.com/matteocontrini/comuni-json)
-- =============================================================================

-- Aggiungi colonne se non esistono
DO $$
BEGIN
    -- Codice catastale (Agenzia delle Entrate)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'comuni_italiani'
                   AND table_name = 'comuni'
                   AND column_name = 'codice_catastale') THEN
        ALTER TABLE comuni_italiani.comuni ADD COLUMN codice_catastale VARCHAR(4);
    END IF;

    -- CAP (array per comuni multi-CAP)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'comuni_italiani'
                   AND table_name = 'comuni'
                   AND column_name = 'cap') THEN
        ALTER TABLE comuni_italiani.comuni ADD COLUMN cap TEXT[];
    END IF;

    -- Popolazione (censimento)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'comuni_italiani'
                   AND table_name = 'comuni'
                   AND column_name = 'popolazione') THEN
        ALTER TABLE comuni_italiani.comuni ADD COLUMN popolazione INTEGER;
    END IF;
END $$;

-- Indici per le nuove colonne
CREATE INDEX IF NOT EXISTS idx_comuni_catastale ON comuni_italiani.comuni(codice_catastale);
CREATE INDEX IF NOT EXISTS idx_comuni_cap ON comuni_italiani.comuni USING GIN(cap);
CREATE INDEX IF NOT EXISTS idx_comuni_popolazione ON comuni_italiani.comuni(popolazione);

-- Commenti
COMMENT ON COLUMN comuni_italiani.comuni.codice_catastale IS 'Codice catastale Agenzia delle Entrate (es: A001)';
COMMENT ON COLUMN comuni_italiani.comuni.cap IS 'Array di Codici di Avviamento Postale. Comuni grandi hanno più CAP.';
COMMENT ON COLUMN comuni_italiani.comuni.popolazione IS 'Popolazione residente (fonte: censimento ISTAT)';

-- =============================================================================
-- TABELLA STAGING: per import dati JSON comuni
-- =============================================================================
CREATE TABLE IF NOT EXISTS comuni_italiani.comuni_json_staging (
    codice VARCHAR(6) PRIMARY KEY,      -- pro_com_t (chiave di join)
    nome VARCHAR(100),
    codice_catastale VARCHAR(4),
    cap TEXT[],
    popolazione INTEGER
);

GRANT ALL PRIVILEGES ON comuni_italiani.comuni_json_staging TO events;
