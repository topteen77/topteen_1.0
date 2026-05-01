/**
 * Career analytics (counselor v2): Chart.js boot for AJAX-injected partials.
 *
 * IMPORTANT: dashboard_shell.html injects page partials via innerHTML; scripts inside the
 * injected HTML won't execute. This file provides a persistent initializer that runs
 * after each injection event and on initial load.
 *
 * Expects:
 * - <script type="application/json" id="ttv2-career-analytics-payload">…</script>
 * - <canvas id="ttv2CaClusterDonut"></canvas>
 * - <canvas id="ttv2CaIvK"></canvas>
 */
(function () {
  if (window.ttv2InitCareerAnalyticsCharts) return;

  var _chartJsPromise = null;

  function readPayload() {
    try {
      var el = document.getElementById("ttv2-career-analytics-payload");
      if (!el) return null;
      return JSON.parse(el.textContent || "{}");
    } catch (e) {
      return null;
    }
  }

  function ensureChartJs() {
    if (typeof Chart !== "undefined") return Promise.resolve(true);
    if (_chartJsPromise) return _chartJsPromise;
    _chartJsPromise = new Promise(function (resolve) {
      try {
        var existing = document.getElementById("ttv2-chartjs");
        if (existing) {
          setTimeout(function () {
            resolve(typeof Chart !== "undefined");
          }, 60);
          return;
        }
        var s = document.createElement("script");
        s.id = "ttv2-chartjs";
        // Pinned UMD build for global `Chart`
        s.src = "https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js";
        s.async = true;
        s.onload = function () {
          resolve(typeof Chart !== "undefined");
        };
        s.onerror = function () {
          resolve(false);
        };
        document.head.appendChild(s);
      } catch (e2) {
        resolve(false);
      }
    });
    return _chartJsPromise;
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

  function destroyCareerCharts() {
    try {
      var prev = window.__ttv2CareerCharts || {};
      Object.keys(prev).forEach(function (k) {
        try {
          if (prev[k] && prev[k].destroy) prev[k].destroy();
        } catch (e) {}
      });
    } catch (e0) {}
    window.__ttv2CareerCharts = {};
  }

  function setCardView(target, view) {
    try {
      var chartWrap = document.querySelector('[data-ttv2-chart-wrap="' + target + '"]');
      var tableWrap = document.querySelector('[data-ttv2-table-wrap="' + target + '"]');
      if (!chartWrap || !tableWrap) return;
      var showTable = view === "table";
      chartWrap.style.display = showTable ? "none" : "";
      tableWrap.style.display = showTable ? "" : "none";
      document.querySelectorAll('[data-ttv2-view-btn][data-target="' + target + '"]').forEach(function (btn) {
        var active = (btn.getAttribute("data-view") || "").trim() === view;
        btn.classList.toggle("active", active);
      });
    } catch (e) {}
  }

  function bindViewTogglesOnce() {
    if (window.__ttv2CareerAnalyticsViewBound) return;
    window.__ttv2CareerAnalyticsViewBound = true;
    document.addEventListener(
      "click",
      function (e) {
        var btn = e.target && (e.target.closest ? e.target.closest("[data-ttv2-view-btn]") : null);
        if (!btn) return;
        var target = (btn.getAttribute("data-target") || "").trim();
        var view = (btn.getAttribute("data-view") || "").trim();
        if (!target || !view) return;
        // Only handle our targets.
        if (target !== "ca_cluster" && target !== "ca_ivk") return;
        e.preventDefault();
        setCardView(target, view);
      },
      true
    );
  }

  function syncCanvasSize(cv) {
    try {
      if (!cv) return;
      var wrap = cv.parentElement;
      if (!wrap) return;
      var w = Math.max(1, wrap.clientWidth || 0);
      var h = Math.max(1, wrap.clientHeight || 0);
      if (w > 1 && h > 1) {
        if (cv.width !== w) cv.width = w;
        if (cv.height !== h) cv.height = h;
      }
    } catch (e) {}
  }

  function initCharts() {
    var payload = readPayload();
    if (!payload) return;

    var donut = document.getElementById("ttv2CaClusterDonut");
    var bar = document.getElementById("ttv2CaIvK");
    if (!donut && !bar) return;

    // Ensure chart view is visible by default.
    setCardView("ca_cluster", "chart");
    setCardView("ca_ivk", "chart");
    bindViewTogglesOnce();

    ensureChartJs().then(function (ok) {
      if (!ok || typeof Chart === "undefined") return;

      var muted = cssVar("--c-text3", "rgba(146,153,176,0.85)");
      var border = cssVar("--c-border", "rgba(255,255,255,.12)");
      Chart.defaults.color = muted;
      Chart.defaults.borderColor = border;
      Chart.defaults.font.family =
        "Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif";

      destroyCareerCharts();

      if (donut) {
        try {
          syncCanvasSize(donut);
          var d = payload.cluster_donut || {};
          var labels = Array.isArray(d.labels) ? d.labels : [];
          var values = Array.isArray(d.values) ? d.values : [];
          if (!labels.length) labels = ["No data"];
          if (!values.length) values = [0];
          window.__ttv2CareerCharts.cluster = new Chart(donut.getContext("2d"), {
            type: "doughnut",
            data: {
              labels: labels,
              datasets: [
                {
                  data: values,
                  backgroundColor: ["#6c7dff", "#34d399", "#a78bfa", "#fb923c", "#f472b6", "#fbbf24"],
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
        } catch (e1) {}
      }

      if (bar) {
        try {
          syncCanvasSize(bar);
          var b = payload.ivk_bar || {};
          window.__ttv2CareerCharts.ivk = new Chart(bar.getContext("2d"), {
            type: "bar",
            data: {
              labels: b.labels || ["General stream"],
              datasets: [
                {
                  label: "Interest",
                  data: b.interest || [0],
                  backgroundColor: "rgba(108,125,255,0.65)",
                  borderWidth: 0,
                  borderRadius: 10,
                },
                {
                  label: "Knowledge",
                  data: b.knowledge || [0],
                  backgroundColor: "rgba(52,211,153,0.65)",
                  borderWidth: 0,
                  borderRadius: 10,
                },
                {
                  label: "Alignment",
                  data: b.alignment || [0],
                  backgroundColor: "rgba(99,102,241,0.35)",
                  borderWidth: 0,
                  borderRadius: 10,
                },
              ],
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: { legend: { position: "bottom", labels: { boxWidth: 10 } } },
              scales: { y: { beginAtZero: true, max: 100 } },
            },
          });
        } catch (e2) {}
      }
    });
  }

  window.ttv2InitCareerAnalyticsCharts = function () {
    try {
      initCharts();
    } catch (e) {}
  };

  // Initial boot (non-AJAX) + AJAX injected partial boots.
  document.addEventListener("ttv2:content:loaded", window.ttv2InitCareerAnalyticsCharts);
  document.addEventListener("ttv2:afterAjaxContentLoad", window.ttv2InitCareerAnalyticsCharts);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", window.ttv2InitCareerAnalyticsCharts);
  } else {
    window.ttv2InitCareerAnalyticsCharts();
  }
})();

