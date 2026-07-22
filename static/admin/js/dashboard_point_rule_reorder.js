(function () {
  'use strict';

  function getCookie(name) {
    var value = '; ' + document.cookie;
    var parts = value.split('; ' + name + '=');
    if (parts.length === 2) {
      return decodeURIComponent(parts.pop().split(';').shift());
    }
    return '';
  }

  function getCsrfToken() {
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input && input.value) {
      return input.value;
    }
    return getCookie('csrftoken');
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
    var reorderUrl = (statusEl && statusEl.getAttribute('data-reorder-url')) || '';
    if (!table || !reorderUrl) {
      return;
    }

    var tbody = table.tBodies[0];
    if (!tbody) {
      return;
    }

    var dragRow = null;
    var startOrderKey = '';
    var saving = false;

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
      }, 2800);
    }

    function rows() {
      return Array.prototype.slice.call(tbody.querySelectorAll('tr')).filter(function (row) {
        return !!row.querySelector('.dpr-drag-handle[data-rule-id]');
      });
    }

    function orderKey() {
      return collectIds().join(',');
    }

    function collectIds() {
      return rows()
        .map(function (row) {
          var handle = row.querySelector('.dpr-drag-handle[data-rule-id]');
          return handle ? parseInt(handle.getAttribute('data-rule-id'), 10) : NaN;
        })
        .filter(function (id) {
          return Number.isFinite(id);
        });
    }

    function persistOrder() {
      var ids = collectIds();
      if (!ids.length || saving) {
        return;
      }
      saving = true;
      showStatus('Saving order…', false);

      fetch(reorderUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ ids: ids }),
      })
        .then(function (response) {
          return response.text().then(function (text) {
            var data = {};
            try {
              data = text ? JSON.parse(text) : {};
            } catch (e) {
              throw new Error('Reorder failed (invalid response)');
            }
            if (!response.ok || !data.ok) {
              throw new Error((data && data.error) || ('Reorder failed (' + response.status + ')'));
            }
            showStatus('Order saved.', false);
            startOrderKey = orderKey();
          });
        })
        .catch(function (err) {
          showStatus(err.message || 'Could not save order.', true);
          console.error('[DashboardPointRule] reorder failed', err);
        })
        .finally(function () {
          saving = false;
        });
    }

    rows().forEach(function (row) {
      var handle = row.querySelector('.dpr-drag-handle');
      if (!handle) {
        return;
      }

      // Drag only from the handle so list-editable inputs stay usable.
      handle.setAttribute('draggable', 'true');
      row.setAttribute('draggable', 'false');

      handle.addEventListener('dragstart', function (event) {
        dragRow = row;
        startOrderKey = orderKey();
        row.classList.add('dpr-dragging');
        try {
          event.dataTransfer.effectAllowed = 'move';
          event.dataTransfer.setData('text/plain', handle.getAttribute('data-rule-id') || '');
        } catch (e) {
          /* ignore */
        }
        // Some browsers need a tick before DOM moves work reliably.
        window.setTimeout(function () {
          row.classList.add('dpr-dragging');
        }, 0);
      });

      handle.addEventListener('dragend', function () {
        row.classList.remove('dpr-dragging');
        rows().forEach(function (r) {
          r.classList.remove('dpr-drop-target');
        });
        // drop often does not fire after DOM moves during dragover — save on dragend.
        if (dragRow && orderKey() !== startOrderKey) {
          persistOrder();
        }
        dragRow = null;
      });

      row.addEventListener('dragover', function (event) {
        if (!dragRow || dragRow === row) {
          return;
        }
        event.preventDefault();
        try {
          event.dataTransfer.dropEffect = 'move';
        } catch (e) {
          /* ignore */
        }
        row.classList.add('dpr-drop-target');
        var rect = row.getBoundingClientRect();
        var before = event.clientY < rect.top + rect.height / 2;
        if (before) {
          tbody.insertBefore(dragRow, row);
        } else if (row.nextSibling !== dragRow) {
          tbody.insertBefore(dragRow, row.nextSibling);
        }
      });

      row.addEventListener('dragleave', function () {
        row.classList.remove('dpr-drop-target');
      });

      row.addEventListener('drop', function (event) {
        event.preventDefault();
        row.classList.remove('dpr-drop-target');
        if (dragRow && orderKey() !== startOrderKey) {
          persistOrder();
        }
      });
    });
  });
})();
