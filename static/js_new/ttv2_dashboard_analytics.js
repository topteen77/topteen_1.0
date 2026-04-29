/**
 * Render Chart.js charts for template v2 dashboard analytics (KPI payload from Django).
 * Expects: <script type="application/json" id="ttv2-analytics-payload">…</script>
 */
(function () {
  var _charts = { psych: null, sess: null, clar: null, risk: null, cred: null };

  function destroyAll() {
    Object.keys(_charts).forEach(function (k) {
      try {
        if (_charts[k] && _charts[k].destroy) {
          _charts[k].destroy();
        }
      } catch (e) {}
      _charts[k] = null;
    });
  }

  function cssVar(name, fallback) {
    try {
      var v = getComputedStyle(document.documentElement).getPropertyValue(name);
      v = (v || "").trim();
      return v || fallback;
    } catch (e) {
      return fallback;
    }
  }

  function readPayload() {
    var el = document.getElementById("ttv2-analytics-payload");
    if (!el) return null;
    try {
      return JSON.parse(el.textContent || "{}");
    } catch (e) {
      return null;
    }
  }

  function clearChartAreaLoading() {
    try {
      document.querySelectorAll("[data-ttv2-charts-area]").forEach(function (el) {
        el.classList.remove("ttv2-da-charts-area--loading");
      });
    } catch (e) {}
  }

  function init() {
    if (typeof Chart === "undefined") {
      clearChartAreaLoading();
      return;
    }
    var data = readPayload();
    if (!data || !data.charts) {
      clearChartAreaLoading();
      return;
    }
    try {
    destroyAll();

    var fg = cssVar("--c-text", "#F0F2FF");
    var accent = cssVar("--c-accent", "#6c7dff");
    var ok = "#34d399";
    var warn = "#fb923c";
    var border = cssVar("--c-border", "rgba(255,255,255,.12)");
    var muted = cssVar("--c-text3", "rgba(146,153,176,0.85)");
    Chart.defaults.color = muted;
    Chart.defaults.borderColor = border;
    Chart.defaults.font.family =
      "Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif";

    var ch = data.charts;

    // Psychometric donut
    var p = ch.psych_donut || {};
    var pDone = Number(p.completed || 0);
    var pPend = Number(p.pending != null ? p.pending : (p.total || 0) - pDone);
    if (pPend < 0) pPend = 0;
    var psychLabels = Array.isArray(p.labels) && p.labels.length >= 2 ? p.labels : ["Completed", "Pending"];
    var elP = document.getElementById("ttv2DaPsych");
    if (elP) {
      _charts.psych = new Chart(elP.getContext("2d"), {
        type: "doughnut",
        data: {
          labels: psychLabels,
          datasets: [
            {
              data: [pDone, pPend],
              backgroundColor: [ok, "rgba(255,255,255,.08)"],
              borderWidth: 0,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: "70%",
          plugins: {
            legend: { position: "bottom", labels: { boxWidth: 10, color: muted } },
            tooltip: { enabled: true },
          },
        },
      });
    }

    // Sessions line
    var sl = ch.sessions_line || {};
    var elS = document.getElementById("ttv2DaSess");
    if (elS) {
      _charts.sess = new Chart(elS.getContext("2d"), {
        type: "line",
        data: {
          labels: sl.labels && sl.labels.length ? sl.labels : ["—", "—", "—", "—"],
          datasets: [
            {
              label: "Sessions",
              data: (sl.values || []).map(function (v) {
                return Number(v) || 0;
              }),
              borderColor: ok,
              backgroundColor: "rgba(52, 211, 153, 0.12)",
              fill: true,
              tension: 0.35,
              pointRadius: 3,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, ticks: { color: muted } },
            x: { ticks: { color: muted, maxRotation: 45, minRotation: 0 } },
          },
        },
      });
    }

    // Clarity
    var cl = ch.clarity_line || {};
    var elC = document.getElementById("ttv2DaClarity");
    if (elC) {
      var pts = (cl.values || [0, 0, 0, 0]).map(function (v) {
        return Number(v) || 0;
      });
      _charts.clar = new Chart(elC.getContext("2d"), {
        type: "line",
        data: {
          labels: cl.labels && cl.labels.length ? cl.labels : ["W1", "W2", "W3", "W4"],
          datasets: [
            {
              data: pts,
              borderColor: warn,
              backgroundColor: "transparent",
              tension: 0.35,
              pointRadius: 2,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: {
              beginAtZero: true,
              max: 100,
              ticks: {
                color: muted,
                callback: function (v) {
                  return v + "%";
                },
              },
            },
            x: { ticks: { color: muted } },
          },
        },
      });
    }

    // Risk (stacked bar)
    var r = ch.risk_donut || {};
    var onT = Number(r.on_track || 0);
    var atR = Number(r.at_risk || 0);
    var elR = document.getElementById("ttv2DaRisk");
    if (elR) {
      _charts.risk = new Chart(elR.getContext("2d"), {
        type: "bar",
        data: {
          labels: ["Students"],
          datasets: [
            {
              label: "On track",
              data: [onT],
              backgroundColor: ok,
              borderWidth: 0,
              borderRadius: 10,
              barThickness: 28,
              maxBarThickness: 32,
            },
            {
              label: "At risk",
              data: [atR],
              backgroundColor: "rgba(248,113,113,0.55)",
              borderWidth: 0,
              borderRadius: 10,
              barThickness: 28,
              maxBarThickness: 32,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: "bottom", labels: { boxWidth: 10 } },
            tooltip: { enabled: true },
          },
          scales: {
            x: { stacked: true, ticks: { color: muted } },
            y: { stacked: true, beginAtZero: true, ticks: { color: muted } },
          },
        },
      });
    }

    // Credits
    var cr = ch.credit_donut || {};
    var u = Math.max(0, Number(cr.used || 0));
    var l = Math.max(0, Number(cr.left || 0));
    if (u + l < 1) l = 1;
    var elCr = document.getElementById("ttv2DaCredit");
    if (elCr) {
      _charts.cred = new Chart(elCr.getContext("2d"), {
        type: "doughnut",
        data: {
          labels: ["Used", "Left"],
          datasets: [
            {
              data: [u, l],
              backgroundColor: [accent, "rgba(128, 140, 255, 0.35)"],
              borderWidth: 0,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: "70%",
          plugins: { legend: { position: "bottom", labels: { boxWidth: 10 } } },
        },
      });
    }

    // Export PDF (footer + any duplicate id in shell)
    var pdfBtns = document.querySelectorAll(
      "#ttv2ExportPdfBtn, #ttv2ExportPdfBtnFooter"
    );
    pdfBtns.forEach(function (btn) {
      if (!btn || btn.dataset.ttv2PdfBound) return;
      btn.dataset.ttv2PdfBound = "1";
      btn.addEventListener("click", function () {
        try {
          window.print();
        } catch (e) {}
      });
    });
    } finally {
      clearChartAreaLoading();
    }
  }

  window.ttv2InitDashboardAnalyticsCharts = function () {
    try {
      init();
    } catch (e) {
      console.error("ttv2 analytics charts", e);
    }
  };
})();
