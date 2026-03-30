/**
 * Live preview: Price + checkout line when MRP, discount %, currency, or dynamic price change.
 * Matches server logic in CounselorCourse.apply_discount_from_percent / get_charge_amount_rupees.
 */
(function () {
  'use strict';

  function parseIntSafe(v, defaultValue) {
    if (v === undefined || v === null || String(v).trim() === '') {
      return defaultValue;
    }
    var n = parseInt(v, 10);
    return isNaN(n) ? defaultValue : n;
  }

  function currencySymbol() {
    var sel = document.getElementById('id_currency');
    if (!sel) {
      return '₹';
    }
    return sel.value === '0' ? '$' : '₹';
  }

  function setCalculatedAmount(value) {
    var display = document.querySelector('.field-amount .readonly');
    if (!display) {
      display = document.querySelector('.field-amount p.readonly');
    }
    if (!display) {
      display = document.querySelector('.field-amount div.readonly');
    }
    if (display) {
      display.textContent = String(value);
    }
    var input = document.querySelector('input#id_amount');
    if (input) {
      input.value = value;
    }
  }

  function recalc() {
    var mrp = parseIntSafe(document.getElementById('id_actual_price') && document.getElementById('id_actual_price').value, 0);
    var discRaw = parseIntSafe(document.getElementById('id_discount_percent') && document.getElementById('id_discount_percent').value, 0);
    var disc = Math.min(100, Math.max(0, discRaw));
    var calculated = Math.max(0, Math.round(mrp * (100 - disc) / 100.0));

    setCalculatedAmount(calculated);

    var dynEl = document.getElementById('id_dynamic_price');
    var charge = calculated;
    if (dynEl && String(dynEl.value).trim() !== '') {
      var d = parseIntSafe(dynEl.value, NaN);
      if (!isNaN(d) && d >= 0) {
        charge = d;
      }
    }

    var symEl = document.getElementById('counselor-checkout-symbol');
    var valEl = document.getElementById('counselor-checkout-value');
    if (symEl) {
      symEl.textContent = currencySymbol();
    }
    if (valEl) {
      valEl.textContent = charge;
    }
  }

  function bind() {
    ['id_actual_price', 'id_discount_percent', 'id_currency', 'id_dynamic_price'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) {
        el.addEventListener('input', recalc);
        el.addEventListener('change', recalc);
      }
    });
    recalc();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
