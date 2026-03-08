document.addEventListener("DOMContentLoaded", function () {
  var el = document.getElementById("map-comune");
  if (!el) return;

  var geojson = JSON.parse(el.dataset.geojson);
  var lat = parseFloat(el.dataset.lat);
  var lng = parseFloat(el.dataset.lng);

  function initMap() {
    var map = L.map("map-comune").setView([lat, lng], 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "\u00a9 OpenStreetMap contributors",
      maxZoom: 18,
    }).addTo(map);
    var layer = L.geoJSON(geojson, {
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
    map.fitBounds(layer.getBounds(), { padding: [20, 20] });
  }

  // Carica Leaflet CSS
  if (!document.querySelector('link[href*="leaflet"]')) {
    var css = document.createElement("link");
    css.rel = "stylesheet";
    css.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    document.head.appendChild(css);
  }

  // Carica Leaflet JS e inizializza
  if (typeof L !== "undefined") {
    initMap();
  } else {
    var s = document.createElement("script");
    s.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    s.onload = initMap;
    document.head.appendChild(s);
  }
});
