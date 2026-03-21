from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from .models import ComuniIstatRawData
from .serializers import (
    IngestionSerializer,
    BulkIngestionSerializer,
    ComuniIstatRawDataSerializer,
)


class IngestionView(APIView):
    """Endpoint per ingestione di un singolo record (regione/provincia/comune)"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=IngestionSerializer,
        responses={201: ComuniIstatRawDataSerializer},
        summary="Ingestione singolo record (regione/provincia/comune)",
        tags=["Comuni ISTAT Ingestion"],
    )
    def post(self, request):
        """Riceve e salva un singolo record di scraping (regione/provincia/comune)."""
        serializer = IngestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            ComuniIstatRawDataSerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )


class BulkIngestionView(APIView):
    """Endpoint per ingestione bulk di record dello stesso tipo"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=BulkIngestionSerializer,
        responses={201: dict},
        summary="Ingestione bulk record dello stesso tipo",
        tags=["Comuni ISTAT Ingestion"],
    )
    def post(self, request):
        """Riceve e salva in batch una lista di record dello stesso tipo."""
        serializer = BulkIngestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tipo = serializer.validated_data['tipo']
        items = serializer.validated_data['items']

        # Prepara gli oggetti in batch
        ingestion_ser = IngestionSerializer()
        objects_to_create = []
        for item_data in items:
            fields = ingestion_ser._extract_fields(tipo, item_data)
            objects_to_create.append(
                ComuniIstatRawData(
                    tipo=tipo,
                    raw_json=item_data,
                    **fields,
                )
            )

        created = ComuniIstatRawData.objects.bulk_create(objects_to_create)

        return Response(
            {'created': len(created), 'tipo': tipo},
            status=status.HTTP_201_CREATED,
        )
