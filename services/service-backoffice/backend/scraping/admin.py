from django.contrib import admin
from django.db import connection
from unfold.admin import ModelAdmin
from .models import ScrapingCategoria, ScrapingLocation


class CategoriaFilter(admin.SimpleListFilter):
    """Filtro per categoria negli eventi"""
    title = 'Categoria'
    parameter_name = 'categoria'

    def lookups(self, request, model_admin):
        with connection.cursor() as cursor:
            cursor.execute("SELECT categoria, categoria FROM events_data.v_categorie ORDER BY categoria")
            return cursor.fetchall()

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(category__contains=[self.value()])
        return queryset


@admin.register(ScrapingCategoria)
class ScrapingCategoriaAdmin(ModelAdmin):
    list_display = ['categoria', 'count']
    ordering = ['categoria']


@admin.register(ScrapingLocation)
class ScrapingLocationAdmin(ModelAdmin):
    list_display = ['location_name', 'city', 'count']
    search_fields = ['location_name', 'city']
    ordering = ['location_name']
