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

