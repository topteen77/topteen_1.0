/**
 * Institute group dashboard: stats, institutes table, Chart.js charts.
 * v1: auto-runs on DOMContentLoaded when not inside the v2 AJAX shell.
 * v2: call window.ttv2BootInstituteGroupDashboard() after #ttv2AjaxContent body is injected.
 */
(function () {
  "use strict";

  function loadStatistics() {
    if (
      !document.getElementById("students-count") &&
      !document.getElementById("counselors-count")
    ) {
      return;
    }
    const url = window.location.pathname + "?data_type=stats";
    fetch(url, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("HTTP error! status: " + response.status);
        }
        return response.json();
      })
      .then(function (data) {
        const studentsCountEl = document.getElementById("students-count");
        const counselorsCountEl = document.getElementById("counselors-count");
        const creditsCountEl = document.getElementById("credits-count");
        const remainingCreditsEl = document.getElementById("remaining-credits-count");
        if (studentsCountEl) studentsCountEl.textContent = data.total_stu_count || 0;
        if (counselorsCountEl) counselorsCountEl.textContent = data.counselors_count || 0;
        if (creditsCountEl) creditsCountEl.textContent = data.total_credits || 0;
        if (remainingCreditsEl) remainingCreditsEl.textContent = data.remaining_credits || 0;
      })
      .catch(function (error) {
        console.error("Error loading statistics:", error);
        ["students-count", "counselors-count", "credits-count", "remaining-credits-count"].forEach(
          function (id) {
            const el = document.getElementById(id);
            if (el) el.textContent = "0";
          }
        );
      });
  }

  function revealIgChartShells() {
    try {
      var bottom = document.getElementById("bottom-charts-section");
      if (bottom) {
        bottom.style.display = "flex";
        bottom.style.visibility = "visible";
      }
    } catch (e) {}
  }

  function _ttv2EscapeHtml(value) {
    if (value === undefined || value === null) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
  function _ttv2FormatNumber(value) {
    const n = Number(value || 0);
    if (!isFinite(n)) return "0";
    return n.toLocaleString();
  }
  function _ttv2MakeBarGradient(ctx, area, colors) {
    if (!ctx || !area) return (colors && colors[0]) || "#6c7dff";
    const c = colors || ["#6c7dff", "#4cc9f0"];
    const isHorizontal = !!(area && area.right > area.left && (area.right - area.left) > (area.bottom - area.top) * 1.2);
    const g = isHorizontal
      ? ctx.createLinearGradient(area.left, 0, area.right, 0)
      : ctx.createLinearGradient(0, area.bottom, 0, area.top);
    g.addColorStop(0, c[0]);
    g.addColorStop(1, c[1]);
    return g;
  }

  /* Chart.js plugin: draw the value at the end of each bar.
     Idempotent registration so this can coexist with the marketing dashboard
     boot script (which registers its own copy under the same id). */
  if (typeof Chart !== "undefined" && Chart && typeof Chart.register === "function" && !window.__ttv2BarLabelsRegistered) {
    const ttv2BarLabelsPlugin = {
      id: "ttv2BarLabels",
      afterDatasetsDraw(chart, _args, opts) {
        if (opts && opts.enabled === false) return;
        const ctx = chart.ctx;
        const horizontal = (chart.options && chart.options.indexAxis === "y");
        ctx.save();
        ctx.font = '600 11px Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
        ctx.fillStyle = (opts && opts.color) || "rgba(15,23,42,0.75)";
        chart.data.datasets.forEach(function (ds, dsIdx) {
          const meta = chart.getDatasetMeta(dsIdx);
          if (!meta || meta.hidden) return;
          meta.data.forEach(function (bar, i) {
            const raw = ds.data && ds.data[i];
            if (raw === undefined || raw === null) return;
            const v = Number(raw);
            if (!v) return;
            const label = v.toLocaleString();
            if (horizontal) {
              ctx.textAlign = "left";
              ctx.textBaseline = "middle";
              ctx.fillText(label, bar.x + 6, bar.y);
            } else {
              ctx.textAlign = "center";
              ctx.textBaseline = "bottom";
              ctx.fillText(label, bar.x, bar.y - 4);
            }
          });
        });
        ctx.restore();
      }
    };
    try { Chart.register(ttv2BarLabelsPlugin); window.__ttv2BarLabelsRegistered = true; } catch (e) {}
  }

  function renderIgSimpleTable(tbodyId, rows) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;
    if (!rows || !rows.length) {
      tbody.innerHTML = '<tr><td colspan="4" class="ttv2-rich-empty">No data available</td></tr>';
      return;
    }
    const max = rows.reduce(function (m, r) { return Math.max(m, Number(r.value || 0)); }, 0) || 1;
    tbody.innerHTML = rows
      .map(function (r, idx) {
        const value = Number(r.value || 0);
        const pct = Math.max(2, Math.round((value / max) * 100));
        const safeLabel = _ttv2EscapeHtml(r.label || "-");
        return (
          "<tr>"
          + '<td><span class="ttv2-rank-pill">#' + (idx + 1) + "</span></td>"
          + '<td class="ttv2-label-cell" title="' + safeLabel + '">' + safeLabel + "</td>"
          + '<td class="ttv2-bar-cell">'
          +   '<div class="ttv2-bar-track" role="progressbar" aria-valuenow="' + value + '" aria-valuemin="0" aria-valuemax="' + max + '">'
          +     '<div class="ttv2-bar-fill" style="width:' + pct + '%"></div>'
          +   "</div>"
          + "</td>"
          + '<td class="ttv2-value-cell"><span class="ttv2-value-chip">' + _ttv2FormatNumber(value) + "</span></td>"
          + "</tr>"
        );
      })
      .join("");
  }

  function setIgGraphView(target, view) {
    const chartWrap = document.querySelector('[data-ig-chart-wrap="' + target + '"]');
    const tableWrap = document.querySelector('[data-ig-table-wrap="' + target + '"]');
    if (!chartWrap || !tableWrap) return;
    const showTable = view === "table";
    chartWrap.style.display = showTable ? "none" : "";
    tableWrap.style.display = showTable ? "" : "none";
    document.querySelectorAll('[data-ig-view-btn][data-target="' + target + '"]').forEach(function (btn) {
      btn.classList.toggle("active", btn.getAttribute("data-view") === view);
    });
  }

  function bindIgGraphViewToggles() {
    if (window._igGraphViewToggleBound) return;
    window._igGraphViewToggleBound = true;
    document.addEventListener("click", function (e) {
      const btn = e.target && (e.target.closest ? e.target.closest("[data-ig-view-btn]") : null);
      if (!btn) return;
      e.preventDefault();
      const target = (btn.getAttribute("data-target") || "").trim();
      const view = (btn.getAttribute("data-view") || "").trim();
      if (!target || !view) return;
      setIgGraphView(target, view);
    });
  }

  function loadCharts() {
    bindIgGraphViewToggles();
    if (!document.getElementById("charts-section")) {
      return;
    }
    const url = window.location.pathname + "?data_type=charts";
    fetch(url, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("HTTP error! status: " + response.status);
        }
        return response.json();
      })
      .then(function (data) {
        revealIgChartShells();
        const chartsSection = document.getElementById("charts-section");
        if (chartsSection) {
          chartsSection.style.display = "block";
          chartsSection.style.visibility = "visible";
        }
        if (data.institutes && data.institutes.length > 0) {
          loadStudentsChart(data.institutes);
        } else {
          const sl = document.getElementById("students-chart-loader");
          if (sl) sl.innerHTML = '<p class="text-gray">No data available</p>';
        }
        if (data.seat_capacity_institutes && data.seat_capacity_institutes.length > 0) {
          loadSeatCapacityDashboardChart(data.seat_capacity_institutes);
        } else {
          const seatCapacityLoader = document.getElementById("seat-capacity-loader");
          const seatCapacitySection = document.getElementById("seat-capacity-section");
          if (seatCapacityLoader && seatCapacitySection) {
            seatCapacitySection.style.display = "block";
            seatCapacityLoader.innerHTML =
              '<p class="text-gray">No seat capacity data available</p>';
          }
        }
        if (data.total_students_count !== undefined && data.test_result_count !== undefined) {
          loadPersonalityChart(data.total_students_count, data.test_result_count);
        } else {
          const pl = document.getElementById("personality-chart-loader");
          if (pl) pl.innerHTML = '<p class="text-gray">No data available</p>';
        }
        if (data.streams_chart_data && data.streams_chart_data.length > 0) {
          loadStreamsChart(data.streams_chart_data);
        } else {
          const streamsLoader = document.getElementById("streams-chart-loader");
          if (streamsLoader) {
            streamsLoader.style.display = "flex";
            streamsLoader.style.alignItems = "center";
            streamsLoader.style.justifyContent = "center";
            streamsLoader.style.minHeight = "300px";
            streamsLoader.innerHTML =
              '<div class="text-center w-100"><i class="bx bx-bar-chart-alt-2" style="font-size: 48px; color: #ccc; margin-bottom: 12px;"></i><p class="text-muted mb-0" style="font-size: 14px;">No stream data available</p></div>';
          }
        }
      })
      .catch(function (error) {
        console.error("Error loading charts:", error);
        revealIgChartShells();
        const cs = document.getElementById("charts-section");
        if (cs) cs.style.display = "block";
        const studentsLoader = document.getElementById("students-chart-loader");
        const personalityLoader = document.getElementById("personality-chart-loader");
        if (studentsLoader) {
          studentsLoader.innerHTML =
            '<p class="text-danger">Error loading chart: ' + (error && error.message ? error.message : "unknown") + "</p>";
        }
        if (personalityLoader) {
          personalityLoader.innerHTML = '<p class="text-danger">Error loading chart</p>';
        }
      });
  }

  function loadStudentsChart(institutes) {
    const loader = document.getElementById("students-chart-loader");
    const canvas = document.getElementById("studentsChart");
    if (!canvas || typeof Chart === "undefined") return;
    const labels = institutes.map(function (inst) {
      return inst.name || "Unknown";
    });
    const values = institutes.map(function (inst) {
      return inst.student_count || 0;
    });
    renderIgSimpleTable("igStudentsTableBody", labels.map(function (label, idx) { return { label: label, value: values[idx] || 0 }; }));
    if (loader) loader.style.display = "none";
    canvas.style.display = "block";
    if (window._igStudentsChartInstance) {
      try {
        window._igStudentsChartInstance.destroy();
      } catch (e) {}
      window._igStudentsChartInstance = null;
    }
    window._igStudentsChartInstance = new Chart(canvas, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Students",
            data: values,
            backgroundColor: function (c) {
              const ch = c && c.chart;
              return _ttv2MakeBarGradient(ch && ch.ctx, ch && ch.chartArea, ["#6c7dff", "#4cc9f0"]);
            },
            hoverBackgroundColor: function (c) {
              const ch = c && c.chart;
              return _ttv2MakeBarGradient(ch && ch.ctx, ch && ch.chartArea, ["#5249DF", "#22d3ee"]);
            },
            borderColor: "transparent",
            borderWidth: 0,
            borderRadius: 8,
            borderSkipped: false,
            categoryPercentage: 0.85,
            barPercentage: 0.85,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 22, right: 4, bottom: 4, left: 4 } },
        animation: { duration: 700, easing: "easeOutQuart" },
        scales: {
          x: {
            ticks: { color: "rgba(15,23,42,0.7)", font: { size: 11, weight: "500" } },
            grid: { display: false, drawBorder: false },
            border: { display: false },
          },
          y: {
            beginAtZero: true,
            ticks: { precision: 0, color: "rgba(15,23,42,0.55)", font: { size: 11 } },
            grid: { color: "rgba(15,23,42,0.06)", drawBorder: false },
            border: { display: false },
          }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "rgba(15,23,42,0.92)",
            padding: 10,
            cornerRadius: 8,
            displayColors: false,
            titleFont: { size: 12, weight: "600" },
            bodyFont: { size: 12 },
            callbacks: {
              label: function (ctx) { return "Students: " + Number(ctx.raw || 0).toLocaleString(); }
            }
          },
          ttv2BarLabels: { enabled: true, color: "rgba(15,23,42,0.75)" }
        }
      },
    });
  }

  function loadSeatCapacityDashboardChart(institutes) {
    const section = document.getElementById("seat-capacity-section");
    const loader = document.getElementById("seat-capacity-loader");
    const wrapper = document.getElementById("seat-capacity-table-wrapper");
    const canvas = document.getElementById("igSeatCapacityDashboardChart");
    if (!section || !canvas) return;

    section.style.display = "block";
    if (!institutes || !institutes.length) {
      if (loader) loader.innerHTML = '<p class="text-gray">No seat capacity data available</p>';
      return;
    }

    const fullLabels = institutes.map(function (inst) { return inst.name || "Unknown"; });
    const labels = fullLabels.map(function (name) {
      return (name && name.length > 18) ? (name.substring(0, 18) + "\u2026") : name;
    });
    const totals = institutes.map(function (inst) {
      return Number(inst.pcm || 0) + Number(inst.cbm || 0) + Number(inst.comm || 0) + Number(inst.hme || 0) + Number(inst.hmb || 0);
    });
    renderIgSimpleTable("igSeatTableBody", fullLabels.map(function (label, idx) { return { label: label, value: totals[idx] || 0 }; }));

    if (loader) loader.style.display = "none";
    if (wrapper) wrapper.style.display = "block";
    canvas.style.display = "block";

    if (window._igSeatCapacityChartInstance) {
      try { window._igSeatCapacityChartInstance.destroy(); } catch (e) {}
      window._igSeatCapacityChartInstance = null;
    }

    window._igSeatCapacityChartInstance = new Chart(canvas, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{
          label: "Total seats",
          data: totals,
          backgroundColor: function (c) {
            const ch = c && c.chart;
            return _ttv2MakeBarGradient(ch && ch.ctx, ch && ch.chartArea, ["#c4b5fd", "#7c3aed"]);
          },
          hoverBackgroundColor: function (c) {
            const ch = c && c.chart;
            return _ttv2MakeBarGradient(ch && ch.ctx, ch && ch.chartArea, ["#a78bfa", "#5b21b6"]);
          },
          borderColor: "transparent",
          borderWidth: 0,
          borderRadius: 8,
          borderSkipped: false,
          categoryPercentage: 0.85,
          barPercentage: 0.85,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 22, right: 4, bottom: 28, left: 4 } },
        animation: { duration: 700, easing: "easeOutQuart" },
        scales: {
          x: {
            ticks: {
              autoSkip: false,
              maxRotation: 60,
              minRotation: 60,
              color: "rgba(15,23,42,0.7)",
              font: { size: 10.5, weight: "500" },
              padding: 4,
            },
            grid: { display: false, drawBorder: false },
            border: { display: false },
          },
          y: {
            beginAtZero: true,
            ticks: { precision: 0, color: "rgba(15,23,42,0.55)", font: { size: 11 } },
            grid: { color: "rgba(15,23,42,0.06)", drawBorder: false },
            border: { display: false },
          }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "rgba(15,23,42,0.92)",
            padding: 10,
            cornerRadius: 8,
            displayColors: false,
            titleFont: { size: 12, weight: "600" },
            bodyFont: { size: 12 },
            callbacks: {
              title: function (items) {
                if (!items || !items.length) return "";
                const idx = items[0].dataIndex;
                return fullLabels[idx] || "";
              },
              label: function (ctx) { return "Seats: " + Number(ctx.raw || 0).toLocaleString(); }
            }
          },
          ttv2BarLabels: { enabled: true, color: "rgba(15,23,42,0.75)" }
        }
      }
    });
  }

  function ttv2LoadInstituteGroupSeatCapacityPage() {
    const section = document.getElementById("seat-capacity-section");
    const tbody = document.getElementById("seat-capacity-tbody");
    if (!section || !tbody) return;
    const url = window.location.pathname + "?data_type=charts";
    fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then(function (response) {
        if (!response.ok) throw new Error("HTTP error! status: " + response.status);
        return response.json();
      })
      .then(function (data) {
        loadSeatCapacityTable((data && data.seat_capacity_institutes) ? data.seat_capacity_institutes : []);
      })
      .catch(function () {
        const loader = document.getElementById("seat-capacity-loader");
        if (loader) loader.innerHTML = '<p class="text-danger">Error loading seat capacity data</p>';
      });
  }

  function loadSeatCapacityTable(institutes) {
    const loader = document.getElementById("seat-capacity-loader");
    const wrapper = document.getElementById("seat-capacity-table-wrapper");
    const tbody = document.getElementById("seat-capacity-tbody");
    const section = document.getElementById("seat-capacity-section");
    if (!tbody || !section) return;
    section.style.display = "block";
    if (loader) loader.style.display = "none";
    if (wrapper) wrapper.style.display = "block";
    tbody.innerHTML = "";
    institutes.forEach(function (inst, index) {
      const row = document.createElement("tr");
      row.innerHTML =
        "<td>" +
        (index + 1) +
        "</td><td>" +
        (inst.name || "-") +
        "</td><td>" +
        (inst.pcm || 0) +
        "</td><td>" +
        (inst.cbm || 0) +
        "</td><td>" +
        (inst.comm || 0) +
        "</td><td>" +
        (inst.hme || 0) +
        "</td><td>" +
        (inst.hmb || 0) +
        "</td>";
      tbody.appendChild(row);
    });
  }

  function loadPersonalityChart(totalStudents, testResultCount) {
    const loader = document.getElementById("personality-chart-loader");
    const canvas = document.getElementById("personalityChart");
    if (!canvas || typeof Chart === "undefined") return;
    const attempted = testResultCount || 0;
    const notAttempted = Math.max(0, (totalStudents || 0) - attempted);
    renderIgSimpleTable("igPsychTableBody", [
      { label: "Attempted", value: attempted },
      { label: "Not Attempted", value: notAttempted },
    ]);
    if (loader) loader.style.display = "none";
    canvas.style.display = "block";
    if (window._igPersonalityChartInstance) {
      try {
        window._igPersonalityChartInstance.destroy();
      } catch (e) {}
      window._igPersonalityChartInstance = null;
    }
    window._igPersonalityChartInstance = new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: ["Attempted", "Not Attempted"],
        datasets: [
          {
            data: [attempted, notAttempted],
            backgroundColor: ["rgba(76, 201, 240, 0.85)", "rgba(108, 125, 255, 0.30)"],
            borderColor: "#ffffff",
            borderWidth: 2,
            hoverOffset: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "62%",
        layout: { padding: 6 },
        animation: { duration: 700, easing: "easeOutQuart" },
        plugins: {
          legend: {
            position: "bottom",
            labels: { boxWidth: 10, boxHeight: 10, font: { size: 11.5, weight: "500" } }
          },
          tooltip: {
            backgroundColor: "rgba(15,23,42,0.92)",
            padding: 10,
            cornerRadius: 8,
            displayColors: false,
            callbacks: {
              label: function (ctx) {
                const total = (ctx.dataset.data || []).reduce(function (a, b) { return a + Number(b || 0); }, 0) || 1;
                const v = Number(ctx.raw || 0);
                const pct = Math.round((v / total) * 100);
                return ctx.label + ": " + v.toLocaleString() + " (" + pct + "%)";
              }
            }
          }
        },
      },
    });
  }

  function loadStreamsChart(streamsData) {
    const loader = document.getElementById("streams-chart-loader");
    const canvas = document.getElementById("streamsChart");
    if (!canvas || typeof Chart === "undefined") return;
    const labels = streamsData.map(function (s) {
      return s.stream || "Unknown";
    });
    const values = streamsData.map(function (s) {
      return s.count || 0;
    });
    renderIgSimpleTable("igStreamsTableBody", labels.map(function (label, idx) { return { label: label, value: values[idx] || 0 }; }));
    if (loader) loader.style.display = "none";
    canvas.style.display = "block";
    if (window._igStreamsChartInstance) {
      try {
        window._igStreamsChartInstance.destroy();
      } catch (e) {}
      window._igStreamsChartInstance = null;
    }
    window._igStreamsChartInstance = new Chart(canvas, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Students",
            data: values,
            backgroundColor: function (c) {
              const ch = c && c.chart;
              return _ttv2MakeBarGradient(ch && ch.ctx, ch && ch.chartArea, ["#a78bfa", "#6366f1"]);
            },
            hoverBackgroundColor: function (c) {
              const ch = c && c.chart;
              return _ttv2MakeBarGradient(ch && ch.ctx, ch && ch.chartArea, ["#8b5cf6", "#4f46e5"]);
            },
            borderColor: "transparent",
            borderWidth: 0,
            borderRadius: 8,
            borderSkipped: false,
            categoryPercentage: 0.85,
            barPercentage: 0.85,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 22, right: 4, bottom: 4, left: 4 } },
        animation: { duration: 700, easing: "easeOutQuart" },
        scales: {
          x: {
            ticks: { color: "rgba(15,23,42,0.7)", font: { size: 11, weight: "500" }, maxRotation: 30, minRotation: 0 },
            grid: { display: false, drawBorder: false },
            border: { display: false },
          },
          y: {
            beginAtZero: true,
            ticks: { precision: 0, color: "rgba(15,23,42,0.55)", font: { size: 11 } },
            grid: { color: "rgba(15,23,42,0.06)", drawBorder: false },
            border: { display: false },
          }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "rgba(15,23,42,0.92)",
            padding: 10,
            cornerRadius: 8,
            displayColors: false,
            titleFont: { size: 12, weight: "600" },
            bodyFont: { size: 12 },
            callbacks: {
              label: function (ctx) { return "Students: " + Number(ctx.raw || 0).toLocaleString(); }
            }
          },
          ttv2BarLabels: { enabled: true, color: "rgba(15,23,42,0.75)" }
        }
      },
    });
  }

  function loadInstitutesTable(url) {
    const loader = document.getElementById("institutes-table-loader");
    const container = document.getElementById("institutes-table-container");
    if (!container) return;
    fetch(url, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("HTTP error! status: " + response.status);
        }
        return response.text();
      })
      .then(function (html) {
        if (loader) loader.style.display = "none";
        container.style.display = "block";
        container.innerHTML = html;
      })
      .catch(function (error) {
        console.error("Error loading institutes table:", error);
        if (loader) loader.innerHTML = '<p class="text-danger">Error loading institutes table</p>';
      });
  }

  function loadInstitutesOnPageLoad() {
    if (!document.getElementById("institutes-table-container")) {
      return;
    }
    const urlObj = new URL(window.location.href);
    urlObj.searchParams.set("data_type", "institutes");
    loadInstitutesTable(urlObj.pathname + urlObj.search);
  }

  function ttv2IgGetCsrfToken() {
    try {
      var name = "csrftoken";
      var cookieValue = null;
      if (document.cookie && document.cookie !== "") {
        var cookies = document.cookie.split(";");
        for (var i = 0; i < cookies.length; i++) {
          var cookie = cookies[i].trim();
          if (cookie.substring(0, name.length + 1) === name + "=") {
            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
            break;
          }
        }
      }
      if (cookieValue) return cookieValue;
      var meta = document.querySelector('meta[name="csrf-token"]');
      if (meta && meta.getAttribute("content")) return meta.getAttribute("content").trim();
      var inp = document.querySelector('input[name="csrfmiddlewaretoken"]');
      if (inp && inp.value) return String(inp.value).trim();
      return "";
    } catch (e) {
      return "";
    }
  }

  /** Visible feedback for institute-group advisor assign/unassign (alerts are often suppressed). */
  window.ttv2IgCounselorFlashMsg = function (msg, variant) {
    var text = msg || "";
    var v = variant || "info";
    var wrap = document.getElementById("ttv2IgCounselorFlash");
    var span = document.getElementById("ttv2IgCounselorFlashText");
    if (!wrap || !span) {
      try {
        window.alert(text);
      } catch (e) {}
      return;
    }
    wrap.classList.remove(
      "d-none",
      "alert-success",
      "alert-danger",
      "alert-warning",
      "alert-info",
      "alert-secondary"
    );
    wrap.classList.add(
      "alert-" +
        (v === "danger"
          ? "danger"
          : v === "success"
            ? "success"
            : v === "warning"
              ? "warning"
              : "info"),
      "show"
    );
    span.textContent = text;
    try {
      wrap.scrollIntoView({ block: "nearest" });
    } catch (e2) {}
    clearTimeout(wrap._ttv2IgFlashT);
    wrap._ttv2IgFlashT = setTimeout(function () {
      try {
        wrap.classList.remove("show");
        wrap.classList.add("d-none");
      } catch (e3) {}
    }, 8000);
  };

  function ttv2IgParseJsonResponse(r) {
    return r.text().then(function (text) {
      var data = {};
      try {
        data = text ? JSON.parse(text) : {};
      } catch (e) {
        data = { ok: false, error: text ? text.slice(0, 200) : "invalid_json" };
      }
      if (!r.ok) {
        data.ok = false;
        data.error = data.error || "HTTP " + r.status;
      }
      return data;
    });
  }

  function ttv2IgUpdateAssignBlockVisibility(actionsWrap) {
    if (!actionsWrap) return;
    var assignBlock = actionsWrap.querySelector("[data-ttv2-ig-assign-block]");
    if (!assignBlock) return;
    var chips = actionsWrap.querySelector("[data-ttv2-ig-assigned-chips]");
    var hasChip =
      chips &&
      chips.querySelector("span.badge[data-counselor-id]");
    assignBlock.classList.toggle("d-none", !!hasChip);
  }

  function reloadIgInstitutesTableKeepingFilters() {
    try {
      var urlObj = new URL(window.location.href);
      urlObj.searchParams.set("data_type", "institutes");
      loadInstitutesTable(urlObj.pathname + urlObj.search);
    } catch (e2) {}
  }

  function ttv2IgAppendAssignedChip(actionsWrap, counselorId, counselorName) {
    var chips = actionsWrap.querySelector("[data-ttv2-ig-assigned-chips]");
    if (!chips) return;
    var sid = String(counselorId);
    if (chips.querySelector('.ttv2-ig-counselor-chip[data-counselor-id="' + sid + '"]')) return;
    var chip = document.createElement("span");
    chip.className = "ttv2-ig-counselor-chip";
    chip.setAttribute("data-counselor-id", sid);
    var nameSpan = document.createElement("span");
    nameSpan.textContent = counselorName || "";
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ttv2-ig-counselor-chip__remove";
    btn.setAttribute("data-ttv2-ig-unassign-chip", "");
    btn.setAttribute("title", "Remove advisor");
    btn.setAttribute("aria-label", "Remove advisor");
    var icon = document.createElement("i");
    icon.className = "bx bx-x";
    btn.appendChild(icon);
    chip.appendChild(nameSpan);
    chip.appendChild(btn);
    chips.appendChild(chip);
    ttv2IgUpdateAssignBlockVisibility(actionsWrap);
  }

  function ttv2IgRemoveAssignedChip(actionsWrap, counselorId) {
    var chips = actionsWrap.querySelector("[data-ttv2-ig-assigned-chips]");
    if (!chips) return;
    var sid = String(counselorId);
    var chip = chips.querySelector('.ttv2-ig-counselor-chip[data-counselor-id="' + sid + '"]');
    if (chip) chip.remove();
    ttv2IgUpdateAssignBlockVisibility(actionsWrap);
  }

  function ttv2IgSyncCounselorsColumn(row, counselorId, counselorName, mode) {
    var cell = row.querySelector("[data-ttv2-ig-counselors-cell]");
    if (!cell) return;
    var sid = String(counselorId);
    if (mode === "add") {
      var ph = cell.querySelector("[data-ttv2-ig-empty-placeholder]");
      if (ph) ph.remove();
      if (!cell.querySelector('[data-counselor-id="' + sid + '"]')) {
        var b = document.createElement("span");
        b.className = "ttv2-ig-counselor-chip ttv2-ig-counselor-chip--readonly";
        b.setAttribute("data-counselor-id", sid);
        b.textContent = counselorName || "";
        cell.appendChild(b);
      }
    } else {
      var el = cell.querySelector('[data-counselor-id="' + sid + '"]');
      if (el) el.remove();
      if (!cell.querySelector("[data-counselor-id]")) {
        var placeholder = document.createElement("span");
        placeholder.className = "ttv2-ig-cell-empty";
        placeholder.setAttribute("data-ttv2-ig-empty-placeholder", "");
        placeholder.textContent = "\u2014";
        cell.appendChild(placeholder);
      }
    }
  }

  function igCounselorDelegatedClickHandler(e) {
    var flashDismiss = e.target.closest("[data-ttv2-ig-flash-dismiss]");
    if (flashDismiss) {
      e.preventDefault();
      var fw = document.getElementById("ttv2IgCounselorFlash");
      if (fw) {
        clearTimeout(fw._ttv2IgFlashT);
        fw.classList.remove("show");
        fw.classList.add("d-none");
      }
      return;
    }

    var apiHost = document.getElementById("ttv2IgCounselorApiHost");
    var instituteUrl =
      apiHost && apiHost.getAttribute("data-institute-url")
        ? apiHost.getAttribute("data-institute-url").trim()
        : "";

    var chipRm = e.target.closest("[data-ttv2-ig-unassign-chip]");
    if (chipRm) {
      e.preventDefault();
      if (!instituteUrl) {
        window.ttv2IgCounselorFlashMsg(
          "Advisor actions are not initialized — refresh this page.",
          "danger"
        );
        return;
      }
      var csrfChip = ttv2IgGetCsrfToken();
      if (!csrfChip) {
        window.ttv2IgCounselorFlashMsg(
          "Missing CSRF token — refresh the page and try again.",
          "danger"
        );
        return;
      }
      var badgeEl = chipRm.closest("span.badge[data-counselor-id]");
      var cidChip = badgeEl ? badgeEl.getAttribute("data-counselor-id") : "";
      var wrapChip = chipRm.closest("[data-ttv2-ig-inst-actions]");
      var slugChip = wrapChip ? wrapChip.getAttribute("data-inst-slug") : "";
      var rowChip = chipRm.closest("tr");
      if (!slugChip || !cidChip) {
        window.ttv2IgCounselorFlashMsg("Could not remove advisor.", "warning");
        return;
      }
      chipRm.setAttribute("disabled", "disabled");
      fetch(instituteUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": csrfChip,
        },
        body: JSON.stringify({
          action: "unassign",
          institute_slug: slugChip,
          counselor_id: parseInt(cidChip, 10),
        }),
      })
        .then(ttv2IgParseJsonResponse)
        .then(function (data) {
          if (!(data && data.ok)) {
            var err = (data && data.error) || "Unassign failed.";
            if (err === "students_assigned") {
              err =
                "Cannot remove: this advisor still has students assigned at this institute.";
            }
            if (err === "last_placement") {
              err =
                "Keep at least one institute assigned to this advisor in your group (add another placement first, then remove from this school).";
            }
            window.ttv2IgCounselorFlashMsg(
              (data && data.message) || err,
              "danger"
            );
          } else {
            window.ttv2IgCounselorFlashMsg(
              "Advisor unassigned from this institute (still available to assign elsewhere).",
              "success"
            );
            if (wrapChip && rowChip && cidChip) {
              ttv2IgRemoveAssignedChip(wrapChip, cidChip);
              ttv2IgSyncCounselorsColumn(rowChip, cidChip, "", "remove");
            }
          }
        })
        .catch(function () {
          window.ttv2IgCounselorFlashMsg("Unassign failed (network error).", "danger");
        })
        .then(function () {
          chipRm.removeAttribute("disabled");
        });
      return;
    }

    var bulkBtn = e.target.closest("#ttv2IgBulkCounselorBtn");
    if (bulkBtn) {
      e.preventDefault();
      var bar = document.getElementById("ttv2IgBulkCounselorBar");
      var sel = document.getElementById("ttv2IgBulkCounselorSelect");
      var bulkUrl =
        ((bar && bar.getAttribute("data-bulk-url")) ||
          (apiHost && apiHost.getAttribute("data-bulk-url")) ||
          "").trim();
      var cid = sel ? String(sel.value || "").trim() : "";
      var csrf = ttv2IgGetCsrfToken();
      if (!csrf) {
        window.ttv2IgCounselorFlashMsg(
          "Missing CSRF token — refresh the page and try again.",
          "danger"
        );
        return;
      }
      if (!bulkUrl || !cid) {
        window.ttv2IgCounselorFlashMsg("Choose a counselor first.", "warning");
        return;
      }
      bulkBtn.disabled = true;
      fetch(bulkUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": csrf,
        },
        body: JSON.stringify({ counselor_id: parseInt(cid, 10) }),
      })
        .then(ttv2IgParseJsonResponse)
        .then(function (data) {
          if (!(data && data.ok)) {
            window.ttv2IgCounselorFlashMsg(
              (data && data.error) || "Bulk assign failed.",
              "danger"
            );
          } else {
            window.ttv2IgCounselorFlashMsg("Advisor assigned across institutes.", "success");
            reloadIgInstitutesTableKeepingFilters();
          }
        })
        .catch(function () {
          window.ttv2IgCounselorFlashMsg("Bulk assign failed (network error).", "danger");
        })
        .then(function () {
          bulkBtn.disabled = false;
        });
      return;
    }

    var assignBtn = e.target.closest("[data-ttv2-ig-assign-btn]");
    if (assignBtn) {
      e.preventDefault();
      if (!instituteUrl) {
        window.ttv2IgCounselorFlashMsg(
          "Advisor actions are not initialized — refresh this page.",
          "danger"
        );
        return;
      }
      var csrf2 = ttv2IgGetCsrfToken();
      if (!csrf2) {
        window.ttv2IgCounselorFlashMsg(
          "Missing CSRF token — refresh the page and try again.",
          "danger"
        );
        return;
      }
      var wrap = assignBtn.closest("[data-ttv2-ig-inst-actions]");
      var slug = wrap ? wrap.getAttribute("data-inst-slug") : "";
      var row = assignBtn.closest("tr");
      var asel = wrap ? wrap.querySelector("[data-ttv2-ig-assign-select]") : null;
      var cid2 = asel ? String(asel.value || "").trim() : "";
      if (!slug || !cid2) {
        window.ttv2IgCounselorFlashMsg("Choose a counselor to assign.", "warning");
        return;
      }
      assignBtn.disabled = true;
      fetch(instituteUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": csrf2,
        },
        body: JSON.stringify({
          action: "assign",
          institute_slug: slug,
          counselor_id: parseInt(cid2, 10),
        }),
      })
        .then(ttv2IgParseJsonResponse)
        .then(function (data) {
          if (!(data && data.ok)) {
            window.ttv2IgCounselorFlashMsg(
              (data && data.error) || "Assign failed.",
              "danger"
            );
          } else {
            window.ttv2IgCounselorFlashMsg("Advisor assigned.", "success");
            if (wrap && row && data.counselor_id != null) {
              var nm =
                typeof data.counselor_name === "string"
                  ? data.counselor_name
                  : "";
              if (!nm && asel && asel.options && asel.selectedIndex >= 0) {
                nm = (
                  asel.options[asel.selectedIndex].textContent || ""
                ).trim();
              }
              ttv2IgAppendAssignedChip(wrap, data.counselor_id, nm);
              ttv2IgSyncCounselorsColumn(row, data.counselor_id, nm, "add");
            }
            if (asel) asel.selectedIndex = 0;
          }
        })
        .catch(function () {
          window.ttv2IgCounselorFlashMsg("Assign failed (network error).", "danger");
        })
        .then(function () {
          assignBtn.disabled = false;
        });
      return;
    }
  }

  function attachIgCounselorDelegationOnce() {
    if (!document.body) return;
    if (document.body.dataset.ttv2IgCounselorDelegated === "1") return;
    document.body.dataset.ttv2IgCounselorDelegated = "1";
    document.body.addEventListener("click", igCounselorDelegatedClickHandler, true);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", attachIgCounselorDelegationOnce);
  } else {
    attachIgCounselorDelegationOnce();
  }

  function bindInstituteFilterFormOnce() {
    const searchForm = document.getElementById("institute-filter-form");
    if (!searchForm || searchForm.getAttribute("data-ttv2-ig-bound") === "1") {
      return;
    }
    searchForm.setAttribute("data-ttv2-ig-bound", "1");
    searchForm.addEventListener("submit", function (e) {
      e.preventDefault();
      const formData = new FormData(this);
      const urlObj = new URL(window.location.href);
      urlObj.searchParams.set("data_type", "institutes");
      formData.forEach(function (value, key) {
        if (value) {
          urlObj.searchParams.set(key, value);
        }
      });
      loadInstitutesTable(urlObj.pathname + urlObj.search);
      try {
        window.history.pushState({}, "", urlObj.pathname + urlObj.search);
      } catch (err) {}
    });
  }

  window.ttv2BootInstituteGroupDashboard = function () {
    if (window._ttv2InstituteGroupDashboardBooted) {
      return;
    }
    window._ttv2InstituteGroupDashboardBooted = true;
    revealIgChartShells();
    loadStatistics();
    loadInstitutesOnPageLoad();
    loadCharts();
    ttv2LoadInstituteGroupSeatCapacityPage();
    bindInstituteFilterFormOnce();
  };

  document.addEventListener("DOMContentLoaded", function () {
    if (document.getElementById("ttv2AjaxContent")) {
      return;
    }
    if (typeof window.ttv2BootInstituteGroupDashboard === "function") {
      window.ttv2BootInstituteGroupDashboard();
    }
  });
})();
