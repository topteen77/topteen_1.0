
/* ═══════════════════════════════════════════════════════
   STATE
═══════════════════════════════════════════════════════ */
var S = {
  step: 1,
  STEPS: 7,
  style: 'ivy_league',
  unis: [],
  studioTemplateId: '',
  fd: null,       /* last collected form data */
  rhtml: '',      /* last resume HTML */
  scores: null,   /* last scores object */
  busy: false,
  saved: [],
  generatedOnce: false
};

/* load persisted resumes */
(function(){
  try {
    var d = JSON.parse(localStorage.getItem('acv3') || '[]');
    S.saved = Array.isArray(d) ? d : [];
  } catch(e) { S.saved = []; }
})();

/* ═══════════════════════════════════════════════════════
   INIT
═══════════════════════════════════════════════════════ */
function wizardAutoStart(){
  var build = document.getElementById('pg-build');
  var land = document.getElementById('pg-land');
  if (build && !land) {
    goPage('build');
    goS(1);
  }
}

function applyServerPrefill(){
  var raw = document.getElementById('admitcv-prefill-json');
  if (!raw || !raw.textContent) return;
  try {
    var d = JSON.parse(raw.textContent);
    if (d.name) sv('f-name', d.name);
    if (d.email) sv('f-email', d.email);
    if (d.phone) sv('f-phone', d.phone);
    if (d.country) sv('f-country', d.country);
    if (d.school) sv('f-school', d.school);
    if (d.grade) {
      var lvl = document.getElementById('f-level');
      if (lvl && !lvl.value) lvl.value = d.grade;
    }
  } catch (e) {}
}

function _splitLines(s){
  return String(s||'').split('\n').map(function(x){ return x.trim(); }).filter(Boolean);
}

function _splitDRows(s){
  return String(s||'').split('\n').map(function(x){ return x.trim(); }).filter(Boolean);
}

function _partsFromDRow(line){
  return String(line||'').split(/\s*\|\s*/).map(function(p){ return p.trim(); });
}

function restoreSimpleList(listId, label, ph, blob){
  var list = document.getElementById(listId);
  if (!list) return;
  var lines = _splitLines(blob);
  list.innerHTML = '';
  if (!lines.length) {
    addSimple(listId, label, ph);
    return;
  }
  for (var i = 0; i < lines.length; i++) addSimple(listId, label, ph);
  var blocks = list.querySelectorAll('.dblk');
  for (var j = 0; j < lines.length; j++) {
    var inp = blocks[j] && blocks[j].querySelector('input[type="text"]');
    if (inp) inp.value = lines[j];
  }
}

function restoreDListBlocks(listId, addFn, lines, fillFn){
  var list = document.getElementById(listId);
  if (!list) return;
  lines = _splitDRows(lines);
  list.innerHTML = '';
  if (!lines.length) {
    addFn();
    return;
  }
  for (var i = 0; i < lines.length; i++) addFn();
  var blocks = list.querySelectorAll('.dblk');
  for (var j = 0; j < lines.length; j++) {
    fillFn(blocks[j], _partsFromDRow(lines[j]));
  }
}

function restoreLeadBlock(blk, parts){
  if (!blk) return;
  var ins = blk.querySelectorAll('input[type="text"],textarea');
  for (var i = 0; i < Math.min(parts.length, ins.length); i++) ins[i].value = parts[i];
}

function restoreExtraBlock(blk, parts){
  if (!blk) return;
  var ins = blk.querySelectorAll('input[type="text"]');
  for (var i = 0; i < Math.min(parts.length, ins.length); i++) ins[i].value = parts[i];
}

function restoreWorkBlock(blk, parts){
  if (!blk) return;
  var ins = blk.querySelectorAll('input[type="text"],textarea,select');
  for (var i = 0; i < Math.min(parts.length, ins.length); i++) ins[i].value = parts[i];
}

function restoreResearchBlock(blk, parts){
  if (!blk) return;
  var ins = blk.querySelectorAll('input[type="text"],textarea,select');
  for (var i = 0; i < Math.min(parts.length, ins.length); i++) ins[i].value = parts[i];
}

function restoreLangBlock(blk, parts){
  if (!blk) return;
  var ins = blk.querySelectorAll('input[type="text"],select');
  if (parts[0] && ins[0]) ins[0].value = parts[0];
  if (parts[1] && ins[1]) ins[1].value = parts[1];
}

function restoreLangsFromString(str){
  if (!str || !str.trim()) return;
  var list = document.getElementById('dl-lang');
  if (!list) return;
  var pairs = String(str).split(',').map(function(x){ return x.trim(); }).filter(Boolean);
  list.innerHTML = '';
  if (!pairs.length) {
    addLang();
    return;
  }
  for (var i = 0; i < pairs.length; i++) {
    addLang();
    var blocks = list.querySelectorAll('.dblk');
    var blk = blocks[blocks.length - 1];
    var m = pairs[i].match(/^(.+?)\s*\(([^)]+)\)\s*$/);
    if (m) restoreLangBlock(blk, [m[1].trim(), m[2].trim()]);
    else restoreLangBlock(blk, [pairs[i], '']);
  }
}

function restoreTestsFromString(str){
  if (!str || !str.trim()) return;
  var parts = String(str).split(/\s*\|\s*/);
  var keys = {
    SAT: 'f-sat', ACT: 'f-act', AP: 'f-ap', GRE: 'f-gre', GMAT: 'f-gmat',
    LSAT: 'f-lsat', IELTS: 'f-ielts', TOEFL: 'f-toefl', Other: 'f-test-other'
  };
  for (var i = 0; i < parts.length; i++) {
    var m = parts[i].match(/^([A-Za-z]+)\s*:\s*(.+)$/);
    if (!m) continue;
    var k = m[1].toUpperCase();
    if (k === 'OTHER') k = 'Other';
    var fid = keys[k];
    if (fid) sv(fid, m[2].trim());
  }
}

function restoreUnisFromString(unisStr){
  if (!unisStr || !String(unisStr).trim()) return;
  S.unis = [];
  var chips = document.querySelectorAll('#country-chips .chip');
  for (var c = 0; c < chips.length; c++) {
    if (chips[c].classList.contains('on')) toggleChip(chips[c]);
  }
  sv('f-other-country', '');
  var tokens = String(unisStr).split(',').map(function(x){ return x.trim(); }).filter(Boolean);
  var other = [];
  for (var i = 0; i < tokens.length; i++) {
    var t = tokens[i];
    var hit = false;
    for (var j = 0; j < chips.length; j++) {
      if (chips[j].textContent.trim() === t) {
        if (!chips[j].classList.contains('on')) toggleChip(chips[j]);
        hit = true;
        break;
      }
    }
    if (!hit) other.push(t);
  }
  if (other.length) sv('f-other-country', other.join(', '));
}

function applyWizardRestore(){
  var raw = document.getElementById('wizard-restore-json');
  if (!raw || !raw.textContent || raw.textContent.trim() === '{}') return;
  var d;
  try {
    d = JSON.parse(raw.textContent);
  } catch (e) {
    return;
  }
  if (!d || typeof d !== 'object' || !Object.keys(d).length) return;
  if (d.generated_once === true) S.generatedOnce = true;

  if (d.name) sv('f-name', d.name);
  if (d.email) sv('f-email', d.email);
  if (d.phone) sv('f-phone', d.phone);
  if (d.country) sv('f-country', d.country);
  if (d.linkedin) sv('f-linkedin', d.linkedin);
  if (d.portfolio) sv('f-portfolio', d.portfolio);
  if (d.level) sv('f-level', d.level);
  if (d.school) sv('f-school', d.school);
  if (d.course) sv('f-course', d.course);
  if (d.career) sv('f-career', d.career);
  if (d.unis) restoreUnisFromString(d.unis);
  if (d.gpa) sv('f-gpa', d.gpa);
  if (d.board) sv('f-board', d.board);
  if (d.board_state) sv('f-board-state', d.board_state);
  if (d.subjects) sv('f-subjects', d.subjects);
  if (d.tests) restoreTestsFromString(d.tests);
  if (d.awards) restoreSimpleList('dl-awards', 'Award', 'e.g. National Mathematics Olympiad — Silver Medal, top 50 nationally (2024)', d.awards);
  if (d.olymp) restoreSimpleList('dl-olymp', 'Competition', 'e.g. International Mathematical Olympiad — Honourable Mention', d.olymp);
  if (d.lead) restoreDListBlocks('dl-lead', addLead, d.lead, restoreLeadBlock);
  if (d.extra) restoreDListBlocks('dl-extra', addExtra, d.extra, restoreExtraBlock);
  if (d.sport) restoreSimpleList('dl-sport', 'Sport', 'e.g. State Under-19 Cricket Captain — led team to Regional Championship 2024', d.sport);
  if (d.intern) restoreDListBlocks('dl-intern', function(){ addWork('dl-intern','Internship'); }, d.intern, restoreWorkBlock);
  if (d.research) restoreDListBlocks('dl-research', addResearch, d.research, restoreResearchBlock);
  if (d.community) restoreDListBlocks('dl-community', function(){ addWork('dl-community','Community Initiative'); }, d.community, restoreWorkBlock);
  if (d.projects) restoreDListBlocks('dl-projects', function(){ addWork('dl-projects','Project'); }, d.projects, restoreWorkBlock);
  if (d.tech) sv('f-tech', d.tech);
  if (d.soft) sv('f-soft', d.soft);
  if (d.langs) restoreLangsFromString(d.langs);
  if (d.certs) restoreSimpleList('dl-certs', 'Certification', 'e.g. Google Data Analytics Certificate — Coursera (2024)', d.certs);
  if (d.personal) sv('f-personal', d.personal);
  if (d.hobbies) sv('f-hobbies', d.hobbies);
  if (d.format) sv('f-format', d.format);
  if (d.tag) sv('f-tag', d.tag);
  if (d.instr) sv('f-instr', d.instr);
  if (typeof d.proofread === 'boolean') {
    var pr = document.getElementById('f-proofread');
    if (pr) pr.checked = d.proofread;
  }
  var sp = d.studio_proto_v1;
  if (sp && sp.template) {
    S.studioTemplateId = String(sp.template);
    updatePdfDownloadLink(S.studioTemplateId);
    var stSel = document.getElementById('f-studio-template');
    if (stSel) stSel.value = String(sp.template);
  }
  if (d.style) {
    S.style = d.style;
    var tiles = document.querySelectorAll('#style-grid .stile[data-style]');
    for (var ti = 0; ti < tiles.length; ti++) {
      if (tiles[ti].getAttribute('data-style') === d.style) {
        pickStyle(tiles[ti], d.style);
        break;
      }
    }
  }
  syncBoardExtraField();
  buildPreview();
}

function updateGenerateButtons(){
  var has = !!S.generatedOnce;
  var btn = document.getElementById('gen-btn');
  var next = document.getElementById('gen-next-btn');
  var again = document.getElementById('gen-again-btn');
  if (btn) btn.style.display = has ? 'none' : '';
  if (next) next.style.display = has ? '' : 'none';
  if (again) again.style.display = has ? '' : 'none';
}

function buildPdfUrlWithTemplate(templateId){
  var base = typeof window.ADMITCV_RESUME_PDF_URL === 'string' ? window.ADMITCV_RESUME_PDF_URL.trim() : '';
  if (!base) return '';
  var tid = String(templateId || '').trim();
  try {
    var u = new URL(base, window.location.origin);
    if (tid) u.searchParams.set('template_id', tid);
    else u.searchParams.delete('template_id');
    return u.toString();
  } catch (e) {
    if (!tid) return base;
    var hashAt = base.indexOf('#');
    var hash = hashAt >= 0 ? base.slice(hashAt) : '';
    var bare = hashAt >= 0 ? base.slice(0, hashAt) : base;
    var qAt = bare.indexOf('?');
    var path = qAt >= 0 ? bare.slice(0, qAt) : bare;
    var q = qAt >= 0 ? bare.slice(qAt + 1) : '';
    var out = [];
    if (q) {
      var parts = q.split('&');
      for (var i = 0; i < parts.length; i++) {
        if (!parts[i]) continue;
        var kv = parts[i].split('=');
        if ((kv[0] || '').trim() === 'template_id') continue;
        out.push(parts[i]);
      }
    }
    out.push('template_id=' + encodeURIComponent(tid));
    return path + '?' + out.join('&') + hash;
  }
}

function updatePdfDownloadLink(templateId){
  var pdfA = document.getElementById('gen-download-pdf-link');
  if (!pdfA) return;
  var href = buildPdfUrlWithTemplate(templateId);
  if (href) pdfA.href = href;
}

window.addEventListener('message', function(ev){
  var data = ev && ev.data ? ev.data : null;
  if (!data) return;
  if (typeof data === 'string') {
    try {
      data = JSON.parse(data);
    } catch (e) {
      return;
    }
  }
  if (!data || data.type !== 'TT_STUDIO_TEMPLATE_PICK') return;
  var tid = String(data.template || '').trim();
  if (!tid) return;
  S.studioTemplateId = tid;
  updatePdfDownloadLink(tid);
});

function persistStudioResumeToLocal(b){
  if(!b) return;
  try {
    var suf = b.rid ? ('_' + b.rid) : '_0';
    localStorage.setItem('topteen_admitcv_wizard_draft' + suf, JSON.stringify(b.d));
    localStorage.setItem('topteen_admitcv_resume_html' + suf, b.html);
    localStorage.setItem('topteen_admitcv_about_plain' + suf, b.plain);
  } catch (e) {}
}

function initStudioTemplatePicker(){
  // Step-6 template selection removed; template choosing happens in Step 7.
}

function paintStudioTemplateSelection(id){
  var grid = document.getElementById('studio-template-grid');
  if (!grid) return;
  var tiles = grid.querySelectorAll('.tpltile[data-tpl]');
  for (var i = 0; i < tiles.length; i++) {
    var t = tiles[i];
    var tid = t.getAttribute('data-tpl') || '';
    var on = (String(tid) === String(id || ''));
    if (on) t.classList.add('on'); else t.classList.remove('on');
    t.setAttribute('aria-pressed', on ? 'true' : 'false');
  }
}

function pickStudioTemplate(id){
  paintStudioTemplateSelection(String(id || ''));
}

document.addEventListener('DOMContentLoaded', function(){
  seedLists();
  wireInputs();
  updBadge();
  initStudioTemplatePicker();
  initStep7TemplatesEmbed();
  wizardAutoStart();
  applyServerPrefill();
  applyWizardRestore();
  try {
    if (typeof window.TOPTEEN_RESUME_HAS_GENERATED === 'boolean' && window.TOPTEEN_RESUME_HAS_GENERATED) {
      S.generatedOnce = true;
    }
  } catch (e) {}
  updateGenerateButtons();
  var pdfA = document.getElementById('gen-download-pdf-link');
  var pdfU = buildPdfUrlWithTemplate(S.studioTemplateId);
  var hubU = typeof window.ADMITCV_RESUME_HUB_URL === 'string' ? window.ADMITCV_RESUME_HUB_URL.trim() : '';
  if(pdfA && pdfU) pdfA.href = pdfU;
  if(pdfA){
    pdfA.addEventListener('click', function(){
      persistStudioResumeToLocal(window.__topteenGenResumeBundle);
    });
  }
  var fin = document.getElementById('gen-finish-btn');
  if(fin && hubU){
    fin.setAttribute('href', hubU);
    fin.addEventListener('click', function(ev){
      ev.preventDefault();
      persistStudioResumeToLocal(window.__topteenGenResumeBundle);
      window.location.href = hubU;
    });
  }
  var pr = document.getElementById('gen-print-btn');
  if(pr) pr.addEventListener('click', printGenPreview);
});

function syncBoardExtraField(){
  var sel = document.getElementById('f-board');
  var wrap = document.getElementById('f-board-state-wrap');
  if(!wrap) return;
  var v = sel && sel.value ? String(sel.value).toLowerCase() : '';
  if(v.indexOf('state board') === 0){
    wrap.style.display = '';
  } else {
    wrap.style.display = 'none';
    if(document.getElementById('f-board-state')) sv('f-board-state','');
  }
}

function wireInputs(){
  var inputs = document.querySelectorAll('input,select,textarea');
  for(var i=0;i<inputs.length;i++){
    inputs[i].addEventListener('input', function(){
      this.classList.remove('bad');
      var eid = 'e-' + this.id.replace('f-','');
      var el = document.getElementById(eid);
      if(el) el.classList.remove('show');
      if(this.id === 'f-other-country') clearStudyDestinationErr();
      if(this.id === 'f-board') syncBoardExtraField();
    });
  }
}

/* ═══════════════════════════════════════════════════════
   PAGE ROUTING
═══════════════════════════════════════════════════════ */
function goPage(id){
  var pages = document.querySelectorAll('.pg');
  for(var i=0;i<pages.length;i++) pages[i].classList.remove('on');
  var pg = document.getElementById('pg-'+id);
  if(pg) pg.classList.add('on');

  var nps = document.querySelectorAll('.nav-pill,.np');
  for(var j=0;j<nps.length;j++) nps[j].classList.remove('on');
  if(id==='land'||id==='build'||id==='result'){
    var nb = document.getElementById('np-build');
    if(nb) nb.classList.add('on');
  } else if(id==='dash'){
    var nd = document.getElementById('np-dash');
    if(nd) nd.classList.add('on');
    renderDash();
  }
  window.scrollTo({top:0,behavior:'smooth'});
}

/* ═══════════════════════════════════════════════════════
   STEP NAVIGATION
═══════════════════════════════════════════════════════ */
function goS(n){
  if (n === 7 && !S.generatedOnce) {
    toast('Generate your resume once to unlock templates.');
    n = 6;
  }
  S.step = n;
  // Step 7 needs a wider canvas for the template picker.
  try {
    var wrap = document.querySelector('.bld-wrap');
    if (wrap) {
      if (n === 7) wrap.classList.add('bld-wrap--wide');
      else wrap.classList.remove('bld-wrap--wide');
    }
  } catch (e) {}
  var panels = document.querySelectorAll('.spanel');
  for(var i=0;i<panels.length;i++) panels[i].classList.remove('on');
  var p = document.getElementById('sp'+n);
  if(p) p.classList.add('on');

  for(var s=1;s<=S.STEPS;s++){
    var d = document.getElementById('sd'+s);
    if(!d) continue;
    d.classList.remove('on','done');
    if(s<n) d.classList.add('done');
    else if(s===n) d.classList.add('on');
  }

  var pct = Math.round(((n-1)/(S.STEPS-1))*100);
  var pf = document.getElementById('spf');
  if(pf) pf.style.width = pct+'%';

  if (n === 7) {
    // Ensure templates iframe always loads when entering Step 7.
    initStep7TemplatesEmbed();
  }
  if(n===S.STEPS) buildPreview();
  goPage('build');
  window.scrollTo({top:0,behavior:'smooth'});
}

function nextS(from){
  if(from===1 && !val1()) return;
  if(from===1 && !valTargets()) return;
  if(from===2 && !val2()) return;
  if(from < S.STEPS) goS(from+1);
  else doGenerate(null);
}

function jumpTo(n){
  if (S.generatedOnce) {
    goS(n);
    return;
  }
  if(n<=S.step) goS(n);
}

/* ═══════════════════════════════════════════════════════
   VALIDATION
═══════════════════════════════════════════════════════ */
function val1(){
  var checks = [
    ['f-name','e-name','Please enter your full name'],
    ['f-country','e-country','Please enter your country'],
    ['f-level','e-level','Please select your education level'],
    ['f-course','e-course','Please enter your intended course']
  ];
  var ok = true;
  for(var i=0;i<checks.length;i++){
    var el = document.getElementById(checks[i][0]);
    var er = document.getElementById(checks[i][1]);
    if(el) el.classList.remove('bad');
    if(er) er.classList.remove('show');
    if(el && !el.value.trim()){
      el.classList.add('bad');
      if(er) er.classList.add('show');
      if(ok) toast('⚠ '+checks[i][2]);
      ok = false;
    }
  }
  return ok;
}

function val2(){
  var el = document.getElementById('f-gpa');
  var er = document.getElementById('e-gpa');
  if(el && !el.value.trim()){
    el.classList.add('bad');
    if(er) er.classList.add('show');
    toast('⚠ Please enter your GPA or grade');
    return false;
  }
  return true;
}

/* ═══════════════════════════════════════════════════════
   CHIPS & STYLE
═══════════════════════════════════════════════════════ */
function clearStudyDestinationErr(){
  var el = document.getElementById('e-other-country');
  if(el) el.classList.remove('show');
  var fc = document.getElementById('fc-study-destination');
  if(fc) fc.classList.remove('warn-on');
}

function toggleChip(el){
  el.classList.toggle('on');
  var v = el.textContent.trim();
  var idx = S.unis.indexOf(v);
  if(el.classList.contains('on')){
    if(idx===-1) S.unis.push(v);
  } else {
    if(idx>-1) S.unis.splice(idx,1);
  }
  clearStudyDestinationErr();
}

function pickStyle(tile, key){
  var tiles = document.querySelectorAll('.stile');
  for(var i=0;i<tiles.length;i++) tiles[i].classList.remove('on');
  tile.classList.add('on');
  S.style = key;
  var es = document.getElementById('e-style');
  if(es) es.classList.remove('show');
  var fcs = document.getElementById('fc-admissions-style');
  if(fcs) fcs.classList.remove('warn-on');
}

function syncStyleFromDom(){
  var on = document.querySelector('#style-grid .stile.on') || document.querySelector('.stile.on');
  if(!on) return;
  var key = on.getAttribute('data-style');
  if(key) S.style = key;
}

function val6Style(){
  syncStyleFromDom();
  var on = document.querySelector('#style-grid .stile.on') || document.querySelector('.stile.on');
  if(on){
    var es = document.getElementById('e-style');
    if(es) es.classList.remove('show');
    var fcs = document.getElementById('fc-admissions-style');
    if(fcs) fcs.classList.remove('warn-on');
    return true;
  }
  var es = document.getElementById('e-style');
  if(es) es.classList.add('show');
  var fcs = document.getElementById('fc-admissions-style');
  if(fcs) fcs.classList.add('warn-on');
  toast('⚠ Select an admissions style.');
  return false;
}

function valTargets(){
  clearStudyDestinationErr();
  var oth = gv('f-other-country');
  if(S.unis.length > 0 || oth) return true;
  var err = document.getElementById('e-other-country');
  if(err) err.classList.add('show');
  var fc = document.getElementById('fc-study-destination');
  if(fc) fc.classList.add('warn-on');
  toast('⚠ Add at least one study destination (select country chips or use Other country).');
  return false;
}

function validateForBuild(){
  if(!val1()){ goS(1); return false; }
  if(!val2()){ goS(2); return false; }
  if(!valTargets()){ goS(1); return false; }
  if(!val6Style()) return false;
  var fmt = document.getElementById('f-format');
  if(!fmt || !fmt.value){
    toast('⚠ Choose a resume format.');
    goS(6);
    return false;
  }
  return true;
}

/* ═══════════════════════════════════════════════════════
   DYNAMIC LIST ENTRIES
═══════════════════════════════════════════════════════ */
function seedLists(){
  addSimple('dl-awards','Award','e.g. National Mathematics Olympiad — Silver Medal, top 50 nationally (2024)');
  addSimple('dl-olymp','Competition','e.g. International Mathematical Olympiad — Honourable Mention');
  addLead();
  addExtra();
  addSimple('dl-sport','Sport','e.g. State Under-19 Cricket Captain — led team to Regional Championship 2024');
  addWork('dl-intern','Internship');
  addResearch();
  addWork('dl-community','Community Initiative');
  addWork('dl-projects','Project');
  addLang();
  addSimple('dl-certs','Certification','e.g. Google Data Analytics Certificate — Coursera (2024)');
}

function rmBlk(btn){
  var blk = btn.parentElement && btn.parentElement.parentElement;
  if(!blk) return;
  var list = blk.parentElement;
  if(list && list.children.length > 1){
    blk.remove();
  } else {
    toast('Keep at least one entry');
  }
}

function mkBlk(label, innerHTML){
  var d = document.createElement('div');
  d.className = 'dblk';
  d.innerHTML =
    '<div class="dblk-hd">'+
      '<span class="dblk-lbl">'+label+'</span>'+
      '<button type="button" class="dblk-rm" onclick="rmBlk(this)" title="Remove">&#215;</button>'+
    '</div>'+innerHTML;
  return d;
}

function addSimple(listId, label, ph){
  var list = document.getElementById(listId);
  if(!list) return;
  var n = list.children.length + 1;
  var b = mkBlk(label+' #'+n,
    '<div class="fg fg1"><div class="fld">'+
    '<input type="text" placeholder="'+(ph||'Enter detail')+'">'+
    '</div></div>'
  );
  list.appendChild(b);
}

function addLead(){
  var list = document.getElementById('dl-lead');
  if(!list) return;
  var n = list.children.length + 1;
  var b = mkBlk('Leadership Role #'+n,
    '<div class="fg fg2" style="margin-bottom:10px;">'+
    '<div class="fld"><label class="lbl">Role / Position</label><input type="text" placeholder="e.g. Student Council President"></div>'+
    '<div class="fld"><label class="lbl">Organisation</label><input type="text" placeholder="e.g. DPS R.K. Puram (3,200 students)"></div>'+
    '<div class="fld"><label class="lbl">Duration</label><input type="text" placeholder="e.g. 2023–2024"></div>'+
    '<div class="fld"><label class="lbl">Scale (people led / scope)</label><input type="text" placeholder="e.g. Led 12-member executive council"></div>'+
    '</div>'+
    '<div class="fld"><label class="lbl">Impact &amp; Achievements</label>'+
    '<textarea placeholder="What changed because of your leadership? What did you build, launch, or improve? Include numbers — people impacted, budget managed, events run."></textarea></div>'
  );
  list.appendChild(b);
}

function addExtra(){
  var list = document.getElementById('dl-extra');
  if(!list) return;
  var n = list.children.length + 1;
  var b = mkBlk('Activity #'+n,
    '<div class="fg fg3" style="margin-bottom:10px;">'+
    '<div class="fld"><label class="lbl">Activity Name</label><input type="text" placeholder="e.g. British Parliamentary Debate"></div>'+
    '<div class="fld"><label class="lbl">Level / Award</label><input type="text" placeholder="e.g. National Runner-Up"></div>'+
    '<div class="fld"><label class="lbl">Duration</label><input type="text" placeholder="e.g. 5 years"></div>'+
    '</div>'+
    '<div class="fld"><label class="lbl">Description</label><input type="text" placeholder="e.g. Won 11 of 14 national tournaments; represented school at Pan-India Championship"></div>'
  );
  list.appendChild(b);
}

function addWork(listId, typeName){
  var list = document.getElementById(listId);
  if(!list) return;
  var n = list.children.length + 1;
  var b = mkBlk(typeName+' #'+n,
    '<div class="fg fg3" style="margin-bottom:10px;">'+
    '<div class="fld"><label class="lbl">Role / Title</label><input type="text" placeholder="Role or position held"></div>'+
    '<div class="fld"><label class="lbl">Organisation</label><input type="text" placeholder="Company / NGO / Institution"></div>'+
    '<div class="fld"><label class="lbl">Duration</label><input type="text" placeholder="e.g. Jun–Aug 2024"></div>'+
    '</div>'+
    '<div class="fld"><label class="lbl">Responsibilities &amp; Impact</label>'+
    '<textarea placeholder="Describe your role and measurable achievements. Quantify: team sizes, % improvements, revenue, users, events, people impacted."></textarea></div>'
  );
  list.appendChild(b);
}

function addResearch(){
  var list = document.getElementById('dl-research');
  if(!list) return;
  var n = list.children.length + 1;
  var b = mkBlk('Research / Publication #'+n,
    '<div class="fg fg2" style="margin-bottom:10px;">'+
    '<div class="fld s2"><label class="lbl">Research Title / Paper Name</label><input type="text" placeholder="e.g. Impact of Microfinance on Rural Women\'s Economic Empowerment in Rajasthan"></div>'+
    '<div class="fld"><label class="lbl">Institution / Supervisor / Journal</label><input type="text" placeholder="e.g. IIT Delhi (Prof. Sharma) | Indian Youth Economics Journal"></div>'+
    '<div class="fld"><label class="lbl">Year</label><input type="text" placeholder="e.g. 2023–24"></div>'+
    '<div class="fld"><label class="lbl">Status</label>'+
    '<select><option value="">Publication status...</option>'+
    '<option>Published — Peer-Reviewed Journal</option>'+
    '<option>Published — Conference Proceedings</option>'+
    '<option>Published — Youth / Online Journal</option>'+
    '<option>Under Review / Submitted</option>'+
    '<option>Presented at Conference</option>'+
    '<option>Independent Research (unpublished)</option>'+
    '<option>Lab Research / RA Position</option></select></div>'+
    '</div>'+
    '<div class="fld"><label class="lbl">Methodology &amp; Findings</label>'+
    '<textarea placeholder="Describe your research methodology, sample size, key findings, and significance."></textarea></div>'
  );
  list.appendChild(b);
}

function addLang(){
  var list = document.getElementById('dl-lang');
  if(!list) return;
  var b = mkBlk('Language',
    '<div class="fg fg2">'+
    '<div class="fld"><label class="lbl">Language</label><input type="text" placeholder="e.g. English, Hindi, French"></div>'+
    '<div class="fld"><label class="lbl">Proficiency Level</label>'+
    '<select><option value="">Select level...</option>'+
    '<option>Native / Mother Tongue</option>'+
    '<option>Bilingual Proficiency (C2)</option>'+
    '<option>Full Professional Proficiency (C1)</option>'+
    '<option>Advanced (B2)</option>'+
    '<option>Intermediate (B1)</option>'+
    '<option>Elementary (A2)</option>'+
    '<option>Beginner (A1)</option></select></div>'+
    '</div>'
  );
  list.appendChild(b);
}

/* ═══════════════════════════════════════════════════════
   DATA COLLECTION
═══════════════════════════════════════════════════════ */
function gv(id){
  var el = document.getElementById(id);
  return el ? el.value.trim() : '';
}

function readDList(id){
  var list = document.getElementById(id);
  if(!list) return '';
  var blocks = list.querySelectorAll('.dblk');
  var rows = [];
  for(var i=0;i<blocks.length;i++){
    var inputs = blocks[i].querySelectorAll('input[type="text"],textarea,select');
    var parts = [];
    for(var j=0;j<inputs.length;j++){
      var v = inputs[j].value.trim();
      if(v) parts.push(v);
    }
    if(parts.length) rows.push(parts.join(' | '));
  }
  return rows.join('\n');
}

function readSimpleList(id){
  var list = document.getElementById(id);
  if(!list) return '';
  var inputs = list.querySelectorAll('input[type="text"]');
  var vals = [];
  for(var i=0;i<inputs.length;i++){
    var v = inputs[i].value.trim();
    if(v) vals.push(v);
  }
  return vals.join('\n');
}

function readLangs(){
  var list = document.getElementById('dl-lang');
  if(!list) return '';
  var blocks = list.querySelectorAll('.dblk');
  var langs = [];
  for(var i=0;i<blocks.length;i++){
    var ins = blocks[i].querySelectorAll('input,select');
    var lang  = ins[0] ? ins[0].value.trim() : '';
    var level = ins[1] ? ins[1].value.trim() : '';
    if(lang) langs.push(level ? lang+' ('+level+')' : lang);
  }
  return langs.join(', ');
}

function readTests(){
  var pairs = [
    ['SAT','f-sat'],['ACT','f-act'],['AP','f-ap'],
    ['GRE','f-gre'],['GMAT','f-gmat'],['LSAT','f-lsat'],
    ['IELTS','f-ielts'],['TOEFL','f-toefl'],['Other','f-test-other']
  ];
  var out = [];
  for(var i=0;i<pairs.length;i++){
    var v = gv(pairs[i][1]);
    if(v) out.push(pairs[i][0]+': '+v);
  }
  return out.join(' | ');
}

function collectFD(){
  var unis = S.unis.slice();
  var oth = gv('f-other-country');
  if(oth) unis.push(oth);
  return {
    name:       gv('f-name'),
    email:      gv('f-email'),
    phone:      gv('f-phone'),
    country:    gv('f-country'),
    linkedin:   gv('f-linkedin'),
    portfolio:  gv('f-portfolio'),
    level:      gv('f-level'),
    school:     gv('f-school'),
    course:     gv('f-course'),
    career:     gv('f-career'),
    unis:       unis.join(', '),
    gpa:        gv('f-gpa'),
    board:      gv('f-board'),
    board_state:gv('f-board-state'),
    subjects:   gv('f-subjects'),
    tests:      readTests(),
    awards:     readSimpleList('dl-awards'),
    olymp:      readSimpleList('dl-olymp'),
    lead:       readDList('dl-lead'),
    extra:      readDList('dl-extra'),
    sport:      readSimpleList('dl-sport'),
    intern:     readDList('dl-intern'),
    research:   readDList('dl-research'),
    community:  readDList('dl-community'),
    projects:   readDList('dl-projects'),
    tech:       gv('f-tech'),
    soft:       gv('f-soft'),
    langs:      readLangs(),
    certs:      readSimpleList('dl-certs'),
    personal:   gv('f-personal'),
    hobbies:    gv('f-hobbies'),
    style:      S.style,
    format:     gv('f-format'),
    tag:        gv('f-tag'),
    instr:      gv('f-instr'),
    proofread:  !!(document.getElementById('f-proofread') && document.getElementById('f-proofread').checked),
    ts:         new Date().toISOString()
  };
}

/* ═══════════════════════════════════════════════════════
   PREVIEW (Step 6)
═══════════════════════════════════════════════════════ */
function buildPreview(){
  var el = document.getElementById('preview-box');
  if(!el) return;
  var d = collectFD();
  var lines = [];
  if(d.name)    lines.push('<strong style="color:var(--prose)">'+esc(d.name)+'</strong> · '+esc(d.country||'International'));
  if(d.level)   lines.push('<span style="color:var(--prose3)">Level:</span> '+esc(d.level));
  if(d.course)  lines.push('<span style="color:var(--prose3)">Applying for:</span> '+esc(d.course));
  if(d.unis)    lines.push('<span style="color:var(--prose3)">Study destinations:</span> <span style="color:var(--aurum2)">'+esc(d.unis)+'</span>');
  if(d.gpa)     lines.push('<span style="color:var(--prose3)">Grade:</span> '+esc(d.gpa));
  if(d.tests)   lines.push('<span style="color:var(--prose3)">Tests:</span> '+esc(d.tests));
  if(d.career)  lines.push('<span style="color:var(--prose3)">Goal:</span> <em>'+esc(d.career)+'</em>');
  el.innerHTML = lines.length
    ? lines.map(function(l){return '<div style="margin-bottom:5px;">'+l+'</div>';}).join('')
    : '<span style="color:var(--prose4)">Complete earlier steps to see your profile summary here.</span>';
}

function esc(s){
  return String(s||'')
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}

/* ═══════════════════════════════════════════════════════
   AI GENERATION
═══════════════════════════════════════════════════════ */
var STYLE_D = {
  ivy_league:
    'Ivy League (Harvard, Yale, Princeton, Columbia, Penn, Brown, Dartmouth, Cornell) — '+
    'achievement-driven with quantified impact, leadership narrative, intellectual vitality and curiosity, '+
    'initiative, depth of commitment, transformational thinking',
  oxford_cambridge:
    'Oxford / Cambridge — academic rigour above all, genuine deep subject passion, '+
    'super-curricular activities beyond the curriculum, reading lists and independent intellectual exploration, '+
    'research-oriented mindset, critical analytical engagement, intellectual independence',
  russell_group:
    'Russell Group UK (UCL, LSE, Imperial, Warwick, Edinburgh, KCL, Manchester) — '+
    'analytical sharpness, interdisciplinary thinking, professional ambition, policy awareness, '+
    'global perspective, independence of thought, employability orientation',
  scholarship:
    'Scholarship Applications (Chevening, Rhodes, Gates Cambridge, Aga Khan, Commonwealth, Fulbright) — '+
    'leadership in context of adversity, transformative community impact, future potential, '+
    'moral character, resilience, global citizenship, clear development mission',
  research_cv:
    'Research CV / PhD — publications and presentations, rigorous research methodology, '+
    'intellectual contributions, identification of gaps in literature, supervisor and faculty fit, '+
    'academic lineage, theoretical frameworks, research independence',
  mba:
    'MBA / Business School (Wharton, HBS, INSEAD, LBS, Booth, Sloan, Kellogg) — '+
    'quantified P&L and business impact with exact figures, team leadership at scale, '+
    'career progression arc, entrepreneurial initiatives, strategic thinking, global exposure'
};

var STYLE_LBL = {
  ivy_league:'Ivy League',oxford_cambridge:'Oxford / Cambridge',
  russell_group:'Russell Group UK',scholarship:'Scholarship',
  research_cv:'Research CV',mba:'MBA / Leadership'
};

var STYLE_ICO = {
  ivy_league:'🏛️',oxford_cambridge:'📖',russell_group:'🎓',
  scholarship:'🏆',research_cv:'🔬',mba:'💼'
};

function buildPrompt(d, rewrite){
  return 'You are a world-class university admissions consultant and professional CV writer with 20+ years experience. Generate a complete, strategically optimised admissions resume in clean HTML.\n\n'+
    'COMPLETE STUDENT PROFILE:\n'+
    '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'+
    'NAME: '+(d.name||'N/A')+'\nCOUNTRY: '+(d.country||'N/A')+'\nEMAIL: '+(d.email||'N/A')+'\nPHONE: '+(d.phone||'N/A')+'\n'+
    'LINKEDIN: '+(d.linkedin||'N/A')+'\nPORTFOLIO: '+(d.portfolio||'N/A')+'\n'+
    'EDUCATION LEVEL: '+(d.level||'N/A')+'\nSCHOOL: '+(d.school||'N/A')+'\n'+
    'INTENDED COURSE: '+(d.course||'N/A')+'\nCAREER GOAL: '+(d.career||'N/A')+'\n'+
    'STUDY DESTINATIONS (countries): '+(d.unis||'Not specified — infer globally competitive positioning')+'\n\n'+
    'ACADEMIC RECORD:\nGPA / GRADE: '+(d.gpa||'N/A')+'\nGRADING BOARD: '+(([d.board,d.board_state].filter(Boolean).join(' — '))||'N/A')+'\n'+
    'KEY SUBJECTS: '+(d.subjects||'N/A')+'\nTEST SCORES: '+(d.tests||'None provided')+'\n'+
    'ACADEMIC AWARDS:\n'+(d.awards||'None listed')+'\nOLYMPIADS & COMPETITIONS:\n'+(d.olymp||'None listed')+'\n\n'+
    'LEADERSHIP & ACTIVITIES:\n'+(d.lead||'None listed')+'\n\nEXTRACURRICULAR ACTIVITIES:\n'+(d.extra||'None listed')+'\n\nSPORTS:\n'+(d.sport||'None listed')+'\n\n'+
    'PROFESSIONAL EXPERIENCE:\nINTERNSHIPS:\n'+(d.intern||'None listed')+'\n\nRESEARCH & PUBLICATIONS:\n'+(d.research||'None listed')+'\n\n'+
    'COMMUNITY SERVICE:\n'+(d.community||'None listed')+'\n\nPROJECTS & ENTREPRENEURSHIP:\n'+(d.projects||'None listed')+'\n\n'+
    'SKILLS & CREDENTIALS:\nTECHNICAL SKILLS: '+(d.tech||'None listed')+'\nSOFT SKILLS: '+(d.soft||'None listed')+'\n'+
    'LANGUAGES: '+(d.langs||'None listed')+'\nCERTIFICATIONS:\n'+(d.certs||'None listed')+'\n'+
    'PERSONAL ACHIEVEMENTS:\n'+(d.personal||'None listed')+'\nHOBBIES & INTERESTS: '+(d.hobbies||'None listed')+'\n\n'+
    'RESUME CONFIGURATION:\nSTYLE: '+(STYLE_D[d.style]||d.style)+'\nFORMAT: '+(d.format||'one_page')+'\n'+
    'TAGLINE: '+(d.tag||'')+'\nSPECIAL INSTRUCTIONS: '+(d.instr||'None')+'\n'+
    'SPELLING / GRAMMAR CHECK REQUESTED: '+(d.proofread ? 'Yes — carefully proofread and correct spelling/typos while preserving the student\'s voice.' : 'No — keep original spelling and phrasing except for critical clarity issues.')+'\n'+
    (rewrite ? 'REWRITE MODE: '+rewrite+'\n' : '')+
    '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'+
    'LANGUAGE TRANSFORMATION RULES — APPLY TO EVERY BULLET:\n'+
    '• NEVER use: "I participated", "helped with", "was responsible for", "was part of", "assisted"\n'+
    '• ALWAYS use elite action verbs: Spearheaded, Pioneered, Orchestrated, Catalysed, Architected, Championed, Synthesised, Directed, Mobilised, Instituted, Steered, Elevated, Engineered, Galvanised, Forged\n'+
    '• Quantify everything: team sizes, percentages, currency amounts, rankings, people impacted, timeframes\n'+
    '• Transform weak statements into powerful achievement narratives:\n'+
    '  WEAK: "Helped NGO with teaching" → STRONG: "Designed and delivered 8-week financial literacy curriculum to 130+ underprivileged students across 3 government schools; trained 5 peer educators to sustain programme independently"\n'+
    '  WEAK: "Member of debate club" → STRONG: "Competed in British Parliamentary Debate for 5 years achieving National Runner-Up at Pan-India Championship 2024, winning 11 of 14 tournaments entered"\n'+
    '• Every bullet must prove IMPACT, SCALE, DEPTH, or RECOGNITION\n\n'+
    'HTML OUTPUT — USE ONLY THESE CSS CLASSES (already defined on the page):\n'+
    'rv-name, rv-tag, rv-con, rv-sec, rv-sh, rv-it, rv-ith, rv-itn, rv-itd, rv-ito, rv-bul (ul), rv-bul li, rv-sum, rv-skw (div), rv-sk (span)\n\n'+
    'REQUIRED SECTIONS — include all that have data:\n'+
    '1. Header: rv-name (full name), rv-tag (course + study-destination tagline), rv-con (contact row with all provided details — wrap linkedin/portfolio in <a href="..."> tags)\n'+
    '2. Profile Summary: rv-sum — 3-4 powerful sentences: identity, unique strengths, ambition, fit with stated study destinations\n'+
    '3. Education — school, board, grades, subjects, relevant coursework\n'+
    '4. Standardised Test Scores (if any provided)\n'+
    '5. Academic Honours & Awards (if any)\n'+
    '6. Leadership & Positions of Responsibility\n'+
    '7. Research & Intellectual Pursuits (if any)\n'+
    '8. Professional Experience & Internships (if any)\n'+
    '9. Community Impact & Social Initiatives (if any)\n'+
    '10. Extracurricular Activities & Sports\n'+
    '11. Projects & Entrepreneurship (if any)\n'+
    '12. Skills, Languages & Certifications\n\n'+
    'CRITICAL OUTPUT RULES:\n'+
    '• Output ONLY the resume HTML — no preamble, no markdown fences, no explanation\n'+
    '• Immediately after the HTML, on a NEW LINE, output exactly: SCORES:{...json...}\n'+
    '• SCORES JSON must contain: academic, leadership, research, extracurricular, community, global, ats, overall, fit (all integers 0-100), tier ("Competitive"|"Strong"|"Outstanding"|"Elite"), suggestions (array of 4 specific actionable strings), booster (string with specific improvements if weak areas exist, otherwise empty string "")\n'+
    '• Score honestly: thin profile = 45-65, average = 65-75, strong = 75-85, elite = 85-95\n'+
    '• The entire response = [HTML][newline]SCORES:{json} — nothing else.';
}

function buildPlainResumeSummary(d){
  var L = [];
  var head = (d.name || 'Student');
  if(d.course) head += ' — ' + d.course;
  if(d.country) head += ' (' + d.country + ')';
  L.push(head);
  if(d.unis) L.push('Study destinations: ' + d.unis);
  if(d.level || d.school) L.push('Education: ' + [d.level, d.school].filter(Boolean).join(' · '));
  if(d.gpa || d.board || d.subjects){
    L.push('Academic: ' + [d.gpa, d.board].filter(Boolean).join(' · ') + (d.subjects ? ' | Subjects: ' + d.subjects : ''));
  }
  if(d.tests) L.push('Tests: ' + d.tests);
  if(d.career) L.push('Career goal: ' + d.career);
  [
    ['Awards', d.awards], ['Competitions', d.olymp], ['Leadership', d.lead], ['Activities', d.extra], ['Sports', d.sport],
    ['Internships', d.intern], ['Research', d.research], ['Community', d.community], ['Projects', d.projects]
  ].forEach(function(pair){
    if(pair[1] && String(pair[1]).trim()) L.push(pair[0] + ':\n' + pair[1]);
  });
  if(d.tech || d.soft) L.push('Skills: ' + [d.tech, d.soft].filter(Boolean).join(' | '));
  if(d.langs) L.push('Languages: ' + d.langs);
  if(d.certs) L.push('Certifications:\n' + d.certs);
  if(d.personal) L.push('Achievements & notes:\n' + d.personal);
  if(d.hobbies) L.push('Interests: ' + d.hobbies);
  L.push('');
  L.push('Admissions style: ' + (STYLE_LBL[d.style] || d.style));
  L.push('Format: ' + String(d.format || '').replace(/_/g, ' '));
  if(d.instr) L.push('Special instructions: ' + d.instr);
  return L.join('\n\n');
}

function buildLocalResumeHtml(d){
  function sec(title, body){
    if(!body || !String(body).trim()) return '';
    return '<div class="rv-sec"><div class="rv-sh">'+esc(title)+'</div>'+body+'</div>';
  }
  function bullets(text){
    if(!text || !String(text).trim()) return '';
    var items = String(text).split(/\n+/).map(function(s){ return s.trim(); }).filter(Boolean);
    if(!items.length) return '';
    return '<ul class="rv-bul">'+items.map(function(s){
      return '<li>'+esc(s)+'</li>';
    }).join('')+'</ul>';
  }
  var tag = d.tag || [d.course, (d.unis || '').split(',')[0]].filter(Boolean).join(' · ');
  var out = [];
  out.push('<div class="rv-name">'+esc(d.name || 'Student')+'</div>');
  out.push('<div class="rv-tag">'+esc(tag)+'</div>');
  var cons = [];
  if(d.email) cons.push(esc(d.email));
  if(d.phone) cons.push(esc(d.phone));
  if(d.country) cons.push(esc(d.country));
  if(d.linkedin && /^https?:\/\//i.test(String(d.linkedin).trim())){
    cons.push('<a href="'+String(d.linkedin).trim().replace(/"/g,'')+'">LinkedIn</a>');
  }
  if(d.portfolio && /^https?:\/\//i.test(String(d.portfolio).trim())){
    cons.push('<a href="'+String(d.portfolio).trim().replace(/"/g,'')+'">Portfolio</a>');
  }
  out.push('<div class="rv-con">'+cons.join(' · ')+'</div>');
  var sumParts = [];
  if(d.course && d.unis){
    var u = d.unis.split(',').map(function(x){ return x.trim(); }).filter(Boolean);
    sumParts.push('Targeting study in ' + u.slice(0, 4).join(', ') + (u.length > 4 ? ', and further destinations.' : '.'));
  }
  if(d.level) sumParts.push('Currently: ' + d.level + (d.school ? ' at ' + d.school : '') + '.');
  if(d.career) sumParts.push('Long-term goal: ' + d.career + '.');
  var sum = sumParts.join(' ');
  if(sum.trim()) out.push('<div class="rv-sum">'+esc(sum)+'</div>');

  var eduBody = '';
  var eduHead = [d.level, d.school].filter(Boolean).join(' · ');
  if(eduHead || d.gpa || d.board || d.subjects){
    eduBody += '<div class="rv-it">';
    if(eduHead) eduBody += '<div class="rv-ith"><span class="rv-itn">'+esc(eduHead)+'</span></div>';
    if(d.gpa || d.board) eduBody += '<div class="rv-ito">'+esc([d.gpa, d.board].filter(Boolean).join(' · '))+'</div>';
    if(d.subjects) eduBody += '<ul class="rv-bul"><li>'+esc(d.subjects)+'</li></ul>';
    eduBody += '</div>';
  }
  out.push(sec('Education', eduBody));

  if(d.tests) out.push(sec('Standardised tests', bullets(d.tests.replace(/\s*\|\s*/g, '\n'))));
  if(d.awards) out.push(sec('Honours & awards', bullets(d.awards)));
  if(d.olymp) out.push(sec('Olympiads & competitions', bullets(d.olymp)));
  if(d.lead) out.push(sec('Leadership', bullets(d.lead)));
  if(d.extra) out.push(sec('Extracurricular activities', bullets(d.extra)));
  if(d.sport) out.push(sec('Sports & athletics', bullets(d.sport)));
  if(d.intern) out.push(sec('Experience & internships', bullets(d.intern)));
  if(d.research) out.push(sec('Research', bullets(d.research)));
  if(d.community) out.push(sec('Community service', bullets(d.community)));
  if(d.projects) out.push(sec('Projects', bullets(d.projects)));
  var skills = [d.tech ? 'Technical: ' + d.tech : '', d.soft ? 'Soft skills: ' + d.soft : ''].filter(Boolean).join('\n');
  if(skills) out.push(sec('Skills', bullets(skills)));
  if(d.langs) out.push(sec('Languages', '<div class="rv-it"><div class="rv-ito">'+esc(d.langs)+'</div></div>'));
  if(d.certs) out.push(sec('Certifications', bullets(d.certs)));
  if(d.personal || d.hobbies) out.push(sec('Additional', bullets([d.personal, d.hobbies].filter(Boolean).join('\n'))));
  var foot = 'Calibrated for ' + (STYLE_LBL[d.style] || d.style) + ' · ' + String(d.format || '').replace(/_/g, ' ');
  out.push(sec('Profile configuration', '<div class="rv-it"><div class="rv-ito">'+esc(foot) + (d.instr ? ' — Notes: ' + esc(d.instr) : '')+'</div></div>'));
  return out.join('');
}

function getCsrfToken(){
  var m = document.cookie.match(/csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1].replace(/^"+|"+$/g, '')) : '';
}

var __genProgTimer = null;
var __genProgVal = 0;
var __genOverlayTimer = null;

function stopGenOverlayTimer(){
  if(__genOverlayTimer){
    clearTimeout(__genOverlayTimer);
    __genOverlayTimer = null;
  }
}

function setOverlayStep(activeIdx){
  var steps = document.querySelectorAll('#overlay .ov-step');
  for(var i=0;i<steps.length;i++){
    steps[i].classList.remove('show','cur','done');
    if(i < activeIdx){
      steps[i].classList.add('show','done');
    } else if(i === activeIdx){
      steps[i].classList.add('show','cur');
    }
  }
}

function showGenOverlay(){
  var ov = document.getElementById('overlay');
  if(!ov) return;
  stopGenOverlayTimer();
  ov.classList.add('on');
  ov.setAttribute('aria-hidden', 'false');
  var ttl = document.getElementById('gen-overlay-title');
  if(ttl) ttl.textContent = 'Generating your resume';
  var sub = document.getElementById('gen-overlay-sub');
  if(sub) sub.textContent = 'AI is analyzing your profile and building a polished resume.';
  setOverlayStep(0);
  __genOverlayTimer = setTimeout(function(){ setOverlayStep(1); }, 900);
}

function markGenOverlayNearDone(){
  var ov = document.getElementById('overlay');
  if(!ov || !ov.classList.contains('on')) return;
  stopGenOverlayTimer();
  setOverlayStep(2);
  var ttl = document.getElementById('gen-overlay-title');
  if(ttl) ttl.textContent = 'Almost done';
  var sub = document.getElementById('gen-overlay-sub');
  if(sub) sub.textContent = 'Final checks are running before opening the next step.';
}

function hideGenOverlay(){
  stopGenOverlayTimer();
  var ov = document.getElementById('overlay');
  if(!ov) return;
  ov.classList.remove('on');
  ov.setAttribute('aria-hidden', 'true');
}

function stopGenProgressTimer(){
  if(__genProgTimer){
    clearInterval(__genProgTimer);
    __genProgTimer = null;
  }
}

function setGenProgAria(pct){
  var bar = document.getElementById('gen-progress-bar');
  if(bar) bar.setAttribute('aria-valuenow', String(Math.round(Math.min(pct, 100))));
}

function updateGenProgFill(){
  var fill = document.getElementById('gen-progress-fill');
  if(fill) fill.style.width = Math.min(__genProgVal, 100) + '%';
  setGenProgAria(__genProgVal);
}

function startGenProgressUI(){
  var w = document.getElementById('gen-progress-wrap');
  var pv = document.getElementById('gen-preview-wrap');
  if(pv) pv.style.display = 'none';
  if(w){
    w.style.display = 'block';
    w.setAttribute('aria-busy', 'true');
  }
  var head = document.getElementById('gen-progress-head');
  if(head) head.textContent = 'Generating your resume';
  var sub = document.getElementById('gen-progress-sub');
  if(sub) sub.textContent = 'Sending your profile to the AI…';
  __genProgVal = 5;
  updateGenProgFill();
  stopGenProgressTimer();
  __genProgTimer = setInterval(function(){
    if(__genProgVal < 88) {
      __genProgVal += Math.random() * 4.5 + 0.9;
      if(__genProgVal > 88) __genProgVal = 88;
      updateGenProgFill();
    }
  }, 400);
}

function pulseGenProgressNearDone(){
  var sub = document.getElementById('gen-progress-sub');
  if(sub) sub.textContent = 'Formatting resume layout and saving to your account…';
}

function finishGenProgressSuccess(){
  stopGenProgressTimer();
  __genProgVal = 100;
  updateGenProgFill();
  var head = document.getElementById('gen-progress-head');
  if(head) head.textContent = 'Almost done';
  pulseGenProgressNearDone();
  markGenOverlayNearDone();
}

function hideGenProgressUI(){
  var w = document.getElementById('gen-progress-wrap');
  if(w){
    w.style.display = 'none';
    w.setAttribute('aria-busy', 'false');
  }
}

function stripTrailingMarkerBlock(raw, marker){
  raw = String(raw || '');
  var tag = '\n' + marker + ':';
  var i = raw.lastIndexOf(tag);
  if (i < 0) return raw;
  var j = raw.indexOf('{', i);
  if (j < 0) return raw.slice(0, i).trim();
  var depth = 0;
  for (var k = j; k < raw.length; k++) {
    var c = raw.charAt(k);
    if (c === '{') depth++;
    else if (c === '}') {
      depth--;
      if (depth === 0) return raw.slice(0, i).trim();
    }
  }
  return raw.slice(0, i).trim();
}

function stripAiTrailersForHtml(raw){
  var s = String(raw || '');
  s = stripTrailingMarkerBlock(s, 'SCORES');
  s = stripTrailingMarkerBlock(s, 'RESUME_DATA');
  return stripMarkdownFences(s.trim());
}

function parseJsonAfterLastMarker(raw, marker){
  raw = String(raw || '');
  var tag = '\n' + marker + ':';
  var i = raw.lastIndexOf(tag);
  if (i < 0) return null;
  var j = raw.indexOf('{', i);
  if (j < 0) return null;
  var depth = 0;
  for (var k = j; k < raw.length; k++) {
    var c = raw.charAt(k);
    if (c === '{') depth++;
    else if (c === '}') {
      depth--;
      if (depth === 0) {
        try {
          return JSON.parse(raw.slice(j, k + 1));
        } catch (e) {
          return null;
        }
      }
    }
  }
  return null;
}

function parseScoreMetaFromRaw(raw){
  var out = { tier: '', overall: null };
  var p = parseJsonAfterLastMarker(raw, 'SCORES');
  if (!p || typeof p !== 'object') return out;
  try {
    if (p.tier) out.tier = String(p.tier);
    if (p.overall != null && p.overall !== '') out.overall = parseInt(p.overall, 10);
  } catch (e) {}
  return out;
}

function stripMarkdownFences(s){
  var t = String(s||'').trim();
  if(!t) return '';
  t = t.replace(/^```\s*[\w-]*\s*\r?\n/i, '');
  t = t.trim();
  if(t.indexOf('```') === 0){
    var nl = t.indexOf('\n');
    if(nl !== -1) t = t.slice(nl + 1).replace(/^\s+/, '');
    else t = t.replace(/^```\s*/, '');
  }
  t = t.trim();
  t = t.replace(/\r?\n```\s*$/m, '');
  t = t.replace(/```\s*$/m, '');
  return t.trim();
}

function showStudioInlinePreview(htmlClean, raw, d, rid, dest, plain, serverPreviewHtml){
  var body = document.getElementById('gen-preview-body');
  var shown = (serverPreviewHtml && String(serverPreviewHtml).trim())
    ? String(serverPreviewHtml)
    : htmlClean;
  if(body) body.innerHTML = shown;
  var meta = document.getElementById('gen-preview-meta');
  if(meta){
    var topU = d.unis ? d.unis.split(',').slice(0,3).map(function(u){return u.trim();}).filter(Boolean).join(', ') : '';
    meta.textContent = (STYLE_LBL[d.style]||d.style) + (topU ? ' · ' + topU : '');
  }
  var sc = parseScoreMetaFromRaw(raw);
  var bd = document.getElementById('gen-preview-badge');
  if(bd){
    if(sc.tier || (sc.overall != null && !isNaN(sc.overall))){
      bd.style.display = 'block';
      var parts = [];
      if(sc.tier) parts.push(sc.tier);
      if(sc.overall != null && !isNaN(sc.overall)) parts.push('Overall ' + sc.overall + '/100');
      bd.textContent = parts.join(' · ');
    } else {
      bd.style.display = 'none';
    }
  }
  var wrap = document.getElementById('gen-preview-wrap');
  if(wrap) wrap.style.display = 'block';
  var pdfA = document.getElementById('gen-download-pdf-link');
  var pdfU = buildPdfUrlWithTemplate(S.studioTemplateId);
  if(pdfA && pdfU) pdfA.href = pdfU;
  var hubU = typeof window.ADMITCV_RESUME_HUB_URL === 'string' ? window.ADMITCV_RESUME_HUB_URL.trim() : '';
  var fin = document.getElementById('gen-finish-btn');
  if(fin && hubU) fin.setAttribute('href', hubU);
  window.__topteenGenResumeBundle = { html: shown, plain: plain, dest: dest, d: d, rid: rid };
  hideGenProgressUI();
  if(wrap) wrap.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function initStep7TemplatesEmbed(){
  var frame = document.getElementById('studio-template-picker-frame-step7');
  if (!frame) return;
  var u = (typeof window.ADMITCV_RESUME_TEMPLATES_EMBED_URL === 'string' ? window.ADMITCV_RESUME_TEMPLATES_EMBED_URL : '').trim();
  if (u) frame.src = (u.indexOf('?') >= 0 ? (u + '&mode=picker') : (u + '?mode=picker'));
}

function doGenerate(rewrite){
  /* Top Teen: validate → server OpenAI → progress UI → inline preview → user continues to editor */
  if (rewrite) {
    toast('Use the classic resume editor to refine your sections.');
    return;
  }
  if (!validateForBuild()) return;

  var btn = document.getElementById('gen-btn');
  var btnDefault = (btn && btn.textContent) ? btn.textContent : 'Generate My Resume';
  if(btn){
    btn.disabled = true;
    btn.textContent = 'Generating…';
  }

  syncStyleFromDom();
  var d = collectFD();
  S.fd = d;

  var genUrl = typeof window.ADMITCV_RESUME_GENERATE_URL === 'string' ? window.ADMITCV_RESUME_GENERATE_URL.trim() : '';
  var rid = (typeof window.TOPTEEN_RESUME_ID !== 'undefined' && window.TOPTEEN_RESUME_ID !== null && window.TOPTEEN_RESUME_ID !== '')
    ? String(window.TOPTEEN_RESUME_ID) : '';
  var classicBase = (typeof window.ADMITCV_RESUME_CLASSIC_URL === 'string' && window.ADMITCV_RESUME_CLASSIC_URL)
    ? window.ADMITCV_RESUME_CLASSIC_URL
    : (rid ? '/user/resume-builder/edit/' + rid + '/' : '/user/resume-builder/');
  var join = classicBase.indexOf('?') >= 0 ? '&' : '?';
  var dest = classicBase + join + 'from_guided=1';

  function restoreBtn(){
    if(btn){
      btn.disabled = false;
      btn.textContent = btnDefault;
    }
  }

  function onGenFailure(){
    stopGenProgressTimer();
    hideGenProgressUI();
    hideGenOverlay();
    restoreBtn();
  }

  startGenProgressUI();
  showGenOverlay();

  if (!genUrl) {
    toast('Resume AI is not configured (missing generate URL).');
    onGenFailure();
    return;
  }

  var payload = { draft: d };
  if (rid) {
    var n = parseInt(rid, 10);
    if (!isNaN(n) && n > 0) payload.resume_id = n;
  }
  fetch(genUrl, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken()
    },
    body: JSON.stringify(payload)
  })
    .then(function (r) {
      return r.text().then(function (text) {
        var j = {};
        try {
          j = text ? JSON.parse(text) : {};
        } catch (e) {
          j = { error: text ? text.slice(0, 240) : 'Invalid server response' };
        }
        return { ok: r.ok, status: r.status, j: j };
      });
    })
    .then(function (res) {
      if (!res.ok) {
        toast((res.j && res.j.error) ? res.j.error : ('Error ' + (res.status || '')));
        onGenFailure();
        return;
      }
      var raw = (res.j && res.j.html) ? String(res.j.html) : '';
      var html = stripAiTrailersForHtml(raw);
      var previewHtml = (res.j && res.j.preview_html) ? String(res.j.preview_html) : '';
      if (!html && !(previewHtml || '').trim()) {
        toast('No resume HTML was returned. Try again.');
        onGenFailure();
        return;
      }
      var plain = buildPlainResumeSummary(d);
      finishGenProgressSuccess();
      setTimeout(function(){
        hideGenOverlay();
        showStudioInlinePreview(html, raw, d, rid, dest, plain, previewHtml);
        // After generating, move the user to templates/download step.
        S.generatedOnce = true;
        updateGenerateButtons();
        goS(7);
        restoreBtn();
      }, 420);
    })
    .catch(function () {
      toast('Network error — check your connection and try again.');
      onGenFailure();
    });
}

/* ═══════════════════════════════════════════════════════
   RENDER RESULT
═══════════════════════════════════════════════════════ */
function renderResult(raw, d){
  S.busy = false;

  /* parse scores */
  var sc = {
    academic:72,leadership:68,research:60,extracurricular:70,
    community:65,global:70,ats:78,overall:70,fit:72,
    tier:'Competitive',suggestions:[],booster:''
  };
  var pscores = parseJsonAfterLastMarker(raw, 'SCORES');
  if (pscores && typeof pscores === 'object') {
    try {
      var keys = Object.keys(pscores);
      for (var k = 0; k < keys.length; k++) sc[keys[k]] = pscores[keys[k]];
    } catch (e) {
      console.warn('[AdmitCV] score parse', e);
    }
  }
  raw = stripAiTrailersForHtml(raw);

  S.rhtml = raw;
  S.scores = sc;

  /* populate resume */
  var out = document.getElementById('rv-out');
  if(out) out.innerHTML = raw;

  /* meta */
  var metaEl = document.getElementById('res-meta');
  if(metaEl){
    var topU = d.unis ? d.unis.split(',').slice(0,3).map(function(u){return u.trim();}).join(', ') : 'Study destinations TBD';
    metaEl.textContent = (STYLE_LBL[d.style]||d.style)+' style · '+topU+' · '+new Date().toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'});
  }

  /* filename */
  var fn = document.getElementById('rv-fn');
  if(fn) fn.textContent = d.name.toLowerCase().replace(/\s+/g,'-')+'-admitcv.pdf';

  /* badges */
  setText('sb-ov',  sc.overall+'/100');
  setText('sb-fit', sc.fit+'/100');
  setText('sb-ats', sc.ats+'/100');

  /* overall ring */
  setText('ov-val', sc.overall);
  var tierMsg = {
    'Elite':'World-class application readiness',
    'Outstanding':'Strong candidate at top universities',
    'Strong':'Competitive for stated study destinations',
    'Competitive':'Targeted improvements will strengthen your application'
  };
  setText('ov-tier', sc.tier||'Competitive');
  setText('ov-desc', tierMsg[sc.tier]||'Profile evaluated across 6 dimensions');

  /* score bars */
  var dims = [
    {l:'Academic Excellence',k:'academic'},
    {l:'Leadership',k:'leadership'},
    {l:'Research & Intellect',k:'research'},
    {l:'Extracurriculars',k:'extracurricular'},
    {l:'Community Impact',k:'community'},
    {l:'Global Competitiveness',k:'global'}
  ];
  var barsEl = document.getElementById('sc-bars');
  if(barsEl){
    barsEl.innerHTML = dims.map(function(dim){
      return '<div class="sc-row">'+
        '<div class="sc-row-top"><span class="sc-lbl">'+dim.l+'</span><span class="sc-val">'+(sc[dim.k]||0)+'/100</span></div>'+
        '<div class="sc-track"><div class="sc-fill" data-w="'+(sc[dim.k]||0)+'"></div></div>'+
        '</div>';
    }).join('');
    setTimeout(function(){
      var fills = barsEl.querySelectorAll('.sc-fill');
      for(var i=0;i<fills.length;i++) fills[i].style.width = (fills[i].getAttribute('data-w')||'0')+'%';
    }, 100);
  }

  /* suggestions */
  var sugEl = document.getElementById('sug-list');
  if(sugEl){
    var icons = ['💡','📈','🎯','⚡','🔑','📚'];
    var sugs = Array.isArray(sc.suggestions) ? sc.suggestions : [];
    sugEl.innerHTML = sugs.length
      ? sugs.map(function(s,i){
          return '<div class="sug"><span class="sug-ico">'+(icons[i]||'→')+'</span><span>'+esc(s)+'</span></div>';
        }).join('')
      : '<div class="sug"><span class="sug-ico">✅</span><span>Excellent profile — continue building on existing strengths.</span></div>';
  }

  /* booster */
  var bst = document.getElementById('booster');
  var bstBd = document.getElementById('booster-bd');
  if(bst && bstBd){
    if(sc.booster && sc.booster.trim()){
      bst.style.display = 'block';
      bstBd.innerHTML = sc.booster.replace(/\n/g,'<br>');
    } else {
      bst.style.display = 'none';
    }
  }

  /* reveal */
  var ov = document.getElementById('overlay');
  if(ov) ov.classList.remove('on');
  var rp = document.getElementById('pg-result');
  if(rp) rp.style.visibility = 'visible';
  window.scrollTo({top:0,behavior:'smooth'});
}

function setText(id, val){
  var el = document.getElementById(id);
  if(el) el.textContent = val;
}

/* ═══════════════════════════════════════════════════════
   REWRITE
═══════════════════════════════════════════════════════ */
function doRewrite(instr){
  if(!S.fd){ toast('Generate a resume first'); return; }
  doGenerate(instr);
}

/* ═══════════════════════════════════════════════════════
   EXPORT ACTIONS
═══════════════════════════════════════════════════════ */
function doCopy(){
  var el = document.getElementById('rv-out');
  if(!el){ toast('No resume to copy'); return; }
  var txt = el.innerText || el.textContent || '';
  if(!txt.trim()){ toast('No resume content'); return; }
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(txt)
      .then(function(){ toast('✓ Resume copied to clipboard'); })
      .catch(function(){ fallbackCopy(txt); });
  } else {
    fallbackCopy(txt);
  }
}

function fallbackCopy(txt){
  var ta = document.createElement('textarea');
  ta.value = txt;
  ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px;';
  document.body.appendChild(ta);
  ta.select();
  var ok = false;
  try{ ok = document.execCommand('copy'); } catch(e){}
  document.body.removeChild(ta);
  toast(ok ? '✓ Resume copied' : '❌ Copy failed — please select and copy manually');
}

function printGenPreview(){
  var b = document.getElementById('gen-preview-body');
  if(!b || !String(b.innerHTML || '').trim()){ toast('Nothing to print yet'); return; }
  var html = b.innerHTML;
  var nm = (S.fd && S.fd.name) ? S.fd.name : 'Resume';
  var win = window.open('', '_blank');
  if(!win){ toast('Pop-up blocked — allow pop-ups to print'); return; }
  win.document.write(
    '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>' + nm + '</title>' +
    '<style>*{box-sizing:border-box}body{margin:0;padding:24px;font-family:Outfit,system-ui,sans-serif;font-size:13px;color:#1a1a2e}' +
    '@media print{@page{margin:14mm}body{padding:0}}</style></head><body>' + html + '</body></html>'
  );
  win.document.close();
  setTimeout(function(){ win.print(); }, 350);
}

function doPrint(){
  var content = document.getElementById('rv-out');
  if(!content){ toast('No resume to print'); return; }
  var html = content.innerHTML;
  var nm = S.fd ? S.fd.name : 'Resume';
  var win = window.open('','_blank');
  if(!win){ toast('❌ Pop-up blocked — please allow pop-ups and try again'); return; }
  win.document.write(
    '<!DOCTYPE html><html lang="en"><head>'+
    '<meta charset="UTF-8">'+
    '<title>'+nm+' — AdmitCV AI</title>'+
    '<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400&family=Outfit:wght@300;400;500;600&display=swap" rel="stylesheet">'+
    '<style>'+
    '*{margin:0;padding:0;box-sizing:border-box}'+
    'body{font-family:"Outfit",sans-serif;color:#1a1a2e;padding:44px 52px;max-width:820px;margin:0 auto;font-size:13px;-webkit-print-color-adjust:exact;print-color-adjust:exact}'+
    '.rv-name{font-family:"Cormorant Garamond",serif;font-size:28px;font-weight:700;color:#07090f;letter-spacing:-.5px;margin-bottom:3px}'+
    '.rv-tag{font-size:12px;color:#4a5a6e;margin-bottom:8px}'+
    '.rv-con{display:flex;flex-wrap:wrap;gap:3px 15px;font-size:11px;color:#4a5a6e;padding-bottom:13px;border-bottom:2.5px solid #07090f;margin-bottom:18px}'+
    '.rv-con a{color:#4a5a6e;text-decoration:none}'+
    '.rv-con i,.rv-con svg,.rv-con .bi,.rv-con [class*="fa-"]{font-size:13px;width:13px;height:13px;min-width:13px;vertical-align:-1px}'+
    '.rv-sec{margin-bottom:17px}'+
    '.rv-sh{font-size:9px;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:#07090f;padding-bottom:4px;border-bottom:1px solid #ddd;margin-bottom:8px}'+
    '.rv-it{margin-bottom:11px}'+
    '.rv-ith{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-bottom:2px}'+
    '.rv-itn{font-size:13px;font-weight:600;color:#1a1a2e}'+
    '.rv-itd{font-size:10.5px;color:#888;white-space:nowrap}'+
    '.rv-ito{font-size:11.5px;color:#5a6a80;font-style:italic;margin-bottom:4px}'+
    '.rv-bul{list-style:none;padding:0;margin:0}'+
    '.rv-bul li{font-size:12px;color:#2a2a3a;padding:1.5px 0 1.5px 14px;position:relative;line-height:1.57}'+
    '.rv-bul li::before{content:"▸";position:absolute;left:0;color:#07090f;font-size:9px;top:4px}'+
    '.rv-sum{font-size:12.5px;color:#2a2a3a;line-height:1.7;background:#f4f6fc;border-left:3px solid #07090f;padding:10px 13px;border-radius:0 5px 5px 0}'+
    '.rv-skw{display:flex;flex-wrap:wrap;gap:5px}'+
    '.rv-sk{padding:3px 9px;background:#eef0f8;border-radius:4px;font-size:11px;color:#243060;font-weight:500}'+
    '@media print{@page{margin:18mm 16mm;size:A4}body{padding:0}}'+
    '</style></head><body>'+html+'</body></html>'
  );
  win.document.close();
  setTimeout(function(){ win.print(); }, 480);
}

function doSave(){
  if(!S.fd || !S.rhtml){ toast('Nothing to save yet'); return; }
  var rec = {
    id:      Date.now(),
    name:    S.fd.name||'Unnamed',
    course:  S.fd.course||'',
    unis:    S.fd.unis||'',
    style:   S.fd.style||'ivy_league',
    scores:  S.scores,
    html:    S.rhtml,
    fd:      S.fd,
    at:      new Date().toISOString()
  };
  S.saved.unshift(rec);
  if(S.saved.length>25) S.saved.length=25;
  try{ localStorage.setItem('acv3', JSON.stringify(S.saved)); }catch(e){}
  updBadge();
  toast('✓ Resume saved to My Resumes');
}

function updBadge(){
  var el = document.getElementById('sv-cnt');
  if(el) el.textContent = S.saved.length;
}

/* ═══════════════════════════════════════════════════════
   DASHBOARD
═══════════════════════════════════════════════════════ */
function renderDash(){
  var rs = S.saved;

  /* KPIs */
  setText('kpi-n', rs.length);
  if(rs.length){
    var scArr = rs.map(function(r){ return r.scores&&r.scores.overall?r.scores.overall:0; }).filter(Boolean);
    setText('kpi-a', scArr.length ? Math.round(scArr.reduce(function(a,b){return a+b;},0)/scArr.length) : '—');
    setText('kpi-t', scArr.length ? Math.max.apply(null,scArr) : '—');
    var uSet = {};
    rs.forEach(function(r){ if(r.unis) r.unis.split(',').forEach(function(u){ uSet[u.trim()]=1; }); });
    setText('kpi-u', Object.keys(uSet).length);
  } else {
    setText('kpi-a','—'); setText('kpi-t','—'); setText('kpi-u','0');
  }

  var container = document.getElementById('rlist');
  if(!container) return;

  if(!rs.length){
    container.innerHTML =
      '<div class="dash-empty">'+
        '<div class="de-ico">📋</div>'+
        '<h3 class="de-t">No Resumes Yet</h3>'+
        '<p class="de-p">Generate your first resume in the Builder. It will appear here once saved.</p>'+
        '<button class="btn-gold" onclick="goPage(\'build\')">Start Building →</button>'+
      '</div>';
    return;
  }

  container.innerHTML = rs.map(function(r){
    var ico   = STYLE_ICO[r.style]||'📄';
    var lbl   = STYLE_LBL[r.style]||r.style;
    var score = r.scores&&r.scores.overall ? r.scores.overall : null;
    var topU  = r.unis ? r.unis.split(',').slice(0,2).map(function(u){return u.trim();}).filter(Boolean) : [];
    var dt    = new Date(r.at).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'});
    return '<div class="rcard" onclick="loadSaved('+r.id+')">'+
      '<div class="rcard-ico">'+ico+'</div>'+
      '<div class="rcard-body">'+
        '<div class="rcard-nm">'+esc(r.name)+(r.course?' — '+esc(r.course):'')+' </div>'+
        '<div class="rcard-m">'+lbl+' · '+dt+'</div>'+
        '<div class="rcard-tags">'+
          '<span class="rtag rtag-a">'+lbl+'</span>'+
          (score?'<span class="rtag rtag-s">Score: '+score+'/100</span>':'')+
          topU.map(function(u){return '<span class="rtag rtag-a">'+esc(u)+'</span>';}).join('')+
        '</div>'+
      '</div>'+
      '<div class="rcard-acts">'+
        '<button class="btn-del" onclick="event.stopPropagation();delSaved('+r.id+')">🗑 Delete</button>'+
        '<button class="btn-gold btn-sm" onclick="event.stopPropagation();loadSaved('+r.id+')">View →</button>'+
      '</div>'+
    '</div>';
  }).join('');
}

function loadSaved(id){
  var rec = null;
  for(var i=0;i<S.saved.length;i++){
    if(S.saved[i].id===id){ rec=S.saved[i]; break; }
  }
  if(!rec){ toast('Resume not found'); return; }
  S.fd    = rec.fd;
  S.rhtml = rec.html;
  S.scores = rec.scores;
  var scoreStr = rec.scores ? '\nSCORES:'+JSON.stringify(rec.scores) : '';
  renderResult(rec.html+scoreStr, rec.fd);
  goPage('result');
}

function delSaved(id){
  if(!confirm('Delete this resume? This cannot be undone.')) return;
  S.saved = S.saved.filter(function(r){ return r.id!==id; });
  try{ localStorage.setItem('acv3',JSON.stringify(S.saved)); }catch(e){}
  updBadge();
  renderDash();
  toast('Resume deleted');
}

/* ═══════════════════════════════════════════════════════
   DEMO PROFILE
═══════════════════════════════════════════════════════ */
function loadDemo(){
  /* Step 1 */
  sv('f-name','Arjun Sharma');
  sv('f-email','arjun.sharma@example.com');
  sv('f-phone','+91 98765 43210');
  sv('f-country','India');
  sv('f-linkedin','https://linkedin.com/in/arjunsharma-econ');
  sv('f-portfolio','https://arjunsharma.notion.site');
  sv('f-level','Class 11–12 / A-Levels / IB / CBSE / ICSE');
  sv('f-school','Delhi Public School, R.K. Puram');
  sv('f-course','Economics / PPE (Philosophy, Politics & Economics)');
  sv('f-career','Development economist focused on poverty alleviation and financial inclusion across South Asia');

  /* select chips */
  S.unis = [];
  var allChips = document.querySelectorAll('#country-chips .chip');
  for(var ci=0;ci<allChips.length;ci++) allChips[ci].classList.remove('on');
  var targets = ['UK','USA','Canada','Singapore'];
  for(var ti=0;ti<allChips.length;ti++){
    if(targets.indexOf(allChips[ti].textContent.trim())>-1){
      allChips[ti].classList.add('on');
      S.unis.push(allChips[ti].textContent.trim());
    }
  }
  sv('f-other-country','Netherlands, Switzerland');

  /* Step 2 */
  sv('f-gpa','95.4% — CBSE Board (Predicted)');
  sv('f-board','CBSE (India)');
  sv('f-subjects','Mathematics (99/100), Economics (98/100), Statistics (97/100), English Core (96/100), History (95/100)');
  sv('f-ielts','8.5 (L:9.0, R:8.5, W:8.0, S:8.5)');
  sv('f-sat','1520 (R:760, M:760)');

  /* awards */
  var aw = document.querySelectorAll('#dl-awards input[type="text"]');
  var awVals = [
    'National Economics Olympiad — Silver Medal, top 50 nationally (2024)',
    'State Mathematics Topper — Rank 1 in Delhi NCR (2023)',
    'School Academic Excellence Award — 3 consecutive years'
  ];
  for(var ai=0;ai<awVals.length;ai++){
    if(!aw[ai]) addSimple('dl-awards','Award','');
    var awList = document.querySelectorAll('#dl-awards input[type="text"]');
    if(awList[ai]) awList[ai].value = awVals[ai];
  }
  var ol = document.querySelectorAll('#dl-olymp input[type="text"]');
  if(ol[0]) ol[0].value = 'International Mathematical Olympiad — Training Camp Participant; National Economics Olympiad Silver Medal; All India Finance Competition 1st Place';

  /* Step 3 - Leadership */
  var leadBlks = document.querySelectorAll('#dl-lead .dblk');
  if(leadBlks[0]){
    var li = leadBlks[0].querySelectorAll('input,textarea');
    if(li[0]) li[0].value='Student Council President';
    if(li[1]) li[1].value='Delhi Public School, R.K. Puram (3,200 students)';
    if(li[2]) li[2].value='2023–2024';
    if(li[3]) li[3].value='Led 12-member executive council representing 3,200+ students across 14 committees';
    if(li[4]) li[4].value='Launched school\'s first mental health awareness week reaching 800 students. Negotiated ₹4 lakh budget for student initiatives — 60% increase over prior year. Introduced monthly inter-house cultural programme with 95% student participation rate.';
  }

  /* activities */
  var exBlks = document.querySelectorAll('#dl-extra .dblk');
  if(exBlks[0]){
    var ei = exBlks[0].querySelectorAll('input');
    if(ei[0]) ei[0].value='British Parliamentary Debate';
    if(ei[1]) ei[1].value='National Runner-Up 2024';
    if(ei[2]) ei[2].value='5 years';
    if(ei[3]) ei[3].value='Won 11 of 14 national tournaments; represented school at Pan-India Inter-School Championship; trained 8 junior debaters';
  }

  /* sports */
  var sp = document.querySelectorAll('#dl-sport input[type="text"]');
  if(sp[0]) sp[0].value='School Cricket First XI — Vice-Captain; led team to Delhi Inter-School Semi-Finals 2023. District Table Tennis Champion (Under-17) 2022.';

  /* Step 4 - Internships */
  var intBlks = document.querySelectorAll('#dl-intern .dblk');
  if(intBlks[0]){
    var ii = intBlks[0].querySelectorAll('input,textarea');
    if(ii[0]) ii[0].value='Research Intern';
    if(ii[1]) ii[1].value='HDFC Securities, Mumbai';
    if(ii[2]) ii[2].value='Jun–Aug 2024';
    if(ii[3]) ii[3].value='Analysed equity research for 6 Nifty 50 companies. Built financial model tracking 3-year P&L projections for consumer goods sector. Presented findings to senior analysts; model adopted in Q3 sector brief distributed to 200+ institutional clients.';
  }

  /* research */
  var resBlks = document.querySelectorAll('#dl-research .dblk');
  if(resBlks[0]){
    var ri = resBlks[0].querySelectorAll('input,select,textarea');
    if(ri[0]) ri[0].value='Impact of Microfinance on Rural Women\'s Economic Empowerment in Rajasthan';
    if(ri[1]) ri[1].value='IIT Delhi (Prof. A. Sharma) | Indian Youth Economics Journal (peer-reviewed)';
    if(ri[2]) ri[2].value='2023–24';
    if(ri[3]) ri[3].value='Published — Youth / Online Journal';
    if(ri[4]) ri[4].value='Conducted primary survey of 200 beneficiaries across 4 districts using stratified random sampling. Found 34% increase in household income among SHG members vs control group. Paper accepted and published in peer-reviewed Indian Youth Economics Journal.';
  }

  /* community */
  var comBlks = document.querySelectorAll('#dl-community .dblk');
  if(comBlks[0]){
    var ci2 = comBlks[0].querySelectorAll('input,textarea');
    if(ci2[0]) ci2[0].value='Founder & Lead Educator';
    if(ci2[1]) ci2[1].value='FinLit India — Financial Literacy Programme';
    if(ci2[2]) ci2[2].value='2021–Present (3+ years)';
    if(ci2[3]) ci2[3].value='Founded initiative teaching personal finance to 130+ underprivileged students aged 12–18 across 3 government schools in South Delhi. Developed original 8-week curriculum; trained 5 peer educators to sustain programme independently. Validated by 40% improvement in financial literacy test scores.';
  }

  /* Step 5 */
  sv('f-tech','Python (pandas, matplotlib, scikit-learn), R (ggplot2, dplyr), SPSS, STATA, LaTeX, Excel/VBA, Financial Modelling, Bloomberg Terminal');
  sv('f-soft','Public Speaking, Cross-cultural Communication, Strategic Planning, Research Design, Community Organising, Curriculum Development');

  /* languages */
  var langBlks = document.querySelectorAll('#dl-lang .dblk');
  if(langBlks[0]){
    var la = langBlks[0].querySelectorAll('input,select');
    if(la[0]) la[0].value='English';
    if(la[1]) la[1].value='Bilingual Proficiency (C2)';
  }
  addLang();
  var langBlks2 = document.querySelectorAll('#dl-lang .dblk');
  if(langBlks2[1]){
    var lb = langBlks2[1].querySelectorAll('input,select');
    if(lb[0]) lb[0].value='Hindi';
    if(lb[1]) lb[1].value='Native / Mother Tongue';
  }
  addLang();
  var langBlks3 = document.querySelectorAll('#dl-lang .dblk');
  if(langBlks3[2]){
    var lc = langBlks3[2].querySelectorAll('input,select');
    if(lc[0]) lc[0].value='French';
    if(lc[1]) lc[1].value='Intermediate (B1)';
  }

  /* certs */
  var certIn = document.querySelectorAll('#dl-certs input[type="text"]');
  if(certIn[0]) certIn[0].value='Yale Financial Markets — Coursera (Prof. Robert Shiller) · 2024';
  addSimple('dl-certs','Certification','');
  var certIn2 = document.querySelectorAll('#dl-certs input[type="text"]');
  if(certIn2[1]) certIn2[1].value='Google Data Analytics Professional Certificate · 2023';
  addSimple('dl-certs','Certification','');
  var certIn3 = document.querySelectorAll('#dl-certs input[type="text"]');
  if(certIn3[2]) certIn3[2].value='CFA Institute Investment Foundations · 2024';

  sv('f-personal','• Published op-ed in The Hindu on UPI\'s role in financial inclusion, reaching 50,000+ readers\n• TEDx speaker on "Why Economic Inequality Is a Solvable Problem" (school TEDx event, 2023)\n• Created YouTube channel "EconSimple" — 2,400 subscribers, 45,000+ views');
  sv('f-hobbies','Classical Hindustani tabla (15 years, Grade 8 equivalent), competitive chess (2100 ELO, District Champion), long-distance running (half-marathon), development economics literature (Acemoglu, Sen, Banerjee)');

  toast('🎓 Demo profile loaded — review the steps, then continue to the resume editor.');
}

function sv(id,val){
  var el = document.getElementById(id);
  if(!el) return;
  if(el.tagName === 'SELECT'){
    var s = val == null ? '' : String(val).trim();
    if(!s){
      el.selectedIndex = 0;
      return;
    }
    el.value = s;
    if(el.value === s) return;
    for(var i = 0; i < el.options.length; i++){
      var opt = el.options[i];
      var ov = (opt.value || '').trim();
      var ot = (opt.text || '').trim();
      if(ov === s || ot === s) { el.selectedIndex = i; return; }
      if(ot && s && (ot.indexOf(s) === 0 || s.indexOf(ot) === 0)) { el.selectedIndex = i; return; }
    }
    return;
  }
  el.value = val;
}

/* ═══════════════════════════════════════════════════════
   TOAST
═══════════════════════════════════════════════════════ */
function toast(msg, dur){
  dur = dur||3200;
  var el = document.getElementById('toast');
  if(!el) return;
  el.textContent = msg;
  el.classList.add('on');
  clearTimeout(el._t);
  el._t = setTimeout(function(){ el.classList.remove('on'); }, dur);
}
