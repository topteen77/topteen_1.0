/**
 * ============================================================
 *  PageChatWidget — "Chat about this page"  v1.0.0
 *  Contextual plug-and-play page chat widget.
 *  Styles are loaded from page-chat-widget.css (same directory).
 *
 *  USAGE:
 *    <script>
 *      window.PageChatConfig = {
 *        wsBase  : 'wss://yourserver.com',   // WebSocket base URL
 *        botName : 'Page Assistant',          // Display name (optional)
 *      };
 *    </script>
 *    <script src="page-chat-widget.js"></script>
 *
 *  FLOW:
 *    1. User clicks FAB → page is scraped (strips nav/header/footer, ≤15 000 chars)
 *    2. WS connects → SEND { type:"init", page_content, page_url, page_title }
 *    3. RECV { type:"init_acknowledged" } → chat UI unlocked
 *    4. SEND { type:"message", message:"..." }
 *    5. RECV { type:"ai_final_response", content, suggested_questions }
 *    6. WS closes when page unloads — nothing persisted
 *
 *  POSITIONING:
 *    FAB sits bottom-LEFT so it never overlaps the main chatbot (bottom-right).
 * ============================================================
 */
(function (global) {
  'use strict';

  /* ============================================================
   * CONFIG
   * ============================================================ */
  const CFG = Object.assign({
    wsBase      : 'wss://careerbot.canamacademy.com',
    botName     : 'Page Assistant',
    maxPageChars: 15000,
  }, global.PageChatConfig || {});

  /* ============================================================
   * CSS LOADER
   * Detects the script's own path and loads page-chat-widget.css
   * from the same directory automatically.
   * ============================================================ */
  function injectStylesheet() {
    if (document.getElementById('pc-styles-link')) return;
    let cssHref = 'page-chat-widget.css';
    const scripts = document.querySelectorAll('script[src]');
    for (const s of scripts) {
      if (s.src && s.src.includes('page-chat-widget.js')) {
        cssHref = s.src.replace('page-chat-widget.js', 'page-chat-widget.css');
        break;
      }
    }
    const link = document.createElement('link');
    link.id   = 'pc-styles-link';
    link.rel  = 'stylesheet';
    link.href = cssHref;
    document.head.appendChild(link);
  }

  function getFabIconSrc() {
    let src = '/static/images_new/general/topteen-aibot.svg';
    const scripts = document.querySelectorAll('script[src]');
    for (const s of scripts) {
      if (s.src && s.src.includes('page-chat-widget.js')) {
        src = s.src.replace(/page-chat-widget\.js(\?.*)?$/, '../images_new/general/topteen-aibot.svg');
        break;
      }
    }
    return src;
  }

  /* ============================================================
   * MARKED.JS LOADER
   * Reuses the instance already loaded by chatbot-widget.js if present.
   * ============================================================ */
  function loadMarked() {
    if (typeof window.marked !== 'undefined') return;
    // Avoid double-loading if chatbot-widget.js already requested it
    if (document.getElementById('pc-marked-script') ||
        document.getElementById('cb-marked-script')) return;
    const s = document.createElement('script');
    s.id  = 'pc-marked-script';
    s.src = 'https://cdn.jsdelivr.net/npm/marked@4.3.0/marked.min.js';
    s.onload = () => {
      if (typeof window.marked !== 'undefined') _configureMarked();
    };
    document.head.appendChild(s);
  }

  function _configureMarked() {
    if (typeof window.marked === 'undefined') return;
    const renderer = new window.marked.Renderer();

    renderer.link = (href, title, text) =>
      `<a href="${href}" target="_blank" rel="noopener noreferrer"${title ? ` title="${title}"` : ''}>${text}</a>`;

    renderer.code = (code) => {
      const esc = code
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      return `<div class="pc-code-block"><button class="pc-copy-btn" onclick="(function(b){var pre=b.nextElementSibling;navigator.clipboard.writeText(pre.textContent).then(function(){b.textContent='Copied!';setTimeout(function(){b.textContent='Copy';},2000)});})(this)">Copy</button><pre><code>${esc}</code></pre></div>`;
    };

    renderer.table = (header, body) =>
      `<div class="pc-table-wrap"><table><thead>${header}</thead><tbody>${body}</tbody></table></div>`;

    window.marked.setOptions({
      renderer,
      breaks    : true,
      gfm       : true,
      headerIds : false,
      pedantic  : false,
    });
  }

  function renderMarkdown(raw) {
    if (!raw) return '';
    if (typeof window.marked !== 'undefined') {
      try { return window.marked.parse(raw); }
      catch (e) { console.warn('[PageChatWidget] marked.parse error:', e); }
    }
    // Minimal plain-text fallback
    return raw
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\n/g, '<br>');
  }

  /* ============================================================
   * PAGE SCRAPER
   * Removes nav/header/footer/aside/scripts/styles and both widget
   * roots, collapses whitespace, caps at maxPageChars characters.
   * ============================================================ */
  function scrapePageContent() {
    const clone = document.body.cloneNode(true);

    ['script', 'style', 'noscript', 'nav', 'header', 'footer', 'aside',
     '#cb-root', '#pc-root'].forEach(sel => {
      try { clone.querySelectorAll(sel).forEach(n => n.remove()); } catch (e) { /* skip */ }
    });

    let text = (clone.innerText || clone.textContent || '')
      .replace(/\s+/g, ' ')
      .trim();

    if (text.length > CFG.maxPageChars) {
      text = text.substring(0, CFG.maxPageChars) + '…';
    }
    return text;
  }

  /* ============================================================
   * HELPERS
   * ============================================================ */
  function formatTime(date) {
    return (date || new Date()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function el(tag, attrs, ...children) {
    const e = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => {
      if      (k === 'className')   e.className = v;
      else if (k === 'innerHTML')   e.innerHTML = v;
      else if (k === 'textContent') e.textContent = v;
      else                          e.setAttribute(k, v);
    });
    children.forEach(c => c && e.appendChild(
      typeof c === 'string' ? document.createTextNode(c) : c
    ));
    return e;
  }

  /* ============================================================
   * SVG ICONS
   * ============================================================ */
  const IC = {
    page    : `<svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm-1 1.5L18.5 9H13V3.5zM6 20V4h5v7h7v9H6z"/></svg>`,
    close   : `<svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>`,
    send    : `<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>`,
    fullscr : `<svg viewBox="0 0 24 24"><path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/></svg>`,
    restore : `<svg viewBox="0 0 24 24"><path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"/></svg>`,
    error   : `<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>`,
    spinner : `<svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 0 1 10 10h-2a8 8 0 0 0-8-8V2z"/></svg>`,
  };

  /* ============================================================
   * MAIN WIDGET CLASS
   * ============================================================ */
  class PageChatWidget {
    constructor() {
      this._ws              = null;
      this._isOpen          = false;
      this._isFullscreen    = false;
      this._isInitialized   = false;
      this._isStreaming     = false;
      this._typingIndicator = null;
      this._typingInterval  = null;
      this._typingMsgIdx    = 0;
      this._unread          = 0;

      injectStylesheet();
      loadMarked();
      this._buildDOM();
      this._bindEvents();
    }

    /* ── Build DOM ─────────────────────────────────────────── */
    _buildDOM() {
      this._root = el('div', { id: 'pc-root' });
      this._backdrop = el('div', { id: 'pc-backdrop', className: 'pc-hide', 'aria-hidden': 'true' });

      /* ---- FAB (pill button, bottom-left) ---- */
      this._fab = el('button', { id: 'pc-fab', 'aria-label': 'Chat about this page' });
      this._fab.innerHTML = `<img src="${getFabIconSrc()}" alt="" width="22" height="22" decoding="async" />` +
        '<span id="pc-fab-label">Chat this page</span>';
      this._badge = el('span', { id: 'pc-badge', className: 'pc-hide' }, '0');
      this._fab.appendChild(this._badge);

      /* ---- Chat window ---- */
      this._win = el('div', { id: 'pc-win', className: 'pc-hide', 'aria-live': 'polite' });

      /* ---- Header ---- */
      const hdr       = el('div', { id: 'pc-hdr' });
      const hdrAvatar = el('div', { id: 'pc-hdr-avatar' });
      hdrAvatar.innerHTML = `<img src="${getFabIconSrc()}" alt="" width="22" height="22" decoding="async" />`;

      const hdrInfo = el('div', { id: 'pc-hdr-info' });
      const hdrName = el('div', { id: 'pc-hdr-name', textContent: CFG.botName });

      const statusRow     = el('div', { id: 'pc-hdr-status' });
      this._statusDot     = el('span', { id: 'pc-status-dot', className: 'connecting' });
      this._statusTxt     = el('span', { id: 'pc-status-txt', textContent: 'Connecting…' });
      statusRow.appendChild(this._statusDot);
      statusRow.appendChild(this._statusTxt);

      hdrInfo.appendChild(hdrName);
      hdrInfo.appendChild(statusRow);

      const hdrActions = el('div', { id: 'pc-hdr-actions' });

      this._fsBtn = el('button', { className: 'pc-hdr-btn', title: 'Expand / Fullscreen' });
      this._fsBtn.innerHTML = IC.fullscr;
      this._fsBtn.addEventListener('click', () => this._toggleFullscreen());

      const closeBtn = el('button', { className: 'pc-hdr-btn', title: 'Close' });
      closeBtn.innerHTML = IC.close;
      closeBtn.addEventListener('click', () => this._toggleWindow());

      hdrActions.appendChild(this._fsBtn);
      hdrActions.appendChild(closeBtn);
      hdr.appendChild(hdrAvatar);
      hdr.appendChild(hdrInfo);
      hdr.appendChild(hdrActions);

      /* ---- Init overlay (covers msg area while connecting) ---- */
      this._overlay = el('div', { id: 'pc-overlay' });
      this._overlay.innerHTML = `
        <div class="pc-overlay-spinner">${IC.spinner}</div>
        <div class="pc-overlay-title">Reading this page…</div>
        <div class="pc-overlay-sub">Just a moment while I scan the content</div>
      `;

      /* ---- Message area ---- */
      this._msgArea = el('div', { id: 'pc-msgs' });

      /* ---- Indicator area ---- */
      this._indArea = el('div', { id: 'pc-ind-area' });

      /* ---- Input area ---- */
      const inputArea = el('div', { id: 'pc-input-area' });
      const inputRow  = el('div', { id: 'pc-input-row' });

      this._input = el('textarea', {
        id          : 'pc-input',
        placeholder : 'Ask anything about this page…',
        rows        : '1',
      });
      this._input.disabled = true;

      this._sendBtn = el('button', { id: 'pc-send', 'aria-label': 'Send' });
      this._sendBtn.innerHTML = IC.send;
      this._sendBtn.disabled = true;

      inputRow.appendChild(this._input);
      inputRow.appendChild(this._sendBtn);

      const hint = el('div', { id: 'pc-input-hint', textContent: 'Enter to send · Shift+Enter for new line' });
      inputArea.appendChild(inputRow);
      inputArea.appendChild(hint);

      /* ---- Assemble window ---- */
      this._win.appendChild(hdr);
      this._win.appendChild(this._overlay);
      this._win.appendChild(this._msgArea);
      this._win.appendChild(this._indArea);
      this._win.appendChild(inputArea);

      /* ---- Assemble root ---- */
      this._root.appendChild(this._fab);
      this._root.appendChild(this._backdrop);
      this._root.appendChild(this._win);
      document.body.appendChild(this._root);
    }

    /* ── Bind events ───────────────────────────────────────── */
    _bindEvents() {
      this._fab.addEventListener('click', () => this._toggleWindow());
      this._sendBtn.addEventListener('click', () => this._send());
      this._input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this._send(); }
      });
      this._input.addEventListener('input', () => {
        this._input.style.height = '46px';
        this._input.style.height = Math.min(this._input.scrollHeight, 120) + 'px';
      });
    }

    /* ── Toggle window open / close ────────────────────────── */
    _toggleWindow() {
      this._isOpen = !this._isOpen;
      this._win.classList.toggle('pc-hide', !this._isOpen);
      this._syncBackdrop();

      if (this._isOpen) {
        this._clearUnread();
        // Kick off init on first open
        if (!this._isInitialized && !this._ws) this._initChat();
        setTimeout(() => { if (!this._input.disabled) this._input.focus(); }, 350);
      }
    }

    /* ── Toggle fullscreen (20 % margin) ───────────────────── */
    _toggleFullscreen() {
      this._isFullscreen = !this._isFullscreen;
      this._win.classList.toggle('pc-fullscreen', this._isFullscreen);
      this._fsBtn.innerHTML = this._isFullscreen ? IC.restore : IC.fullscr;
      this._syncBackdrop();
    }

    _syncBackdrop() {
      if (!this._backdrop) return;
      const showBackdrop = this._isOpen && this._isFullscreen;
      this._backdrop.classList.toggle('pc-hide', !showBackdrop);
    }

    /* ── Init: scrape → WS connect → send init ─────────────── */
    _initChat() {
      const pageContent = scrapePageContent();
      const pageUrl     = window.location.href;
      const pageTitle   = document.title || 'Untitled Page';

      this._setStatus('connecting', 'Connecting…');

      const wsUrl = CFG.wsBase.replace(/\/$/, '') + '/ws/page-chat/';

      try {
        this._ws = new WebSocket(wsUrl);
      } catch (e) {
        this._setStatus('offline', 'Offline');
        this._overlayError('Failed to connect to server.');
        return;
      }

      this._ws.onopen = () => {
        this._setStatus('connecting', 'Analyzing page…');
        this._ws.send(JSON.stringify({
          type        : 'init',
          page_content: pageContent,
          page_url    : pageUrl,
          page_title  : pageTitle,
        }));
      };

      this._ws.onmessage = (e) => {
        try {
          this._handleMessage(JSON.parse(e.data));
        } catch (err) {
          console.warn('[PageChatWidget] Invalid JSON:', e.data);
        }
      };

      this._ws.onerror = () => {
        this._setStatus('offline', 'Offline');
        this._overlayError('Connection failed. Please refresh and try again.');
      };

      this._ws.onclose = () => {
        if (this._isInitialized) this._setStatus('offline', 'Offline');
      };
    }

    /* ── Handle server messages ─────────────────────────────── */
    _handleMessage(data) {
      switch (data.type) {

        case 'init_acknowledged':
          this._isInitialized       = true;
          this._overlay.style.display = 'none';
          this._input.disabled      = false;
          this._sendBtn.disabled    = false;
          this._setStatus('online', 'Online');
          this._appendBotMsg("I've read this page. What would you like to know about it?");
          setTimeout(() => this._input.focus(), 100);
          break;

        case 'assistant_typing':
          if (data.status === 'started') this._showTyping();
          else this._hideTyping();
          break;

        case 'ai_final_response':
          this._hideTyping();
          this._isStreaming = false;
          this._enableInput();
          if (data.content) this._appendBotMsg(data.content, true);
          if (data.suggested_questions && data.suggested_questions.length)
            this._renderSuggestions(data.suggested_questions);
          this._scrollToBottom();
          if (!this._isOpen) this._addUnread();
          break;

        case 'end_of_response':
          this._hideTyping();
          this._isStreaming = false;
          this._enableInput();
          break;

        case 'error':
          this._hideTyping();
          this._isStreaming = false;
          this._enableInput();
          if (data.detail) console.warn('[PageChatWidget] Error detail:', data.detail);
          this._showError(data.error || 'Something went wrong. Please try again.');
          break;

        default:
          // Unknown message type — ignore silently
          break;
      }
    }

    /* ── Send user message ──────────────────────────────────── */
    _send() {
      const text = this._input.value.trim();
      if (!text || !this._ws || this._ws.readyState !== WebSocket.OPEN || this._isStreaming) return;

      // Remove suggestion chips before sending
      this._msgArea.querySelectorAll('.pc-suggestions').forEach(s => s.remove());

      this._appendUserMsg(text);
      this._input.value      = '';
      this._input.style.height = '46px';
      this._isStreaming      = true;
      this._input.disabled   = true;
      this._sendBtn.disabled = true;
      this._scrollToBottom();

      this._ws.send(JSON.stringify({ type: 'message', message: text }));
    }

    /* ── DOM: user message ──────────────────────────────────── */
    _appendUserMsg(text) {
      const row    = el('div', { className: 'pc-msg pc-user' });
      const bubble = el('div', { className: 'pc-bubble', textContent: text });
      const ts     = el('div', { className: 'pc-ts', textContent: formatTime() });
      row.appendChild(bubble);
      row.appendChild(ts);
      this._msgArea.appendChild(row);
    }

    /* ── DOM: bot message ───────────────────────────────────── */
    _appendBotMsg(content, isMarkdown = false) {
      const row    = el('div', { className: 'pc-msg pc-bot' });
      const bubble = el('div', { className: isMarkdown ? 'pc-bubble pc-md' : 'pc-bubble' });
      if (isMarkdown) bubble.innerHTML = renderMarkdown(content);
      else bubble.textContent = content;
      const ts = el('div', { className: 'pc-ts', textContent: formatTime() });
      row.appendChild(bubble);
      row.appendChild(ts);
      this._msgArea.appendChild(row);
    }

    /* ── DOM: suggested questions ───────────────────────────── */
    _renderSuggestions(questions) {
      if (!questions || !questions.length) return;
      const wrap = el('div', { className: 'pc-suggestions' });
      questions.forEach(q => {
        const btn = el('button', { className: 'pc-suggestion-btn', textContent: q });
        btn.addEventListener('click', () => {
          this._msgArea.querySelectorAll('.pc-suggestions').forEach(s => s.remove());
          this._input.value = q;
          this._send();
        });
        wrap.appendChild(btn);
      });
      this._msgArea.appendChild(wrap);
    }

    /* ── DOM: error strip ───────────────────────────────────── */
    _showError(msg) {
      const row = el('div', { className: 'pc-err-msg' });
      row.innerHTML = IC.error + `<span>${msg}</span>`;
      this._msgArea.appendChild(row);
      this._scrollToBottom();
    }

    /* ── DOM: overlay error state ───────────────────────────── */
    _overlayError(msg) {
      this._overlay.innerHTML = `
        <div class="pc-overlay-icon-err">${IC.error}</div>
        <div class="pc-overlay-title" style="color:#B91C1C">${msg}</div>
        <div class="pc-overlay-sub">Please refresh the page and try again.</div>
      `;
    }

    /* ── Typing indicator with rotating messages ─────────────── */
    _showTyping() {
      if (this._typingIndicator) return;
      const msgs = [
        'Reading the content…',
        'Thinking about your question…',
        'Preparing the answer…',
        'Cross-checking the page…',
        'Almost done…',
      ];
      this._typingMsgIdx    = 0;
      this._typingIndicator = el('div', { className: 'pc-indicator' });
      this._typingIndicator.innerHTML = `
        <div class="pc-dot-row"><span></span><span></span><span></span></div>
        <span class="pc-typing-text">${msgs[0]}</span>
      `;
      this._indArea.appendChild(this._typingIndicator);
      this._scrollToBottom();

      this._typingInterval = setInterval(() => {
        this._typingMsgIdx = (this._typingMsgIdx + 1) % msgs.length;
        const t = this._typingIndicator
          ? this._typingIndicator.querySelector('.pc-typing-text')
          : null;
        if (t) t.textContent = msgs[this._typingMsgIdx];
      }, 4000);
    }

    _hideTyping() {
      if (this._typingInterval) { clearInterval(this._typingInterval); this._typingInterval = null; }
      if (this._typingIndicator) { this._typingIndicator.remove(); this._typingIndicator = null; }
    }

    /* ── Status helpers ─────────────────────────────────────── */
    _setStatus(state, label) {
      if (this._statusDot) this._statusDot.className = state;
      if (this._statusTxt) this._statusTxt.textContent = label;
    }

    _enableInput() {
      this._input.disabled   = false;
      this._sendBtn.disabled = false;
    }

    /* ── Unread badge ───────────────────────────────────────── */
    _addUnread() {
      this._unread++;
      this._badge.textContent = this._unread > 9 ? '9+' : this._unread;
      this._badge.classList.remove('pc-hide');
    }

    _clearUnread() {
      this._unread = 0;
      this._badge.classList.add('pc-hide');
    }

    /* ── Scroll ─────────────────────────────────────────────── */
    _scrollToBottom() {
      requestAnimationFrame(() => {
        this._msgArea.scrollTop = this._msgArea.scrollHeight;
      });
    }
  }

  /* ============================================================
   * BOOT
   * ============================================================ */
  function boot() {
    if (document.getElementById('pc-root')) return;
    new PageChatWidget();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

})(window);
