import json

from django.contrib import admin
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from .models import EtlRun, EtlError, TraceLog


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


@admin.register(TraceLog)
class TraceLogAdmin(ModelAdmin):
    list_display = ['trace_id_short', 'service', 'operation', 'level_badge', 'message_short', 'created_at']
    list_filter = ['level', 'service', 'operation']
    search_fields = ['trace_id', 'message', 'operation']
    ordering = ['-created_at']
    list_per_page = 50
    readonly_fields = ['trace_id', 'span_id', 'parent_span_id', 'service', 'operation', 'level', 'message', 'metadata_pretty', 'created_at', 'trace_timeline']

    fieldsets = (
        ('Trace Context', {
            'fields': ('trace_id', 'span_id', 'parent_span_id'),
        }),
        ('Evento', {
            'fields': ('service', 'operation', 'level', 'message', 'metadata_pretty', 'created_at'),
        }),
        ('Timeline completa', {
            'fields': ('trace_timeline',),
            'description': 'Tutti gli step registrati per questo trace_id',
        }),
    )

    def trace_id_short(self, obj):
        return obj.trace_id[:12] + '...'
    trace_id_short.short_description = 'Trace ID'

    def message_short(self, obj):
        if not obj.message:
            return '-'
        return obj.message[:80] + ('...' if len(obj.message) > 80 else '')
    message_short.short_description = 'Messaggio'

    def level_badge(self, obj):
        colors = {
            'info': '#3b82f6',
            'warning': '#f59e0b',
            'error': '#ef4444',
        }
        color = colors.get(obj.level, '#6b7280')
        return mark_safe(
            f'<span style="background:{color};color:#fff;padding:2px 8px;'
            f'border-radius:4px;font-size:11px;font-weight:600;">'
            f'{obj.level.upper()}</span>'
        )
    level_badge.short_description = 'Livello'

    def metadata_pretty(self, obj):
        if not obj.metadata:
            return '-'
        formatted = json.dumps(obj.metadata, indent=2, ensure_ascii=False, default=str)
        return mark_safe(f'<pre style="max-height:300px;overflow:auto;font-size:12px;">{formatted}</pre>')
    metadata_pretty.short_description = 'Metadata'

    def trace_timeline(self, obj):
        """Mostra timeline completa del trace con tutti gli step."""
        logs = TraceLog.objects.filter(trace_id=obj.trace_id).order_by('created_at')

        if not logs.exists():
            return 'Nessun evento trovato'

        colors = {'info': '#3b82f6', 'warning': '#f59e0b', 'error': '#ef4444'}
        icons = {'info': '●', 'warning': '▲', 'error': '✖'}

        html_parts = [
            '<div style="font-family:monospace;font-size:13px;line-height:1.8;">',
        ]

        for i, log in enumerate(logs):
            color = colors.get(log.level, '#6b7280')
            icon = icons.get(log.level, '●')
            is_last = (i == len(logs) - 1)
            connector = '│' if not is_last else ' '
            ts = log.created_at.strftime('%H:%M:%S.%f')[:-3] if log.created_at else '??:??:??.???'

            # Riga principale
            html_parts.append(
                f'<div style="padding:4px 0;">'
                f'<span style="color:{color};font-weight:bold;">{icon}</span> '
                f'<span style="color:#9ca3af;">{ts}</span> '
                f'<span style="background:#1f2937;color:#e5e7eb;padding:1px 6px;border-radius:3px;font-size:11px;">'
                f'{log.service}</span> '
                f'<strong>{log.operation}</strong>'
            )
            if log.message:
                html_parts.append(f' — <span style="color:#d1d5db;">{log.message}</span>')
            html_parts.append('</div>')

            # Metadata (compatto)
            if log.metadata:
                meta_str = json.dumps(log.metadata, ensure_ascii=False, default=str)
                if len(meta_str) > 200:
                    meta_str = meta_str[:200] + '...'
                html_parts.append(
                    f'<div style="padding-left:24px;color:#6b7280;font-size:11px;">'
                    f'{connector} {meta_str}</div>'
                )

        html_parts.append('</div>')
        return mark_safe(''.join(html_parts))
    trace_timeline.short_description = 'Timeline'
