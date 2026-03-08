import os
import subprocess
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connection

class Command(BaseCommand):
    help = 'Import ISTAT boundaries (shapefiles) into PostGIS'

    def handle(self, *args, **options):
        # 1. Configuration & Paths
        base_dir = str(settings.BASE_DIR)
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        data_dir = os.path.join(base_dir, 'fixtures', 'confini_istat', 'Limiti01012026')

        # SQL schema file is in the app data directory
        sql_schema_file = os.path.join(app_dir, 'data', 'comuni-schema.sql')

        if not os.path.exists(data_dir):
            raise CommandError(f"Data directory not found: {data_dir}")
        if not os.path.exists(sql_schema_file):
            raise CommandError(f"SQL schema file not found: {sql_schema_file}")

        # Check for ogr2ogr
        if subprocess.call(['which', 'ogr2ogr'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
            raise CommandError("ogr2ogr not found. Please install gdal-bin.")

        # Database credentials from Django settings
        db_conf = settings.DATABASES['default']
        db_name = db_conf['NAME']
        db_user = db_conf['USER']
        db_password = db_conf['PASSWORD']
        db_host = db_conf['HOST']
        db_port = db_conf['PORT']

        pg_conn = f"PG:host={db_host} port={db_port} dbname={db_name} user={db_user} password={db_password}"

        # 2. Create Schema
        self.stdout.write(self.style.WARNING(f"[1/4] Creating schema from {sql_schema_file}..."))
        with open(sql_schema_file, 'r') as f:
            sql_schema = f.read()

        with connection.cursor() as cursor:
            cursor.execute(sql_schema)
        self.stdout.write(self.style.SUCCESS("  Schema created"))

        # 3. Import Shapefiles
        self.stdout.write(self.style.WARNING("\n[2/4] Importing shapefiles with ogr2ogr..."))

        shapefiles = [
            ("RipGeo01012026/RipGeo01012026_WGS84.shp", "ripartizioni_import", "Ripartizioni"),
            ("Reg01012026/Reg01012026_WGS84.shp", "regioni_import", "Regioni"),
            ("ProvCM01012026/ProvCM01012026_WGS84.shp", "province_import", "Province"),
            ("Com01012026/Com01012026_WGS84.shp", "comuni_import", "Comuni"),
        ]

        for shp_subpath, table_name, label in shapefiles:
            shp_path = os.path.join(data_dir, shp_subpath)
            self.stdout.write(f"  Importing {label}...")

            cmd = [
                'ogr2ogr',
                '-f', 'PostgreSQL', pg_conn,
                shp_path,
                '-nln', f'comuni_istat.{table_name}',
                '-nlt', 'PROMOTE_TO_MULTI',
                '-t_srs', 'EPSG:4326',
                '-lco', 'GEOMETRY_NAME=geom',
                '-lco', 'PRECISION=NO',
                '-overwrite',
                '--config', 'PG_USE_COPY', 'YES'
            ]

            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if process.returncode != 0:
                raise CommandError(f"ogr2ogr failed for {label}: {process.stderr}")

            self.stdout.write(self.style.SUCCESS(f"  {label} imported"))

        # 4. Transfer to final tables
        self.stdout.write(self.style.WARNING("\n[3/4] Transferring data to final tables..."))

        transfer_sql = """
        -- Svuota tabelle finali (nell'ordine corretto per FK)
        TRUNCATE comuni_istat.comuni CASCADE;
        TRUNCATE comuni_istat.province CASCADE;
        TRUNCATE comuni_istat.regioni CASCADE;
        TRUNCATE comuni_istat.ripartizioni CASCADE;

        -- Ripartizioni
        INSERT INTO comuni_istat.ripartizioni (cod_rip, den_rip, geom, shape_area, shape_length)
        SELECT cod_rip, den_rip, geom, shape_area, shape_leng
        FROM comuni_istat.ripartizioni_import;

        -- Regioni
        INSERT INTO comuni_istat.regioni (cod_rip, cod_reg, den_reg, geom, shape_area, shape_length)
        SELECT cod_rip, cod_reg, den_reg, geom, shape_area, shape_leng
        FROM comuni_istat.regioni_import;

        -- Province
        INSERT INTO comuni_istat.province (cod_rip, cod_reg, cod_prov, cod_cm, cod_uts, den_prov, den_cm, den_uts, sigla, tipo_uts, geom, shape_area, shape_length)
        SELECT cod_rip, cod_reg, cod_prov, cod_cm, cod_uts, den_prov, den_cm, den_uts, sigla, tipo_uts, geom, shape_area, shape_leng
        FROM comuni_istat.province_import;

        -- Comuni (con calcolo centroide)
        INSERT INTO comuni_istat.comuni (cod_rip, cod_reg, cod_prov, cod_cm, cod_uts, pro_com, pro_com_t, comune, comune_a, cc_uts, geom, centroid, shape_area, shape_length)
        SELECT cod_rip, cod_reg, cod_prov, cod_cm, cod_uts, pro_com, pro_com_t, comune, comune_a, cc_uts, geom, ST_Centroid(geom), shape_area, shape_leng
        FROM comuni_istat.comuni_import;

        -- Elimina tabelle temporanee
        DROP TABLE IF EXISTS comuni_istat.ripartizioni_import;
        DROP TABLE IF EXISTS comuni_istat.regioni_import;
        DROP TABLE IF EXISTS comuni_istat.province_import;
        DROP TABLE IF EXISTS comuni_istat.comuni_import;
        """

        with connection.cursor() as cursor:
            cursor.execute(transfer_sql)

        self.stdout.write(self.style.SUCCESS("  Data transferred and temp tables dropped"))

        # 5. Verification
        self.stdout.write(self.style.WARNING("\n[4/4] Verifying import..."))
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM comuni_istat.comuni")
            count = cursor.fetchone()[0]
            self.stdout.write(f"  Total Comuni: {count}")

            cursor.execute("SELECT COUNT(*) FROM comuni_istat.province")
            count = cursor.fetchone()[0]
            self.stdout.write(f"  Total Province: {count}")

        self.stdout.write(self.style.SUCCESS("\nImport completed successfully!"))
