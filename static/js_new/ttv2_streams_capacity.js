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
    var theme =
      (document.documentElement.getAttribute("data-ttv2-theme") || "").toLowerCase() === "dark"
        ? "dark"
        : "light";
    var chartTextColor = theme === "dark" ? "rgba(232, 234, 240, 0.82)" : "#475569";
    var chartGrid =
      theme === "dark" ? "rgba(255, 255, 255, 0.08)" : "rgba(148, 163, 184, 0.18)";

    function gradientFill(ctx, top, bottom) {
      var g = ctx.createLinearGradient(0, 0, 0, 260);
      g.addColorStop(0, top);
      g.addColorStop(1, bottom);
      return g;
    }

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
        var color = idx === 0
          ? gradientFill(capCanvas.getContext("2d"), "rgba(59,130,246,.95)", "rgba(125,211,252,.78)")
          : gradientFill(capCanvas.getContext("2d"), "rgba(139,92,246,.95)", "rgba(216,180,254,.78)");
        return {
          label: cls,
          data: capPerStream.slice(),
          backgroundColor: color,
          borderColor: idx === 0 ? "rgba(59,130,246,.95)" : "rgba(139,92,246,.95)",
          borderWidth: 1,
          borderRadius: 10,
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
              labels: { boxWidth: 10, color: chartTextColor, font: { size: 11, weight: "600" } },
            },
            tooltip: {
              backgroundColor: "rgba(15,23,42,.92)",
              titleColor: "#e2e8f0",
              bodyColor: "#e2e8f0",
              borderColor: "rgba(148,163,184,.2)",
              borderWidth: 1,
              padding: 10,
            },
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: { color: chartTextColor },
              grid: { color: chartGrid },
            },
            x: {
              ticks: { color: chartTextColor },
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
      var occCtx = occCanvas.getContext("2d");
      var occGradient = gradientFill(occCtx, "rgba(16,185,129,.94)", "rgba(52,211,153,.74)");
      new Chart(occCanvas.getContext("2d"), {
        type: "bar",
        data: {
          labels: occLabels,
          datasets: [
            {
              label: "Occupancy %",
              data: occData,
              backgroundColor: occGradient,
              borderColor: "rgba(5,150,105,.9)",
              borderWidth: 1,
              borderRadius: 10,
            },
          ],
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: "rgba(15,23,42,.92)",
              titleColor: "#e2e8f0",
              bodyColor: "#e2e8f0",
              callbacks: {
                label: function (ctx) {
                  return " Occupancy: " + Number(ctx.raw || 0).toFixed(1) + "%";
                },
              },
            },
          },
          scales: {
            x: {
              beginAtZero: true,
              max: 100,
              ticks: {
                color: chartTextColor,
                callback: function (v) {
                  return String(v) + "%";
                },
              },
              grid: { color: chartGrid },
            },
            y: { ticks: { color: chartTextColor }, grid: { display: false } },
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

  /** Re-render charts when v2 light/dark theme toggles (no custom event from theme script). */
  (function observeThemeForCharts() {
    var deb;
    var obs = new MutationObserver(function () {
      if (!document.getElementById("ttv2StreamsCapacityByStream")) return;
      clearTimeout(deb);
      deb = setTimeout(function () {
        window.ttv2InitStreamsCapacityCharts();
      }, 80);
    });
    try {
      obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-ttv2-theme"] });
    } catch (e) {}
  })();
})();

