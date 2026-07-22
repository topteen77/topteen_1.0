(function () {
  'use strict';

  function getCookie(name) {
    var value = '; ' + document.cookie;
    var parts = value.split('; ' + name + '=');
    if (parts.length === 2) {
      return parts.pop().split(';').shift();
    }
    return '';
  }

  function ready(fn) {
    if (document.readyState !== 'loading') {
      fn();
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
  }

  ready(function () {
    var table = document.getElementById('result_list');
    var statusEl = document.getElementById('dpr-reorder-status');
    var reorderUrl = statusEl && statusEl.getAttribute('data-reorder-url');
    if (!table || !reorderUrl) {
      return;
    }

    var tbody = table.tBodies[0];
    if (!tbody) {
      return;
    }

    var dragRow = null;

    function showStatus(message, isError) {
      if (!statusEl) {
        return;
      }
      statusEl.textContent = message;
      statusEl.classList.add('is-visible');
      statusEl.classList.toggle('is-error', !!isError);
      window.clearTimeout(showStatus._timer);
      showStatus._timer = window.setTimeout(function () {
        statusEl.classList.remove('is-visible');
      }, 2500);
    }

    function rows() {
      return Array.prototype.slice.call(tbody.querySelectorAll('tr'));
    }

    function collectIds() {
      return rows()
        .map(function (row) {
          var handle = row.querySelector('.dpr-drag-handle[data-rule-id]');
          if (handle) {
            return parseInt(handle.getAttribute('data-rule-id'), 10);
          }
          var action = row.querySelector('input.action-select');
          return action ? parseInt(action.value, 10) : NaN;
        })
        .filter(function (id) {
          return Number.isFinite(id);
        });
    }

    function persistOrder() {
      var ids = collectIds();
      if (!ids.length) {
        return;
      }
      fetch(reorderUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken'),
        },
        body: JSON.stringify({ ids: ids }),
      })
        .then(function (response) {
          return response.json().then(function (data) {
            if (!response.ok || !data.ok) {
              throw new Error((data && data.error) || 'Reorder failed');
            }
            showStatus('Order saved.', false);
          });
        })
        .catch(function (err) {
          showStatus(err.message || 'Could not save order.', true);
        });
    }

    rows().forEach(function (row) {
      var handle = row.querySelector('.dpr-drag-handle');
      if (!handle) {
        return;
      }
      row.setAttribute('draggable', 'true');

      row.addEventListener('dragstart', function (event) {
        if (event.target.closest('input, select, textarea, a, button')) {
          event.preventDefault();
          return;
        }
        dragRow = row;
        row.classList.add('dpr-dragging');
        try {
          event.dataTransfer.effectAllowed = 'move';
          event.dataTransfer.setData('text/plain', handle.getAttribute('data-rule-id') || '');
        } catch (e) {
          /* ignore */
        }
      });

      row.addEventListener('dragend', function () {
        row.classList.remove('dpr-dragging');
        rows().forEach(function (r) {
          r.classList.remove('dpr-drop-target');
        });
        dragRow = null;
      });

      row.addEventListener('dragover', function (event) {
        if (!dragRow || dragRow === row) {
          return;
        }
        event.preventDefault();
        row.classList.add('dpr-drop-target');
        var rect = row.getBoundingClientRect();
        var before = event.clientY < rect.top + rect.height / 2;
        if (before) {
          tbody.insertBefore(dragRow, row);
        } else {
          tbody.insertBefore(dragRow, row.nextSibling);
        }
      });

      row.addEventListener('dragleave', function () {
        row.classList.remove('dpr-drop-target');
      });

      row.addEventListener('drop', function (event) {
        event.preventDefault();
        row.classList.remove('dpr-drop-target');
        persistOrder();
      });
    });
  });
})();
