(function () {
  'use strict';

  var NS = window.__ttNotificationBell = window.__ttNotificationBell || {};
  NS.tabId = NS.tabId || ('t' + Math.random().toString(36).slice(2, 9));

  if (NS.booted) {
    if (typeof NS.rescan === 'function') {
      NS.rescan();
    }
    return;
  }
  NS.booted = true;

  if (NS.pollId) {
    clearInterval(NS.pollId);
    NS.pollId = null;
  }
  if (NS.leaderHeartbeatId) {
    clearInterval(NS.leaderHeartbeatId);
    NS.leaderHeartbeatId = null;
  }

  var cfg = window.__ttNotificationBellConfig || {};
  var latestUrl = cfg.latestUrl || '';
  var markReadUrl = cfg.markReadUrl || '';
  var markBucketReadUrl = cfg.markBucketReadUrl || '';
  var notificationsPageUrl = cfg.notificationsPageUrl || '';
  var pollMs = parseInt(cfg.pollMs, 10) || 60000;
  var userId = cfg.userId || 'anon';
  var LS_LEADER = 'tt_notif_leader_' + userId;
  var LS_STATE = 'tt_notif_state_' + userId;
  var LEADER_TTL_MS = 25000;

  function csrfToken() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }

  function esc(s) {
    return String(s || '').replace(/[&<>"]/g, function (c) {
      return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c];
    });
  }

  function bellRoots() {
    return Array.prototype.slice.call(document.querySelectorAll('.tt-notification-bell-wrap'));
  }

  function listElements() {
    var lists = [];
    bellRoots().forEach(function (wrap) {
      var listEl = wrap.querySelector('.tt-notification-latest-scroll');
      if (listEl) lists.push(listEl);
    });
    return lists;
  }

  function readLeaderRecord() {
    try {
      var raw = localStorage.getItem(LS_LEADER);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function writeLeaderRecord() {
    try {
      localStorage.setItem(LS_LEADER, JSON.stringify({tabId: NS.tabId, ts: Date.now()}));
    } catch (e) {}
  }

  function isLeader() {
    var now = Date.now();
    var cur = readLeaderRecord();
    if (!cur || now - (cur.ts || 0) > LEADER_TTL_MS) {
      writeLeaderRecord();
      return true;
    }
    if (cur.tabId === NS.tabId) {
      return true;
    }
    return false;
  }

  function publishState(data) {
    try {
      localStorage.setItem(LS_STATE, JSON.stringify({ts: Date.now(), data: data}));
    } catch (e) {}
  }

  function applySharedState() {
    try {
      var raw = localStorage.getItem(LS_STATE);
      if (!raw) return;
      var parsed = JSON.parse(raw);
      if (parsed && parsed.data && parsed.data.success) {
        setBadgeCount(parsed.data.unread_count || 0);
        paintLists(parsed.data);
      }
    } catch (e) {}
  }

  function markRead(id) {
    var fd = new FormData();
    fd.append('id', id);
    return fetch(markReadUrl, {
      method: 'POST',
      headers: {'X-CSRFToken': csrfToken(), 'X-Requested-With': 'XMLHttpRequest'},
      body: fd
    }).then(function (r) { return r.json(); });
  }

  function markBucketRead(bucketKey) {
    var fd = new FormData();
    fd.append('bucket', bucketKey);
    return fetch(markBucketReadUrl, {
      method: 'POST',
      headers: {'X-CSRFToken': csrfToken(), 'X-Requested-With': 'XMLHttpRequest'},
      body: fd
    }).then(function (r) { return r.json(); });
  }

  function setBadgeCount(c) {
    var n = parseInt(c, 10) || 0;
    bellRoots().forEach(function (wrap) {
      var badgeEl = wrap.querySelector('.tt-notification-badge');
      if (!badgeEl) return;
      if (n > 0) {
        badgeEl.classList.add('tt-notification-badge--visible');
        badgeEl.setAttribute('aria-hidden', 'false');
        badgeEl.textContent = n > 99 ? '99+' : String(n);
      } else {
        badgeEl.classList.remove('tt-notification-badge--visible');
        badgeEl.setAttribute('aria-hidden', 'true');
        badgeEl.textContent = '';
      }
      wrap.classList.toggle('tt-notification-bell-wrap--empty', n <= 0);
    });
  }

  function renderSummaryBuckets(buckets, listEl) {
    var rows = (buckets || []).map(function (b) {
      var count = parseInt(b.count, 10) || 0;
      var zeroClass = count > 0 ? '' : ' tt-notification-summary-count--zero';
      var url = b.url || '#';
      var clearAttr = (b.clear_on_click === false) ? '0' : '1';
      return (
        '<a href="' + esc(url) + '" class="tt-notification-summary-row" data-bucket="' + esc(b.key || '') + '" data-url="' + esc(url) + '" data-clear-on-click="' + clearAttr + '">' +
        '<span class="tt-notification-summary-label">' + esc(b.label || '') + '</span>' +
        '<span class="tt-notification-summary-count' + zeroClass + '">' + String(count) + '</span>' +
        '</a>'
      );
    }).join('');
    if (!rows) {
      listEl.innerHTML = '<div class="tt-notification-empty"><i class="bx bx-bell-off"></i> No notifications yet.</div>';
      return;
    }
    listEl.innerHTML = rows;
    listEl.querySelectorAll('a.tt-notification-summary-row').forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.preventDefault();
        var key = el.getAttribute('data-bucket');
        var href = el.getAttribute('data-url') || '#';
        var clearOnClick = el.getAttribute('data-clear-on-click') !== '0';
        function go() { window.location.href = href; }
        if (!clearOnClick) { go(); return; }
        markBucketRead(key).then(function (data) {
          if (data && data.success && typeof data.unread_count === 'number') {
            setBadgeCount(data.unread_count);
          }
          go();
        }).catch(go);
      });
    });
  }

  function render(items, listEl) {
    if (!items.length) {
      listEl.innerHTML = '<div class="tt-notification-empty">No notifications yet.</div>';
      return;
    }
    listEl.innerHTML = items.map(function (n) {
      var pay = n.payload || {};
      var retry = '';
      if (pay.retry_payment_path && pay.show_retry_payment) {
        var rl = esc(pay.retry_payment_label || 'Retry payment');
        retry = '<div class="tt-notification-retry-wrap"><a class="btn btn-sm btn-primary tt-notification-retry" href="' + esc(pay.retry_payment_path) + '">' + rl + '</a></div>';
      }
      var bodyRaw = n.body || '';
      var unreadClass = n.is_read ? '' : ' tt-notification-item--unread';
      var tipText = [n.title || '', bodyRaw].filter(Boolean).join(' — ');
      var tip = esc(tipText);
      return '<div class="tt-notification-item' + unreadClass + '" data-id="' + n.id + '" title="' + tip + '">' +
        '<div class="tt-notification-title">' + esc(n.title) + '</div>' +
        (bodyRaw ? '<div class="tt-notification-body">' + esc(bodyRaw) + '</div>' : '') +
        retry +
        '<div class="tt-notification-meta">' + esc(n.created) + '</div>' +
      '</div>';
    }).join('');
    listEl.querySelectorAll('.tt-notification-item').forEach(function (el) {
      el.addEventListener('click', function (e) {
        if (e.target && e.target.closest && e.target.closest('a.tt-notification-retry')) {
          return;
        }
        e.preventDefault();
        var nid = el.getAttribute('data-id');
        markRead(nid).then(function () {
          return loadLatest(true);
        }).then(function (data) {
          if (data && data.success) setBadgeCount(data.unread_count || 0);
          window.location.href = notificationsPageUrl;
        }).catch(function () {
          window.location.href = notificationsPageUrl;
        });
      });
    });
    listEl.querySelectorAll('a.tt-notification-retry').forEach(function (a) {
      a.addEventListener('click', function (e) {
        e.stopPropagation();
        var row = a.closest('.tt-notification-item');
        if (!row) return;
        markRead(row.getAttribute('data-id')).then(function () {
          return loadLatest(true);
        }).then(function (data) {
          if (data && data.success) setBadgeCount(data.unread_count || 0);
        }).catch(function () {});
      });
    });
  }

  function paintLists(data) {
    var lists = listElements();
    if (!lists.length) return;
    lists.forEach(function (listEl) {
      if (data.summary_mode && data.buckets) {
        renderSummaryBuckets(data.buckets, listEl);
      } else {
        render(data.notifications || [], listEl);
      }
    });
  }

  function loadLatest(force) {
    force = !!force;
    if (!latestUrl) return Promise.resolve();

    if (!force && !isLeader()) {
      applySharedState();
      return Promise.resolve();
    }

    if (NS.latestInflight) {
      return NS.latestInflight;
    }

    var lists = listElements();
    if (!lists.length) return Promise.resolve();

    NS.latestInflight = fetch(latestUrl, {
      headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.success) return data;
        setBadgeCount(data.unread_count || 0);
        paintLists(data);
        publishState(data);
        return data;
      })
      .catch(function () {
        lists.forEach(function (listEl) {
          listEl.innerHTML = '<div class="tt-notification-load-err">Could not load notifications.</div>';
        });
      })
      .finally(function () {
        NS.latestInflight = null;
      });

    return NS.latestInflight;
  }

  function bindDropdownHandlers() {
    bellRoots().forEach(function (wrap) {
      if (wrap.getAttribute('data-tt-bell-bound') === '1') return;
      wrap.setAttribute('data-tt-bell-bound', '1');
      var btn = wrap.querySelector('.tt-notification-bell');
      if (!btn) return;
      btn.addEventListener('shown.bs.dropdown', function () {
        loadLatest(isLeader());
      });
    });
  }

  function ensurePoll() {
    if (!isLeader()) return;
    if (NS.pollId) return;
    NS.pollId = setInterval(function () { loadLatest(); }, pollMs);
  }

  function ensureLeaderHeartbeat() {
    if (NS.leaderHeartbeatId) return;
    NS.leaderHeartbeatId = setInterval(function () {
      if (isLeader()) {
        writeLeaderRecord();
      }
    }, 10000);
  }

  function start() {
    if (NS.started) return;
    NS.started = true;

    bindDropdownHandlers();
    ensureLeaderHeartbeat();

    if (isLeader()) {
      loadLatest();
      ensurePoll();
    } else {
      applySharedState();
    }
  }

  NS.rescan = bindDropdownHandlers;
  NS.loadLatest = loadLatest;

  window.addEventListener('storage', function (e) {
    if (e.key === LS_STATE) {
      applySharedState();
    }
    if (e.key === LS_LEADER && !isLeader() && NS.pollId) {
      clearInterval(NS.pollId);
      NS.pollId = null;
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, {once: true});
  } else {
    start();
  }

  window.addEventListener('pageshow', function () {
    bindDropdownHandlers();
    if (!isLeader()) {
      applySharedState();
    }
  });
})();
