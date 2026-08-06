/**
 * TopTeen site-wide Voice widget (FAB + panel + status bar).
 * Admin flags via GET /api/voice/settings/ (live). Forms via TTVoiceNav headless.
 */
(function (global) {
  'use strict';

  var PREF_NAV = 'tt_voice_nav';
  var PREF_TALK = 'tt_voice_talk_type';
  var PREF_SR = 'tt_voice_screen_reader';
  var PREF_LISTEN = 'tt_voice_nav_listen';
  var PREF_CUES = 'tt_voice_nav_cues';
  var SILENCE_MS = 5000;
  var EXCLUDE_PREFIXES = ['/psychometric/', '/api/web/take_test/', '/api/web/test/'];

  var state = {
    mounted: false,
    settings: null,
    navOn: false,
    talkOn: false,
    screenReaderOn: false,
    voiceCuesOn: true,
    speaking: false,
    listening: false,
    paused: false,
    wantListen: false,
    busy: false,
    micDenied: false,
    panelOpen: false,
    linkNumbersOn: false,
    numberedLinks: [],
    recognition: null,
    mediaRecorder: null,
    mediaStream: null,
    cloudChunks: null,
    silenceTimer: null,
    ignoreEnd: false,
    formsRegistered: false,
    resumeTimer: null,
    uiPhase: '',
    cueToken: 0,
    cueSpeaking: false,
    lastCuePhase: '',
    lastCueAt: 0,
    skipNextSpeakCue: false,
    lastHelpContextKey: '',
    awaitLoginField: null,
    _ctxObserver: null,
    _ctxRefreshTimer: null,
    els: {}
  };

  function pathExcluded() {
    try {
      var p = (global.location && global.location.pathname) || '';
      for (var i = 0; i < EXCLUDE_PREFIXES.length; i++) {
        if (p.indexOf(EXCLUDE_PREFIXES[i]) === 0) return true;
      }
    } catch (e) {}
    return false;
  }

  function getPref(key, fallback) {
    try {
      var v = global.localStorage.getItem(key);
      if (v === '1' || v === 'true') return true;
      if (v === '0' || v === 'false') return false;
    } catch (e) {}
    return fallback;
  }

  function setPref(key, on) {
    try { global.localStorage.setItem(key, on ? '1' : '0'); } catch (e) {}
  }

  function adminAllowsWidget() {
    var s = state.settings;
    var mode = (s && s.mode) || global.TT_VOICE_TO_TEXT_MODE || 'browser';
    if (String(mode).toLowerCase() === 'off') return false;
    if (s && typeof s.enabled !== 'undefined' && s.enabled === false) return false;
    if (s && typeof s.widget_enabled !== 'undefined') return !!s.widget_enabled;
    return global.TT_VOICE_WIDGET_ENABLED !== false;
  }

  function adminAllowsNav() {
    var s = state.settings;
    if (s && typeof s.nav_enabled !== 'undefined') return !!s.nav_enabled;
    return global.TT_VOICE_NAV_ENABLED !== false;
  }

  function adminAllowsTalk() {
    var s = state.settings;
    if (s && typeof s.talk_type_enabled !== 'undefined') return !!s.talk_type_enabled;
    return global.TT_VOICE_TALK_TYPE_ENABLED !== false;
  }

  function adminAllowsLinkNumbers() {
    var s = state.settings;
    if (s && typeof s.link_numbers_enabled !== 'undefined') return !!s.link_numbers_enabled;
    return global.TT_VOICE_LINK_NUMBERS_ENABLED !== false;
  }

  function modeLabel() {
    var mode = (state.settings && state.settings.mode) || global.TT_VOICE_TO_TEXT_MODE || 'browser';
    if (mode === 'openai') return 'OpenAI';
    if (mode === 'off') return 'Off';
    return 'Browser';
  }

  function getSpeechCtor() {
    try { return global.SpeechRecognition || global.webkitSpeechRecognition || null; } catch (e) { return null; }
  }

  function insecure() {
    try {
      if (global.isSecureContext !== false) return false;
      var h = (global.location && global.location.hostname) || '';
      if (h === 'localhost' || h === '127.0.0.1' || h === '::1' || h.endsWith('.localhost')) return false;
      if (/^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[0-1])\.)/.test(h)) return false;
      return true;
    } catch (e) {
      return false;
    }
  }

  function canMicHardware() {
    try { return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia); } catch (e) { return false; }
  }

  function isCloud() {
    var mode = (state.settings && state.settings.mode) || global.TT_VOICE_TO_TEXT_MODE || '';
    return String(mode).toLowerCase() === 'openai';
  }

  function canListen() {
    if (state.micDenied) return false;
    if (isCloud()) return canMicHardware() && !insecure();
    return !!getSpeechCtor() && !insecure();
  }

  function syncBottomStack() {
    if (global.TTVoiceNav && typeof global.TTVoiceNav.syncBottomStack === 'function') {
      return global.TTVoiceNav.syncBottomStack();
    }
    var offset = 0;
    try {
      var cookie = document.getElementById('eu-cookie-consent');
      if (cookie) {
        var style = global.getComputedStyle ? getComputedStyle(cookie) : null;
        var visible = style ? style.display !== 'none' : (cookie.style.display !== 'none');
        if (visible && cookie.offsetHeight) offset = cookie.offsetHeight;
      }
      document.documentElement.style.setProperty('--tt-bottom-stack', offset + 'px');
    } catch (e) {}
    return offset;
  }

  function setListenIntent(on) {
    try {
      global.sessionStorage.setItem(PREF_LISTEN, on ? '1' : '0');
    } catch (e) {}
  }

  function getListenIntent() {
    try {
      return global.sessionStorage.getItem(PREF_LISTEN) === '1';
    } catch (e) {
      return false;
    }
  }

  function inferPromptPhase(text, kind) {
    if (kind === 'paused' || kind === 'err' || kind === 'speak' || kind === 'wait' ||
        kind === 'ready' || kind === 'understood') {
      return kind;
    }
    var t = String(text || '').toLowerCase();
    if (/^got it|^understood|heard you/.test(t)) return 'understood';
    if (/speak now|listening|allow microphone|say a command|your turn/.test(t)) return 'speak';
    if (/processing|transcribing|wait|opening|working|resuming|loading|one moment/.test(t)) return 'wait';
    if (/paused|mic (is )?off|mic paused/.test(t)) return 'paused';
    if (/error|failed|not available|unavailable|denied|could not|try help/.test(t)) return 'err';
    return 'ready';
  }

  function promptCopy(phase) {
    if (phase === 'speak') {
      return {
        badge: 'SPEAK NOW',
        title: 'Your turn — Speak now',
        hint: 'Mic is on. Say a command, or tap a button below.',
        micOn: true,
        micLabel: 'Microphone on',
        icon: 'bx-microphone',
        tone: 'speak'
      };
    }
    if (phase === 'understood') {
      return {
        badge: 'GOT IT',
        title: 'Understood',
        hint: 'We heard you — working on it next.',
        micOn: false,
        micLabel: 'Microphone off',
        icon: 'bx-check-circle',
        tone: 'understood'
      };
    }
    if (phase === 'wait') {
      return {
        badge: 'PROCESSING',
        title: 'Processing…',
        hint: 'Please wait — mic is paused. You can still tap a command button.',
        micOn: false,
        micLabel: 'Microphone off',
        icon: 'bx-loader-alt',
        tone: 'wait'
      };
    }
    if (phase === 'paused') {
      return {
        badge: 'MIC OFF',
        title: 'Mic paused',
        hint: 'Tap Start listening, or say “Start listening”.',
        micOn: false,
        micLabel: 'Microphone off',
        icon: 'bx-microphone-off',
        tone: 'paused'
      };
    }
    if (phase === 'err') {
      return {
        badge: 'TRY AGAIN',
        title: 'Something went wrong',
        hint: 'Try another command, or tap Start listening.',
        micOn: false,
        micLabel: 'Microphone unavailable',
        icon: 'bx-error-circle',
        tone: 'err'
      };
    }
    return {
      badge: 'MIC OFF',
      title: 'Ready when you are',
      hint: 'Tap Start listening to begin, then speak or use the buttons.',
      micOn: false,
      micLabel: 'Microphone off',
      icon: 'bx-microphone-off',
      tone: 'ready'
    };
  }

  function setBarStatus(text, kind, silent) {
    var el = state.els.status;
    var phase = inferPromptPhase(text, kind);
    var copy = promptCopy(phase);
    var statusText = text || copy.title;
    // Prefer friendly titles for core phases when callers pass short flags
    if (phase === 'speak' && (!text || /^speak now$/i.test(text))) {
      statusText = copy.title;
    } else if (phase === 'wait' && (!text || /^(processing|wait)/i.test(text))) {
      statusText = copy.title;
    } else if (phase === 'understood' && (!text || /^(got it|understood)$/i.test(text))) {
      statusText = text && /[“"]/.test(text) ? text : copy.title;
    }
    if (el) {
      el.textContent = statusText;
      el.classList.toggle('is-paused', phase === 'paused');
      el.classList.toggle('is-err', phase === 'err');
      el.classList.toggle('is-speak', phase === 'speak');
      el.classList.toggle('is-wait', phase === 'wait');
      el.classList.toggle('is-understood', phase === 'understood');
      el.classList.toggle('is-ready', phase === 'ready');
    }
    if (state.els.promptBadge) {
      state.els.promptBadge.innerHTML =
        '<i class="bx ' + copy.icon + (phase === 'wait' ? ' ttvw-spin' : '') +
        '" aria-hidden="true"></i><span>' + copy.badge + '</span>';
    }
    if (state.els.micIcon) {
      state.els.micIcon.className =
        'ttvw-mic-icon ' + (copy.micOn ? 'is-on' : 'is-off') +
        ' is-' + phase;
      state.els.micIcon.setAttribute('aria-label', copy.micLabel);
      state.els.micIcon.title = copy.micLabel;
      state.els.micIcon.innerHTML =
        '<i class="bx ' + copy.icon + (phase === 'wait' ? ' ttvw-spin' : '') +
        '" aria-hidden="true"></i>';
    }
    if (state.els.promptHint) state.els.promptHint.textContent = copy.hint;
    if (state.els.prompt) {
      state.els.prompt.className =
        'ttvw-bar-prompt is-' + phase + (copy.micOn ? ' mic-on' : ' mic-off');
    }
    if (state.els.bar) {
      state.els.bar.classList.toggle('is-speak', phase === 'speak');
      state.els.bar.classList.toggle('is-wait', phase === 'wait');
      state.els.bar.classList.toggle('is-understood', phase === 'understood');
      state.els.bar.classList.toggle('is-paused-phase', phase === 'paused');
      state.els.bar.classList.toggle('mic-on', !!copy.micOn);
      state.els.bar.classList.toggle('mic-off', !copy.micOn);
    }
    syncStartListeningButtons();
    if (!silent) announceVoiceCue(phase);
    else state.uiPhase = phase;
  }

  function canSpeakVoiceCues() {
    if (!state.navOn || !state.voiceCuesOn) return false;
    try {
      return !!(global.speechSynthesis && global.SpeechSynthesisUtterance);
    } catch (e) {
      return false;
    }
  }

  function spokenLineForPhase(phase) {
    if (phase === 'speak') return 'Speak now.';
    if (phase === 'understood') return 'Got it.';
    if (phase === 'wait') return 'Processing.';
    if (phase === 'paused') return 'Microphone paused.';
    if (phase === 'err') return 'Please try again.';
    return '';
  }

  function stopVoiceCue() {
    state.cueToken += 1;
    state.cueSpeaking = false;
    try {
      if (global.speechSynthesis) global.speechSynthesis.cancel();
    } catch (e) {}
  }

  function announceVoiceCue(phase) {
    var prev = state.uiPhase;
    state.uiPhase = phase;
    if (!canSpeakVoiceCues()) return;
    if (prev === phase && phase !== 'understood') return;

    // Screen Reader reading page aloud — don't interrupt with short cues
    try {
      if (state.screenReaderOn && global.TTScreenReader &&
          typeof global.TTScreenReader.isSpeaking === 'function' &&
          global.TTScreenReader.isSpeaking()) {
        return;
      }
    } catch (eSr) {}

    if (phase === 'speak' && state.skipNextSpeakCue) {
      state.skipNextSpeakCue = false;
      return;
    }

    // After "Got it", skip saying "Processing" — visual wait is enough
    if (phase === 'wait' && state.lastCuePhase === 'understood' &&
        (Date.now() - state.lastCueAt) < 1500) {
      return;
    }

    // Avoid repeating Speak now on every recognition restart
    if (phase === 'speak' && state.lastCuePhase === 'speak' &&
        (Date.now() - state.lastCueAt) < 2200) {
      return;
    }

    var line = spokenLineForPhase(phase);
    if (!line) return;

    stopVoiceCue();
    var token = state.cueToken;
    state.lastCuePhase = phase;
    state.lastCueAt = Date.now();
    state.cueSpeaking = true;

    // Only pause the mic when we are actually about to speak a cue.
    // (Previously early-returns could leave UI as SPEAK NOW with mic already dead.)
    if (phase === 'speak' && state.wantListen) {
      state.ignoreEnd = true;
      try { destroyRecognition(); } catch (eD) {}
      try { stopCloudTracks(); } catch (eC) {}
      state.listening = false;
      syncFabListening();
      syncStartListeningButtons();
    }

    var u = new SpeechSynthesisUtterance(line);
    u.lang = navigator.language || 'en-IN';
    u.rate = 1.08;
    u.pitch = 1;
    u.volume = 1;

    function afterCue() {
      if (token !== state.cueToken) return;
      state.cueSpeaking = false;
      if (phase === 'speak' && state.wantListen && state.navOn && !state.busy && !state.paused) {
        state.skipNextSpeakCue = true;
        try { startListeningNow(); } catch (eStart) {}
      }
    }
    u.onend = afterCue;
    u.onerror = afterCue;

    try {
      global.speechSynthesis.resume();
    } catch (eR) {}
    try {
      global.speechSynthesis.speak(u);
      // Safety if onend never fires (Chrome + modal focus often stalls TTS)
      setTimeout(function () {
        if (token !== state.cueToken) return;
        if (state.cueSpeaking) afterCue();
      }, Math.min(2800, 700 + line.length * 70));
    } catch (eSpeak) {
      afterCue();
    }
  }

  function setVoiceCuesOn(on) {
    state.voiceCuesOn = !!on;
    setPref(PREF_CUES, state.voiceCuesOn);
    if (!state.voiceCuesOn) stopVoiceCue();
    if (state.els.cuesToggle) state.els.cuesToggle.checked = state.voiceCuesOn;
  }

  function setHeard(text) {
    if (state.els.heard) {
      state.els.heard.textContent = text || '';
      state.els.heard.classList.toggle('is-empty', !text);
    }
  }

  function syncFabListening() {
    if (state.els.fab) {
      state.els.fab.classList.toggle('is-listening', !!state.listening);
    }
  }

  function updateAdminLine() {
    if (!state.els.adminLine) return;
    state.els.adminLine.textContent =
      'Admin: ' + modeLabel() +
      ' · Nav ' + (adminAllowsNav() ? 'on' : 'off') +
      ' · Talk ' + (adminAllowsTalk() ? 'on' : 'off') +
      (adminAllowsLinkNumbers() ? ' · Link#' : '') +
      ' · SR ' + (state.screenReaderOn ? 'on' : 'off');
  }

  function canScreenReader() {
    if (global.TTScreenReader && typeof global.TTScreenReader.canSpeak === 'function') {
      return !!global.TTScreenReader.canSpeak();
    }
    try { return !!(global.speechSynthesis && global.SpeechSynthesisUtterance); } catch (e) { return false; }
  }

  function stopScreenReader() {
    if (global.TTScreenReader && typeof global.TTScreenReader.stop === 'function') {
      try { global.TTScreenReader.stop(); } catch (e) {}
    } else {
      try { if (global.speechSynthesis) global.speechSynthesis.cancel(); } catch (e2) {}
    }
    state.speaking = false;
    syncScreenReaderUi();
  }

  function toggleScreenReaderSpeak() {
    if (!state.screenReaderOn || !canScreenReader()) return;
    if (global.TTScreenReader && typeof global.TTScreenReader.toggle === 'function') {
      var started = global.TTScreenReader.toggle();
      state.speaking = !!global.TTScreenReader.isSpeaking();
      syncScreenReaderUi();
      return started;
    }
    // Fallback: should not normally run
    if (state.speaking || (global.speechSynthesis && global.speechSynthesis.speaking)) {
      stopScreenReader();
      return;
    }
  }

  function syncScreenReaderUi() {
    if (global.TTScreenReader && typeof global.TTScreenReader.isSpeaking === 'function') {
      state.speaking = !!global.TTScreenReader.isSpeaking();
    }
    if (global.TTScreenReader && typeof global.TTScreenReader.isEnabled === 'function') {
      state.screenReaderOn = !!global.TTScreenReader.isEnabled();
    }
    var on = !!state.screenReaderOn && canScreenReader();
    if (state.els.srToggle) {
      state.els.srToggle.checked = !!state.screenReaderOn;
      state.els.srToggle.disabled = !canScreenReader();
      if (state.els.srRow) state.els.srRow.classList.toggle('is-disabled', !canScreenReader());
    }
    if (state.els.srControls) {
      state.els.srControls.hidden = !on;
    }
    var rate = 1;
    var vol = 1;
    if (global.TTScreenReader) {
      if (typeof global.TTScreenReader.getRate === 'function') rate = global.TTScreenReader.getRate();
      if (typeof global.TTScreenReader.getVolume === 'function') vol = global.TTScreenReader.getVolume();
    }
    if (state.els.srRate) state.els.srRate.value = String(rate);
    if (state.els.srVol) state.els.srVol.value = String(vol);
    if (state.els.srRateVal) {
      state.els.srRateVal.textContent = (Math.round(rate * 100) / 100).toFixed(2) + 'x';
    }
    if (state.els.srVolVal) {
      state.els.srVolVal.textContent = Math.round(vol * 100) + '%';
    }
    if (state.els.srBtn) {
      state.els.srBtn.hidden = !on;
      state.els.srBtn.setAttribute('aria-hidden', on ? 'false' : 'true');
      state.els.srBtn.classList.toggle('is-speaking', !!state.speaking);
      state.els.srBtn.setAttribute('aria-pressed', state.speaking ? 'true' : 'false');
      state.els.srBtn.title = state.speaking
        ? 'Stop reading'
        : 'Read selection or page aloud';
      state.els.srBtn.setAttribute(
        'aria-label',
        state.speaking ? 'Stop reading' : 'Read selection or page aloud'
      );
      var icon = state.els.srBtn.querySelector('i');
      if (icon) icon.className = state.speaking ? 'bx bx-stop-circle' : 'bx bx-volume-full';
    }
  }

  function setScreenReaderOn(on) {
    state.screenReaderOn = !!on && canScreenReader();
    setPref(PREF_SR, state.screenReaderOn);
    if (global.TTScreenReader && typeof global.TTScreenReader.setEnabled === 'function') {
      global.TTScreenReader.setEnabled(state.screenReaderOn);
    }
    if (!state.screenReaderOn) stopScreenReader();
    else syncScreenReaderUi();
    updateAdminLine();
  }

  function updateMicAvailabilityUi() {
    var ok = canListen();
    if (state.els.fab) {
      state.els.fab.classList.toggle('is-mic-unavailable', !ok);
      state.els.fab.setAttribute('title', ok ? 'Voice' : 'Mic not available');
      state.els.fab.setAttribute('aria-label', ok ? 'Voice controls' : 'Mic not available');
    }
    // Mic off → never show / keep Voice Navigation bar
    if (!ok) {
      if (state.navOn) {
        state.navOn = false;
        setPref(PREF_NAV, false);
        setListenIntent(false);
        if (state.els.navToggle) state.els.navToggle.checked = false;
      }
      stopListening(true);
      hideBar();
    }
    if (state.els.navToggle) {
      state.els.navToggle.disabled = !ok || !adminAllowsNav();
      state.els.navRow.classList.toggle('is-disabled', !ok || !adminAllowsNav());
    }
    syncStartListeningButtons();
    hideEngineNavBar();
  }

  function applyVisibility(opts) {
    opts = opts || {};
    var soft = !!opts.soft; // settings poll — update flags/UI only, don't restart mic
    var show = !pathExcluded() && adminAllowsWidget();
    if (state.els.wrap) state.els.wrap.classList.toggle('is-on', show);
    syncFabStackClass();
    if (!show) {
      stopListening(true);
      hideBar();
      hideLinkNumbers();
      if (state.els.panel) state.els.panel.classList.remove('is-open');
      state.panelOpen = false;
      return;
    }
    // Resolve user prefs against admin
    var navDefault = !!(state.settings && state.settings.nav_default_on) || !!global.TT_VOICE_NAV_DEFAULT_ON;
    var talkDefault = !!(state.settings && state.settings.talk_type_default_on) || !!global.TT_VOICE_TALK_TYPE_DEFAULT_ON;
    var micOk = canListen();
    state.navOn = micOk && adminAllowsNav() && getPref(PREF_NAV, navDefault);
    state.talkOn = adminAllowsTalk() && getPref(PREF_TALK, talkDefault);
    state.screenReaderOn = canScreenReader() && getPref(PREF_SR, false);
    state.voiceCuesOn = getPref(PREF_CUES, true);
    if (global.TTScreenReader && typeof global.TTScreenReader.setEnabled === 'function') {
      try { global.TTScreenReader.setEnabled(state.screenReaderOn); } catch (eSr) {}
    }
    if (state.els.navToggle) {
      state.els.navToggle.checked = state.navOn;
      state.els.navToggle.disabled = !micOk || !adminAllowsNav();
      state.els.navRow.classList.toggle('is-disabled', !micOk || !adminAllowsNav());
    }
    if (state.els.cuesToggle) {
      state.els.cuesToggle.checked = !!state.voiceCuesOn;
      if (state.els.cuesRow) {
        state.els.cuesRow.classList.toggle('is-disabled', !state.navOn);
        state.els.cuesToggle.disabled = !state.navOn;
      }
    }
    if (state.els.talkToggle) {
      state.els.talkToggle.checked = state.talkOn;
      state.els.talkRow.classList.toggle('is-disabled', !adminAllowsTalk());
    }
    syncScreenReaderUi();
    try {
      if (typeof global.TT_VOICE_TALK_TYPE_DEFAULT_ON === 'undefined') {
        global.TT_VOICE_TALK_TYPE_DEFAULT_ON = talkDefault;
      }
    } catch (e) {}
    if (global.TTSpeechInput && typeof global.TTSpeechInput.enhance === 'function') {
      try { global.TTSpeechInput.enhance(document); } catch (eEnh) {}
    }
    updateAdminLine();
    updateMicAvailabilityUi();
    hideEngineNavBar();

    // Soft update: never interrupt an active Speak-now / processing cycle
    if (soft) {
      if (!state.navOn) {
        hideBar();
        stopListening(true);
        hideLinkNumbers();
      } else if (state.wantListen || getListenIntent()) {
        showBar();
      }
      syncStartListeningButtons();
      return;
    }

    if (state.navOn && micOk) {
      // Keep listening across page loads when user left mic “want listen” on
      if (getListenIntent()) {
        state.wantListen = true;
        state.paused = false;
        showBar();
        scheduleResumeListening('Page loaded — resuming Speak now…');
      } else {
        state.wantListen = false;
        state.paused = true;
        showBar();
        setBarStatus('Mic paused — tap Start listening when ready', 'paused');
      }
    } else {
      hideBar();
      stopListening(true);
      hideLinkNumbers();
    }
    syncStartListeningButtons();
  }

  function syncFabStackClass() {
    try {
      var hasChat = !!document.getElementById('cb-fab-wrap');
      document.body.classList.toggle('ttvw-with-chatbot', hasChat);
    } catch (e) {}
  }

  function showBar() {
    if (!state.els.bar) return;
    if (!canListen() || !state.navOn) {
      hideBar();
      updateMicAvailabilityUi();
      return;
    }
    hideEngineNavBar();
    syncBottomStack();
    syncFabStackClass();
    state.els.bar.classList.add('is-on');
    document.body.classList.add('ttvw-bar-open');
    refreshNavHelpUi();
    updateMicAvailabilityUi();
    if (state.busy) setBarStatus('Processing…', 'wait');
    else if (state.listening) setBarStatus('Your turn — Speak now', 'speak');
    else if (state.paused || !state.wantListen) {
      setBarStatus('Mic paused — tap Start listening when ready', 'paused');
    } else {
      setBarStatus('Ready when you are', 'ready');
    }
    syncStartListeningButtons();
  }

  function scheduleResumeListening(reason) {
    clearTimeout(state.resumeTimer);
    if (!state.navOn || !canListen() || !getListenIntent()) return;
    if (state.listening) {
      state.skipNextSpeakCue = true;
      setBarStatus('Your turn — Speak now', 'speak');
      return;
    }
    if (state.busy) return;
    // Visual only — avoid saying "Processing" while the page reloads
    state.uiPhase = 'wait';
    if (state.els.status) state.els.status.textContent = reason || 'Resuming on this page…';
    state.resumeTimer = setTimeout(function () {
      state.resumeTimer = null;
      if (!state.navOn || !canListen() || !getListenIntent()) return;
      if (state.busy || state.listening) return;
      state.wantListen = true;
      state.paused = false;
      resumeListeningWithPrompt();
    }, 450);
  }

  function hideBar() {
    if (state.els.bar) state.els.bar.classList.remove('is-on');
    document.body.classList.remove('ttvw-bar-open');
    if (state.els.help) state.els.help.classList.remove('is-open');
    hideEngineNavBar();
  }

  /** Always suppress legacy #ttVoiceNavBar when the site widget is active. */
  function hideEngineNavBar() {
    try {
      var el = document.getElementById('ttVoiceNavBar');
      if (el) {
        el.classList.remove('is-visible');
        el.style.display = 'none';
      }
      document.body.classList.remove('ttvn-bar-open');
      var active = global.TTVoiceNav && global.TTVoiceNav._active && global.TTVoiceNav._active();
      if (active) {
        active.headless = true;
        active.config = active.config || {};
        active.config.headless = true;
        if (typeof global.TTVoiceNav.hideBar === 'function') {
          global.TTVoiceNav.hideBar();
        } else if (active.bar) {
          active.bar.classList.remove('is-visible');
          active.bar.style.display = 'none';
        }
      }
    } catch (e) {}
  }

  function syncStartListeningButtons() {
    var show = !!state.navOn && canListen();
    var btns = [];
    if (state.els.panel) {
      var pStart = state.els.panel.querySelector('[data-ttvw-start]');
      if (pStart) btns.push(pStart);
    }
    if (state.els.bar) {
      var bStart = state.els.bar.querySelector('[data-ttvw-bar-start]');
      if (bStart) btns.push(bStart);
    }
    var label = 'Start listening';
    var title = 'Start listening';
    if (!show) {
      label = 'Mic not available';
      title = 'Mic not available';
    } else if (state.busy) {
      label = 'Wait…';
      title = 'Mic paused while processing — wait or tap a command';
    } else if (state.listening) {
      label = 'Listening…';
      title = 'Speak now — mic is on';
    } else if (state.paused || (state.navOn && !state.wantListen)) {
      label = 'Start listening';
      title = 'Tap to speak — mic is paused';
    }
    btns.forEach(function (btn) {
      if (!state.navOn) {
        btn.hidden = true;
        btn.style.display = 'none';
        btn.disabled = true;
        return;
      }
      btn.hidden = false;
      btn.style.display = '';
      // Allow restart while paused; disable only when mic unavailable or already listening/busy
      btn.disabled = !show || state.busy || state.listening;
      btn.setAttribute('aria-disabled', btn.disabled ? 'true' : 'false');
      btn.classList.toggle('is-unavailable', !show);
      btn.classList.toggle('is-listening-btn', !!state.listening);
      btn.classList.toggle('is-wait-btn', !!state.busy);
      btn.title = title;
      btn.textContent = label;
    });
  }

  function elIsVisible(el) {
    if (!el) return false;
    try {
      // Hidden if any ancestor is display:none / visibility:hidden / inert panel
      var node = el;
      while (node && node.nodeType === 1) {
        var st = global.getComputedStyle ? getComputedStyle(node) : null;
        if (st) {
          if (st.display === 'none' || st.visibility === 'hidden' || Number(st.opacity) === 0) return false;
        }
        if (node.classList && node.classList.contains('student-popup-panel') &&
            !node.classList.contains('active')) return false;
        if (node.id === 'loginRequiredPopup' &&
            !node.classList.contains('show') &&
            node.getAttribute('aria-hidden') !== 'false') {
          // Popup closed — still allow dedicated login pages outside popup
          if (!document.body || String(document.body.className || '').indexOf('login-page') === -1) {
            return false;
          }
        }
        node = node.parentElement;
      }
      if (el.offsetWidth === 0 && el.offsetHeight === 0 && el.getClientRects && !el.getClientRects().length) {
        return false;
      }
    } catch (e) {}
    return true;
  }

  function getActiveLoginRoot() {
    var popup = document.getElementById('loginRequiredPopup');
    var popupOpen = !!(popup && (
      popup.classList.contains('show') ||
      popup.getAttribute('aria-hidden') === 'false'
    ));
    if (popupOpen) {
      return document.querySelector('#loginRequiredPopup .student-popup-panel.active') || popup;
    }
    // Dedicated login pages only (not the closed global popup markup)
    if (document.body && String(document.body.className || '').indexOf('login-page') !== -1) {
      return document.getElementById('loginSignupForm') ||
        document.getElementById('loginpwd') ||
        document.querySelector('.login-page form') ||
        document.body;
    }
    if (document.getElementById('loginSignupForm') || document.getElementById('loginpwd')) {
      return document.getElementById('loginSignupForm') || document.getElementById('loginpwd');
    }
    return null;
  }

  function isLoginUiOpen() {
    var popup = document.getElementById('loginRequiredPopup');
    if (popup && (popup.classList.contains('show') || popup.getAttribute('aria-hidden') === 'false')) {
      return true;
    }
    return !!(document.body && String(document.body.className || '').indexOf('login-page') !== -1) ||
      !!(document.getElementById('loginSignupForm') || document.getElementById('loginpwd'));
  }

  /** Detect page / overlay so Help + chips show relevant commands. */
  function detectPageContext() {
    var path = '';
    try { path = String((global.location && global.location.pathname) || '').toLowerCase(); } catch (e) {}
    var body = document.body;
    var bodyCls = (body && body.className) ? String(body.className) : '';

    var loginPopup = document.getElementById('loginRequiredPopup');
    var popupOpen = !!(loginPopup && (
      loginPopup.classList.contains('show') ||
      (loginPopup.getAttribute('aria-hidden') === 'false')
    ));
    var pwdPanel = document.getElementById('studentPasswordPanel');
    var emailStep = document.getElementById('studentLoginEmailStep');
    var loginPage = !!(
      bodyCls.indexOf('login-page') !== -1 ||
      /\/(user\/login|users\/login|loginpwd|student\/login|sign[_-]?in)/.test(path) ||
      document.getElementById('loginSignupForm') ||
      document.getElementById('loginpwd') ||
      document.getElementById('mobileEmail')
    );
    if (popupOpen || (pwdPanel && pwdPanel.classList.contains('active')) ||
        (loginPage && (document.querySelector('input[type="password"], [data-tt-speech="identity"], #studentLoginInput, #mobileEmail')))) {
      var onPassword = !!(
        (pwdPanel && pwdPanel.classList.contains('active') && elIsVisible(pwdPanel)) ||
        elIsVisible(document.getElementById('studentPasswordInput')) ||
        elIsVisible(document.getElementById('loginpwdPassword')) ||
        elIsVisible(document.querySelector('#loginpwd input[name="password"]'))
      );
      return { id: 'login', label: 'Login', onPassword: onPassword, popup: popupOpen };
    }

    if (document.getElementById('blogSearchInput') ||
        document.getElementById('blogFilterSection') ||
        /\/blogs\/?$/.test(path) || path.indexOf('/blogs/') === 0 || path.indexOf('/blog/') === 0) {
      var detail = !!(document.querySelector('.single-blog-sectin, .blog-title.fs-28, article.blog-detail') ||
        /\/blogs?\/[^/]+/.test(path));
      if (detail && !document.getElementById('blogSearchInput')) {
        return { id: 'blog_detail', label: 'Blog article' };
      }
      return { id: 'blogs', label: 'Blogs' };
    }

    if (path === '/' || path === '' || bodyCls.indexOf('home') !== -1) {
      return { id: 'home', label: 'Home' };
    }
    return { id: 'generic', label: 'This page' };
  }

  function pageContextHelpCommands(ctx) {
    ctx = ctx || detectPageContext();
    var list = [];
    var group = 'On this page';

    if (ctx.id === 'blogs') {
      list.push(
        { label: 'Go home', desc: 'Open the homepage', group: group },
        { label: 'Search for [words]', desc: 'e.g. Search for part time jobs', group: group },
        { label: 'Search', desc: 'Focus the blog search box', group: group },
        { label: 'Open [blog title]', desc: 'e.g. Open Why Teens should have Part time jobs', group: group },
        { label: 'Show numbers', desc: 'Number blog links, then say Go to 3', group: group },
        { label: 'Go back', desc: 'Previous page', group: group }
      );
      try {
        collectPageContentLinks().slice(0, 10).forEach(function (t) {
          list.push({
            label: 'Open ' + t.label,
            desc: 'Open this blog on the page',
            group: group
          });
        });
      } catch (eB) {}
      try {
        collectActionButtons().slice(0, 8).forEach(function (b) {
          list.push({
            label: 'Click ' + b.label,
            desc: 'Activate “' + b.label + '”',
            group: group
          });
        });
      } catch (eBa) {}
      return list;
    }

    if (ctx.id === 'blog_detail') {
      list.push(
        { label: 'Go home', desc: 'Open the homepage', group: group },
        { label: 'Open Blogs', desc: 'Back to all blogs', group: group },
        { label: 'Go back', desc: 'Previous page', group: group },
        { label: 'Scroll down', desc: 'Read further down the article', group: group },
        { label: 'Scroll to top', desc: 'Jump to the top', group: group }
      );
      try {
        collectActionButtons().slice(0, 10).forEach(function (b) {
          list.push({
            label: 'Click ' + b.label,
            desc: 'Activate “' + b.label + '”',
            group: group
          });
        });
      } catch (eBd) {}
      return list;
    }

    if (ctx.id === 'login') {
      if (ctx.onPassword) {
        list.push(
          { label: 'Enter password [your password]', desc: 'Fill the password field', group: group },
          { label: 'Sign in', desc: 'Submit login (or say Click Submit)', group: group },
          { label: 'Click Submit', desc: 'Same as Sign in', group: group },
          { label: 'Back', desc: 'Return to email step', group: group }
        );
      } else {
        list.push(
          { label: 'Enter email [your email]', desc: 'e.g. Enter email name at gmail dot com', group: group },
          { label: 'Continue', desc: 'Continue after email / mobile (or Click Continue)', group: group },
          { label: 'Click Submit', desc: 'Same as Continue on this step', group: group }
        );
      }
      list.push(
        { label: 'Go home', desc: 'Leave login and open homepage', group: group },
        { label: 'Go back', desc: 'Previous login step or previous page', group: group }
      );
      collectLoginActionButtons().forEach(function (b) {
        list.push({
          label: 'Click ' + b.label,
          desc: 'Activate “' + b.label + '”',
          group: group
        });
      });
      return list;
    }

    if (ctx.id === 'home') {
      list.push(
        { label: 'Go home', desc: 'You are on the homepage', group: group },
        { label: 'Go back', desc: 'Previous page', group: group },
        { label: 'Open Blogs', desc: 'Go to blogs', group: group },
        { label: 'Open login', desc: 'Open sign-in', group: group },
        { label: 'Open menu', desc: 'Open top navigation', group: group },
        { label: 'Open search', desc: 'Open site search', group: group }
      );
    } else {
      list.push(
        { label: 'Go home', desc: 'Open the homepage', group: group },
        { label: 'Go back', desc: 'Previous page', group: group }
      );
    }

    // All visible action buttons on public pages
    try {
      collectActionButtons().slice(0, 20).forEach(function (b) {
        list.push({
          label: 'Click ' + b.label,
          desc: 'Activate “' + b.label + '” on this page',
          group: group
        });
      });
    } catch (eAct) {}

    if (ctx.id === 'home') return list;

    // Generic: a few content links if any
    try {
      collectPageContentLinks().slice(0, 6).forEach(function (t) {
        list.push({
          label: 'Open ' + t.label,
          desc: 'Open this item on the page',
          group: group
        });
      });
    } catch (eG) {}
    return list;
  }

  function pageCommandList() {
    var ctx = detectPageContext();
    var cmds = [];
    if (global.TTVoiceNav && typeof global.TTVoiceNav.getPageCommands === 'function') {
      try { cmds = global.TTVoiceNav.getPageCommands() || []; } catch (e) {}
    }
    if (!cmds.length) {
      cmds = [
        { label: 'Go home', desc: 'Open homepage', group: 'Navigate' },
        { label: 'Go back', desc: 'Previous page', group: 'Navigate' }
      ];
    }
    var contextCmds = pageContextHelpCommands(ctx);
    var extras = alwaysHelpCommands(ctx);
    var seen = {};
    var out = [];
    function add(c) {
      if (!c || !c.label) return;
      var key = String(c.label).toLowerCase();
      if (seen[key]) return;
      seen[key] = true;
      out.push(c);
    }
    // Page-specific first so Help leads with what works here
    contextCmds.forEach(add);
    cmds.forEach(add);
    extras.forEach(add);
    return out;
  }

  function alwaysHelpCommands(ctx) {
    ctx = ctx || detectPageContext();
    var list = [
      { label: 'Scroll to top', desc: 'Jump to the top of the page', group: 'Scroll' },
      { label: 'Scroll to bottom', desc: 'Jump to the bottom of the page', group: 'Scroll' },
      { label: 'Scroll down', desc: 'Move down one screen', group: 'Scroll' },
      { label: 'Scroll up', desc: 'Move up one screen', group: 'Scroll' },
      { label: 'Open menu', desc: 'Open the top navigation menu (mobile)', group: 'Top navigation' },
      { label: 'Close menu', desc: 'Close the top navigation menu', group: 'Top navigation' },
      { label: 'Open search', desc: 'Open site search', group: 'Top navigation' },
      { label: 'Skip to content', desc: 'Jump to main content', group: 'Navigate' }
    ];
    if (adminAllowsLinkNumbers()) {
      list.push(
        { label: 'Show numbers', desc: 'Number links, then say Go to 3', group: 'Actions' },
        { label: 'Hide numbers', desc: 'Hide link numbers', group: 'Actions' }
      );
    }
    list.push(
      { label: 'Click Save', desc: 'Click a visible Save button', group: 'Actions' },
      { label: 'Click Continue', desc: 'Click Continue / Next', group: 'Actions' },
      { label: 'Click Submit', desc: 'Click Submit / Sign in / Apply', group: 'Actions' },
      { label: 'Click [button name]', desc: 'Say Click followed by the button label', group: 'Actions' },
      { label: 'Open [menu item]', desc: 'Say Open About Us, Open Blogs…', group: 'Top navigation' }
    );
    // Only list blog-style open/search templates when on blogs (already in On this page)
    if (ctx.id !== 'blogs' && ctx.id !== 'login') {
      list.push(
        { label: 'Search for [words]', desc: 'Search when a search box is available', group: 'Actions' }
      );
    }
    collectTopNavTargets().slice(0, 12).forEach(function (t) {
      list.push({
        label: 'Open ' + t.label,
        desc: 'Open “' + t.label + '” from top navigation',
        group: 'Top navigation'
      });
    });
    // Content links only when not already listed under On this page
    if (ctx.id !== 'blogs' && ctx.id !== 'login') {
      try {
        collectPageContentLinks().slice(0, 6).forEach(function (t) {
          list.push({
            label: 'Open ' + t.label,
            desc: 'Open this item on the current page',
            group: 'Actions'
          });
        });
      } catch (ePage) {}
    }
    collectActionButtons().slice(0, 8).forEach(function (b) {
      list.push({
        label: 'Click ' + b.label,
        desc: 'Activate the “' + b.label + '” button',
        group: 'Actions'
      });
    });
    return list;
  }

  function escapeHelp(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  /** Stable key for current page / login step — used to refresh Help + chips. */
  function pageContextKey() {
    var ctx = detectPageContext();
    var path = '';
    try { path = String((global.location && global.location.pathname) || '') + String((global.location && global.location.search) || ''); } catch (e) {}
    var btnSig = '';
    try {
      btnSig = collectActionButtons().slice(0, 10).map(function (b) { return b.label; }).join('|');
    } catch (e2) {}
    var linkSig = '';
    try {
      if (ctx.id === 'blogs' || ctx.id === 'generic') {
        linkSig = collectPageContentLinks().slice(0, 6).map(function (t) { return t.label; }).join('|');
      }
    } catch (e3) {}
    return [ctx.id, ctx.label || '', ctx.onPassword ? 'pwd' : 'id', ctx.popup ? 'pop' : '', path, btnSig, linkSig].join('::');
  }

  /**
   * Rebuild Help panel + command chips for the page the user is on now.
   * opts.forceHtml — always rewrite Help HTML
   * opts.open — open the Help panel
   */
  function refreshNavHelpUi(opts) {
    opts = opts || {};
    var key = '';
    try { key = pageContextKey(); } catch (eKey) { key = String(Date.now()); }
    var changed = key !== state.lastHelpContextKey;
    state.lastHelpContextKey = key;

    try { renderWidgetChips(); } catch (eChips) {}

    if (!state.els.help) return changed;
    var helpOpen = state.els.help.classList.contains('is-open');
    if (opts.open) {
      state.els.help.innerHTML = helpHtml();
      state.els.help.classList.add('is-open');
      return true;
    }
    if (helpOpen && (changed || opts.forceHtml)) {
      state.els.help.innerHTML = helpHtml();
    }
    return changed;
  }

  function scheduleNavHelpRefresh() {
    clearTimeout(state._ctxRefreshTimer);
    state._ctxRefreshTimer = setTimeout(function () {
      state._ctxRefreshTimer = null;
      try {
        if (!isLoginUiOpen() && state.awaitLoginField) state.awaitLoginField = null;
      } catch (eAwait) {}
      try { refreshNavHelpUi(); } catch (e) {}
    }, 180);
  }

  /** Keep Help/chips in sync when login popup / panels / main content change. */
  function watchPageContextChanges() {
    if (state._ctxObserver || !global.MutationObserver) return;
    var roots = [];
    var popup = document.getElementById('loginRequiredPopup');
    if (popup) roots.push(popup);
    var main = document.querySelector('main, [role="main"], .std-shell-main, #blogFilterSection, #content');
    if (main) roots.push(main);
    if (!roots.length && document.body) roots.push(document.body);

    state._ctxObserver = new MutationObserver(function () {
      scheduleNavHelpRefresh();
    });
    roots.forEach(function (root) {
      try {
        state._ctxObserver.observe(root, {
          attributes: true,
          attributeFilter: ['class', 'aria-hidden', 'style', 'hidden'],
          childList: true,
          subtree: true
        });
      } catch (eObs) {}
    });
  }

  function helpHtml() {
    var ctx = detectPageContext();
    var cmds = pageCommandList();
    var pathLabel = '';
    try {
      pathLabel = String((global.location && global.location.pathname) || '/');
    } catch (eP) {}
    var banner =
      '<div class="ttvw-help-banner">' +
      '<strong>Commands for: ' + escapeHelp(ctx.label || 'This page') + '</strong>' +
      '<span>' + escapeHelp(pathLabel) + (ctx.onPassword ? ' · password step' : '') + '</span>' +
      '</div>';

    var groups = {};
    var order = ['On this page', 'Scroll', 'Top navigation', 'Navigate', 'Actions', 'Page', 'Mic'];
    cmds.forEach(function (c) {
      var g = c.group || 'Page';
      if (!groups[g]) groups[g] = [];
      groups[g].push(c);
    });
    groups.Mic = groups.Mic || [];
    groups.Mic.push(
      { label: 'Start listening', desc: 'Turn mic on' },
      { label: 'Stop / Pause mic', desc: 'Turn mic off' },
      { label: 'Exit', desc: 'Turn Voice Navigation off' },
      { label: 'Help', desc: 'Show this list' }
    );

    var sections = [];
    order.forEach(function (name) {
      var items = groups[name];
      if (!items || !items.length) return;
      var title = name === 'On this page' ? ('On this page — ' + (ctx.label || 'here')) : name;
      var rows = items.map(function (c) {
        return '<div class="ttvw-help-item"><strong>' + escapeHelp(c.label) +
          '</strong><span>' + escapeHelp(c.desc || '') + '</span></div>';
      }).join('');
      sections.push(
        '<div class="ttvw-help-section">' +
        '<div class="ttvw-help-title">' + escapeHelp(title) + '</div>' +
        '<div class="ttvw-help-list">' + rows + '</div></div>'
      );
      delete groups[name];
    });
    Object.keys(groups).forEach(function (name) {
      var items = groups[name];
      if (!items || !items.length) return;
      var rows = items.map(function (c) {
        return '<div class="ttvw-help-item"><strong>' + escapeHelp(c.label) +
          '</strong><span>' + escapeHelp(c.desc || '') + '</span></div>';
      }).join('');
      sections.push(
        '<div class="ttvw-help-section">' +
        '<div class="ttvw-help-title">' + escapeHelp(name) + '</div>' +
        '<div class="ttvw-help-list">' + rows + '</div></div>'
      );
    });

    var notes = '';
    if (ctx.id === 'blogs') {
      notes += '<div class="ttvw-help-note">Blogs: say “Search for part time jobs” or “Open Why Teens should have Part time jobs”. Or “Show numbers” then “Go to 3”.</div>';
    } else if (ctx.id === 'login') {
      notes += '<div class="ttvw-help-note">Login: say “Enter email name at gmail dot com”, then “Enter password yourpassword”, then “Sign in” or “Submit”.</div>';
    } else {
      notes += '<div class="ttvw-help-note">Tips: say “Scroll to top”, “Open About Us”, or “Click Save”. On phones, open the menu first if needed.</div>';
    }
    notes += '<div class="ttvw-help-note">This list refreshes for the page you are on. Open Help again anytime after you navigate.</div>';
    if (adminAllowsLinkNumbers()) {
      notes += '<div class="ttvw-help-note">Say “Show numbers” then “Go to 3” for numbered links.</div>';
    }
    notes += '<div class="ttvw-help-note">The site speaks prompts aloud: “Speak now”, “Got it”, “Processing”. Turn off Speak prompts in the Voice panel if you prefer silent cues.</div>';
    return banner + sections.join('') + notes;
  }

  function chipCommandList() {
    var ctx = detectPageContext();
    var priority = [];
    if (ctx.id === 'blogs') {
      priority = [
        'Go home', 'Search', 'Show numbers', 'Go back', 'Open menu', 'Scroll to top'
      ];
    } else if (ctx.id === 'login') {
      priority = ctx.onPassword
        ? ['Sign in', 'Click Submit', 'Back', 'Go home']
        : ['Continue', 'Click Continue', 'Click Submit', 'Go home'];
    } else if (ctx.id === 'blog_detail') {
      priority = ['Go home', 'Open Blogs', 'Scroll down', 'Go back'];
    } else {
      priority = [
        'Scroll to top', 'Scroll to bottom', 'Go back', 'Go home',
        'Explore careers', 'Open login', 'Open notebook', 'Open menu',
        'Show numbers', 'Open search'
      ];
    }
    var all = pageCommandList();
    var byLabel = {};
    all.forEach(function (c) {
      if (c && c.label) byLabel[String(c.label).toLowerCase()] = c;
    });
    var out = [];
    var seen = {};
    // Login help chips (display-only templates are not in priority — spoken enter email/password)
    if (ctx.id === 'login') {
      if (ctx.onPassword) {
        out.push({
          label: 'Enter password …',
          desc: 'Say Enter password followed by your password'
        });
        seen['enter password …'] = true;
      } else {
        out.push({
          label: 'Enter email …',
          desc: 'Say Enter email name at gmail dot com'
        });
        seen['enter email …'] = true;
      }
    }
    if (ctx.id === 'blogs') {
      out.push({
        label: 'Search for …',
        desc: 'Say Search for part time jobs'
      });
      seen['search for …'] = true;
    }
    priority.forEach(function (label) {
      var c = byLabel[label.toLowerCase()];
      if (!c) {
        // Allow chip even if not in help list (Continue / Sign in shortcuts)
        if (/^(click |continue|sign in|back|submit)/i.test(label)) {
          c = { label: label, desc: label };
        } else {
          return;
        }
      }
      var key = label.toLowerCase();
      if (seen[key]) return;
      seen[key] = true;
      out.push(c);
    });
    if (ctx.id === 'blogs') {
      try {
        collectPageContentLinks().slice(0, 4).forEach(function (t) {
          var label = 'Open ' + t.label;
          var key = label.toLowerCase();
          if (seen[key]) return;
          seen[key] = true;
          out.push({ label: label, desc: 'Open this blog' });
        });
      } catch (eC) {}
    }
    collectActionButtons().slice(0, 2).forEach(function (b) {
      var label = 'Click ' + b.label;
      var key = label.toLowerCase();
      if (seen[key]) return;
      seen[key] = true;
      out.push({ label: label, desc: 'Click ' + b.label });
    });
    return out.slice(0, 10);
  }

  function normalizeSpeakLabel(s) {
    return String(s || '')
      .replace(/[^\w\s&/-]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .toLowerCase();
  }

  function scoreSpeakMatch(spoken, key) {
    var s = normalizeSpeakLabel(spoken);
    var k = normalizeSpeakLabel(key);
    if (!s || !k) return 0;
    if (k === s) return 1000;
    if (k.indexOf(s) !== -1) return 850 - Math.min(120, k.length - s.length);
    if (s.indexOf(k) !== -1 && k.length >= 6) return 700;
    var words = s.split(/\s+/).filter(function (w) { return w.length > 2; });
    if (!words.length) return 0;
    var hit = 0;
    for (var i = 0; i < words.length; i++) {
      if (k.indexOf(words[i]) !== -1) hit += 1;
    }
    if (!hit) return 0;
    var ratio = hit / words.length;
    if (ratio < 0.5) return 0;
    return Math.round(400 * ratio) + (hit === words.length ? 80 : 0) + Math.min(40, hit * 5);
  }

  function findBestTarget(spoken, targets) {
    var s = normalizeSpeakLabel(spoken);
    if (!s || !targets || !targets.length) return null;
    var best = null;
    var bestScore = 0;
    for (var i = 0; i < targets.length; i++) {
      var t = targets[i];
      var score = scoreSpeakMatch(s, t.key || t.label || '');
      if (score > bestScore) {
        bestScore = score;
        best = t;
      }
    }
    // Require a meaningful match (avoid opening random short links)
    if (bestScore < 250) return null;
    return best;
  }

  function collectTopNavTargets() {
    var roots = [
      document.querySelector('.navbar'),
      document.querySelector('.tt-header'),
      document.querySelector('.std-shell-topbar'),
      document.querySelector('nav[role="navigation"]'),
      document.querySelector('.tt-navbar')
    ].filter(Boolean);
    var out = [];
    var seen = {};
    roots.forEach(function (root) {
      var links = root.querySelectorAll('a[href]');
      for (var i = 0; i < links.length; i++) {
        var a = links[i];
        if (!a || a.closest('#tt-voice-fab-wrap, #tt-voice-bar, #cb-fab-wrap, #cb-root')) continue;
        var href = (a.getAttribute('href') || '').trim();
        if (!href || href === '#' || href.indexOf('javascript:') === 0) continue;
        if (a.classList.contains('search-toggle')) continue;
        var label = normalizeSpace(a.getAttribute('aria-label') || a.textContent || '');
        if (!label || label.length > 48) continue;
        if (/^(search|menu|close|toggle)/i.test(label)) continue;
        var key = normalizeSpeakLabel(label);
        if (!key || seen[key]) continue;
        seen[key] = true;
        out.push({ el: a, label: label, key: key });
      }
    });
    return out;
  }

  /** Article / blog / card links in main content (for “Open Why Teens…”). */
  function collectPageContentLinks() {
    var root = document.querySelector('main, [role="main"], .std-shell-main, #content, .content, #blogFilterSection') ||
      document.body;
    var nodes = root.querySelectorAll(
      'a[href], .blog-card a[href], article a[href], h2 a[href], h3 a[href], .card a[href]'
    );
    var out = [];
    var seenHref = {};
    for (var i = 0; i < nodes.length && out.length < 80; i++) {
      var a = nodes[i];
      if (!a || a.closest('#tt-voice-fab-wrap, #tt-voice-bar, #cb-fab-wrap, #cb-root, nav, header, .navbar, .tt-header, .std-shell-topbar, .blog-filter-btn, .footer, footer')) continue;
      var href = (a.getAttribute('href') || '').trim();
      if (!href || href === '#' || href.indexOf('javascript:') === 0) continue;
      if (href.indexOf('/category/') !== -1 && !a.closest('.blog-card')) continue;
      try {
        var st = global.getComputedStyle ? getComputedStyle(a) : null;
        if (st && (st.display === 'none' || st.visibility === 'hidden')) continue;
      } catch (eVis) {}
      var label = normalizeSpace(
        a.getAttribute('aria-label') || a.getAttribute('title') ||
        (a.querySelector('img') && a.querySelector('img').getAttribute('alt')) ||
        a.textContent || ''
      );
      if (!label || label.length < 4 || label.length > 140) continue;
      if (/^(read more|learn more|view all|see all|next|previous|share|save)$/i.test(label)) continue;
      var key = normalizeSpeakLabel(label);
      if (!key || seenHref[href + '|' + key]) continue;
      seenHref[href + '|' + key] = true;
      out.push({ el: a, label: label, key: key });
    }
    return out;
  }

  function collectActionButtons() {
    var roots = [];
    var loginRoot = getActiveLoginRoot();
    if (loginRoot) roots.push(loginRoot);
    var main = document.querySelector('main, [role="main"], .std-shell-main, #content, .content');
    if (main) roots.push(main);
    // Public page CTAs often sit outside <main>
    if (document.body) roots.push(document.body);

    var out = [];
    var seen = {};
    var skipRe = /voice|microphone|chat|cookie|close|dismiss|burger|menu toggle|speak to fill|show password|hide password/i;
    var skipClosest = '#tt-voice-fab-wrap, #tt-voice-bar, #tt-voice-panel, #cb-fab-wrap, #cb-root, #eu-cookie-consent, #tt-sr-controls, #tt-sr-caption, nav, header, .navbar, .std-shell-topbar, .tt-header, footer, .footer';

    function addEl(el) {
      if (!el || el.disabled || el.getAttribute('aria-disabled') === 'true') return;
      if (el.closest(skipClosest) && !(loginRoot && loginRoot.contains(el))) return;
      if (!elIsVisible(el)) return;
      var label = normalizeSpace(
        el.getAttribute('aria-label') || el.value || el.textContent || ''
      );
      if (!label || label.length > 48 || label.length < 2) return;
      if (skipRe.test(label)) return;
      var key = normalizeSpeakLabel(label);
      if (!key || seen[key]) return;
      seen[key] = true;
      out.push({ el: el, label: label, key: key });
    }

    for (var r = 0; r < roots.length && out.length < 40; r++) {
      var root = roots[r];
      if (!root) continue;
      var nodes = root.querySelectorAll(
        'button, a.btn, a.button, [role="button"], input[type="submit"], input[type="button"], .btn, .cta-btn, .student-popup-btn'
      );
      for (var i = 0; i < nodes.length && out.length < 40; i++) {
        addEl(nodes[i]);
      }
    }
    return out;
  }

  function normalizeSpace(s) {
    return String(s || '').replace(/\s+/g, ' ').trim();
  }

  function runPageSearch(query) {
    var q = normalizeSpace(query);
    if (!q) return null;

    // Prefer on-page blog / content search
    var blogInput = document.getElementById('blogSearchInput') ||
      document.querySelector('.js-blog-sidebar-search-input, form.blog-search input[name="search"], input[name="search"]');
    if (blogInput) {
      blogInput.focus();
      blogInput.value = q;
      try {
        blogInput.dispatchEvent(new Event('input', { bubbles: true }));
      } catch (eIn) {}
      var blogForm = blogInput.form || blogInput.closest('form');
      if (blogForm) {
        try {
          if (typeof blogForm.requestSubmit === 'function') blogForm.requestSubmit();
          else blogForm.submit();
        } catch (eSub) {
          try { blogForm.submit(); } catch (e2) {}
        }
        return 'Searching blogs for “' + q + '”';
      }
      // Fallback: navigate with query
      try {
        var action = (blogForm && blogForm.getAttribute('action')) || '/blogs/';
        global.location.href = action + (action.indexOf('?') >= 0 ? '&' : '?') + 'search=' + encodeURIComponent(q);
        return 'Searching blogs for “' + q + '”';
      } catch (eNav) {}
    }

    // Header / site search
    openSiteSearch();
    var siteInput = document.getElementById('search-input') ||
      document.querySelector('.search-container input[type="search"], .search-container input[type="text"], input[name="q"]');
    if (siteInput) {
      siteInput.focus();
      siteInput.value = q;
      try {
        siteInput.dispatchEvent(new Event('input', { bubbles: true }));
      } catch (e3) {}
      var siteForm = siteInput.form || siteInput.closest('form');
      if (siteForm) {
        try {
          if (typeof siteForm.requestSubmit === 'function') siteForm.requestSubmit();
          else siteForm.submit();
        } catch (e4) {
          try { siteForm.submit(); } catch (e5) {}
        }
        return 'Searching for “' + q + '”';
      }
      // Press Enter
      try {
        siteInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
      } catch (e6) {}
      return 'Typed “' + q + '” in search — press Enter if needed';
    }

    // Last resort: blogs listing URL
    try {
      global.location.href = '/blogs/?search=' + encodeURIComponent(q);
      return 'Searching blogs for “' + q + '”';
    } catch (e7) {}
    return null;
  }

  function scrollPage(kind) {
    var y = global.pageYOffset || document.documentElement.scrollTop || 0;
    var vh = global.innerHeight || document.documentElement.clientHeight || 600;
    if (kind === 'top') {
      global.scrollTo({ top: 0, behavior: 'smooth' });
      return 'Scrolled to top';
    }
    if (kind === 'bottom') {
      var h = Math.max(
        document.body.scrollHeight || 0,
        document.documentElement.scrollHeight || 0
      );
      global.scrollTo({ top: h, behavior: 'smooth' });
      return 'Scrolled to bottom';
    }
    if (kind === 'down') {
      global.scrollTo({ top: y + Math.round(vh * 0.85), behavior: 'smooth' });
      return 'Scrolled down';
    }
    if (kind === 'up') {
      global.scrollTo({ top: Math.max(0, y - Math.round(vh * 0.85)), behavior: 'smooth' });
      return 'Scrolled up';
    }
    return 'Done';
  }

  function isTopMenuOpen() {
    var menu = document.getElementById('menu') ||
      document.querySelector('.navbar-block, .navbar-collapse, .tt-mobile-nav');
    var burger = document.getElementById('burger');
    if (menu && (menu.classList.contains('is-active') || menu.classList.contains('is-open') ||
        menu.classList.contains('show') || menu.classList.contains('active'))) {
      return true;
    }
    if (burger && burger.classList.contains('is-active')) return true;
    return false;
  }

  function toggleTopMenu(open) {
    var burger = document.getElementById('burger') ||
      document.querySelector('.burger, .navbar-toggler');
    var menu = document.getElementById('menu') ||
      document.querySelector('.navbar-block, .navbar-collapse, .tt-mobile-nav');
    if (!menu && !burger) return null;

    var wantOpen = open !== false;
    var isOpen = isTopMenuOpen();
    if (wantOpen === isOpen) {
      return wantOpen ? 'Menu already open' : 'Menu already closed';
    }

    // Match header.html openMenu/closeMenu (more reliable than synthetic click)
    if (wantOpen) {
      if (burger) burger.classList.add('is-active');
      if (menu) {
        menu.classList.add('is-active');
        menu.classList.add('is-open');
      }
      try { document.body.classList.add('no-scroll'); } catch (e) {}
      return 'Opening menu';
    }

    if (burger) burger.classList.remove('is-active');
    if (menu) {
      menu.classList.remove('is-active');
      menu.classList.remove('is-open');
      menu.classList.remove('show');
      menu.classList.remove('active');
    }
    try { document.body.classList.remove('no-scroll'); } catch (e2) {}
    return 'Closing menu';
  }

  function openLoginPopup() {
    try {
      if (typeof global.showLoginRequiredPopup === 'function') {
        global.showLoginRequiredPopup();
        return 'Opening login';
      }
    } catch (e) {}

    var selectors = [
      '#header-signin-btn',
      '.student-login-popup-trigger',
      '[onclick*="showLoginRequiredPopup"]',
      '.btn-profile-login',
      '#openStudentLogin',
      '.open-login',
      '[data-bs-target="#studentLoginModal"]',
      'a[href*="/user/login"]',
      'a[href*="/users/login"]',
      'a[href*="student/login"]'
    ];
    for (var i = 0; i < selectors.length; i++) {
      var el = document.querySelector(selectors[i]);
      if (!el) continue;
      try {
        el.click();
        return 'Opening login';
      } catch (eClick) {}
    }
    return null;
  }

  function openSiteSearch() {
    var toggle = document.querySelector('.search-toggle, .main-search-icon a');
    if (!toggle) {
      var candidates = document.querySelectorAll('[aria-label]');
      for (var i = 0; i < candidates.length; i++) {
        var al = String(candidates[i].getAttribute('aria-label') || '').toLowerCase();
        if (al.indexOf('search') !== -1) { toggle = candidates[i]; break; }
      }
    }
    if (toggle) {
      toggle.click();
      return 'Opening search';
    }
    return null;
  }

  function renderWidgetChips() {
    var host = state.els.chips;
    if (!host) return;
    var cmds = chipCommandList().filter(function (c) {
      return c && c.label && String(c.label).toLowerCase() !== 'help';
    });
    host.innerHTML = '';
    cmds.forEach(function (c) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'ttvw-chip';
      btn.textContent = c.label;
      btn.disabled = !!state.busy;
      btn.addEventListener('click', function () {
        if (state.busy) return;
        var lab = String(c.label || '');
        if (/\u2026|\.\.\.|\[/.test(lab)) {
          // Hint only — do NOT set phase "speak" (that can kill an active mic via TTS cue)
          if (/email/i.test(lab)) {
            state.awaitLoginField = 'email';
            setBarStatus('Say your email like name at gmail dot com', 'understood', true);
          } else if (/password/i.test(lab)) {
            state.awaitLoginField = 'password';
            setBarStatus('Say your password', 'understood', true);
          } else if (/search/i.test(lab)) {
            setBarStatus(c.desc || 'Say Search for …', 'understood', true);
          } else {
            setBarStatus(c.desc || ('Say the full command: ' + lab.replace(/\u2026|\.\.\./g, '…')), 'understood', true);
          }
          if (state.wantListen && !state.listening && !state.busy) {
            try { resumeSoon(); } catch (eR) {}
          }
          return;
        }
        handleUtterance(lab);
      });
      host.appendChild(btn);
    });
  }

  function setChipsBusy(busy) {
    if (!state.els.chips) return;
    var chips = state.els.chips.querySelectorAll('.ttvw-chip');
    for (var i = 0; i < chips.length; i++) chips[i].disabled = !!busy;
  }

  /** Pause mic while a command runs; keep wantListen so we can resume. */
  function pauseMicForProcessing(msg) {
    clearSilence();
    state.ignoreEnd = true;
    destroyRecognition();
    stopCloudTracks();
    state.listening = false;
    syncFabListening();
    setChipsBusy(true);
    if (msg !== false) setBarStatus(msg || 'Processing…', 'wait');
  }

  function finishProcessing(okMsg, kind) {
    state.busy = false;
    setChipsBusy(false);
    clearTimeout(state._understoodTimer);
    try { refreshNavHelpUi(); } catch (eChips) {}
    if (kind === 'err') {
      setBarStatus(okMsg || 'Try again', 'err');
    } else if (okMsg) {
      // Visual confirmation only — "Got it" was already spoken
      setBarStatus(okMsg, 'understood', true);
    } else {
      setBarStatus('Your turn — Speak now', 'speak');
    }
    resumeSoon();
  }

  function showUnderstoodThenProcess(heardText) {
    var short = String(heardText || '').trim();
    if (short.length > 48) short = short.slice(0, 45) + '…';
    setBarStatus(short ? ('Got it: “' + short + '”') : 'Understood', 'understood');
    clearTimeout(state._understoodTimer);
    state._understoodTimer = setTimeout(function () {
      if (!state.busy) return;
      setBarStatus('Processing…', 'wait');
    }, 380);
  }

  function runUtteranceCommand(text) {
    var raw = String(text || '').trim();
    var t = raw.toLowerCase().replace(/[^\w\s@./-]/g, ' ').replace(/\s+/g, ' ').trim();
    var statusMsg = '';

    try {
      if (runLoginFillCommand(raw)) {
        statusMsg = (state.els.status && state.els.status.textContent) || 'Done';
        if (/speak now|your turn|processing|got it|understood/i.test(statusMsg)) {
          statusMsg = 'Done';
        }
        finishProcessing(statusMsg);
        return;
      }
      if (runSiteCommand(t)) {
        if (/^(stop|stop listening|pause|exit|quit|close voice|turn off)$/.test(t)) {
          state.busy = false;
          setChipsBusy(false);
          clearTimeout(state._understoodTimer);
          return;
        }
        statusMsg = (state.els.status && state.els.status.textContent) || 'Done';
        if (/speak now|your turn|processing|got it|understood/i.test(statusMsg)) {
          statusMsg = 'Done';
        }
        finishProcessing(statusMsg);
        return;
      }

      var navActive = global.TTVoiceNav && global.TTVoiceNav._active && global.TTVoiceNav._active();
      if (navActive && navActive.formCtx && navActive.formCtx.active) {
        global.TTVoiceNav.handleUtterance(text);
        state.busy = false;
        setChipsBusy(false);
        clearTimeout(state._understoodTimer);
        setBarStatus('Got it — next field or command', 'understood');
        clearTimeout(state.resumeTimer);
        state.resumeTimer = setTimeout(function () {
          state.resumeTimer = null;
          if (!state.navOn || !state.wantListen || state.busy) return;
          resumeListeningWithPrompt();
        }, 700);
        return;
      }

      if (global.TTVoiceNav && typeof global.TTVoiceNav.handleUtterance === 'function') {
        global.TTVoiceNav.handleUtterance(text);
        state.busy = false;
        setChipsBusy(false);
        clearTimeout(state._understoodTimer);
        setBarStatus('Done', 'understood');
        clearTimeout(state.resumeTimer);
        state.resumeTimer = setTimeout(function () {
          state.resumeTimer = null;
          if (!state.navOn || !state.wantListen || state.busy) return;
          resumeListeningWithPrompt();
        }, 700);
        return;
      }

      finishProcessing('Try Help or a page command button', 'err');
    } catch (eCmd) {
      try { console.warn('[tt-voice-widget] command error', eCmd); } catch (e2) {}
      finishProcessing('Command failed', 'err');
    }
  }

  function handleUtterance(raw) {
    var text = String(raw || '').trim();
    if (!text || state.busy) return;
    setHeard('“' + text + '”');
    state.busy = true;
    // Stop mic first (no status flash), then Got it → Processing → result
    pauseMicForProcessing(false);
    showUnderstoodThenProcess(text);
    clearTimeout(state._cmdTimer);
    state._cmdTimer = setTimeout(function () {
      state._cmdTimer = null;
      if (!state.busy) return;
      setBarStatus('Processing…', 'wait');
      runUtteranceCommand(text);
    }, 480);
  }

  function resumeSoon() {
    if (!state.navOn || !state.wantListen || state.busy) return;
    clearTimeout(state.resumeTimer);
    state.resumeTimer = setTimeout(function () {
      state.resumeTimer = null;
      if (!state.navOn || !state.wantListen || state.busy || state.listening) return;
      if (!canListen()) {
        updateMicAvailabilityUi();
        return;
      }
      // Login popup: skip spoken cue — TTS often stalls behind the modal and leaves SPEAK NOW with mic off
      if (isLoginUiOpen()) {
        state.paused = false;
        state.cueSpeaking = false;
        state.skipNextSpeakCue = true;
        stopVoiceCue();
        setBarStatus(
          state.awaitLoginField === 'email'
            ? 'Say your email like name at gmail dot com'
            : (state.awaitLoginField === 'password'
              ? 'Say your password'
              : 'Your turn — Speak now'),
          'speak',
          true
        );
        try { startListeningNow(); } catch (eL) {}
        return;
      }
      resumeListeningWithPrompt();
    }, 500);
  }

  /** Speak “Speak now” (if cues on), then open the mic. */
  function resumeListeningWithPrompt() {
    if (!state.navOn || !state.wantListen || state.busy) return;
    if (!canListen()) {
      updateMicAvailabilityUi();
      return;
    }
    state.paused = false;
    if (isLoginUiOpen()) {
      state.skipNextSpeakCue = true;
      state.cueSpeaking = false;
      stopVoiceCue();
      setBarStatus('Your turn — Speak now', 'speak', true);
      try { startListeningNow(); } catch (e2) {}
      return;
    }
    setBarStatus('Your turn — Speak now', 'speak');
    // Cue path starts the mic after TTS; if cue skipped/off, start immediately
    if (!state.cueSpeaking) startListeningNow();
  }

  /* —— Link numbers —— */
  function hideLinkNumbers() {
    state.linkNumbersOn = false;
    state.numberedLinks = [];
    try {
      var marks = document.querySelectorAll('.ttvw-link-num');
      for (var i = 0; i < marks.length; i++) marks[i].parentNode.removeChild(marks[i]);
    } catch (e) {}
  }

  function showLinkNumbers() {
    if (!adminAllowsLinkNumbers()) {
      setBarStatus('Link numbering is disabled by admin', 'err');
      return;
    }
    hideLinkNumbers();
    var links = document.querySelectorAll('a[href]:not([href^="#"]):not([href^="javascript"])');
    var n = 0;
    state.numberedLinks = [];
    for (var i = 0; i < links.length && n < 40; i++) {
      var a = links[i];
      if (!a.offsetParent) continue;
      n += 1;
      var badge = document.createElement('span');
      badge.className = 'ttvw-link-num';
      badge.textContent = String(n);
      a.insertBefore(badge, a.firstChild);
      state.numberedLinks.push(a);
    }
    state.linkNumbersOn = true;
    setBarStatus('Showing ' + n + ' link numbers. Say “Go to 3”.');
  }

  /* —— Site commands —— */
  function normalizeSpokenIdentity(text) {
    var t = String(text || '').trim().toLowerCase();
    if (!t) return '';
    t = t.replace(/^(?:is|as|equals?)\s+/, '');
    t = t.replace(/\s+at\s+the\s+rate\s+/gi, '@');
    t = t.replace(/\s+at\s+/gi, '@');
    t = t.replace(/\s+dot\s+/gi, '.');
    t = t.replace(/\s+underscore\s+/gi, '_');
    t = t.replace(/\s+dash\s+/gi, '-');
    var digitsOnly = t.replace(/[\s\-().]/g, '');
    if (/^\+?\d{8,15}$/.test(digitsOnly)) {
      return digitsOnly.replace(/^\+91/, '').replace(/^0/, '');
    }
    if (t.indexOf('@') !== -1) {
      t = t.replace(/\s*@\s*/g, '@').replace(/\s*\.\s*/g, '.').replace(/\s+/g, '');
    }
    return t;
  }

  function normalizeSpokenPassword(text) {
    return String(text || '').replace(/\s+/g, '');
  }

  function pickVisibleInputIn(root, selectors) {
    var scope = root || document;
    for (var i = 0; i < selectors.length; i++) {
      var nodes = scope.querySelectorAll(selectors[i]);
      for (var j = 0; j < nodes.length; j++) {
        var el = nodes[j];
        if (!el || el.disabled) continue;
        if (el.readOnly && el.id === 'studentPasswordUsername') continue;
        if (elIsVisible(el)) return el;
      }
    }
    return null;
  }

  function findLoginIdentityInput() {
    var root = getActiveLoginRoot() || document;
    return pickVisibleInputIn(root, [
      '#studentLoginInput',
      '#studentSignupInput',
      '#mobileEmail',
      'input[data-tt-speech="identity"]',
      'input[name="email"]',
      'input[name="username"]:not([readonly])',
      'input[type="email"]',
      'input[autocomplete="username"]'
    ]) || pickVisibleInputIn(document, [
      '#studentLoginInput',
      '#mobileEmail',
      'input[data-tt-speech="identity"]'
    ]);
  }

  function findLoginPasswordInput() {
    var root = getActiveLoginRoot() || document;
    return pickVisibleInputIn(root, [
      '#studentPasswordInput',
      '#loginpwdPassword',
      'input[data-tt-speech="password"]',
      'input[name="password"]',
      'input[type="password"]'
    ]);
  }

  function setInputValue(el, value, opts) {
    if (!el) return false;
    opts = opts || {};
    // Focusing during Voice Nav often kills Chrome SpeechRecognition behind login modal
    if (!opts.noFocus) {
      try { el.focus(); } catch (eF) {}
    }
    try {
      var proto = global.HTMLInputElement && global.HTMLInputElement.prototype;
      var desc = proto && Object.getOwnPropertyDescriptor(proto, 'value');
      if (desc && desc.set) desc.set.call(el, value);
      else el.value = value;
    } catch (eSet) {
      el.value = value;
    }
    try {
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      if (typeof InputEvent === 'function') {
        el.dispatchEvent(new InputEvent('input', { bubbles: true, data: value }));
      }
    } catch (e) {}
    return true;
  }

  /** Resolve Continue / Sign in / Back for the active login step only. */
  function resolveLoginActionButton(spokenBtn) {
    if (!isLoginUiOpen()) return null;
    var s = normalizeSpeakLabel(spokenBtn || '');
    if (!s) return null;

    var pwdPanel = document.getElementById('studentPasswordPanel');
    var onPassword = !!(pwdPanel && pwdPanel.classList.contains('active') && elIsVisible(pwdPanel)) ||
      elIsVisible(document.getElementById('studentPasswordInput')) ||
      elIsVisible(document.getElementById('loginpwdPassword'));

    function btn(id, label) {
      var el = document.getElementById(id);
      if (el && elIsVisible(el) && !el.disabled) return { el: el, label: label || normalizeSpace(el.textContent || id) };
      return null;
    }

    if (/^(back|previous|go back)$/.test(s)) {
      return btn('studentPasswordBack', 'Back') ||
        btn('studentLoginOtpBack', 'Back') ||
        btn('studentSignupOtpBack', 'Back') ||
        btn('studentSignupPwdBack', 'Back');
    }

    if (onPassword && /^(sign in|signin|submit|login|continue|next)$/.test(s)) {
      return btn('studentPasswordSubmit', 'Sign in') ||
        btn('loginpwdSubmit', 'Sign in') ||
        (function () {
          var el = document.querySelector('#loginpwd button[type="submit"], #loginpwd input[type="submit"]');
          return el && elIsVisible(el) ? { el: el, label: 'Sign in' } : null;
        })();
    }

    if (/^(sign in|signin|login)$/.test(s)) {
      return btn('studentPasswordSubmit', 'Sign in');
    }

    if (/^(continue|next|proceed|submit|send otp|verify)$/.test(s)) {
      if (/verify/.test(s)) {
        return btn('studentLoginVerifyOtp', 'Verify OTP') ||
          btn('studentSignupVerifyOtp', 'Verify OTP');
      }
      return btn('studentLoginContinueBtn', 'Continue') ||
        btn('studentSignupContinueBtn', 'Continue') ||
        btn('studentLoginVerifyOtp', 'Verify OTP') ||
        (function () {
          var el = document.querySelector(
            '#loginSignupForm button[type="submit"], #loginSignupForm .btn-primary, .login-page button[type="submit"]'
          );
          return el && elIsVisible(el) ? { el: el, label: normalizeSpace(el.textContent || 'Continue') } : null;
        })();
    }
    return null;
  }

  function collectLoginActionButtons() {
    var root = getActiveLoginRoot();
    if (!root) return [];
    var nodes = root.querySelectorAll(
      'button, a.btn, [role="button"], input[type="submit"], input[type="button"], .student-popup-btn'
    );
    var out = [];
    var seen = {};
    for (var i = 0; i < nodes.length && out.length < 12; i++) {
      var el = nodes[i];
      if (!el || el.disabled || !elIsVisible(el)) continue;
      if (el.classList && (el.classList.contains('student-popup-eye') || el.classList.contains('tt-speech-mic'))) continue;
      if (el.classList && el.classList.contains('profile-completion-close')) continue;
      var label = normalizeSpace(
        el.getAttribute('aria-label') || el.value || el.textContent || ''
      );
      if (!label || label.length > 40) continue;
      var key = normalizeSpeakLabel(label);
      if (!key || seen[key]) continue;
      seen[key] = true;
      out.push({ el: el, label: label, key: key });
    }
    return out;
  }

  /** “Enter email …”, “Enter password …”. Uses original speech for password casing. */
  function runLoginFillCommand(raw) {
    var text = String(raw || '').trim();
    if (!text) return false;
    var lower = text.toLowerCase().replace(/\s+/g, ' ').trim();

    // Continuation: previous turn was “Enter email” / “Enter password” with no value
    if (state.awaitLoginField === 'email' && isLoginUiOpen()) {
      if (/^(cancel|never ?mind|stop|back)$/.test(lower)) {
        state.awaitLoginField = null;
        setBarStatus('Cancelled — say Enter email or Continue');
        return true;
      }
      if (/^(enter|type|fill|set)\s+(?:the\s+)?(?:email|password)/.test(lower)) {
        state.awaitLoginField = null;
      } else if (!/^(continue|next|submit|sign in|signin|click|go |open |help|scroll)/.test(lower)) {
        var emailElAwait = findLoginIdentityInput();
        if (!emailElAwait) {
          state.awaitLoginField = null;
          setBarStatus('Open login first', 'err');
          return true;
        }
        var emailValAwait = normalizeSpokenIdentity(text);
        if (!emailValAwait || emailValAwait.length < 3) {
          setBarStatus('Say your email like name at gmail dot com', 'err');
          return true;
        }
        setInputValue(emailElAwait, emailValAwait, { noFocus: true });
        state.awaitLoginField = null;
        setBarStatus('Email set — say Continue');
        try { renderWidgetChips(); } catch (eA1) {}
        return true;
      } else {
        state.awaitLoginField = null;
      }
    }
    if (state.awaitLoginField === 'password' && isLoginUiOpen()) {
      if (/^(cancel|never ?mind|stop|back)$/.test(lower)) {
        state.awaitLoginField = null;
        setBarStatus('Cancelled — say Enter password or Sign in');
        return true;
      }
      if (/^(enter|type|fill|set)\s+(?:the\s+)?password/.test(lower)) {
        state.awaitLoginField = null;
      } else if (!/^(continue|next|submit|sign in|signin|click|go |open |help|scroll)/.test(lower)) {
        var pwdElAwait = findLoginPasswordInput();
        if (!pwdElAwait) {
          state.awaitLoginField = null;
          setBarStatus('Enter email and Continue first', 'err');
          return true;
        }
        var pwdValAwait = normalizeSpokenPassword(text);
        if (!pwdValAwait) {
          setBarStatus('Say your password now', 'err');
          return true;
        }
        setInputValue(pwdElAwait, pwdValAwait, { noFocus: true });
        state.awaitLoginField = null;
        setBarStatus('Password entered — say Sign in');
        try { renderWidgetChips(); } catch (eA2) {}
        return true;
      } else {
        state.awaitLoginField = null;
      }
    }

    // Bare “enter email” / “enter password” → wait for next utterance
    if (/^(?:enter|type|fill|set)?\s*(?:the\s+)?(?:email|e-mail|username|user name|mobile|login id)$/.test(lower) ||
        lower === 'email' || lower === 'e-mail') {
      if (!isLoginUiOpen() && !findLoginIdentityInput()) return false;
      if (!findLoginIdentityInput()) {
        setBarStatus('Open login first, then say Enter email', 'err');
        return true;
      }
      state.awaitLoginField = 'email';
      setBarStatus('OK — now say your email like name at gmail dot com');
      return true;
    }
    if (/^(?:enter|type|fill|set)?\s*(?:the\s+)?password$/.test(lower) || lower === 'password') {
      if (!isLoginUiOpen() && !findLoginPasswordInput()) return false;
      if (!findLoginPasswordInput()) {
        setBarStatus('Enter email and Continue first, then Enter password', 'err');
        return true;
      }
      state.awaitLoginField = 'password';
      setBarStatus('OK — now say your password');
      return true;
    }

    var emailM = lower.match(/^(?:enter|type|fill|set|my)?\s*(?:the\s+)?(?:email|e-mail|username|user name|mobile|login id|login)\s*(?:is|as|equals?)?\s*[:=]?\s+(.+)$/) ||
      lower.match(/^(?:email|e-mail|username|mobile)\s*[:=]\s*(.+)$/) ||
      lower.match(/^(?:email|e-mail)\s+(.+)$/);
    if (emailM) {
      var emailVal = normalizeSpokenIdentity(emailM[1]);
      if (!isLoginUiOpen() && !findLoginIdentityInput()) return false;
      var emailEl = findLoginIdentityInput();
      if (!emailEl) {
        setBarStatus('Open login first, then say Enter email …', 'err');
        return true;
      }
      if (!emailVal || /^(please|now|here)$/.test(emailVal)) {
        state.awaitLoginField = 'email';
        setBarStatus('Say your email like name at gmail dot com');
        return true;
      }
      setInputValue(emailEl, emailVal, { noFocus: true });
      state.awaitLoginField = null;
      setBarStatus('Email set — say Continue');
      try { renderWidgetChips(); } catch (e1) {}
      return true;
    }

    var pwdM = lower.match(/^(?:enter|type|fill|set|my)?\s*(?:the\s+)?password\s*(?:is|as|equals?)?\s*[:=]?\s+(.+)$/) ||
      lower.match(/^password\s*[:=]\s*(.+)$/) ||
      lower.match(/^password\s+(.+)$/);
    if (pwdM) {
      var pwdRaw = text.replace(/^(?:enter|type|fill|set|my)?\s*(?:the\s+)?password\s*(?:is|as|equals?)?\s*[:=]?\s+/i, '')
        .replace(/^password\s*[:=]?\s*/i, '');
      var pwdVal = normalizeSpokenPassword(pwdRaw);
      if (!isLoginUiOpen() && !findLoginPasswordInput()) return false;
      var pwdEl = findLoginPasswordInput();
      if (!pwdEl) {
        setBarStatus('Enter email and say Continue first, then Enter password …', 'err');
        return true;
      }
      if (!pwdVal) {
        state.awaitLoginField = 'password';
        setBarStatus('Say your password now');
        return true;
      }
      setInputValue(pwdEl, pwdVal, { noFocus: true });
      state.awaitLoginField = null;
      setBarStatus('Password entered — say Sign in');
      try { renderWidgetChips(); } catch (e2) {}
      return true;
    }

    return false;
  }

  function runSiteCommand(t) {
    // Normalize speech variants: "log in" → "login", collapse spaces
    t = String(t || '')
      .toLowerCase()
      .replace(/\blog\s+in\b/g, 'login')
      .replace(/\bsign\s*[- ]?\s*in\b/g, 'sign in')
      .replace(/\s+/g, ' ')
      .trim();

    if (/^(start listening|listen|resume)$/.test(t)) {
      startListening();
      return true;
    }
    if (/^(stop|stop listening|pause)$/.test(t)) {
      pauseListening();
      return true;
    }
    if (/^(exit|quit|close voice|turn off)$/.test(t)) {
      exitNav();
      return true;
    }
    if (/^(help|commands|show help|show commands)$/.test(t) || t.indexOf('voice command') !== -1) {
      refreshNavHelpUi({ forceHtml: true, open: true });
      var ctxHelp = detectPageContext();
      setBarStatus('Help for ' + (ctxHelp.label || 'this page'));
      return true;
    }
    if (/^(go home|home|open home)$/.test(t)) {
      global.location.href = '/';
      return true;
    }
    if (/^(go back|back|previous page)$/.test(t)) {
      // On login password/OTP step, Back returns to previous login step — not browser history
      if (isLoginUiOpen()) {
        var loginBack = resolveLoginActionButton('back');
        if (loginBack && loginBack.el) {
          try { loginBack.el.click(); } catch (eBack) {}
          setBarStatus('Back');
          try { renderWidgetChips(); } catch (eB2) {}
          return true;
        }
      }
      global.history.back();
      return true;
    }

    // —— Login actions without needing “Click …” ——
    if (isLoginUiOpen() && /^(continue|next|proceed|submit|sign in|signin|send otp|verify|verify otp)$/.test(t)) {
      var loginAct = resolveLoginActionButton(t);
      if (loginAct && loginAct.el) {
        try { loginAct.el.click(); } catch (eLa) {}
        setBarStatus('Clicked “' + loginAct.label + '”');
        setTimeout(function () { try { renderWidgetChips(); } catch (e3) {} }, 400);
        return true;
      }
    }

    // —— Scroll ——
    if (/^(go to top|scroll to top|scroll top|page top|top of (the )?page|scroll up to top)$/.test(t) ||
        t === 'top') {
      setBarStatus(scrollPage('top'));
      return true;
    }
    if (/^(go to bottom|scroll to bottom|scroll bottom|page bottom|bottom of (the )?page|scroll down to bottom)$/.test(t) ||
        t === 'bottom') {
      setBarStatus(scrollPage('bottom'));
      return true;
    }
    if (/^(scroll down|page down|move down)$/.test(t)) {
      setBarStatus(scrollPage('down'));
      return true;
    }
    if (/^(scroll up|page up|move up)$/.test(t)) {
      setBarStatus(scrollPage('up'));
      return true;
    }

    // —— Login (before generic "open …" so it never misses) ——
    if (/^(open login|login|sign in|signin|open sign in)$/.test(t)) {
      if (isLoginUiOpen()) {
        var already = resolveLoginActionButton(t === 'login' ? 'sign in' : t);
        if (already && already.el && /sign|submit/.test(normalizeSpeakLabel(t))) {
          try { already.el.click(); } catch (eAl) {}
          setBarStatus('Clicked “' + already.label + '”');
          return true;
        }
        setBarStatus('Login is already open — enter email, then Continue');
        return true;
      }
      var loginMsg = openLoginPopup();
      setBarStatus(loginMsg || 'Login not available on this page', loginMsg ? '' : 'err');
      return true;
    }

    // —— Top navigation menu ——
    if (/^(open menu|open navigation|show menu|open nav|hamburger|open hamburger|show navigation)$/.test(t)) {
      var openMsg = toggleTopMenu(true);
      setBarStatus(openMsg || 'Menu not available', openMsg ? '' : 'err');
      return true;
    }
    if (/^(close menu|close navigation|hide menu|close nav|hide navigation)$/.test(t)) {
      var closeMsg = toggleTopMenu(false);
      setBarStatus(closeMsg || 'Menu not available', closeMsg ? '' : 'err');
      return true;
    }
    if (/^(open search|show search|search)$/.test(t)) {
      var blogSearch = document.getElementById('blogSearchInput') ||
        document.querySelector('.js-blog-sidebar-search-input');
      if (blogSearch) {
        try { blogSearch.focus(); } catch (eF) {}
        setBarStatus('Blog search ready — say “Search for part time jobs”');
        return true;
      }
      var searchMsg = openSiteSearch();
      setBarStatus(searchMsg || 'Search not available', searchMsg ? '' : 'err');
      return true;
    }

    // —— Search for <query> (blog page search or site search) ——
    var searchFor = t.match(/^(?:search for|search|find|look for)\s+(.+)$/);
    if (searchFor) {
      var q = searchFor[1].replace(/^(blogs?|articles?|posts?)\s+(about|on|for)\s+/i, '').trim();
      if (q && !/^(menu|login|numbers)$/.test(q)) {
        var sMsg = runPageSearch(q);
        setBarStatus(sMsg || 'Search not available', sMsg ? '' : 'err');
        return true;
      }
    }

    if (/^(reload|refresh|reload page)$/.test(t)) {
      global.location.reload();
      return true;
    }
    if (/^(skip to content|main content|go to content)$/.test(t)) {
      var main = document.querySelector('main, #content, [role="main"], .std-shell-main');
      if (main) {
        try { main.setAttribute('tabindex', '-1'); main.focus(); } catch (e) {}
        main.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      setBarStatus('Skipped to content');
      return true;
    }

    // Link numbers before generic open/click handlers
    if (/^(show numbers|show link numbers|number links)$/.test(t)) {
      showLinkNumbers();
      return true;
    }
    if (/^(hide numbers|hide link numbers)$/.test(t)) {
      hideLinkNumbers();
      setBarStatus('Link numbers hidden');
      return true;
    }
    var goN = t.match(/^(?:go to|open|click)\s+(?:number\s+)?(\d+)$/);
    if (goN && state.linkNumbersOn) {
      var idx = parseInt(goN[1], 10) - 1;
      var link = state.numberedLinks[idx];
      if (link) {
        setBarStatus('Opening link ' + (idx + 1));
        link.click();
      } else {
        setBarStatus('No link number ' + goN[1], 'err');
      }
      return true;
    }

    // —— Open / go to top-nav item OR page content (blog titles, cards) ——
    var navSpeak = t.match(/^(?:open|go to|navigate to|show|read)\s+(.+)$/);
    if (navSpeak) {
      var spokenNav = navSpeak[1].replace(/^(the|a|an|blog|article|post)\s+/i, '').trim();
      // Skip if this is a known non-nav command prefix handled elsewhere
      if (!/^(login|sign in|signin|notebook|notes|home|menu|search|numbers|navigation|nav)$/.test(spokenNav) &&
          !/^\d+$/.test(spokenNav)) {
        var navHit = findBestTarget(spokenNav, collectTopNavTargets());
        if (!navHit) {
          navHit = findBestTarget(spokenNav, collectPageContentLinks());
        }
        if (navHit && navHit.el) {
          // On mobile, open menu first if link is in collapsed nav
          try {
            var inMenu = navHit.el.closest('#menu, .navbar-block, .navbar-collapse');
            if (inMenu && !isTopMenuOpen() && window.matchMedia &&
                window.matchMedia('(max-width: 991.98px)').matches) {
              toggleTopMenu(true);
            }
          } catch (eMenu) {}
          setTimeout(function () {
            try { navHit.el.click(); } catch (eClick) {
              try { global.location.href = navHit.el.href; } catch (e2) {}
            }
          }, 160);
          setBarStatus('Opening ' + navHit.label);
          return true;
        }
        setBarStatus('Could not find “' + spokenNav + '” on this page', 'err');
        return true;
      }
    }

    // —— Click action buttons ——
    var clickSpeak = t.match(/^(?:click|press|tap|hit)\s+(.+)$/);
    if (clickSpeak) {
      var spokenBtn = clickSpeak[1]
        .replace(/^(the|a|an|on)\s+/, '')
        .replace(/\s+button$/, '')
        .trim();
      if (/^\d+$/.test(spokenBtn)) {
        setBarStatus('Say “Show numbers” first, then “Go to ' + spokenBtn + '”', 'err');
        return true;
      }
      if (spokenBtn.length >= 2) {
        // Login UI: resolve Continue / Sign in / Back by active step first
        var loginHit = resolveLoginActionButton(spokenBtn);
        if (loginHit && loginHit.el) {
          try { loginHit.el.click(); } catch (eLh) {}
          setBarStatus('Clicked “' + loginHit.label + '”');
          setTimeout(function () { try { renderWidgetChips(); } catch (e4) {} }, 400);
          return true;
        }

        var aliasMap = {
          continue: ['continue', 'next', 'proceed'],
          next: ['next', 'continue'],
          save: ['save', 'save changes', 'save note'],
          submit: ['submit', 'sign in', 'signin', 'apply', 'send'],
          'sign in': ['sign in', 'signin', 'submit'],
          signin: ['sign in', 'signin', 'submit'],
          apply: ['apply', 'submit'],
          download: ['download', 'export'],
          cancel: ['cancel', 'close'],
          back: ['back', 'previous']
        };
        var buttons = collectLoginActionButtons().concat(collectActionButtons());
        var hit = findBestTarget(spokenBtn, buttons);
        if (!hit && aliasMap[spokenBtn]) {
          var aliases = aliasMap[spokenBtn];
          for (var ai = 0; ai < aliases.length && !hit; ai++) {
            hit = findBestTarget(aliases[ai], buttons);
          }
        }
        if (hit && hit.el) {
          try { hit.el.click(); } catch (eBtn) {}
          setBarStatus('Clicked “' + hit.label + '”');
          setTimeout(function () { try { renderWidgetChips(); } catch (e5) {} }, 300);
          return true;
        }
        setBarStatus('No button named “' + spokenBtn + '” on this page', 'err');
        return true;
      }
    }

    if (/^(open notebook|notebook|open notes)$/.test(t)) {
      var nb = document.getElementById('openParentNotebook') ||
        document.querySelector('[data-open-notebook], .open-notebook, #notebookFab');
      if (nb) nb.click();
      else {
        var drawer = document.getElementById('parentNotebookDrawer');
        if (drawer) {
          try { drawer.classList.add('is-open'); } catch (e2) {}
        } else {
          setBarStatus('Notebook not available on this page', 'err');
          return true;
        }
      }
      setBarStatus('Opening notebook');
      return true;
    }
    if (/(edit|open|change).*(contact|personal|profile|info)/.test(t) || t === 'edit contact') {
      var openBtn = document.getElementById('openPersonalInfoModal');
      if (openBtn) {
        openBtn.click();
        setTimeout(function () {
          if (global.TTVoiceNav && global.TTVoiceNav.activateFormById) {
            global.TTVoiceNav.activateFormById('personal');
          }
        }, 350);
        setBarStatus('Opened personal information');
      } else {
        setBarStatus('Edit contact is not available on this page', 'err');
      }
      return true;
    }
    return false;
  }

  function clearSilence() {
    if (state.silenceTimer) {
      clearTimeout(state.silenceTimer);
      state.silenceTimer = null;
    }
  }

  function armSilence() {
    clearSilence();
    // Give more time on login while dictating email/password
    var ms = SILENCE_MS;
    try {
      if (isLoginUiOpen() || state.awaitLoginField) ms = Math.max(ms, 12000);
    } catch (eSil) {}
    state.silenceTimer = setTimeout(function () {
      pauseListening();
    }, ms);
  }

  function stopCloudTracks() {
    try {
      if (state.mediaStream) {
        state.mediaStream.getTracks().forEach(function (tr) { tr.stop(); });
      }
    } catch (e) {}
    state.mediaStream = null;
  }

  function finishCloud() {
    clearSilence();
    var chunks = state.cloudChunks || [];
    var mime = (state.mediaRecorder && state.mediaRecorder.mimeType) || 'audio/webm';
    var rec = state.mediaRecorder;
    state.mediaRecorder = null;
    state.cloudChunks = null;
    stopCloudTracks();
    state.listening = false;
    syncFabListening();
    if (!chunks.length) {
      pauseListening();
      return;
    }
    setBarStatus('Transcribing… — please wait', 'wait');
    var transcribe = global.TTSpeechInput && global.TTSpeechInput.transcribeBlob;
    if (typeof transcribe !== 'function') {
      setBarStatus('Cloud helper missing', 'err');
      pauseListening();
      return;
    }
    transcribe(new Blob(chunks, { type: mime })).then(function (text) {
      if (text) handleUtterance(text);
      else pauseListening();
    }).catch(function (err) {
      setBarStatus((err && err.message) || 'Transcription failed', 'err');
      pauseListening();
    });
  }

  function destroyRecognition() {
    if (!state.recognition) return;
    var r = state.recognition;
    try { r.onstart = r.onerror = r.onend = r.onresult = null; } catch (e) {}
    try { r.abort(); } catch (e2) {}
    state.recognition = null;
  }

  function stopListening(hard) {
    state.wantListen = !hard && state.wantListen;
    clearSilence();
    state.ignoreEnd = true;
    if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
      try { state.mediaRecorder.stop(); } catch (e) { finishCloud(); }
    } else {
      destroyRecognition();
      stopCloudTracks();
    }
    state.listening = false;
    syncFabListening();
  }

  function pauseListening() {
    state.wantListen = false;
    setListenIntent(false);
    stopVoiceCue();
    stopListening(true);
    state.paused = true;
    setBarStatus('Mic paused — tap Start listening when ready', 'paused');
    syncStartListeningButtons();
  }

  function exitNav() {
    state.navOn = false;
    setPref(PREF_NAV, false);
    setListenIntent(false);
    stopVoiceCue();
    if (state.els.navToggle) state.els.navToggle.checked = false;
    stopListening(true);
    hideBar();
    hideLinkNumbers();
    state.paused = false;
    state.wantListen = false;
    setBarStatus('Voice Navigation off', 'ready');
    syncStartListeningButtons();
  }

  function startListening() {
    if (!state.navOn || !adminAllowsNav()) return;
    setListenIntent(true);
    state.wantListen = true;
    state.paused = false;
    function go() {
      if (canSpeakVoiceCues()) {
        setBarStatus('Your turn — Speak now', 'speak');
        if (!state.cueSpeaking) startListeningNow();
        return;
      }
      startListeningNow();
    }
    // Never block Speak now on settings HTTP — use last known admin flags
    go();
  }

  function startListeningNow() {
    if (!adminAllowsWidget() || !adminAllowsNav() || !state.navOn) return;
    if (state.busy) return;
    if (state.cueSpeaking) return;
    if (!canListen()) {
      updateMicAvailabilityUi();
      hideBar();
      return;
    }
    state.wantListen = true;
    state.paused = false;
    setListenIntent(true);
    // Keep Speak now UI — do not announce "Processing" while opening mic
    state.skipNextSpeakCue = true;
    state.uiPhase = 'speak';
    if (isCloud()) {
      startCloudListen();
      return;
    }
    startBrowserListen();
  }

  function startBrowserListen() {
    destroyRecognition();
    var Ctor = getSpeechCtor();
    if (!Ctor) {
      setBarStatus('Speech recognition not supported', 'err');
      return;
    }
    var rec = new Ctor();
    state.recognition = rec;
    // Same pattern as student notebook / TTVoiceNav: one utterance, then process
    rec.continuous = false;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    rec.lang = navigator.language || 'en-IN';
    rec.onstart = function () {
      state.listening = true;
      state.ignoreEnd = false;
      syncFabListening();
      setBarStatus('Your turn — Speak now', 'speak');
      setHeard('');
      armSilence();
      syncStartListeningButtons();
    };
    rec.onresult = function (ev) {
      if (state.busy) return;
      armSilence();
      var interim = '';
      var finalText = '';
      for (var i = ev.resultIndex; i < ev.results.length; i++) {
        var piece = (ev.results[i][0] && ev.results[i][0].transcript) || '';
        if (!piece) continue;
        if (ev.results[i].isFinal) finalText += (finalText ? ' ' : '') + piece;
        else interim = piece;
      }
      var shown = (finalText || interim || '').trim();
      if (shown) setHeard('“' + shown + '”');
      if (finalText) handleUtterance(finalText);
    };
    rec.onerror = function (ev) {
      var err = (ev && ev.error) || '';
      if (err === 'no-speech' || err === 'aborted') return;
      if (err === 'not-allowed' || err === 'service-not-allowed' || err === 'audio-capture') {
        state.micDenied = true;
        state.wantListen = false;
        setListenIntent(false);
        state.busy = false;
        setBarStatus('Mic not available', 'err');
        updateMicAvailabilityUi();
        hideBar();
        return;
      }
      setBarStatus('Mic error: ' + (err || 'unknown'), 'err');
    };
    rec.onend = function () {
      state.listening = false;
      syncFabListening();
      if (state.ignoreEnd || state.busy) return;
      // Restart listen loop until silence timer pauses us (notebook-style)
      if (state.wantListen && state.navOn) {
        setTimeout(function () {
          if (state.wantListen && state.navOn && !state.busy && !state.listening) {
            try { startListeningNow(); } catch (eRestart) { pauseListening(); }
          }
        }, 180);
      } else if (state.navOn) {
        pauseListening();
      }
    };
    try { rec.start(); } catch (eStart) {
      setBarStatus('Could not start listening', 'err');
    }
  }

  function startCloudListen() {
    if (!canMicHardware()) {
      setBarStatus('Microphone unavailable', 'err');
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      state.mediaStream = stream;
      state.cloudChunks = [];
      var mime = '';
      try {
        if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) mime = 'audio/webm;codecs=opus';
        else if (MediaRecorder.isTypeSupported('audio/webm')) mime = 'audio/webm';
        else if (MediaRecorder.isTypeSupported('audio/mp4')) mime = 'audio/mp4';
      } catch (e) {}
      var rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      state.mediaRecorder = rec;
      rec.ondataavailable = function (ev) {
        if (ev.data && ev.data.size) state.cloudChunks.push(ev.data);
      };
      rec.onstop = function () { finishCloud(); };
      rec.start(250);
      state.listening = true;
      syncFabListening();
      setBarStatus('Speak now', 'speak');
      setHeard('');
      armSilence();
      syncStartListeningButtons();
    }).catch(function () {
      state.micDenied = true;
      state.wantListen = false;
      setListenIntent(false);
      setBarStatus('Microphone permission denied', 'err');
      updateMicAvailabilityUi();
      hideBar();
    });
  }

  /* —— Declarative forms —— */
  function discoverDeclarativeForms() {
    if (!global.TTVoiceNav) return;
    var forms = document.querySelectorAll('[data-tt-voice-form]');
    for (var i = 0; i < forms.length; i++) {
      var root = forms[i];
      var id = root.getAttribute('data-tt-voice-form') || ('auto_' + i);
      if (root.dataset.ttVoiceBound === '1') continue;
      root.dataset.ttVoiceBound = '1';
      var fields = [];
      var nodes = root.querySelectorAll('[data-tt-voice-field]');
      for (var f = 0; f < nodes.length; f++) {
        var el = nodes[f];
        if (el.type === 'password' || el.type === 'hidden' || el.type === 'file') continue;
        if (!el.id) el.id = 'ttvw_f_' + id + '_' + f;
        var keys = (el.getAttribute('data-tt-voice-keys') || el.name || el.id || '')
          .split(',').map(function (s) { return s.trim(); }).filter(Boolean);
        fields.push({
          id: el.id,
          label: el.getAttribute('aria-label') || el.getAttribute('placeholder') || keys[0] || el.id,
          keys: keys,
          type: el.getAttribute('data-tt-voice-type') || (el.tagName === 'TEXTAREA' ? 'textarea' : (el.type || 'text')),
          required: !!el.required
        });
      }
      if (!fields.length) continue;
      global.TTVoiceNav.registerForm({
        id: id,
        form: root.id ? ('#' + root.id) : null,
        modal: root.getAttribute('data-tt-voice-modal') || null,
        fields: fields,
        onSave: function (done) {
          var btn = root.querySelector('[type="submit"], [data-tt-voice-save]');
          if (btn) btn.click();
          done('Saved');
        }
      });
    }
  }

  function ensureHeadlessNav() {
    if (!global.TTVoiceNav) return;
    var active = global.TTVoiceNav._active && global.TTVoiceNav._active();
    if (!active) {
      global.TTVoiceNav.attach({
        headless: true,
        forms: [],
        pageCommands: [],
        onStatus: function (text, kind) {
          if (state.navOn) setBarStatus(text, kind === 'err' ? 'err' : '');
        },
        onHeard: function (text) {
          if (state.navOn) setHeard(text);
        }
      });
    } else {
      // Prefer widget bar over profile green bar — always headless when widget is on
      try {
        active.headless = true;
        active.config = active.config || {};
        active.config.headless = true;
        active.config.onStatus = function (text, kind) {
          if (state.navOn) setBarStatus(text, kind === 'err' ? 'err' : '');
        };
        active.config.onHeard = function (text) {
          if (state.navOn) setHeard(text);
        };
      } catch (e) {}
      hideEngineNavBar();
    }
    discoverDeclarativeForms();
  }

  function registerBuiltinForms() {
    if (!global.TTVoiceNav || state.formsRegistered) return;
    state.formsRegistered = true;
    // Login popup identity fields (password skipped)
    var loginForm = document.getElementById('studentLoginForm') ||
      document.querySelector('.student-login-popup form, #loginForm');
    if (loginForm) {
      var idField = loginForm.querySelector('[data-tt-speech="identity"], input[name="username"], input[name="email"], input[name="mobile"]');
      if (idField) {
        if (!idField.id) idField.id = 'ttvw_login_identity';
        global.TTVoiceNav.registerForm({
          id: 'login',
          form: loginForm.id ? ('#' + loginForm.id) : null,
          fields: [
            {
              id: idField.id,
              label: 'Login ID',
              keys: ['username', 'email', 'mobile', 'login', 'id'],
              type: idField.getAttribute('data-tt-speech') === 'identity' ? 'text' : (idField.type || 'text'),
              required: true
            }
          ],
          onSave: function (done) {
            var btn = loginForm.querySelector('[type="submit"], .student-popup-submit');
            if (btn) btn.click();
            done('Submitting login…');
          }
        });
      }
    }
  }

  function mountDom() {
    if (state.mounted) return;
    state.mounted = true;

    var wrap = document.createElement('div');
    wrap.id = 'tt-voice-fab-wrap';
    wrap.innerHTML = [
      '<div id="tt-voice-panel" role="dialog" aria-label="Voice settings">',
      '  <div class="ttvw-panel-head">',
      '    <h3>Voice</h3>',
      '    <button type="button" class="ttvw-sr-btn" data-ttvw-sr-speak hidden aria-hidden="true" title="Read page aloud" aria-label="Read page aloud">',
      '      <i class="bx bx-volume-full" aria-hidden="true"></i>',
      '    </button>',
      '  </div>',
      '  <div class="ttvw-admin" data-ttvw-admin></div>',
      '  <div class="ttvw-row" data-ttvw-nav-row>',
      '    <span>Voice Navigation</span>',
      '    <label class="ttvw-switch"><input type="checkbox" data-ttvw-nav /><span></span></label>',
      '  </div>',
      '  <div class="ttvw-row" data-ttvw-cues-row>',
      '    <span>Speak prompts</span>',
      '    <label class="ttvw-switch"><input type="checkbox" data-ttvw-cues checked /><span></span></label>',
      '  </div>',
      '  <div class="ttvw-row" data-ttvw-talk-row>',
      '    <span>Talk &amp; Type</span>',
      '    <label class="ttvw-switch"><input type="checkbox" data-ttvw-talk /><span></span></label>',
      '  </div>',
      '  <div class="ttvw-row" data-ttvw-sr-row>',
      '    <span>Screen Reader</span>',
      '    <label class="ttvw-switch"><input type="checkbox" data-ttvw-sr /><span></span></label>',
      '  </div>',
      '  <div class="ttvw-sr-controls" data-ttvw-sr-controls hidden>',
      '    <div class="ttvw-sr-ctrl">',
      '      <label for="ttvw-sr-rate">Speed</label>',
      '      <input id="ttvw-sr-rate" type="range" min="0.5" max="2" step="0.05" data-ttvw-sr-rate />',
      '      <span data-ttvw-sr-rate-val>1.00x</span>',
      '    </div>',
      '    <div class="ttvw-sr-ctrl">',
      '      <label for="ttvw-sr-vol">Volume</label>',
      '      <input id="ttvw-sr-vol" type="range" min="0" max="1" step="0.05" data-ttvw-sr-vol />',
      '      <span data-ttvw-sr-vol-val>100%</span>',
      '    </div>',
      '  </div>',
      '  <div class="ttvw-actions">',
      '    <button type="button" class="primary" data-ttvw-start>Start listening</button>',
      '    <button type="button" data-ttvw-help>Help</button>',
      '  </div>',
      '</div>',
      '<button type="button" id="tt-voice-fab" aria-label="Voice controls" title="Voice">',
      '  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2z"/></svg>',
      '</button>'
    ].join('');

    var bar = document.createElement('div');
    bar.id = 'tt-voice-bar';
    bar.innerHTML = [
      '<div class="ttvw-bar-inner">',
      '  <div class="ttvw-bar-prompt is-ready mic-off" data-ttvw-prompt>',
      '    <span class="ttvw-mic-icon is-off" data-ttvw-mic-icon role="img" aria-label="Microphone off" title="Microphone off">',
      '      <i class="bx bx-microphone-off" aria-hidden="true"></i>',
      '    </span>',
      '    <span class="ttvw-prompt-badge" data-ttvw-prompt-badge>',
      '      <i class="bx bx-microphone-off" aria-hidden="true"></i><span>MIC OFF</span>',
      '    </span>',
      '    <div class="ttvw-prompt-body">',
      '      <div class="ttvw-bar-status" data-ttvw-status>Voice Navigation</div>',
      '      <div class="ttvw-bar-hint" data-ttvw-hint>Tap Start listening to begin, then speak or use the buttons.</div>',
      '    </div>',
      '  </div>',
      '  <div class="ttvw-bar-heard is-empty" data-ttvw-heard></div>',
      '  <div class="ttvw-chips" data-ttvw-chips></div>',
      '  <div class="ttvw-bar-actions">',
      '    <button type="button" data-ttvw-bar-start>Start listening</button>',
      '    <button type="button" data-ttvw-bar-stop>Stop / Pause mic</button>',
      '    <button type="button" data-ttvw-bar-help>Help</button>',
      '    <button type="button" data-ttvw-bar-exit>Exit</button>',
      '  </div>',
      '  <div id="tt-voice-help"></div>',
      '</div>'
    ].join('');

    document.body.appendChild(wrap);
    document.body.appendChild(bar);
    syncBottomStack();
    try {
      global.addEventListener('resize', syncBottomStack);
      var cookie = document.getElementById('eu-cookie-consent');
      if (cookie && global.MutationObserver) {
        new MutationObserver(syncBottomStack).observe(cookie, {
          attributes: true, attributeFilter: ['style', 'class'], childList: true, subtree: true
        });
      }
      var accept = document.getElementById('eu-cookie-consent-accept');
      if (accept) accept.addEventListener('click', function () {
        setTimeout(syncBottomStack, 50);
        setTimeout(syncBottomStack, 400);
      });
    } catch (eStack) {}

    state.els = {
      wrap: wrap,
      panel: wrap.querySelector('#tt-voice-panel'),
      fab: wrap.querySelector('#tt-voice-fab'),
      adminLine: wrap.querySelector('[data-ttvw-admin]'),
      navToggle: wrap.querySelector('[data-ttvw-nav]'),
      cuesToggle: wrap.querySelector('[data-ttvw-cues]'),
      talkToggle: wrap.querySelector('[data-ttvw-talk]'),
      srToggle: wrap.querySelector('[data-ttvw-sr]'),
      srBtn: wrap.querySelector('[data-ttvw-sr-speak]'),
      srControls: wrap.querySelector('[data-ttvw-sr-controls]'),
      srRate: wrap.querySelector('[data-ttvw-sr-rate]'),
      srVol: wrap.querySelector('[data-ttvw-sr-vol]'),
      srRateVal: wrap.querySelector('[data-ttvw-sr-rate-val]'),
      srVolVal: wrap.querySelector('[data-ttvw-sr-vol-val]'),
      navRow: wrap.querySelector('[data-ttvw-nav-row]'),
      cuesRow: wrap.querySelector('[data-ttvw-cues-row]'),
      talkRow: wrap.querySelector('[data-ttvw-talk-row]'),
      srRow: wrap.querySelector('[data-ttvw-sr-row]'),
      bar: bar,
      status: bar.querySelector('[data-ttvw-status]'),
      heard: bar.querySelector('[data-ttvw-heard]'),
      prompt: bar.querySelector('[data-ttvw-prompt]'),
      promptBadge: bar.querySelector('[data-ttvw-prompt-badge]'),
      promptHint: bar.querySelector('[data-ttvw-hint]'),
      micIcon: bar.querySelector('[data-ttvw-mic-icon]'),
      chips: bar.querySelector('[data-ttvw-chips]'),
      help: bar.querySelector('#tt-voice-help')
    };

    state.els.fab.addEventListener('click', function () {
      if (!canListen()) {
        updateMicAvailabilityUi();
        // Allow Talk & Type settings only — never enable Voice Navigation without mic
        state.panelOpen = !state.panelOpen;
        state.els.panel.classList.toggle('is-open', state.panelOpen);
        if (state.panelOpen) updateMicAvailabilityUi();
        return;
      }
      state.panelOpen = !state.panelOpen;
      state.els.panel.classList.toggle('is-open', state.panelOpen);
      if (state.panelOpen) updateMicAvailabilityUi();
    });

    state.els.navToggle.addEventListener('change', function () {
      if (!adminAllowsNav() || !canListen()) {
        state.els.navToggle.checked = false;
        state.navOn = false;
        hideBar();
        syncStartListeningButtons();
        updateMicAvailabilityUi();
        return;
      }
      state.navOn = !!state.els.navToggle.checked;
      setPref(PREF_NAV, state.navOn);
      if (state.navOn) {
        showBar();
        setListenIntent(true);
        state.wantListen = true;
        startListening();
      } else {
        setListenIntent(false);
        exitNav();
        syncStartListeningButtons();
      }
    });

    if (state.els.cuesToggle) {
      state.els.cuesToggle.addEventListener('change', function () {
        setVoiceCuesOn(!!state.els.cuesToggle.checked);
      });
    }

    state.els.talkToggle.addEventListener('change', function () {
      if (!adminAllowsTalk()) {
        state.els.talkToggle.checked = false;
        return;
      }
      state.talkOn = !!state.els.talkToggle.checked;
      setPref(PREF_TALK, state.talkOn);
      if (global.TTSpeechInput) {
        try {
          if (typeof global.TTSpeechInput.stopAll === 'function' && !state.talkOn) {
            global.TTSpeechInput.stopAll();
          }
          global.TTSpeechInput.enhance(document);
        } catch (e) {}
      }
    });

    if (state.els.srToggle) {
      state.els.srToggle.addEventListener('change', function () {
        if (!canScreenReader()) {
          state.els.srToggle.checked = false;
          setScreenReaderOn(false);
          return;
        }
        setScreenReaderOn(!!state.els.srToggle.checked);
      });
    }
    if (state.els.srBtn) {
      state.els.srBtn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        toggleScreenReaderSpeak();
      });
    }
    if (state.els.srRate) {
      state.els.srRate.addEventListener('input', function () {
        if (global.TTScreenReader && typeof global.TTScreenReader.setRate === 'function') {
          global.TTScreenReader.setRate(state.els.srRate.value, true);
        }
        syncScreenReaderUi();
      });
    }
    if (state.els.srVol) {
      state.els.srVol.addEventListener('input', function () {
        if (global.TTScreenReader && typeof global.TTScreenReader.setVolume === 'function') {
          global.TTScreenReader.setVolume(state.els.srVol.value, true);
        }
        syncScreenReaderUi();
      });
    }
    try {
      global.addEventListener('tt-voice-screen-reader', function () {
        syncScreenReaderUi();
      });
    } catch (eSrListen) {}

    function bindStart(btn) {
      if (!btn) return;
      btn.addEventListener('click', function () {
        if (!canListen()) {
          updateMicAvailabilityUi();
          hideBar();
          return;
        }
        if (state.busy) return;
        // Do not auto-enable Voice Navigation — only listen when toggle is on
        if (!state.navOn || !adminAllowsNav()) {
          syncStartListeningButtons();
          return;
        }
        setHeard('');
        setListenIntent(true);
        showBar();
        startListening();
      });
    }
    bindStart(wrap.querySelector('[data-ttvw-start]'));
    bindStart(bar.querySelector('[data-ttvw-bar-start]'));

    bar.querySelector('[data-ttvw-bar-stop]').addEventListener('click', function () {
      pauseListening();
    });
    bar.querySelector('[data-ttvw-bar-exit]').addEventListener('click', function () {
      exitNav();
    });
    function openHelp() {
      if (!state.els.help) return;
      var isOpen = state.els.help.classList.contains('is-open');
      if (isOpen) {
        state.els.help.classList.remove('is-open');
        setBarStatus('Help closed');
      } else {
        // Always rebuild from the page the user is on right now
        refreshNavHelpUi({ forceHtml: true, open: true });
        var ctx = detectPageContext();
        setBarStatus('Help for ' + (ctx.label || 'this page'));
      }
      try { renderWidgetChips(); } catch (eH) {}
    }
    wrap.querySelector('[data-ttvw-help]').addEventListener('click', openHelp);
    bar.querySelector('[data-ttvw-bar-help]').addEventListener('click', openHelp);
  }

  function onSettings(detail, opts) {
    opts = opts || {};
    // Merge so a partial payload never wipes widget_enabled / nav_enabled
    var incoming = detail || {};
    var prev = state.settings || {};
    state.settings = {
      ok: true,
      mode: incoming.mode != null ? incoming.mode : (prev.mode || global.TT_VOICE_TO_TEXT_MODE || 'browser'),
      enabled: incoming.enabled != null ? incoming.enabled : (prev.enabled !== false),
      widget_enabled: incoming.widget_enabled != null ? incoming.widget_enabled :
        (prev.widget_enabled != null ? prev.widget_enabled : global.TT_VOICE_WIDGET_ENABLED !== false),
      nav_enabled: incoming.nav_enabled != null ? incoming.nav_enabled :
        (prev.nav_enabled != null ? prev.nav_enabled : global.TT_VOICE_NAV_ENABLED !== false),
      talk_type_enabled: incoming.talk_type_enabled != null ? incoming.talk_type_enabled :
        (prev.talk_type_enabled != null ? prev.talk_type_enabled : global.TT_VOICE_TALK_TYPE_ENABLED !== false),
      link_numbers_enabled: incoming.link_numbers_enabled != null ? incoming.link_numbers_enabled :
        (prev.link_numbers_enabled != null ? prev.link_numbers_enabled : global.TT_VOICE_LINK_NUMBERS_ENABLED !== false),
      nav_default_on: incoming.nav_default_on != null ? incoming.nav_default_on :
        (prev.nav_default_on != null ? prev.nav_default_on : !!global.TT_VOICE_NAV_DEFAULT_ON),
      talk_type_default_on: incoming.talk_type_default_on != null ? incoming.talk_type_default_on :
        (prev.talk_type_default_on != null ? prev.talk_type_default_on : !!global.TT_VOICE_TALK_TYPE_DEFAULT_ON)
    };
    // Soft after first init so background settings polls don't restart/pause the mic
    var soft = opts.soft != null ? !!opts.soft : !!state._settingsReady;
    applyVisibility({ soft: soft });
    state._settingsReady = true;
    ensureHeadlessNav();
    registerBuiltinForms();
  }

  function init() {
    if (pathExcluded()) return;
    if (document.body && document.body.getAttribute('data-tt-voice-widget') === '0') return;

    mountDom();

    try {
      global.addEventListener('tt-voice-settings', function (ev) {
        onSettings(ev.detail, { soft: true });
      });
    } catch (e) {}

    if (global.TTSpeechInput && typeof global.TTSpeechInput.startVoiceSettingsWatcher === 'function') {
      global.TTSpeechInput.startVoiceSettingsWatcher();
      global.TTSpeechInput.refreshVoiceSettings(true).then(function (data) {
        onSettings(data || global.TT_VOICE_SETTINGS, { soft: false });
      });
    } else {
      onSettings(global.TT_VOICE_SETTINGS || {
        ok: true,
        mode: global.TT_VOICE_TO_TEXT_MODE || 'browser',
        enabled: global.TT_VOICE_TO_TEXT_ENABLED !== false,
        widget_enabled: global.TT_VOICE_WIDGET_ENABLED !== false,
        nav_enabled: global.TT_VOICE_NAV_ENABLED !== false,
        talk_type_enabled: global.TT_VOICE_TALK_TYPE_ENABLED !== false,
        link_numbers_enabled: global.TT_VOICE_LINK_NUMBERS_ENABLED !== false,
        nav_default_on: !!global.TT_VOICE_NAV_DEFAULT_ON,
        talk_type_default_on: !!global.TT_VOICE_TALK_TYPE_DEFAULT_ON
      }, { soft: false });
    }

    // Late forms (login popup)
    setTimeout(function () {
      ensureHeadlessNav();
      registerBuiltinForms();
      discoverDeclarativeForms();
    }, 800);

    // Resume after full navigation / bfcache restore
    try {
      global.addEventListener('pageshow', function () {
        if (pathExcluded()) return;
        state.lastHelpContextKey = '';
        try { refreshNavHelpUi({ forceHtml: true }); } catch (eRef) {}
        if (!state.navOn || !canListen() || !getListenIntent()) return;
        if (state.listening || state.busy) return;
        scheduleResumeListening('Back on page — resuming Speak now…');
      });
      global.addEventListener('popstate', function () {
        state.lastHelpContextKey = '';
        scheduleNavHelpRefresh();
      });
    } catch (ePage) {}

    watchPageContextChanges();
  }

  global.TTVoiceWidget = {
    init: init,
    isExcludedPath: pathExcluded,
    startListening: startListening,
    stopListening: function () { pauseListening(); },
    registerForm: function (cfg) {
      ensureHeadlessNav();
      if (global.TTVoiceNav) return global.TTVoiceNav.registerForm(cfg);
    },
    _state: function () { return state; }
  };

  try {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init);
    } else {
      setTimeout(init, 0);
    }
  } catch (eBoot) {}
})(typeof window !== 'undefined' ? window : this);
