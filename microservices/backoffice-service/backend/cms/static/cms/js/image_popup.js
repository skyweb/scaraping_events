(function () {
  "use strict";

  /* URL endpoint upload (iniettato dal widget come data-attr) */
  const UPLOAD_URL = "/api/cms/upload/";

  /* ── Apri dialog ── */
  window.imgPopupOpen = function (widgetId) {
    const dialog = document.getElementById("dlg-" + widgetId);
    if (!dialog) return;
    /* Aggiorna preview iniziale */
    const hidden = document.getElementById(widgetId);
    const urlInput = dialog.querySelector(".ip-url-input");
    const preview = dialog.querySelector(".ip-preview");
    if (hidden && urlInput) urlInput.value = hidden.value || "";
    refreshPreview(preview, hidden ? hidden.value : "");
    dialog.showModal();
  };

  /* ── Conferma e chiudi ── */
  window.imgPopupConfirm = function (widgetId) {
    const dialog = document.getElementById("dlg-" + widgetId);
    const hidden = document.getElementById(widgetId);
    const urlInput = dialog.querySelector(".ip-url-input");
    if (hidden && urlInput) hidden.value = urlInput.value;
    /* Aggiorna thumbnail nel bottone */
    const thumb = document.querySelector('[data-trigger="' + widgetId + '"] .ip-thumb');
    const icon = document.querySelector('[data-trigger="' + widgetId + '"] .ip-icon');
    if (thumb && urlInput.value) {
      thumb.src = urlInput.value;
      thumb.style.display = "block";
      if (icon) icon.style.display = "none";
    } else if (thumb && !urlInput.value) {
      thumb.style.display = "none";
      if (icon) icon.style.display = "";
    }
    dialog.close();
  };

  /* ── Annulla ── */
  window.imgPopupClose = function (widgetId) {
    document.getElementById("dlg-" + widgetId)?.close();
  };

  /* ── Live preview da URL ── */
  window.imgPopupPreview = function (widgetId) {
    const dialog = document.getElementById("dlg-" + widgetId);
    const urlInput = dialog.querySelector(".ip-url-input");
    const preview = dialog.querySelector(".ip-preview");
    refreshPreview(preview, urlInput ? urlInput.value : "");
  };

  /* ── Upload file via AJAX ── */
  window.imgPopupUpload = function (widgetId, input) {
    if (!input.files || !input.files[0]) return;
    const dialog = document.getElementById("dlg-" + widgetId);
    const urlInput = dialog.querySelector(".ip-url-input");
    const preview = dialog.querySelector(".ip-preview");
    const status = dialog.querySelector(".ip-upload-status");

    var fd = new FormData();
    fd.append("file", input.files[0]);

    /* CSRF token */
    var csrfToken =
      document.querySelector("[name=csrfmiddlewaretoken]")?.value ||
      getCookie("csrftoken");
    if (csrfToken) fd.append("csrfmiddlewaretoken", csrfToken);

    if (status) {
      status.textContent = "Caricamento in corso...";
      status.className = "ip-upload-status ip-loading";
    }

    fetch(UPLOAD_URL, { method: "POST", body: fd })
      .then(function (r) {
        if (!r.ok) throw new Error("Errore upload");
        return r.json();
      })
      .then(function (data) {
        if (urlInput) urlInput.value = data.url;
        refreshPreview(preview, data.url);
        if (status) {
          status.textContent = "Caricato!";
          status.className = "ip-upload-status ip-ok";
        }
        /* Reset file input */
        input.value = "";
      })
      .catch(function () {
        if (status) {
          status.textContent = "Errore nel caricamento";
          status.className = "ip-upload-status ip-err";
        }
      });
  };

  /* ── Helpers ── */
  function refreshPreview(container, url) {
    if (!container) return;
    if (url) {
      container.innerHTML =
        '<img src="' + url + '" onerror="this.parentNode.innerHTML=\'Anteprima non disponibile\'" />';
    } else {
      container.innerHTML =
        '<span class="ip-no-img">Nessuna immagine</span>';
    }
  }

  function getCookie(name) {
    var v = "; " + document.cookie;
    var parts = v.split("; " + name + "=");
    if (parts.length === 2) return parts.pop().split(";").shift();
    return "";
  }
})();
