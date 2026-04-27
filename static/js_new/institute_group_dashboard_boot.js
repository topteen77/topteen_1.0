/**
 * Institute group dashboard: stats, institutes table, Chart.js charts.
 * v1: auto-runs on DOMContentLoaded when not inside the v2 AJAX shell.
 * v2: call window.ttv2BootInstituteGroupDashboard() after #ttv2AjaxContent body is injected.
 */
(function () {
  "use strict";

  function loadStatistics() {
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

  function loadCharts() {
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
          loadSeatCapacityTable(data.seat_capacity_institutes);
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
