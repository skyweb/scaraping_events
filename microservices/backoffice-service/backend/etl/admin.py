from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import EtlRun, EtlError


@admin.register(EtlRun)
class EtlRunAdmin(ModelAdmin):
    list_display = ['run_type', 'source', 'status', 'staging_count', 'inserted_count', 'updated_count', 'started_at']
    list_filter = ['status', 'run_type', 'source']
    ordering = ['-started_at']
    list_per_page = 25


@admin.register(EtlError)
class EtlErrorAdmin(ModelAdmin):
    list_display = ['error_type', 'source', 'json_file', 'created_at']
    list_filter = ['error_type', 'source']
    search_fields = ['error_message', 'json_file']
    ordering = ['-created_at']
    list_per_page = 25
