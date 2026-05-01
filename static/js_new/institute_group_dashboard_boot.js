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

  function renderIgSimpleTable(tbodyId, rows) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;
    if (!rows || !rows.length) {
      tbody.innerHTML = '<tr><td colspan="2" class="text-muted">No data available</td></tr>';
      return;
    }
    tbody.innerHTML = rows
      .map(function (r) {
        return '<tr><td>' + (r.label || '-') + '</td><td class="text-end">' + (r.value || 0) + '</td></tr>';
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
            backgroundColor: "rgba(63, 55, 201, 0.8)",
            borderColor: "rgba(63, 55, 201, 1)",
            borderWidth: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 700, easing: "easeOutQuart" },
        scales: { y: { beginAtZero: true } },
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

    const labels = institutes.map(function (inst) { return inst.name || "Unknown"; });
    const totals = institutes.map(function (inst) {
      return Number(inst.pcm || 0) + Number(inst.cbm || 0) + Number(inst.comm || 0) + Number(inst.hme || 0) + Number(inst.hmb || 0);
    });
    renderIgSimpleTable("igSeatTableBody", labels.map(function (label, idx) { return { label: label, value: totals[idx] || 0 }; }));

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
          backgroundColor: "rgba(167, 139, 250, 0.85)",
          borderColor: "rgba(139, 92, 246, 1)",
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            ticks: {
              autoSkip: false,
              maxRotation: 90,
              minRotation: 90
            }
          },
          y: { beginAtZero: true }
        },
        plugins: { legend: { display: false } }
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
            backgroundColor: ["rgba(63, 55, 201, 0.8)", "rgba(200, 200, 200, 0.8)"],
            borderColor: ["rgba(63, 55, 201, 1)", "rgba(200, 200, 200, 1)"],
            borderWidth: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 700, easing: "easeOutQuart" },
        plugins: { legend: { position: "bottom" } },
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
            backgroundColor: "rgba(111, 66, 193, 0.8)",
            borderColor: "rgba(111, 66, 193, 1)",
            borderWidth: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 700, easing: "easeOutQuart" },
        scales: { y: { beginAtZero: true } },
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
