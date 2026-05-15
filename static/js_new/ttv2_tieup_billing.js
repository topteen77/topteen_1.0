/**
 * Institute / group tie-up billing: coupon select + preview + Pay Now.
 * Same behaviour for single institute and group institute dashboards.
 */
(function (global) {
  'use strict';

  function readCookie(name) {
    var m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return m ? decodeURIComponent(m[2]) : '';
  }

  function getCsrfToken(root) {
    var el = (root && root.querySelector('input[name="csrfmiddlewaretoken"]')) ||
      document.querySelector('#ttv2TieupBillingRoot input[name="csrfmiddlewaretoken"]') ||
      document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (el && el.value) {
      return el.value;
    }
    if (global.ttv2GetCsrfToken) {
      return global.ttv2GetCsrfToken();
    }
    return readCookie('csrftoken') || '';
  }

  function msg(el, text, isError) {
    if (!el) return;
    el.textContent = text || '';
    el.className = 'small mt-2 ' + (isError ? 'text-danger' : 'text-success');
  }

  function ensureRazorpayScript(cb) {
    if (global.Razorpay) {
      cb();
      return;
    }
    var existing = document.querySelector('script[data-ttv2-razorpay-checkout]');
    if (existing) {
      existing.addEventListener('load', cb);
      return;
    }
    var s = document.createElement('script');
    s.src = 'https://checkout.razorpay.com/v1/checkout.js';
    s.setAttribute('data-ttv2-razorpay-checkout', '1');
    s.onload = cb;
    s.onerror = function () {
      alert('Could not load payment checkout. Please refresh and try again.');
    };
    document.head.appendChild(s);
  }

  function getCouponCodeFromUi() {
    var sel = document.getElementById('tieupCouponSelect');
    var inp = document.getElementById('tieupCouponCode');
    var manual = inp ? (inp.value || '').trim() : '';
    if (manual) return manual.toUpperCase();
    if (sel && sel.value) return sel.value.trim().toUpperCase();
    return '';
  }

  function syncManualFromSelect() {
    var sel = document.getElementById('tieupCouponSelect');
    var inp = document.getElementById('tieupCouponCode');
    if (!sel || !inp) return;
    if (sel.value) {
      inp.value = sel.value;
    }
  }

  function renderCouponSelect(selectEl, applySelectedBtn, coupons) {
    if (!selectEl) return;
    var current = selectEl.value;
    selectEl.innerHTML = '';
    var empty = document.createElement('option');
    empty.value = '';
    empty.textContent = '— No coupon —';
    selectEl.appendChild(empty);
    (coupons || []).forEach(function (c) {
      var opt = document.createElement('option');
      opt.value = c.code;
      opt.textContent = (c.label || c.code) + ' → pay ₹' + (c.final_amount || '0');
      if (c.discount_amount) {
        opt.setAttribute('data-discount', c.discount_amount);
      }
      if (c.final_amount) {
        opt.setAttribute('data-final', c.final_amount);
      }
      selectEl.appendChild(opt);
    });
    if (current) {
      selectEl.value = current;
    }
    if (applySelectedBtn) {
      applySelectedBtn.disabled = !(coupons && coupons.length);
    }
  }

  function fetchCoupons(listUrl, orderId, root, selectEl, applySelectedBtn) {
    if (!listUrl || !orderId) return;
    var csrf = getCsrfToken(root);
    var url = listUrl + (listUrl.indexOf('?') >= 0 ? '&' : '?') + 'order_id=' + encodeURIComponent(orderId);
    fetch(url, { method: 'GET', headers: { 'X-CSRFToken': csrf }, credentials: 'same-origin' })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (res) {
        if (res.ok && res.data && res.data.success) {
          renderCouponSelect(selectEl, applySelectedBtn, res.data.coupons || []);
        }
      })
      .catch(function () { /* keep server-rendered options */ });
  }

  function applyCoupon(root, previewUrl, orderId, code, applyBtn) {
    var csrf = getCsrfToken(root);
    var fd = new FormData();
    fd.append('order_id', orderId);
    fd.append('coupon_code', code || '');
    fd.append('csrfmiddlewaretoken', csrf);
    if (applyBtn) applyBtn.disabled = true;
    return fetch(previewUrl, { method: 'POST', headers: { 'X-CSRFToken': csrf }, body: fd, credentials: 'same-origin' })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, status: r.status, data: d }; }); })
      .then(function (res) {
        var d = res.data || {};
        var couponMsg = document.getElementById('tieupCouponMsg');
        var sel = document.getElementById('tieupCouponSelect');
        var inp = document.getElementById('tieupCouponCode');
        if (res.ok && d.success) {
          var note = 'Discount ₹' + d.discount + ', pay ₹' + d.final_amount;
          if (d.capped && d.capped_message) {
            note += ' — ' + d.capped_message;
          }
          msg(couponMsg, note, false);
          var fa = document.getElementById('tieupFinalAmount');
          if (fa) fa.textContent = '₹' + d.final_amount;
          if (code && sel) {
            sel.value = code;
          }
          if (code && inp) {
            inp.value = code;
          }
        } else if (res.status === 403) {
          msg(couponMsg, 'Session expired. Refresh the page and try again.', true);
        } else {
          msg(couponMsg, d.error || 'Invalid coupon', true);
        }
        return res;
      })
      .catch(function () {
        msg(document.getElementById('tieupCouponMsg'), 'Could not validate coupon.', true);
      })
      .finally(function () {
        if (applyBtn) applyBtn.disabled = false;
      });
  }

  function clearCouponUi() {
    var sel = document.getElementById('tieupCouponSelect');
    var inp = document.getElementById('tieupCouponCode');
    if (sel) sel.value = '';
    if (inp) inp.value = '';
    msg(document.getElementById('tieupCouponMsg'), '', false);
  }

  function initTtv2TieupBilling(root) {
    if (!root || root.getAttribute('data-ttv2-tieup-init') === '1') return;
    root.setAttribute('data-ttv2-tieup-init', '1');

    var orderId = root.getAttribute('data-order-id') || '';
    var createUrl = root.getAttribute('data-create-order-url') || '';
    var verifyUrl = root.getAttribute('data-verify-url') || '';
    var previewUrl = root.getAttribute('data-coupon-preview-url') || '';
    var listCouponsUrl = root.getAttribute('data-list-coupons-url') || '';
    var couponSelect = document.getElementById('tieupCouponSelect');
    var applySelectedBtn = document.getElementById('tieupApplySelectedCoupon');

    function runApply(code, btn) {
      if (!previewUrl || !orderId) return;
      applyCoupon(root, previewUrl, orderId, code, btn);
    }

    if (couponSelect) {
      couponSelect.addEventListener('change', function () {
        syncManualFromSelect();
      });
    }

    if (applySelectedBtn) {
      applySelectedBtn.addEventListener('click', function () {
        if (!orderId) {
          msg(document.getElementById('tieupCouponMsg'), 'No pending order.', true);
          return;
        }
        var code = getCouponCodeFromUi();
        if (!code) {
          msg(document.getElementById('tieupCouponMsg'), 'Select or enter a coupon code.', true);
          return;
        }
        runApply(code, applySelectedBtn);
      });
    }

    var clearBtn = document.getElementById('tieupClearCoupon');
    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        clearCouponUi();
        if (orderId && previewUrl) {
          runApply('', clearBtn);
        }
      });
    }

    var instSel = document.getElementById('tieupInstituteSelect');
    if (instSel) {
      function syncInstitute() {
        var opt = instSel.options[instSel.selectedIndex];
        if (!opt) return;
        orderId = opt.getAttribute('data-order-id') || '';
        createUrl = opt.getAttribute('data-create-url') || '';
        previewUrl = opt.getAttribute('data-preview-url') || '';
        listCouponsUrl = opt.getAttribute('data-list-url') || listCouponsUrl;
        root.setAttribute('data-order-id', orderId);
        root.setAttribute('data-create-order-url', createUrl);
        root.setAttribute('data-coupon-preview-url', previewUrl);
        root.setAttribute('data-list-coupons-url', listCouponsUrl);
        var fa = document.getElementById('tieupFinalAmount');
        if (fa) fa.textContent = '₹' + (opt.getAttribute('data-pending-total') || '0');
        clearCouponUi();
        fetchCoupons(listCouponsUrl, orderId, root, couponSelect, applySelectedBtn);
      }
      instSel.addEventListener('change', syncInstitute);
      syncInstitute();
    } else if (listCouponsUrl && orderId) {
      fetchCoupons(listCouponsUrl, orderId, root, couponSelect, applySelectedBtn);
    }

    var applyBtn = document.getElementById('tieupApplyCoupon');
    if (applyBtn) {
      applyBtn.addEventListener('click', function () {
        if (!previewUrl) {
          msg(document.getElementById('tieupCouponMsg'), 'Coupon preview is not available.', true);
          return;
        }
        if (!orderId) {
          msg(document.getElementById('tieupCouponMsg'), 'No pending order to apply a coupon to.', true);
          return;
        }
        var code = getCouponCodeFromUi();
        if (!code) {
          runApply('', applyBtn);
          return;
        }
        runApply(code, applyBtn);
      });
    }

    var payBtn = document.getElementById('tieupPayNow');
    if (payBtn) {
      payBtn.addEventListener('click', function () {
        if (!createUrl) {
          alert('Payment is not available on this page. Open Payments from the sidebar.');
          return;
        }
        if (!orderId) {
          alert('No pending order to pay.');
          return;
        }
        var csrf = getCsrfToken(root);
        var code = getCouponCodeFromUi();
        var fd = new FormData();
        fd.append('order_id', orderId);
        fd.append('coupon_code', code);
        fd.append('csrfmiddlewaretoken', csrf);
        payBtn.disabled = true;
        fetch(createUrl, { method: 'POST', headers: { 'X-CSRFToken': csrf }, body: fd, credentials: 'same-origin' })
          .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, status: r.status, data: d }; }); })
          .then(function (res) {
            var data = res.data || {};
            if (!res.ok || !data.success) {
              if (res.status === 403) {
                alert('Session expired. Refresh the page and try again.');
              } else {
                alert(data.error || 'Could not start payment');
              }
              return;
            }
            if (data.gateway === 'eazypay' && data.payment_url) {
              global.location.href = data.payment_url;
              return;
            }
            if (data.gateway === 'razorpay' || data.order_id) {
              ensureRazorpayScript(function () {
                var opts = {
                  key: data.key,
                  amount: data.amount_paise,
                  currency: 'INR',
                  name: 'TopTeen',
                  description: 'Institute tie-up',
                  order_id: data.order_id,
                  handler: function (resp) {
                    fetch(verifyUrl, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                      credentials: 'same-origin',
                      body: JSON.stringify({
                        payment_id: data.payment_record_id,
                        gateway_payment_id: resp.razorpay_payment_id,
                        gateway_order_id: resp.razorpay_order_id,
                        gateway_signature: resp.razorpay_signature,
                      }),
                    })
                      .then(function (r) { return r.json(); })
                      .then(function (v) {
                        if (v.success && v.redirect_url) {
                          global.location.href = v.redirect_url;
                        } else {
                          alert(v.error || 'Verification failed');
                        }
                      })
                      .catch(function () {
                        alert('Verification request failed.');
                      });
                  },
                };
                new global.Razorpay(opts).open();
              });
              return;
            }
            alert('Unsupported payment gateway response.');
          })
          .catch(function () {
            alert('Could not start payment. Please try again.');
          })
          .finally(function () { payBtn.disabled = false; });
      });
    }
  }

  function bootTtv2TieupBilling() {
    var root = document.getElementById('ttv2TieupBillingRoot');
    if (root) initTtv2TieupBilling(root);
  }

  global.ttv2InitTieupBilling = bootTtv2TieupBilling;

  document.addEventListener('DOMContentLoaded', bootTtv2TieupBilling);
  document.addEventListener('ttv2:content:loaded', bootTtv2TieupBilling);
  document.addEventListener('ttv2:afterAjaxContentLoad', bootTtv2TieupBilling);
})(window);
