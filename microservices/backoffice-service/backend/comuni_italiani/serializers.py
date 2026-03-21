from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from .models import ComuniIstatRawData


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Record ISTAT",
            value={
                "id": 1,
                "tipo": "comune",
                "codice_istat": "015146",
                "regione": "Lombardia",
                "provincia": "Milano",
                "comune": "Milano",
                "created_at": "2026-03-20T10:00:00Z",
            },
            response_only=True,
        ),
    ]
)
class ComuniIstatRawDataSerializer(serializers.ModelSerializer):
    """Serializer per la risposta (output)"""

    class Meta:
        model = ComuniIstatRawData
        fields = ['id', 'tipo', 'codice_istat', 'regione', 'provincia', 'comune', 'created_at']


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Comune',
            value={
                'tipo': 'comune',
                'data': {
                    'codice_istat': '015146',
                    'nome': 'Milano',
                    'regione': 'Lombardia',
                    'provincia': 'Milano',
                    'popolazione': 1396059,
                    'superficie_kmq': 181.67,
                },
            },
            request_only=True,
        ),
        OpenApiExample(
            'Regione',
            value={
                'tipo': 'regione',
                'data': {
                    'codice_istat': '03',
                    'nome': 'Lombardia',
                    'popolazione': 10027602,
                    'num_province': 12,
                    'num_comuni': 1506,
                },
            },
            request_only=True,
        ),
    ]
)
class IngestionSerializer(serializers.Serializer):
    """Serializer per l'ingestion di un singolo record"""
    tipo = serializers.ChoiceField(choices=['regione', 'provincia', 'comune'])
    data = serializers.DictField()

    def _extract_fields(self, tipo, data):
        """Estrae i campi chiave dal JSON in base al tipo"""
        codice_istat = data.get('codice_istat', '')

        if tipo == 'regione':
            return {
                'codice_istat': codice_istat,
                'regione': data.get('nome', ''),
                'provincia': None,
                'comune': None,
            }
        elif tipo == 'provincia':
            return {
                'codice_istat': codice_istat,
                'regione': data.get('regione', ''),
                'provincia': data.get('nome', ''),
                'comune': None,
            }
        else:  # comune
            return {
                'codice_istat': codice_istat,
                'regione': data.get('regione', ''),
                'provincia': data.get('provincia', ''),
                'comune': data.get('nome', ''),
            }

    def create(self, validated_data):
        """Crea un record ComuniIstatRawData estraendo i campi chiave dal JSON."""
        tipo = validated_data['tipo']
        data = validated_data['data']
        fields = self._extract_fields(tipo, data)

        return ComuniIstatRawData.objects.create(
            tipo=tipo,
            raw_json=data,
            **fields,
        )


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Bulk comuni',
            value={
                'tipo': 'comune',
                'items': [
                    {
                        'codice_istat': '015146',
                        'nome': 'Milano',
                        'regione': 'Lombardia',
                        'provincia': 'Milano',
                    },
                    {
                        'codice_istat': '015146',
                        'nome': 'Monza',
                        'regione': 'Lombardia',
                        'provincia': 'Monza e della Brianza',
                    },
                ],
            },
            request_only=True,
        ),
    ]
)
class BulkIngestionSerializer(serializers.Serializer):
    """Serializer per l'ingestion bulk di record dello stesso tipo"""
    tipo = serializers.ChoiceField(choices=['regione', 'provincia', 'comune'])
    items = serializers.ListField(child=serializers.DictField(), min_length=1)
