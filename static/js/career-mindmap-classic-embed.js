/**
 * Career mindmap: jsMind API JSON → CounselorClassicMindmap (same renderer as counselor course classic).
 * Used by career_mindmap.html (variation 16) and careers chat/modal when DEFAULT_MINDMAP_TYPE is 16.
 */
(function (global) {
  'use strict';

  /** Bootstrap .d-flex uses display:flex !important — inline display:none does not hide the overlay. */
  function hideCareerMindmapLoading(el) {
    if (!el) return;
    try {
      el.classList.remove('d-flex');
      el.classList.add('d-none');
      el.style.setProperty('display', 'none', 'important');
      el.setAttribute('aria-hidden', 'true');
    } catch (e) {}
  }

  function stripHtml(s) {
    if (!s) return '';
    var d = document.createElement('div');
    d.innerHTML = s;
    var t = (d.textContent || '').trim().replace(/\s+/g, ' ');
    return t;
  }

  function jsMindNodeToClassicNodes(root) {
    var list = [];
    function walk(n, parentId, depth, pathIndices) {
      var id = pathIndices.length === 0 ? 'root' : 'n' + pathIndices.join('_');
      var level = depth === 0 ? 'root' : depth === 1 ? 'topic' : depth === 2 ? 'sub' : 'leaf';
      var raw = n && (n.topic != null ? n.topic : n.title);
      var text = stripHtml(raw != null ? String(raw) : '') || '—';
      if (text.length > 200) text = text.slice(0, 197) + '…';
      var o = { id: id, text: text, level: level };
      if (parentId) o.parent = parentId;
      list.push(o);
      var kids = (n && n.children) || [];
      for (var i = 0; i < kids.length; i++) {
        walk(kids[i], id, depth + 1, pathIndices.concat([i]));
      }
    }
    walk(root, null, 0, []);
    return list;
  }

  var cssLoaded = false;
  var jsPromise = null;

  function loadClassicCss(href) {
    if (cssLoaded || !href) return Promise.resolve();
    return new Promise(function (resolve) {
      var id = 'career-classic-mm-css-global';
      if (document.getElementById(id)) {
        cssLoaded = true;
        resolve();
        return;
      }
      var lk = document.createElement('link');
      lk.id = id;
      lk.rel = 'stylesheet';
      lk.href = href;
      var done = false;
      function finish() {
        if (done) return;
        done = true;
        cssLoaded = true;
        resolve();
      }
      lk.onload = finish;
      lk.onerror = finish;
      document.head.appendChild(lk);
      // Cached stylesheets often do not fire onload (WebKit / Chrome); do not hang forever.
      setTimeout(finish, 120);
    });
  }

  function loadClassicJs(src) {
    if (global.CounselorClassicMindmap) return Promise.resolve();
    if (jsPromise) return jsPromise;
    jsPromise = new Promise(function (resolve, reject) {
      var sc = document.createElement('script');
      sc.src = src;
      sc.async = true;
      sc.onload = function () {
        if (global.CounselorClassicMindmap) resolve();
        else {
          jsPromise = null;
          reject(new Error('CounselorClassicMindmap not defined'));
        }
      };
      sc.onerror = function () {
        jsPromise = null;
        reject(new Error('Failed to load classic-mindmap.js'));
      };
      document.head.appendChild(sc);
    });
    return jsPromise;
  }

  /**
   * @param {object} opts
   * @param {string} opts.apiUrl
   * @param {HTMLElement} opts.hostElement — mount target (cleared)
   * @param {HTMLElement} [opts.loadingEl]
   * @param {string} opts.cssHref — static URL to classic-mindmap.css
   * @param {string} opts.jsSrc — static URL to classic-mindmap.js
   * @param {HTMLElement} [opts.hideElement] — e.g. SVG to hide
   * @returns {Promise<{zoomIn:Function,zoomOut:Function,reset:Function,expandAll:Function,collapseAll:Function,destroy:Function}>}
   */
  function initFromApi(opts) {
    opts = opts || {};
    var apiUrl = opts.apiUrl;
    var hostEl = opts.hostElement;
    var loadingEl = opts.loadingEl;
    var cssHref = opts.cssHref;
    var jsSrc = opts.jsSrc;
    var hideEl = opts.hideElement;
    if (!apiUrl || !hostEl) return Promise.reject(new Error('CareerMindmapClassic: missing apiUrl or hostElement'));

    if (hideEl) hideEl.style.display = 'none';
    hostEl.style.display = 'block';
    hostEl.innerHTML = '';

    return fetch(apiUrl, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        if (!data || data.available === false || !data.data) throw new Error('No mindmap data');
        return loadClassicCss(cssHref)
          .then(function () {
            return loadClassicJs(jsSrc);
          })
          .then(function () {
            var nodes = jsMindNodeToClassicNodes(data.data);
            var layout = (opts.layout === 'vertical' ? 'vertical' : 'horizontal');
            return global.CounselorClassicMindmap.mount(hostEl, {
              nodes: nodes,
              layout: layout,
              fillContainer: opts.fillContainer !== false,
              initialExpandDepth: 1,
              visualStyle: opts.visualStyle === 'ribbon' ? 'ribbon' : 'pill',
            });
          });
      })
      .catch(function (err) {
        hostEl.innerHTML =
          '<p class="text-muted small p-3 mb-0">Classic mindmap could not be loaded. ' +
          (err && err.message ? String(err.message) : '') +
          '</p>';
        throw err;
      })
      .then(
        function (api) {
          hideCareerMindmapLoading(loadingEl);
          return api;
        },
        function (err) {
          hideCareerMindmapLoading(loadingEl);
          throw err;
        }
      );
  }

  global.CareerMindmapClassic = {
    jsMindNodeToClassicNodes: jsMindNodeToClassicNodes,
    initFromApi: initFromApi,
  };
})(typeof window !== 'undefined' ? window : this);
