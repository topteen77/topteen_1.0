/**
 * Dynamic week dropdown (current + previous month) in week format.
 * Writes ?ttv2_week_start=YYYY-MM-DD (Monday) and reloads the page so server-side
 * analytics payload and charts update accordingly.
 */
(function () {
  "use strict";

  function pad2(n) {
    return n < 10 ? "0" + n : String(n);
  }

  function isoDate(d) {
    return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate());
  }

  function startOfWeekMonday(d) {
    var x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    var day = x.getDay(); // 0..6 (Sun..Sat)
    var diff = day === 0 ? -6 : 1 - day; // move to Monday
    x.setDate(x.getDate() + diff);
    x.setHours(0, 0, 0, 0);
    return x;
  }

  function addDays(d, n) {
    var x = new Date(d.getTime());
    x.setDate(x.getDate() + n);
    return x;
  }

  function fmtLabel(monday) {
    var end = addDays(monday, 6);
    var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    var s = "Week of " + pad2(monday.getDate()) + "–" + pad2(end.getDate()) + " " + months[end.getMonth()] + " " + end.getFullYear();
    return s;
  }

  function getParam(name) {
    try {
      return new URLSearchParams(window.location.search || "").get(name) || "";
    } catch (e) {
      return "";
    }
  }

  function setParamAndReload(name, value) {
    try {
      var url = new URL(window.location.href);
      if (value) url.searchParams.set(name, value);
      else url.searchParams.delete(name);
      // keep hash
      window.location.href = url.toString();
    } catch (e) {}
  }

  function buildWeeksForTwoMonths() {
    var now = new Date();
    now.setHours(0, 0, 0, 0);

    var curMonthStart = new Date(now.getFullYear(), now.getMonth(), 1);
    var prevMonthStart = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    var rangeStart = startOfWeekMonday(prevMonthStart);

    // end at last day of current month
    var curMonthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    var rangeEnd = addDays(startOfWeekMonday(curMonthEnd), 6);

    var weeks = [];
    for (var d = new Date(rangeStart.getTime()); d <= rangeEnd; d = addDays(d, 7)) {
      weeks.push(new Date(d.getTime()));
    }

    // newest first (more convenient)
    weeks.sort(function (a, b) {
      return b.getTime() - a.getTime();
    });
    return weeks;
  }

  function init() {
    var btn = document.getElementById("ttv2WeekDropdownBtn");
    var menu = document.getElementById("ttv2WeekDropdownMenu");
    if (!btn || !menu) return;

    var selected = (getParam("ttv2_week_start") || "").trim();
    if (!selected) {
      selected = isoDate(startOfWeekMonday(new Date()));
    }

    var weeks = buildWeeksForTwoMonths();
    if (!weeks.length) return;

    menu.innerHTML = "";
    weeks.forEach(function (monday) {
      var value = isoDate(monday);
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = "#";
      a.className = "dropdown-item";
      a.setAttribute("data-week", value);
      a.textContent = fmtLabel(monday);
      if (value === selected) {
        a.classList.add("active");
        btn.textContent = a.textContent;
      }
      a.addEventListener("click", function (e) {
        e.preventDefault();
        setParamAndReload("ttv2_week_start", value);
      });
      li.appendChild(a);
      menu.appendChild(li);
    });
  }

  window.ttv2InitWeekDropdown = function () {
    try {
      init();
    } catch (e) {}
  };

  document.addEventListener("DOMContentLoaded", init);
})();

