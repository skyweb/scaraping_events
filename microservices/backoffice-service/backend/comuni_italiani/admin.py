from django.contrib import admin
from django.db import connection
from unfold.admin import ModelAdmin
from .models import (
    RipartizioneGeografica,
    RegioneItaliana,
    ProvinciaItaliana,
    ComuneItaliano,
)


class RegioneFilter(admin.SimpleListFilter):
    """Filtro per regione nei comuni"""
    title = 'Regione'
    parameter_name = 'regione'

    def lookups(self, request, model_admin):
        with connection.cursor() as cursor:
            cursor.execute('SELECT cod_reg, den_reg FROM comuni_italiani.regioni ORDER BY den_reg')
            return cursor.fetchall()

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(cod_reg=self.value())
        return queryset


class ProvinciaFilter(admin.SimpleListFilter):
    """Filtro per provincia nei comuni"""
    title = 'Provincia'
    parameter_name = 'provincia'

    def lookups(self, request, model_admin):
        with connection.cursor() as cursor:
            cursor.execute('SELECT cod_uts, den_uts FROM comuni_italiani.province ORDER BY den_uts')
            return cursor.fetchall()

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(cod_uts_id=self.value())
        return queryset


@admin.register(ComuneItaliano)
class ComuneItalianoAdmin(ModelAdmin):
    list_display = ['comune', 'cod_uts', 'popolazione']
    search_fields = ['comune']
    list_filter = [RegioneFilter, ProvinciaFilter]
    list_per_page = 50


@admin.register(ProvinciaItaliana)
class ProvinciaItalianaAdmin(ModelAdmin):
    list_display = ['den_uts', 'sigla', 'cod_reg']
    search_fields = ['den_uts', 'sigla']
    list_filter = [RegioneFilter]
    list_per_page = 50
