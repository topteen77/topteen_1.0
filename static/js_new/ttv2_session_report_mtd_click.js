/**
 * Session report (v2): click month-to-date week row to load that week.
 * This navigates (non-AJAX) by updating ?ttv2_week_start=YYYY-MM-DD.
 */
(function () {
  if (window.ttv2InitSessionReportMtdWeekClick) return;

  function applyWeek(isoMonday) {
    try {
      var u = new URL(window.location.href);
      if (isoMonday) u.searchParams.set('ttv2_week_start', isoMonday);
      else u.searchParams.delete('ttv2_week_start');
      // Clear date range if present (week drives the report).
      u.searchParams.delete('ttv2_date_start');
      u.searchParams.delete('ttv2_date_end');
      window.location.href = u.toString();
    } catch (e) {}
  }

  function init() {
    document.querySelectorAll('tr[data-ttv2-mtd-week="1"]').forEach(function (tr) {
      if (tr.dataset.ttv2Bound === '1') return;
      tr.dataset.ttv2Bound = '1';
      tr.style.cursor = 'pointer';
      tr.addEventListener('click', function () {
        var wk = (tr.getAttribute('data-ttv2-week-start') || '').trim();
        if (!wk) return;
        applyWeek(wk);
      });
    });
  }

  window.ttv2InitSessionReportMtdWeekClick = init;
  document.addEventListener('ttv2:content:loaded', init);
  document.addEventListener('ttv2:afterAjaxContentLoad', init);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();

