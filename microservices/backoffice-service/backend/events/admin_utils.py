"""
Funzioni di utilità condivise per l'admin di Django.

Raccoglie le funzioni di rendering HTML (chip, date, link, immagini, JSON)
usate da più classi ModelAdmin per evitare duplicazioni.
"""
import json

from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe


# =============================================================================
# Chip HTML generici
# =============================================================================

def render_chip(text, color, bg):
    """Genera un chip HTML con testo, colore testo e colore sfondo."""
    return format_html(
        '<span style="display:inline-block;padding:0.2rem 0.75rem;border-radius:9999px;'
        'font-size:0.75rem;font-weight:600;white-space:nowrap;color:{};background:{};">{}</span>',
        color, bg, text,
    )


# =============================================================================
# Chip di stato temporale degli eventi
# =============================================================================

def render_event_status_chip(date_start, date_end):
    """
    Restituisce un chip colorato in base allo stato temporale dell'evento.

    - Rosso: Scaduto (date_end < oggi)
    - Verde: In corso (oggi compreso tra start e end)
    - Blu: Futuro (date_start > oggi)

    Restituisce "-" se date_start è None.
    """
    if not date_start:
        return "-"

    today = timezone.now().date()
    # Normalizza a date se sono datetime
    if hasattr(date_start, 'date'):
        date_start = date_start.date()
    if date_end and hasattr(date_end, 'date'):
        date_end = date_end.date()
    end = date_end if date_end else date_start

    if end < today:
        return render_chip('Scaduto', '#991b1b', '#fee2e2')
    elif date_start <= today <= end:
        return render_chip('In corso', '#166534', '#dcfce7')
    else:
        return render_chip('Prossimamente', '#1e40af', '#dbeafe')


# =============================================================================
# Chip categorie
# =============================================================================

def render_category_chips(categories):
    """
    Renderizza una lista di categorie come chip blu.

    Restituisce "-" se la lista è vuota o None.
    """
    if not categories:
        return "-"

    chips = ''.join(
        f'<span style="display:inline-block;padding:0.125rem 0.5rem;margin:0.125rem;'
        f'background:#e0f2fe;color:#0369a1;border-radius:9999px;font-size:0.75rem;font-weight:500;">'
        f'{cat}</span>'
        for cat in categories
    )
    return mark_safe(
        f'<div style="display:flex;flex-wrap:wrap;gap:0.125rem;">{chips}</div>'
    )


# =============================================================================
# Formattazione date
# =============================================================================

def format_date_italian(date):
    """Formatta una data in formato italiano dd/mm/yyyy. Restituisce '-' se None."""
    if date:
        return date.strftime('%d/%m/%Y')
    return "-"


def format_datetime_italian(dt):
    """Formatta un datetime in formato italiano dd/mm/yyyy HH:MM (con timezone locale). Restituisce '-' se None."""
    if dt:
        return timezone.localtime(dt).strftime('%d/%m/%Y %H:%M')
    return "-"


# =============================================================================
# Link e immagini
# =============================================================================

def render_clickable_link(url):
    """Renderizza un URL come link cliccabile con icona di apertura esterna."""
    if url:
        return format_html(
            '<a href="{0}" target="_blank" class="text-primary-600 font-medium '
            'hover:underline flex items-center gap-1">{0} '
            '<span class="material-symbols-outlined text-sm">open_in_new</span></a>',
            url,
        )
    return "-"


def render_image_preview(url):
    """Renderizza un'anteprima dell'immagine (max 100x150px) con bordi arrotondati."""
    if url:
        return format_html(
            '<img src="{}" style="max-height:100px;max-width:150px;border-radius:4px;" />',
            url,
        )
    return "-"


def render_image_thumbnail(url):
    """
    Renderizza una miniatura cliccabile (max 60x80px).

    Il click apre un popup overlay a schermo intero con l'immagine.
    Include lo script JS per il popup (registrato una sola volta su window).
    """
    if url:
        return format_html(
            '<a href="javascript:void(0);" onclick="openImagePopup(\'{0}\')" style="cursor:pointer;">'
            '<img src="{0}" style="max-height:60px;max-width:80px;border-radius:4px;object-fit:cover;" />'
            '</a>'
            '<script>'
            'if (!window.openImagePopup) {{'
            '  window.openImagePopup = function(url) {{'
            '    var overlay = document.createElement("div");'
            '    overlay.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;'
            'background:rgba(0,0,0,0.8);z-index:9999;display:flex;align-items:center;'
            'justify-content:center;cursor:pointer;";'
            '    overlay.onclick = function() {{ document.body.removeChild(overlay); }};'
            '    var img = document.createElement("img");'
            '    img.src = url;'
            '    img.style.cssText = "max-width:90%;max-height:90%;border-radius:8px;'
            'box-shadow:0 4px 20px rgba(0,0,0,0.5);";'
            '    overlay.appendChild(img);'
            '    document.body.appendChild(overlay);'
            '  }};'
            '}}'
            '</script>',
            url,
        )
    return "-"


def render_clickable_image_url(url):
    """Renderizza l'URL dell'immagine come link cliccabile con word-break per URL lunghi."""
    if url:
        return format_html(
            '<div style="min-width:600px;display:inline-block;">'
            '<a href="{0}" target="_blank" class="text-primary-600 font-medium '
            'hover:underline flex items-center gap-1" style="word-break:break-all;">'
            '{0} <span class="material-symbols-outlined text-sm">open_in_new</span></a></div>',
            url,
        )
    return "-"


# =============================================================================
# JSON preview con sintassi colorata
# =============================================================================

def render_json_preview(raw_data, unique_id):
    """
    Renderizza raw_data come JSON con sintassi colorata (tema scuro Catppuccin) e pulsante copia.

    Parametri:
        raw_data: dict/list da serializzare in JSON
        unique_id: identificativo univoco per gli elementi DOM (es. "json-42-staging")
    """
    if not raw_data:
        return "-"

    data = json.dumps(raw_data, indent=2, sort_keys=True, ensure_ascii=False)
    fn = unique_id.replace('-', '_')
    return mark_safe(f'''
        <div style="position:relative;width:100%;">
            <button type="button" onclick="{fn}_copy()"
                style="position:absolute;top:8px;right:8px;padding:0.375rem 0.75rem;
                background:#2563eb;color:#fff;border:none;border-radius:0.375rem;
                cursor:pointer;font-size:0.75rem;display:flex;align-items:center;gap:0.25rem;z-index:1;"
                onmouseover="this.style.background='#1d4ed8'"
                onmouseout="this.style.background='#2563eb'">
                <span class="material-symbols-outlined" style="font-size:1rem;">content_copy</span> Copia
            </button>
            <pre id="{unique_id}" style="white-space:pre-wrap;word-wrap:break-word;
                background:#1e1e2e;color:#cdd6f4;padding:2.5rem 1rem 1rem;
                border-radius:0.5rem;font-family:'Fira Code',Consolas,monospace;
                font-size:0.8rem;line-height:1.6;width:100%;box-sizing:border-box;
                overflow-x:auto;"></pre>
        </div>
        <script>
        (function() {{
            var raw = {json.dumps(data)};
            var el = document.getElementById("{unique_id}");
            el.innerHTML = raw
                .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                .replace(/"([^"]+)"\\s*:/g, '<span style="color:#89b4fa;">"$1"</span>:')
                .replace(/:\\s*"([^"]*)"/g, ': <span style="color:#a6e3a1;">"$1"</span>')
                .replace(/:\\s*(\\d+\\.?\\d*)/g, ': <span style="color:#fab387;">$1</span>')
                .replace(/:\\s*(true|false)/g, ': <span style="color:#f38ba8;">$1</span>')
                .replace(/:\\s*(null)/g, ': <span style="color:#6c7086;">$1</span>');
        }})();
        function {fn}_copy() {{
            var raw = {json.dumps(data)};
            navigator.clipboard.writeText(raw).then(function() {{
                var btn = event.target.closest("button");
                var orig = btn.innerHTML;
                btn.innerHTML = '<span class="material-symbols-outlined" style="font-size:1rem;">check</span> Copiato!';
                btn.style.background = '#16a34a';
                setTimeout(function() {{ btn.innerHTML = orig; btn.style.background = '#2563eb'; }}, 2000);
            }});
        }}
        </script>
    ''')
