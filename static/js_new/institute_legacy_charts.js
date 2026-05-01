/**
 * Institute dashboard legacy charts (psych pie, streams bar, sessions line).
 * Reads JSON from #ttv2-institute-legacy-charts-payload (injected HTML is OK; script tags are not executed).
 * Safe to call multiple times after AJAX partial reload (destroys previous Chart instances).
 */
(function () {
  function destroyIfAny(canvas) {
    if (!canvas || typeof Chart === "undefined") return;
    try {
      var existing = Chart.getChart(canvas);
      if (existing) existing.destroy();
    } catch (e) {}
  }

  function setPsyView(view) {
    try {
      var root = document.querySelector("[data-ttv2-psy]");
      if (!root) return;
      var cw = root.querySelector('[data-ttv2-psy-wrap="chart"]');
      var tw = root.querySelector('[data-ttv2-psy-wrap="table"]');
      if (cw) cw.style.display = view === "chart" ? "" : "none";
      if (tw) tw.style.display = view === "table" ? "" : "none";
      root.querySelectorAll("[data-ttv2-psy-view]").forEach(function (b) {
        var v = (b.getAttribute("data-ttv2-psy-view") || "").trim();
        var on = v === view;
        b.classList.toggle("active", on);
        b.setAttribute("aria-pressed", on ? "true" : "false");
      });
    } catch (e) {}
  }

  function bindPsyToggleOnce() {
    try {
      var root = document.querySelector("[data-ttv2-psy]");
      if (!root || root.getAttribute("data-ttv2-psy-bound") === "1") return;
      root.setAttribute("data-ttv2-psy-bound", "1");
      root.addEventListener("click", function (e) {
        var btn = e.target && e.target.closest ? e.target.closest("[data-ttv2-psy-view]") : null;
        if (!btn) return;
        var v = (btn.getAttribute("data-ttv2-psy-view") || "").trim();
        if (v) setPsyView(v);
      });
      setPsyView("chart");
    } catch (e) {}
  }

  function fillPsyTable(totalStudents, testTaken) {
    try {
      var tb = document.querySelector("[data-ttv2-psy-table-body]");
      if (!tb) return;
      var remaining = Math.max(0, (parseInt(totalStudents, 10) || 0) - (parseInt(testTaken, 10) || 0));
      tb.innerHTML =
        "<tr><td>Taken exam</td><td class=\"text-end\">" +
        (parseInt(testTaken, 10) || 0) +
        "</td></tr>" +
        "<tr><td>Remaining students</td><td class=\"text-end\">" +
        remaining +
        "</td></tr>";
    } catch (e) {}
  }

  function parsePayload() {
    var el = document.getElementById("ttv2-institute-legacy-charts-payload");
    if (!el || !el.textContent) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      console.warn("ttv2InitInstituteLegacyCharts: invalid payload", e);
      return null;
    }
  }

  window.ttv2InitInstituteLegacyCharts = function () {
    var payload = parsePayload();
    if (!payload || typeof Chart === "undefined") return;

    var hasStudents = !!payload.hasStudents;
    var totalStudents = parseInt(payload.totalStudents, 10) || 0;
    var testTaken = parseInt(payload.testTaken, 10) || 0;
    var streams = payload.streams && typeof payload.streams === "object" ? payload.streams : {};
    var sessionsJson = payload.sessionsJson || "[]";

    var personalityCtx = document.getElementById("personality-chart");
    if (personalityCtx && hasStudents) {
      destroyIfAny(personalityCtx);
      new Chart(personalityCtx, {
        type: "pie",
        data: {
          labels: ["Taken exam", "Remaining students"],
          datasets: [
            {
              data: [testTaken, Math.max(0, totalStudents - testTaken)],
              backgroundColor: ["#93c5fd", "#1e3a8a"],
              hoverBackgroundColor: ["#7dd3fc", "#172554"],
              borderWidth: 0,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: "bottom",
              labels: { usePointStyle: true, padding: 16, font: { size: 12, weight: "500" } },
            },
          },
        },
      });
    }
    bindPsyToggleOnce();
    fillPsyTable(totalStudents, testTaken);

    var streamCtx = document.getElementById("stream_chart");
    var streamKeys = Object.keys(streams).filter(function (k) {
      return streams[k] != null;
    });
    if (streamCtx && streamKeys.length > 0) {
      destroyIfAny(streamCtx);
      var streamLabels = [];
      var streamData = [];
      streamKeys.forEach(function (k) {
        streamLabels.push(k);
        streamData.push(Number(streams[k]) || 0);
      });
      var streamColors = [
        "#2563eb",
        "#ec4899",
        "#22c55e",
        "#eab308",
        "#f97316",
        "#8b5cf6",
        "#06b6d4",
      ];
      new Chart(streamCtx, {
        type: "bar",
        data: {
          labels: streamLabels,
          datasets: [
            {
              label: "Students",
              data: streamData,
              backgroundColor: streamLabels.map(function (_, i) {
                return streamColors[i % streamColors.length];
              }),
              borderColor: streamLabels.map(function (_, i) {
                return streamColors[i % streamColors.length];
              }),
              borderWidth: 1,
              borderRadius: 6,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, grid: { color: "rgba(148, 163, 184, 0.2)" } },
            x: { grid: { display: false } },
          },
        },
      });
    }

    var sessionsCtx = document.getElementById("sessionsChart");
    if (!sessionsCtx || !sessionsJson || sessionsJson === "[]") return;
    try {
      var sessionsData = typeof sessionsJson === "string" ? JSON.parse(sessionsJson) : sessionsJson;
      if (
        sessionsData &&
        sessionsData.length > 0 &&
        sessionsData[0].sessions &&
        sessionsData[0].sessions.length > 0
      ) {
        destroyIfAny(sessionsCtx);
        var labels = sessionsData[0].sessions.map(function (s) {
          var date = new Date(s.day);
          return date.toLocaleDateString("en-IN", { day: "numeric", month: "numeric" });
        });
        var totals = sessionsData[0].sessions.map(function (_, dayIndex) {
          return sessionsData.reduce(function (sum, counselor) {
            var row = counselor.sessions && counselor.sessions[dayIndex];
            return sum + (row && row.session_count ? row.session_count : 0);
          }, 0);
        });
        new Chart(sessionsCtx, {
          type: "line",
          data: {
            labels: labels,
            datasets: [
              {
                label: "Number of sessions",
                data: totals,
                borderColor: "#f97316",
                backgroundColor: "rgba(249, 115, 22, 0.08)",
                pointBackgroundColor: "#3b82f6",
                pointBorderColor: "#fff",
                pointBorderWidth: 2,
                pointRadius: 5,
                borderWidth: 2,
                fill: true,
                tension: 0.35,
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
                title: { display: true, text: "Number of sessions", font: { size: 11 } },
                ticks: { stepSize: 1, precision: 0 },
                grid: { color: "rgba(148, 163, 184, 0.25)" },
              },
              x: { grid: { display: false } },
            },
          },
        });
      }
    } catch (e) {
      console.error("ttv2InitInstituteLegacyCharts: sessions chart", e);
    }
  };

  document.addEventListener("DOMContentLoaded", function () {
    if (document.getElementById("ttv2-institute-legacy-charts-payload")) {
      try {
        window.ttv2InitInstituteLegacyCharts();
      } catch (e) {}
    }
  });
})();
