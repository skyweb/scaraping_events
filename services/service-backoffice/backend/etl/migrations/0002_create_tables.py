from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('etl', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS etl_runs (
                    id BIGSERIAL PRIMARY KEY,
                    run_type VARCHAR(50) NOT NULL,
                    source VARCHAR(50),
                    status VARCHAR(20) NOT NULL DEFAULT 'running',
                    staging_count INTEGER NOT NULL DEFAULT 0,
                    inserted_count INTEGER NOT NULL DEFAULT 0,
                    updated_count INTEGER NOT NULL DEFAULT 0,
                    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    staging_completed_at TIMESTAMPTZ,
                    upsert_completed_at TIMESTAMPTZ
                );
            """,
            reverse_sql="DROP TABLE IF EXISTS etl_runs;",
        ),
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS etl_errors (
                    id BIGSERIAL PRIMARY KEY,
                    error_type VARCHAR(50) NOT NULL,
                    source VARCHAR(50),
                    json_file VARCHAR(255),
                    error_message TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """,
            reverse_sql="DROP TABLE IF EXISTS etl_errors;",
        ),
    ]
