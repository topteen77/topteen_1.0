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

  function parseIsoDate(s) {
    if (!s) return null;
    var m = String(s).trim().match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return null;
    var y = Number(m[1]);
    var mo = Number(m[2]);
    var da = Number(m[3]);
    if (!y || mo < 1 || mo > 12 || da < 1 || da > 31) return null;
    var d = new Date(y, mo - 1, da);
    if (isNaN(d.getTime())) return null;
    d.setHours(0, 0, 0, 0);
    return d;
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
    // Match UI reference: "Week of 27-03 May 2026"
    var s = "Week of " + pad2(monday.getDate()) + "-" + pad2(end.getDate()) + " " + months[end.getMonth()] + " " + end.getFullYear();
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

  function buildWeeksForCurrentMonth() {
    var now = new Date();
    now.setHours(0, 0, 0, 0);

    var curMonthStart = new Date(now.getFullYear(), now.getMonth(), 1);
    var curMonthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    var rangeStart = startOfWeekMonday(curMonthStart);
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

  function addMenuItem(menu, text, value, onClick) {
    var li = document.createElement("li");
    var a = document.createElement("a");
    a.href = "#";
    a.className = "dropdown-item";
    a.setAttribute("data-week", value || "");
    a.textContent = text;
    a.addEventListener("click", function (e) {
      e.preventDefault();
      onClick();
    });
    li.appendChild(a);
    menu.appendChild(li);
    return a;
  }

  function init() {
    var btn = document.getElementById("ttv2WeekDropdownBtn");
    var menu = document.getElementById("ttv2WeekDropdownMenu");
    if (!btn || !menu) return;

    // Toggle handling:
    // - Prefer Bootstrap Dropdown API (positions menu with Popper)
    // - Fallback to a minimal "show" class toggle (works even after AJAX DOM swaps)
    if (!btn.getAttribute("data-ttv2-week-toggle-bound")) {
      btn.setAttribute("data-ttv2-week-toggle-bound", "1");
      btn.addEventListener(
        "click",
        function (e) {
          try {
            // If Bootstrap is available, use it.
            if (window.bootstrap && window.bootstrap.Dropdown) {
              e.preventDefault();
              var dd = window.bootstrap.Dropdown.getOrCreateInstance(btn);
              dd.toggle();
              return;
            }
            // Manual toggle
            e.preventDefault();
            e.stopPropagation();
            var open = menu.classList.contains("show");
            if (open) {
              menu.classList.remove("show");
              btn.setAttribute("aria-expanded", "false");
            } else {
              menu.classList.add("show");
              btn.setAttribute("aria-expanded", "true");
            }
          } catch (err) {}
        },
        true
      );
      document.addEventListener(
        "click",
        function () {
          try {
            if (!menu.classList.contains("show")) return;
            menu.classList.remove("show");
            btn.setAttribute("aria-expanded", "false");
          } catch (e) {}
        },
        true
      );
      document.addEventListener(
        "keydown",
        function (e) {
          try {
            if (e.key !== "Escape") return;
            if (!menu.classList.contains("show")) return;
            menu.classList.remove("show");
            btn.setAttribute("aria-expanded", "false");
          } catch (err) {}
        },
        true
      );
    }

    var selected = (getParam("ttv2_week_start") || "").trim();
    var hasWeekSelected = !!selected;
    var selectedDate = parseIsoDate(selected);
    if (selectedDate) {
      selected = isoDate(startOfWeekMonday(selectedDate));
    }

    var weeks = buildWeeksForCurrentMonth();
    if (!weeks.length) return;

    menu.innerHTML = "";

    var matchedSelected = false;
    weeks.forEach(function (monday) {
      var value = isoDate(monday);
      var a = addMenuItem(menu, fmtLabel(monday), value, function () {
        setParamAndReload("ttv2_week_start", value);
      });
      if (hasWeekSelected && value === selected) {
        matchedSelected = true;
        a.classList.add("active");
        btn.textContent = a.textContent;
      }
    });

    // Divider between weeks and "All" (last item)
    var dividerLi = document.createElement("li");
    var hr = document.createElement("hr");
    hr.className = "dropdown-divider";
    dividerLi.appendChild(hr);
    menu.appendChild(dividerLi);

    // "All" option clears the week filter (server treats missing param as overall view).
    var allA = addMenuItem(menu, "All", "", function () {
      setParamAndReload("ttv2_week_start", "");
    });
    if (!hasWeekSelected) {
      allA.classList.add("active");
      btn.textContent = "All";
    }

    // If a week was selected but it's not in the current-month list, still show its label on the button.
    if (hasWeekSelected && !matchedSelected && selectedDate) {
      btn.textContent = fmtLabel(startOfWeekMonday(selectedDate));
    }
  }

  window.ttv2InitWeekDropdown = function () {
    try {
      init();
    } catch (e) {}
  };

  document.addEventListener("DOMContentLoaded", init);
})();

