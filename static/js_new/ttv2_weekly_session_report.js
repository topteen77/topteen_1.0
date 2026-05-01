/* Weekly session report widget (v2): chart/table toggle + AJAX fetch.
   Expects Chart.js loaded globally and counselor dashboard endpoint supports ?data_type=sessions.
*/

(function () {
  var _chartJsPromise = null;

  function ensureChartJs() {
    if (typeof Chart !== 'undefined') return Promise.resolve(true);
    if (_chartJsPromise) return _chartJsPromise;
    _chartJsPromise = new Promise(function (resolve) {
      try {
        var existing = document.getElementById('ttv2-chartjs');
        if (existing) {
          setTimeout(function () { resolve(typeof Chart !== 'undefined'); }, 60);
          return;
        }
        var s = document.createElement('script');
        s.id = 'ttv2-chartjs';
        // Pinned UMD build for consistent global `Chart`.
        s.src = 'https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js';
        s.async = true;
        s.onload = function () { resolve(typeof Chart !== 'undefined'); };
        s.onerror = function () { resolve(false); };
        document.head.appendChild(s);
      } catch (e) {
        resolve(false);
      }
    });
    return _chartJsPromise;
  }

  function fetchSessionsJson() {
    try {
      var url = new URL(window.location.href);
      url.searchParams.set('data_type', 'sessions');
      // Optional: show student-wise series in chart/table (top N students for week).
      var group = (url.searchParams.get('ttv2_sess_group') || '').trim().toLowerCase();
      if (!group) {
        try {
          if ((window.location.pathname || '').indexOf('/session-report/') !== -1) group = 'student';
        } catch (e0) {}
      }
      if (group) url.searchParams.set('group', group);
      return fetch(url.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } }).then(function (r) {
        return r.json();
      });
    } catch (e) {
      return Promise.reject(e);
    }
  }

  function buildTable(widgetEl, sessionsData) {
    var headRow = widgetEl.querySelector('[data-ttv2-sess-table-head]');
    var body = widgetEl.querySelector('[data-ttv2-sess-table-body]');
    if (!headRow || !body) return;

    var counselors = sessionsData || [];
    var names = counselors.map(function (c) {
      return (c && (c.series_name || c.counselor_name))
        ? String(c.series_name || c.counselor_name)
        : 'Series';
    });
    var dates = [];
    try {
      if (counselors[0] && counselors[0].sessions) {
        dates = counselors[0].sessions.map(function (s) { return s.day; });
      }
    } catch (e) { dates = []; }

    // header
    headRow.innerHTML = '';
    var thDate = document.createElement('th');
    thDate.textContent = 'Date';
    headRow.appendChild(thDate);
    names.forEach(function (nm) {
      var th = document.createElement('th');
      th.className = 'text-end';
      th.textContent = nm;
      headRow.appendChild(th);
    });
    if (names.length > 1) {
      var thTot = document.createElement('th');
      thTot.className = 'text-end';
      thTot.textContent = 'Total';
      headRow.appendChild(thTot);
    }

    // body rows
    body.innerHTML = '';
    dates.forEach(function (d, idx) {
      var tr = document.createElement('tr');
      var tdD = document.createElement('td');
      tdD.textContent = d || '-';
      tr.appendChild(tdD);

      var total = 0;
      counselors.forEach(function (c) {
        var n = 0;
        try { n = parseInt((c.sessions && c.sessions[idx] && c.sessions[idx].session_count) || 0, 10) || 0; } catch (e) { n = 0; }
        total += n;
        var td = document.createElement('td');
        td.className = 'text-end';
        td.textContent = String(n);
        tr.appendChild(td);
      });

      if (names.length > 1) {
        var tdT = document.createElement('td');
        tdT.className = 'text-end fw-semibold';
        tdT.textContent = String(total);
        tr.appendChild(tdT);
      }
      body.appendChild(tr);
    });
  }

  function renderChart(widgetEl, sessionsData) {
    var canvas = widgetEl.querySelector('[data-ttv2-sess-canvas]');
    if (!canvas || typeof Chart === 'undefined') return;
    var ctx = canvas.getContext('2d');
    if (!ctx) return;

    // destroy previous chart if any
    try {
      if (canvas.__ttv2Chart && typeof canvas.__ttv2Chart.destroy === 'function') {
        canvas.__ttv2Chart.destroy();
      }
    } catch (e) {}

    var counselors = sessionsData || [];
    var labels = [];
    try {
      labels = (counselors[0] && counselors[0].sessions) ? counselors[0].sessions.map(function (s) { return s.day; }) : [];
    } catch (e) { labels = []; }

    var palette = ['#ff758c', '#11998e', '#667eea', '#3357FF', '#89f7fe', '#9B59B6', '#E67E22'];
    var datasets = counselors.map(function (c, i) {
      var data = [];
      try { data = (c.sessions || []).map(function (s) { return s.session_count || 0; }); } catch (e) { data = []; }
      var col = palette[i % palette.length];
      return {
        label: String(c.series_name || c.counselor_name || 'Series'),
        data: data,
        backgroundColor: col,
        borderColor: col,
        borderWidth: 1,
      };
    });

    canvas.__ttv2Chart = new Chart(ctx, {
      type: 'bar',
      data: { labels: labels, datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              stepSize: 1,
              callback: function (value) { return Number.isInteger(value) ? value : null; }
            },
            title: { display: true, text: 'Number of Sessions' }
          },
          x: { title: { display: true, text: 'Date' } }
        },
        plugins: {
          legend: { position: 'top' }
        }
      }
    });
  }

  function setView(widgetEl, view) {
    var chartWrap = widgetEl.querySelector('[data-ttv2-sess-chart-wrap]');
    var tableWrap = widgetEl.querySelector('[data-ttv2-sess-table-wrap]');
    if (!chartWrap || !tableWrap) return;
    var isTable = view === 'table';
    chartWrap.style.display = isTable ? 'none' : 'block';
    tableWrap.style.display = isTable ? 'block' : 'none';

    widgetEl.querySelectorAll('button[data-ttv2-sess-view]').forEach(function (btn) {
      var v = btn.getAttribute('data-ttv2-sess-view');
      if (v === view) btn.classList.add('active'); else btn.classList.remove('active');
    });
  }

  function initWidget(widgetEl) {
    if (!widgetEl || widgetEl.dataset.ttv2SessInited === '1') return;
    widgetEl.dataset.ttv2SessInited = '1';

    var loader = widgetEl.querySelector('[data-ttv2-sess-loader]');
    function showLoader(on) {
      if (!loader) return;
      loader.style.display = on ? 'block' : 'none';
    }

    setView(widgetEl, 'chart');

    widgetEl.addEventListener('click', function (e) {
      var btn = e.target && e.target.closest ? e.target.closest('button[data-ttv2-sess-view]') : null;
      if (!btn) return;
      e.preventDefault();
      setView(widgetEl, (btn.getAttribute('data-ttv2-sess-view') || 'chart').trim());
    });

    showLoader(true);
    ensureChartJs()
      .then(function () { return fetchSessionsJson(); })
      .then(function (data) {
        var sessionsData = (data && data.sessions_data) ? data.sessions_data : [];
        if (!sessionsData.length || !(sessionsData[0] && sessionsData[0].sessions && sessionsData[0].sessions.length)) {
          // simple empty state
          var chartWrap = widgetEl.querySelector('[data-ttv2-sess-chart-wrap]');
          if (chartWrap) {
            chartWrap.innerHTML = '<div class="text-center py-4" style="color:var(--c-text3);font-size:12px;">No session data for this period yet.</div>';
          }
          var body = widgetEl.querySelector('[data-ttv2-sess-table-body]');
          if (body) body.innerHTML = '<tr><td colspan="5" class="text-center py-4" style="color:var(--c-text3);font-size:12px;">No session data for this period yet.</td></tr>';
          return;
        }
        renderChart(widgetEl, sessionsData);
        buildTable(widgetEl, sessionsData);
      })
      .catch(function () {
        var chartWrap = widgetEl.querySelector('[data-ttv2-sess-chart-wrap]');
        if (chartWrap) {
          chartWrap.innerHTML = '<div class="text-center py-4 text-danger" style="font-size:12px;">Could not load sessions.</div>';
        }
      })
      .finally(function () {
        showLoader(false);
      });
  }

  function initAll() {
    document.querySelectorAll('[data-ttv2-weekly-sessions]').forEach(initWidget);
  }

  // Expose for AJAX body reinits (v2 loads body via fetch)
  try { window.ttv2InitWeeklySessionReport = initAll; } catch (e) {}

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
})();

