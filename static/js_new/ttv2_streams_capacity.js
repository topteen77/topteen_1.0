/**
 * Streams & seat capacity (Template v2)
 * - KPI cards are server-rendered
 * - Charts are client-rendered using Chart.js
 * - Works with AJAX partial reload (listens to ttv2:afterAjaxContentLoad)
 */
(function () {
  "use strict";

  function destroyIfAny(canvas) {
    if (!canvas || typeof Chart === "undefined") return;
    try {
      var existing = Chart.getChart(canvas);
      if (existing) existing.destroy();
    } catch (e) {}
  }

  function parsePayload() {
    var el = document.getElementById("ttv2-streams-capacity-payload");
    if (!el || !el.textContent) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      console.warn("ttv2StreamsCapacity: invalid payload", e);
      return null;
    }
  }

  function init() {
    var payload = parsePayload();
    if (!payload || typeof Chart === "undefined") return;

    var streamsMeta = Array.isArray(payload.streams_meta) ? payload.streams_meta : [];
    var classes = Array.isArray(payload.classes) ? payload.classes : [];
    var capMap = payload.cap_map && typeof payload.cap_map === "object" ? payload.cap_map : {};
    var occ = Array.isArray(payload.occupancy_by_stream) ? payload.occupancy_by_stream : [];

    // Chart 1: capacity by stream (11th vs 12th) – grouped bars
    var capCanvas = document.getElementById("ttv2StreamsCapacityByStream");
    if (capCanvas && streamsMeta.length > 0 && classes.length > 0) {
      destroyIfAny(capCanvas);
      var labels = streamsMeta.map(function (s) {
        return s.label || s.code || "-";
      });
      var capPerStream = streamsMeta.map(function (s) {
        var code = s.code || "";
        return Number(capMap[code] || 0);
      });
      var ds = classes.map(function (cls, idx) {
        var color = idx === 0 ? "rgba(96,165,250,.85)" : "rgba(167,139,250,.85)";
        return {
          label: cls,
          data: capPerStream.slice(),
          backgroundColor: color,
          borderColor: color,
          borderWidth: 1,
          borderRadius: 6,
          barPercentage: 0.75,
          categoryPercentage: 0.7,
        };
      });
      new Chart(capCanvas.getContext("2d"), {
        type: "bar",
        data: { labels: labels, datasets: ds },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: "bottom",
              labels: { boxWidth: 10, color: "#cbd5e1", font: { size: 11, weight: "600" } },
            },
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: { color: "#94a3b8" },
              grid: { color: "rgba(148, 163, 184, 0.18)" },
            },
            x: {
              ticks: { color: "#94a3b8" },
              grid: { display: false },
            },
          },
        },
      });
    }

    // Chart 2: occupancy rate by stream – horizontal bars (%)
    var occCanvas = document.getElementById("ttv2StreamsOccupancyByStream");
    if (occCanvas && occ.length > 0) {
      destroyIfAny(occCanvas);
      var occLabels = occ.map(function (r) {
        return r.label || r.code || "-";
      });
      var occData = occ.map(function (r) {
        return Number(r.pct || 0);
      });
      new Chart(occCanvas.getContext("2d"), {
        type: "bar",
        data: {
          labels: occLabels,
          datasets: [
            {
              label: "Occupancy %",
              data: occData,
              backgroundColor: "rgba(167,139,250,.85)",
              borderColor: "rgba(167,139,250,.85)",
              borderWidth: 1,
              borderRadius: 6,
            },
          ],
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: {
              beginAtZero: true,
              max: 100,
              ticks: {
                color: "#94a3b8",
                callback: function (v) {
                  return String(v) + "%";
                },
              },
              grid: { color: "rgba(148, 163, 184, 0.18)" },
            },
            y: { ticks: { color: "#94a3b8" }, grid: { display: false } },
          },
        },
      });
    }
  }

  window.ttv2InitStreamsCapacityCharts = function () {
    try {
      init();
    } catch (e) {
      console.error("ttv2StreamsCapacityCharts", e);
    }
  };

  document.addEventListener("DOMContentLoaded", window.ttv2InitStreamsCapacityCharts);
  document.addEventListener("ttv2:content:loaded", window.ttv2InitStreamsCapacityCharts);
  document.addEventListener("ttv2:afterAjaxContentLoad", window.ttv2InitStreamsCapacityCharts);
})();

