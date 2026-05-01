/**
 * Dashboard date-range dropdown.
 * - Default state: All
 * - Apply writes ?ttv2_date_start=YYYY-MM-DD&ttv2_date_end=YYYY-MM-DD
 * - Reset clears date filters (and legacy week param).
 */
(function () {
  "use strict";

  function getParam(name) {
    try {
      return (new URLSearchParams(window.location.search || "").get(name) || "").trim();
    } catch (e) {
      return "";
    }
  }

  function parseIsoDate(s) {
    if (!s) return null;
    var m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return null;
    var d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
    if (isNaN(d.getTime())) return null;
    d.setHours(0, 0, 0, 0);
    return d;
  }

  function isoDate(d) {
    var y = d.getFullYear();
    var m = String(d.getMonth() + 1).padStart(2, "0");
    var day = String(d.getDate()).padStart(2, "0");
    return y + "-" + m + "-" + day;
  }

  function fmtLabel(startRaw, endRaw) {
    var s = parseIsoDate(startRaw);
    var e = parseIsoDate(endRaw);
    if (!s || !e) return "All";
    var mons = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return (
      String(s.getDate()).padStart(2, "0") +
      " " +
      mons[s.getMonth()] +
      " " +
      s.getFullYear() +
      " – " +
      String(e.getDate()).padStart(2, "0") +
      " " +
      mons[e.getMonth()] +
      " " +
      e.getFullYear()
    );
  }

  function applyRange(startVal, endVal) {
    try {
      var u = new URL(window.location.href);
      if (startVal && endVal) {
        u.searchParams.set("ttv2_date_start", startVal);
        u.searchParams.set("ttv2_date_end", endVal);
      } else {
        u.searchParams.delete("ttv2_date_start");
        u.searchParams.delete("ttv2_date_end");
      }
      // Keep backwards compatibility clean.
      u.searchParams.delete("ttv2_week_start");
      window.location.href = u.toString();
    } catch (e) {}
  }

  function applyWeek(mondayIso) {
    try {
      var u = new URL(window.location.href);
      if (mondayIso) {
        u.searchParams.set("ttv2_week_start", mondayIso);
      } else {
        u.searchParams.delete("ttv2_week_start");
      }
      u.searchParams.delete("ttv2_date_start");
      u.searchParams.delete("ttv2_date_end");
      window.location.href = u.toString();
    } catch (e) {}
  }

  function mondayOf(d) {
    var x = new Date(d.getTime());
    var wd = x.getDay(); // Sun=0
    var diff = (wd + 6) % 7; // Mon=0
    x.setDate(x.getDate() - diff);
    x.setHours(0, 0, 0, 0);
    return x;
  }

  function init() {
    var btn = document.getElementById("ttv2WeekDropdownBtn");
    var menu = document.getElementById("ttv2WeekDropdownMenu");
    if (!btn || !menu) return;
    var iconOnly = btn.getAttribute("data-icon-only") === "1";

    var startVal = getParam("ttv2_date_start");
    var endVal = getParam("ttv2_date_end");

    // Legacy fallback: if only week is selected, prefill a 7-day range.
    if (!(startVal && endVal)) {
      var wk = getParam("ttv2_week_start");
      var wkDate = parseIsoDate(wk);
      if (wkDate) {
        var wkEnd = new Date(wkDate.getTime());
        wkEnd.setDate(wkEnd.getDate() + 6);
        startVal = isoDate(wkDate);
        endVal = isoDate(wkEnd);
      }
    }

    var currentLabel = fmtLabel(startVal, endVal);
    if (!iconOnly) {
      btn.textContent = currentLabel;
    }
    btn.setAttribute("title", "Select date range (" + currentLabel + ")");
    btn.setAttribute("aria-label", "Select date range (" + currentLabel + ")");
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var thisMon = mondayOf(today);
    var lastMon = new Date(thisMon.getTime());
    lastMon.setDate(lastMon.getDate() - 7);
    var prevMon = new Date(thisMon.getTime());
    prevMon.setDate(prevMon.getDate() - 14);
    var thisIso = isoDate(thisMon);
    var lastIso = isoDate(lastMon);
    var prevIso = isoDate(prevMon);

    menu.innerHTML =
      '<li><div class="px-3 pt-2" style="min-width:260px;" data-ttv2-range-box>' +
      '<div class="fw-semibold mb-2" style="font-size:12px;">Quick weeks</div>' +
      '<div class="d-flex flex-wrap gap-2 mb-2">' +
      '<button type="button" class="btn btn-sm btn-outline-secondary" id="ttv2WeekThis">This week</button>' +
      '<button type="button" class="btn btn-sm btn-outline-secondary" id="ttv2WeekLast">Last week</button>' +
      '<button type="button" class="btn btn-sm btn-outline-secondary" id="ttv2WeekPrev">2 weeks ago</button>' +
      '<button type="button" class="btn btn-sm btn-outline-secondary" id="ttv2WeekAll">All</button>' +
      "</div>" +
      '<div class="ttv2-sp-hr" style="margin:10px 0;"></div>' +
      '<div class="fw-semibold mb-2" style="font-size:12px;">Select date range</div>' +
      '<div class="mb-2"><label class="form-label mb-1" style="font-size:11px;">From</label><input type="date" class="form-control form-control-sm" id="ttv2DateStart"></div>' +
      '<div class="mb-2"><label class="form-label mb-1" style="font-size:11px;">To</label><input type="date" class="form-control form-control-sm" id="ttv2DateEnd"></div>' +
      '<div class="d-flex justify-content-between gap-2">' +
      '<button type="button" class="btn btn-sm btn-outline-secondary" id="ttv2DateReset">All</button>' +
      '<button type="button" class="btn btn-sm btn-primary" id="ttv2DateApply">Apply</button>' +
      "</div></div></li>";

    var box = menu.querySelector("[data-ttv2-range-box]");
    var startInput = menu.querySelector("#ttv2DateStart");
    var endInput = menu.querySelector("#ttv2DateEnd");
    var resetBtn = menu.querySelector("#ttv2DateReset");
    var applyBtn = menu.querySelector("#ttv2DateApply");
    var wkThis = menu.querySelector("#ttv2WeekThis");
    var wkLast = menu.querySelector("#ttv2WeekLast");
    var wkPrev = menu.querySelector("#ttv2WeekPrev");
    var wkAll = menu.querySelector("#ttv2WeekAll");
    if (!startInput || !endInput || !resetBtn || !applyBtn) return;

    startInput.value = startVal || "";
    endInput.value = endVal || "";

    if (box && !box.getAttribute("data-ttv2-stop-prop")) {
      box.setAttribute("data-ttv2-stop-prop", "1");
      box.addEventListener("click", function (e) {
        e.stopPropagation();
      });
    }

    if (!applyBtn.getAttribute("data-ttv2-bound")) {
      applyBtn.setAttribute("data-ttv2-bound", "1");
      applyBtn.addEventListener("click", function () {
        var s = (startInput.value || "").trim();
        var e = (endInput.value || "").trim();
        if (!s || !e) return;
        if (s > e) {
          var t = s;
          s = e;
          e = t;
        }
        applyRange(s, e);
      });
    }

    if (!resetBtn.getAttribute("data-ttv2-bound")) {
      resetBtn.setAttribute("data-ttv2-bound", "1");
      resetBtn.addEventListener("click", function () {
        applyRange("", "");
      });
    }

    function bindWeekBtn(el, isoVal) {
      if (!el || el.getAttribute("data-ttv2-bound")) return;
      el.setAttribute("data-ttv2-bound", "1");
      el.addEventListener("click", function () {
        applyWeek(isoVal || "");
      });
    }

    bindWeekBtn(wkThis, thisIso);
    bindWeekBtn(wkLast, lastIso);
    bindWeekBtn(wkPrev, prevIso);
    bindWeekBtn(wkAll, "");
  }

  window.ttv2InitWeekDropdown = function () {
    try {
      init();
    } catch (e) {}
  };

  document.addEventListener("DOMContentLoaded", init);
})();

