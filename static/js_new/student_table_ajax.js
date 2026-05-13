/**
 * Centralized AJAX functions for loading student tables across different roles
 * This can be used by institute, counselor, marketing group admin, etc.
 */

/**
 * Load student table via AJAX
 * @param {string} url - The URL to fetch student table data from
 * @param {Object} options - Configuration options
 * @param {string} options.containerId - ID of the container element (default: 'students-table-container')
 * @param {string} options.loaderId - ID of the loader element (default: 'students-loader')
 * @param {string} options.wrapperId - ID of the wrapper element (default: 'students-table-wrapper')
 * @param {Function} options.onSuccess - Callback function called on successful load
 * @param {Function} options.onError - Callback function called on error
 */
function loadStudentsTable(url, options = {}) {
  const config = {
    containerId: options.containerId || 'students-table-container',
    loaderId: options.loaderId || 'students-loader',
    wrapperId: options.wrapperId || 'students-table-wrapper',
    onSuccess: options.onSuccess || null,
    onError: options.onError || null,
  };

  const tableContainer = document.getElementById(config.containerId);
  const loader = document.getElementById(config.loaderId);
  const wrapper = document.getElementById(config.wrapperId);

  if (!tableContainer && !wrapper) {
    console.error('Student table container or wrapper not found');
    if (config.onError) config.onError('Container not found');
    return;
  }

  // Show loader, hide table
  if (loader) loader.style.display = 'block';
  if (tableContainer) tableContainer.style.display = 'none';
  if (wrapper) wrapper.style.display = 'none';

  // Ensure data_type is in URL for AJAX requests
  let ajaxUrl = url;
  if (!ajaxUrl.includes('data_type=')) {
    ajaxUrl += (ajaxUrl.includes('?') ? '&' : '?') + 'data_type=students';
  }

  console.log('Loading students from:', ajaxUrl);

  fetch(ajaxUrl, {
    headers: {
      'X-Requested-With': 'XMLHttpRequest',
    }
  })
    .then(response => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return response.text();
    })
    .then(html => {
      // Hide loader
      if (loader) loader.style.display = 'none';

      // Update table content
      if (wrapper) {
        wrapper.innerHTML = html;
        wrapper.style.display = 'block';
      } else if (tableContainer) {
        tableContainer.innerHTML = html;
        tableContainer.style.display = 'block';
      }

      // v2 roster header: show count for current filters/search (matches paginator total, not unscoped org total).
      try {
        var hostEl = wrapper || tableContainer;
        var inj = hostEl
          ? (hostEl.querySelector && hostEl.querySelector('#students-table-container'))
          : null;
        if (!inj && tableContainer && tableContainer.id === 'students-table-container') {
          inj = tableContainer;
        }
        var n = inj && inj.getAttribute ? inj.getAttribute('data-ttv2-roster-total') : null;
        var countEl = document.getElementById('ttv2-students-roster-count');
        if (countEl && n !== null && n !== undefined && String(n).length) {
          countEl.textContent = String(n);
        }
      } catch (eCount) {}

      // Re-initialize student row hover if function exists
      if (typeof initializeStudentRowHover === 'function') {
        initializeStudentRowHover();
      }
      if (typeof initializeStudentRowHandlers === 'function') {
        initializeStudentRowHandlers();
      }

      // Re-initialize tooltips if function exists
      if (typeof initTooltips === 'function') {
        initTooltips();
      }

      // Institute v2: re-bind advisor change/unassign controls after AJAX inject.
      // (Injected HTML scripts won't run; bindings must happen here.)
      try {
        if (typeof window !== 'undefined' && typeof window.ttv2InitAdvisorChangeControls === 'function') {
          window.ttv2InitAdvisorChangeControls();
        }
      } catch (e0) {}

      // Counselor remarks: bind save buttons (delegated).
      try {
        if (typeof window !== 'undefined' && typeof window.ttv2InitCounselorRemarksControls === 'function') {
          window.ttv2InitCounselorRemarksControls();
        }
      } catch (e1) {}

      // Counselor follow-up (modal): bind open + submit handlers.
      try {
        if (typeof window !== 'undefined' && typeof window.ttv2InitCounselorFollowUpControls === 'function') {
          window.ttv2InitCounselorFollowUpControls();
        }
      } catch (eF) {}

      // Institute/admin: follow-up history timeline viewer.
      try {
        if (typeof window !== 'undefined' && typeof window.ttv2InitFollowUpHistoryViewer === 'function') {
          window.ttv2InitFollowUpHistoryViewer();
        }
      } catch (eH) {}

      // Call success callback
      if (config.onSuccess) {
        config.onSuccess(html);
      }
    })
    .catch(error => {
      console.error('Error loading students table:', error);
      
      // Hide loader
      if (loader) loader.style.display = 'none';
      
      // Show error message
      const errorMsg = 'Error loading students. Please refresh the page.';
      if (wrapper) {
        wrapper.innerHTML = `<div class="alert alert-danger">${errorMsg}</div>`;
        wrapper.style.display = 'block';
      } else if (tableContainer) {
        tableContainer.innerHTML = `<div class="alert alert-danger">${errorMsg}</div>`;
        tableContainer.style.display = 'block';
      }

      // Call error callback
      if (config.onError) {
        config.onError(error);
      }
    });
}

function ttv2GetCookie(name) {
  try {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      var cookies = document.cookie.split(';');
      for (var i = 0; i < cookies.length; i++) {
        var cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  } catch (e) {
    return null;
  }
}

/**
 * Grid cards: assign / unassign advisor (delegated on document.body, capture phase).
 */
function ttv2BindAdvCardDelegatedActionsOnce() {
  if (typeof document === 'undefined') return;
  if (document.body.dataset.ttv2AdvCardDelegated === '1') return;
  document.body.dataset.ttv2AdvCardDelegated = '1';

  document.body.addEventListener(
    'click',
    function (e) {
      var assignBtn =
        e.target && e.target.closest
          ? e.target.closest('[data-ttv2-adv-card-assign]')
          : null;
      if (assignBtn) {
        e.preventDefault();
        e.stopPropagation();
        var wrap = assignBtn.closest('.ttv2-adv-card-assign-wrap');
        var sel = wrap ? wrap.querySelector('[data-ttv2-adv-card-select]') : null;
        var url = assignBtn.getAttribute('data-set-url') || '#';
        var smId = assignBtn.getAttribute('data-sm-id');
        var counselorId = sel ? String(sel.value || '').trim() : '';
        if (!url || url === '#' || !smId || !counselorId) {
          try {
            alert('Choose an advisor to assign.');
          } catch (x) {}
          return;
        }
        var csrftoken =
          typeof ttv2GetCookie === 'function' ? ttv2GetCookie('csrftoken') : '';
        assignBtn.disabled = true;
        fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': csrftoken || '',
          },
          body: JSON.stringify({
            student_management_id: smId,
            counselor_id: counselorId,
          }),
        })
          .then(function (r) {
            return r.json().catch(function () {
              return { ok: false };
            });
          })
          .then(function (data) {
            if (!(data && data.ok)) {
              try {
                alert(data && data.error ? data.error : 'Assign failed');
              } catch (e2) {}
            } else if (
              typeof window.ttv2InitStudentTableAfterBodyInject === 'function'
            ) {
              window.ttv2InitStudentTableAfterBodyInject();
            }
          })
          .catch(function () {
            try {
              alert('Assign failed');
            } catch (e4) {}
          })
          .then(function () {
            assignBtn.disabled = false;
          });
        return;
      }

      var unBtn =
        e.target && e.target.closest
          ? e.target.closest('[data-ttv2-adv-card-unassign]')
          : null;
      if (!unBtn) return;
      e.preventDefault();
      e.stopPropagation();
      var url = unBtn.getAttribute('data-set-url') || '#';
      var smId = unBtn.getAttribute('data-sm-id');
      if (!url || url === '#' || !smId) return;
      var csrftoken =
        typeof ttv2GetCookie === 'function' ? ttv2GetCookie('csrftoken') : '';
      fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrftoken || '',
        },
        body: JSON.stringify({ student_management_id: smId, counselor_id: '' }),
      })
        .then(function (r) {
          return r.json().catch(function () {
            return { ok: false };
          });
        })
        .then(function (data) {
          if (!(data && data.ok)) {
            try {
              alert(data && data.error ? data.error : 'Unassign failed');
            } catch (e2) {}
          } else if (
            typeof window.ttv2InitStudentTableAfterBodyInject === 'function'
          ) {
            window.ttv2InitStudentTableAfterBodyInject();
          }
        })
        .catch(function () {
          try {
            alert('Unassign failed');
          } catch (e4) {}
        });
    },
    true
  );
}

function ttv2InitCounselorRemarksControls() {
  if (document.body.dataset.ttv2RemarksBound === '1') return;
  document.body.dataset.ttv2RemarksBound = '1';

  document.body.addEventListener('click', function (e) {
    var btn = e.target && e.target.closest ? e.target.closest('[data-ttv2-remark-save]') : null;
    if (!btn) return;
    var smId = (btn.getAttribute('data-sm-id') || '').trim();
    if (!smId) return;

    var container = document.getElementById('students-table-container');
    var url = container ? (container.getAttribute('data-ttv2-remark-url') || '').trim() : '';
    if (!url || url === '#') return;

    var ta = document.querySelector('textarea[data-ttv2-remark-text][data-sm-id="' + smId + '"]');
    var statusEl = document.querySelector('[data-ttv2-remark-status][data-sm-id="' + smId + '"]');
    var msg = ta ? (ta.value || '').trim() : '';
    if (!msg) {
      if (statusEl) statusEl.textContent = 'Please type a remark.';
      return;
    }
    if (statusEl) statusEl.textContent = 'Saving...';
    btn.disabled = true;

    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': ttv2GetCookie('csrftoken') || ''
      },
      body: JSON.stringify({ student_management_id: smId, message: msg })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data || !data.success) throw new Error((data && data.error) || 'Save failed');
        if (statusEl) statusEl.textContent = 'Saved.';
        // Update "Last" message inline (simple refresh by reloading table not required).
        try {
          var cell = btn.closest('td');
          if (cell) {
            var lastMsg = cell.querySelector('div[style*="white-space:pre-wrap"]');
            if (lastMsg) lastMsg.textContent = data.message || msg;
            var lastWhen = cell.querySelector('div[style*="font-size:11px"]');
            if (lastWhen && data.when) lastWhen.textContent = 'Last: ' + data.when;
          }
        } catch (e2) {}
        if (ta) ta.value = '';
      })
      .catch(function () {
        if (statusEl) statusEl.textContent = 'Failed to save.';
      })
      .finally(function () {
        btn.disabled = false;
      });
  });
}

try {
  window.ttv2InitCounselorRemarksControls = ttv2InitCounselorRemarksControls;
} catch (e0) {}

function ttv2InitCounselorFollowUpControls() {
  if (document.body.dataset.ttv2FollowUpBound === '1') return;
  document.body.dataset.ttv2FollowUpBound = '1';

  function autoSizeFollowupTextarea(el) {
    if (!el) return;
    try {
      var maxHeight = 220;
      el.style.height = 'auto';
      var nextHeight = Math.min(el.scrollHeight || 0, maxHeight);
      el.style.height = Math.max(nextHeight, 112) + 'px';
      el.style.overflowY = (el.scrollHeight || 0) > maxHeight ? 'auto' : 'hidden';
    } catch (e0) {}
  }

  function getFollowupUrl() {
    var container = document.getElementById('students-table-container');
    return container ? (container.getAttribute('data-ttv2-followup-url') || '').trim() : '';
  }

  function formatDateLabel(rawValue) {
    var value = (rawValue || '').trim();
    if (!value) return '-';
    try {
      var dt = new Date(value + 'T00:00:00');
      if (!isNaN(dt.getTime())) {
        return dt.toLocaleDateString('en-GB', {
          day: '2-digit',
          month: 'short',
          year: 'numeric'
        });
      }
    } catch (e0) {}
    return value;
  }

  function normalizeFollowupLabel(rawValue, fallback) {
    var value = (rawValue || '').trim();
    if (!value) return fallback || '-';
    return value
      .split(/[-_\s]+/)
      .filter(Boolean)
      .map(function (part) {
        return part.charAt(0).toUpperCase() + part.slice(1);
      })
      .join(' ');
  }

  function openModal(smId, studentName, details) {
    if (typeof bootstrap === 'undefined' || !bootstrap.Modal) return;
    var modalEl = document.getElementById('ttv2FollowUpModal');
    if (!modalEl) return;

    var titleEl = document.getElementById('ttv2FollowUpModalTitle');
    var smInp = document.getElementById('ttv2FollowUpSmId');
    var modeEl = document.getElementById('ttv2FollowUpMode');
    var statusEl = document.getElementById('ttv2FollowUpStatus');
    var lastEl = document.getElementById('ttv2FollowUpLastDate');
    var nextEl = document.getElementById('ttv2FollowUpNextDate');
    var msgEl = document.getElementById('ttv2FollowUpMessage');
    var chkEl = document.getElementById('ttv2FollowUpIsFollowed');
    var stEl = document.getElementById('ttv2FollowUpFormStatus');
    var saveBtn = document.getElementById('ttv2FollowUpSaveBtn');
    var currentWrap = document.getElementById('ttv2FollowUpCurrentWrap');
    var emptyState = document.getElementById('ttv2FollowUpEmptyState');
    var currentLabel = document.getElementById('ttv2FollowUpCurrentLabel');
    var currentMode = document.getElementById('ttv2FollowUpCurrentMode');
    var currentStatus = document.getElementById('ttv2FollowUpCurrentStatus');
    var currentLast = document.getElementById('ttv2FollowUpCurrentLastDate');
    var currentNext = document.getElementById('ttv2FollowUpCurrentNextDate');
    var currentMsgWrap = document.getElementById('ttv2FollowUpCurrentMessageWrap');
    var currentMsg = document.getElementById('ttv2FollowUpCurrentMessage');
    var mode = details && details.mode ? String(details.mode).trim() : '';
    var status = details && details.status ? String(details.status).trim() : '';
    var lastDate = details && details.lastDate ? String(details.lastDate).trim() : '';
    var nextDate = details && details.nextDate ? String(details.nextDate).trim() : '';
    var message = details && details.message ? String(details.message) : '';
    var smartLabel = details && details.smartLabel ? String(details.smartLabel).trim() : '';
    var isFollowed = !!(details && details.isFollowed);
    var hasExisting = !!(mode || status || lastDate || nextDate || message || isFollowed);

    if (titleEl) {
      var titleTextEl = titleEl.querySelector ? titleEl.querySelector('span') : null;
      if (titleTextEl) titleTextEl.textContent = 'Follow up - ' + (studentName || 'Student');
      else titleEl.textContent = 'Follow up - ' + (studentName || 'Student');
    }
    if (smInp) smInp.value = String(smId || '');
    if (modeEl) modeEl.value = mode;
    if (statusEl) statusEl.value = status;
    if (lastEl) lastEl.value = lastDate;
    if (nextEl) nextEl.value = nextDate;
    if (msgEl) msgEl.value = message;
    autoSizeFollowupTextarea(msgEl);
    if (chkEl) chkEl.checked = isFollowed;
    if (stEl) stEl.textContent = '';
    if (saveBtn) saveBtn.disabled = false;
    if (currentWrap) currentWrap.hidden = !hasExisting;
    if (emptyState) emptyState.hidden = hasExisting;
    if (currentLabel) currentLabel.textContent = normalizeFollowupLabel(smartLabel, 'Saved');
    if (currentMode) currentMode.textContent = normalizeFollowupLabel(mode, '-');
    if (currentStatus) currentStatus.textContent = normalizeFollowupLabel(status, isFollowed ? 'Completed' : '-');
    if (currentLast) currentLast.textContent = formatDateLabel(lastDate);
    if (currentNext) currentNext.textContent = formatDateLabel(nextDate);
    if (currentMsgWrap) currentMsgWrap.hidden = !message;
    if (currentMsg) currentMsg.textContent = message || '';

    bootstrap.Modal.getOrCreateInstance(modalEl).show();
  }

  document.body.addEventListener('input', function (e) {
    var textarea = e.target;
    if (!textarea || textarea.id !== 'ttv2FollowUpMessage') return;
    autoSizeFollowupTextarea(textarea);
  }, true);

  function reloadRoster() {
    try {
      if (typeof loadStudentsTable !== 'function') return;
      var url = new URL(window.location.href);
      url.searchParams.delete('ttv2_partial');
      url.searchParams.set('data_type', 'students');
      loadStudentsTable(url.toString());
    } catch (e) {}
  }

  document.body.addEventListener('click', function (e) {
    var btn = e.target && e.target.closest ? e.target.closest('[data-ttv2-followup-open]') : null;
    if (!btn) return;
    e.preventDefault();

    var smId = (btn.getAttribute('data-sm-id') || '').trim();
    if (!smId) return;
    var studentName = (btn.getAttribute('data-student-name') || '').trim();
    openModal(smId, studentName, {
      mode: (btn.getAttribute('data-ttv2-followup-mode') || '').trim(),
      status: (btn.getAttribute('data-ttv2-followup-status') || '').trim(),
      lastDate: (btn.getAttribute('data-ttv2-followup-last-date') || '').trim(),
      nextDate: (btn.getAttribute('data-ttv2-followup-next-date') || '').trim(),
      message: btn.getAttribute('data-ttv2-followup-message') || '',
      smartLabel: (btn.getAttribute('data-ttv2-followup-label') || '').trim(),
      isFollowed: (btn.getAttribute('data-ttv2-followup-is-followed') || '').trim() === '1'
    });
  }, true);

  document.body.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form || form.id !== 'ttv2FollowUpForm') return;
    e.preventDefault();

    var url = getFollowupUrl();
    if (!url || url === '#') return;

    var smInp = document.getElementById('ttv2FollowUpSmId');
    var modeEl = document.getElementById('ttv2FollowUpMode');
    var statusEl = document.getElementById('ttv2FollowUpStatus');
    var lastEl = document.getElementById('ttv2FollowUpLastDate');
    var nextEl = document.getElementById('ttv2FollowUpNextDate');
    var msgEl = document.getElementById('ttv2FollowUpMessage');
    var chkEl = document.getElementById('ttv2FollowUpIsFollowed');
    var stEl = document.getElementById('ttv2FollowUpFormStatus');
    var saveBtn = document.getElementById('ttv2FollowUpSaveBtn');

    var smId = smInp ? (smInp.value || '').trim() : '';
    var mode = modeEl ? (modeEl.value || '').trim() : '';
    var status = statusEl ? (statusEl.value || '').trim() : '';
    if (!smId || !mode || !status) {
      if (stEl) stEl.textContent = 'Please select mode and status.';
      return;
    }
    if (stEl) stEl.textContent = 'Saving...';
    if (saveBtn) saveBtn.disabled = true;

    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': ttv2GetCookie('csrftoken') || ''
      },
      body: JSON.stringify({
        student_management_id: smId,
        mode_of_follow_up: mode,
        follow_up_status: status,
        last_follow_up_date: lastEl ? (lastEl.value || '') : '',
        next_follow_up_date: nextEl ? (nextEl.value || '') : '',
        message: msgEl ? (msgEl.value || '') : '',
        is_followed_up: chkEl ? !!chkEl.checked : false
      })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data || !data.success) throw new Error((data && data.error) || 'Save failed');
        if (stEl) stEl.textContent = 'Saved.';
        try {
          var modalEl = document.getElementById('ttv2FollowUpModal');
          if (modalEl && typeof bootstrap !== 'undefined' && bootstrap.Modal) {
            bootstrap.Modal.getOrCreateInstance(modalEl).hide();
          }
        } catch (e0) {}
        reloadRoster();
      })
      .catch(function () {
        if (stEl) stEl.textContent = 'Failed to save.';
      })
      .finally(function () {
        if (saveBtn) saveBtn.disabled = false;
      });
  }, true);
}

try {
  window.ttv2InitCounselorFollowUpControls = ttv2InitCounselorFollowUpControls;
} catch (e0) {}

function ttv2InitFollowUpHistoryViewer() {
  if (document.body.dataset.ttv2FollowUpHistoryBound === '1') return;
  document.body.dataset.ttv2FollowUpHistoryBound = '1';

  function getHistoryUrl(smId) {
    var u = new URL(window.location.href);
    u.searchParams.set('data_type', 'session_history_student');
    u.searchParams.set('student_id', String(smId || ''));
    return u.toString();
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function badgeForStatus(status) {
    var normalized = String(status || '').toLowerCase();
    if (normalized === 'completed') return 'bg-success';
    if (normalized === 'pending') return 'bg-warning text-dark';
    return 'bg-info text-dark';
  }

  function iconForMode(mode) {
    var normalized = String(mode || '').toLowerCase();
    if (normalized === 'email') return 'bx-envelope';
    if (normalized === 'meeting') return 'bx-group';
    return 'bx-phone-call';
  }

  function renderItems(items) {
    if (!items || !items.length) return '';
    return items
      .map(function (item) {
        var when = escapeHtml(item.when || '—');
        var counselor = escapeHtml(item.counselor || '');
        var mode = escapeHtml(item.mode || '—');
        var status = escapeHtml(item.status || '—');
        var next = escapeHtml(item.next || '');
        var message = escapeHtml(item.message || '');
        var modeIcon = iconForMode(item.mode || '');
        return (
          '<div class="ttv2-sr-session">' +
            '<div class="ttv2-sr-dot" aria-hidden="true"></div>' +
            '<div class="ttv2-sr-session-main min-w-0">' +
              '<div class="ttv2-sr-card">' +
                '<div class="ttv2-sr-session-top">' +
                  '<div class="ttv2-sr-when">' + when + '</div>' +
                  '<div class="ttv2-sr-chips">' +
                    (counselor ? '<span class="badge ttv2-sr-badge ttv2-sr-badge--advisor"><i class="bx bx-user-circle"></i><span>' + counselor + '</span></span>' : '') +
                    '<span class="badge ttv2-sr-badge ttv2-sr-badge--mode"><i class="bx ' + modeIcon + '"></i><span>' + mode + '</span></span>' +
                    '<span class="badge ttv2-sr-badge ' + badgeForStatus(status) + '"><span>' + status + '</span></span>' +
                    (next ? '<span class="badge ttv2-sr-badge ttv2-sr-badge--next"><i class="bx bx-calendar-event"></i><span>Next: ' + next + '</span></span>' : '') +
                  '</div>' +
                '</div>' +
                (message ? '<div class="ttv2-sr-msg"><div class="ttv2-sr-msg-label">Latest note</div><div class="ttv2-sr-msg-text">' + message + '</div></div>' : '') +
              '</div>' +
            '</div>' +
          '</div>'
        );
      })
      .join('');
  }

  function setModalLoading(isLoading) {
    var loading = document.getElementById('ttv2FollowUpHistoryLoading');
    if (loading) loading.hidden = !isLoading;
  }

  function setModalEmpty(isEmpty, titleText, bodyText) {
    var empty = document.getElementById('ttv2FollowUpHistoryEmpty');
    if (!empty) return;
    empty.hidden = !isEmpty;
    var titleEl = empty.querySelector('.ttv2-followup-history-empty-title');
    var bodyEl = empty.querySelector('.ttv2-followup-history-empty-text');
    if (titleEl && titleText) titleEl.textContent = titleText;
    if (bodyEl && bodyText) bodyEl.textContent = bodyText;
  }

  function setModalTimeline(html, hasItems) {
    var timeline = document.getElementById('ttv2FollowUpHistoryTimeline');
    if (!timeline) return;
    timeline.innerHTML = hasItems ? html : '';
    timeline.hidden = !hasItems;
  }

  document.body.addEventListener('click', function (e) {
    var btn = e.target && e.target.closest ? e.target.closest('[data-ttv2-followup-history-open]') : null;
    if (!btn) return;
    e.preventDefault();

    var modalEl = document.getElementById('ttv2FollowUpHistoryModal');
    if (!modalEl || typeof bootstrap === 'undefined' || !bootstrap.Modal) return;

    var smId = (btn.getAttribute('data-sm-id') || '').trim();
    if (!smId) return;

    var studentName = (btn.getAttribute('data-student-name') || '').trim() || 'Student';
    var titleEl = document.getElementById('ttv2FollowUpHistoryModalTitle');
    if (titleEl) {
      var titleTextEl = titleEl.querySelector ? titleEl.querySelector('span') : null;
      if (titleTextEl) titleTextEl.textContent = 'Follow-up history - ' + studentName;
      else titleEl.textContent = 'Follow-up history - ' + studentName;
    }

    setModalTimeline('', false);
    setModalEmpty(false, '', '');
    setModalLoading(true);
    bootstrap.Modal.getOrCreateInstance(modalEl).show();

    fetch(getHistoryUrl(smId), {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        var items = data && data.items ? data.items : [];
        if (!data || !data.ok) throw new Error('Failed to load history');
        if (!items.length) {
          setModalTimeline('', false);
          setModalEmpty(
            true,
            'No follow-up history yet',
            'Timeline entries will appear here after counselors add follow-up notes.'
          );
          return;
        }
        setModalEmpty(false, '', '');
        setModalTimeline(renderItems(items), true);
      })
      .catch(function () {
        setModalTimeline('', false);
        setModalEmpty(
          true,
          'Unable to load follow-up history',
          'Please try again in a moment.'
        );
      })
      .finally(function () {
        setModalLoading(false);
      });
  }, true);
}

try {
  window.ttv2InitFollowUpHistoryViewer = ttv2InitFollowUpHistoryViewer;
} catch (e0) {}

/**
 * Update per page records count
 * @param {string|number} value - Number of records per page or 'all'
 * @param {string} baseUrl - Base URL to use (default: current page URL)
 */
function updatePerPage(value, baseUrl = null) {
  const url = new URL(baseUrl || window.location.href);
  url.searchParams.delete('ttv2_partial');
  url.searchParams.set('per_page', value);
  url.searchParams.delete('page'); // Reset to page 1 when changing per_page
  loadStudentsTable(url.toString());
}

/**
 * Handle filter form submission with AJAX
 * @param {Event} event - Form submit event
 * @param {string} formId - ID of the filter form (default: 'filter-form')
 */
function handleStudentFilterSubmit(event, formId = 'filter-form') {
  event.preventDefault();
  const form = document.getElementById(formId);
  if (!form) return;

  const url = new URL(window.location.href);
  const params = url.searchParams;

  const formData = new FormData(form);
  const formKeys = new Set();
  for (const [key] of formData.entries()) {
    formKeys.add(key);
  }
  for (const key of formKeys) {
    const value = formData.get(key);
    if (value) {
      params.set(key, String(value));
    } else {
      params.delete(key);
    }
  }

  // Reset to page 1 when filtering
  params.set('page', '1');
  params.set('data_type', 'students');
  params.delete('ttv2_partial');

  loadStudentsTable(url.pathname + '?' + params.toString());
}

/**
 * Initialize student table AJAX functionality
 * Sets up event listeners for filter form, per_page dropdown, and pagination links
 */
function initStudentTableAJAX() {
  // Handle filter form submission
  const filterForm = document.getElementById('filter-form');
  if (filterForm) {
    filterForm.addEventListener('submit', (e) => handleStudentFilterSubmit(e));
  }

  // Handle per_page dropdown change
  const perPageSelect = document.getElementById('per_page');
  if (perPageSelect) {
    perPageSelect.addEventListener('change', function() {
      updatePerPage(this.value);
    });
  }

  // Handle pagination links (delegated event listener)
  document.addEventListener('click', function(e) {
    const paginationLink = e.target.closest('.pagination a.page-link');
    if (paginationLink && paginationLink.href) {
      e.preventDefault();
      const url = new URL(paginationLink.href);
      url.searchParams.delete('ttv2_partial');
      url.searchParams.set('data_type', 'students');
      loadStudentsTable(url.toString());
    }
  });

  // Load table on page load if not already loaded
  if (document.getElementById('students-table-wrapper') || document.getElementById('students-table-container')) {
    const url = new URL(window.location.href);
    url.searchParams.delete('ttv2_partial');
    url.searchParams.set('data_type', 'students');
    // Only load if page is first load (no data_type in URL)
    if (!window.location.search.includes('data_type=')) {
      setTimeout(() => {
        loadStudentsTable(url.toString());
      }, 100);
    }
  }
}

/**
 * Institute dashboard (Template v2): student table + side panel live inside HTML
 * injected by AJAX, so scripts embedded in that HTML do not execute. The v2 shell
 * loads student_table_ajax.js once, then must call this after the partial is
 * inserted to bind filters and fetch rows via data_type=students.
 */
function ttv2BindInstituteStudentPanelOnce() {
  const wrapper = document.getElementById('students-table-wrapper');
  const panel = document.getElementById('studentDetailsPanel');
  if (!wrapper || !panel || wrapper.getAttribute('data-ttv2-panel-delegation') === '1') {
    return;
  }
  wrapper.setAttribute('data-ttv2-panel-delegation', '1');
  wrapper.addEventListener('click', function (ev) {
    if (ev.target && ev.target.closest && ev.target.closest('a,button,input,select,textarea,label')) {
      return;
    }
    const row = ev.target.closest('.student-row');
    if (!row) {
      return;
    }
    try {
      const studentId = row.getAttribute('data-student-id') || '';
      const name = row.getAttribute('data-student-name') || '-';
      const email = row.getAttribute('data-student-email') || '-';
      const contact = row.getAttribute('data-student-contact') || '-';
      const studentClass = row.getAttribute('data-student-class') || '-';
      const stream = row.getAttribute('data-student-stream') || '-';
      const created = row.getAttribute('data-student-created') || '-';

      panel.setAttribute('data-student-id', studentId);
      panel.setAttribute('data-student-class-id', row.getAttribute('data-student-class-id') || '');

      const editBtn = document.getElementById('panel-edit-student-btn');
      const passwordBtn = document.getElementById('panel-change-password-btn');
      if (editBtn) {
        editBtn.disabled = !studentId;
      }
      if (passwordBtn) {
        passwordBtn.disabled = !studentId;
      }

      const ne = document.getElementById('panel-student-name');
      const ee = document.getElementById('panel-student-email');
      const ce = document.getElementById('panel-student-contact');
      const cle = document.getElementById('panel-student-class');
      const se = document.getElementById('panel-student-stream');
      const cr = document.getElementById('panel-student-created');
      if (ne) {
        ne.textContent = name;
      }
      if (ee) {
        ee.textContent = email;
      }
      if (ce) {
        ce.textContent = contact;
      }
      if (cle) {
        cle.textContent = studentClass;
      }
      if (se) {
        se.textContent = stream;
      }
      if (cr) {
        cr.textContent = created;
      }

      panel.classList.add('show');
    } catch (err) {
      console.error('Error handling institute student row click', err);
    }
  });
}

function ttv2InitStudentTableAfterBodyInject() {
  function syncDisplayButtons(mode) {
    try {
      var m = (mode || '').trim().toLowerCase();
      if (!m) {
        var inp = document.getElementById('ttv2DisplayInput');
        m = (inp && inp.value ? String(inp.value) : 'cards').trim().toLowerCase() || 'cards';
      }
      document.querySelectorAll('[data-ttv2-display]').forEach(function (btn) {
        var v = (btn.getAttribute('data-ttv2-display') || '').trim().toLowerCase();
        var on = v === m;
        btn.classList.toggle('active', on);
        btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
    } catch (e) {}
  }

  const filterForm = document.getElementById('filter-form');
  const filterDrawer = document.getElementById('ttv2StudentFilterDrawer');
  if (filterForm && !filterForm.dataset.ttv2StudentAjaxBound) {
    filterForm.dataset.ttv2StudentAjaxBound = '1';
    filterForm.addEventListener('submit', function (e) {
      handleStudentFilterSubmit(e, 'filter-form');
    });
  }

  // Auto-apply filters:
  // - Search: debounce; submit only after >=3 chars, or when cleared.
  // - Selects: submit immediately on change.
  (function(){
    if (!filterForm || filterForm.dataset.ttv2AutoApplyBound === '1') return;
    filterForm.dataset.ttv2AutoApplyBound = '1';

    var searchEl = document.getElementById('student_name');
    var instNameEl = document.getElementById('institute_name');
    var tSearch = null;
    var tInst = null;
    function submitIfOk() {
      try {
        // Use the same AJAX submit path
        handleStudentFilterSubmit(new Event('submit'), 'filter-form');
      } catch (e) {
        try { filterForm.requestSubmit ? filterForm.requestSubmit() : filterForm.submit(); } catch(e2) {}
      }
    }
    function onSearchChange() {
      if (!searchEl) return;
      var v = (searchEl.value || '').trim();
      if (tSearch) {
        clearTimeout(tSearch);
        tSearch = null;
      }
      tSearch = setTimeout(function(){
        // Only search after 3+ chars; or reset when empty.
        if (v.length === 0 || v.length >= 3) {
          submitIfOk();
        }
      }, 350);
    }
    if (searchEl && !searchEl.dataset.ttv2Bound) {
      searchEl.dataset.ttv2Bound = '1';
      searchEl.addEventListener('input', onSearchChange);
    }

    function onInstNameChange() {
      if (!instNameEl) return;
      var v = (instNameEl.value || '').trim();
      if (tInst) {
        clearTimeout(tInst);
        tInst = null;
      }
      tInst = setTimeout(function () {
        if (v.length === 0 || v.length >= 2) {
          submitIfOk();
        }
      }, 350);
    }
    if (instNameEl && !instNameEl.dataset.ttv2Bound) {
      instNameEl.dataset.ttv2Bound = '1';
      instNameEl.addEventListener('input', onInstNameChange);
    }

    ['classes', 'streams', 'assessment', 'counselor_assigned', 'institute_slug_filter'].forEach(function (id) {
      var el = document.getElementById(id);
      if (!el || el.dataset.ttv2Bound) return;
      el.dataset.ttv2Bound = '1';
      el.addEventListener('change', function(){
        submitIfOk();
      });
    });
  })();

  // Mobile filter drawer (students page): open/close sheet style panel.
  if (filterDrawer && !filterDrawer.dataset.ttv2DrawerBound) {
    filterDrawer.dataset.ttv2DrawerBound = '1';
    var bodyEl = document.body;
    var openBtns = document.querySelectorAll('[data-ttv2-filter-open]');
    var closeBtns = filterDrawer.querySelectorAll('[data-ttv2-filter-close]');
    function closeDrawer() {
      filterDrawer.classList.remove('is-open');
      if (bodyEl) bodyEl.classList.remove('ttv2-filter-drawer-open');
    }
    function openDrawer() {
      filterDrawer.classList.add('is-open');
      if (bodyEl) bodyEl.classList.add('ttv2-filter-drawer-open');
    }
    openBtns.forEach(function (btn) {
      btn.addEventListener('click', function () { openDrawer(); });
    });
    closeBtns.forEach(function (btn) {
      btn.addEventListener('click', function () { closeDrawer(); });
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeDrawer();
    });
    if (filterForm && !filterForm.dataset.ttv2DrawerSubmitBound) {
      filterForm.dataset.ttv2DrawerSubmitBound = '1';
      filterForm.addEventListener('submit', function () {
        closeDrawer();
      });
    }
  }

  // Display toggle (cards/list): buttons can be outside the filter form.
  if (!document.body.dataset.ttv2DisplayToggleBound) {
    document.body.dataset.ttv2DisplayToggleBound = '1';
    document.addEventListener('click', function (e) {
      const btn = e.target && e.target.closest ? e.target.closest('[data-ttv2-display]') : null;
      if (!btn) return;
      const form = document.getElementById('filter-form');
      if (!form) return;
      e.preventDefault();
      const mode = (btn.getAttribute('data-ttv2-display') || '').trim();
      if (!mode) return;
      const inp = document.getElementById('ttv2DisplayInput');
      if (inp) inp.value = mode;
      syncDisplayButtons(mode);
      // Use AJAX path (same as filters) so the page doesn't reload.
      try {
        handleStudentFilterSubmit(new Event('submit'), 'filter-form');
      } catch (err) {
        try {
          // Fallback: full submit if something fails
          form.requestSubmit ? form.requestSubmit() : form.submit();
        } catch (e2) {
          try { form.submit(); } catch (e3) {}
        }
      }
    }, true);
  }

  // Card click → open popup (student dashboard/report) if URL available.
  const wrapper = document.getElementById('students-table-wrapper');
  if (wrapper && !wrapper.dataset.ttv2CardPopupBound) {
    wrapper.dataset.ttv2CardPopupBound = '1';
    wrapper.addEventListener('click', function (e) {
      const reportBtn = e.target && e.target.closest ? e.target.closest('[data-ttv2-open-report]') : null;
      if (!reportBtn) return;
      const url = (reportBtn.getAttribute('data-ttv2-report-url') || '').trim();
      if (!url) return;
      e.preventDefault();
      try {
        if (typeof window.ttv2OpenStudentReportModal === 'function') {
          window.ttv2OpenStudentReportModal(url, reportBtn.getAttribute('data-ttv2-report-title') || 'Student report');
        } else {
          window.open(url, '_blank', 'noopener');
        }
      } catch (err) {
        window.open(url, '_blank', 'noopener');
      }
    });
    wrapper.addEventListener('click', function (e) {
      // Ignore explicit clicks on links/buttons inside the card.
      if (e.target && e.target.closest && e.target.closest('a,button,input,select,textarea')) {
        return;
      }
      const card = e.target && e.target.closest ? e.target.closest('.ttv2-student-card[data-ttv2-report-url]') : null;
      if (!card) return;
      const url = (card.getAttribute('data-ttv2-report-url') || '').trim();
      if (!url) return;
      e.preventDefault();
      try {
        if (typeof window.ttv2OpenStudentReportModal === 'function') {
          window.ttv2OpenStudentReportModal(url, card.getAttribute('data-ttv2-student-name') || 'Student report');
        } else {
          window.open(url, '_blank', 'noopener');
        }
      } catch (err) {
        window.open(url, '_blank', 'noopener');
      }
    });
    wrapper.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      const card = e.target && e.target.closest ? e.target.closest('.ttv2-student-card[data-ttv2-report-url]') : null;
      if (!card) return;
      const url = (card.getAttribute('data-ttv2-report-url') || '').trim();
      if (!url) return;
      e.preventDefault();
      try {
        if (typeof window.ttv2OpenStudentReportModal === 'function') {
          window.ttv2OpenStudentReportModal(url, card.getAttribute('data-ttv2-student-name') || 'Student report');
        } else {
          window.open(url, '_blank', 'noopener');
        }
      } catch (err) {
        window.open(url, '_blank', 'noopener');
      }
    });
  }
  const perPageSelect = document.getElementById('per_page');
  if (perPageSelect && !perPageSelect.dataset.ttv2StudentAjaxBound) {
    perPageSelect.dataset.ttv2StudentAjaxBound = '1';
    perPageSelect.addEventListener('change', function () {
      updatePerPage(this.value);
    });
  }
  if (!document.getElementById('students-table-wrapper') && !document.getElementById('students-table-container')) {
    return;
  }
  const url = new URL(window.location.href);
  url.searchParams.delete('ttv2_partial');
  url.searchParams.set('data_type', 'students');
  // Default view: cards (server falls back to list when param missing)
  try {
    if (!url.searchParams.get('display')) {
      const inp = document.getElementById('ttv2DisplayInput');
      const mode = (inp && inp.value ? String(inp.value) : 'cards').trim() || 'cards';
      url.searchParams.set('display', mode);
    }
  } catch (e) {}
  syncDisplayButtons(url.searchParams.get('display') || '');
  loadStudentsTable(url.toString(), {
    onSuccess: function () {
      ttv2BindInstituteStudentPanelOnce();
    }
  });
}

if (typeof window !== 'undefined') {
  window.ttv2BindInstituteStudentPanelOnce = ttv2BindInstituteStudentPanelOnce;
  window.ttv2InitStudentTableAfterBodyInject = ttv2InitStudentTableAfterBodyInject;
}

try {
  if (typeof ttv2BindAdvCardDelegatedActionsOnce === 'function') {
    ttv2BindAdvCardDelegatedActionsOnce();
  }
} catch (_eAdvDel) {}

// Auto-initialize on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initStudentTableAJAX);
} else {
  initStudentTableAJAX();
}

