/**
 * Render Chart.js charts for template v2 dashboard analytics (KPI payload from Django).
 * Per-chart donut loaders show % + tracking status while each graph initializes.
 * Expects: <script type="application/json" id="ttv2-analytics-payload">…</script>
 */
(function () {
  var _charts = { psych: null, sess: null, clar: null, risk: null, cred: null };
  var _boundViewToggle = false;
  var CHART_KEYS = ["psych", "sess", "clar", "risk", "cred"];
  var _chartJsPromise = null;

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

  /** Legacy whole-area overlay (optional); per-slot loaders are primary. */
  function clearChartAreaLoading() {
    try {
      document.querySelectorAll("[data-ttv2-charts-area]").forEach(function (el) {
        el.classList.remove("ttv2-da-charts-area--loading");
      });
    } catch (e) {}
  }

  function slotRoot(key) {
    return document.querySelector('[data-ttv2-chart-loader="' + key + '"]');
  }

  function ensureChartJs() {
    if (typeof Chart !== "undefined") return Promise.resolve(true);
    if (_chartJsPromise) return _chartJsPromise;
    _chartJsPromise = new Promise(function (resolve) {
      try {
        var s = document.createElement("script");
        // Use a pinned UMD build for consistent global `Chart`.
        s.src = "https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js";
        s.async = true;
        s.onload = function () {
          resolve(typeof Chart !== "undefined");
        };
        s.onerror = function () {
          resolve(false);
        };
        document.head.appendChild(s);
      } catch (e) {
        resolve(false);
      }
    });
    return _chartJsPromise;
  }

  function updateChartSlot(key, pct, status, isError) {
    var root = slotRoot(key);
    if (!root) return;
    root.style.display = "flex";
    root.setAttribute("aria-busy", "true");
    var clamped = Math.max(0, Math.min(100, Number(pct) || 0));
    root.style.setProperty("--ttv2-load-pct", String(clamped));
    var donut = root.querySelector(".ttv2-chart-slot-loader__donut");
    if (donut) donut.style.setProperty("--ttv2-load-pct", String(clamped));
    var p = root.querySelector(".ttv2-chart-slot-loader__pct");
    if (p) p.textContent = Math.round(clamped) + "%";
    var s = root.querySelector("[data-ttv2-load-status]");
    if (s && status) s.textContent = status;
    try {
      root.setAttribute("aria-valuenow", String(Math.round(clamped)));
    } catch (e2) {}
    root.classList.toggle("ttv2-chart-slot-loader--error", !!isError);
  }

  function hideChartSlot(key) {
    var root = slotRoot(key);
    if (!root) return;
    root.style.display = "none";
    root.setAttribute("aria-busy", "false");
    root.classList.remove("ttv2-chart-slot-loader--error");
  }

  function resetAllChartSlots() {
    CHART_KEYS.forEach(function (key) {
      updateChartSlot(key, 0, "Queued", false);
    });
  }

  function hideAllChartSlots() {
    CHART_KEYS.forEach(hideChartSlot);
  }

  function runChartFast(key, buildFn) {
    // No artificial waits: show quick status updates but render ASAP.
    updateChartSlot(key, 22, "Preparing…", false);
    try {
      if (typeof buildFn === "function") buildFn();
      updateChartSlot(key, 100, "Ready", false);
      // Let the DOM paint once before hiding, so loader doesn't flicker.
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          hideChartSlot(key);
        });
      });
    } catch (err) {
      console.error("ttv2 chart " + key, err);
      updateChartSlot(key, 100, "Error", true);
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          hideChartSlot(key);
        });
      });
    }
  }

  function toRows(labels, values) {
    var out = [];
    var len = Math.max(labels.length, values.length);
    for (var i = 0; i < len; i++) {
      out.push({
        label: String(labels[i] != null ? labels[i] : "—"),
        value: Number(values[i]) || 0,
      });
    }
    return out;
  }

  function fillTableBody(tbodyId, rows) {
    var tbody = document.getElementById(tbodyId);
    if (!tbody) return;
    if (!rows || !rows.length) {
      tbody.innerHTML = '<tr><td colspan="2" class="text-muted">No data available</td></tr>';
      return;
    }
    tbody.innerHTML = rows
      .map(function (r) {
        return (
          "<tr><td>" +
          String(r.label) +
          '</td><td class="text-end">' +
          String(r.value) +
          "</td></tr>"
        );
      })
      .join("");
  }

  function setCardView(target, view) {
    var chartWrap = document.querySelector('[data-ttv2-chart-wrap="' + target + '"]');
    var tableWrap = document.querySelector('[data-ttv2-table-wrap="' + target + '"]');
    if (!chartWrap || !tableWrap) return;
    var showTable = view === "table";
    chartWrap.style.display = showTable ? "none" : "";
    tableWrap.style.display = showTable ? "" : "none";
    document.querySelectorAll('[data-ttv2-view-btn][data-target="' + target + '"]').forEach(function (btn) {
      var active = btn.getAttribute("data-view") === view;
      btn.classList.toggle("active", active);
    });
  }

  function bindViewToggles() {
    if (_boundViewToggle) return;
    _boundViewToggle = true;
    document.addEventListener("click", function (e) {
      var btn = e.target && (e.target.closest ? e.target.closest("[data-ttv2-view-btn]") : null);
      if (!btn) return;
      e.preventDefault();
      var target = (btn.getAttribute("data-target") || "").trim();
      var view = (btn.getAttribute("data-view") || "").trim();
      if (!target || !view) return;
      setCardView(target, view);
    });
  }

  function bindPdfExportOnce() {
    var pdfBtns = document.querySelectorAll("#ttv2ExportPdfBtn, #ttv2ExportPdfBtnFooter");
    pdfBtns.forEach(function (btn) {
      if (!btn || btn.dataset.ttv2PdfBound) return;
      btn.dataset.ttv2PdfBound = "1";
      btn.addEventListener("click", function () {
        try {
          window.print();
        } catch (e) {}
      });
    });
  }

  function init() {
    clearChartAreaLoading();
    resetAllChartSlots();
    var data = readPayload();
    if (!data || !data.charts) {
      CHART_KEYS.forEach(function (key) {
        updateChartSlot(key, 100, "No analytics payload", true);
      });
      hideAllChartSlots();
      return;
    }

    // Only keep loaders for charts that actually exist on this page.
    // If a canvas is missing, hide that loader quickly.
    try {
      if (!document.getElementById("ttv2DaPsych")) hideChartSlot("psych");
      if (!document.getElementById("ttv2DaSess")) hideChartSlot("sess");
      if (!document.getElementById("ttv2DaClarity")) hideChartSlot("clar");
      if (!document.getElementById("ttv2DaRisk")) hideChartSlot("risk");
      if (!document.getElementById("ttv2DaCredit")) hideChartSlot("cred");
    } catch (e0) {}

    CHART_KEYS.forEach(function (k) {
      updateChartSlot(k, 10, "Loading charts…", false);
    });

    ensureChartJs().then(function (okLoaded) {
      if (!okLoaded || typeof Chart === "undefined") {
        CHART_KEYS.forEach(function (k) {
          updateChartSlot(k, 100, "Chart engine unavailable", true);
        });
        hideAllChartSlots();
        return;
      }

      destroyAll();

      var accent = cssVar("--c-accent", "#6c7dff");
      var ok = "#34d399";
      var pending = "#facc15";
      var warn = "#fb923c";
      var border = cssVar("--c-border", "rgba(255,255,255,.12)");
      var muted = cssVar("--c-text3", "rgba(146,153,176,0.85)");
      Chart.defaults.color = muted;
      Chart.defaults.borderColor = border;
      Chart.defaults.font.family =
        "Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif";

      var ch = data.charts;

      var p = ch.psych_donut || {};
      var pDone = Number(p.completed || 0);
      var pPend = Number(p.pending != null ? p.pending : (p.total || 0) - pDone);
      if (pPend < 0) pPend = 0;
      var psychLabels =
        Array.isArray(p.labels) && p.labels.length >= 2
          ? p.labels
          : ["Completed", "Pending"];

      var sl = ch.sessions_line || {};
      var cl = ch.clarity_line || {};
      var pts = (cl.values || [0, 0, 0, 0]).map(function (v) {
        return Number(v) || 0;
      });

      var r = ch.risk_donut || {};
      var onT = Number(r.on_track || 0);
      var atR = Number(r.at_risk || 0);

      var cr = ch.credit_donut || {};
      var u = Math.max(0, Number(cr.used || 0));
      var l = Math.max(0, Number(cr.left || 0));
      if (u + l < 1) l = 1;

      // Render charts fast (no staged delays). In practice, Chart.js init is sync.
      runChartFast("psych", function () {
      var elP = document.getElementById("ttv2DaPsych");
      if (elP) {
        _charts.psych = new Chart(elP.getContext("2d"), {
          type: "doughnut",
          data: {
            labels: psychLabels,
            datasets: [
              {
                data: [pDone, pPend],
                backgroundColor: [ok, pending],
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
      fillTableBody("ttv2DaTblPsych", toRows(psychLabels, [pDone, pPend]));
      });

      runChartFast("sess", function () {
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
          fillTableBody(
            "ttv2DaTblSess",
            toRows(
              sl.labels && sl.labels.length ? sl.labels : ["—", "—", "—", "—"],
              (sl.values || []).map(function (v) {
                return Number(v) || 0;
              })
            )
          );
      });

      runChartFast("clar", function () {
          var elC = document.getElementById("ttv2DaClarity");
          if (elC) {
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
          fillTableBody(
            "ttv2DaTblClar",
            toRows(cl.labels && cl.labels.length ? cl.labels : ["W1", "W2", "W3", "W4"], pts)
          );
      });

      runChartFast("risk", function () {
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
          fillTableBody("ttv2DaTblRisk", toRows(["On track", "At risk"], [onT, atR]));
      });

      runChartFast("cred", function () {
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
          fillTableBody("ttv2DaTblCred", toRows(["Used", "Left"], [u, l]));
      });

      CHART_KEYS.forEach(function (k) {
        setCardView(k, "chart");
      });
      bindPdfExportOnce();
      clearChartAreaLoading();
    });
  }

  window.ttv2InitDashboardAnalyticsCharts = function () {
    try {
      bindViewToggles();
      init();
    } catch (e) {
      console.error("ttv2 analytics charts", e);
      hideAllChartSlots();
      clearChartAreaLoading();
    }
  };
})();
