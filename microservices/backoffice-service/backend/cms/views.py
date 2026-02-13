import uuid

from django.contrib.admin.views.decorators import staff_member_required
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from rest_framework import viewsets, mixins
from rest_framework.permissions import AllowAny

from .models import PaginaCitta
from .serializers import PaginaCittaListSerializer, PaginaCittaDetailSerializer


class PaginaCittaViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """API readonly per le pagine città (pubblico, senza autenticazione)."""
    permission_classes = [AllowAny]
    authentication_classes = []
    lookup_field = 'slug'
    pagination_class = None

    def get_queryset(self):
        return PaginaCitta.objects.filter(is_attiva=True).prefetch_related(
            'navigazione', 'sezioni__articoli'
        )

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PaginaCittaDetailSerializer
        return PaginaCittaListSerializer


@require_POST
@staff_member_required
def upload_image(request):
    """Upload immagine da admin CMS. Salva il file e restituisce l'URL."""
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'File richiesto'}, status=400)

    file = request.FILES['file']
    ext = file.name.rsplit('.', 1)[-1].lower() if '.' in file.name else 'jpg'
    filename = f'cms/articoli/{uuid.uuid4().hex[:12]}.{ext}'
    path = default_storage.save(filename, file)
    return JsonResponse({'url': f'/media/{path}'})
