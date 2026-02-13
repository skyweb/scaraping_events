from django import forms
from django.utils.safestring import mark_safe


class ImagePopupWidget(forms.HiddenInput):
    """
    Widget che mostra un bottone con thumbnail.
    Al click apre un popup per inserire URL o caricare file.
    Il valore viene salvato come URL nel campo nascosto.
    """

    class Media:
        js = ('cms/js/image_popup.js',)
        css = {'all': ('cms/css/image_popup.css',)}

    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        widget_id = attrs.get('id', name)
        value = value or ''

        # Thumbnail nel bottone
        if value:
            thumb_html = (
                f'<img class="ip-thumb" src="{value}" alt="" />'
                f'<span class="material-symbols-outlined ip-icon" style="display:none">add_photo_alternate</span>'
            )
        else:
            thumb_html = '<span class="material-symbols-outlined ip-icon">add_photo_alternate</span>'

        # Anteprima nel dialog
        if value:
            preview_html = f'<img src="{value}" />'
        else:
            preview_html = '<span class="ip-no-img">Nessuna immagine</span>'

        html = f"""
        <input type="hidden" name="{name}" id="{widget_id}" value="{value}" />
        <button type="button" class="ip-trigger" data-trigger="{widget_id}"
                onclick="imgPopupOpen('{widget_id}')">
            {thumb_html} Immagine
        </button>
        <dialog id="dlg-{widget_id}" class="ip-dialog">
            <div class="ip-dialog-inner">
                <h3>Gestione immagine</h3>
                <div class="ip-preview">{preview_html}</div>
                <div class="ip-field">
                    <label>URL immagine</label>
                    <input type="url" class="ip-url-input" value="{value}"
                           placeholder="https://example.com/immagine.jpg"
                           oninput="imgPopupPreview('{widget_id}')" />
                </div>
                <div class="ip-separator">oppure</div>
                <div class="ip-field">
                    <label>Carica file</label>
                    <input type="file" accept="image/*"
                           onchange="imgPopupUpload('{widget_id}', this)" />
                    <div class="ip-upload-status"></div>
                </div>
                <div class="ip-actions">
                    <button type="button" class="ip-btn ip-btn-secondary"
                            onclick="imgPopupClose('{widget_id}')">Annulla</button>
                    <button type="button" class="ip-btn ip-btn-primary"
                            onclick="imgPopupConfirm('{widget_id}')">Conferma</button>
                </div>
            </div>
        </dialog>
        """
        return mark_safe(html)
