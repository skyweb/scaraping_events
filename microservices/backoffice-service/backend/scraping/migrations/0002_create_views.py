from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scraping', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE VIEW events_data.v_categorie AS
                SELECT
                    unnest(category) AS categoria,
                    COUNT(*) AS count
                FROM events_data.staging_events
                WHERE category IS NOT NULL
                GROUP BY unnest(category)
                ORDER BY categoria;
            """,
            reverse_sql="DROP VIEW IF EXISTS events_data.v_categorie;",
        ),
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE VIEW events_data.v_locations AS
                SELECT
                    COALESCE(location_name, '') || '|||' || COALESCE(city, '') AS location_name,
                    city,
                    COUNT(*) AS count
                FROM events_data.staging_events
                WHERE location_name IS NOT NULL
                GROUP BY location_name, city
                ORDER BY location_name;
            """,
            reverse_sql="DROP VIEW IF EXISTS events_data.v_locations;",
        ),
    ]
