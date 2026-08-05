/**
 * TopTeen voice navigation + form fill (mobile-first).
 *
 * Visibility gate (all required):
 *   1) Admin ENABLE_VOICE_TO_TEXT / window.TT_VOICE_TO_TEXT_ENABLED
 *   2) Browser speech usable (SpeechRecognition + secure context)
 *   3) No prior session engine failure (sessionStorage tt_voice_stt_ok !== '0')
 *
 * Only then: mic, green status box, and command suggestion chips are shown.
 *
 * Usage:
 *   TTVoiceNav.attach({ pageCommands, forms });
 *   TTVoiceNav.detach();
 */
(function (global) {
  'use strict';

  var BAR_ID = 'ttVoiceNavBar';
  var STYLE_ID = 'ttVoiceNavStyles';
  var PROBE_KEY = 'tt_voice_stt_ok';
  var SILENCE_MS = 4000;

  var active = null; // { recognition, wantListening, busy, formCtx, ... }

  function voiceFeatureEnabled() {
    try {
      if (typeof global.TT_VOICE_TO_TEXT_ENABLED !== 'undefined' && !global.TT_VOICE_TO_TEXT_ENABLED) {
        return false;
      }
    } catch (e) {}
    return true;
  }

  function getSpeechCtor() {
    try {
      return global.SpeechRecognition || global.webkitSpeechRecognition || null;
    } catch (e) {
      return null;
    }
  }

  function insecureContextBlocked() {
    try {
      return global.isSecureContext === false;
    } catch (e) {
      return false;
    }
  }

  function canUseSpeechNow() {
    return !!getSpeechCtor() && !insecureContextBlocked();
  }

  function isAppleMobileSafari() {
    try {
      var ua = (navigator.userAgent || '');
      var iOS = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
      var webkit = /WebKit/i.test(ua);
      var notCriOS = !/CriOS|FxiOS|EdgiOS|OPiOS/i.test(ua);
      return iOS && webkit && notCriOS;
    } catch (e) {
      return false;
    }
  }

  function speechUnavailableReason() {
    if (!voiceFeatureEnabled()) return 'Voice is turned off by admin.';
    if (insecureContextBlocked()) {
      return 'This page is not a secure context (use HTTPS or localhost).';
    }
    if (!getSpeechCtor()) {
      if (isAppleMobileSafari()) {
        return 'iPhone Safari has no browser speech-to-text. Use the green chips, or tap a field and use the iOS keyboard mic.';
      }
      return 'This browser has no speech engine. Try Chrome or Edge on desktop/Android.';
    }
    if (getProbeCache() === '0') {
      return 'Speech engine failed earlier this session. Refresh or clear site data, then try again.';
    }
    return '';
  }

  function getProbeCache() {
    try {
      return global.sessionStorage.getItem(PROBE_KEY);
    } catch (e) {
      return null;
    }
  }

  function setProbeCache(ok) {
    try {
      global.sessionStorage.setItem(PROBE_KEY, ok ? '1' : '0');
    } catch (e) {}
  }

  function speechEngineReady() {
    if (!canUseSpeechNow()) return false;
    if (getProbeCache() === '0') return false;
    return true;
  }

  /**
   * Show green command bar when admin enables voice.
   * Mic only when the browser speech engine is ready; otherwise chips-only
   * (so LAN/dev can still test navigation when Chrome STT fails).
   */
  function shouldShowVoiceUi() {
    return voiceFeatureEnabled();
  }

  function micAllowed(state) {
    if (state && state.commandsOnly) return false;
    return speechEngineReady();
  }

  function norm(s) {
    return String(s || '')
      .toLowerCase()
      .replace(/[^\w\s@.+-]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  var WORD_DIGIT = {
    zero: '0', oh: '0', one: '1', two: '2', three: '3', four: '4',
    five: '5', six: '6', seven: '7', eight: '8', nine: '9'
  };

  function spokenToDigits(text) {
    var raw = String(text || '');
    var digits = raw.replace(/\D+/g, '');
    if (digits.length >= 8) return digits;
    var parts = norm(raw).split(' ');
    var out = '';
    for (var i = 0; i < parts.length; i++) {
      if (WORD_DIGIT[parts[i]] != null) out += WORD_DIGIT[parts[i]];
      else if (/^\d+$/.test(parts[i])) out += parts[i];
    }
    return out || digits;
  }

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    var css = document.createElement('style');
    css.id = STYLE_ID;
    css.textContent = [
      '#' + BAR_ID + '{',
      'position:fixed;left:0;right:0;bottom:0;z-index:12200;',
      'padding:10px 12px calc(10px + env(safe-area-inset-bottom,0px));',
      'pointer-events:none;display:none;',
      'font-family:inherit;',
      '}',
      '#' + BAR_ID + '.is-visible{display:block;}',
      '#' + BAR_ID + ' .ttvn-panel{',
      'pointer-events:auto;max-width:720px;margin:0 auto;',
      'background:linear-gradient(180deg,#e8f8ef 0%,#d7f2e3 100%);',
      'border:1px solid #8fd3a8;border-radius:16px;',
      'box-shadow:0 8px 28px rgba(16,80,40,.18);',
      'padding:10px 12px;color:#14532d;',
      '}',
      '#' + BAR_ID + ' .ttvn-row{display:flex;align-items:flex-start;gap:10px;}',
      '#' + BAR_ID + ' .ttvn-mic{',
      'flex:0 0 auto;width:48px;height:48px;border-radius:50%;',
      'border:2px solid #2f9e5d;background:#fff;color:#1b7a45;',
      'display:inline-flex;align-items:center;justify-content:center;',
      'font-size:22px;line-height:1;touch-action:manipulation;',
      '}',
      '#' + BAR_ID + ' .ttvn-mic.is-listening{',
      'background:#1b7a45;color:#fff;border-color:#14532d;',
      'animation:ttvn-pulse 1.2s ease-in-out infinite;',
      '}',
      '#' + BAR_ID + ' .ttvn-mic:disabled,',
      '#' + BAR_ID + ' .ttvn-mic.is-busy{',
      'opacity:.55;cursor:not-allowed;animation:none;',
      '}',
      '#' + BAR_ID + ' .ttvn-body{flex:1;min-width:0;}',
      '#' + BAR_ID + ' .ttvn-heard{',
      'font-size:14px;font-weight:700;line-height:1.3;',
      'word-break:break-word;min-height:1.3em;',
      '}',
      '#' + BAR_ID + ' .ttvn-status{',
      'font-size:12px;line-height:1.35;margin-top:2px;opacity:.92;',
      '}',
      '#' + BAR_ID + ' .ttvn-status.is-err{color:#9a3412;}',
      '#' + BAR_ID + ' .ttvn-chips{',
      'display:flex;gap:8px;overflow-x:auto;-webkit-overflow-scrolling:touch;',
      'margin-top:8px;padding-bottom:2px;scrollbar-width:none;',
      '}',
      '#' + BAR_ID + ' .ttvn-chips::-webkit-scrollbar{display:none;}',
      '#' + BAR_ID + ' .ttvn-chip{',
      'flex:0 0 auto;border:1px solid #6fbf8d;background:#fff;',
      'color:#166534;border-radius:999px;padding:7px 12px;',
      'font-size:12px;font-weight:600;white-space:nowrap;',
      'touch-action:manipulation;min-height:36px;',
      '}',
      '#' + BAR_ID + ' .ttvn-chip:disabled{opacity:.5;}',
      '#' + BAR_ID + ' .ttvn-help{',
      'display:none;margin-top:8px;padding:8px 10px;',
      'background:rgba(255,255,255,.72);border-radius:12px;',
      'font-size:12px;line-height:1.45;',
      '}',
      '#' + BAR_ID + ' .ttvn-help.is-open{display:block;}',
      '#' + BAR_ID + ' .ttvn-close{',
      'flex:0 0 auto;width:36px;height:36px;border:0;background:transparent;',
      'color:#166534;font-size:22px;line-height:1;border-radius:8px;',
      '}',
      '@keyframes ttvn-pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.06)}}',
      'body.ttvn-bar-open{padding-bottom:118px !important;}',
      '@media (max-width:767.98px){',
      'body.ttvn-bar-open{padding-bottom:128px !important;}',
      '#' + BAR_ID + ' .ttvn-panel{border-radius:14px 14px 0 0;}',
      '}'
    ].join('');
    document.head.appendChild(css);
  }

  function ensureBar(state) {
    injectStyles();
    var bar = document.getElementById(BAR_ID);
    if (bar) {
      state.bar = bar;
      state.heardEl = bar.querySelector('[data-ttvn-heard]');
      state.statusEl = bar.querySelector('[data-ttvn-status]');
      state.chipsEl = bar.querySelector('[data-ttvn-chips]');
      state.helpEl = bar.querySelector('[data-ttvn-help]');
      state.micBtn = bar.querySelector('[data-ttvn-mic]');
      return bar;
    }
    bar = document.createElement('div');
    bar.id = BAR_ID;
    bar.setAttribute('role', 'region');
    bar.setAttribute('aria-label', 'Voice commands');
    bar.innerHTML =
      '<div class="ttvn-panel">' +
        '<div class="ttvn-row">' +
          '<button type="button" class="ttvn-mic" data-ttvn-mic aria-label="Start voice command" title="Voice command">' +
            "<i class='bx bx-microphone' aria-hidden='true'></i>" +
          '</button>' +
          '<div class="ttvn-body">' +
            '<div class="ttvn-heard" data-ttvn-heard>Tap mic to speak</div>' +
            '<div class="ttvn-status" data-ttvn-status>Try: Edit contact · Help</div>' +
            '<div class="ttvn-chips" data-ttvn-chips></div>' +
            '<div class="ttvn-help" data-ttvn-help></div>' +
          '</div>' +
          '<button type="button" class="ttvn-close" data-ttvn-collapse aria-label="Hide voice bar" title="Hide">×</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(bar);
    state.bar = bar;
    state.heardEl = bar.querySelector('[data-ttvn-heard]');
    state.statusEl = bar.querySelector('[data-ttvn-status]');
    state.chipsEl = bar.querySelector('[data-ttvn-chips]');
    state.helpEl = bar.querySelector('[data-ttvn-help]');
    state.micBtn = bar.querySelector('[data-ttvn-mic]');

    if (state.micBtn) {
      state.micBtn.addEventListener('click', function (e) {
        e.preventDefault();
        if (state.busy || state.micBtn.disabled) return;
        if (state.wantListening) stopListening(state, 'Paused. Tap mic to continue.');
        else startListening(state);
      });
    }
    var collapse = bar.querySelector('[data-ttvn-collapse]');
    if (collapse) {
      collapse.addEventListener('click', function () {
        stopListening(state);
        hideBar(state);
      });
    }
    return bar;
  }

  function showBar(state) {
    if (!state || !state.bar) return;
    state.bar.classList.add('is-visible');
    document.body.classList.add('ttvn-bar-open');
  }

  function hideBar(state) {
    if (!state || !state.bar) return;
    state.bar.classList.remove('is-visible');
    document.body.classList.remove('ttvn-bar-open');
  }

  function setHeard(state, text) {
    if (state.heardEl) state.heardEl.textContent = text || '';
  }

  function setStatus(state, text, kind) {
    if (!state.statusEl) return;
    state.statusEl.textContent = text || '';
    state.statusEl.classList.toggle('is-err', kind === 'err');
  }

  function setBusy(state, busy, reason) {
    state.busy = !!busy;
    if (state.micBtn) {
      state.micBtn.disabled = !!busy;
      state.micBtn.classList.toggle('is-busy', !!busy);
      state.micBtn.setAttribute('aria-disabled', busy ? 'true' : 'false');
    }
    if (state.chipsEl) {
      var chips = state.chipsEl.querySelectorAll('.ttvn-chip');
      for (var i = 0; i < chips.length; i++) chips[i].disabled = !!busy;
    }
    if (busy) {
      setStatus(state, reason || 'Working…');
      if (state.wantListening) stopListening(state, reason || 'Working…', true);
    }
  }

  function currentSuggestions(state) {
    if (state.formCtx && state.formCtx.active) {
      return ['Next', 'Back', 'Save', 'Cancel', 'Help'];
    }
    return ['Edit contact', 'Help'];
  }

  function helpText(state) {
    var reason = speechUnavailableReason();
    var iosTip = reason
      ? '<br><br><strong>Why no mic?</strong><br>' + reason
      : '';
    if (state.formCtx && state.formCtx.active) {
      return [
        '<strong>Form commands</strong>',
        '• Next / Back — move fields',
        '• Name … / Mobile … / Email … / School …',
        '• Gender male|female · Class 10',
        '• Save · Cancel · Help',
        'Invalid values stay on the field until fixed.',
        iosTip,
        isAppleMobileSafari()
          ? '<br><br>On iPhone: tap a field, then use the keyboard microphone for dictation.'
          : ''
      ].join('<br>');
    }
    return [
      '<strong>Page commands</strong>',
      '• Edit contact — open personal info',
      '• Help — show this list',
      'Open a form, then say Next / Save or dictate a field.',
      iosTip
    ].join('<br>');
  }

  function renderChips(state) {
    if (!state.chipsEl) return;
    var items = currentSuggestions(state);
    state.chipsEl.innerHTML = '';
    items.forEach(function (label) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'ttvn-chip';
      btn.textContent = label;
      btn.disabled = !!state.busy;
      btn.addEventListener('click', function () {
        if (state.busy) return;
        handleUtterance(state, label);
      });
      state.chipsEl.appendChild(btn);
    });
    if (state.helpEl) {
      state.helpEl.innerHTML = helpText(state);
    }
  }

  function destroyRecognition(state) {
    if (!state.recognition) return;
    var r = state.recognition;
    try { r.onstart = r.onerror = r.onend = r.onresult = null; } catch (e) {}
    try { r.abort(); } catch (e2) {}
    state.recognition = null;
  }

  function stopListening(state, statusMsg, keepBusy) {
    state.wantListening = false;
    state.ignoreEnd = true;
    if (state.silenceTimer) {
      clearTimeout(state.silenceTimer);
      state.silenceTimer = null;
    }
    destroyRecognition(state);
    if (state.micBtn) {
      state.micBtn.classList.remove('is-listening');
      var icon = state.micBtn.querySelector('i');
      if (icon) icon.className = 'bx bx-microphone';
    }
    if (statusMsg) setStatus(state, statusMsg, keepBusy ? null : null);
    else if (!keepBusy && !state.busy) {
      setStatus(state, state.formCtx && state.formCtx.active
        ? 'Say Next, Save, or a field value'
        : 'Try: Edit contact · Help');
    }
  }

  function applyMicVisibility(state) {
    if (!state || !state.micBtn) return;
    var allow = micAllowed(state);
    state.micBtn.hidden = !allow;
    state.micBtn.style.display = allow ? '' : 'none';
    state.micBtn.setAttribute('aria-hidden', allow ? 'false' : 'true');
    if (!allow) {
      state.micBtn.classList.remove('is-listening');
      state.micBtn.disabled = true;
    } else if (!state.busy) {
      state.micBtn.disabled = false;
    }
  }

  function markBroken(state, reason) {
    try { console.warn('[tt-voice-nav] speech engine unavailable:', reason || 'unknown'); } catch (e) {}
    setProbeCache(false);
    stopListening(state);
    // Keep the green bar + chips so users can still navigate/test without STT.
    if (state) {
      state.commandsOnly = true;
      applyMicVisibility(state);
      setHeard(state, 'Voice engine unavailable');
      setStatus(state, 'Use suggestion chips below (mic hidden). Reason logged in console.');
      showBar(state);
      renderChips(state);
    }
  }

  function armSilence(state) {
    if (state.silenceTimer) clearTimeout(state.silenceTimer);
    state.silenceTimer = setTimeout(function () {
      state.silenceTimer = null;
      if (!state.wantListening) return;
      stopListening(state, 'Paused. Tap mic to speak more.');
    }, SILENCE_MS);
  }

  function startListening(state) {
    if (state.busy || !shouldShowVoiceUi()) return;
    if (!micAllowed(state)) {
      setStatus(state, 'Mic unavailable here — tap a suggestion chip instead.');
      return;
    }
    var Ctor = getSpeechCtor();
    if (!Ctor) {
      markBroken(state, 'SpeechRecognition missing');
      return;
    }
    destroyRecognition(state);
    var r = new Ctor();
    state.recognition = r;
    state.wantListening = true;
    state.ignoreEnd = false;
    state.networkRetry = false;
    r.continuous = false;
    r.interimResults = true;
    r.maxAlternatives = 1;
    r.lang = navigator.language || 'en-IN';

    r.onstart = function () {
      setProbeCache(true);
      if (state.micBtn) {
        state.micBtn.classList.add('is-listening');
        var icon = state.micBtn.querySelector('i');
        if (icon) icon.className = 'bx bx-stop-circle';
      }
      setHeard(state, 'Listening…');
      setStatus(state, 'Speak a command — pause 4s to stop');
      armSilence(state);
    };

    r.onerror = function (ev) {
      var err = (ev && ev.error) || '';
      try { console.warn('[tt-voice-nav] error:', err); } catch (e) {}
      if (err === 'aborted' || err === 'no-speech') return;
      if (err === 'network' && !state.networkRetry && state.wantListening) {
        state.networkRetry = true;
        state.ignoreEnd = true;
        destroyRecognition(state);
        setTimeout(function () {
          if (state.wantListening && !state.busy) startListening(state);
        }, 400);
        return;
      }
      if (
        err === 'network' ||
        err === 'not-allowed' ||
        err === 'service-not-allowed' ||
        err === 'audio-capture'
      ) {
        markBroken(state, err);
        return;
      }
      stopListening(state, 'Could not hear that. Tap mic to try again.');
    };

    r.onend = function () {
      if (!state.wantListening || state.ignoreEnd || state.busy) {
        if (state.micBtn) state.micBtn.classList.remove('is-listening');
        return;
      }
      // restart until silence timer stops us
      setTimeout(function () {
        if (state.wantListening && !state.busy && shouldShowVoiceUi()) {
          try { startListening(state); } catch (e) {}
        }
      }, 180);
    };

    r.onresult = function (event) {
      if (!state.wantListening || state.busy) return;
      var interim = '';
      var finalText = '';
      for (var i = event.resultIndex; i < event.results.length; i++) {
        var piece = (event.results[i][0] && event.results[i][0].transcript) || '';
        if (!piece) continue;
        if (event.results[i].isFinal) finalText += (finalText ? ' ' : '') + piece;
        else interim = piece;
      }
      var shown = (finalText || interim || '').trim();
      if (shown) {
        setHeard(state, '“' + shown + '”');
        armSilence(state);
      }
      if (finalText) {
        handleUtterance(state, finalText);
      }
    };

    try {
      r.start();
    } catch (eStart) {
      try { console.warn('[tt-voice-nav] start failed', eStart); } catch (e2) {}
      stopListening(state, 'Could not start microphone.');
    }
  }

  /* ---------- validation & field ops ---------- */

  function validateField(field, value) {
    var v = String(value == null ? '' : value).trim();
    if (field.required && !v) {
      return { ok: false, message: (field.label || 'This field') + ' is required.' };
    }
    if (!v) return { ok: true, value: v };
    if (field.type === 'email') {
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) {
        return { ok: false, message: 'Enter a valid email address.' };
      }
    }
    if (field.type === 'mobile') {
      var d = spokenToDigits(v).slice(0, 10);
      if (!/^[6-9]\d{9}$/.test(d)) {
        return { ok: false, message: 'Mobile must be a 10-digit number starting with 6–9.' };
      }
      return { ok: true, value: d };
    }
    if (field.type === 'date') {
      // accept YYYY-MM-DD or spoken-ish dd/mm/yyyy
      var iso = v;
      var m = v.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})$/);
      if (m) {
        iso = m[3] + '-' + ('0' + m[2]).slice(-2) + '-' + ('0' + m[1]).slice(-2);
      }
      if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
        return { ok: false, message: 'Say date as day month year, or pick it on screen.' };
      }
      return { ok: true, value: iso };
    }
    return { ok: true, value: v };
  }

  function getFormFields(formCfg) {
    return formCfg.fields || [];
  }

  function focusField(state, field) {
    var el = document.getElementById(field.id);
    if (!el) return;
    try {
      el.focus({ preventScroll: false });
      el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    } catch (e) {
      try { el.focus(); } catch (e2) {}
    }
    state.formCtx.index = getFormFields(state.formCtx.cfg).indexOf(field);
    setStatus(state, 'Editing ' + (field.label || field.id));
  }

  function setFieldValue(field, value) {
    var el = document.getElementById(field.id);
    if (!el) return false;
    if (el.tagName === 'SELECT') {
      var want = norm(value);
      var opts = el.options;
      var matched = null;
      // Pass 1: exact label/value match (avoids "female" matching "male")
      for (var i = 0; i < opts.length; i++) {
        var o = opts[i];
        var label = norm(o.textContent);
        var val = norm(o.value);
        if (!o.value && !label) continue;
        if (label === want || val === want) {
          matched = o;
          break;
        }
      }
      // Pass 2: safer partial match — only label contains full want (not want contains label)
      if (!matched) {
        for (var i2 = 0; i2 < opts.length; i2++) {
          var o2 = opts[i2];
          var label2 = norm(o2.textContent);
          if (!o2.value && !label2) continue;
          if (label2.indexOf(want) !== -1) {
            matched = o2;
            break;
          }
        }
      }
      // class shortcuts: "class 10" / "10"
      if (!matched && field.type === 'grade') {
        var g = want.replace(/class|grade|std|standard/g, '').trim();
        for (var j = 0; j < opts.length; j++) {
          var gl = norm(opts[j].textContent);
          if (gl === g || gl.indexOf(g) !== -1 || String(opts[j].value) === g) {
            matched = opts[j];
            break;
          }
        }
      }
      if (!matched) return false;
      el.value = matched.value;
    } else {
      el.value = value;
    }
    try {
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    } catch (e) {}
    return true;
  }

  function findFieldByAlias(fields, spoken) {
    var raw = String(spoken || '').trim();
    var t = norm(raw);
    for (var i = 0; i < fields.length; i++) {
      var f = fields[i];
      var keys = f.keys || [];
      for (var k = 0; k < keys.length; k++) {
        var key = norm(keys[k]);
        if (t === key || t.indexOf(key + ' ') === 0) {
          // Preserve original casing/spacing for the value portion
          var re = new RegExp('^' + key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '[\\s:]+', 'i');
          var rest = raw.replace(re, '').trim();
          return { field: f, rest: rest };
        }
      }
    }
    return null;
  }

  function parseGender(text) {
    var t = norm(text);
    if (/\b(male|boy|man)\b/.test(t) && !/female/.test(t)) return 'Male';
    if (/\b(female|girl|woman)\b/.test(t)) return 'Female';
    if (/\b(trans|transgender)\b/.test(t)) return 'Transgender';
    return text;
  }

  /* ---------- command handling ---------- */

  function runCommand(state, fn, workingMsg) {
    setBusy(state, true, workingMsg || 'Working…');
    var finished = false;
    function done(okMsg, kind) {
      if (finished) return;
      finished = true;
      setBusy(state, false);
      if (okMsg) setStatus(state, okMsg, kind === 'err' ? 'err' : null);
      renderChips(state);
    }
    try {
      var result = fn(done);
      if (result && typeof result.then === 'function') {
        result.then(function () { /* done called by fn */ }).catch(function () {
          done('Something went wrong.', 'err');
        });
      } else if (result !== 'async') {
        // sync commands call done themselves or we finish
      }
    } catch (e) {
      try { console.warn('[tt-voice-nav] command error', e); } catch (e2) {}
      done('Command failed.', 'err');
    }
  }

  function activateForm(state, formCfg) {
    state.formCtx = {
      active: true,
      cfg: formCfg,
      index: 0
    };
    var fields = getFormFields(formCfg);
    if (fields[0]) focusField(state, fields[0]);
    renderChips(state);
    if (state.helpEl) state.helpEl.classList.remove('is-open');
  }

  function deactivateForm(state) {
    state.formCtx = { active: false, cfg: null, index: 0 };
    renderChips(state);
  }

  function handleUtterance(state, raw) {
    var text = String(raw || '').trim();
    if (!text || state.busy) return;
    setHeard(state, '“' + text + '”');
    var t = norm(text);

    // Help
    if (t === 'help' || t === 'commands' || t.indexOf('voice command') !== -1) {
      runCommand(state, function (done) {
        if (state.helpEl) {
          state.helpEl.innerHTML = helpText(state);
          state.helpEl.classList.add('is-open');
        }
        done('Showing voice command help');
      }, 'Opening help…');
      return;
    }

    // Page-level commands
    if (!state.formCtx || !state.formCtx.active) {
      var pageCmds = state.config.pageCommands || [];
      for (var p = 0; p < pageCmds.length; p++) {
        var pc = pageCmds[p];
        if (pc.match && pc.match.test(t)) {
          runCommand(state, function (done) {
            var r = pc.run(done, text);
            if (r === 'async') return 'async';
            if (!r) done('Done');
          }, 'Running…');
          return;
        }
      }
      // fuzzy edit contact
      if (/(edit|open|change).*(contact|personal|profile|info)/.test(t) || t === 'edit contact') {
        var openBtn = document.getElementById('openPersonalInfoModal');
        if (openBtn) {
          runCommand(state, function (done) {
            openBtn.click();
            setTimeout(function () {
              var forms = state.config.forms || [];
              var cfg = forms[0] || null;
              for (var fi = 0; fi < forms.length; fi++) {
                if (forms[fi].id === 'personal') { cfg = forms[fi]; break; }
              }
              if (cfg) activateForm(state, cfg);
              done('Opened personal information');
            }, 350);
            return 'async';
          }, 'Opening contact info…');
          return;
        }
      }
      setStatus(state, 'Try: Edit contact · Help', 'err');
      return;
    }

    // Form context
    var cfg = state.formCtx.cfg;
    var fields = getFormFields(cfg);

    if (t === 'cancel' || t === 'close') {
      runCommand(state, function (done) {
        var modal = cfg.modal ? document.querySelector(cfg.modal) : null;
        if (modal && global.bootstrap && bootstrap.Modal) {
          var inst = bootstrap.Modal.getInstance(modal);
          if (inst) inst.hide();
        }
        deactivateForm(state);
        done('Cancelled');
      }, 'Closing…');
      return;
    }

    if (t === 'save' || t === 'save changes' || t === 'submit') {
      runCommand(state, function (done) {
        // validate all required fields first
        for (var i = 0; i < fields.length; i++) {
          var f = fields[i];
          var el = document.getElementById(f.id);
          var val = el ? el.value : '';
          var check = validateField(f, val);
          if (!check.ok) {
            focusField(state, f);
            if (el) el.classList.add('is-invalid');
            done(check.message, 'err');
            return 'async';
          }
          if (el) el.classList.remove('is-invalid');
        }
        var form = cfg.form ? document.querySelector(cfg.form) : null;
        if (form) {
          if (typeof cfg.onSave === 'function') {
            var maybe = cfg.onSave(function (ok, msg) {
              done(ok ? (msg || 'Saved') : (msg || 'Could not save'), ok ? null : 'err');
            });
            if (maybe === 'async' || (maybe && maybe.then)) return 'async';
          } else {
            form.requestSubmit();
            done('Saving…');
            return 'async';
          }
        }
        done('Save not available', 'err');
        return 'async';
      }, 'Validating…');
      return;
    }

    if (t === 'next' || t === 'next field') {
      runCommand(state, function (done) {
        var idx = state.formCtx.index || 0;
        var cur = fields[idx];
        if (cur) {
          var el = document.getElementById(cur.id);
          var check = validateField(cur, el ? el.value : '');
          if (!check.ok) {
            if (el) el.classList.add('is-invalid');
            focusField(state, cur);
            done(check.message, 'err');
            return 'async';
          }
          if (el) el.classList.remove('is-invalid');
        }
        var next = fields[Math.min(idx + 1, fields.length - 1)];
        if (next) focusField(state, next);
        done(next ? ('Moved to ' + (next.label || next.id)) : 'Last field');
      }, 'Next field…');
      return;
    }

    if (t === 'back' || t === 'previous' || t === 'previous field') {
      runCommand(state, function (done) {
        var idx = state.formCtx.index || 0;
        var prev = fields[Math.max(idx - 1, 0)];
        if (prev) focusField(state, prev);
        done(prev ? ('Moved to ' + (prev.label || prev.id)) : 'First field');
      }, 'Previous field…');
      return;
    }

    // Field-targeted fill: "name Rahul" / "mobile 987..."
    // Use original text so values keep spoken casing.
    var hit = findFieldByAlias(fields, text);
    if (hit && hit.rest) {
      runCommand(state, function (done) {
        var value = hit.rest;
        if (hit.field.type === 'gender') value = parseGender(value);
        if (hit.field.type === 'mobile') value = spokenToDigits(value);
        var check = validateField(hit.field, value);
        if (!check.ok) {
          focusField(state, hit.field);
          done(check.message, 'err');
          return 'async';
        }
        var ok = setFieldValue(hit.field, check.value);
        if (!ok) {
          done('Could not set ' + (hit.field.label || 'field'), 'err');
          return 'async';
        }
        focusField(state, hit.field);
        var el = document.getElementById(hit.field.id);
        if (el) el.classList.remove('is-invalid');
        done((hit.field.label || 'Field') + ' updated');
      }, 'Filling…');
      return;
    }

    // Bare gender / class utterances while on that field
    var curField = fields[state.formCtx.index || 0];
    if (curField) {
      var fillVal = text;
      if (curField.type === 'gender') fillVal = parseGender(text);
      if (curField.type === 'mobile') fillVal = spokenToDigits(text);
      if (curField.type === 'grade' && /class|grade|\b\d{1,2}\b/.test(t)) fillVal = text;

      // Only auto-fill current field if it doesn't look like a navigation command
      if (!/^(next|back|save|cancel|help)/.test(t)) {
        runCommand(state, function (done) {
          var check = validateField(curField, fillVal);
          if (!check.ok) {
            var elBad = document.getElementById(curField.id);
            if (elBad) elBad.classList.add('is-invalid');
            done(check.message, 'err');
            return 'async';
          }
          if (!setFieldValue(curField, check.value)) {
            done('Could not set ' + (curField.label || 'field') + '. Try Help.', 'err');
            return 'async';
          }
          var elOk = document.getElementById(curField.id);
          if (elOk) elOk.classList.remove('is-invalid');
          done((curField.label || 'Field') + ' set. Say Next or Save.');
        }, 'Filling…');
        return;
      }
    }

    setStatus(state, 'Didn’t catch that. Try Next, Save, or Help.', 'err');
    if (state.helpEl) {
      state.helpEl.innerHTML = helpText(state);
      state.helpEl.classList.add('is-open');
    }
  }

  function bindFormLifecycle(state) {
    (state.config.forms || []).forEach(function (formCfg) {
      if (!formCfg.modal) return;
      var modal = document.querySelector(formCfg.modal);
      if (!modal) return;
      modal.addEventListener('shown.bs.offcanvas', function () {});
      modal.addEventListener('shown.bs.modal', function () {
        if (!shouldShowVoiceUi()) return;
        ensureBar(state);
        showBar(state);
        applyMicVisibility(state);
        activateForm(state, formCfg);
        if (state.commandsOnly || !micAllowed(state)) {
          setHeard(state, isAppleMobileSafari() ? 'iPhone: use chips + keyboard mic' : 'Use chips to navigate');
          setStatus(
            state,
            isAppleMobileSafari()
              ? 'Safari has no web speech mic — tap Next/Save, or dictate in a field'
              : (speechUnavailableReason() || 'Mic unavailable — tap Next, Save, or Help')
          );
        } else {
          setHeard(state, 'Tap mic to speak');
          setStatus(state, 'Say Next, Save, or a field value');
        }
      });
      modal.addEventListener('hidden.bs.modal', function () {
        if (state.formCtx && state.formCtx.cfg === formCfg) {
          deactivateForm(state);
          if (state.commandsOnly || !micAllowed(state)) {
            setHeard(state, isAppleMobileSafari() ? 'iPhone chips mode' : 'Voice engine unavailable');
            setStatus(state, speechUnavailableReason() || 'Tap chips to test commands');
          } else {
            setHeard(state, 'Tap mic to speak');
            setStatus(state, 'Try: Edit contact · Help');
          }
          if (state.helpEl) state.helpEl.classList.remove('is-open');
        }
      });
    });
  }

  function attach(config) {
    detach();
    if (!shouldShowVoiceUi()) {
      try {
        console.warn('[tt-voice-nav] UI hidden — admin disabled ENABLE_VOICE_TO_TEXT');
      } catch (e) {}
      return null;
    }

    var state = {
      config: config || {},
      busy: false,
      wantListening: false,
      commandsOnly: !speechEngineReady(),
      formCtx: { active: false, cfg: null, index: 0 },
      recognition: null,
      silenceTimer: null,
      networkRetry: false,
      ignoreEnd: false
    };

    var finishAttach = function (forceCommandsOnly) {
      if (forceCommandsOnly) state.commandsOnly = true;
      if (!speechEngineReady()) state.commandsOnly = true;
      ensureBar(state);
      showBar(state);
      applyMicVisibility(state);
      renderChips(state);
      bindFormLifecycle(state);
      active = state;
      if (state.commandsOnly) {
        setHeard(state, isAppleMobileSafari() ? 'iPhone chips mode' : 'Voice engine unavailable');
        setStatus(
          state,
          speechUnavailableReason() || 'Tap chips to test commands (mic hidden on this device/URL)'
        );
      } else {
        setHeard(state, 'Tap mic to speak');
        setStatus(state, 'Try: Edit contact · Help');
      }
    };

    if (navigator.permissions && navigator.permissions.query) {
      try {
        navigator.permissions.query({ name: 'microphone' }).then(function (status) {
          if (!shouldShowVoiceUi()) return;
          if (status.state === 'denied') {
            try { console.warn('[tt-voice-nav] mic permission denied — chips-only mode'); } catch (e) {}
            finishAttach(true);
            return;
          }
          finishAttach(false);
        }).catch(function () { finishAttach(false); });
        active = state;
        return state;
      } catch (e) {}
    }
    finishAttach(false);
    return state;
  }

  function detach() {
    if (!active) return;
    stopListening(active);
    hideBar(active);
    if (active.bar && active.bar.parentNode) {
      active.bar.parentNode.removeChild(active.bar);
    }
    document.body.classList.remove('ttvn-bar-open');
    active = null;
  }

  // Test helpers
  function _parseAndValidateDemo(fieldType, spoken) {
    var field = { type: fieldType, required: true, label: fieldType, id: 'x', keys: [] };
    var value = spoken;
    if (fieldType === 'mobile') value = spokenToDigits(spoken);
    if (fieldType === 'gender') value = parseGender(spoken);
    return validateField(field, value);
  }

  global.TTVoiceNav = {
    attach: attach,
    detach: detach,
    shouldShowVoiceUi: shouldShowVoiceUi,
    speechEngineReady: speechEngineReady,
    voiceFeatureEnabled: voiceFeatureEnabled,
    canUseSpeechNow: canUseSpeechNow,
    handleUtterance: function (text) {
      if (active) handleUtterance(active, text);
    },
    clearSpeechFailureCache: function () {
      try { global.sessionStorage.removeItem(PROBE_KEY); } catch (e) {}
    },
    _validateField: validateField,
    _spokenToDigits: spokenToDigits,
    _parseGender: parseGender,
    _parseAndValidateDemo: _parseAndValidateDemo,
    _active: function () { return active; }
  };
})(typeof window !== 'undefined' ? window : this);
