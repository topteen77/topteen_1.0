/**
 * TopTeen voice navigation + form fill (mobile-first).
 *
 * Visibility gate:
 *   1) Admin VOICE_TO_TEXT_MODE / window.TT_VOICE_TO_TEXT_ENABLED (off hides all)
 *   2) Mic: browser STT when mode=browser; MediaRecorder+OpenAI when mode=openai
 *   3) Chips still show when STT unavailable (commands-only)
 *
 * Mic + green bar + chips when voice is enabled.
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

  function getVoiceMode() {
    try {
      if (global.TTSpeechInput && typeof global.TTSpeechInput.getVoiceMode === 'function') {
        return global.TTSpeechInput.getVoiceMode();
      }
    } catch (e0) {}
    try {
      var mode = String(global.TT_VOICE_TO_TEXT_MODE || '').toLowerCase();
      if (mode === 'off' || mode === 'browser' || mode === 'openai') return mode;
    } catch (e) {}
    try {
      if (typeof global.TT_VOICE_TO_TEXT_ENABLED !== 'undefined' && !global.TT_VOICE_TO_TEXT_ENABLED) {
        return 'off';
      }
    } catch (e2) {}
    return 'browser';
  }

  function isCloudMode() {
    return getVoiceMode() === 'openai';
  }

  function voiceFeatureEnabled() {
    return getVoiceMode() !== 'off';
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

  function canUseMicHardware() {
    if (insecureContextBlocked()) return false;
    try {
      return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    } catch (e) {
      return false;
    }
  }

  function canUseSpeechNow() {
    if (isCloudMode()) return canUseMicHardware();
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
    if (isCloudMode()) {
      if (!canUseMicHardware()) return 'Microphone not available for cloud voice-to-text.';
      return '';
    }
    if (!getSpeechCtor()) {
      if (isAppleMobileSafari()) {
        return 'iPhone Safari has no browser speech-to-text. Switch admin voice mode to OpenAI, or use chips / keyboard mic.';
      }
      return 'This browser has no speech engine. Try Chrome/Edge, or set admin voice mode to OpenAI.';
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
    if (isCloudMode()) return true;
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

  function getCurrentField(state) {
    if (!state.formCtx || !state.formCtx.active || !state.formCtx.cfg) return null;
    var fields = getFormFields(state.formCtx.cfg);
    var idx = state.formCtx.index || 0;
    return fields[idx] || null;
  }

  function isLastField(state) {
    if (!state.formCtx || !state.formCtx.active || !state.formCtx.cfg) return false;
    var fields = getFormFields(state.formCtx.cfg);
    if (!fields.length) return false;
    return (state.formCtx.index || 0) >= fields.length - 1;
  }

  function optionSpeakChips(field) {
    if (!field) return [];
    var el = document.getElementById(field.id);
    if (!el) return [];
    var out = [];
    if (el.tagName === 'SELECT') {
      for (var i = 0; i < el.options.length && out.length < 5; i++) {
        var o = el.options[i];
        if (!o.value) continue;
        var label = String(o.textContent || '').replace(/\s+/g, ' ').trim();
        if (label) out.push(label);
      }
      return out;
    }
    if (el.type === 'radio' || field.type === 'radio') {
      var name = el.name || field.name || field.id;
      var radios = document.querySelectorAll('input[type="radio"][name="' + name + '"]');
      for (var r = 0; r < radios.length && out.length < 5; r++) {
        var lab = '';
        try {
          var id = radios[r].id;
          var labEl = id ? document.querySelector('label[for="' + id + '"]') : null;
          lab = labEl ? labEl.textContent : (radios[r].value || '');
        } catch (e) { lab = radios[r].value || ''; }
        lab = String(lab || '').replace(/\s+/g, ' ').trim();
        if (lab) out.push(lab);
      }
    }
    return out;
  }

  function fieldSpeakHint(field) {
    if (!field) return '';
    if (field.type === 'date') {
      return 'Say date like 15 January 2005 or 15/01/2005';
    }
    if (field.type === 'gender' || field.type === 'select' || field.type === 'radio' || field.type === 'grade') {
      var opts = optionSpeakChips(field);
      if (opts.length) return 'Say one of: ' + opts.slice(0, 4).join(', ');
      return 'Say the option name clearly';
    }
    if (field.type === 'mobile') return 'Say the 10-digit mobile number';
    if (field.type === 'email') return 'Say email like name at gmail dot com';
    return 'Speak the value, then say Next';
  }

  function currentSuggestions(state) {
    if (state.formCtx && state.formCtx.active) {
      // After finishing the last field (said Next), show finish actions only.
      if (state.formCtx.atEnd) {
        return ['Save', 'Cancel', 'Reset', 'Back', 'Help'];
      }
      var chips = isLastField(state)
        ? ['Next', 'Back', 'Save', 'Help']
        : ['Next', 'Back', 'Help'];
      var field = getCurrentField(state);
      var opts = optionSpeakChips(field);
      for (var i = 0; i < opts.length && chips.length < 8; i++) {
        if (chips.indexOf(opts[i]) === -1) chips.push(opts[i]);
      }
      return chips;
    }
    return ['Edit contact', 'Help'];
  }

  function helpText(state) {
    var reason = speechUnavailableReason();
    var iosTip = reason
      ? '<br><br><strong>Why no mic?</strong><br>' + reason
      : '';
    if (state.formCtx && state.formCtx.active) {
      var field = getCurrentField(state);
      var fieldTip = field
        ? '<br><br><strong>This field (' + (field.label || field.id) + ')</strong><br>' + fieldSpeakHint(field)
        : '';
      return [
        '<strong>How to speak</strong>',
        '• Text: say the value, then Next',
        '• Date: “15 January 2005” or “15/01/2005”',
        '• Dropdown / gender / class: say the option (“Male”, “Class 10”)',
        '• Radio: say the choice label',
        '• Or “Gender female”, “Class 10”, “Birthday 15/01/2005”',
        '<br><strong>Navigate</strong>',
        '• Next / Back — move fields',
        '• On last field: Save · Cancel · Reset',
        '• Help — show this list',
        fieldTip,
        iosTip,
        isAppleMobileSafari()
          ? '<br><br>On iPhone: use OpenAI voice mode, chips, or the keyboard mic.'
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

  function stopCloudTracks(state) {
    try {
      if (state.mediaStream) {
        state.mediaStream.getTracks().forEach(function (t) { t.stop(); });
      }
    } catch (e) {}
    state.mediaStream = null;
  }

  function finishCloudListening(state) {
    if (!state) return;
    if (state.silenceTimer) {
      clearTimeout(state.silenceTimer);
      state.silenceTimer = null;
    }
    var chunks = state.cloudChunks || [];
    var mime = (state.mediaRecorder && state.mediaRecorder.mimeType) || 'audio/webm';
    var rec = state.mediaRecorder;
    state.mediaRecorder = null;
    if (rec) {
      try { rec.ondataavailable = rec.onstop = rec.onerror = null; } catch (e0) {}
    }
    stopCloudTracks(state);
    state.cloudChunks = null;
    state.wantListening = false;
    if (state.micBtn) {
      state.micBtn.classList.remove('is-listening');
      var icon = state.micBtn.querySelector('i');
      if (icon) icon.className = 'bx bx-microphone';
    }
    if (!chunks.length) {
      setStatus(state, 'No audio captured. Tap mic to try again.', 'err');
      return;
    }
    var blob = new Blob(chunks, { type: mime });
    setStatus(state, 'Transcribing…');
    var transcribe = global.TTSpeechInput && global.TTSpeechInput.transcribeBlob;
    if (typeof transcribe !== 'function') {
      setStatus(state, 'Cloud voice helper missing. Reload the page.', 'err');
      return;
    }
    transcribe(blob).then(function (text) {
      setProbeCache(true);
      if (!text) {
        setStatus(state, 'No speech detected. Tap mic to try again.', 'err');
        return;
      }
      handleUtterance(state, text);
    }).catch(function (err) {
      try { console.warn('[tt-voice-nav] cloud transcribe failed', err); } catch (e) {}
      setStatus(state, (err && err.message) || 'Transcription failed', 'err');
    });
  }

  function stopListening(state, statusMsg, keepBusy) {
    if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
      state.wantListening = false;
      state.ignoreEnd = true;
      try { state.mediaRecorder.stop(); } catch (e) { finishCloudListening(state); }
      return;
    }
    state.wantListening = false;
    state.ignoreEnd = true;
    if (state.silenceTimer) {
      clearTimeout(state.silenceTimer);
      state.silenceTimer = null;
    }
    destroyRecognition(state);
    stopCloudTracks(state);
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

  function startCloudListening(state) {
    if (!canUseMicHardware() || typeof MediaRecorder === 'undefined') {
      markBroken(state, 'Cloud mic / MediaRecorder unavailable');
      return;
    }
    state.wantListening = true;
    state.ignoreEnd = false;
    state.cloudChunks = [];
    setHeard(state, 'Starting…');
    setStatus(state, 'Allow microphone, then speak');
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      if (!state.wantListening || state.busy) {
        try { stream.getTracks().forEach(function (t) { t.stop(); }); } catch (e) {}
        return;
      }
      state.mediaStream = stream;
      var mime = '';
      try {
        if (global.TTSpeechInput && MediaRecorder.isTypeSupported) {
          if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) mime = 'audio/webm;codecs=opus';
          else if (MediaRecorder.isTypeSupported('audio/mp4')) mime = 'audio/mp4';
          else if (MediaRecorder.isTypeSupported('audio/webm')) mime = 'audio/webm';
        }
      } catch (eMime) {}
      var rec;
      try {
        rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      } catch (eRec) {
        try { stream.getTracks().forEach(function (t) { t.stop(); }); } catch (e2) {}
        markBroken(state, 'MediaRecorder failed');
        return;
      }
      state.mediaRecorder = rec;
      rec.ondataavailable = function (ev) {
        if (ev && ev.data && ev.data.size) state.cloudChunks.push(ev.data);
      };
      rec.onstop = function () { finishCloudListening(state); };
      try { rec.start(250); } catch (eStart) {
        markBroken(state, 'Could not start recorder');
        return;
      }
      setProbeCache(true);
      if (state.micBtn) {
        state.micBtn.classList.add('is-listening');
        var icon = state.micBtn.querySelector('i');
        if (icon) icon.className = 'bx bx-stop-circle';
      }
      setHeard(state, 'Listening…');
      setStatus(state, 'Speak a command — tap mic to stop');
      if (state.silenceTimer) clearTimeout(state.silenceTimer);
      state.silenceTimer = setTimeout(function () {
        state.silenceTimer = null;
        if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
          try { state.mediaRecorder.stop(); } catch (e) {}
        }
      }, Math.max(SILENCE_MS, 8000));
    }).catch(function (err) {
      state.wantListening = false;
      markBroken(state, (err && err.name) || 'mic-denied');
    });
  }

  function startListening(state) {
    if (state.busy || !shouldShowVoiceUi()) return;
    if (!micAllowed(state)) {
      setStatus(state, 'Mic unavailable here — tap a suggestion chip instead.');
      return;
    }
    if (isCloudMode()) {
      startCloudListening(state);
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

  var MONTH_MAP = {
    january: 1, jan: 1, february: 2, feb: 2, march: 3, mar: 3,
    april: 4, apr: 4, may: 5, june: 6, jun: 6, july: 7, jul: 7,
    august: 8, aug: 8, september: 9, sep: 9, sept: 9,
    october: 10, oct: 10, november: 11, nov: 11, december: 12, dec: 12
  };

  var DAY_WORDS = {
    first: 1, second: 2, third: 3, fourth: 4, fifth: 5, sixth: 6, seventh: 7,
    eighth: 8, ninth: 9, tenth: 10, eleventh: 11, twelfth: 12, thirteenth: 13,
    fourteenth: 14, fifteenth: 15, sixteenth: 16, seventeenth: 17, eighteenth: 18,
    nineteenth: 19, twentieth: 20, twenty: 20, thirtieth: 30, thirty: 30
  };

  var GRADE_WORDS = {
    sixth: 6, '6th': 6, seventh: 7, '7th': 7, eighth: 8, '8th': 8,
    ninth: 9, '9th': 9, tenth: 10, '10th': 10, eleventh: 11, '11th': 11,
    twelfth: 12, '12th': 12
  };

  function pad2(n) {
    return ('0' + String(n)).slice(-2);
  }

  function isValidYmd(y, m, d) {
    y = Number(y); m = Number(m); d = Number(d);
    if (!y || m < 1 || m > 12 || d < 1 || d > 31) return false;
    var dt = new Date(y, m - 1, d);
    return dt.getFullYear() === y && dt.getMonth() === m - 1 && dt.getDate() === d;
  }

  function parseSpokenDate(text) {
    var raw = String(text || '').replace(/\s+/g, ' ').trim();
    if (!raw) return '';
    if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw;

    var m = raw.match(/^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{4})$/);
    if (m && isValidYmd(m[3], m[2], m[1])) {
      return m[3] + '-' + pad2(m[2]) + '-' + pad2(m[1]);
    }
    m = raw.match(/^(\d{4})[\/\-.](\d{1,2})[\/\-.](\d{1,2})$/);
    if (m && isValidYmd(m[1], m[2], m[3])) {
      return m[1] + '-' + pad2(m[2]) + '-' + pad2(m[3]);
    }

    var t = norm(raw).replace(/(\d+)(st|nd|rd|th)\b/g, '$1');
    var parts = t.split(' ').filter(Boolean);
    var day = 0;
    var month = 0;
    var year = 0;

    for (var i = 0; i < parts.length; i++) {
      var p = parts[i];
      if (MONTH_MAP[p]) {
        month = MONTH_MAP[p];
        continue;
      }
      if (/^\d{4}$/.test(p)) {
        year = Number(p);
        continue;
      }
      if (/^\d{1,2}$/.test(p)) {
        var num = Number(p);
        if (!day && num >= 1 && num <= 31) day = num;
        else if (!year && String(p).length === 4) year = num;
        continue;
      }
      if (DAY_WORDS[p] && !day) {
        day = DAY_WORDS[p];
        // "twenty first" / "twenty one"
        var nxt = parts[i + 1];
        if ((p === 'twenty' || p === 'thirty') && nxt && DAY_WORDS[nxt] && DAY_WORDS[nxt] < 10) {
          day = (p === 'twenty' ? 20 : 30) + DAY_WORDS[nxt];
          i += 1;
        } else if ((p === 'twenty' || p === 'thirty') && nxt && /^\d$/.test(nxt)) {
          day = (p === 'twenty' ? 20 : 30) + Number(nxt);
          i += 1;
        }
      }
    }

    if (day && month && year && isValidYmd(year, month, day)) {
      return year + '-' + pad2(month) + '-' + pad2(day);
    }
    return '';
  }

  function parseGrade(text) {
    var t = norm(text);
    if (!t) return text;
    if (GRADE_WORDS[t] != null) return String(GRADE_WORDS[t]);
    var m = t.match(/\b(?:class|grade|std|standard)?\s*([6-9]|1[0-2]|6th|7th|8th|9th|10th|11th|12th)\b/);
    if (m) {
      var g = m[1];
      if (GRADE_WORDS[g] != null) return String(GRADE_WORDS[g]);
      return String(parseInt(g, 10));
    }
    for (var key in GRADE_WORDS) {
      if (Object.prototype.hasOwnProperty.call(GRADE_WORDS, key) && t.indexOf(key) !== -1) {
        return String(GRADE_WORDS[key]);
      }
    }
    return text;
  }

  function parseGender(text) {
    var t = norm(text);
    if (/\b(female|girl|woman)\b/.test(t)) return 'Female';
    if (/\b(male|boy|man)\b/.test(t) && !/female/.test(t)) return 'Male';
    if (/\b(trans|transgender)\b/.test(t)) return 'Transgender';
    return text;
  }

  function normalizeFillValue(field, value) {
    if (!field) return value;
    if (field.type === 'date') {
      return parseSpokenDate(value) || String(value || '').trim();
    }
    if (field.type === 'gender') return parseGender(value);
    if (field.type === 'grade') return parseGrade(value);
    if (field.type === 'mobile') return spokenToDigits(value);
    return value;
  }

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
      var iso = parseSpokenDate(v);
      if (!iso) {
        return {
          ok: false,
          message: 'Say date like 15 January 2005 or 15/01/2005, or pick it on screen.'
        };
      }
      return { ok: true, value: iso };
    }
    if (field.type === 'gender') {
      var g = parseGender(v);
      if (!/^(male|female|transgender)$/i.test(g)) {
        return { ok: false, message: 'Say Male, Female, or Transgender.' };
      }
      return { ok: true, value: g };
    }
    if (field.type === 'grade') {
      var gr = parseGrade(v);
      if (!/^(6|7|8|9|10|11|12)$/.test(String(gr))) {
        return { ok: false, message: 'Say Class 6 to Class 12 (e.g. Class 10).' };
      }
      return { ok: true, value: String(gr) };
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
    if (state.formCtx) {
      state.formCtx.index = getFormFields(state.formCtx.cfg).indexOf(field);
      state.formCtx.atEnd = false;
    }
    var hint = fieldSpeakHint(field);
    var last = isLastField(state);
    setStatus(
      state,
      'Editing ' + (field.label || field.id) +
        (hint ? ' — ' + hint : '') +
        (last ? ' · Last field: say Save, Cancel, or Reset' : '')
    );
    renderChips(state);
  }

  function matchSelectOption(el, value, field) {
    var want = norm(value);
    var opts = el.options;
    var matched = null;
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
    if (!matched) {
      for (var i2 = 0; i2 < opts.length; i2++) {
        var o2 = opts[i2];
        var label2 = norm(o2.textContent);
        if (!o2.value && !label2) continue;
        if (want && label2.indexOf(want) !== -1) {
          matched = o2;
          break;
        }
      }
    }
    if (!matched && (field.type === 'grade' || field.type === 'select')) {
      var g = want.replace(/\b(class|grade|std|standard)\b/g, '').trim();
      for (var j = 0; j < opts.length; j++) {
        var gl = norm(opts[j].textContent);
        var gv = String(opts[j].value || '');
        if (!gv && !gl) continue;
        if (gl === g || gv === g || gl.indexOf(g) !== -1 || ('class ' + g) === gl) {
          matched = opts[j];
          break;
        }
      }
    }
    return matched;
  }

  function setFieldValue(field, value) {
    var el = document.getElementById(field.id);
    if (!el) return false;

    // Radio group: field.id is one radio, or field.name is the group name
    if (el.type === 'radio' || field.type === 'radio') {
      var name = el.name || field.name || field.id;
      var want = norm(value);
      var radios = document.querySelectorAll('input[type="radio"][name="' + name + '"]');
      var hit = null;
      for (var r = 0; r < radios.length; r++) {
        var radio = radios[r];
        var lab = '';
        try {
          var labEl = radio.id ? document.querySelector('label[for="' + radio.id + '"]') : null;
          if (!labEl) labEl = radio.closest('label');
          lab = labEl ? labEl.textContent : '';
        } catch (eLab) {}
        var l = norm(lab);
        var v = norm(radio.value);
        if (l === want || v === want || (want && l.indexOf(want) !== -1)) {
          hit = radio;
          break;
        }
      }
      if (!hit) return false;
      hit.checked = true;
      try {
        hit.dispatchEvent(new Event('input', { bubbles: true }));
        hit.dispatchEvent(new Event('change', { bubbles: true }));
        var tab = hit.closest('.profile-choice-tab');
        if (tab) tab.click();
      } catch (eRadio) {}
      return true;
    }

    if (el.tagName === 'SELECT') {
      var matched = matchSelectOption(el, value, field);
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
    // Prefer longer keys first so "date of birth" wins over "date"
    var ranked = [];
    for (var i = 0; i < fields.length; i++) {
      var f = fields[i];
      var keys = f.keys || [];
      for (var k = 0; k < keys.length; k++) {
        ranked.push({ field: f, key: norm(keys[k]) });
      }
    }
    ranked.sort(function (a, b) { return b.key.length - a.key.length; });
    for (var r = 0; r < ranked.length; r++) {
      var key = ranked[r].key;
      if (!key) continue;
      if (t === key || t.indexOf(key + ' ') === 0 || t.indexOf(key + ':') === 0) {
        var re = new RegExp('^' + key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '[\\s:]+', 'i');
        var rest = raw.replace(re, '').trim();
        return { field: ranked[r].field, rest: rest };
      }
    }
    return null;
  }

  function resumeListeningSoon(state) {
    if (!state || state.commandsOnly || !micAllowed(state)) return;
    if (state._resumeTimer) {
      clearTimeout(state._resumeTimer);
      state._resumeTimer = null;
    }
    state._resumeTimer = setTimeout(function () {
      state._resumeTimer = null;
      if (!state || state.busy || state.wantListening) return;
      if (!shouldShowVoiceUi() || !micAllowed(state)) return;
      setHeard(state, 'Listening…');
      setStatus(state, 'Speak mode on — pause to stop if you don’t speak');
      startListening(state);
    }, 450);
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
      // After a command, turn speak mode back on; silence / no speech turns it off.
      resumeListeningSoon(state);
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
      index: 0,
      atEnd: false
    };
    var fields = getFormFields(formCfg);
    if (fields[0]) focusField(state, fields[0]);
    else renderChips(state);
    if (state.helpEl) state.helpEl.classList.remove('is-open');
    resumeListeningSoon(state);
  }

  function deactivateForm(state) {
    state.formCtx = { active: false, cfg: null, index: 0, atEnd: false };
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

    if (t === 'reset' || t === 'clear' || t === 'clear form' || t === 'start over') {
      runCommand(state, function (done) {
        var form = cfg.form ? document.querySelector(cfg.form) : null;
        if (form && typeof form.reset === 'function') {
          form.reset();
          try {
            form.dispatchEvent(new Event('change', { bubbles: true }));
          } catch (eReset) {}
        }
        state.formCtx.atEnd = false;
        var fieldsReset = getFormFields(cfg);
        if (fieldsReset[0]) focusField(state, fieldsReset[0]);
        done('Form reset. Start from the first field.');
      }, 'Resetting…');
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
        if (state.formCtx.atEnd) {
          done('Already at the end. Say Save, Cancel, or Reset.');
          return 'async';
        }
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
        if (idx >= fields.length - 1) {
          state.formCtx.atEnd = true;
          renderChips(state);
          done('Last field done. Say Save, Cancel, or Reset.');
          return 'async';
        }
        var next = fields[idx + 1];
        if (next) focusField(state, next);
        var msg = 'Moved to ' + (next.label || next.id);
        if (isLastField(state)) {
          msg += '. Last field — after this say Save, Cancel, or Reset.';
        } else {
          msg += '. ' + fieldSpeakHint(next);
        }
        done(msg);
      }, 'Next field…');
      return;
    }

    if (t === 'back' || t === 'previous' || t === 'previous field') {
      runCommand(state, function (done) {
        if (state.formCtx.atEnd) {
          state.formCtx.atEnd = false;
          var last = fields[fields.length - 1];
          if (last) focusField(state, last);
          done('Back to ' + ((last && last.label) || 'last field'));
          return 'async';
        }
        var idx = state.formCtx.index || 0;
        var prev = fields[Math.max(idx - 1, 0)];
        if (prev) focusField(state, prev);
        done(prev ? ('Moved to ' + (prev.label || prev.id) + '. ' + fieldSpeakHint(prev)) : 'First field');
      }, 'Previous field…');
      return;
    }

    // Field-targeted fill: "name Rahul" / "mobile 987..." / "birthday 15 january 2005"
    var hit = findFieldByAlias(fields, text);
    if (hit && hit.rest) {
      runCommand(state, function (done) {
        var value = normalizeFillValue(hit.field, hit.rest);
        var check = validateField(hit.field, value);
        if (!check.ok) {
          focusField(state, hit.field);
          done(check.message, 'err');
          return 'async';
        }
        var ok = setFieldValue(hit.field, check.value);
        if (!ok) {
          done(
            'Could not set ' + (hit.field.label || 'field') + '. ' + fieldSpeakHint(hit.field),
            'err'
          );
          return 'async';
        }
        focusField(state, hit.field);
        var el = document.getElementById(hit.field.id);
        if (el) el.classList.remove('is-invalid');
        var nextHint = isLastField(state)
          ? 'Say Next for Save/Cancel/Reset, or Save now.'
          : 'Say Next to continue.';
        done((hit.field.label || 'Field') + ' updated. ' + nextHint);
      }, 'Filling…');
      return;
    }

    // Bare value for the current field (date / select / radio / text)
    var curField = fields[state.formCtx.index || 0];
    if (curField && !state.formCtx.atEnd) {
      // Only auto-fill current field if it doesn't look like a navigation command
      if (!/^(next|back|save|cancel|reset|clear|help|close)/.test(t)) {
        runCommand(state, function (done) {
          var fillVal = normalizeFillValue(curField, text);
          var check = validateField(curField, fillVal);
          if (!check.ok) {
            var elBad = document.getElementById(curField.id);
            if (elBad) elBad.classList.add('is-invalid');
            done(check.message + ' ' + fieldSpeakHint(curField), 'err');
            return 'async';
          }
          if (!setFieldValue(curField, check.value)) {
            done(
              'Could not set ' + (curField.label || 'field') + '. ' + fieldSpeakHint(curField),
              'err'
            );
            return 'async';
          }
          var elOk = document.getElementById(curField.id);
          if (elOk) elOk.classList.remove('is-invalid');
          var nextMsg = isLastField(state)
            ? 'Say Next for Save/Cancel/Reset, or Save now.'
            : 'Say Next to continue.';
          done((curField.label || 'Field') + ' set. ' + nextMsg);
        }, 'Filling…');
        return;
      }
    }

    setStatus(
      state,
      state.formCtx.atEnd || isLastField(state)
        ? 'Try Save, Cancel, Reset, Back, or Help.'
        : 'Didn’t catch that. Try Next, or say Help for how to speak.',
      'err'
    );
    if (state.helpEl) {
      state.helpEl.innerHTML = helpText(state);
      state.helpEl.classList.add('is-open');
    }
    resumeListeningSoon(state);
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
              ? 'Safari has no web speech mic — tap Next/Save, or use chips'
              : (speechUnavailableReason() || 'Mic unavailable — tap Next, Save, or Help')
          );
        }
        // When mic works, activateForm already resumes speak mode + field hint.
      });
      modal.addEventListener('hidden.bs.modal', function () {
        if (state.formCtx && state.formCtx.cfg === formCfg) {
          if (state._resumeTimer) {
            clearTimeout(state._resumeTimer);
            state._resumeTimer = null;
          }
          stopListening(state);
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
        console.warn('[tt-voice-nav] UI hidden — admin VOICE_TO_TEXT_MODE=off');
      } catch (e) {}
      return null;
    }

    var state = {
      config: config || {},
      busy: false,
      wantListening: false,
      commandsOnly: !speechEngineReady(),
      formCtx: { active: false, cfg: null, index: 0, atEnd: false },
      recognition: null,
      _resumeTimer: null,
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
    if (active._resumeTimer) {
      clearTimeout(active._resumeTimer);
      active._resumeTimer = null;
    }
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
    if (fieldType === 'date') value = parseSpokenDate(spoken) || spoken;
    if (fieldType === 'grade') value = parseGrade(spoken);
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
    _parseSpokenDate: parseSpokenDate,
    _parseGrade: parseGrade,
    _parseAndValidateDemo: _parseAndValidateDemo,
    _active: function () { return active; }
  };
})(typeof window !== 'undefined' ? window : this);
