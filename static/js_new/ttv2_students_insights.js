/**
 * Students insights (KPI + stream donut + class bar) for any dashboard page.
 * Expects one or more roots: [data-ttv2-students-insights] and fetches
 * same URL + ?data_type=students_analytics (XHR).
 */
(function () {
  "use strict";

  var PALETTE = ["#a78bfa", "#6c7dff", "#34d399", "#fb923c", "#f472b6", "#fbbf24"];

  function cssVar(name, fallback) {
    try {
      var v = getComputedStyle(document.documentElement).getPropertyValue(name);
      v = (v || "").trim();
      return v || fallback;
    } catch (e) {
      return fallback;
    }
  }

  function setText(root, sel, text) {
    var el = root.querySelector(sel);
    if (el) el.textContent = String(text);
  }

  function setLbl(root, key, text) {
    var el = root.querySelector('[data-kpi-lbl="' + key + '"]');
    if (el) el.textContent = String(text);
  }

  function initRoot(root, force) {
    if (!root || root.getAttribute("data-ttv2-students-insights") !== "1") {
      return;
    }
    var streamCanvas = root.querySelector('canvas[data-chart="stream"]');
    var classCanvas = root.querySelector('canvas[data-chart="class"]');
    if (!streamCanvas || !classCanvas || typeof Chart === "undefined") {
      return;
    }
    if (!force && root.getAttribute("data-ttv2-si-bound") === "1") {
      return;
    }
    root.setAttribute("data-ttv2-si-bound", "1");

    if (typeof Chart !== "undefined") {
      Chart.defaults.color = cssVar("--c-text3", "rgba(146,153,176,0.85)");
      Chart.defaults.borderColor = cssVar("--c-border", "rgba(255,255,255,.12)");
    }

    var url = new URL(window.location.href);
    url.searchParams.set("data_type", "students_analytics");
    var weekSel = (url.searchParams.get("ttv2_week_start") || "").trim();
    if (weekSel) {
      setLbl(root, "total", "New enrolments (week)");
      setLbl(root, "class10", "Class 10 (new)");
      setLbl(root, "senior", "Class 11–12 (new)");
      setLbl(root, "unassigned", "Unassigned (new)");
    } else {
      setLbl(root, "total", "Total enrolled");
      setLbl(root, "class10", "Class 10");
      setLbl(root, "senior", "Class 11–12");
      setLbl(root, "unassigned", "Unassigned stream / section");
    }

    [streamCanvas, classCanvas].forEach(function (cv) {
      var card = cv.closest(".ttv2-si-chart-card");
      if (card) card.classList.add("ttv2-loading");
    });

    fetch(url.toString(), { headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (!data || !data.success) {
          return;
        }

        setText(root, '[data-kpi="total"]', data.total || 0);
        setText(root, '[data-kpi="class10"]', data.class10 || 0);
        var senior = (data.class11 || 0) + (data.class12 || 0);
        setText(root, '[data-kpi="senior"]', senior);
        var unass =
          typeof data.unassigned === "number"
            ? data.unassigned
            : (data.stream_unassigned || 0) + (data.no_section || 0);
        setText(root, '[data-kpi="unassigned"]', unass);

        var top = (data.top_stream_label || "").trim();
        setText(
          root,
          '[data-kpi-sub="class10"]',
          top ? "Top stream: " + top : ""
        );
        setText(root, '[data-kpi-sub="senior"]', senior ? "Grades 11 & 12" : "");
        setText(
          root,
          '[data-kpi-sub="unassigned"]',
          unass ? "Missing stream or class section" : "All assigned"
        );

        var sc = data.stream_counts || {};
        var streamLabels = Object.keys(sc);
        var streamData = streamLabels.map(function (k) {
          return Number(sc[k] || 0);
        });
        if (!streamLabels.length) {
          streamLabels = ["No stream data"];
          streamData = [0];
        }

        if (root._ttv2SiStreamChart) {
          try {
            root._ttv2SiStreamChart.destroy();
          } catch (e) {}
          root._ttv2SiStreamChart = null;
        }
        if (root._ttv2SiClassChart) {
          try {
            root._ttv2SiClassChart.destroy();
          } catch (e) {}
          root._ttv2SiClassChart = null;
        }

        var sctx = streamCanvas.getContext("2d");
        root._ttv2SiStreamChart = new Chart(sctx, {
          type: "doughnut",
          data: {
            labels: streamLabels,
            datasets: [
              {
                data: streamData,
                backgroundColor: PALETTE,
                borderWidth: 0,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "72%",
            animation: { duration: 650, easing: "easeOutQuart" },
            plugins: {
              legend: { position: "left", labels: { boxWidth: 10 } },
            },
          },
        });

        var c10 = data.class10 || 0;
        var c11 = data.class11 || 0;
        var c12 = data.class12 || 0;
        var cOther = data.class_other || 0;
        var barLabels = ["Class 10", "Class 11", "Class 12", "Other / primary"];
        var barData = [c10, c11, c12, cOther];
        var cctx = classCanvas.getContext("2d");
        root._ttv2SiClassChart = new Chart(cctx, {
          type: "bar",
          data: {
            labels: barLabels,
            datasets: [
              {
                label: "Students",
                data: barData,
                backgroundColor: ["#6c7dff", "#34d399", "#22c55e", "#94a3b8"],
                borderRadius: 10,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 650, easing: "easeOutQuart" },
            plugins: { legend: { display: false } },
            scales: {
              y: {
                beginAtZero: true,
                ticks: { stepSize: 1 },
              },
            },
          },
        });
      })
      .catch(function () {})
      .finally(function () {
        [streamCanvas, classCanvas].forEach(function (cv) {
          var card = cv.closest(".ttv2-si-chart-card");
          if (card) card.classList.remove("ttv2-loading");
        });
      });
  }

  function scan(force) {
    document.querySelectorAll("[data-ttv2-students-insights]").forEach(function (root) {
      initRoot(root, !!force);
    });
  }

  window.ttv2InitStudentsInsightsBlocks = function (force) {
    document.querySelectorAll("[data-ttv2-students-insights]").forEach(function (root) {
      root.removeAttribute("data-ttv2-si-bound");
      initRoot(root, true);
    });
  };

  document.addEventListener("DOMContentLoaded", function () {
    scan(false);
  });
})();
