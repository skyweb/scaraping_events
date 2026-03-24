document.addEventListener("DOMContentLoaded", function () {
  var el = document.getElementById("map-event-location");
  if (!el) return;

  var lat = parseFloat(el.dataset.lat);
  var lng = parseFloat(el.dataset.lng);
  var map = null;

  function expandContainer() {
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
    map = L.map("map-event-location").setView([lat, lng], 15);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      attribution: '\u00a9 <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> \u00a9 <a href="https://carto.com/">CARTO</a>',
      maxZoom: 19,
      subdomains: "abcd",
    }).addTo(map);
    var locationName = el.dataset.locationName || "";
    var popup = (locationName ? "Luogo: <strong>" + locationName + "</strong><br>" : "")
      + "Lat: " + lat.toFixed(6) + "<br>"
      + "Lng: " + lng.toFixed(6);
    L.circleMarker([lat, lng], {
      radius: 8,
      fillColor: "#ef4444",
      color: "#fff",
      weight: 2,
      fillOpacity: 0.9,
    })
      .bindPopup(popup)
      .addTo(map);
    setTimeout(function () {
      map.invalidateSize();
    }, 150);
  }

  function tryInit() {
    if (el.offsetParent !== null && el.offsetWidth > 0) {
      if (!map) {
        initMap();
      } else {
        map.invalidateSize();
      }
    }
  }

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
