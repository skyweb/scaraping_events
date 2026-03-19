/**
 * Persiste il tab attivo Unfold in sessionStorage.
 *
 * Unfold usa Alpine.js con x-data="{openTab: null}" sui fieldset tab.
 * Questo script intercetta i click sui tab, salva l'indice in sessionStorage,
 * e lo ripristina al caricamento pagina.
 */
(function () {
  var STORAGE_KEY = "unfold_active_tab";

  // --- Ripristina tab al caricamento ---
  function restoreTab() {
    var saved = sessionStorage.getItem(STORAGE_KEY);
    if (!saved) return;

    // Aspetta che Alpine.js abbia inizializzato i tab
    var attempts = 0;
    var interval = setInterval(function () {
      attempts++;
      var tabs = document.querySelectorAll(
        "[x-data] ul a[x-on\\:click*='openTab']"
      );
      if (tabs.length === 0 && attempts < 20) return;
      clearInterval(interval);

      for (var i = 0; i < tabs.length; i++) {
        var clickExpr = tabs[i].getAttribute("x-on:click") || "";
        // x-on:click="openTab = '1-contenuto'"
        var match = clickExpr.match(/openTab\s*=\s*'([^']+)'/);
        if (match && match[1] === saved) {
          tabs[i].click();
          break;
        }
      }
    }, 50);
  }

  // --- Intercetta click sui tab e salva ---
  document.addEventListener("click", function (e) {
    var el = e.target.closest("a[x-on\\:click*='openTab']");
    if (!el) return;
    var clickExpr = el.getAttribute("x-on:click") || "";
    var match = clickExpr.match(/openTab\s*=\s*'([^']+)'/);
    if (match) {
      sessionStorage.setItem(STORAGE_KEY, match[1]);
    }
  });

  // Ripristina dopo DOMContentLoaded
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", restoreTab);
  } else {
    restoreTab();
  }
})();
