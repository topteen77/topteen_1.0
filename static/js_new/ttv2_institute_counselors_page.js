/**
 * Institute v2 Counselors page: Chart.js (session activity + coverage) + partial reload on counselor focus.
 */
(function () {
  function getCookie(name) {
    try {
      var m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
      return m ? decodeURIComponent(m[2]) : null;
    } catch (e) {
      return null;
    }
  }

  function ensureChartJs(cb) {
    if (typeof Chart !== 'undefined') return cb(true);
    var existing = document.querySelector('script[data-ttv2-chartjs]');
    if (existing) return setTimeout(function () { cb(typeof Chart !== 'undefined'); }, 80);
    var s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js';
    s.async = true;
    s.setAttribute('data-ttv2-chartjs', '1');
    s.onload = function () { cb(typeof Chart !== 'undefined'); };
    s.onerror = function () { cb(false); };
    document.head.appendChild(s);
  }

  function destroyCharts() {
    try {
      if (window.__ttv2CounselorCharts) {
        Object.keys(window.__ttv2CounselorCharts).forEach(function (k) {
          try {
            window.__ttv2CounselorCharts[k].destroy();
          } catch (e) {}
        });
      }
    } catch (e) {}
    window.__ttv2CounselorCharts = {};
  }

  function readPayload() {
    var el = document.getElementById('ttv2-counselors-charts-payload');
    if (!el) return null;
    try {
      return JSON.parse(el.textContent || '{}');
    } catch (e) {
      return null;
    }
  }

  function renderCharts() {
    var root = document.getElementById('sec-institute-counselors');
    if (!root) return;
    var data = readPayload();
    if (!data || !data.line) return;

    var lineEl = document.getElementById('ttv2CounselorsLine');
    var donutEl = document.getElementById('ttv2CounselorsDonut');
    if (!lineEl || !donutEl) return;

    destroyCharts();

    var lineCfg = data.line || {};
    var donut = data.donut || {};
    var labels = lineCfg.labels || [];
    var values = lineCfg.values || [];
    var c1 = getComputedStyle(document.documentElement).getPropertyValue('--c-accent') || '#34d399';
    var c2 = getComputedStyle(document.documentElement).getPropertyValue('--c-text3') || '#64748b';

    ensureChartJs(function (ok) {
      if (!ok || typeof Chart === 'undefined') return;
      var g = Chart.defaults.color;
      try {
        Chart.defaults.color = getComputedStyle(document.body).color || '#94a3b8';
      } catch (e) {}

      window.__ttv2CounselorCharts.line = new Chart(lineEl.getContext('2d'), {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'Sessions',
              data: values,
              borderColor: c1,
              backgroundColor: 'rgba(52, 211, 153, 0.12)',
              fill: true,
              tension: 0.25,
              pointRadius: 3,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, ticks: { precision: 0 } },
            x: { ticks: { maxRotation: 0, autoSkip: true } },
          },
        },
      });

      var cd = parseInt(donut.counselled, 10) || 0;
      var nd = parseInt(donut.not_counselled, 10) || 0;
      window.__ttv2CounselorCharts.donut = new Chart(donutEl.getContext('2d'), {
        type: 'doughnut',
        data: {
          labels: ['Counselled', 'Remaining'],
          datasets: [
            {
              data: [cd, nd],
              backgroundColor: [c1, 'rgba(148, 163, 184, 0.25)'],
              borderWidth: 0,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '68%',
          plugins: {
            legend: { position: 'bottom', labels: { boxWidth: 10 } },
          },
        },
      });

      try {
        Chart.defaults.color = g;
      } catch (e2) {}
    });
  }

  function reloadPartial(focusId) {
    var host = document.getElementById('ttv2AjaxContent');
    if (!host) return;
    var u;
    try {
      u = new URL(window.location.href);
    } catch (e) {
      return;
    }
    u.searchParams.set('ttv2_partial', '1');
    if (focusId) u.searchParams.set('focus_counselor', String(focusId));
    else u.searchParams.delete('focus_counselor');
    host.setAttribute('aria-busy', 'true');
    fetch(u.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) {
        return r.text();
      })
      .then(function (html) {
        host.innerHTML = html;
        host.setAttribute('aria-busy', 'false');
        try {
          if (typeof window.ttv2AfterAjaxContentLoad === 'function') window.ttv2AfterAjaxContentLoad();
        } catch (e2) {}
        try {
          window.dispatchEvent(new CustomEvent('ttv2:afterAjaxContentLoad'));
        } catch (e3) {}
      })
      .catch(function () {
        host.setAttribute('aria-busy', 'false');
      });
  }

  function bindSelect() {
    var sel = document.getElementById('ttv2CounselorFocusSelect');
    if (!sel || sel.getAttribute('data-ttv2-bound') === '1') return;
    sel.setAttribute('data-ttv2-bound', '1');
    sel.addEventListener('change', function () {
      reloadPartial(sel.value || '');
    });
  }

  window.ttv2InitInstituteCounselorsPage = function () {
    var host = document.getElementById('ttv2AjaxContent');
    var marker = host ? host.querySelector('[data-ttv2-page]') : null;
    var page = marker ? (marker.getAttribute('data-ttv2-page') || '').trim().toLowerCase() : '';
    if (page !== 'counselors') return;
    bindSelect();
    renderCharts();
  };
})();
