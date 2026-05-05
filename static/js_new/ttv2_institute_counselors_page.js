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

  function trimCssVar(v, fallback) {
    try {
      var s = (v || '').trim();
      return s || fallback;
    } catch (e) {
      return fallback;
    }
  }

  function hideCounselorsChartsRefreshing() {
    var w = document.getElementById('ttv2CounselorsChartsRefreshWrap');
    if (!w) return;
    w.classList.remove('ttv2-cc--refreshing');
    w.setAttribute('aria-busy', 'false');
  }

  function showCounselorsChartsRefreshing() {
    var w = document.getElementById('ttv2CounselorsChartsRefreshWrap');
    if (!w) return;
    w.classList.add('ttv2-cc--refreshing');
    w.setAttribute('aria-busy', 'true');
  }

  function renderCharts() {
    var root = document.getElementById('sec-institute-counselors');
    if (!root) {
      hideCounselorsChartsRefreshing();
      return;
    }
    var data = readPayload();
    if (!data) {
      hideCounselorsChartsRefreshing();
      return;
    }
    if (!data.line || typeof data.line !== 'object') {
      data.line = { title: '', subtitle: '', labels: [], values: [] };
    }
    if (!data.donut || typeof data.donut !== 'object') {
      data.donut = { counselled: 0, not_counselled: 0 };
    }
    if (!Array.isArray(data.line_table)) data.line_table = [];
    if (!Array.isArray(data.donut_table)) data.donut_table = [];

    var lineEl = document.getElementById('ttv2CounselorsLine');
    var donutEl = document.getElementById('ttv2CounselorsDonut');
    if (!lineEl || !donutEl) {
      hideCounselorsChartsRefreshing();
      return;
    }

    destroyCharts();

    var lineCfg = data.line || {};
    var donut = data.donut || {};
    var labels = lineCfg.labels || [];
    var values = lineCfg.values || [];
    var c1 = trimCssVar(
      getComputedStyle(document.documentElement).getPropertyValue('--c-accent'),
      '#34d399'
    );

    ensureChartJs(function (ok) {
      if (!ok || typeof Chart === 'undefined') {
        hideCounselorsChartsRefreshing();
        return;
      }
      try {
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

      function kickResize() {
        try {
          if (window.__ttv2CounselorCharts.line && window.__ttv2CounselorCharts.line.resize) {
            window.__ttv2CounselorCharts.line.resize();
          }
        } catch (e3) {}
        try {
          if (window.__ttv2CounselorCharts.donut && window.__ttv2CounselorCharts.donut.resize) {
            window.__ttv2CounselorCharts.donut.resize();
          }
        } catch (e4) {}
      }
      function doneLoading() {
        hideCounselorsChartsRefreshing();
      }
      try {
        requestAnimationFrame(function () {
          kickResize();
          setTimeout(function () {
            kickResize();
            requestAnimationFrame(doneLoading);
          }, 72);
        });
      } catch (e5) {
        setTimeout(function () {
          kickResize();
          doneLoading();
        }, 72);
      }
      } catch (chartErr) {
        hideCounselorsChartsRefreshing();
      }
    });
  }

  function mergeCounselorsQueryParams(u, focusId) {
    u.searchParams.set('ttv2_partial', '1');
    if (focusId) u.searchParams.set('focus_counselor', String(focusId));
    else u.searchParams.delete('focus_counselor');
    var rsel = document.getElementById('ttv2CounselorsRange');
    if (rsel && rsel.value) {
      u.searchParams.set('counselors_range', rsel.value);
      if (rsel.value === 'custom') {
        var df = document.getElementById('ttv2CounselorsFrom');
        var dt = document.getElementById('ttv2CounselorsTo');
        if (df && df.value) u.searchParams.set('counselors_from', df.value);
        else u.searchParams.delete('counselors_from');
        if (dt && dt.value) u.searchParams.set('counselors_to', dt.value);
        else u.searchParams.delete('counselors_to');
      } else {
        u.searchParams.delete('counselors_from');
        u.searchParams.delete('counselors_to');
      }
    }
    return u;
  }

  function kickCounselorChartResize() {
    try {
      if (window.__ttv2CounselorCharts.line && window.__ttv2CounselorCharts.line.resize) {
        window.__ttv2CounselorCharts.line.resize();
      }
    } catch (e) {}
    try {
      if (window.__ttv2CounselorCharts.donut && window.__ttv2CounselorCharts.donut.resize) {
        window.__ttv2CounselorCharts.donut.resize();
      }
    } catch (e2) {}
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
    showCounselorsChartsRefreshing();
    mergeCounselorsQueryParams(u, focusId);
    host.setAttribute('aria-busy', 'true');
    fetch(u.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) {
        return r.text();
      })
      .then(function (html) {
        host.innerHTML = html;
        host.setAttribute('aria-busy', 'false');
        showCounselorsChartsRefreshing();
        try {
          if (typeof window.ttv2AfterAjaxContentLoad === 'function') window.ttv2AfterAjaxContentLoad();
        } catch (e2) {}
        try {
          window.dispatchEvent(new CustomEvent('ttv2:afterAjaxContentLoad'));
        } catch (e3) {}
      })
      .catch(function () {
        host.setAttribute('aria-busy', 'false');
        hideCounselorsChartsRefreshing();
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

  function bindCounselorsRange() {
    var rsel = document.getElementById('ttv2CounselorsRange');
    if (!rsel || rsel.getAttribute('data-ttv2-bound') === '1') return;
    rsel.setAttribute('data-ttv2-bound', '1');
    rsel.addEventListener('change', function () {
      var customRow = document.getElementById('ttv2CounselorsCustomDates');
      if (customRow) {
        if (rsel.value === 'custom') customRow.classList.remove('d-none');
        else customRow.classList.add('d-none');
      }
      if (rsel.value !== 'custom') {
        var fsel = document.getElementById('ttv2CounselorFocusSelect');
        reloadPartial(fsel ? fsel.value || '' : '');
      }
    });
    var applyBtn = document.getElementById('ttv2CounselorsRangeApply');
    if (applyBtn && applyBtn.getAttribute('data-ttv2-bound') !== '1') {
      applyBtn.setAttribute('data-ttv2-bound', '1');
      applyBtn.addEventListener('click', function () {
        var fsel = document.getElementById('ttv2CounselorFocusSelect');
        reloadPartial(fsel ? fsel.value || '' : '');
      });
    }
  }

  function bindCounselorsViewToggles() {
    document.querySelectorAll('#sec-institute-counselors [data-ttv2-cc-view]').forEach(function (btn) {
      if (btn.getAttribute('data-ttv2-bound') === '1') return;
      btn.setAttribute('data-ttv2-bound', '1');
      btn.addEventListener('click', function () {
        var bodyId = btn.getAttribute('data-ccard-body');
        if (!bodyId) return;
        var wrap = document.getElementById(bodyId);
        if (!wrap) return;
        var grp = btn.parentElement;
        if (grp) {
          grp.querySelectorAll('[data-ttv2-cc-view]').forEach(function (b) {
            var on = b === btn;
            b.classList.toggle('active', on);
            b.setAttribute('aria-pressed', on ? 'true' : 'false');
          });
        }
        var view = (btn.getAttribute('data-view') || 'chart').toLowerCase();
        var ch = wrap.querySelector('.ttv2-ccard-view-chart');
        var tb = wrap.querySelector('.ttv2-ccard-view-table');
        if (ch) ch.classList.toggle('d-none', view !== 'chart');
        if (tb) tb.classList.toggle('d-none', view !== 'table');
        if (view === 'chart') {
          try {
            requestAnimationFrame(function () {
              kickCounselorChartResize();
              setTimeout(kickCounselorChartResize, 80);
            });
          } catch (e) {
            setTimeout(kickCounselorChartResize, 80);
          }
        }
      });
    });
  }

  window.ttv2InitInstituteCounselorsPage = function () {
    var host = document.getElementById('ttv2AjaxContent');
    var marker = host ? host.querySelector('[data-ttv2-page]') : null;
    var page = marker ? (marker.getAttribute('data-ttv2-page') || '').trim().toLowerCase() : '';
    var sec = document.getElementById('sec-institute-counselors');
    var hasPayload = !!document.getElementById('ttv2-counselors-charts-payload');
    if (page !== 'counselors' && !(sec && hasPayload)) return;
    bindSelect();
    bindCounselorsRange();
    bindCounselorsViewToggles();
    // Defer until after dashboard_shell shows #sec-institute-counselors (layout was 0×0 if we chart too early).
    function runOnce() {
      renderCharts();
    }
    try {
      requestAnimationFrame(runOnce);
    } catch (e) {
      runOnce();
    }
    setTimeout(function () {
      try {
        if (window.__ttv2CounselorCharts.line && window.__ttv2CounselorCharts.line.resize) {
          window.__ttv2CounselorCharts.line.resize();
        }
        if (window.__ttv2CounselorCharts.donut && window.__ttv2CounselorCharts.donut.resize) {
          window.__ttv2CounselorCharts.donut.resize();
        }
      } catch (e2) {}
    }, 150);
  };
})();
