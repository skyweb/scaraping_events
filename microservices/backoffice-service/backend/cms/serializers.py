from rest_framework import serializers

from .models import PaginaCitta, TabNavigazione, SezionePagina, ArticoloSezione, SezioneEventi


class TabNavigazioneSerializer(serializers.ModelSerializer):
    class Meta:
        model = TabNavigazione
        fields = ['label', 'url']


class ArticoloSezioneSerializer(serializers.ModelSerializer):
    immagine = serializers.SerializerMethodField()

    class Meta:
        model = ArticoloSezione
        fields = ['titolo', 'immagine', 'categoria', 'colore_categoria', 'url']

    def get_immagine(self, obj):
        return obj.immagine_finale


def _staging_event_to_articolo(ev):
    """Converte un StagingEvent nel formato articolo CMS."""
    return {
        'titolo': ev.title,
        'immagine': ev.image_url or '',
        'categoria': ev.category[0] if ev.category else '',
        'colore_categoria': 'red',
        'url': ev.url or '',
    }


def _serialize_sezione_pagina(sezione):
    """Serializza una SezionePagina includendo articoli manuali + staging events."""
    # Articoli manuali
    articoli_manuali = list(ArticoloSezioneSerializer(sezione.articoli.all(), many=True).data)

    # Staging events collegati
    articoli_eventi = [
        _staging_event_to_articolo(ei.evento)
        for ei in sezione.eventi.select_related('evento').all()
    ]

    return {
        'titolo': sezione.titolo,
        'colore': sezione.colore,
        'link_vedi_tutti': sezione.link_vedi_tutti,
        'articoli': articoli_manuali + articoli_eventi,
    }


class SezionePaginaSerializer(serializers.ModelSerializer):
    articoli = ArticoloSezioneSerializer(many=True, read_only=True)

    class Meta:
        model = SezionePagina
        fields = ['titolo', 'colore', 'link_vedi_tutti', 'articoli']


class PaginaCittaListSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaginaCitta
        fields = ['nome', 'slug']


class PaginaCittaDetailSerializer(serializers.ModelSerializer):
    navigazione = TabNavigazioneSerializer(many=True, read_only=True)
    sezioni = serializers.SerializerMethodField()

    class Meta:
        model = PaginaCitta
        fields = ['nome', 'slug', 'navigazione', 'sezioni']

    def get_sezioni(self, obj):
        """Restituisce sezioni manuali + sezioni eventi attive, ordinate per ordine."""
        # Sezioni manuali (con articoli + staging events)
        sezioni_manuali = list(
            obj.sezioni.filter(is_attiva=True).prefetch_related('articoli', 'eventi__evento')
        )
        # Sezioni eventi dedicate
        sezioni_eventi = list(
            obj.sezioni_eventi.filter(is_attiva=True).prefetch_related('eventi__evento')
        )

        # Unisci e ordina per campo ordine
        combined = sorted(
            [(s, 'manuale') for s in sezioni_manuali] +
            [(s, 'eventi') for s in sezioni_eventi],
            key=lambda x: x[0].ordine,
        )

        result = []
        for sezione, tipo in combined:
            if tipo == 'manuale':
                result.append(_serialize_sezione_pagina(sezione))
            else:
                articoli = [
                    _staging_event_to_articolo(es.evento)
                    for es in sezione.eventi.select_related('evento').all()
                ]
                result.append({
                    'titolo': sezione.titolo,
                    'colore': sezione.colore,
                    'link_vedi_tutti': sezione.link_vedi_tutti,
                    'articoli': articoli,
                })
        return result
