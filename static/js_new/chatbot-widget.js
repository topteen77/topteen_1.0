/**
 * ============================================================
 *  TopTeenBot — Chatbot Widget  v1.0.0
 *  Plug-and-place chatbot widget.
 *  Styles are loaded from chatbot-widget.css (same directory).
 *
 *  USAGE:
 *    <script>
 *      window.ChatbotConfig = {
 *        baseUrl : 'http://localhost:8000',   // REST base URL
 *        wsBase  : 'ws://localhost:8000',     // WebSocket base URL
 *        botName : 'TopTeenBot',              // Display name
 *        devMode : true,                      // Show session-ID panel
 *      };
 *    </script>
 *    <script src="chatbot-widget.js"></script>
 * ============================================================
 */
(function (global) {
  'use strict';

  /* ============================================================
   * CONFIG — merge defaults with window.ChatbotConfig
   * ============================================================ */
  const CFG = Object.assign({
    // baseUrl : 'https://careerbot.canamacademy.com',
    baseUrl : 'http://127.0.0.1:8000',
    wsBase  : 'ws://127.0.0.1:8000',
    // wsBase  : 'wss://careerbot.canamacademy.com',
    botName : 'Career Counsellor',
    devMode : false,  // Production mode - auto-creates sessions
  }, global.ChatbotConfig || {});

  /* ============================================================
   * CSS LOADER
   * Detects the script's own path and loads chatbot-widget.css
   * from the same directory automatically.
   * ============================================================ */
  function injectStylesheet() {
    if (document.getElementById('cb-styles-link')) return;

    // Resolve CSS path relative to this script's location
    let cssHref = 'chatbot-widget.css'; // fallback
    const scripts = document.querySelectorAll('script[src]');
    for (const s of scripts) {
      if (s.src && s.src.includes('chatbot-widget.js')) {
        cssHref = s.src.replace('chatbot-widget.js', 'chatbot-widget.css');
        break;
      }
    }

    const link   = document.createElement('link');
    link.id      = 'cb-styles-link';
    link.rel     = 'stylesheet';
    link.href    = cssHref;
    document.head.appendChild(link);
  }

  /* ============================================================
   * SVG ICONS  (inline — zero external dependency)
   * ============================================================ */
  const IC = {
    chat    : `<svg viewBox="0 0 24 24"><path d="M20 2H4a2 2 0 00-2 2v18l4-4h14a2 2 0 002-2V4a2 2 0 00-2-2z"/></svg>`,
    close   : `<svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>`,
    newchat : `<svg viewBox="0 0 24 24"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 000-1.41l-2.34-2.34a1 1 0 00-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>`,
    bot     : `<svg viewBox="0 0 24 24"><path d="M12 2a2 2 0 012 2c0 .74-.4 1.38-1 1.72V7h1a7 7 0 017 7H3a7 7 0 017-7h1V5.72A2 2 0 0110 4a2 2 0 012-2zM7.5 13a1.5 1.5 0 100 3 1.5 1.5 0 000-3zm9 0a1.5 1.5 0 100 3 1.5 1.5 0 000-3zM3 21v-1a3 3 0 013-3h12a3 3 0 013 3v1H3z"/></svg>`,
    send    : `<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>`,
    fullscr : `<svg viewBox="0 0 24 24"><path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/></svg>`,
    restore : `<svg viewBox="0 0 24 24"><path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"/></svg>`,
    error   : `<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>`,
    search  : `<svg viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>`,
    chevron : `<svg viewBox="0 0 24 24"><path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"/></svg>`,
    toolSql : `<svg viewBox="0 0 24 24"><path d="M12 3C7.58 3 4 4.79 4 7v10c0 2.21 3.58 4 8 4s8-1.79 8-4V7c0-2.21-3.58-4-8-4zm6 14c0 .5-2.13 2-6 2s-6-1.5-6-2v-2.23c1.61.78 3.72 1.23 6 1.23s4.39-.45 6-1.23V17zm0-4.55c-1.3.83-3.42 1.55-6 1.55s-4.7-.72-6-1.55V9.55C7.3 10.38 9.42 11 12 11s4.7-.62 6-1.45v2.9zM12 9C8.13 9 6 7.5 6 7s2.13-2 6-2 6 1.5 6 2-2.13 2-6 2z"/></svg>`,
    retry   : `<svg viewBox="0 0 24 24"><path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/></svg>`,
  };

  /* ============================================================
   * MARKDOWN → HTML RENDERER
   * Supports: headings, bold, italic, del, inline code, fenced
   * code blocks (+ copy button), tables, blockquotes, ul/ol,
   * checkboxes, links (bare URLs auto-linked), images, hr.
   * ============================================================ */
  function renderMarkdown(raw) {
    if (!raw) return '';

    /* ── Primary: marked.js (loaded from CDN) ── */
    if (typeof window.marked !== 'undefined') {
      try { return window.marked.parse(raw); }
      catch (e) { console.warn('[ChatbotWidget] marked.parse error, using built-in fallback:', e); }
    }

    /* ── Fallback: built-in custom parser ── */
    let s = raw;

    function esc(t) {
      return t
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
    }

    // Stash fenced code blocks
    const codeBlocks = [];
    s = s.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
      const idx         = codeBlocks.length;
      const escapedCode = esc(code.trimEnd());
      const langLabel   = lang
        ? `<span style="font-size:10px;color:#89B4FA;position:absolute;top:8px;left:14px;">${esc(lang)}</span>`
        : '';
      const copyBtn = `<button class="cb-copy-code" onclick="cbCopyCode(this)">Copy</button>`;
      codeBlocks.push(
        `<div style="position:relative;">${copyBtn}${langLabel}` +
        `<pre style="${lang ? 'padding-top:26px;' : ''}"><code>${escapedCode}</code></pre></div>`
      );
      return `\x00CODE${idx}\x00`;
    });

    // Stash inline code
    const inlineCodes = [];
    s = s.replace(/`([^`]+)`/g, (_, code) => {
      const idx = inlineCodes.length;
      inlineCodes.push(`<code>${esc(code)}</code>`);
      return `\x00ICODE${idx}\x00`;
    });

    // GFM tables
    s = s.replace(/\|.+\|[\s\S]*?\n(?=\n|$)/g, (table) => {
      const rows = table.trim().split('\n');
      if (rows.length < 2) return table;
      if (!/^[\s|:-]+$/.test(rows[1])) return table;
      const headers = rows[0].split('|').map(c => c.trim()).filter(Boolean);
      const aligns  = rows[1].split('|').map(c => c.trim()).filter(Boolean).map(c => {
        if (c.startsWith(':') && c.endsWith(':')) return 'center';
        if (c.endsWith(':'))                       return 'right';
        return 'left';
      });
      let html = '<div class="cb-table-wrap"><table><thead><tr>';
      headers.forEach((h, i) =>
        html += `<th style="text-align:${aligns[i] || 'left'}">${inlineMarkdown(h)}</th>`
      );
      html += '</tr></thead><tbody>';
      rows.slice(2).forEach(row => {
        const cells = row.split('|').map(c => c.trim()).filter(Boolean);
        if (!cells.length) return;
        html += '<tr>';
        cells.forEach((c, i) =>
          html += `<td style="text-align:${aligns[i] || 'left'}">${inlineMarkdown(c)}</td>`
        );
        html += '</tr>';
      });
      html += '</tbody></table></div>';
      return html;
    });

    // Blockquotes
    s = s.replace(/^(>[ \t]?.+(\n>[ \t]?.+)*)/gm, (match) => {
      const inner = match.replace(/^>[ \t]?/gm, '');
      return `<blockquote>${inlineMarkdown(inner)}</blockquote>`;
    });

    // Headings
    s = s.replace(/^(#{1,6}) (.+)$/gm, (_, hashes, text) => {
      const level = hashes.length;
      return `<h${level}>${inlineMarkdown(text)}</h${level}>`;
    });

    // Horizontal rules
    s = s.replace(/^[-*_]{3,}\s*$/gm, '<hr>');

    // Lists
    s = parseListBlock(s);

    // Paragraphs
    const blocks = s.split(/\n{2,}/);
    s = blocks.map(block => {
      block = block.trim();
      if (!block) return '';
      if (/^<(h[1-6]|ul|ol|li|blockquote|pre|table|div|hr|tr|td|th)[\s>]/.test(block)) return block;
      if (/\x00CODE\d+\x00/.test(block)) return block;
      return `<p>${inlineMarkdown(block.replace(/\n/g, '<br>'))}</p>`;
    }).join('\n');

    // Restore stashed blocks
    codeBlocks.forEach((cb, i)  => { s = s.replace(`\x00CODE${i}\x00`,  cb); });
    inlineCodes.forEach((ic, i) => { s = s.replace(`\x00ICODE${i}\x00`, ic); });

    return s;
  }

  function inlineMarkdown(text) {
    return text
      .replace(/!\[([^\]]*)\]\(([^)]+)\)/g,
        (_, alt, src) => `<img src="${src}" alt="${alt}" style="max-width:100%;border-radius:6px;" loading="lazy">`)
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g,
        (_, label, href) => `<a href="${href}" target="_blank" rel="noopener noreferrer">${label}</a>`)
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/__(.+?)__/g,     '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g,     '<em>$1</em>')
      .replace(/_(.+?)_/g,       '<em>$1</em>')
      .replace(/~~(.+?)~~/g,     '<del>$1</del>')
      .replace(/(?<![="'`])(https?:\/\/[^\s<>"']+)/g,
        url => `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`);
  }

  function parseListBlock(text) {
    // Unordered
    text = text.replace(/((?:^[ \t]*[-*+] .+\n?)+)/gm, (block) => {
      const items = block.trim().split('\n').map(line => {
        const m = line.match(/^[ \t]*[-*+] \[( |x)\] (.+)$/);
        if (m) {
          return `<li><input type="checkbox" disabled ${m[1] === 'x' ? 'checked' : ''}> ${inlineMarkdown(m[2])}</li>`;
        }
        return `<li>${inlineMarkdown(line.replace(/^[ \t]*[-*+] /, ''))}</li>`;
      });
      return `<ul>${items.join('')}</ul>`;
    });
    // Ordered
    text = text.replace(/((?:^[ \t]*\d+\. .+\n?)+)/gm, (block) => {
      const items = block.trim().split('\n').map(line =>
        `<li>${inlineMarkdown(line.replace(/^[ \t]*\d+\. /, ''))}</li>`
      );
      return `<ol>${items.join('')}</ol>`;
    });
    return text;
  }

  /* Global copy-code handler (needed for inline onclick) */
  global.cbCopyCode = function (btn) {
    const code = btn.closest('div').querySelector('code').innerText;
    navigator.clipboard.writeText(code).then(() => {
      btn.textContent = 'Copied!';
      btn.classList.add('copied');
      setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
    });
  };

  /* ============================================================
   * MARKED.JS — production-grade markdown parser
   * Loaded dynamically from CDN so the widget stays self-contained.
   * Configured with custom renderers to keep our copy-button code
   * blocks and target="_blank" links. Falls back silently to the
   * built-in parser if the CDN is unreachable.
   * ============================================================ */
  function loadMarked() {
    // Already on the page (e.g. host app loaded it)
    if (typeof window.marked !== 'undefined') { _configureMarked(); return; }
    const s   = document.createElement('script');
    s.src     = 'https://cdn.jsdelivr.net/npm/marked@4.3.0/marked.min.js';
    s.onload  = () => _configureMarked();
    s.onerror = () => console.warn('[ChatbotWidget] marked.js CDN unavailable — using built-in parser.');
    document.head.appendChild(s);
  }

  function _configureMarked() {
    if (!window.marked) return;

    const R = new marked.Renderer();

    /* Links — always open in a new tab */
    R.link = function (href, title, text) {
      const safe = (href || '#').replace(/"/g, '&quot;');
      const tip  = title ? ` title="${title.replace(/"/g, '&quot;')}"` : '';
      return `<a href="${safe}"${tip} target="_blank" rel="noopener noreferrer">${text}</a>`;
    };

    /* Fenced code blocks — keep our copy-button UI */
    R.code = function (code, lang) {
      const escaped = code
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      const langStr   = (lang || '').split(/\s/)[0].trim();
      const langLabel = langStr
        ? `<span style="font-size:10px;color:#89B4FA;position:absolute;top:8px;left:14px;">${langStr}</span>`
        : '';
      const copyBtn = `<button class="cb-copy-code" onclick="cbCopyCode(this)">Copy</button>`;
      return (
        `<div style="position:relative;">${copyBtn}${langLabel}` +
        `<pre style="${langStr ? 'padding-top:26px;' : ''}"><code>${escaped}</code></pre></div>`
      );
    };

    marked.setOptions({
      renderer  : R,
      gfm       : true,    // GitHub Flavoured Markdown (tables, strikethrough, autolinks)
      breaks    : true,    // single \n → <br>
      mangle    : false,   // don't obfuscate emails
      headerIds : false,   // cleaner HTML — no id="" on headings
      pedantic  : false,
    });
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
   * MAIN WIDGET CLASS
   * ============================================================ */
  class ChatbotWidget {
    constructor() {
      this._sessionId       = null;
      this._sessionTitle    = 'New Chat';
      this._ws              = null;
      this._isOpen          = false;
      this._isFullscreen    = false;
      this._aiBuffer        = '';
      this._streamingBubble = null;
      this._unread          = 0;
      this._isStreaming     = false;
      this._searchIndicator = null;
      this._typingIndicator = null;
      this._typingMessageIndex = 0;
      this._typingInterval  = null;
      this._firstMessageSent = false;  // Track if first message has been sent

      injectStylesheet();
      loadMarked();         // async — loaded before first message in normal use
      this._buildDOM();
      this._bindEvents();

      if (!CFG.devMode) this._createSession();
    }

    /* ── build DOM ──────────────────────────────────────────── */
    _buildDOM() {
      this._root = el('div', { id: 'cb-root' });

      /* ---- FAB ---- */
      const fabWrap    = el('div', { id: 'cb-fab-wrap' });
      this._fab        = el('button', { id: 'cb-fab', 'aria-label': 'Open chat' });
      this._fab.innerHTML = IC.chat;
      this._badge      = el('div', { id: 'cb-badge' }, '0');
      fabWrap.appendChild(this._fab);
      fabWrap.appendChild(this._badge);

      /* ---- Chat window ---- */
      this._win = el('div', { id: 'cb-window', 'aria-live': 'polite' });
      this._win.classList.add('cb-hide');

      /* ---- Header ---- */
      const hdr     = el('div', { id: 'cb-header' });

      // Avatar
      const av  = el('div', { id: 'cb-hdr-avatar' });
      av.innerHTML = IC.bot;

      // Info block
      const info       = el('div', { id: 'cb-hdr-info' });
      this._hdrName    = el('div', { id: 'cb-hdr-name',  textContent: CFG.botName });

      // Status row
      const statusRow    = el('div', { id: 'cb-hdr-status' });
      this._statusDot    = el('span', { id: 'cb-status-dot', className: 'offline' });
      this._statusTxt    = el('span', { id: 'cb-status-txt', textContent: 'Offline' });
      statusRow.appendChild(this._statusDot);
      statusRow.appendChild(this._statusTxt);

      info.appendChild(this._hdrName);
      info.appendChild(statusRow);

      // Action buttons
      const actions = el('div', { id: 'cb-hdr-actions' });

      // Fullscreen button
      this._fsBtn = el('button', { className: 'cb-hdr-btn', title: 'Expand / Fullscreen', id: 'cb-fs-btn' });
      this._fsBtn.innerHTML = IC.fullscr;
      this._fsBtn.addEventListener('click', () => this._toggleFullscreen());

      // New Session button
      const newBtn = el('button', { className: 'cb-hdr-btn', title: 'New Session' });
      newBtn.innerHTML = IC.newchat;
      newBtn.addEventListener('click', () => this._startNewSession());

      // Close button
      const closeBtn = el('button', { className: 'cb-hdr-btn', title: 'Close chat' });
      closeBtn.innerHTML = IC.close;
      closeBtn.addEventListener('click', () => this._toggleWindow());

      actions.appendChild(this._fsBtn);
      actions.appendChild(newBtn);
      actions.appendChild(closeBtn);

      hdr.appendChild(av);
      hdr.appendChild(info);
      hdr.appendChild(actions);

      /* ---- Dev panel (collapsible) ---- */
      this._devPanel    = null;
      this._devCollapsed = true;  // start collapsed to save space
      if (CFG.devMode) {
        this._devPanel = el('div', { id: 'cb-dev-panel', className: 'cb-dev-collapsed' });

        // Clickable label row with chevron
        const lbl     = el('div', { id: 'cb-dev-label' });
        const lblText = el('span', { textContent: '⚙  Dev Mode — Session ID' });
        const chevron = el('span', { id: 'cb-dev-chevron', innerHTML: IC.chevron });
        lbl.appendChild(lblText);
        lbl.appendChild(chevron);
        lbl.addEventListener('click', () => this._toggleDevPanel());

        // Collapsible body
        const devBody = el('div', { id: 'cb-dev-body' });
        const row     = el('div', { id: 'cb-dev-row' });
        this._sidInput = el('input', {
          type: 'text', id: 'cb-sid-input',
          placeholder: 'Paste session UUID here…',
        });
        const btnConnect = el('button', { id: 'cb-btn-connect', className: 'cb-dev-btn', textContent: 'Connect' });
        btnConnect.addEventListener('click', () => this._connectWithId(this._sidInput.value.trim()));
        row.appendChild(this._sidInput);
        row.appendChild(btnConnect);
        this._sidDisplay = el('div', { id: 'cb-sid-display', textContent: 'No session connected.' });
        devBody.appendChild(row);
        devBody.appendChild(this._sidDisplay);

        this._devPanel.appendChild(lbl);
        this._devPanel.appendChild(devBody);
      }

      /* ---- Messages area ---- */
      this._msgArea = el('div', {
        id: 'cb-messages', role: 'log', 'aria-label': 'Chat messages',
      });
      this._showWelcome();

      /* ---- Indicators ---- */
      this._indicatorArea = el('div', { id: 'cb-indicators' });

      /* ---- Input area ---- */
      const inputArea = el('div', { id: 'cb-input-area' });
      const inputRow  = el('div', { id: 'cb-input-row' });

      this._input = el('textarea', {
        id: 'cb-input',
        placeholder: 'Ask me anything…',
        rows: '1',
        'aria-label': 'Message input',
      });

      this._sendBtn = el('button', { id: 'cb-send', title: 'Send message', disabled: '' });
      this._sendBtn.innerHTML = IC.send;

      const hint = el('div', { id: 'cb-input-hint', textContent: 'Enter ↵ to send · Shift+Enter for new line' });
      inputRow.appendChild(this._input);
      inputRow.appendChild(this._sendBtn);
      inputArea.appendChild(inputRow);
      inputArea.appendChild(hint);

      /* ---- Assemble ---- */
      this._win.appendChild(hdr);
      if (this._devPanel) this._win.appendChild(this._devPanel);
      this._win.appendChild(this._msgArea);
      this._win.appendChild(this._indicatorArea);
      this._win.appendChild(inputArea);

      this._root.appendChild(fabWrap);
      this._root.appendChild(this._win);
      document.body.appendChild(this._root);
    }

    /* ── bind events ────────────────────────────────────────── */
    _bindEvents() {
      this._fab.addEventListener('click', () => this._toggleWindow());

      this._input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this._send();
        }
      });

      this._sendBtn.addEventListener('click', () => this._send());

      this._input.addEventListener('input', () => {
        this._input.style.height = '46px';
        this._input.style.height = Math.min(this._input.scrollHeight, 120) + 'px';
      });
    }

    /* ── open / close window ────────────────────────────────── */
    _toggleWindow() {
      this._isOpen = !this._isOpen;
      this._win.classList.toggle('cb-hide', !this._isOpen);
      this._fab.innerHTML = this._isOpen ? IC.close : IC.chat;
      if (this._isOpen) {
        this._clearUnread();
        setTimeout(() => this._input.focus(), 350);
      }
    }

    /* ── fullscreen toggle ──────────────────────────────────── */
    _toggleFullscreen() {
      this._isFullscreen = !this._isFullscreen;
      this._win.classList.toggle('cb-fullscreen', this._isFullscreen);
      this._fsBtn.innerHTML = this._isFullscreen ? IC.restore : IC.fullscr;
      this._fsBtn.classList.toggle('cb-fs-active', this._isFullscreen);
      this._fsBtn.title = this._isFullscreen ? 'Restore window' : 'Expand / Fullscreen';
    }

    /* ── dev panel collapse / expand ────────────────────────── */
    _toggleDevPanel() {
      if (!this._devPanel) return;
      this._devCollapsed = !this._devCollapsed;
      this._devPanel.classList.toggle('cb-dev-collapsed', this._devCollapsed);
    }

    /* ── new session (header button) ────────────────────────── */
    // Clears the UI and immediately creates a brand-new session.
    // Works in both devMode and production.
    _startNewSession() {
      this._hideAllIndicators();
      this._streamingBubble = null;
      this._aiBuffer        = '';
      this._isStreaming     = false;
      this._showWelcome();
      // Disconnect any existing WebSocket cleanly
      if (this._ws) { this._ws.onclose = null; this._ws.close(); this._ws = null; }
      // Clear dev-panel input if present
      if (this._sidInput)   this._sidInput.value = '';
      this._updateDevDisplay('Creating session…');
      this._createSession();
    }

    /* ── welcome screen ─────────────────────────────────────── */
    _showWelcome() {
      this._msgArea.innerHTML = '';
      const w = el('div', { className: 'cb-welcome' });
      w.innerHTML = `
        <div class="cb-welcome-icon">🤖</div>
        <h3>Hello! I'm ${CFG.botName}</h3>
        <p>Ask me anything — I'll help with accurate, up‑to‑date answers.</p>
        ${CFG.devMode
          ? '<span class="cb-welcome-dev-note">⚙ Dev Mode — create or connect a session above</span>'
          : ''}
      `;
      this._msgArea.appendChild(w);
    }

    /* ── status helpers ─────────────────────────────────────── */
    _setStatus(state) {
      const labels = {
        connected   : 'Online',
        connecting  : 'Connecting…',
        disconnected: 'Offline',
      };
      this._statusDot.className   = state === 'connected' ? '' : state === 'connecting' ? 'connecting' : 'offline';
      this._statusTxt.textContent = labels[state] || state;
      this._sendBtn.disabled      = state !== 'connected';
      this._input.disabled        = state !== 'connected';
    }

    _setSessionTitle(title) {
      this._sessionTitle = title || 'Chat';
      // No longer updating header title - removed
    }

    /* ── unread badge ───────────────────────────────────────── */
    _addUnread() {
      if (this._isOpen) return;
      this._unread++;
      this._badge.textContent = this._unread > 9 ? '9+' : String(this._unread);
      this._badge.classList.add('visible');
    }
    _clearUnread() {
      this._unread = 0;
      this._badge.classList.remove('visible');
    }

    /* ── REST: create session ───────────────────────────────── */
    async _createSession(title = 'New Chat') {
      this._setStatus('connecting');
      this._updateDevDisplay('Creating session…');
      try {
        const res = await fetch(`${CFG.baseUrl}/chat-api/sessions/`, {
          method : 'POST',
          headers: { 'Content-Type': 'application/json' },
          body   : JSON.stringify({ title }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const session = await res.json();
        this._connectWebSocket(session.id, session.title);
      } catch (err) {
        this._setStatus('disconnected');
        this._updateDevDisplay(`Error: ${err.message}`);
        this._showErrorMessage(`Failed to create session: ${err.message}`);
      }
    }

    /* ── Dev mode: connect by pasted UUID ───────────────────── */
    async _connectWithId(id) {
      if (!id) { alert('Please paste a valid session UUID.'); return; }
      if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) {
        alert('Invalid UUID format. Please paste a proper session UUID.'); return;
      }
      this._setStatus('connecting');
      try {
        const res = await fetch(`${CFG.baseUrl}/chat-api/sessions/${id}/`);
        if (!res.ok) throw new Error(`Session not found (HTTP ${res.status})`);
        const session = await res.json();
        await this._loadHistory(id);
        this._connectWebSocket(id, session.title);
      } catch (err) {
        this._setStatus('disconnected');
        this._updateDevDisplay(`Error: ${err.message}`);
        this._showErrorMessage(`Could not connect: ${err.message}`);
      }
    }

    /* ── REST: load chat history ────────────────────────────── */
    async _loadHistory(sessionId) {
      try {
        const res = await fetch(`${CFG.baseUrl}/chat-api/chat-history/${sessionId}/`);
        if (!res.ok) return;
        const messages = await res.json();

        // Include human, ai, and tool messages
        const relevant = messages.filter(m => m.role === 'human' || m.role === 'ai' || m.role === 'tool');
        if (!relevant.length) return;

        this._msgArea.innerHTML = '';

        // Process messages: merge consecutive AI chunks, render tools as cards
        const merged = [];
        let lastAi   = null;
        relevant.forEach(m => {
          if (m.role === 'ai') {
            if (lastAi) { lastAi.content += m.content; return; }
            lastAi = { ...m };
            merged.push(lastAi);
          } else if (m.role === 'tool') {
            lastAi = null;
            // Tool messages rendered as collapsed cards
            merged.push({ ...m, isTool: true });
          } else {
            lastAi = null;
            merged.push(m);
          }
        });

        merged.forEach(m => {
          if (m.isTool) {
            // Render tool message as a collapsed tool card
            const toolName = m.metadata?.tool_name || 'unknown';
            const isDebug = toolName.startsWith('sql_db_');
            this._appendToolCard({
              tool_name: toolName,
              message: m.content,
              is_debug: isDebug
            });
          } else {
            this._appendMessage(m.role === 'human' ? 'user' : 'bot', m.content, new Date(m.created_at));
          }
        });
        this._scrollToBottom();
      } catch (e) {
        console.warn('[ChatbotWidget] History load failed:', e);
      }
    }

    /* ── WebSocket: connect ─────────────────────────────────── */
    _connectWebSocket(sessionId, title) {
      if (this._ws) {
        this._ws.onclose = null;
        this._ws.close();
        this._ws = null;
      }

      this._sessionId = sessionId;
      this._setSessionTitle(title);
      this._setStatus('connecting');
      this._updateDevDisplay(`Connecting… ID: ${sessionId}`);

      this._ws = new WebSocket(`${CFG.wsBase}/ws/chat/${sessionId}/`);

      this._ws.onmessage = (evt) => {
        try { this._handleServerMessage(JSON.parse(evt.data)); }
        catch (e) { console.error('[ChatbotWidget] Parse error:', e); }
      };

      this._ws.onclose = (evt) => {
        this._setStatus('disconnected');
        this._hideAllIndicators();
        if (evt.code === 4004) {
          this._showErrorMessage('Invalid session ID. The session does not exist.');
          this._updateDevDisplay('Error: Invalid session (4004)');
        } else if (evt.code !== 1000) {
          this._updateDevDisplay(`Disconnected (code ${evt.code})`);
        }
      };

      this._ws.onerror = () => {
        this._setStatus('disconnected');
        this._showErrorMessage('WebSocket connection failed. Check that the server is running.');
      };
    }

    /* ── WebSocket: handle all server events ────────────────── */
    _handleServerMessage(data) {
      switch (data.type) {

        case 'connection_success':
          this._setStatus('connected');
          this._setSessionTitle(data.session_title);
          this._updateDevDisplay(`Connected ✓  ID: ${this._sessionId}`);
          break;

        case 'user_message_saved':
          // Already shown optimistically — nothing to do
          break;

        case 'assistant_typing':
          this._collapseAllToolCards();   // fold previous exchange's tool cards
          this._aiBuffer        = '';
          this._streamingBubble = null;
          this._isStreaming     = true;
          this._showTypingIndicator();
          break;

        case 'tool':
          this._showSearchIndicator();
          break;

        case 'retrying':
          // Show subtle retry status - request is still in progress
          this._showRetryIndicator(data.attempt, data.max_attempts, data.message);
          break;

        case 'tool_output':
          this._hideRetryIndicator(); // Hide retry indicator on successful tool response
          this._appendToolCard(data);
          break;

        case 'ai_final_response': {
          // Complete response arrives at once (no streaming chunks)
          this._hideTypingIndicator();
          this._hideRetryIndicator();
          const content = data.content || '';
          this._appendMessage('bot', content);
          // Render suggested follow-up questions if provided
          const questions = Array.isArray(data.suggested_questions)
            ? data.suggested_questions.filter(q => typeof q === 'string' && q.trim())
            : [];
          if (questions.length > 0) this._renderSuggestedQuestions(questions);
          this._scrollToBottom();
          if (!this._isOpen) this._addUnread();
          break;
        }

        case 'ai': {
          // Legacy streaming chunk support (kept for backward compatibility)
          this._hideTypingIndicator();
          this._aiBuffer += (data.message || '');
          if (!this._streamingBubble) {
            this._streamingBubble = this._appendStreamingBot();
          }
          this._streamingBubble.innerHTML = renderMarkdown(this._aiBuffer);
          this._streamingBubble.classList.add('cb-streaming-cursor');
          this._scrollToBottom();
          break;
        }

        case 'end_of_response':
          this._hideAllIndicators();
          this._isStreaming = false;
          if (this._streamingBubble) {
            // Finalise any streaming bubble (legacy 'ai' chunk flow)
            this._streamingBubble.classList.remove('cb-streaming-cursor');
            this._streamingBubble.innerHTML = renderMarkdown(this._aiBuffer);
            this._streamingBubble = null;
          }
          this._aiBuffer = '';
          this._scrollToBottom();
          if (!this._isOpen) this._addUnread();
          break;

        case 'error':
          this._hideAllIndicators();
          this._hideRetryIndicator();
          this._isStreaming     = false;
          this._streamingBubble = null;
          // Log detail to console for debugging, but only show error to user
          if (data.detail) {
            console.warn('[ChatbotWidget] Error detail:', data.detail);
          }
          this._showErrorMessage(data.error || 'An unknown error occurred.');
          break;
      }
    }

    /* ── send message ───────────────────────────────────────── */
    _send() {
      const text = this._input.value.trim();
      if (!text || !this._ws || this._ws.readyState !== WebSocket.OPEN || this._isStreaming) return;

      // Remove any visible suggestion chips before sending
      this._msgArea.querySelectorAll('.cb-suggestions').forEach(s => s.remove());

      let messageToSend = text;

      // Check if this is the first message and student data exists in localStorage
      if (!this._firstMessageSent) {
        const studentId = localStorage.getItem('student_id');
        const studentClass = localStorage.getItem('student_class');
        const class10Status = localStorage.getItem('psychometric_class10_status');
        const class12Status = localStorage.getItem('psychometric_class12_status');

        // If all student fields exist, append the system message
        if (studentId && studentClass && class10Status && class12Status) {
          const systemMessage = `\n\n------ system message bellow ------\n\nhere is the student details to access his Psychometric Test\n\nstudent_id : ${studentId}\nstudent_class : ${studentClass}\npsychometric_class10_status : ${class10Status}\npsychometric_class12_status : ${class12Status}`;
          messageToSend = text + systemMessage;
        }

        this._firstMessageSent = true;
      }

      this._appendMessage('user', text);
      this._input.value = '';
      this._input.style.height = '46px';
      this._scrollToBottom();

      this._ws.send(JSON.stringify({ message: messageToSend }));
    }

    /* ── new conversation ───────────────────────────────────── */
    _newConversation() {
      this._hideAllIndicators();
      this._streamingBubble = null;
      this._aiBuffer        = '';
      this._isStreaming     = false;
      this._showWelcome();

      if (CFG.devMode) {
        this._sidInput.value = '';
        this._updateDevDisplay('No session connected.');
        this._setStatus('disconnected');
        if (this._ws) { this._ws.onclose = null; this._ws.close(); this._ws = null; }
      } else {
        this._createSession();
      }
    }

    /* ── DOM: append finished message (no avatar) ───────────── */
    _appendMessage(role, content, date) {
      const welcome = this._msgArea.querySelector('.cb-welcome');
      if (welcome) welcome.remove();

      const isUser = role === 'user';
      const row    = el('div', { className: `cb-msg ${isUser ? 'cb-user' : 'cb-bot'}` });
      const bubble = el('div', { className: `cb-bubble${isUser ? '' : ' cb-md'}` });

      if (isUser) {
        bubble.textContent = content;
      } else {
        bubble.innerHTML = renderMarkdown(content);
      }

      const ts = el('div', { className: 'cb-ts', textContent: formatTime(date) });
      row.appendChild(bubble);
      row.appendChild(ts);
      this._msgArea.appendChild(row);
      return bubble;
    }

    /* ── DOM: create streaming bot bubble (no avatar) ───────── */
    _appendStreamingBot() {
      const welcome = this._msgArea.querySelector('.cb-welcome');
      if (welcome) welcome.remove();

      const row    = el('div', { className: 'cb-msg cb-bot' });
      const bubble = el('div', { className: 'cb-bubble cb-md' });
      const ts     = el('div', { className: 'cb-ts', textContent: formatTime() });
      row.appendChild(bubble);
      row.appendChild(ts);
      this._msgArea.appendChild(row);
      return bubble;
    }

    /* ── DOM: suggested follow-up questions ────────────────────── */
    // Renders clickable question chips below the last bot message.
    // Clicking a chip fills the input with that question and sends it.
    _renderSuggestedQuestions(questions) {
      if (!questions || !questions.length) return;

      const wrap = el('div', { className: 'cb-suggestions' });
      questions.forEach(q => {
        const btn = el('button', { className: 'cb-suggestion-btn', textContent: q });
        btn.addEventListener('click', () => {
          // Remove all suggestion rows before sending
          this._msgArea.querySelectorAll('.cb-suggestions').forEach(s => s.remove());
          this._input.value = q;
          this._send();
        });
        wrap.appendChild(btn);
      });
      this._msgArea.appendChild(wrap);
    }

    /* ── DOM: error strip ───────────────────────────────────── */
    _showErrorMessage(msg) {
      const err = el('div', { className: 'cb-err-msg' });
      err.innerHTML = IC.error + `<span>${msg}</span>`;
      this._msgArea.appendChild(err);
      this._scrollToBottom();
    }

    /* ── DOM: typing indicator ──────────────────────────────── */
    _showTypingIndicator() {
      if (this._typingIndicator) return;
      
      // Agent-like status messages that rotate
      const messages = [
        'Analyzing your question...',
        'Gathering information...',
        'Consulting knowledge base...',
        'Preparing response...',
        'Almost ready...'
      ];
      
      const ind = el('div', { className: 'cb-indicator cb-ind-typing' });
      const textSpan = el('span', { textContent: messages[0] });
      const dotRow = el('div', { className: 'cb-dot-row' });
      dotRow.innerHTML = '<span></span><span></span><span></span>';
      ind.appendChild(textSpan);
      ind.appendChild(dotRow);
      
      this._typingIndicator = ind;
      this._typingMessageIndex = 0;
      this._indicatorArea.appendChild(ind);
      this._scrollToBottom();
      
      // Rotate messages every 4 seconds
      this._typingInterval = setInterval(() => {
        this._typingMessageIndex = (this._typingMessageIndex + 1) % messages.length;
        textSpan.textContent = messages[this._typingMessageIndex];
      }, 4000);
    }
    
    _hideTypingIndicator() {
      if (this._typingInterval) {
        clearInterval(this._typingInterval);
        this._typingInterval = null;
      }
      if (this._typingIndicator) { 
        this._typingIndicator.remove(); 
        this._typingIndicator = null; 
      }
    }

    /* ── DOM: search indicator ──────────────────────────────── */
    _showSearchIndicator() {
      if (this._searchIndicator) return;
      const ind = el('div', { className: 'cb-indicator cb-ind-search' });
      ind.innerHTML = `${IC.search}<span>Searching the web…</span><div class="cb-dot-row"><span></span><span></span><span></span></div>`;
      this._searchIndicator = ind;
      this._indicatorArea.appendChild(ind);
      this._scrollToBottom();
    }
    _hideSearchIndicator() {
      if (this._searchIndicator) { this._searchIndicator.remove(); this._searchIndicator = null; }
    }

    /* ── DOM: retry indicator ──────────────────────────────── */
    _showRetryIndicator(attempt, maxAttempts, message) {
      // Remove existing retry indicator first
      this._hideRetryIndicator();
      const ind = el('div', { className: 'cb-indicator cb-ind-retry' });
      ind.innerHTML = `${IC.retry}<span>${message || `Retrying… (${attempt}/${maxAttempts})`}</span>`;
      this._retryIndicator = ind;
      this._indicatorArea.appendChild(ind);
      this._scrollToBottom();
    }
    _hideRetryIndicator() {
      if (this._retryIndicator) { this._retryIndicator.remove(); this._retryIndicator = null; }
    }

    _hideAllIndicators() {
      this._hideTypingIndicator();
      this._hideSearchIndicator();
      this._hideRetryIndicator();
    }

    /* ── Tool output card ───────────────────────────────────── */
    // Renders a collapsible card inline in the chat for each
    // tool_output event. Web search results → source links;
    // SQL/DB tools → loading message (production) or raw output (devMode).
    _appendToolCard(data) {
      const { tool_name, message, is_debug } = data;

      // Identify tool types
      const isWeb   = tool_name === 'duckduckgo_results_json' || tool_name === 'google_search';
      const isSqlTool = tool_name && tool_name.startsWith('sql_db_');

      // In production mode, SQL tools show a friendly loading message.
      // In devMode, we show the raw output. Legacy is_debug flag is still respected.
      const showSqlCard = isSqlTool && (!is_debug || CFG.devMode);

      // Skip rendering if it's a debug-only tool and we're not in devMode
      if (is_debug && !CFG.devMode && !isSqlTool) return;

      // Remove welcome screen if still showing
      const welcome = this._msgArea.querySelector('.cb-welcome');
      if (welcome) welcome.remove();

      // Determine card styling class
      const cardClass = isWeb ? 'cb-tc-web' : 'cb-tc-sql';
      const card = el('div', { className: `cb-tool-card ${cardClass}` });

      /* ── Header ── */
      const hdr     = el('div', { className: 'cb-tool-card-hdr' });
      const iconEl  = el('span', { className: 'cb-tool-card-icon', innerHTML: isWeb ? IC.search : IC.toolSql });
      const labelEl = el('span', { className: 'cb-tool-card-label',
        textContent: isWeb ? 'Web Search' : (isSqlTool ? 'Database' : tool_name.replace(/_/g, ' ')) });
      const metaEl  = el('span', { className: 'cb-tool-card-meta' });
      const chevron = el('span', { className: 'cb-tool-card-chevron', innerHTML: IC.chevron });
      hdr.appendChild(iconEl);
      hdr.appendChild(labelEl);
      hdr.appendChild(metaEl);
      hdr.appendChild(chevron);

      /* ── Body ── */
      const body = el('div', { className: 'cb-tool-card-body' });

      if (isWeb) {
        // Web Search: Parse and display results
        const results = this._parseWebSearchResults(message || '');
        const n = results.length;
        metaEl.textContent = `${n} source${n !== 1 ? 's' : ''}`;
        if (n === 0) {
          body.appendChild(el('div', { className: 'cb-tool-empty', textContent: 'No results returned.' }));
        } else {
          results.forEach(r => {
            const item = document.createElement('a');
            item.className = 'cb-src-item';
            item.href      = r.link || '#';
            item.target    = '_blank';
            item.rel       = 'noopener noreferrer';
            item.appendChild(el('div', { className: 'cb-src-title',   textContent: r.title   || 'Untitled' }));
            if (r.snippet)
              item.appendChild(el('div', { className: 'cb-src-snippet', textContent: r.snippet }));
            item.appendChild(el('div', { className: 'cb-src-url',     textContent: this._truncateUrl(r.link || '') }));
            body.appendChild(item);
          });
        }
      } else if (isSqlTool) {
        // SQL/Database tool output
        if (CFG.devMode) {
          // Dev mode: show raw SQL query and results
          metaEl.textContent = 'debug';
          body.appendChild(el('pre', { className: 'cb-tool-raw', textContent: message || '(empty)' }));
        } else {
          // Production mode: show user-friendly loading message
          metaEl.textContent = 'working';
          const loadingMsg = el('div', { className: 'cb-tool-loading' });
          loadingMsg.innerHTML = `<span class="cb-tool-loading-icon">🔍</span><span>${message || 'Fetching information from database...'}</span>`;
          body.appendChild(loadingMsg);
        }
      } else {
        // Other debug tools (fallback)
        metaEl.textContent = 'debug';
        body.appendChild(el('pre', { className: 'cb-tool-raw', textContent: message || '(empty)' }));
      }

      /* ── Toggle on header click ── */
      hdr.addEventListener('click', () => card.classList.toggle('cb-tc-open'));

      card.appendChild(hdr);
      card.appendChild(body);
      this._msgArea.appendChild(card);
      this._scrollToBottom();
    }

    /* ── Parse web search results (DuckDuckGo or Google) ─────── */
    // Handles multiple formats:
    // - DuckDuckGo: "snippet: ..., title: ..., link: ..."
    // - Google Search: plain text with dates and "..." separators
    // - JSON: array or object with results
    // Output: [{snippet, title, link}, ...]
    _parseWebSearchResults(text) {
      const results = [];
      if (!text) return results;

      // Try JSON format first
      if (text.trim().startsWith('[') || text.trim().startsWith('{')) {
        try {
          const parsed = JSON.parse(text);
          const items = Array.isArray(parsed) ? parsed : (parsed.results || parsed.items || []);
          return items.map(r => ({
            snippet: r.snippet || r.description || r.summary || '',
            title: r.title || r.name || '',
            link: r.link || r.url || r.href || ''
          })).filter(r => r.link || r.title);
        } catch (e) {
          // Not valid JSON, fall through to text parsing
        }
      }

      // Check for DuckDuckGo format: "snippet: ..., title: ..., link: ..."
      if (text.includes('snippet:') && text.includes('title:') && text.includes('link:')) {
        const chunks = text.split(/snippet:\s*/i).slice(1);
        for (const chunk of chunks) {
          if (!chunk.trim()) continue;
          const result = { snippet: '', title: '', link: '' };
          const snippetMatch = chunk.match(/^(.+?)(?=,\s*title:|,\s*link:|$)/i);
          if (snippetMatch) result.snippet = snippetMatch[1].trim().replace(/,$/, '');
          const titleMatch = chunk.match(/title:\s*(.+?)(?=,\s*link:|,\s*snippet:|$)/i);
          if (titleMatch) result.title = titleMatch[1].trim().replace(/,$/, '');
          const linkMatch = chunk.match(/link:\s*(https?:\/\/[^\s,]+)/i);
          if (linkMatch) result.link = linkMatch[1].trim();
          if (result.link || result.title) results.push(result);
        }
        return results;
      }

      // Google Search plain text format: "Dec 11, 2023 ... snippet text ... Apr 16, 2024 ..."
      // Split by date patterns followed by "..."
      const datePattern = /\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\s*\.\.\./gi;
      const matches = text.split(datePattern).filter(s => s.trim());
      
      // Also try splitting by just "..." if no dates found
      const snippets = matches.length > 0 ? matches : text.split(/\.\.\./).filter(s => s.trim());
      
      for (const snippet of snippets) {
        const trimmed = snippet.trim();
        if (!trimmed || trimmed.length < 20) continue; // Skip very short fragments
        
        results.push({
          snippet: trimmed,
          title: 'Search Result',
          link: ''
        });
      }

      return results.length > 0 ? results : [{ snippet: text, title: 'Search Result', link: '' }];
    }

    /* ── Collapse all tool cards (called on each new exchange) ─ */
    _collapseAllToolCards() {
      this._msgArea.querySelectorAll('.cb-tool-card').forEach(c => c.classList.remove('cb-tc-open'));
    }

    /* ── URL truncator ──────────────────────────────────────── */
    _truncateUrl(url) {
      try {
        const u    = new URL(url);
        const path = u.pathname.length > 28 ? u.pathname.slice(0, 28) + '…' : u.pathname;
        return u.hostname + path;
      } catch { return url.slice(0, 45); }
    }

    /* ── DOM: scroll to bottom ──────────────────────────────── */
    _scrollToBottom() {
      this._msgArea.scrollTop = this._msgArea.scrollHeight;
    }

    /* ── Dev mode: update session display text ──────────────── */
    _updateDevDisplay(text) {
      if (this._sidDisplay) this._sidDisplay.textContent = text;
    }
  }

  /* ============================================================
   * AUTO-INITIALISE when DOM is ready
   * ============================================================ */
  function init() {
    global.ChatbotWidgetInstance = new ChatbotWidget();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

}(window));
