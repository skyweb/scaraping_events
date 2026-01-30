from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import RangeDateFilter
from .models import ProductionEvent, StagingEvent, EtlRun, EtlError


@admin.register(ProductionEvent)
class ProductionEventAdmin(ModelAdmin):
    list_display = ['title', 'city', 'source', 'date_start', 'date_end', 'is_active']
    list_filter = [
        'is_active',
        'city',
        'source',
        ('date_start', RangeDateFilter),
    ]
    list_filter_submit = True
    search_fields = ['title', 'description', 'location_name']
    readonly_fields = ['uuid', 'content_hash', 'created_at', 'updated_at', 'scraped_at']
    ordering = ['-date_start']
    list_per_page = 25

    fieldsets = (
        ('Informazioni Evento', {
            'fields': (
                'title',
                ('source', 'uuid', 'content_hash'),  # 3 campi affiancati
                'url',
            ),
            'classes': ['tab'],
        }),
        ('Contenuto', {
            'fields': (
                'description',
                'category',
                'image_url',
            ),
            'classes': ['tab'],
        }),
        ('Luogo', {
            'fields': (
                'city',
                ('location_name', 'location_address'),  # affiancati
            ),
            'classes': ['tab'],
        }),
        ('Date e Orari', {
            'fields': (
                ('date_start', 'date_end'),      # date affiancate
                ('time_start', 'time_end'),      # orari affiancati
                'time_info',
                ('schedule', 'weekdays'),        # affiancati
            ),
            'classes': ['tab'],
        }),
        ('Info Aggiuntive', {
            'fields': (
                ('price', 'website'),            # affiancati
                'raw_data',
            ),
            'classes': ['tab'],
        }),
        ('Stato', {
            'fields': (
                'is_active',
                ('scraped_at', 'created_at', 'updated_at'),  # 3 timestamp affiancati
            ),
            'classes': ['tab'],
        }),
    )


@admin.register(StagingEvent)
class StagingEventAdmin(ModelAdmin):
    list_display = ['title', 'city', 'source', 'loaded_at']
    list_filter = ['city', 'source']
    search_fields = ['title', 'description']
    readonly_fields = ['loaded_at']
    list_per_page = 25

    fieldsets = (
        # Tab 1: Informazioni principali
        ('Informazioni Evento', {
            'fields': (
                'title',
                ('source', 'uuid'),           # source e uuid affiancati
                ('city', 'location_name'),    # city e location_name affiancati
                'location_address',
                'url',
            ),
            'classes': ['tab'],
        }),
        # Tab 2: Contenuto
        ('Contenuto', {
            'fields': (
                'description',
                'category',
                'image_url',
                ('price', 'website'),         # price e website affiancati
            ),
            'classes': ['tab'],
        }),
        # Tab 3: Date e orari
        ('Date e Orari', {
            'fields': (
                ('date_start', 'date_end'),   # date affiancate
                ('time_start', 'time_end'),   # orari affiancati
                'time_info',
                ('schedule', 'weekdays'),     # schedule e weekdays affiancati
            ),
            'classes': ['tab'],
        }),
        # Tab 4: Dati tecnici
        ('Dati Tecnici', {
            'fields': (
                'content_hash',
                'raw_data',
                ('scraped_at', 'loaded_at'),  # timestamp affiancati
            ),
            'classes': ['tab'],
        }),
    )


@admin.register(EtlRun)
class EtlRunAdmin(ModelAdmin):
    list_display = ['run_type', 'source', 'status', 'staging_count', 'inserted_count', 'updated_count', 'started_at']
    list_filter = ['run_type', 'source', 'status']
    readonly_fields = ['started_at', 'staging_completed_at', 'upsert_completed_at']
    ordering = ['-started_at']
    list_per_page = 25


@admin.register(EtlError)
class EtlErrorAdmin(ModelAdmin):
    list_display = ['error_type', 'source', 'json_file', 'created_at']
    list_filter = ['error_type', 'source']
    search_fields = ['error_message', 'json_file']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    list_per_page = 25
