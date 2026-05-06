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

  function getFollowupUrl() {
    var container = document.getElementById('students-table-container');
    return container ? (container.getAttribute('data-ttv2-followup-url') || '').trim() : '';
  }

  function openModal(smId, studentName) {
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

    if (titleEl) titleEl.textContent = 'Create follow up - ' + (studentName || 'Student');
    if (smInp) smInp.value = String(smId || '');
    if (modeEl) modeEl.value = '';
    if (statusEl) statusEl.value = '';
    if (lastEl) lastEl.value = '';
    if (nextEl) nextEl.value = '';
    if (msgEl) msgEl.value = '';
    if (chkEl) chkEl.checked = false;
    if (stEl) stEl.textContent = '';
    if (saveBtn) saveBtn.disabled = false;

    bootstrap.Modal.getOrCreateInstance(modalEl).show();
  }

  function reloadRoster() {
    try {
      if (typeof loadStudentsTable !== 'function') return;
      var url = new URL(window.location.href);
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
    openModal(smId, studentName);
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

/**
 * Update per page records count
 * @param {string|number} value - Number of records per page or 'all'
 * @param {string} baseUrl - Base URL to use (default: current page URL)
 */
function updatePerPage(value, baseUrl = null) {
  const url = new URL(baseUrl || window.location.href);
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

  const formData = new FormData(form);
  const params = new URLSearchParams();
  
  // Add all form fields to URL params
  for (const [key, value] of formData.entries()) {
    if (value) {
      params.append(key, value);
    }
  }

  // Reset to page 1 when filtering
  params.set('page', '1');
  params.set('data_type', 'students');

  const url = window.location.pathname + '?' + params.toString();
  loadStudentsTable(url);
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
      url.searchParams.set('data_type', 'students');
      loadStudentsTable(url.toString());
    }
  });

  // Load table on page load if not already loaded
  if (document.getElementById('students-table-wrapper') || document.getElementById('students-table-container')) {
    const url = new URL(window.location.href);
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
    var t = null;
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
      if (t) { clearTimeout(t); t = null; }
      t = setTimeout(function(){
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

    ['classes', 'streams', 'assessment'].forEach(function(id){
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
  url.searchParams.set('data_type', 'students');
  // Default view: cards (server falls back to list when param missing)
  try {
    if (!url.searchParams.get('display')) {
      const inp = document.getElementById('ttv2DisplayInput');
      const mode = (inp && inp.value ? String(inp.value) : 'cards').trim() || 'cards';
      url.searchParams.set('display', mode);
    }
  } catch (e) {}
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

// Auto-initialize on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initStudentTableAJAX);
} else {
  initStudentTableAJAX();
}

