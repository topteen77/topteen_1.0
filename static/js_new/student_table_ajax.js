/**
 * Centralized AJAX functions for loading student tables across different roles
 * This can be used by institute, counselor, marketing group admin, etc.
 */

/**
 * Build the students roster AJAX URL, merging the live filter form over the base URL
 * so assign/unassign reloads keep institute_slug and other filters (window.location alone
 * can be stale after AJAX-only filter applies).
 *
 * @param {Object} opts
 * @param {string} [opts.baseUrl] - Defaults to window.location.href
 */
function ttv2BuildStudentRosterLoadUrl(opts) {
  opts = opts || {};
  try {
    var base = opts.baseUrl || window.location.href;
    var url = new URL(base, window.location.origin);
    url.searchParams.delete('ttv2_partial');
    url.searchParams.set('data_type', 'students');
    var form = document.getElementById('filter-form');
    if (form) {
      var fd = new FormData(form);
      var keys = {};
      try {
        fd.forEach(function (_v, k) {
          keys[k] = true;
        });
      } catch (e0) {
        try {
          for (var it = fd.entries(), n = it.next(); !n.done; n = it.next()) {
            keys[n.value[0]] = true;
          }
        } catch (e1) {}
      }
      Object.keys(keys).forEach(function (key) {
        var v = fd.get(key);
        if (v != null && String(v).trim() !== '') {
          url.searchParams.set(key, String(v));
        } else {
          url.searchParams.delete(key);
        }
      });
    }
    return url.toString();
  } catch (e) {
    try {
      var u = new URL(window.location.href);
      u.searchParams.delete('ttv2_partial');
      u.searchParams.set('data_type', 'students');
      return u.toString();
    } catch (e2) {
      return window.location.pathname + '?data_type=students';
    }
  }
}

try {
  window.ttv2BuildStudentRosterLoadUrl = ttv2BuildStudentRosterLoadUrl;
} catch (eWb) {}

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

  const fetchOpts = (typeof window.ttv2AjaxFetchOptions === 'function')
    ? window.ttv2AjaxFetchOptions()
    : { headers: { 'X-Requested-With': 'XMLHttpRequest' }, redirect: 'manual', credentials: 'same-origin' };

  fetch(ajaxUrl, fetchOpts)
    .then(response => {
      if (typeof window.ttv2HandleAuthResponse === 'function' && window.ttv2HandleAuthResponse(response)) {
        if (loader) loader.style.display = 'none';
        if (config.onError) config.onError('session_expired');
        return null;
      }
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return response.text();
    })
    .then(html => {
      if (!html) return;
      if (typeof window.ttv2IsLoginPageHtml === 'function' && window.ttv2IsLoginPageHtml(html)) {
        if (loader) loader.style.display = 'none';
        if (typeof window.ttv2PromptLogin === 'function') window.ttv2PromptLogin();
        if (config.onError) config.onError('session_expired');
        return;
      }
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

      try {
        var hostAfter = wrapper || tableContainer;
        var injAfter =
          hostAfter && hostAfter.querySelector
            ? hostAfter.querySelector('#students-table-container')
            : null;
        if (!injAfter && tableContainer && tableContainer.id === 'students-table-container') {
          injAfter = tableContainer;
        }
        if (typeof window.ttv2RefreshBulkAdvisorBar === 'function') {
          window.ttv2RefreshBulkAdvisorBar(injAfter || null);
        }
      } catch (_eRbLoad) {}

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

function ttv2ReloadStudentRosterAjax() {
  try {
    if (typeof loadStudentsTable !== 'function') return;
    loadStudentsTable(ttv2BuildStudentRosterLoadUrl({}));
  } catch (eR0) {}
}

function ttv2StudentRosterFlashMsg(msg, variant) {
  var text = msg || '';
  var v = variant || 'info';
  var wrap = document.getElementById('ttv2StudentRosterFlash');
  var span = document.getElementById('ttv2StudentRosterFlashText');
  if (!wrap || !span) {
    try {
      if (text) window.alert(text);
    } catch (eA) {}
    return;
  }
  wrap.classList.remove(
    'd-none',
    'alert-success',
    'alert-danger',
    'alert-warning',
    'alert-info'
  );
  wrap.classList.add(
    v === 'danger'
      ? 'alert-danger'
      : v === 'success'
        ? 'alert-success'
        : v === 'warning'
          ? 'alert-warning'
          : 'alert-info',
    'show'
  );
  span.textContent = text;
  try {
    wrap.scrollIntoView({ block: 'nearest' });
  } catch (eSc) {}
  clearTimeout(wrap._ttv2RosterFlashT);
  wrap._ttv2RosterFlashT = setTimeout(function () {
    try {
      wrap.classList.remove('show');
      wrap.classList.add('d-none');
    } catch (eH) {}
  }, 9000);
}

try {
  window.ttv2ReloadStudentRosterAjax = ttv2ReloadStudentRosterAjax;
  window.ttv2StudentRosterFlashMsg = ttv2StudentRosterFlashMsg;
} catch (eW0) {}

/**
 * Institute group bulk bar: enable/disable assign vs unassign controls from row counts on the loaded page.
 * @param {HTMLElement} [host] - Prefer #students-table-container (fallback: lookup by id)
 */
function ttv2RefreshBulkAdvisorBar(host) {
  try {
    var container = host && host.querySelector ? host : null;
    if (!container) {
      container = document.getElementById('students-table-container');
    }
    if (!container) return;
    var bulkBar = container.querySelector('[data-ttv2-bulk-adv-bar]');
    if (!bulkBar) return;
    if (!bulkBar.querySelector('[data-ttv2-select-master="unassigned"]')) return;

    var nu = container.querySelectorAll(
      'tbody tr.student-row[data-sm-id][data-ttv2-adv-unassigned="1"]'
    ).length;
    var na = container.querySelectorAll(
      'tbody tr.student-row[data-sm-id][data-ttv2-adv-assigned="1"]'
    ).length;

    var mUn = bulkBar.querySelector('[data-ttv2-select-master="unassigned"]');
    var mAs = bulkBar.querySelector('[data-ttv2-select-master="assigned"]');
    var bulkSel = bulkBar.querySelector('[data-ttv2-bulk-adv-counselor]');
    var bulkApply = bulkBar.querySelector('[data-ttv2-bulk-adv-apply]');
    var bulkUn = bulkBar.querySelector('[data-ttv2-bulk-adv-unapply]');

    var noUn = nu === 0;
    var noAs = na === 0;

    if (mUn) {
      if (noUn) mUn.checked = false;
      mUn.disabled = noUn;
    }
    if (bulkSel) {
      if (noUn) bulkSel.selectedIndex = 0;
      bulkSel.disabled = noUn;
    }
    if (bulkApply) {
      bulkApply.disabled = noUn;
    }

    if (mAs) {
      if (noAs) mAs.checked = false;
      mAs.disabled = noAs;
    }
    if (bulkUn) {
      bulkUn.disabled = noAs;
    }

    if (noUn) {
      container
        .querySelectorAll(
          'tbody tr.student-row[data-sm-id][data-ttv2-adv-unassigned="1"] input[data-ttv2-sm-select]'
        )
        .forEach(function (cb) {
          cb.checked = false;
        });
    }
    if (noAs) {
      container
        .querySelectorAll(
          'tbody tr.student-row[data-sm-id][data-ttv2-adv-assigned="1"] input[data-ttv2-sm-select]'
        )
        .forEach(function (cb) {
          cb.checked = false;
        });
    }
  } catch (_eRb) {}
}

try {
  window.ttv2RefreshBulkAdvisorBar = ttv2RefreshBulkAdvisorBar;
} catch (_eWBr) {}

if (typeof document !== 'undefined' && document.body) {
  if (document.body.dataset.ttv2RosterFlashDismiss !== '1') {
    document.body.dataset.ttv2RosterFlashDismiss = '1';
    document.body.addEventListener(
      'click',
      function (e) {
        var b =
          e.target && e.target.closest
            ? e.target.closest('[data-ttv2-student-roster-flash-dismiss]')
            : null;
        if (!b) return;
        var fw = document.getElementById('ttv2StudentRosterFlash');
        if (fw) {
          clearTimeout(fw._ttv2RosterFlashT);
          fw.classList.remove('show');
          fw.classList.add('d-none');
        }
      },
      true
    );
  }
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
 * Institute / institute-group / marketing list view: advisor assign, bulk assign, unassign.
 * Uses per-row data-ttv2-set-url (institute slug). Defined here so shells without role_boot/institute.html still bind.
 */
function ttv2InitAdvisorChangeControls() {
  try {
    var container = document.getElementById('students-table-container');
    if (!container || container.__ttv2AdvBound) {
      return;
    }
    container.__ttv2AdvBound = true;

    function postSet(smId, counselorId, cb, rowUrlOverride) {
      var url =
        rowUrlOverride ||
        container.getAttribute('data-ttv2-set-counselor-url') ||
        '#';
      if (!url || url === '#') {
        return;
      }
      fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': ttv2GetCookie('csrftoken') || ''
        },
        body: JSON.stringify({ student_management_id: smId, counselor_id: counselorId })
      })
        .then(function (r) {
          return r.json().catch(function () {
            return { ok: false };
          });
        })
        .then(function (data) {
          if (cb) cb(data);
        })
        .catch(function () {
          if (cb) cb({ ok: false });
        });
    }

    container.addEventListener('click', function (e) {
      var toggleBtn =
        e.target && e.target.closest ? e.target.closest('[data-ttv2-adv-toggle-change]') : null;
      if (toggleBtn) {
        e.preventDefault();
        var cell = toggleBtn.closest('[data-ttv2-adv-cell]');
        var panel = cell ? cell.querySelector('[data-ttv2-adv-change-panel]') : null;
        if (!panel) return;
        var willShow = panel.classList.contains('d-none');
        panel.classList.toggle('d-none', !willShow);
        toggleBtn.setAttribute('aria-expanded', willShow ? 'true' : 'false');
        return;
      }

      var assignRowBtn =
        e.target && e.target.closest ? e.target.closest('[data-ttv2-adv-assign]') : null;
      if (assignRowBtn) {
        e.preventDefault();
        var trA = assignRowBtn.closest('tr[data-sm-id]');
        if (!trA) return;
        var selU = trA.querySelector('[data-ttv2-adv-select-unassigned]');
        var counselorPick = selU ? String(selU.value || '').trim() : '';
        if (!counselorPick) {
          try {
            alert('Choose an advisor first.');
          } catch (ePick) {}
          return;
        }
        var smIdA = trA.getAttribute('data-sm-id');
        var rowUrlA = (trA.getAttribute('data-ttv2-set-url') || '').trim();
        assignRowBtn.disabled = true;
        postSet(smIdA, counselorPick, function (data) {
          assignRowBtn.disabled = false;
          if (!(data && data.ok)) {
            var em = (data && data.error) ? data.error : 'Assign failed';
            if (typeof window.ttv2StudentRosterFlashMsg === 'function') {
              window.ttv2StudentRosterFlashMsg(em, 'danger');
            } else {
              try {
                alert(em);
              } catch (e2) {}
            }
            return;
          }
          if (typeof window.ttv2StudentRosterFlashMsg === 'function') {
            window.ttv2StudentRosterFlashMsg('Advisor assigned.', 'success');
          }
          if (typeof window.ttv2ReloadStudentRosterAjax === 'function') {
            window.ttv2ReloadStudentRosterAjax();
          } else if (typeof window.ttv2InitStudentTableAfterBodyInject === 'function') {
            window.ttv2InitStudentTableAfterBodyInject();
          }
        }, rowUrlA || undefined);
        return;
      }

      var bulkApply =
        e.target && e.target.closest ? e.target.closest('[data-ttv2-bulk-adv-apply]') : null;
      if (bulkApply) {
        e.preventDefault();
        var bulkBar = bulkApply.closest('[data-ttv2-bulk-adv-bar]');
        var bulkSel = bulkBar ? bulkBar.querySelector('[data-ttv2-bulk-adv-counselor]') : null;
        var opt =
          bulkSel && bulkSel.selectedIndex >= 0 ? bulkSel.options[bulkSel.selectedIndex] : null;
        var instScope = opt ? String(opt.getAttribute("data-counselor-inst-id") || "").trim() : "";
        var bulkCid = bulkSel ? String(bulkSel.value || "").trim() : "";
        if (!bulkCid) {
          try {
            alert("Choose an advisor for the selected students.");
          } catch (eB0) {}
          return;
        }
        var hasIgMasters =
          !!(
            bulkBar &&
            bulkBar.querySelector('[data-ttv2-select-master="unassigned"]')
          );
        var pickedSelector = hasIgMasters
          ? 'tbody tr.student-row[data-sm-id][data-ttv2-adv-unassigned="1"] input[data-ttv2-sm-select]:checked'
          : 'tbody tr.student-row[data-sm-id] input[data-ttv2-sm-select]:checked';
        var picked = container.querySelectorAll(pickedSelector);
        if (!picked.length) {
          try {
            alert(
              hasIgMasters
                ? "Select at least one unassigned student on this page."
                : "Select at least one student on this page."
            );
          } catch (eB1) {}
          return;
        }
        bulkApply.disabled = true;
        var prevBulk = bulkApply.textContent;
        bulkApply.textContent = "Assigning…";
        var seq = Promise.resolve();
        var skipped = 0;
        var okN = 0;
        var failN = 0;
        picked.forEach(function (inp) {
          var trb = inp.closest("tr[data-sm-id]");
          if (!trb) return;
          var smIdb = trb.getAttribute("data-sm-id");
          var rowUrlb = (trb.getAttribute("data-ttv2-set-url") || "").trim();
          var rowInst = String(trb.getAttribute("data-sm-inst-id") || "").trim();
          if (instScope && rowInst && instScope !== rowInst) {
            skipped += 1;
            return;
          }
          seq = seq.then(function () {
            return new Promise(function (resolve) {
              postSet(smIdb, bulkCid, function (data) {
                if (data && data.ok) okN += 1;
                else failN += 1;
                resolve();
              }, rowUrlb || undefined);
            });
          });
        });
        seq
          .catch(function () {})
          .then(function () {
            bulkApply.disabled = false;
            bulkApply.textContent = prevBulk || "Assign selected";
            var parts = [];
            if (okN) parts.push(okN + " student(s) assigned.");
            if (failN) parts.push(failN + " failed.");
            if (skipped) parts.push(skipped + " skipped (wrong school for advisor).");
            var msg = parts.join(" ");
            if (typeof window.ttv2StudentRosterFlashMsg === "function" && msg) {
              var vari = failN && !okN ? "danger" : failN ? "warning" : "success";
              window.ttv2StudentRosterFlashMsg(msg, vari);
            } else if (skipped > 0) {
              try {
                alert(
                  skipped +
                    " row(s) skipped — they are not at the same institute as the advisor you picked."
                );
              } catch (eSk) {}
            }
            if (typeof window.ttv2ReloadStudentRosterAjax === "function") {
              window.ttv2ReloadStudentRosterAjax();
            } else if (typeof window.ttv2InitStudentTableAfterBodyInject === "function") {
              window.ttv2InitStudentTableAfterBodyInject();
            }
          });
        return;
      }

      var bulkUn =
        e.target && e.target.closest ? e.target.closest("[data-ttv2-bulk-adv-unapply]") : null;
      if (bulkUn) {
        e.preventDefault();
        var pickedU = container.querySelectorAll(
          "tbody tr.student-row[data-sm-id][data-ttv2-adv-assigned='1'] input[data-ttv2-sm-select]:checked"
        );
        if (!pickedU.length) {
          if (typeof window.ttv2StudentRosterFlashMsg === "function") {
            window.ttv2StudentRosterFlashMsg(
              "Select at least one assigned student on this page.",
              "warning"
            );
          } else {
            try {
              alert("Select at least one assigned student on this page.");
            } catch (eU0) {}
          }
          return;
        }
        bulkUn.disabled = true;
        var prevU = bulkUn.textContent;
        bulkUn.textContent = "Unassigning…";
        var seqU = Promise.resolve();
        var okU = 0;
        var failU = 0;
        pickedU.forEach(function (inp) {
          var tru = inp.closest("tr[data-sm-id]");
          if (!tru) return;
          var smU = tru.getAttribute("data-sm-id");
          var rowUrlU = (tru.getAttribute("data-ttv2-set-url") || "").trim();
          seqU = seqU.then(function () {
            return new Promise(function (resolve) {
              postSet(smU, "", function (data) {
                if (data && data.ok) okU += 1;
                else failU += 1;
                resolve();
              }, rowUrlU || undefined);
            });
          });
        });
        seqU
          .catch(function () {})
          .then(function () {
            bulkUn.disabled = false;
            bulkUn.textContent = prevU || "Unassign selected";
            var m =
              (okU ? okU + " unassigned. " : "") + (failU ? failU + " failed." : "");
            if (typeof window.ttv2StudentRosterFlashMsg === "function" && m.trim()) {
              window.ttv2StudentRosterFlashMsg(
                m.trim(),
                failU && !okU ? "danger" : failU ? "warning" : "success"
              );
            }
            if (typeof window.ttv2ReloadStudentRosterAjax === "function") {
              window.ttv2ReloadStudentRosterAjax();
            } else if (typeof window.ttv2InitStudentTableAfterBodyInject === "function") {
              window.ttv2InitStudentTableAfterBodyInject();
            }
          });
        return;
      }

      var unBtn = e.target && e.target.closest ? e.target.closest("[data-ttv2-adv-unassign]") : null;
      if (!unBtn) return;
      e.preventDefault();
      var tr = e.target.closest('tr[data-sm-id]');
      if (!tr) return;
      var smId = tr.getAttribute('data-sm-id');
      var rowUrl = (tr.getAttribute('data-ttv2-set-url') || '').trim();
      postSet(smId, '', function (data) {
        if (!(data && data.ok)) {
          var eu = (data && data.error) ? data.error : 'Unassign failed';
          if (typeof window.ttv2StudentRosterFlashMsg === 'function') {
            window.ttv2StudentRosterFlashMsg(eu, 'danger');
          } else {
            try {
              alert(eu);
            } catch (e2) {}
          }
          return;
        }
        if (typeof window.ttv2StudentRosterFlashMsg === 'function') {
          window.ttv2StudentRosterFlashMsg('Advisor unassigned.', 'success');
        }
        if (typeof window.ttv2ReloadStudentRosterAjax === 'function') {
          window.ttv2ReloadStudentRosterAjax();
        } else if (typeof window.ttv2InitStudentTableAfterBodyInject === 'function') {
          window.ttv2InitStudentTableAfterBodyInject();
        }
      }, rowUrl || undefined);
    });

    container.addEventListener('change', function (e) {
      var masterMode =
        e.target && e.target.closest ? e.target.closest('[data-ttv2-select-master]') : null;
      if (masterMode && container.contains(masterMode)) {
        var mode = (masterMode.getAttribute('data-ttv2-select-master') || '')
          .trim()
          .toLowerCase();
        var on = masterMode.checked;
        if (on && (mode === 'unassigned' || mode === 'assigned')) {
          var bulkBarEl = masterMode.closest('[data-ttv2-bulk-adv-bar]');
          if (bulkBarEl) {
            bulkBarEl.querySelectorAll('[data-ttv2-select-master]').forEach(function (other) {
              if (other !== masterMode) other.checked = false;
            });
          }
        }
        var q = 'tbody tr.student-row[data-sm-id] input[data-ttv2-sm-select]';
        if (mode === 'unassigned') {
          q =
            'tbody tr.student-row[data-sm-id][data-ttv2-adv-unassigned="1"] input[data-ttv2-sm-select]';
        } else if (mode === 'assigned') {
          q =
            'tbody tr.student-row[data-sm-id][data-ttv2-adv-assigned="1"] input[data-ttv2-sm-select]';
        }
        container.querySelectorAll(q).forEach(function (cb) {
          cb.checked = on;
        });
        return;
      }
      var master =
        e.target && e.target.closest ? e.target.closest('[data-ttv2-select-all-sm]') : null;
      if (master) {
        var on = master.checked;
        var q = 'tbody tr.student-row[data-sm-id] input[data-ttv2-sm-select]';
        container.querySelectorAll(q).forEach(function (cb) {
          cb.checked = on;
        });
        return;
      }

      var sel =
        e.target && e.target.closest ? e.target.closest('[data-ttv2-adv-select-change-save]') : null;
      if (!sel) return;
      var tr = sel.closest('tr[data-sm-id]');
      if (!tr) return;
      var smId = tr.getAttribute('data-sm-id');
      var counselorId = sel.value || '';
      var rowUrl = (tr.getAttribute('data-ttv2-set-url') || '').trim();
      postSet(smId, counselorId, function (data) {
        if (!(data && data.ok)) {
          var ex = (data && data.error) ? data.error : 'Update failed';
          if (typeof window.ttv2StudentRosterFlashMsg === 'function') {
            window.ttv2StudentRosterFlashMsg(ex, 'danger');
          } else {
            try {
              alert(ex);
            } catch (e2) {}
          }
          return;
        }
        if (typeof window.ttv2StudentRosterFlashMsg === 'function') {
          window.ttv2StudentRosterFlashMsg('Advisor updated.', 'success');
        }
        if (typeof window.ttv2ReloadStudentRosterAjax === 'function') {
          window.ttv2ReloadStudentRosterAjax();
        } else if (typeof window.ttv2InitStudentTableAfterBodyInject === 'function') {
          window.ttv2InitStudentTableAfterBodyInject();
        }
      }, rowUrl || undefined);
    });
  } catch (e0) {}
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
              var emsg = data && data.error ? data.error : 'Assign failed';
              if (typeof window.ttv2StudentRosterFlashMsg === 'function') {
                window.ttv2StudentRosterFlashMsg(emsg, 'danger');
              } else {
                try {
                  alert(emsg);
                } catch (e2) {}
              }
            } else {
              if (typeof window.ttv2StudentRosterFlashMsg === 'function') {
                window.ttv2StudentRosterFlashMsg('Advisor assigned.', 'success');
              }
              if (typeof window.ttv2ReloadStudentRosterAjax === 'function') {
                window.ttv2ReloadStudentRosterAjax();
              } else if (
                typeof window.ttv2InitStudentTableAfterBodyInject === 'function'
              ) {
                window.ttv2InitStudentTableAfterBodyInject();
              }
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
            var e2msg = data && data.error ? data.error : 'Unassign failed';
            if (typeof window.ttv2StudentRosterFlashMsg === 'function') {
              window.ttv2StudentRosterFlashMsg(e2msg, 'danger');
            } else {
              try {
                alert(e2msg);
              } catch (e2) {}
            }
          } else {
            if (typeof window.ttv2StudentRosterFlashMsg === 'function') {
              window.ttv2StudentRosterFlashMsg('Advisor unassigned.', 'success');
            }
            if (typeof window.ttv2ReloadStudentRosterAjax === 'function') {
              window.ttv2ReloadStudentRosterAjax();
            } else if (
              typeof window.ttv2InitStudentTableAfterBodyInject === 'function'
            ) {
              window.ttv2InitStudentTableAfterBodyInject();
            }
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
      if (typeof window.ttv2ReloadStudentRosterAjax === 'function') {
        window.ttv2ReloadStudentRosterAjax();
      } else if (typeof loadStudentsTable === 'function') {
        loadStudentsTable(
          typeof ttv2BuildStudentRosterLoadUrl === 'function'
            ? ttv2BuildStudentRosterLoadUrl({})
            : (function () {
                var u = new URL(window.location.href);
                u.searchParams.delete('ttv2_partial');
                u.searchParams.set('data_type', 'students');
                return u.toString();
              })()
        );
      }
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
  try {
    var s = ttv2BuildStudentRosterLoadUrl({ baseUrl: baseUrl || undefined });
    var url = new URL(s, window.location.origin);
    url.searchParams.set('per_page', value);
    url.searchParams.delete('page');
    loadStudentsTable(url.toString());
  } catch (ePp) {
    var u = new URL(baseUrl || window.location.href);
    u.searchParams.delete('ttv2_partial');
    u.searchParams.set('data_type', 'students');
    u.searchParams.set('per_page', value);
    u.searchParams.delete('page');
    loadStudentsTable(u.toString());
  }
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

  let finalUrl;
  try {
    const u = new URL(ttv2BuildStudentRosterLoadUrl({}));
    u.searchParams.set('page', '1');
    finalUrl = u.pathname + '?' + u.searchParams.toString();
  } catch (eU) {
    finalUrl = window.location.pathname + '?data_type=students&page=1';
  }

  try {
    if (typeof history !== 'undefined' && history.replaceState) {
      history.replaceState(null, '', finalUrl);
    }
  } catch (eH) {}

  loadStudentsTable(finalUrl);
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
      loadStudentsTable(ttv2BuildStudentRosterLoadUrl({ baseUrl: paginationLink.href }));
    }
  });

  // Load table on page load if not already loaded
  if (document.getElementById('students-table-wrapper') || document.getElementById('students-table-container')) {
    // Only load if page is first load (no data_type in URL)
    if (!window.location.search.includes('data_type=')) {
      setTimeout(() => {
        loadStudentsTable(ttv2BuildStudentRosterLoadUrl({}));
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
      const reportCard = reportBtn.closest ? reportBtn.closest('.ttv2-student-card') : null;
      const reportStudentId = (
        (reportBtn.getAttribute('data-ttv2-student-id') || '').trim()
        || (reportCard ? (reportCard.getAttribute('data-ttv2-student-id') || '').trim() : '')
      );
      try {
        if (typeof window.ttv2OpenStudentReportModal === 'function') {
          window.ttv2OpenStudentReportModal(
            url,
            reportBtn.getAttribute('data-ttv2-report-title') || 'Student report',
            reportStudentId || undefined
          );
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
      const cardStudentId = (card.getAttribute('data-ttv2-student-id') || '').trim();
      try {
        if (typeof window.ttv2OpenStudentReportModal === 'function') {
          window.ttv2OpenStudentReportModal(
            url,
            card.getAttribute('data-ttv2-student-name') || 'Student report',
            cardStudentId || undefined
          );
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
      const cardStudentId = (card.getAttribute('data-ttv2-student-id') || '').trim();
      try {
        if (typeof window.ttv2OpenStudentReportModal === 'function') {
          window.ttv2OpenStudentReportModal(
            url,
            card.getAttribute('data-ttv2-student-name') || 'Student report',
            cardStudentId || undefined
          );
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
  const url = new URL(ttv2BuildStudentRosterLoadUrl({}));
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
  window.ttv2InitAdvisorChangeControls = ttv2InitAdvisorChangeControls;
  window.ttv2RefreshBulkAdvisorBar = ttv2RefreshBulkAdvisorBar;
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

