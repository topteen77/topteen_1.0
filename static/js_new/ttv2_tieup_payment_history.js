/**
 * Tie-up payment history status tabs (All / Pending / Received / Failed).
 * Uses document delegation so filters work after v2 AJAX inject and partial reload.
 */
(function (global) {
  'use strict';

  var bound = false;

  function bootTtv2TieupPaymentHistory() {
    if (bound) return;
    bound = true;

    document.addEventListener('click', function (e) {
      var btn = e.target && e.target.closest ? e.target.closest('[data-ttv2-tieup-pay-status]') : null;
      if (!btn) return;

      var root = document.getElementById('ttv2TieupPaymentsRoot');
      if (!root || !root.contains(btn)) return;

      e.preventDefault();
      e.stopPropagation();

      var instituteSel = root.querySelector('[data-ttv2-tieup-pay-institute]');
      reloadTtv2TieupPayments(root, {
        status: btn.getAttribute('data-ttv2-tieup-pay-status'),
        institute: instituteSel ? instituteSel.value : undefined,
      });
    });

    document.addEventListener('change', function (e) {
      var sel = e.target && e.target.matches ? e.target : null;
      if (!sel || !sel.matches('[data-ttv2-tieup-pay-institute]')) return;
      var root = document.getElementById('ttv2TieupPaymentsRoot');
      if (!root || !root.contains(sel)) return;
      var curUrl = new URL(window.location.href);
      reloadTtv2TieupPayments(root, {
        institute: sel.value || '',
        status: curUrl.searchParams.get('status') || '',
      });
    });
  }

  function reloadTtv2TieupPayments(root, opts) {
    opts = opts || {};
    var url = new URL(window.location.href);
    if (opts.status !== undefined) {
      if (opts.status) url.searchParams.set('status', opts.status);
      else url.searchParams.delete('status');
    }
    if (opts.institute !== undefined) {
      if (opts.institute) url.searchParams.set('institute', opts.institute);
      else url.searchParams.delete('institute');
    }
    url.searchParams.set('ttv2_payments_partial', '1');

    var buttons = root.querySelectorAll('[data-ttv2-tieup-pay-status]');
    buttons.forEach(function (b) { b.disabled = true; });
    var instituteSel = root.querySelector('[data-ttv2-tieup-pay-institute]');
    if (instituteSel) instituteSel.disabled = true;

    fetch(url.toString(), {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
      })
        .then(function (r) {
          if (!r.ok) throw new Error('Filter request failed');
          return r.text();
        })
        .then(function (html) {
          root.outerHTML = html;
          url.searchParams.delete('ttv2_payments_partial');
          window.history.replaceState({}, '', url.toString());
        })
        .catch(function () {
          /* keep current table on error */
        })
        .finally(function () {
          var newRoot = document.getElementById('ttv2TieupPaymentsRoot');
          if (!newRoot) return;
          newRoot.querySelectorAll('[data-ttv2-tieup-pay-status]').forEach(function (b) {
            b.disabled = false;
          });
          var sel = newRoot.querySelector('[data-ttv2-tieup-pay-institute]');
          if (sel) sel.disabled = false;
        });
  }

  global.ttv2InitTieupPaymentHistory = bootTtv2TieupPaymentHistory;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootTtv2TieupPaymentHistory);
  } else {
    bootTtv2TieupPaymentHistory();
  }
  document.addEventListener('ttv2:content:loaded', bootTtv2TieupPaymentHistory);
  document.addEventListener('ttv2:afterAjaxContentLoad', bootTtv2TieupPaymentHistory);
})(window);
