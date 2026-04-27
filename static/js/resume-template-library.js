(function () {
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  }

  var cat = 'all';
  var accent = 'all';
  var selectedId = null;
  var catalog = [];
  var rid = String(window.__TT_RESUME_ID || '');
  var prevBase = (window.__TT_RESUME_PREVIEW_URL || '').replace(/\/?$/, '/');
  if (prevBase.indexOf('?') === -1 && !prevBase.endsWith('/')) {
    prevBase = window.__TT_RESUME_PREVIEW_URL || '';
  }

  function parseCatalogFromJsonScript() {
    var el = document.getElementById('rtl-library-catalog');
    if (!el || !el.textContent) return [];
    try {
      var parsed = JSON.parse(el.textContent);
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function syncCatalogFromDom() {
    var grid = document.getElementById('rtl-template-grid');
    if (!grid) return [];
    var out = [];
    grid.querySelectorAll('.rtl-card').forEach(function (el) {
      var id = parseInt(el.getAttribute('data-id'), 10);
      if (isNaN(id)) return;
      out.push({
        id: id,
        category: String(el.getAttribute('data-category') || '').toLowerCase(),
        accent_hex: el.getAttribute('data-accent') || '',
        layout: el.getAttribute('data-layout') || '',
      });
    });
    return out;
  }

  function resolveCatalog() {
    var fromDom = syncCatalogFromDom();
    if (fromDom.length) return fromDom;
    var fromJson = parseCatalogFromJsonScript();
    if (fromJson.length) return fromJson;
    var w = window.__TT_LIBRARY_CATALOG;
    return Array.isArray(w) ? w : [];
  }

  function cardVisible(item) {
    if (cat !== 'all' && String(item.category || '').toLowerCase() !== cat) return false;
    if (accent !== 'all' && String(item.accent_hex || '').toLowerCase() !== String(accent).toLowerCase())
      return false;
    return true;
  }

  function setPdfHref() {
    var pdfA = document.getElementById('rtl-btn-pdf');
    if (!pdfA) return;
    var base = (window.__TT_RESUME_PDF_URL || '').split('#')[0];
    var u = base.indexOf('?') >= 0 ? base : base + '?resume_id=' + encodeURIComponent(rid);
    if (selectedId) u += (u.indexOf('?') >= 0 ? '&' : '?') + 'template_id=' + encodeURIComponent(selectedId);
    pdfA.href = u;
  }

  function setFrameSrc() {
    var frame = document.getElementById('rtl-preview-frame');
    if (!frame || !window.__TT_RESUME_PREVIEW_URL) return;
    var u = window.__TT_RESUME_PREVIEW_URL + '?resume_id=' + encodeURIComponent(rid);
    if (selectedId) u += '&template_id=' + encodeURIComponent(selectedId);
    frame.src = u;
  }

  function paintCards() {
    var grid = document.getElementById('rtl-template-grid');
    if (!grid || grid.querySelector('.rtl-card')) return;
    if (!catalog.length) return;
    grid.innerHTML = catalog
      .map(function (t) {
        var layout = esc((t.layout || 'v01').toLowerCase());
        var ac = esc(t.accent_hex || '#19718c');
        var ccat = esc(String(t.category || '').toLowerCase());
        return (
          '<article class="rtl-card" data-id="' +
          t.id +
          '" data-category="' +
          ccat +
          '" data-accent="' +
          ac +
          '" data-layout="' +
          layout +
          '">' +
          '<div class="rtl-thumb" style="--c:' +
          ac +
          '">' +
          '<div class="mock"><div style="flex:1;display:flex;flex-direction:column;width:100%">' +
          '<div class="bar"></div><div class="body"><div class="main">' +
          '<div class="ln"></div><div class="ln" style="width:70%"></div><div class="ln" style="width:88%"></div>' +
          '</div><div class="side"></div></div></div></div>' +
          '<div class="rtl-card-meta"><strong>' +
          esc(t.name) +
          '</strong>' +
          ccat +
          ' · ' +
          layout +
          '</div></article>'
        );
      })
      .join('');
  }

  function bindCardClicks(grid) {
    grid.querySelectorAll('.rtl-card').forEach(function (el) {
      if (el.getAttribute('data-tt-bound') === '1') return;
      el.setAttribute('data-tt-bound', '1');
      el.addEventListener('click', function () {
        selectedId = parseInt(el.getAttribute('data-id'), 10);
        grid.querySelectorAll('.rtl-card').forEach(function (c) {
          c.classList.remove('on');
        });
        el.classList.add('on');
        var hid = document.getElementById('rtl-selected-template-id');
        var btn = document.getElementById('rtl-apply-btn');
        if (hid) hid.value = String(selectedId);
        if (btn) btn.disabled = false;
        setFrameSrc();
        setPdfHref();
      });
    });
  }

  function renderGrid() {
    var grid = document.getElementById('rtl-template-grid');
    if (!grid) return;
    paintCards();
    bindCardClicks(grid);
    refilterClasses();
  }

  function refilterClasses() {
    var grid = document.getElementById('rtl-template-grid');
    if (!grid) return;
    grid.querySelectorAll('.rtl-card').forEach(function (el) {
      var id = parseInt(el.getAttribute('data-id'), 10);
      var item = catalog.find(function (x) {
        return Number(x.id) === id;
      });
      el.classList.toggle('hide', !!(item && !cardVisible(item)));
    });
  }

  function boot() {
    catalog = resolveCatalog();
    renderGrid();

    var first = catalog.find(function (t) {
      return cardVisible(t);
    });
    if (first) {
      selectedId = Number(first.id);
      var hid = document.getElementById('rtl-selected-template-id');
      var btn = document.getElementById('rtl-apply-btn');
      if (hid) hid.value = String(selectedId);
      if (btn) btn.disabled = false;
      var el = document.querySelector('.rtl-card[data-id="' + first.id + '"]');
      if (el) el.classList.add('on');
    }
    setFrameSrc();
    setPdfHref();

    var catFilters = document.getElementById('rtl-cat-filters');
    if (catFilters) {
      catFilters.addEventListener('click', function (ev) {
        var b = ev.target.closest ? ev.target.closest('button[data-cat]') : null;
        if (!b) return;
        cat = b.getAttribute('data-cat') || 'all';
        document.querySelectorAll('#rtl-cat-filters button').forEach(function (x) {
          x.classList.remove('on');
        });
        b.classList.add('on');
        refilterClasses();
      });
    }
    var colorFilters = document.getElementById('rtl-color-filters');
    if (colorFilters) {
      colorFilters.addEventListener('click', function (ev) {
        var b = ev.target.closest ? ev.target.closest('button[data-accent]') : null;
        if (!b) return;
        accent = b.getAttribute('data-accent') || 'all';
        document.querySelectorAll('#rtl-color-filters button').forEach(function (x) {
          x.classList.remove('on');
        });
        b.classList.add('on');
        refilterClasses();
      });
    }

    var printBtn = document.getElementById('rtl-btn-print');
    if (printBtn) {
      printBtn.addEventListener('click', function () {
        var frame = document.getElementById('rtl-preview-frame');
        if (!frame || !frame.contentWindow) return;
        try {
          frame.contentWindow.focus();
          frame.contentWindow.print();
        } catch (e) {}
      });
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
