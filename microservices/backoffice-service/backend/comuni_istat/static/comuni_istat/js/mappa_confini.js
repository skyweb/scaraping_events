document.addEventListener("DOMContentLoaded", function () {
  var el = document.getElementById("map-comune");
  if (!el) return;

  var geojson = JSON.parse(el.dataset.geojson);
  var lat = parseFloat(el.dataset.lat);
  var lng = parseFloat(el.dataset.lng);
  var map = null;
  var layer = null;

  function expandContainer() {
    // Rimuove max-w-2xl dal container readonly di Unfold
    var parent = el.parentElement;
    if (parent) {
      parent.style.maxWidth = "none";
      parent.style.width = "100%";
      parent.style.padding = "0";
    }
  }

  function initMap() {
    if (map) return;
    expandContainer();
    map = L.map("map-comune").setView([lat, lng], 12);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      attribution: '\u00a9 <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> \u00a9 <a href="https://carto.com/">CARTO</a>',
      maxZoom: 19,
      subdomains: "abcd",
    }).addTo(map);
    layer = L.geoJSON(geojson, {
      style: {
        color: "#7c3aed",
        weight: 2,
        fillOpacity: 0.15,
        fillColor: "#a78bfa",
      },
    }).addTo(map);
    L.circleMarker([lat, lng], {
      radius: 6,
      fillColor: "#ef4444",
      color: "#fff",
      weight: 2,
      fillOpacity: 0.9,
    }).addTo(map);
    setTimeout(function () {
      map.invalidateSize();
      map.fitBounds(layer.getBounds(), { padding: [20, 20] });
    }, 150);
  }

  function tryInit() {
    if (el.offsetParent !== null && el.offsetWidth > 0) {
      if (!map) {
        initMap();
      } else {
        // Tab già inizializzato, reinvalida
        map.invalidateSize();
        map.fitBounds(layer.getBounds(), { padding: [20, 20] });
      }
    }
  }

  // Carica Leaflet CSS
  if (!document.querySelector('link[href*="leaflet"]')) {
    var css = document.createElement("link");
    css.rel = "stylesheet";
    css.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    document.head.appendChild(css);
  }

  function setupListeners() {
    tryInit();
    document.addEventListener("click", function () {
      setTimeout(tryInit, 250);
    });
  }

  if (typeof L !== "undefined") {
    setupListeners();
  } else {
    var s = document.createElement("script");
    s.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    s.onload = setupListeners;
    document.head.appendChild(s);
  }
});
