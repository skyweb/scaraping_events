from rest_framework import serializers
from .models import ComuniItalianiRawData


class ComuniItalianiRawDataSerializer(serializers.ModelSerializer):
    """Serializer per la risposta (output)"""

    class Meta:
        model = ComuniItalianiRawData
        fields = ['id', 'tipo', 'codice_istat', 'regione', 'provincia', 'comune', 'created_at']


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
        tipo = validated_data['tipo']
        data = validated_data['data']
        fields = self._extract_fields(tipo, data)

        return ComuniItalianiRawData.objects.create(
            tipo=tipo,
            raw_json=data,
            **fields,
        )


class BulkIngestionSerializer(serializers.Serializer):
    """Serializer per l'ingestion bulk di record dello stesso tipo"""
    tipo = serializers.ChoiceField(choices=['regione', 'provincia', 'comune'])
    items = serializers.ListField(child=serializers.DictField(), min_length=1)
