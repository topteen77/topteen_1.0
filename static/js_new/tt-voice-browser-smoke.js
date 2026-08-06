/**
 * Browser viewport smoke for voice nav helpers (desktop / tablet / mobile).
 * Run from repo root: node static/js_new/tt-voice-browser-smoke.js
 */
const { chromium } = require('playwright');

const HTML = `<!doctype html><html><body>
<header class="tt-header">
  <nav class="navbar">
    <div class="burger" id="burger"></div>
    <div class="navbar-block" id="menu">
      <ul class="menu">
        <li class="menu-item single-link"><a href="/about/" class="menu-link">About Us</a></li>
        <li class="menu-item dropdown">
          <span class="dropdown-toggle menu-link">Discover</span>
          <div class="dropdown-content">
            <a href="/vocational/">Vocational Courses</a>
            <a href="/career-planning/">Career Planning Hub</a>
          </div>
        </li>
        <li class="menu-item dropdown">
          <div class="dropdown-content blogs-menu">
            <a href="/blogs/">Blogs</a>
            <a href="/careers/">Career Library</a>
          </div>
        </li>
        <li class="menu-item search-icon"><a href="#" class="menu-link search-toggle" aria-label="Open search">Search</a></li>
      </ul>
    </div>
  </nav>
</header>
<main>
  <h1>Demo</h1>
  <p id="long">content</p>
  <button type="button" id="saveBtn">Save</button>
  <button type="button" id="continueBtn">Continue</button>
  <a class="btn" href="/apply/" id="applyBtn">Apply Now</a>
</main>
<script>
window.__clicks = [];
document.getElementById('burger').addEventListener('click', function () {
  document.getElementById('menu').classList.toggle('is-active');
  window.__clicks.push('burger');
});
['saveBtn','continueBtn','applyBtn'].forEach(function(id){
  document.getElementById(id).addEventListener('click', function(){ window.__clicks.push(id); });
});
document.querySelectorAll('a[href]').forEach(function(a){
  a.addEventListener('click', function(e){ e.preventDefault(); window.__clicks.push(a.textContent.trim()); });
});
function normalizeSpeakLabel(s){return String(s||'').replace(/[^\\w\\s&/-]/g,' ').replace(/\\s+/g,' ').trim().toLowerCase();}
function normalizeSpace(s){return String(s||'').replace(/\\s+/g,' ').trim();}
function collectTopNavTargets(){
  var root=document.querySelector('.navbar');
  var out=[], seen={};
  root.querySelectorAll('a[href]').forEach(function(a){
    var href=(a.getAttribute('href')||'').trim();
    if(!href||href==='#'||a.classList.contains('search-toggle')) return;
    var label=normalizeSpace(a.getAttribute('aria-label')||a.textContent||'');
    if(!label||label.length>48) return;
    var key=normalizeSpeakLabel(label); if(!key||seen[key]) return; seen[key]=true;
    out.push({el:a,label:label,key:key});
  });
  return out;
}
function collectActionButtons(){
  var out=[], seen={};
  document.querySelectorAll('main button, main a.btn').forEach(function(el){
    var label=normalizeSpace(el.textContent||'');
    var key=normalizeSpeakLabel(label); if(!key||seen[key]) return; seen[key]=true;
    out.push({el:el,label:label,key:key});
  });
  return out;
}
function findBestTarget(spoken, targets){
  var s=normalizeSpeakLabel(spoken), exact=null, partial=null;
  targets.forEach(function(t){
    if(t.key===s) exact=t;
    else if(t.key.indexOf(s)!==-1||s.indexOf(t.key)!==-1){ if(!partial||t.key.length<partial.key.length) partial=t; }
  });
  return exact||partial;
}
function scrollPage(kind){
  var y=window.pageYOffset||0, vh=window.innerHeight||600;
  if(kind==='top'){ window.scrollTo(0,0); return 'top'; }
  if(kind==='bottom'){ window.scrollTo(0, document.body.scrollHeight); return 'bottom'; }
  if(kind==='down'){ window.scrollTo(0, y+Math.round(vh*0.85)); return 'down'; }
  if(kind==='up'){ window.scrollTo(0, Math.max(0,y-Math.round(vh*0.85))); return 'up'; }
}
window.__voice = {
  collectTopNavTargets, collectActionButtons, findBestTarget, scrollPage,
  openNav: function(name){ var hit=findBestTarget(name, collectTopNavTargets()); if(hit) hit.el.click(); return hit&&hit.label; },
  clickBtn: function(name){ var hit=findBestTarget(name, collectActionButtons()); if(hit) hit.el.click(); return hit&&hit.label; },
  toggleMenu: function(){ document.getElementById('burger').click(); return document.getElementById('menu').classList.contains('is-active'); }
};
// tall page for scroll
document.getElementById('long').style.height='2500px';
</script>
</body></html>`;

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/usr/bin/google-chrome',
    args: ['--no-sandbox', '--disable-dev-shm-usage']
  });
  const viewports = [
    { name: 'desktop', width: 1280, height: 800 },
    { name: 'tablet', width: 768, height: 1024 },
    { name: 'mobile', width: 390, height: 844 }
  ];
  let failed = 0;
  let passed = 0;

  for (const vp of viewports) {
    const page = await browser.newPage({ viewport: vp });
    await page.setContent(HTML, { waitUntil: 'domcontentloaded' });

    const results = await page.evaluate(() => {
      const out = [];
      out.push(['scroll-top', window.__voice.scrollPage('top') === 'top']);
      out.push(['scroll-down', window.__voice.scrollPage('down') === 'down']);
      out.push(['scroll-bottom', window.__voice.scrollPage('bottom') === 'bottom']);
      out.push(['scroll-up', window.__voice.scrollPage('up') === 'up']);
      out.push(['nav-about', window.__voice.openNav('about us') === 'About Us']);
      out.push(['nav-blogs', window.__voice.openNav('blogs') === 'Blogs']);
      out.push(['nav-career-planning', window.__voice.openNav('career planning hub') === 'Career Planning Hub']);
      out.push(['click-save', window.__voice.clickBtn('save') === 'Save']);
      out.push(['click-continue', window.__voice.clickBtn('continue') === 'Continue']);
      out.push(['click-apply', window.__voice.clickBtn('apply now') === 'Apply Now']);
      const open = window.__voice.toggleMenu();
      out.push(['menu-open', open === true]);
      const closed = window.__voice.toggleMenu();
      out.push(['menu-close', closed === false]);
      out.push(['nav-count', window.__voice.collectTopNavTargets().length >= 4]);
      out.push(['btn-count', window.__voice.collectActionButtons().length >= 3]);
      return out;
    });

    results.forEach(([id, ok]) => {
      if (ok) passed += 1;
      else {
        failed += 1;
        console.error('FAIL', vp.name, id);
      }
    });
    await page.close();
  }

  await browser.close();
  console.log('Browser voice smoke: ' + passed + ' passed, ' + failed + ' failed across ' + viewports.length + ' viewports');
  if (failed) process.exit(1);
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
