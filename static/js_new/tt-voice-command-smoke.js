/**
 * Smoke tests for Voice Navigation command phrases (desktop / tablet / mobile phrasing).
 * Run: node static/js_new/tt-voice-command-smoke.js
 */
(function () {
  'use strict';

  function norm(t) {
    return String(t || '').toLowerCase().replace(/[^\w\s@./-]/g, ' ').replace(/\s+/g, ' ').trim();
  }

  var RULES = [
    { id: 'scroll-top', re: /^(go to top|scroll to top|scroll top|page top|top of (the )?page|scroll up to top)$/, samples: ['scroll to top', 'go to top', 'scroll top', 'page top', 'top of the page'] },
    { id: 'scroll-bottom', re: /^(go to bottom|scroll to bottom|scroll bottom|page bottom|bottom of (the )?page|scroll down to bottom)$/, samples: ['scroll to bottom', 'go to bottom', 'scroll bottom', 'bottom of page'] },
    { id: 'scroll-down', re: /^(scroll down|page down|move down)$/, samples: ['scroll down', 'page down', 'move down'] },
    { id: 'scroll-up', re: /^(scroll up|page up|move up)$/, samples: ['scroll up', 'page up', 'move up'] },
    { id: 'open-login', re: /^(open login|login|sign in|signin|open sign in)$/, samples: ['open login', 'login', 'sign in', 'open sign in'] },
    { id: 'open-menu', re: /^(open menu|open navigation|show menu|open nav|hamburger|open hamburger|show navigation)$/, samples: ['open menu', 'show menu', 'open navigation', 'hamburger'] },
    { id: 'close-menu', re: /^(close menu|close navigation|hide menu|close nav)$/, samples: ['close menu', 'hide menu'] },
    { id: 'open-search', re: /^(open search|search|show search)$/, samples: ['open search', 'show search'] },
    { id: 'help', re: /^(help|commands|show help|show commands)$/, samples: ['help', 'show commands', 'commands'] },
    { id: 'nav-open', re: /^(?:open|go to|navigate to|show)\s+(.+)$/, samples: ['open about us', 'go to blogs', 'navigate to career library', 'open vocational courses'] },
    { id: 'click-btn', re: /^(?:click|press|tap|hit)\s+(.+)$/, samples: ['click save', 'press continue', 'tap next', 'click submit'] },
    { id: 'go-home', re: /^(go home|home|open home)$/, samples: ['go home', 'home', 'open home'] },
    { id: 'go-back', re: /^(go back|back|previous page)$/, samples: ['go back', 'back', 'previous page'] }
  ];

  var failed = 0;
  var passed = 0;

  RULES.forEach(function (rule) {
    rule.samples.forEach(function (sample) {
      var t = norm(sample);
      var ok = rule.re.test(t);
      if (ok) {
        passed += 1;
      } else {
        failed += 1;
        console.error('FAIL', rule.id, JSON.stringify(sample), '→', JSON.stringify(t));
      }
    });
  });

  // Conflict checks: scroll phrases must not be swallowed only by generic nav
  var conflicts = [
    { phrase: 'scroll to top', must: 'scroll-top', mustNotExtract: null },
    { phrase: 'go to top', must: 'scroll-top' },
    { phrase: 'open menu', must: 'open-menu' }
  ];
  conflicts.forEach(function (c) {
    var t = norm(c.phrase);
    var hit = RULES.filter(function (r) { return r.re.test(t); }).map(function (r) { return r.id; });
    if (hit.indexOf(c.must) === -1) {
      failed += 1;
      console.error('FAIL conflict', c.phrase, 'expected', c.must, 'got', hit);
    } else {
      passed += 1;
    }
  });

  // Viewport-agnostic label matching (simulates desktop/tablet/mobile spoken labels)
  function findBest(spoken, targets) {
    var s = norm(spoken);
    var exact = null;
    var partial = null;
    targets.forEach(function (t) {
      var key = norm(t);
      if (key === s) exact = t;
      else if (key.indexOf(s) !== -1 || s.indexOf(key) !== -1) {
        if (!partial || key.length < norm(partial).length) partial = t;
      }
    });
    return exact || partial;
  }
  var navLabels = ['About Us', 'Career Planning Hub', 'Blogs', 'Vocational Courses', 'Career Library'];
  [
    ['about us', 'About Us'],
    ['career planning hub', 'Career Planning Hub'],
    ['blogs', 'Blogs'],
    ['vocational courses', 'Vocational Courses']
  ].forEach(function (pair) {
    var hit = findBest(pair[0], navLabels);
    if (hit !== pair[1]) {
      failed += 1;
      console.error('FAIL nav match', pair[0], '→', hit);
    } else {
      passed += 1;
    }
  });

  console.log('Voice command smoke: ' + passed + ' passed, ' + failed + ' failed');
  if (failed) process.exit(1);
})();
