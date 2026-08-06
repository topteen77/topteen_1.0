/**
 * TopTeen client-side Screen Reader (Speech Synthesis).
 *
 * Reads ONLY visible content text from:
 *   headings, paragraphs, lists, tables, blockquotes
 * Skips: images/media, menus, sidebars, widgets, footers, forms/controls
 * Speaks plain text only — never HTML tags or attributes (alt/aria/title).
 * Selection → read selection; otherwise from top of main content.
 */
(function (global) {
  'use strict';

  var PREF_KEY = 'tt_voice_screen_reader';
  var PREF_RATE = 'tt_voice_sr_rate';
  var PREF_VOL = 'tt_voice_sr_volume';
  var STYLE_ID = 'tt-sr-styles';
  var CAPTION_ID = 'tt-sr-caption';
  var HIGHLIGHT_CLASS = 'tt-sr-reading';
  var CONTROLS_ID = 'tt-sr-controls';

  /** Chrome to never read (menus, widgets, footers, media, controls). */
  var SKIP_SEL = [
    'script', 'style', 'noscript', 'template',
    'svg', 'canvas', 'iframe', 'object', 'embed',
    'img', 'picture', 'video', 'audio', 'map', 'area',
    'button', 'input', 'select', 'textarea', 'option', 'datalist',
    'nav', 'header', 'footer', 'aside',
    '[role="navigation"]', '[role="banner"]', '[role="contentinfo"]',
    '[role="menu"]', '[role="menubar"]', '[role="toolbar"]',
    '[role="complementary"]', '[aria-hidden="true"]',
    '.std-shell-topbar', '.std-shell-sidebar', '.std-shell-brand-wrap',
    '.student-dash-sidebar', '.profile-sidebar', '.parent-sidebar',
    '#mobileProfileDrawer', '.offcanvas', '.modal', '.modal-backdrop',
    '.offcanvas-backdrop', '.dropdown-menu', '.breadcrumb',
    '#tt-voice-fab-wrap', '#tt-voice-bar', '#tt-voice-panel', '#ttVoiceNavBar',
    '#tt-sr-caption', '#tt-sr-controls', '#cb-fab-wrap', '#cb-root', '#pc-fab', '#pc-root',
    '#eu-cookie-consent', '.pwa-update-banner', '.footer', '.site-footer',
    '.footer-cta', '.note-mic-btn', '.note-screen-reader-btn', '.ttvw-chip',
    '.navbar', '.nav-menu', '.main-menu', '.bottom-nav'
  ].join(',');

  /** Only these content tags are read (visible text nodes only). */
  var READ_TAGS = {
    h1: 'heading', h2: 'heading', h3: 'heading', h4: 'heading',
    h5: 'heading', h6: 'heading',
    p: 'paragraph',
    li: 'list',
    dt: 'list', dd: 'list',
    td: 'table', th: 'table',
    caption: 'table',
    blockquote: 'paragraph',
    figcaption: 'paragraph'
  };

  var state = {
    enabled: false,
    speaking: false,
    queue: [],
    index: 0,
    timer: null,
    keepAlive: null,
    activeEl: null,
    captionEl: null,
    controlsEl: null,
    voicesReady: false,
    rate: 1,
    volume: 1,
    currentUtterance: null,
    chunkToken: 0
  };

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    var css = document.createElement('style');
    css.id = STYLE_ID;
    css.textContent = [
      '.' + HIGHLIGHT_CLASS + '{',
      'outline: 2px solid #0d9488 !important;',
      'outline-offset: 2px;',
      'background: rgba(13,148,136,0.18) !important;',
      'border-radius: 4px;',
      'transition: background .15s ease;',
      '}',
      '#' + CAPTION_ID + '{',
      'position:fixed;left:50%;bottom:calc(72px + env(safe-area-inset-bottom,0px));',
      'transform:translateX(-50%);z-index:2147483646;',
      'max-width:min(920px,calc(100vw - 24px));',
      'background:#0f766e;color:#fff;padding:10px 14px;border-radius:12px;',
      'font:600 14px/1.45 system-ui,Segoe UI,sans-serif;',
      'box-shadow:0 10px 28px rgba(15,118,110,.35);',
      'display:none;pointer-events:none;',
      '}',
      '#' + CAPTION_ID + '.is-on{display:block;}',
      '#' + CAPTION_ID + ' mark{',
      'background:#fef08a;color:#134e4a;border-radius:3px;padding:0 2px;',
      '}',
      '#' + CONTROLS_ID + '{',
      'position:fixed;left:50%;bottom:calc(12px + env(safe-area-inset-bottom,0px));',
      'transform:translateX(-50%);z-index:2147483646;',
      'width:min(420px,calc(100vw - 24px));',
      'background:#fff;border:1px solid #99f6e4;border-radius:14px;',
      'box-shadow:0 10px 28px rgba(15,118,110,.22);',
      'padding:10px 12px;display:none;font:12px/1.3 system-ui,Segoe UI,sans-serif;color:#134e4a;',
      '}',
      '#' + CONTROLS_ID + '.is-on{display:block;}',
      '#' + CONTROLS_ID + ' .tt-sr-ctrl-row{',
      'display:flex;align-items:center;gap:8px;margin:6px 0;',
      '}',
      '#' + CONTROLS_ID + ' label{flex:0 0 54px;font-weight:700;}',
      '#' + CONTROLS_ID + ' input[type=range]{flex:1;min-width:0;}',
      '#' + CONTROLS_ID + ' .tt-sr-ctrl-val{flex:0 0 42px;text-align:right;font-variant-numeric:tabular-nums;}',
      '#' + CONTROLS_ID + ' .tt-sr-ctrl-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:4px;}',
      '#' + CONTROLS_ID + ' .tt-sr-ctrl-actions button{',
      'border:1px solid #99f6e4;background:#f0fdfa;color:#0f766e;',
      'border-radius:999px;padding:6px 12px;font-weight:700;cursor:pointer;',
      '}'
    ].join('');
    document.head.appendChild(css);
  }

  function clamp(n, min, max) {
    n = Number(n);
    if (isNaN(n)) return min;
    return Math.min(max, Math.max(min, n));
  }

  function loadRateVol() {
    try {
      var r = parseFloat(global.localStorage.getItem(PREF_RATE));
      var v = parseFloat(global.localStorage.getItem(PREF_VOL));
      state.rate = clamp(isNaN(r) ? 1 : r, 0.5, 2);
      state.volume = clamp(isNaN(v) ? 1 : v, 0, 1);
    } catch (e) {
      state.rate = 1;
      state.volume = 1;
    }
  }

  function saveRateVol() {
    try {
      global.localStorage.setItem(PREF_RATE, String(state.rate));
      global.localStorage.setItem(PREF_VOL, String(state.volume));
    } catch (e) {}
  }

  function ensureCaption() {
    injectStyles();
    var el = document.getElementById(CAPTION_ID);
    if (el) {
      state.captionEl = el;
      return el;
    }
    el = document.createElement('div');
    el.id = CAPTION_ID;
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
    document.body.appendChild(el);
    state.captionEl = el;
    return el;
  }

  function formatRate(r) {
    return (Math.round(clamp(r, 0.5, 2) * 100) / 100).toFixed(2) + 'x';
  }

  function formatVol(v) {
    return Math.round(clamp(v, 0, 1) * 100) + '%';
  }

  function syncControlLabels() {
    if (!state.controlsEl) return;
    var rateVal = state.controlsEl.querySelector('[data-tt-sr-rate-val]');
    var volVal = state.controlsEl.querySelector('[data-tt-sr-vol-val]');
    var rateIn = state.controlsEl.querySelector('[data-tt-sr-rate]');
    var volIn = state.controlsEl.querySelector('[data-tt-sr-vol]');
    if (rateVal) rateVal.textContent = formatRate(state.rate);
    if (volVal) volVal.textContent = formatVol(state.volume);
    if (rateIn) rateIn.value = String(state.rate);
    if (volIn) volIn.value = String(state.volume);
  }

  function ensureControls() {
    injectStyles();
    var el = document.getElementById(CONTROLS_ID);
    if (el) {
      state.controlsEl = el;
      syncControlLabels();
      return el;
    }
    el = document.createElement('div');
    el.id = CONTROLS_ID;
    el.innerHTML = [
      '<div class="tt-sr-ctrl-row">',
      '  <label for="tt-sr-rate">Speed</label>',
      '  <input id="tt-sr-rate" type="range" min="0.5" max="2" step="0.05" data-tt-sr-rate />',
      '  <span class="tt-sr-ctrl-val" data-tt-sr-rate-val></span>',
      '</div>',
      '<div class="tt-sr-ctrl-row">',
      '  <label for="tt-sr-vol">Volume</label>',
      '  <input id="tt-sr-vol" type="range" min="0" max="1" step="0.05" data-tt-sr-vol />',
      '  <span class="tt-sr-ctrl-val" data-tt-sr-vol-val></span>',
      '</div>',
      '<div class="tt-sr-ctrl-actions">',
      '  <button type="button" data-tt-sr-stop>Stop</button>',
      '</div>'
    ].join('');
    document.body.appendChild(el);
    state.controlsEl = el;

    var rateIn = el.querySelector('[data-tt-sr-rate]');
    var volIn = el.querySelector('[data-tt-sr-vol]');
    var stopBtn = el.querySelector('[data-tt-sr-stop]');
    if (rateIn) {
      rateIn.addEventListener('input', function () {
        setRate(rateIn.value, true);
      });
    }
    if (volIn) {
      volIn.addEventListener('input', function () {
        setVolume(volIn.value, true);
      });
    }
    if (stopBtn) {
      stopBtn.addEventListener('click', function () {
        stop();
      });
    }
    syncControlLabels();
    return el;
  }

  function showControls() {
    var el = ensureControls();
    el.classList.add('is-on');
  }

  function hideControls() {
    if (state.controlsEl) state.controlsEl.classList.remove('is-on');
  }

  function hideCaption() {
    if (state.captionEl) {
      state.captionEl.classList.remove('is-on');
      state.captionEl.innerHTML = '';
    }
  }

  function getPref() {
    try {
      var v = global.localStorage.getItem(PREF_KEY);
      if (v === '1' || v === 'true') return true;
      if (v === '0' || v === 'false') return false;
    } catch (e) {}
    return false;
  }

  function setPref(on) {
    try { global.localStorage.setItem(PREF_KEY, on ? '1' : '0'); } catch (e) {}
  }

  function canSpeak() {
    try {
      return !!(global.speechSynthesis && global.SpeechSynthesisUtterance);
    } catch (e) {
      return false;
    }
  }

  function normalizeSpace(s) {
    return String(s || '').replace(/\s+/g, ' ').trim();
  }

  function warmVoices() {
    if (!canSpeak()) return;
    try {
      var list = global.speechSynthesis.getVoices();
      if (list && list.length) state.voicesReady = true;
      global.speechSynthesis.onvoiceschanged = function () {
        state.voicesReady = true;
      };
      // Kick load on Safari
      global.speechSynthesis.getVoices();
    } catch (e) {}
  }

  function pickVoice() {
    try {
      var voices = global.speechSynthesis.getVoices() || [];
      if (!voices.length) return null;
      var lang = (navigator.language || 'en-IN').toLowerCase();
      var base = lang.split('-')[0];
      var exact = voices.filter(function (v) { return (v.lang || '').toLowerCase() === lang; });
      if (exact.length) return exact[0];
      var partial = voices.filter(function (v) {
        return (v.lang || '').toLowerCase().indexOf(base) === 0;
      });
      if (partial.length) return partial[0];
      return voices[0];
    } catch (e) {
      return null;
    }
  }

  function clearHighlight() {
    try {
      var nodes = document.querySelectorAll('.' + HIGHLIGHT_CLASS);
      for (var i = 0; i < nodes.length; i++) nodes[i].classList.remove(HIGHLIGHT_CLASS);
    } catch (e) {}
    state.activeEl = null;
  }

  function clearKeepAlive() {
    if (state.keepAlive) {
      clearInterval(state.keepAlive);
      state.keepAlive = null;
    }
  }

  function startKeepAlive() {
    clearKeepAlive();
    // Chrome sometimes pauses speechSynthesis mid-read; nudge resume while active.
    state.keepAlive = setInterval(function () {
      if (!state.speaking || !global.speechSynthesis) {
        clearKeepAlive();
        return;
      }
      try {
        if (global.speechSynthesis.paused) global.speechSynthesis.resume();
      } catch (e) {}
    }, 4000);
  }

  function showCaption(text) {
    var el = ensureCaption();
    el.innerHTML = '<mark>' + escapeHtml(text) + '</mark>';
    el.classList.add('is-on');
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function highlightEl(el) {
    clearHighlight();
    if (!el || !el.classList) {
      return;
    }
    // Don't outline huge containers
    var tag = (el.tagName || '').toLowerCase();
    if (tag === 'body' || tag === 'html' || tag === 'main' || el.id === 'studentDashboardShell') {
      return;
    }
    el.classList.add(HIGHLIGHT_CLASS);
    state.activeEl = el;
    try {
      el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
    } catch (e) {
      try { el.scrollIntoView(true); } catch (e2) {}
    }
  }

  function pauseForKind(kind) {
    if (kind === 'heading') return 700;
    if (kind === 'list') return 420;
    if (kind === 'table') return 380;
    if (kind === 'paragraph') return 480;
    if (kind === 'sentence') return 220;
    return 320;
  }

  function splitSentences(text) {
    var t = normalizeSpace(text);
    if (!t) return [];
    var parts = t.match(/[^.!?…]+[.!?…]+|[^.!?…]+$/g);
    if (!parts) return [t];
    return parts.map(normalizeSpace).filter(Boolean);
  }

  function isVisible(el) {
    if (!el || el.nodeType !== 1) return false;
    try {
      var st = global.getComputedStyle ? getComputedStyle(el) : null;
      if (!st) return true;
      if (st.display === 'none' || st.visibility === 'hidden' || st.visibility === 'collapse') {
        return false;
      }
      if (parseFloat(st.opacity || '1') === 0) return false;
      // Off-screen / clipped helpers
      if (st.position === 'absolute' || st.position === 'fixed') {
        var r = el.getBoundingClientRect();
        if (r.width < 1 && r.height < 1) return false;
      }
    } catch (e) {}
    return true;
  }

  function isSkipped(el) {
    if (!el || el.nodeType !== 1) return true;
    try {
      if (el.closest && el.closest(SKIP_SEL)) return true;
      if (!isVisible(el)) return true;
    } catch (e) {}
    return false;
  }

  function blockKind(el) {
    var tag = (el.tagName || '').toLowerCase();
    return READ_TAGS[tag] || 'paragraph';
  }

  /**
   * Visible text only — walks text nodes, skips images/media/hidden nodes.
   * Never includes HTML tags, attributes, alt, or aria-label.
   */
  function visibleTextFrom(el) {
    if (!el) return '';
    var parts = [];
    try {
      if (global.NodeFilter && document.createTreeWalker) {
        var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, {
          acceptNode: function (node) {
            var parent = node.parentElement;
            if (!parent) return NodeFilter.FILTER_REJECT;
            var ptag = (parent.tagName || '').toLowerCase();
            if (ptag === 'script' || ptag === 'style' || ptag === 'noscript' ||
                ptag === 'svg' || ptag === 'title') {
              return NodeFilter.FILTER_REJECT;
            }
            if (parent.closest && parent.closest(
              'img,picture,svg,canvas,video,audio,button,input,select,textarea,[aria-hidden="true"]'
            )) {
              return NodeFilter.FILTER_REJECT;
            }
            if (!isVisible(parent)) return NodeFilter.FILTER_REJECT;
            if (!normalizeSpace(node.nodeValue)) return NodeFilter.FILTER_REJECT;
            return NodeFilter.FILTER_ACCEPT;
          }
        });
        var n = walker.nextNode();
        while (n) {
          parts.push(n.nodeValue);
          n = walker.nextNode();
        }
      } else {
        // Fallback: clone and strip media / controls before reading text
        var clone = el.cloneNode(true);
        var kill = clone.querySelectorAll(
          'img,picture,svg,canvas,video,audio,script,style,button,input,select,textarea'
        );
        for (var k = 0; k < kill.length; k++) {
          if (kill[k].parentNode) kill[k].parentNode.removeChild(kill[k]);
        }
        parts.push(clone.textContent || '');
      }
    } catch (e) {
      parts.push(el.textContent || '');
    }
    // Strip any leftover tag-like noise and URLs-only noise from attributes never applied
    return normalizeSpace(parts.join(' '))
      .replace(/<\/?[a-zA-Z][^>]*>/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function isReadableTag(el) {
    if (!el || el.nodeType !== 1) return false;
    var tag = (el.tagName || '').toLowerCase();
    return !!READ_TAGS[tag];
  }

  function collectFromRoot(root) {
    var out = [];
    if (!root) return out;

    function pushEl(el) {
      if (!el || isSkipped(el) || !isReadableTag(el)) return;
      // Prefer leaf list items / cells — still ok if nested spans exist
      var text = visibleTextFrom(el);
      if (!text || text.length < 2) return;
      if (text.length > 4000) text = text.slice(0, 4000);
      var kind = blockKind(el);
      var sentences = (kind === 'heading' || kind === 'table') ? [text] : splitSentences(text);
      // Table cells: keep as one chunk for clarity
      if (kind === 'table') sentences = [text];
      for (var s = 0; s < sentences.length; s++) {
        out.push({
          text: sentences[s],
          el: el,
          kind: s === sentences.length - 1 ? kind : 'sentence'
        });
      }
    }

    var selector = Object.keys(READ_TAGS).join(',');
    var nodes = root.querySelectorAll(selector);
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      if (isSkipped(el)) continue;
      // Skip empty table cells
      pushEl(el);
    }
    return out;
  }

  function getMainRoot() {
    var candidates = [
      document.querySelector('[role="main"]'),
      document.querySelector('main'),
      document.querySelector('.std-shell-main .student-dash-main-col'),
      document.querySelector('.student-dash-main-col'),
      document.querySelector('.app-right-content'),
      document.querySelector('.std-shell-main')
    ];
    for (var i = 0; i < candidates.length; i++) {
      if (candidates[i] && isVisible(candidates[i])) return candidates[i];
    }
    return document.body;
  }

  function queueFromText(text, el, baseKind) {
    var sentences = splitSentences(text);
    var out = [];
    for (var i = 0; i < sentences.length; i++) {
      out.push({
        text: sentences[i],
        el: el || null,
        kind: i === sentences.length - 1 ? (baseKind || 'paragraph') : 'sentence'
      });
    }
    return out;
  }

  function getDomSelectionText() {
    try {
      var sel = global.getSelection && global.getSelection();
      if (!sel || sel.isCollapsed) return '';
      var t = normalizeSpace(sel.toString());
      return t;
    } catch (e) {
      return '';
    }
  }

  function getInputSelection(el) {
    if (!el) return null;
    var tag = (el.tagName || '').toLowerCase();
    if (tag !== 'textarea' && !(tag === 'input' && /text|search|url|tel|email/i.test(el.type || 'text'))) {
      return null;
    }
    var start = typeof el.selectionStart === 'number' ? el.selectionStart : 0;
    var end = typeof el.selectionEnd === 'number' ? el.selectionEnd : 0;
    var value = String(el.value || '');
    if (end > start) {
      return { text: value.slice(start, end), el: el, start: start, end: end, full: false };
    }
    // No selection → from top of field
    return { text: value, el: el, start: 0, end: value.length, full: true };
  }

  function buildQueue() {
    // 1) Text field selection / note body
    var active = document.activeElement;
    var fieldSel = getInputSelection(active);
    if (!fieldSel) {
      var noteBody = document.getElementById('noteContent');
      var noteTitle = document.getElementById('noteTitle');
      if (noteBody || noteTitle) {
        // Prefer note content when on create/edit note page
        var title = noteTitle && noteTitle.value ? normalizeSpace(noteTitle.value) : '';
        var bodySel = getInputSelection(noteBody);
        var chunks = [];
        if (title) {
          chunks.push({ text: title, el: noteTitle, kind: 'heading' });
        }
        if (bodySel && bodySel.text) {
          chunks = chunks.concat(queueFromText(bodySel.text, noteBody, 'paragraph'));
        }
        if (chunks.length) return chunks;
      }
    } else if (fieldSel.text) {
      return queueFromText(fieldSel.text, fieldSel.el, 'paragraph');
    }

    // 2) Page DOM selection — plain visible text only (no tags)
    var selected = getDomSelectionText().replace(/<\/?[a-zA-Z][^>]*>/g, '').trim();
    if (selected) {
      return queueFromText(selected, null, 'paragraph');
    }

    // 3) From top of main content — headings / paragraphs / lists / tables only
    var blocks = collectFromRoot(getMainRoot());
    if (blocks.length) return blocks;

    return [{ text: 'No readable text on this page.', el: null, kind: 'paragraph' }];
  }

  function stop() {
    state.chunkToken += 1;
    if (state.timer) {
      clearTimeout(state.timer);
      state.timer = null;
    }
    clearKeepAlive();
    state.queue = [];
    state.index = 0;
    state.speaking = false;
    state.currentUtterance = null;
    try {
      if (global.speechSynthesis) {
        global.speechSynthesis.cancel();
      }
    } catch (e) {}
    clearHighlight();
    hideCaption();
    hideControls();
    emit();
  }

  function emit() {
    try {
      global.dispatchEvent(new CustomEvent('tt-voice-screen-reader', {
        detail: {
          on: !!state.enabled,
          speaking: !!state.speaking,
          index: state.index,
          total: state.queue.length,
          rate: state.rate,
          volume: state.volume
        }
      }));
    } catch (e) {}
  }

  function applyUtteranceSettings(u) {
    u.lang = navigator.language || 'en-IN';
    u.rate = clamp(state.rate, 0.5, 2);
    u.pitch = 1;
    u.volume = clamp(state.volume, 0, 1);
    var voice = pickVoice();
    if (voice) u.voice = voice;
  }

  function speakChunk(chunk, done) {
    if (!chunk || !chunk.text) {
      done();
      return;
    }
    showCaption(chunk.text);
    showControls();
    if (chunk.el) {
      var tag = (chunk.el.tagName || '').toLowerCase();
      if (tag === 'textarea' || tag === 'input') {
        try {
          var val = String(chunk.el.value || '');
          var idx = val.indexOf(chunk.text);
          if (idx >= 0 && typeof chunk.el.setSelectionRange === 'function') {
            chunk.el.focus();
            chunk.el.setSelectionRange(idx, idx + chunk.text.length);
          }
        } catch (eSel) {}
        highlightEl(chunk.el.closest('.note-field, .note-content-wrap, .tt-speech-wrap') || chunk.el);
      } else {
        highlightEl(chunk.el);
      }
    } else {
      clearHighlight();
    }
    // Keep caption visible after highlight (highlight must not clear it)
    showCaption(chunk.text);

    var token = state.chunkToken;
    var u = new SpeechSynthesisUtterance(chunk.text);
    applyUtteranceSettings(u);
    state.currentUtterance = u;

    var finished = false;
    function finish() {
      if (finished) return;
      finished = true;
      if (state.currentUtterance === u) state.currentUtterance = null;
      done();
    }
    u.onend = finish;
    u.onerror = finish;

    try {
      global.speechSynthesis.resume();
    } catch (eR) {}
    try {
      global.speechSynthesis.speak(u);
      // Chrome can leave the engine paused after cancel; nudge again.
      if (global.speechSynthesis.paused) global.speechSynthesis.resume();
    } catch (eSpeak) {
      finish();
      return;
    }

    // Safety timeout — iOS can stall without onend
    var ms = Math.min(90000, Math.max(5000, Math.round(chunk.text.length * (90 / Math.max(0.5, state.rate)))));
    setTimeout(function () {
      if (token !== state.chunkToken) return;
      if (!finished) finish();
    }, ms);
  }

  function runNext() {
    if (!state.speaking) return;
    if (state.index >= state.queue.length) {
      stop();
      return;
    }
    var chunk = state.queue[state.index];
    var token = state.chunkToken;
    speakChunk(chunk, function () {
      if (!state.speaking || token !== state.chunkToken) return;
      state.index += 1;
      emit();
      var wait = pauseForKind(chunk.kind);
      state.timer = setTimeout(function () {
        state.timer = null;
        if (!state.speaking || token !== state.chunkToken) return;
        runNext();
      }, wait);
    });
  }

  function restartCurrentChunk() {
    if (!state.speaking || !state.queue.length) return;
    if (state.timer) {
      clearTimeout(state.timer);
      state.timer = null;
    }
    state.chunkToken += 1;
    try {
      if (global.speechSynthesis) global.speechSynthesis.cancel();
    } catch (e) {}
    // Speak immediately (slider input is a user gesture on most browsers)
    runNext();
  }

  function setRate(value, reSpeak) {
    state.rate = clamp(value, 0.5, 2);
    saveRateVol();
    syncControlLabels();
    emit();
    if (reSpeak && state.speaking) restartCurrentChunk();
    return state.rate;
  }

  function setVolume(value, reSpeak) {
    state.volume = clamp(value, 0, 1);
    saveRateVol();
    syncControlLabels();
    emit();
    if (reSpeak && state.speaking) restartCurrentChunk();
    return state.volume;
  }

  function getRate() { return state.rate; }
  function getVolume() { return state.volume; }

  function start() {
    if (!canSpeak() || !state.enabled) return false;
    // Soft reset without clearing enabled flag
    state.chunkToken += 1;
    if (state.timer) {
      clearTimeout(state.timer);
      state.timer = null;
    }
    clearKeepAlive();
    try {
      // Only cancel if something is already queued — cancel()+speak() in the same tick
      // can drop audio on Chrome. Idle start must speak inside the user gesture.
      if (global.speechSynthesis && (global.speechSynthesis.speaking || global.speechSynthesis.pending)) {
        global.speechSynthesis.cancel();
      }
    } catch (e) {}
    clearHighlight();
    hideCaption();

    warmVoices();
    loadRateVol();
    var queue = buildQueue();
    if (!queue.length) {
      queue = [{ text: 'No readable content on this page.', el: null, kind: 'paragraph' }];
    }
    state.queue = queue;
    state.index = 0;
    state.speaking = true;
    showControls();
    startKeepAlive();
    emit();

    // Speak first chunk synchronously in this user gesture (required on mobile).
    // Do NOT defer behind a silent unlock utterance or setTimeout.
    try {
      global.speechSynthesis.resume();
    } catch (eR) {}
    runNext();
    return true;
  }

  function toggle() {
    if (!state.enabled) return false;
    if (state.speaking || (global.speechSynthesis && (global.speechSynthesis.speaking || global.speechSynthesis.pending))) {
      stop();
      return false;
    }
    return start();
  }

  function setEnabled(on) {
    state.enabled = !!on && canSpeak();
    setPref(state.enabled);
    if (!state.enabled) stop();
    emit();
    return state.enabled;
  }

  function isEnabled() {
    return !!state.enabled && canSpeak();
  }

  function isSpeaking() {
    return !!state.speaking;
  }

  // Boot
  warmVoices();
  loadRateVol();
  state.enabled = getPref() && canSpeak();
  injectStyles();

  global.TTScreenReader = {
    canSpeak: canSpeak,
    isEnabled: isEnabled,
    isSpeaking: isSpeaking,
    setEnabled: setEnabled,
    start: start,
    stop: stop,
    toggle: toggle,
    getPref: getPref,
    setRate: setRate,
    setVolume: setVolume,
    getRate: getRate,
    getVolume: getVolume
  };
})(typeof window !== 'undefined' ? window : this);
