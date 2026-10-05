/**
 * Pending-approval View / Approve / Reject.
 *
 * Marketing dashboard HTML is injected with innerHTML, so <script> tags inside
 * the partial never run. These handlers live on the shell and stay active.
 */
(function (global) {
  if (global.__ttv2PendingApprovalBound) return;
  global.__ttv2PendingApprovalBound = true;

  function eventElement(e) {
    var t = e && e.target;
    if (!t) return null;
    if (t.nodeType === 1) return t;
    return t.parentElement || null;
  }

  function closest(e, selector) {
    var el = eventElement(e);
    if (!el || !el.closest) return null;
    return el.closest(selector);
  }

  function val(el, name) {
    return (el && el.getAttribute(name)) || '';
  }

  function setContactNode(n, raw) {
    if (!n) return;
    var v = (raw || '').trim();
    n.textContent = '';
    if (!v) {
      n.textContent = '—';
      return;
    }
    var a = document.createElement('a');
    a.href = (v.indexOf('@') >= 0 ? 'mailto:' : 'tel:') + v;
    a.textContent = v;
    n.appendChild(a);
  }

  function disposeModal(node) {
    try {
      if (global.bootstrap && bootstrap.Modal) {
        var inst = bootstrap.Modal.getInstance(node);
        if (inst) inst.dispose();
      }
    } catch (err) {}
  }

  function takeModal(id) {
    var nodes = document.querySelectorAll('[id="' + id + '"]');
    if (!nodes.length) return null;
    var el = nodes[nodes.length - 1];
    for (var i = 0; i < nodes.length - 1; i++) {
      disposeModal(nodes[i]);
      if (nodes[i].parentNode) nodes[i].parentNode.removeChild(nodes[i]);
    }
    if (el.parentNode !== document.body) document.body.appendChild(el);
    return el;
  }

  function showModal(el) {
    if (!el || !global.bootstrap || !bootstrap.Modal) return false;
    bootstrap.Modal.getOrCreateInstance(el).show();
    return true;
  }

  function approveUrl(id) {
    var form = document.getElementById('ttv2ApproveBillingForm');
    var tpl = form ? (form.getAttribute('data-approve-url-template') || '') : '';
    if (tpl && id) return tpl.replace('/0/', '/' + id + '/');
    return id ? ('/institute/institute_approve_billing/' + id + '/') : '';
  }

  function openApprove(btn) {
    var id = val(btn, 'data-institute-id');
    var name = val(btn, 'data-institute-name');
    var modal = takeModal('ttv2ApproveInstituteBillingModal');
    var form = modal ? modal.querySelector('#ttv2ApproveBillingForm') : document.getElementById('ttv2ApproveBillingForm');
    var nameEl = modal ? modal.querySelector('#ttv2ApproveInstName') : document.getElementById('ttv2ApproveInstName');
    if (nameEl) nameEl.textContent = name || '—';
    if (form && id) {
      var tpl = form.getAttribute('data-approve-url-template') || '';
      form.action = (tpl && id) ? tpl.replace('/0/', '/' + id + '/') : approveUrl(id);
    }
    if (showModal(modal)) return;
    var fallback = id ? ('/institute/institute_approve/' + id + '/') : '';
    if (fallback) window.location.href = fallback;
  }

  function openView(btn) {
    var modal = takeModal('ttv2PendingInstituteViewModal');
    var name = val(btn, 'data-institute-name');
    var slug = val(btn, 'data-institute-slug');
    var id = val(btn, 'data-institute-id');
    var days = val(btn, 'data-institute-days');
    var urgency = val(btn, 'data-institute-urgency');
    var wait = days === '0'
      ? 'Registered today'
      : ('Waiting ' + (days || '0') + ' day' + (days === '1' ? '' : 's'));
    if (urgency) wait += ' · ' + urgency;
    function inModal(sel) {
      return modal ? modal.querySelector(sel) : document.querySelector(sel);
    }
    var nameEl = inModal('#ttv2PendingViewName');
    if (nameEl) nameEl.textContent = name || '—';
    var waitEl = inModal('#ttv2PendingViewWait');
    if (waitEl) waitEl.textContent = wait;
    var createdEl = inModal('#ttv2PendingViewCreated');
    if (createdEl) createdEl.textContent = val(btn, 'data-institute-created') || '—';
    setContactNode(inModal('#ttv2PendingViewEmail'), val(btn, 'data-institute-email'));
    setContactNode(inModal('#ttv2PendingViewMobile'), val(btn, 'data-institute-mobile'));
    setContactNode(inModal('#ttv2PendingViewContact'), val(btn, 'data-institute-contact'));
    var adminEl = inModal('#ttv2PendingViewAdmin');
    if (adminEl) adminEl.textContent = val(btn, 'data-institute-admin') || '—';
    var addressEl = inModal('#ttv2PendingViewAddress');
    if (addressEl) addressEl.textContent = val(btn, 'data-institute-address') || '—';
    var open = inModal('#ttv2PendingViewOpen');
    if (open) {
      open.href = slug ? ('/institute/' + encodeURIComponent(slug) + '/dashboard/') : '#';
    }
    var approve = inModal('#ttv2PendingViewApprove');
    if (approve) {
      approve.setAttribute('data-ttv2-approve-billing', '1');
      approve.setAttribute('data-institute-id', id);
      approve.setAttribute('data-institute-name', name);
    }
    var reject = inModal('#ttv2PendingViewReject');
    if (reject) {
      reject.href = id ? ('/institute/institute_reject/' + id + '/') : '#';
      reject.setAttribute('data-no-ttv2-ajax', '1');
    }
    showModal(modal);
  }

  document.addEventListener('click', function (e) {
    var viewBtn = closest(e, '[data-ttv2-pending-view]');
    if (viewBtn) {
      e.preventDefault();
      openView(viewBtn);
      return;
    }
    var approveBtn = closest(e, '[data-ttv2-approve-billing]');
    if (approveBtn) {
      e.preventDefault();
      openApprove(approveBtn);
    }
  });

  function formatInr(n) {
    return '₹' + n.toFixed(2);
  }

  function recalc(root) {
    if (!root) return;
    var total = 0;
    root.querySelectorAll('.tieup-qty').forEach(function (qtyEl) {
      var qty = parseFloat(qtyEl.value) || 0;
      if (qty < 0) {
        qty = 0;
        qtyEl.value = '0';
      }
      var priceName = qtyEl.getAttribute('data-unit');
      var priceEl = priceName ? root.querySelector('[name="' + priceName + '"]') : null;
      var price = priceEl ? (parseFloat(priceEl.value) || 0) : 0;
      if (price < 0 && priceEl) {
        price = 0;
        priceEl.value = '0';
      }
      var sub = qty * price;
      total += sub;
      var subEl = root.querySelector('.tieup-subtotal[data-for="' + qtyEl.name + '"]');
      if (subEl) subEl.textContent = formatInr(sub);
    });
    root.querySelectorAll('.tieup-order-total').forEach(function (totEl) {
      totEl.textContent = formatInr(total);
    });
  }

  document.addEventListener('input', function (e) {
    var t = eventElement(e);
    if (!t || !t.classList) return;
    if (!t.classList.contains('tieup-qty') && !t.classList.contains('tieup-price')) return;
    recalc(t.closest('.tieup-billing-block'));
  });

  document.addEventListener('shown.bs.modal', function (e) {
    var modal = e.target;
    if (!modal || !modal.querySelectorAll) return;
    modal.querySelectorAll('.tieup-billing-block').forEach(recalc);
  });
})(window);
