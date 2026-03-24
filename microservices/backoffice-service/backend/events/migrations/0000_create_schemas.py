"""
Crea gli schemi PostgreSQL custom prima di qualsiasi tabella.

Necessario sia in produzione (se non eseguito da 03-schemas.sql)
che nel database di test creato da Django.
"""
from django.db import migrations


CREATE_SCHEMAS_SQL = """
CREATE SCHEMA IF NOT EXISTS events_data;
CREATE SCHEMA IF NOT EXISTS comuni;
CREATE SCHEMA IF NOT EXISTS comuni_italiani;
CREATE SCHEMA IF NOT EXISTS comuni_istat;
"""

REVERSE_SQL = migrations.RunSQL.noop


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.RunSQL(sql=CREATE_SCHEMAS_SQL, reverse_sql=REVERSE_SQL),
    ]
