import io
import json
import os
import re

import boto3
from botocore.exceptions import ClientError

from comuni_istat.items import ComuneItem, ProvinciaItem, RegioneItem


def _to_snake_case(nome):
    """Converte un nome in snake_case (minuscolo con underscore).

    - Sostituisce spazi, apostrofi e trattini con underscore
    - Tutto minuscolo
    - Rimuove underscore doppi

    Esempi:
        "Pesaro e Urbino"    → "pesaro_e_urbino"
        "L'Aquila"           → "l_aquila"
        "Valle d'Aosta"      → "valle_d_aosta"
        "Ascoli Piceno"      → "ascoli_piceno"
        "Reggio nell'Emilia" → "reggio_nell_emilia"
    """
    # Sostituisce spazi, apostrofi e trattini con underscore
    result = re.sub(r"[\s'\-]+", "_", nome)
    # Rimuove eventuali underscore doppi
    result = re.sub(r"_+", "_", result)
    # Tutto minuscolo, strip underscore ai bordi
    return result.lower().strip("_")


class JsonExportPipeline:
    """Pipeline che scrive i JSON in modo incrementale durante lo scraping.

    - Regione: scritta subito al ricevimento
    - Provincia: scritta subito al ricevimento
    - Comuni: scritti su disco appena la provincia è completa (incrementale)

    Output:
        data/output/
        ├── 01_piemonte/
        │   ├── piemonte.json
        │   ├── 001_torino/
        │   │   ├── torino.json
        │   │   └── torino_comuni.json
        │   └── ...
        └── ...
    """

    def open_spider(self, spider):
        self.output_dir = os.environ.get(
            "OUTPUT_DIR",
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data",
                "output",
            ),
        )
        os.makedirs(self.output_dir, exist_ok=True)

        # Mappa per risolvere i path: {nome_regione: reg_path}
        self.regioni_path = {}
        # Path provincia su disco: {(regione, provincia): path}
        self.province_path = {}
        # Conteggio atteso comuni per provincia: {(regione, provincia): num_comuni}
        self.expected_comuni = {}
        # Accumula comuni per provincia: {(regione, provincia): [dict, ...]}
        self.comuni = {}
        # Contatori
        self.tot_regioni = 0
        self.tot_province = 0
        self.tot_comuni = 0

    def process_item(self, item, spider):
        if isinstance(item, RegioneItem):
            self._salva_regione(dict(item), spider)
        elif isinstance(item, ProvinciaItem):
            self._salva_provincia(dict(item), spider)
        elif isinstance(item, ComuneItem):
            key = (item["regione"], item["provincia"])
            self.comuni.setdefault(key, []).append(dict(item))
            self.tot_comuni += 1
            # Scrivi subito se la provincia è completa
            expected = self.expected_comuni.get(key)
            if expected and len(self.comuni[key]) >= expected:
                self._salva_comuni_provincia(key, spider)
        return item

    def _salva_regione(self, data, spider):
        """Scrive il JSON della regione subito su disco."""
        nome = data.get("nome", "")
        codice = data.get("codice_istat", "00")
        reg_snake = _to_snake_case(nome)
        reg_folder = f"{codice}_{reg_snake}"
        reg_path = os.path.join(self.output_dir, reg_folder)
        os.makedirs(reg_path, exist_ok=True)

        # Salva path per le province
        self.regioni_path[nome] = reg_path

        # Scrive JSON regione
        reg_file = os.path.join(reg_path, f"{reg_snake}.json")
        self._write_json(reg_file, data)
        self.tot_regioni += 1
        spider.logger.info(f"[REGIONE] {nome} → {reg_folder}/")

    def _salva_provincia(self, data, spider):
        """Scrive il JSON della provincia subito su disco."""
        nome = data.get("nome", "")
        regione = data.get("regione", "")
        codice = data.get("codice_istat", "000")
        prov_snake = _to_snake_case(nome)
        prov_folder = f"{codice}_{prov_snake}"

        reg_path = self.regioni_path.get(regione, self.output_dir)
        prov_path = os.path.join(reg_path, prov_folder)
        os.makedirs(prov_path, exist_ok=True)

        # Salva path e conteggio atteso per la scrittura incrementale dei comuni
        key = (regione, nome)
        self.province_path[key] = prov_path
        num_comuni = data.get("num_comuni")
        if num_comuni:
            self.expected_comuni[key] = int(num_comuni)

        # Scrive JSON provincia
        prov_file = os.path.join(prov_path, f"{prov_snake}.json")
        self._write_json(prov_file, data)
        self.tot_province += 1
        spider.logger.info(f"  [PROVINCIA] {regione} → {nome}")

    def _salva_comuni_provincia(self, key, spider):
        """Scrive il file _comuni.json per una provincia e libera la memoria."""
        regione, provincia = key
        prov_path = self.province_path.get(key)

        if not prov_path:
            # Fallback: ricostruisce il path cercando la cartella su disco
            reg_path = self.regioni_path.get(regione, self.output_dir)
            prov_snake = _to_snake_case(provincia)
            prov_dirs = [
                d for d in os.listdir(reg_path)
                if d.endswith(f"_{prov_snake}") and os.path.isdir(os.path.join(reg_path, d))
            ]
            if prov_dirs:
                prov_path = os.path.join(reg_path, prov_dirs[0])
            else:
                prov_path = os.path.join(reg_path, f"000_{prov_snake}")
                os.makedirs(prov_path, exist_ok=True)

        prov_snake = _to_snake_case(provincia)
        comuni_file = os.path.join(prov_path, f"{prov_snake}_comuni.json")
        self._write_json(comuni_file, self.comuni[key])

        count = len(self.comuni[key])
        del self.comuni[key]
        spider.logger.info(f"    [COMUNI] {regione}/{provincia}: {count} comuni scritti")

    def close_spider(self, spider):
        """Scrive eventuali comuni rimasti (safety net) e log finale."""
        # Scrivi province incomplete rimaste in memoria
        remaining = list(self.comuni.keys())
        for key in remaining:
            spider.logger.warning(
                f"    [COMUNI] {key[0]}/{key[1]}: provincia incompleta, "
                f"{len(self.comuni[key])}/{self.expected_comuni.get(key, '?')} comuni"
            )
            self._salva_comuni_provincia(key, spider)

        spider.logger.info(
            f"Scraping completato: "
            f"{self.tot_regioni} regioni, {self.tot_province} province, "
            f"{self.tot_comuni} comuni → {self.output_dir}"
        )

    @staticmethod
    def _write_json(filepath, data):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


class MinioExportPipeline:
    """Pipeline che scrive i JSON su MinIO (S3-compatible) invece che su disco locale.

    Stessa struttura gerarchica di JsonExportPipeline:
        comuni-italiani/
        ├── 01_piemonte/
        │   ├── piemonte.json
        │   ├── 001_torino/
        │   │   ├── torino.json
        │   │   └── torino_comuni.json

    Env vars richieste:
        MINIO_ENDPOINT     — es. minio:9000
        MINIO_ACCESS_KEY   — access key (default: minioadmin)
        MINIO_SECRET_KEY   — secret key
        MINIO_BUCKET       — bucket name (default: comuni-italiani)
        MINIO_USE_SSL      — "true"/"false" (default: false)
    """

    def open_spider(self, spider):
        endpoint = os.environ.get("MINIO_ENDPOINT", "minio:9000")
        access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
        secret_key = os.environ.get("MINIO_SECRET_KEY", "")
        use_ssl = os.environ.get("MINIO_USE_SSL", "false").lower() == "true"
        scheme = "https" if use_ssl else "http"

        self.bucket = os.environ.get("MINIO_BUCKET", "comuni-italiani")
        self.prefix = os.environ.get("MINIO_PREFIX", "")  # sottocartella opzionale

        self.s3 = boto3.client(
            "s3",
            endpoint_url=f"{scheme}://{endpoint}",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

        # Crea il bucket se non esiste
        try:
            self.s3.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.s3.create_bucket(Bucket=self.bucket)
            spider.logger.info(f"Bucket '{self.bucket}' creato su MinIO")

        # Stato interno (come JsonExportPipeline)
        self.regioni_path = {}
        self.province_path = {}
        self.expected_comuni = {}
        self.comuni = {}
        self.tot_regioni = 0
        self.tot_province = 0
        self.tot_comuni = 0

    def process_item(self, item, spider):
        if isinstance(item, RegioneItem):
            self._salva_regione(dict(item), spider)
        elif isinstance(item, ProvinciaItem):
            self._salva_provincia(dict(item), spider)
        elif isinstance(item, ComuneItem):
            key = (item["regione"], item["provincia"])
            self.comuni.setdefault(key, []).append(dict(item))
            self.tot_comuni += 1
            expected = self.expected_comuni.get(key)
            if expected and len(self.comuni[key]) >= expected:
                self._salva_comuni_provincia(key, spider)
        return item

    def _s3_key(self, *parts):
        """Costruisce la chiave S3 con eventuale prefisso."""
        segments = [self.prefix] + list(parts) if self.prefix else list(parts)
        return "/".join(s for s in segments if s)

    def _salva_regione(self, data, spider):
        nome = data.get("nome", "")
        codice = data.get("codice_istat", "00")
        reg_snake = _to_snake_case(nome)
        reg_folder = f"{codice}_{reg_snake}"

        self.regioni_path[nome] = reg_folder

        key = self._s3_key(reg_folder, f"{reg_snake}.json")
        self._upload_json(key, data)
        self.tot_regioni += 1
        spider.logger.info(f"[REGIONE] {nome} → s3://{self.bucket}/{key}")

    def _salva_provincia(self, data, spider):
        nome = data.get("nome", "")
        regione = data.get("regione", "")
        codice = data.get("codice_istat", "000")
        prov_snake = _to_snake_case(nome)
        prov_folder = f"{codice}_{prov_snake}"

        reg_folder = self.regioni_path.get(regione, "")
        prov_path = f"{reg_folder}/{prov_folder}" if reg_folder else prov_folder

        key_tuple = (regione, nome)
        self.province_path[key_tuple] = prov_path
        num_comuni = data.get("num_comuni")
        if num_comuni:
            self.expected_comuni[key_tuple] = int(num_comuni)

        key = self._s3_key(prov_path, f"{prov_snake}.json")
        self._upload_json(key, data)
        self.tot_province += 1
        spider.logger.info(f"  [PROVINCIA] {regione} → {nome}")

    def _salva_comuni_provincia(self, key_tuple, spider):
        regione, provincia = key_tuple
        prov_path = self.province_path.get(key_tuple, "")
        prov_snake = _to_snake_case(provincia)

        if not prov_path:
            reg_folder = self.regioni_path.get(regione, "")
            prov_path = f"{reg_folder}/000_{prov_snake}" if reg_folder else f"000_{prov_snake}"

        s3_key = self._s3_key(prov_path, f"{prov_snake}_comuni.json")
        self._upload_json(s3_key, self.comuni[key_tuple])

        count = len(self.comuni[key_tuple])
        del self.comuni[key_tuple]
        spider.logger.info(f"    [COMUNI] {regione}/{provincia}: {count} comuni → MinIO")

    def close_spider(self, spider):
        remaining = list(self.comuni.keys())
        for key in remaining:
            spider.logger.warning(
                f"    [COMUNI] {key[0]}/{key[1]}: provincia incompleta, "
                f"{len(self.comuni[key])}/{self.expected_comuni.get(key, '?')} comuni"
            )
            self._salva_comuni_provincia(key, spider)

        spider.logger.info(
            f"Scraping completato (MinIO): "
            f"{self.tot_regioni} regioni, {self.tot_province} province, "
            f"{self.tot_comuni} comuni → s3://{self.bucket}/"
        )

    def _upload_json(self, key, data):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=io.BytesIO(body),
            ContentType="application/json",
        )
