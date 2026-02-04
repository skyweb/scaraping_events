-- =============================================================================
-- SCHEMA: comuni_italiani - Confini amministrativi ISTAT 01/01/2025
-- =============================================================================
-- NOTA: Le tabelle sono gestite da Django (migrations).
-- Questo file crea solo lo schema e i permessi.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS comuni_italiani;

-- =============================================================================
-- GRANT: Permessi
-- =============================================================================
GRANT ALL PRIVILEGES ON SCHEMA comuni_italiani TO events;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA comuni_italiani TO events;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA comuni_italiani TO events;

-- =============================================================================
-- INDICI CUSTOM (non gestiti da Django)
-- =============================================================================
-- Indice su LOWER(comune) per ricerche case-insensitive
CREATE INDEX IF NOT EXISTS idx_comuni_nome_lower
    ON comuni_italiani.comuni(LOWER(comune));

-- Indice GIN per ricerca su array CAP
CREATE INDEX IF NOT EXISTS idx_comuni_cap
    ON comuni_italiani.comuni USING GIN(cap);
