-- =============================================================================
-- PERMESSI: Grant privileges allo user events
-- =============================================================================
GRANT ALL PRIVILEGES ON SCHEMA events_data TO events;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA events_data TO events;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA events_data TO events;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA events_data TO events;
