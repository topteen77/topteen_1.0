/**
 * Session report (v2): per-student expandable history cards.
 * Fetches full history from the same page URL via ?data_type=session_history_student&student_id=...
 */
(function () {
  if (window.ttv2InitSessionReportStudents) return;

  function getHistoryUrl(studentId) {
    var u = new URL(window.location.href);
    u.searchParams.set('data_type', 'session_history_student');
    u.searchParams.set('student_id', String(studentId || ''));
    return u.toString();
  }

  function escapeHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function badgeForStatus(st) {
    var v = String(st || '').toLowerCase();
    if (v === 'completed') return 'bg-success';
    if (v === 'pending') return 'bg-warning text-dark';
    return 'bg-info text-dark';
  }

  function renderItems(items) {
    if (!items || !items.length) {
      return '<div class="text-center py-4" style="color:var(--c-text3);font-size:12px;">No session history.</div>';
    }
    return items
      .map(function (r) {
        var when = escapeHtml(r.when || '—');
        var mode = escapeHtml(r.mode || '—');
        var status = escapeHtml(r.status || '—');
        var next = escapeHtml(r.next || '');
        var counselor = escapeHtml(r.counselor || '');
        var msg = escapeHtml(r.message || '');
        return (
          '<div class="ttv2-sr-session">' +
          '<div class="ttv2-sr-dot" aria-hidden="true"></div>' +
          '<div class="ttv2-sr-session-main min-w-0">' +
          '<div class="ttv2-sr-session-top">' +
          '<div class="ttv2-sr-when">' +
          when +
          '</div>' +
          '<div class="ttv2-sr-chips">' +
          (counselor ? '<span class="badge bg-dark">' + counselor + '</span>' : '') +
          '<span class="badge bg-secondary">' +
          mode +
          '</span>' +
          '<span class="badge ' +
          badgeForStatus(status) +
          '">' +
          status +
          '</span>' +
          (next ? '<span class="badge bg-dark">Next: ' + next + '</span>' : '') +
          '</div>' +
          '</div>' +
          (msg ? '<div class="ttv2-sr-msg">' + msg + '</div>' : '') +
          '</div>' +
          '</div>'
        );
      })
      .join('');
  }

  function fetchHistory(studentId) {
    return fetch(getHistoryUrl(studentId), { headers: { 'X-Requested-With': 'XMLHttpRequest' } }).then(function (r) {
      return r.json();
    });
  }

  function initCard(cardEl) {
    if (!cardEl || cardEl.dataset.ttv2SrBound === '1') return;
    cardEl.dataset.ttv2SrBound = '1';

    var studentId = (cardEl.getAttribute('data-student-id') || '').trim();
    var btnToggle = cardEl.querySelector('[data-ttv2-sr-toggle]');
    var btnLoadAll = cardEl.querySelector('[data-ttv2-sr-loadall]');
    var body = cardEl.querySelector('[data-ttv2-sr-body]');
    var loading = cardEl.querySelector('[data-ttv2-sr-loading]');
    var list = cardEl.querySelector('[data-ttv2-sr-sessions]');

    function setOpen(open) {
      if (!body) return;
      body.style.display = open ? '' : 'none';
    }

    function setLoading(on) {
      if (!loading) return;
      loading.style.display = on ? '' : 'none';
    }

    function loadAll() {
      if (!studentId || !list) return;
      if (cardEl.dataset.ttv2SrLoaded === '1') {
        // already loaded once; just ensure open
        setOpen(true);
        return;
      }
      setOpen(true);
      setLoading(true);
      fetchHistory(studentId)
        .then(function (data) {
          if (!data || !data.ok) return;
          cardEl.dataset.ttv2SrLoaded = '1';
          list.innerHTML = renderItems(data.items || []);
          if (btnLoadAll) btnLoadAll.style.display = 'none';
        })
        .catch(function () {})
        .finally(function () {
          setLoading(false);
        });
    }

    if (btnToggle) {
      btnToggle.addEventListener('click', function () {
        var isOpen = body && body.style.display !== 'none';
        setOpen(!isOpen);
      });
    }
    if (btnLoadAll) {
      btnLoadAll.addEventListener('click', function () {
        loadAll();
      });
    }
  }

  function initAll() {
    document.querySelectorAll('[data-ttv2-student-card]').forEach(initCard);
  }

  window.ttv2InitSessionReportStudents = initAll;

  document.addEventListener('ttv2:content:loaded', initAll);
  document.addEventListener('ttv2:afterAjaxContentLoad', initAll);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initAll);
  else initAll();
})();

