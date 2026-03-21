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
            'classes': ('wide',),
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
        logs = list(TraceLog.objects.filter(trace_id=obj.trace_id).order_by('created_at'))

        if not logs:
            return 'Nessun evento trovato'

        level_colors = {'info': '#3b82f6', 'warning': '#f59e0b', 'error': '#ef4444'}
        level_icons = {'info': '✓', 'warning': '⚠', 'error': '✖'}
        service_colors = {
            'backoffice-django': '#6366f1',
            'backoffice-celery-worker': '#8b5cf6',
        }

        style = (
            '<style>'
            '.tl-wrap{width:100%;font-family:ui-monospace,monospace;font-size:13px;position:relative;}'
            '.tl-wrap-outer{display:contents;}'
            '.tl-wrap-outer+style,.tl-wrap-outer~*{}'
            'div:has(> .tl-wrap){display:block !important;width:100% !important;'
            'max-width:100% !important;grid-column:1/-1 !important;}'
            'div.flex:has(> label[for="id_trace_timeline"]){display:none !important;}'
            '.tl-row{display:flex;align-items:flex-start;position:relative;padding:0;}'
            '.tl-line{position:absolute;left:19px;top:0;bottom:0;width:2px;background:#374151;}'
            '.tl-row:last-child .tl-line{display:none;}'
            '.tl-dot{flex-shrink:0;width:38px;display:flex;align-items:center;justify-content:center;'
            'padding-top:16px;position:relative;z-index:1;}'
            '.tl-dot span{width:24px;height:24px;border-radius:50%;display:flex;align-items:center;'
            'justify-content:center;font-size:12px;font-weight:700;color:#fff;}'
            '.tl-body{flex:1;min-width:0;padding:12px 0 12px 12px;}'
            '.tl-header{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}'
            '.tl-ts{color:#9ca3af;font-size:12px;white-space:nowrap;}'
            '.tl-svc{padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;color:#fff;white-space:nowrap;}'
            '.tl-op{font-weight:700;color:#e5e7eb;}'
            '.tl-msg{color:#d1d5db;margin-left:4px;}'
            '.tl-meta{margin-top:6px;background:#111827;border:1px solid #1f2937;border-radius:6px;'
            'padding:8px 12px;font-size:11px;color:#9ca3af;overflow-x:auto;white-space:pre-wrap;'
            'word-break:break-all;max-height:160px;overflow-y:auto;}'
            '.tl-meta summary{cursor:pointer;color:#6b7280;font-size:11px;user-select:none;}'
            '.tl-meta summary:hover{color:#9ca3af;}'
            '</style>'
        )

        html_parts = [style, '<div class="tl-wrap">']

        for i, log in enumerate(logs):
            color = level_colors.get(log.level, '#6b7280')
            icon = level_icons.get(log.level, '●')
            svc_color = service_colors.get(log.service, '#4b5563')
            ts = log.created_at.strftime('%H:%M:%S.%f')[:-3] if log.created_at else '—'

            html_parts.append(
                f'<div class="tl-row">'
                f'<div class="tl-line"></div>'
                f'<div class="tl-dot"><span style="background:{color};">{icon}</span></div>'
                f'<div class="tl-body">'
                f'<div class="tl-header">'
                f'<span class="tl-ts">{ts}</span>'
                f'<span class="tl-svc" style="background:{svc_color};">{log.service}</span>'
                f'<span class="tl-op">{log.operation}</span>'
            )
            if log.message:
                html_parts.append(f'<span class="tl-msg">— {log.message}</span>')
            html_parts.append('</div>')  # .tl-header

            if log.metadata:
                meta_str = json.dumps(log.metadata, indent=2, ensure_ascii=False, default=str)
                html_parts.append(
                    f'<details class="tl-meta"><summary>metadata</summary>'
                    f'<pre style="margin:4px 0 0;">{meta_str}</pre></details>'
                )

            html_parts.append('</div></div>')  # .tl-body, .tl-row

        html_parts.append('</div>')
        return mark_safe(''.join(html_parts))
    trace_timeline.short_description = 'Timeline'
