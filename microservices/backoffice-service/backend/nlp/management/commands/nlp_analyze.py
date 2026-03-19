"""
Management command per analisi NLP degli staging events.

Analizza le description con spaCy ed estrae entità strutturate
(persone, organizzazioni, luoghi, date, contatti, prezzi).
I risultati vengono salvati in raw_data.nlp.

Utilizzo:
    # Analizza tutti gli eventi senza nlp
    python manage.py nlp_analyze

    # Analizza solo un source specifico
    python manage.py nlp_analyze --source love_vda

    # Forza ri-analisi anche se già analizzato
    python manage.py nlp_analyze --force

    # Limita il numero di eventi
    python manage.py nlp_analyze --limit 100

    # Dry-run: mostra risultati senza salvare
    python manage.py nlp_analyze --dry-run --limit 5
"""

import json
import time

from django.core.management.base import BaseCommand

from events.models import StagingEvent
from nlp.extractor import analyze_staging_event


class Command(BaseCommand):
    help = "Analizza staging events con spaCy NLP ed estrae entità strutturate"

    def add_arguments(self, parser):
        parser.add_argument("--source", type=str, help="Filtra per source (spider name)")
        parser.add_argument("--limit", type=int, default=0, help="Numero massimo di eventi (0=tutti)")
        parser.add_argument("--force", action="store_true", help="Ri-analizza anche eventi già processati")
        parser.add_argument("--dry-run", action="store_true", help="Mostra risultati senza salvare")

    def handle(self, *args, **options):
        source = options["source"]
        limit = options["limit"]
        force = options["force"]
        dry_run = options["dry_run"]

        qs = StagingEvent.objects.filter(description__isnull=False).exclude(description="")

        if source:
            qs = qs.filter(source=source)

        if not force:
            # Escludi eventi che hanno già nlp in raw_data
            qs = qs.exclude(raw_data__has_key="nlp")

        qs = qs.order_by("-created_at")

        if limit > 0:
            qs = qs[:limit]

        total = qs.count() if limit == 0 else min(limit, qs.count())
        self.stdout.write(f"Analisi NLP di {total} eventi" + (" (dry-run)" if dry_run else ""))

        processed = 0
        enriched = 0
        errors = 0
        start = time.monotonic()

        for event in qs.iterator():
            try:
                entities = analyze_staging_event(event)

                if entities:
                    enriched += 1

                    if dry_run:
                        self.stdout.write(
                            f"\n  [{event.source}] {event.title[:60]}"
                        )
                        for key, values in entities.items():
                            self.stdout.write(f"    {key}: {values}")
                    else:
                        # Salva in raw_data.nlp
                        raw = event.raw_data or {}
                        raw["nlp"] = entities
                        StagingEvent.objects.filter(pk=event.pk).update(raw_data=raw)

                processed += 1

                if processed % 50 == 0:
                    elapsed = time.monotonic() - start
                    rate = processed / elapsed if elapsed > 0 else 0
                    self.stdout.write(f"  ... {processed}/{total} ({rate:.1f} evt/s, {enriched} arricchiti)")

            except Exception as e:
                errors += 1
                self.stderr.write(f"  Errore [{event.pk}] {event.title[:40]}: {e}")

        elapsed = time.monotonic() - start
        self.stdout.write(self.style.SUCCESS(
            f"\nCompletato: {processed} analizzati, {enriched} arricchiti, "
            f"{errors} errori in {elapsed:.1f}s"
        ))
