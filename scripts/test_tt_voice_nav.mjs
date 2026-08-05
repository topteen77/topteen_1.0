/**
 * Headless checks for tt-voice-nav.js (no real mic).
 * Run: node scripts/test_tt_voice_nav.mjs
 */
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const src = fs.readFileSync(path.join(root, 'static/js_new/tt-voice-nav.js'), 'utf8');

function makeDoc() {
  const store = new Map();
  const bodyChildren = [];
  const body = {
    classList: {
      _s: new Set(),
      add(c) { this._s.add(c); },
      remove(c) { this._s.delete(c); },
      contains(c) { return this._s.has(c); }
    },
    appendChild(el) { bodyChildren.push(el); el.parentNode = body; return el; },
    removeChild(el) {
      const i = bodyChildren.indexOf(el);
      if (i >= 0) bodyChildren.splice(i, 1);
      el.parentNode = null;
    }
  };
  const headChildren = [];
  const head = {
    appendChild(el) { headChildren.push(el); return el; }
  };
  function el(tag) {
    const attrs = {};
    const kids = [];
    const node = {
      tagName: String(tag).toUpperCase(),
      style: {},
      classList: {
        _s: new Set(),
        add(c) { this._s.add(c); },
        remove(c) { this._s.delete(c); },
        toggle(c, on) {
          if (on === false) this._s.delete(c);
          else if (on === true) this._s.add(c);
          else if (this._s.has(c)) this._s.delete(c);
          else this._s.add(c);
        },
        contains(c) { return this._s.has(c); }
      },
      children: kids,
      parentNode: null,
      _listeners: {},
      setAttribute(k, v) { attrs[k] = String(v); },
      getAttribute(k) { return attrs[k] || null; },
      addEventListener(type, fn) {
        (this._listeners[type] = this._listeners[type] || []).push(fn);
      },
      querySelector(sel) {
        if (sel.startsWith('[data-ttvn-')) {
          const key = sel.slice(1, -1);
          const walk = (n) => {
            if (n.getAttribute && n.getAttribute(key) !== null) return n;
            for (const c of n.children || []) {
              const hit = walk(c);
              if (hit) return hit;
            }
            return null;
          };
          return walk(node);
        }
        return null;
      },
      querySelectorAll(sel) {
        const out = [];
        if (sel === '.ttvn-chip') {
          const walk = (n) => {
            if (n.classList && n.classList.contains('ttvn-chip')) out.push(n);
            for (const c of n.children || []) walk(c);
          };
          walk(node);
        }
        return out;
      }
    };
    Object.defineProperty(node, 'innerHTML', {
      get() { return this._html || ''; },
      set(v) {
        this._html = String(v);
        // crude: create stub children for data attrs used by ensureBar
        kids.length = 0;
        const re = /data-ttvn-[a-z]+/g;
        let m;
        const seen = new Set();
        while ((m = re.exec(v))) {
          if (seen.has(m[0])) continue;
          seen.add(m[0]);
          const child = el('div');
          child.setAttribute(m[0], '');
          if (m[0] === 'data-ttvn-mic' || m[0] === 'data-ttvn-collapse') child.tagName = 'BUTTON';
          if (m[0] === 'data-ttvn-mic') {
            const icon = el('i');
            child.children.push(icon);
            child.querySelector = function (s) {
              if (s === 'i') return icon;
              return null;
            };
          }
          if (m[0] === 'data-ttvn-chips') {
            child.querySelectorAll = function (s) {
              if (s === '.ttvn-chip') return this.children.filter((c) => c.classList.contains('ttvn-chip'));
              return [];
            };
          }
          kids.push(child);
          child.parentNode = node;
        }
      }
    });
    Object.defineProperty(node, 'textContent', {
      get() { return this._text || ''; },
      set(v) { this._text = String(v); }
    });
    Object.defineProperty(node, 'disabled', {
      get() { return !!this._disabled; },
      set(v) { this._disabled = !!v; }
    });
    return node;
  }

  const doc = {
    body,
    head,
    getElementById(id) {
      if (id === 'ttVoiceNavBar') return bodyChildren.find((c) => c.id === id) || null;
      if (id === 'ttVoiceNavStyles') return headChildren.find((c) => c.id === id) || null;
      return store.get(id) || null;
    },
    createElement(tag) {
      const node = el(tag);
      return node;
    },
    querySelector() { return null; }
  };
  // allow setting id on createElement results
  const _create = doc.createElement.bind(doc);
  doc.createElement = function (tag) {
    const node = _create(tag);
    Object.defineProperty(node, 'id', {
      get() { return this._id || ''; },
      set(v) { this._id = v; }
    });
    return node;
  };
  return { doc, store, bodyChildren };
}

function loadApi(overrides = {}) {
  const { doc } = makeDoc();
  const sessionStorage = {
    _d: {},
    getItem(k) { return this._d[k] == null ? null : this._d[k]; },
    setItem(k, v) { this._d[k] = String(v); }
  };
  const sandbox = {
    window: {},
    document: doc,
    navigator: { language: 'en-IN', permissions: undefined },
    sessionStorage,
    console,
    setTimeout,
    clearTimeout,
    Event: function () {},
    bootstrap: undefined
  };
  sandbox.window = sandbox;
  sandbox.global = sandbox;
  sandbox.window.TT_VOICE_TO_TEXT_ENABLED = overrides.admin !== false;
  sandbox.window.isSecureContext = overrides.secure !== false;
  if (overrides.speech !== false) {
    sandbox.window.SpeechRecognition = function () {};
    sandbox.window.webkitSpeechRecognition = sandbox.window.SpeechRecognition;
  }
  if (overrides.probe != null) sessionStorage.setItem('tt_voice_stt_ok', overrides.probe);
  vm.runInNewContext(src, sandbox, { filename: 'tt-voice-nav.js' });
  return sandbox.window.TTVoiceNav;
}

let failed = 0;
function assert(cond, msg) {
  if (!cond) {
    failed += 1;
    console.error('FAIL:', msg);
  } else {
    console.log('OK:', msg);
  }
}

const api1 = loadApi({ admin: true, secure: true, speech: true });
assert(api1.shouldShowVoiceUi() === true, 'show UI when admin on');
assert(api1.speechEngineReady() === true, 'speech ready when secure+speech');

const api2 = loadApi({ admin: false });
assert(api2.shouldShowVoiceUi() === false, 'hide UI when admin off');

const api3 = loadApi({ admin: true, secure: false });
assert(api3.shouldShowVoiceUi() === true, 'chips bar still allowed on insecure context');
assert(api3.speechEngineReady() === false, 'speech not ready on insecure context');

const api4 = loadApi({ admin: true, probe: '0' });
assert(api4.shouldShowVoiceUi() === true, 'chips bar allowed after prior engine failure');
assert(api4.speechEngineReady() === false, 'speech not ready after prior failure');

const api5 = loadApi({ admin: true, speech: false });
assert(api5.shouldShowVoiceUi() === true, 'chips bar allowed without SpeechRecognition');
assert(api5.speechEngineReady() === false, 'speech not ready without SpeechRecognition');

const vOk = loadApi()._parseAndValidateDemo('mobile', 'nine eight seven six five four three two one zero');
assert(vOk.ok && vOk.value === '9876543210', 'mobile spoken digits validate');

const vBad = loadApi()._parseAndValidateDemo('mobile', '12345');
assert(!vBad.ok, 'short mobile rejected');

const g = loadApi()._parseGender('I am female');
assert(g === 'Female', 'gender parse female');

const d1 = loadApi()._parseSpokenDate('15 January 2005');
assert(d1 === '2005-01-15', 'spoken month date parses');

const d2 = loadApi()._parseSpokenDate('15/01/2005');
assert(d2 === '2005-01-15', 'numeric dd/mm/yyyy date parses');

const d3 = loadApi()._validateField(
  { type: 'date', required: false, label: 'DOB' },
  '15th Jan 2005'
);
assert(d3.ok && d3.value === '2005-01-15', 'date field validates spoken form');

const gr = loadApi()._parseGrade('class 10');
assert(gr === '10', 'grade parse class 10');

const emailBad = loadApi()._validateField(
  { type: 'email', required: false, label: 'Email' },
  'not-an-email'
);
assert(!emailBad.ok, 'bad email rejected');

const apiOff = loadApi({ admin: false });
assert(apiOff.attach({ pageCommands: [], forms: [] }) == null, 'attach no-ops when admin disabled');

if (failed) {
  console.error('\n' + failed + ' test(s) failed');
  process.exit(1);
}
console.log('\nAll voice-nav unit checks passed');
