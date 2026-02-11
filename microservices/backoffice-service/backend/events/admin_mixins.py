"""
Mixin condiviso tra StagingEventAdmin e ProductionEventAdmin.

Contiene gli 11 metodi di visualizzazione identici tra le due classi,
evitando la duplicazione del codice.
"""
from django.utils.safestring import mark_safe

from .admin_utils import (
    format_date_italian,
    render_category_chips,
    render_clickable_image_url,
    render_clickable_link,
    render_event_status_chip,
    render_image_preview,
    render_image_thumbnail,
    render_json_preview,
)


class EventDisplayMixin:
    """
    Mixin con i metodi di visualizzazione comuni a Staging e Production.

    Fornisce: chip stato, categorie, URL cliccabile, anteprima immagine,
    miniatura, descrizione HTML, JSON colorato, URL immagine, date readonly.
    """

    def event_status_chip(self, obj):
        """Chip colorato per stato temporale: Passato (rosso), In corso (verde), Futuro (blu)."""
        return render_event_status_chip(obj.date_start, obj.date_end)
    event_status_chip.short_description = "Stato"

    def category_list(self, obj):
        """Mostra le categorie come chip blu nella lista e nel dettaglio."""
        return render_category_chips(obj.category)
    category_list.short_description = "Categorie"

    def clickable_url(self, obj):
        """URL sorgente come link cliccabile con icona di apertura esterna."""
        return render_clickable_link(obj.url)
    clickable_url.short_description = "URL Sorgente"

    def image_preview(self, obj):
        """Anteprima dell'immagine nel dettaglio evento (max 100x150px)."""
        return render_image_preview(obj.image_url)
    image_preview.short_description = "Anteprima"

    def image_thumbnail(self, obj):
        """Miniatura cliccabile nella lista. Click apre popup a schermo intero."""
        return render_image_thumbnail(obj.image_url)
    image_thumbnail.short_description = "Immagine"

    def description_preview(self, obj):
        """Renderizza la descrizione come HTML formattato (senza codice sorgente visibile)."""
        if obj.description:
            return mark_safe(obj.description)
        return "-"
    description_preview.short_description = "Anteprima Descrizione (HTML)"

    def json_preview(self, obj):
        """JSON raw_data con sintassi colorata (tema scuro) e pulsante copia."""
        table = getattr(obj, '_meta', None)
        suffix = table.db_table if table else 'event'
        unique_id = f"json-{obj.pk}-{suffix}"
        return render_json_preview(obj.raw_data, unique_id)
    json_preview.short_description = "Raw Data"

    def clickable_image_url(self, obj):
        """URL dell'immagine come link cliccabile con word-break per URL lunghi."""
        return render_clickable_image_url(obj.image_url)
    clickable_image_url.short_description = "URL Immagine"

    def date_start_display(self, obj):
        """Data di inizio in formato italiano dd/mm/yyyy — sola lettura."""
        return format_date_italian(obj.date_start)
    date_start_display.short_description = "Data Inizio"

    def date_start_ro(self, obj):
        """Copia readonly di date_start per il Tab 1 (le date editabili sono nel Tab 3)."""
        return format_date_italian(obj.date_start)
    date_start_ro.short_description = "Data Inizio"

    def date_end_ro(self, obj):
        """Copia readonly di date_end per il Tab 1 (le date editabili sono nel Tab 3)."""
        return format_date_italian(obj.date_end)
    date_end_ro.short_description = "Data Fine"
