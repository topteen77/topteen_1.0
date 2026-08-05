/**
 * TopTeen speech-to-text for form inputs.
 * Port of the proven parent-notebook voice engine
 * (templates/template20/parents/includes/parent_notebook_drawer.html)
 * adapted for short login/signup fields.
 *
 * Usage:
 *   TTSpeechInput.enhance(rootEl);
 *   TTSpeechInput.stopAll();
 *   TTSpeechInput.bind(inputEl, { mode: 'identity'|'password'|'text' });
 */
(function (global) {
  'use strict';

  var active = null;
  var isAndroid = /Android/i.test((typeof navigator !== 'undefined' && navigator.userAgent) || '');
  var isDesktop = !isAndroid && !/iPhone|iPad|iPod/i.test((typeof navigator !== 'undefined' && navigator.userAgent) || '');
  var SILENCE_MS = 4000;

  function pageHost() {
    try { return (global.location && global.location.hostname) || ''; } catch (e) { return ''; }
  }

  function pageOrigin() {
    try { return (global.location && global.location.origin) || ''; } catch (e) { return ''; }
  }

  function isLocalDevHost(h) {
    h = h || pageHost();
    if (!h) return false;
    if (h === 'localhost' || h === '127.0.0.1' || h === '::1') return true;
    if (h.endsWith('.localhost')) return true;
    return /^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[0-1])\.)/.test(h);
  }

  function getSpeechRecognitionCtor() {
    try {
      return global.SpeechRecognition || global.webkitSpeechRecognition || null;
    } catch (e) {
      return null;
    }
  }

  /**
   * Chrome secure-context rules (why LAN IP fails):
   * - http://localhost / http://127.0.0.1  → secure context → mic/speech OK
   * - http://10.x / http://192.168.x       → NOT secure → browser blocks mic
   * Our code cannot override that; user must use localhost, HTTPS, or Chrome flag.
   */
  function insecureContextBlocked() {
    try {
      return global.isSecureContext === false;
    } catch (e) {
      return false;
    }
  }

  function speechApiPresent() {
    return !!getSpeechRecognitionCtor();
  }

  function canUseSpeechNow() {
    // Need the API object AND a secure context (or Chrome treating origin as secure)
    if (!speechApiPresent()) return false;
    if (insecureContextBlocked()) return false;
    return true;
  }

  function voiceFeatureEnabled() {
    try {
      if (typeof global.TT_VOICE_TO_TEXT_ENABLED !== 'undefined' && !global.TT_VOICE_TO_TEXT_ENABLED) {
        return false;
      }
    } catch (e) {}
    return true;
  }

  function getSpeechProbeCache() {
    try { return global.sessionStorage.getItem('tt_voice_stt_ok'); } catch (e) { return null; }
  }

  function setSpeechProbeCache(ok) {
    try { global.sessionStorage.setItem('tt_voice_stt_ok', ok ? '1' : '0'); } catch (e) {}
  }

  function isSupported() {
    return voiceFeatureEnabled() && canUseSpeechNow();
  }

  function localDevHelpMessage() {
    var host = pageHost();
    var origin = pageOrigin() || ('http://' + host + ':8002');
    if (host === 'localhost' || host === '127.0.0.1' || host === '::1') {
      return 'Voice needs Chrome/Edge with mic permission. Allow microphone for this site, then tap mic again.';
    }
    if (isLocalDevHost(host)) {
      return 'Chrome blocks microphone on http://' + host + ' (not a secure context). ' +
        'Use http://localhost:8002 on this PC, or HTTPS. ' +
        'Or in Chrome: chrome://flags/#unsafely-treat-insecure-origin-as-secure → add ' +
        origin + ' → Relaunch.';
    }
    return 'Voice typing needs HTTPS (secure context). Open the HTTPS site in Chrome, then tap mic.';
  }

  function normSpeech(s) {
    return String(s || '').replace(/\s+/g, ' ').trim();
  }

  function joinParts(a, b) {
    a = (a || '').replace(/\s+$/, '');
    b = (b || '').replace(/^\s+/, '');
    if (!a) return b;
    if (!b) return a;
    return a + ' ' + b;
  }

  // Append speech without stuttering (handles echoes + cumulative chunks).
  function appendUniqueSpeech(existing, piece) {
    var c = normSpeech(existing);
    var p = normSpeech(piece);
    if (!p) return c;
    if (!c) return p;
    var cL = c.toLowerCase();
    var pL = p.toLowerCase();
    if (cL === pL || cL.endsWith(' ' + pL) || cL.endsWith(pL)) return c;
    if (pL.startsWith(cL)) return p;
    if (cL.startsWith(pL)) return c;
    var max = Math.min(c.length, p.length);
    for (var n = max; n >= 3; n--) {
      if (cL.slice(-n) === pL.slice(0, n)) {
        return normSpeech(c + p.slice(n));
      }
    }
    return joinParts(c, p);
  }

  var WORD_TO_DIGIT = {
    zero: '0', oh: '0', o: '0', one: '1', two: '2', three: '3', four: '4',
    five: '5', six: '6', seven: '7', eight: '8', nine: '9'
  };

  function spokenWordsToDigits(text) {
    var words = String(text || '').toLowerCase().split(/[\s\-]+/).filter(Boolean);
    if (!words.length) return '';
    var digits = '';
    for (var i = 0; i < words.length; i++) {
      var w = words[i].replace(/[^a-z0-9]/g, '');
      if (/^\d$/.test(w)) { digits += w; continue; }
      if (WORD_TO_DIGIT[w] == null) return '';
      digits += WORD_TO_DIGIT[w];
    }
    return digits;
  }

  /** Normalize spoken email / mobile for login & signup identity fields. */
  function normalizeIdentity(text) {
    var t = normSpeech(text);
    if (!t) return '';
    t = t.replace(/\s+at\s+the\s+rate\s+/gi, '@');
    t = t.replace(/\s+at\s+/gi, '@');
    t = t.replace(/\s+dot\s+/gi, '.');
    t = t.replace(/\s+underscore\s+/gi, '_');
    var digitsOnly = t.replace(/[\s\-().]/g, '');
    if (/^\+?\d{8,15}$/.test(digitsOnly)) {
      return digitsOnly.replace(/^\+91/, '').replace(/^0/, '');
    }
    // "nine eight seven …" → 987…
    var spoken = spokenWordsToDigits(t);
    if (/^\d{8,15}$/.test(spoken)) {
      return spoken.replace(/^91/, '').replace(/^0/, '');
    }
    if (t.indexOf('@') !== -1) {
      t = t.replace(/\s*@\s*/g, '@').replace(/\s*\.\s*/g, '.').replace(/\s+/g, '');
    }
    return t;
  }

  function normalizeByMode(text, mode) {
    if (mode === 'identity') return normalizeIdentity(text);
    if (mode === 'password') return String(text || '').replace(/\s+/g, '');
    return normSpeech(text);
  }

  function errorMessageForSpeech(err) {
    if (err === 'network') {
      return 'Voice engine error. Try Google Chrome, allow mic, or type instead.';
    }
    if (err === 'not-allowed' || err === 'service-not-allowed') {
      return 'Microphone permission blocked. Allow mic access, then tap mic again.';
    }
    if (err === 'audio-capture') return 'No microphone found. You can still type.';
    if (err === 'language-not-supported') return 'Voice language not supported.';
    return 'Could not use microphone. Tap mic to try again.';
  }

  function flashTip(state, msg, kind) {
    if (!state || !state.input) return;
    var wrap = state.input.closest('.student-popup-input-wrap, .tt-speech-wrap') || state.input.parentElement;
    if (!wrap) return;
    var tip = wrap.querySelector('.tt-speech-tip');
    if (!tip) {
      tip = document.createElement('p');
      tip.className = 'tt-speech-tip';
      tip.setAttribute('role', 'status');
      wrap.appendChild(tip);
    }
    tip.textContent = msg || '';
    tip.classList.toggle('is-visible', !!msg);
    tip.classList.toggle('is-err', kind === 'is-err');
    tip.classList.toggle('is-ok', kind === 'is-ok');
    if (state.tipTimer) clearTimeout(state.tipTimer);
    if (msg) {
      state.tipTimer = setTimeout(function () {
        // Keep listening tip while active
        if (state.wantListening && kind !== 'is-err') return;
        tip.textContent = '';
        tip.classList.remove('is-visible', 'is-err', 'is-ok');
      }, kind === 'is-err' ? 6000 : 4500);
    }
  }

  function setMicUi(state, listening) {
    if (!state || !state.micBtn || state.micUnavailable || state.micBtn.hidden) return;
    state.micBtn.classList.toggle('is-listening', !!listening);
    state.micBtn.setAttribute('aria-pressed', listening ? 'true' : 'false');
    var icon = state.micBtn.querySelector('i');
    if (icon) icon.className = listening ? 'bx bx-stop-circle' : 'bx bx-microphone';
    if (state.input) state.input.classList.toggle('is-speech-listening', !!listening);
    state.micBtn.setAttribute('title', listening ? 'Stop listening' : 'Speak to fill');
    state.micBtn.setAttribute('aria-label', listening ? 'Stop listening' : 'Speak to fill');
  }

  function writeSpeechToBox(state, interim) {
    if (!state || !state.input) return;
    var text;
    if (isAndroid) {
      text = joinParts(state.sessionBase, state.androidCommitted);
    } else {
      text = joinParts(state.speechPrefix, joinParts(state.speechFinal, interim || ''));
    }
    state.input.value = normalizeByMode(text, state.mode);
    try {
      var ev;
      if (typeof Event === 'function') ev = new Event('input', { bubbles: true });
      else if (global.document && global.document.createEvent) {
        ev = global.document.createEvent('Event');
        ev.initEvent('input', true, true);
      }
      if (ev) state.input.dispatchEvent(ev);
    } catch (eDisp) {}
    try {
      state.input.focus({ preventScroll: true });
      var len = state.input.value.length;
      if (typeof state.input.setSelectionRange === 'function') {
        state.input.setSelectionRange(len, len);
      }
    } catch (e) {}
  }

  function commitSpeechToPrefix(state) {
    if (!state) return;
    if (isAndroid) {
      state.speechPrefix = joinParts(state.sessionBase, state.androidCommitted);
      state.speechFinal = '';
      writeSpeechToBox(state, '');
      return;
    }
    if (!state.speechFinal) return;
    state.speechPrefix = joinParts(state.speechPrefix, state.speechFinal);
    state.speechFinal = '';
    writeSpeechToBox(state, '');
  }

  function resetSpeechSessionFromBox(state) {
    state.sessionBase = state.input ? state.input.value : '';
    state.androidCommitted = '';
    state.speechPrefix = state.sessionBase;
    state.speechFinal = '';
    state.networkRetryUsed = false;
    state.ignoreEndRestart = false;
  }

  function clearSilenceTimer(state) {
    if (state.silenceTimer) {
      clearTimeout(state.silenceTimer);
      state.silenceTimer = null;
    }
  }

  function clearRestartTimer(state) {
    if (state.restartTimer) {
      clearTimeout(state.restartTimer);
      state.restartTimer = null;
    }
  }

  function armSilenceTimer(state) {
    clearSilenceTimer(state);
    if (!state.wantListening) return;
    state.silenceTimer = setTimeout(function () {
      state.silenceTimer = null;
      if (!state.wantListening) return;
      stopListening(state);
      flashTip(state, 'Paused. Tap mic to speak more.', 'is-ok');
    }, SILENCE_MS);
  }

  function destroyRecognition(state) {
    if (!state || !state.recognition) return;
    var r = state.recognition;
    try { r.onstart = null; } catch (e) {}
    try { r.onerror = null; } catch (e2) {}
    try { r.onend = null; } catch (e3) {}
    try { r.onresult = null; } catch (e4) {}
    try { r.abort(); } catch (e5) {}
    state.recognition = null;
  }

  function markSpeechBroken(state, message) {
    try { console.warn('[tt-speech] unavailable:', message || 'unknown'); } catch (e) {}
    setSpeechProbeCache(false);
    if (state) {
      clearTimeout(state.tipTimer);
      flashTip(state, '');
    }
    hideMic(state);
  }

  function setMicUnavailable(state, message) {
    // Hide broken mic; do not leave a disabled control or long error tip.
    markSpeechBroken(state, message || 'microphone unavailable');
  }

  function setMicAvailable(state) {
    if (!state || !state.micBtn) return;
    state.micUnavailable = false;
    state.micBtn.hidden = false;
    state.micBtn.removeAttribute('hidden');
    state.micBtn.style.display = 'inline-flex';
    state.micBtn.classList.remove('is-unavailable', 'is-disabled', 'is-listening');
    state.micBtn.setAttribute('aria-disabled', 'false');
    state.micBtn.setAttribute('aria-hidden', 'false');
    state.micBtn.setAttribute('title', 'Speak to fill');
    state.micBtn.setAttribute('aria-label', 'Speak to fill');
    var icon = state.micBtn.querySelector('i');
    if (icon) icon.className = 'bx bx-microphone';
  }

  function hideMic(state) {
    if (!state || !state.micBtn) return;
    state.micUnavailable = true;
    state.wantListening = false;
    clearSilenceTimer(state);
    clearRestartTimer(state);
    destroyRecognition(state);
    state.micBtn.hidden = true;
    state.micBtn.setAttribute('aria-hidden', 'true');
    state.micBtn.classList.remove('is-listening', 'is-disabled', 'is-unavailable');
    state.micBtn.style.display = 'none';
    if (state.input) {
      state.input.classList.remove('has-speech', 'is-speech-listening');
      var wrap = state.input.closest('.student-popup-input-wrap');
      if (wrap) wrap.classList.remove('has-speech', 'has-eye-speech');
    }
    if (active === state) active = null;
  }

  function stopListening(state) {
    if (!state) return;
    state.wantListening = false;
    state.ignoreEndRestart = true;
    clearSilenceTimer(state);
    clearRestartTimer(state);
    if (!state.micUnavailable && state.micBtn && !state.micBtn.hidden) setMicUi(state, false);
    else if (state.micBtn) {
      state.micBtn.classList.remove('is-listening');
      if (state.input) state.input.classList.remove('is-speech-listening');
    }
    if (state.recognition) {
      try { state.recognition.stop(); } catch (e) {}
      try { state.recognition.abort(); } catch (e2) {}
    }
    commitSpeechToPrefix(state);
    if (active === state) active = null;
  }

  function stopAll() {
    if (active) stopListening(active);
  }

  function bindRecognitionHandlers(state) {
    var recognition = state.recognition;
    if (!recognition) return;

    recognition.onstart = function () {
      if (state.micUnavailable) return;
      state.ignoreEndRestart = false;
      setSpeechProbeCache(true);
      setMicUi(state, true);
      flashTip(state, 'Listening… pause 4s to stop, or tap mic', 'is-ok');
      armSilenceTimer(state);
    };

    recognition.onerror = function (ev) {
      var err = (ev && ev.error) || '';
      try { console.warn('[tt-speech] error:', err); } catch (eLog) {}
      if (err === 'aborted') return;
      if (err === 'no-speech') return;

      if (err === 'network') {
        // Desktop Chrome often throws a one-off network error — retry once (parent notebook)
        state.ignoreEndRestart = true;
        clearRestartTimer(state);
        commitSpeechToPrefix(state);
        if (state.wantListening && !state.networkRetryUsed) {
          state.networkRetryUsed = true;
          flashTip(state, 'Voice error (network) — retrying…', 'is-ok');
          destroyRecognition(state);
          setTimeout(function () {
            if (!state.wantListening || state.micUnavailable) return;
            if (!initRecognition(state)) {
              state.wantListening = false;
              markSpeechBroken(state, errorMessageForSpeech('network'));
              return;
            }
            startRecognitionEngine(state);
          }, 450);
          return;
        }
        state.wantListening = false;
        clearSilenceTimer(state);
        markSpeechBroken(state, errorMessageForSpeech('network'));
        return;
      }

      state.wantListening = false;
      state.ignoreEndRestart = true;
      clearSilenceTimer(state);
      clearRestartTimer(state);
      commitSpeechToPrefix(state);
      markSpeechBroken(state, errorMessageForSpeech(err));
    };

    recognition.onend = function () {
      if (state.micUnavailable) return;
      commitSpeechToPrefix(state);
      if (!state.wantListening || state.ignoreEndRestart) {
        clearSilenceTimer(state);
        setMicUi(state, false);
        return;
      }
      // Keep listening until 4s silence (Android/desktop one-shot engines end early)
      clearRestartTimer(state);
      state.restartTimer = setTimeout(function () {
        state.restartTimer = null;
        if (!state.wantListening || state.micUnavailable || state.ignoreEndRestart) return;
        startRecognitionEngine(state);
      }, isAndroid ? 320 : 160);
    };

    recognition.onresult = function (event) {
      if (state.micUnavailable) return;

      if (isAndroid) {
        // Finals only — interimResults is off on Android to prevent stutter loops
        var chunk = '';
        for (var a = 0; a < event.results.length; a++) {
          if (!event.results[a].isFinal) continue;
          var ap = normSpeech((event.results[a][0] && event.results[a][0].transcript) || '');
          if (ap) chunk = appendUniqueSpeech(chunk, ap);
        }
        if (!chunk && event.results.length) {
          chunk = normSpeech((event.results[event.results.length - 1][0] &&
            event.results[event.results.length - 1][0].transcript) || '');
        }
        if (!chunk) return;
        state.androidCommitted = appendUniqueSpeech(state.androidCommitted, chunk);
        writeSpeechToBox(state, '');
        armSilenceTimer(state);
        return;
      }

      var interim = '';
      var gotSpeech = false;
      for (var i = event.resultIndex; i < event.results.length; i++) {
        var piece = normSpeech((event.results[i][0] && event.results[i][0].transcript) || '');
        if (!piece) continue;
        gotSpeech = true;
        if (event.results[i].isFinal) {
          state.speechFinal = appendUniqueSpeech(state.speechFinal, piece);
        } else {
          interim = piece;
        }
      }
      if (gotSpeech) {
        if (interim && state.speechFinal) {
          var sf = state.speechFinal.toLowerCase();
          var im = interim.toLowerCase();
          if (im.startsWith(sf) || sf.endsWith(im)) interim = im.startsWith(sf) ? interim : '';
        }
        writeSpeechToBox(state, interim);
        armSilenceTimer(state);
      }
    };
  }

  function initRecognition(state) {
    var Ctor = getSpeechRecognitionCtor();
    if (!Ctor) return false;
    if (insecureContextBlocked()) return false;
    destroyRecognition(state);
    state.recognition = new Ctor();
    // Both platforms: one-shot + restart until 4s pause.
    // Android: no interim (main cause of repeated words).
    state.recognition.continuous = false;
    state.recognition.interimResults = !isAndroid;
    state.recognition.maxAlternatives = 1;
    state.recognition.lang = (navigator.language || 'en-IN');
    bindRecognitionHandlers(state);
    return true;
  }

  function startRecognitionEngine(state) {
    if (!state.recognition && !initRecognition(state)) return;
    try {
      state.recognition.start();
    } catch (err) {
      destroyRecognition(state);
      if (!initRecognition(state)) {
        state.wantListening = false;
        setMicUi(state, false);
        flashTip(state, 'Could not start microphone. Tap mic to retry.', 'is-err');
        if (active === state) active = null;
        return;
      }
      try {
        state.recognition.start();
      } catch (e2) {
        state.wantListening = false;
        setMicUi(state, false);
        flashTip(state, 'Could not start microphone. Tap mic to retry.', 'is-err');
        if (active === state) active = null;
      }
    }
  }

  function beginListening(state) {
    if (!voiceFeatureEnabled()) {
      markSpeechBroken(state, 'disabled by admin (ENABLE_VOICE_TO_TEXT)');
      return;
    }
    // Hard browser block: http://10.x is not a secure context
    if (insecureContextBlocked()) {
      markSpeechBroken(state, localDevHelpMessage());
      return;
    }
    if (!speechApiPresent()) {
      markSpeechBroken(state, 'Voice typing needs Chrome or Edge.');
      return;
    }

    if (active && active !== state) stopListening(active);
    resetSpeechSessionFromBox(state);
    state.wantListening = true;
    state.ignoreEndRestart = false;
    state.networkRetryUsed = false;
    active = state;
    setMicUi(state, true);
    flashTip(state, isDesktop ? 'Starting microphone…' : 'Listening… pause 4s to stop, or tap mic', 'is-ok');

    // Desktop: unlock mic permission first — reduces false "network" errors in Chrome
    if (isDesktop && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      navigator.mediaDevices.getUserMedia({ audio: true })
        .then(function (stream) {
          try { stream.getTracks().forEach(function (t) { t.stop(); }); } catch (e) {}
          if (!state.wantListening || state.micUnavailable) return;
          if (!initRecognition(state)) {
            state.wantListening = false;
            markSpeechBroken(state, localDevHelpMessage());
            return;
          }
          startRecognitionEngine(state);
        })
        .catch(function (err) {
          state.wantListening = false;
          if (active === state) active = null;
          var name = (err && err.name) || '';
          if (name === 'SecurityError' || insecureContextBlocked()) {
            markSpeechBroken(state, localDevHelpMessage());
          } else {
            markSpeechBroken(state, 'Microphone permission blocked (not-allowed).');
          }
        });
      return;
    }

    if (!initRecognition(state)) {
      state.wantListening = false;
      markSpeechBroken(state, localDevHelpMessage());
      return;
    }
    startRecognitionEngine(state);
  }

  function probeAndMaybeShowMic(state) {
    if (!state || !state.micBtn) return;
    hideMic(state);
    if (!voiceFeatureEnabled()) {
      try { console.warn('[tt-speech] disabled by admin (ENABLE_VOICE_TO_TEXT)'); } catch (e) {}
      return;
    }
    if (!canUseSpeechNow()) {
      try { console.warn('[tt-speech] unavailable:', localDevHelpMessage()); } catch (e2) {}
      return;
    }
    var cached = getSpeechProbeCache();
    if (cached === '0') {
      try { console.warn('[tt-speech] skipped — previous engine failure this session'); } catch (e3) {}
      return;
    }
    if (cached === '1') {
      if (state.input) {
        var wrapOk = state.input.closest('.student-popup-input-wrap, .tt-speech-wrap');
        if (wrapOk) wrapOk.classList.add('has-speech');
        state.input.classList.add('has-speech');
      }
      setMicAvailable(state);
      return;
    }

    function showReady() {
      if (state.input) {
        var wrap = state.input.closest('.student-popup-input-wrap, .tt-speech-wrap');
        if (wrap) wrap.classList.add('has-speech');
        state.input.classList.add('has-speech');
      }
      setMicAvailable(state);
    }

    if (navigator.permissions && navigator.permissions.query) {
      try {
        navigator.permissions.query({ name: 'microphone' }).then(function (status) {
          if (!voiceFeatureEnabled()) return;
          if (status.state === 'denied') {
            markSpeechBroken(state, 'microphone permission denied');
            return;
          }
          if (status.state === 'granted') {
            // Silent probe: only show mic if speech engine starts cleanly
            var Ctor = getSpeechRecognitionCtor();
            if (!Ctor) {
              markSpeechBroken(state, 'SpeechRecognition missing');
              return;
            }
            destroyRecognition(state);
            var r = new Ctor();
            var settled = false;
            function finish(ok, reason) {
              if (settled) return;
              settled = true;
              try { r.onstart = r.onerror = r.onend = null; } catch (e) {}
              try { r.abort(); } catch (e2) {}
              state.recognition = null;
              if (ok) {
                setSpeechProbeCache(true);
                showReady();
              } else {
                markSpeechBroken(state, reason || 'probe-failed');
              }
            }
            r.continuous = false;
            r.interimResults = false;
            r.maxAlternatives = 1;
            r.lang = (navigator.language || 'en-IN');
            r.onstart = function () { finish(true); };
            r.onerror = function (ev) {
              var err = (ev && ev.error) || '';
              if (err === 'aborted' || err === 'no-speech') {
                finish(true);
                return;
              }
              try { console.warn('[tt-speech] probe error:', err); } catch (eLog) {}
              finish(false, err || 'probe-error');
            };
            r.onend = function () { if (!settled) finish(true); };
            state.recognition = r;
            try {
              r.start();
            } catch (eStart) {
              try { console.warn('[tt-speech] probe start failed', eStart); } catch (e2) {}
              finish(false, 'probe-start-failed');
            }
            setTimeout(function () {
              if (!settled) finish(false, 'probe-timeout');
            }, 3500);
            return;
          }
          showReady();
        }).catch(function () { showReady(); });
        return;
      } catch (ePerm) {}
    }
    showReady();
  }

  function ensureMicButton(input) {
    var wrap = input.closest('.student-popup-input-wrap, .tt-speech-wrap') || input.parentElement;
    if (!wrap) return null;
    var existing = wrap.querySelector('.student-popup-mic, .tt-speech-mic');
    if (existing) return existing;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'student-popup-mic tt-speech-mic';
    btn.setAttribute('aria-label', 'Speak to fill');
    btn.setAttribute('title', 'Speak to fill');
    btn.setAttribute('aria-pressed', 'false');
    btn.innerHTML = "<i class='bx bx-microphone' aria-hidden='true'></i>";
    wrap.appendChild(btn);
    return btn;
  }

  function bind(input, options) {
    options = options || {};
    if (!input || input.dataset.ttSpeechBound === '1') return null;

    var wrap = input.closest('.student-popup-input-wrap, .tt-speech-wrap');
    var micBtn = options.micBtn || (voiceFeatureEnabled() ? ensureMicButton(input) : null);
    if (!micBtn) {
      // Remove leftover mic markup when voice is disabled site-wide
      var leftover = wrap && wrap.querySelector('.student-popup-mic, .tt-speech-mic');
      if (leftover) leftover.hidden = true;
      return null;
    }

    var state = {
      input: input,
      micBtn: micBtn,
      mode: options.mode || input.getAttribute('data-tt-speech') || 'text',
      wantListening: false,
      micUnavailable: true,
      ignoreEndRestart: false,
      networkRetryUsed: false,
      recognition: null,
      sessionBase: '',
      androidCommitted: '',
      speechPrefix: '',
      speechFinal: '',
      silenceTimer: null,
      restartTimer: null,
      tipTimer: null
    };

    if (input.classList.contains('has-toggle') && wrap) wrap.classList.add('has-eye-speech');
    hideMic(state);
    probeAndMaybeShowMic(state);

    micBtn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (micBtn.hidden || state.micUnavailable) return;
      if (state.wantListening) {
        stopListening(state);
        flashTip(state, '');
        return;
      }
      beginListening(state);
    });

    input.dataset.ttSpeechBound = '1';
    input._ttSpeechState = state;
    return state;
  }

  function enhance(root) {
    root = root || document;
    if (!voiceFeatureEnabled()) {
      try {
        var mics = root.querySelectorAll('.student-popup-mic, .tt-speech-mic');
        for (var m = 0; m < mics.length; m++) {
          mics[m].hidden = true;
          mics[m].style.display = 'none';
        }
      } catch (e) {}
      return [];
    }
    var nodes = root.querySelectorAll('[data-tt-speech]');
    var bound = [];
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      if (el.tagName !== 'INPUT' && el.tagName !== 'TEXTAREA') continue;
      var st = bind(el, { mode: el.getAttribute('data-tt-speech') || 'text' });
      if (st) bound.push(st);
    }
    return bound;
  }

  global.TTSpeechInput = {
    isSupported: isSupported,
    speechApiPresent: speechApiPresent,
    canUseSpeechNow: canUseSpeechNow,
    voiceFeatureEnabled: voiceFeatureEnabled,
    localDevHelpMessage: localDevHelpMessage,
    bind: bind,
    enhance: enhance,
    stopAll: stopAll,
    _normalizeIdentity: normalizeIdentity,
    _normalizeByMode: normalizeByMode
  };
})(typeof window !== 'undefined' ? window : this);
