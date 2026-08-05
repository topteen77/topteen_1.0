/**
 * Browser verification for voice nav green bar + commands (mocked mic).
 * Run: node scripts/test_tt_voice_nav_browser.mjs
 */
import path from 'path';
import { fileURLToPath } from 'url';
import { chromium } from 'playwright';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixture = path.join(__dirname, 'voice_nav_browser_fixture.html');

let failed = 0;
function assert(cond, msg) {
  if (!cond) {
    failed += 1;
    console.error('FAIL:', msg);
  } else {
    console.log('OK:', msg);
  }
}

// Prefer system Chrome (avoids downloading Playwright browsers; disk-friendly).
const browser = await chromium.launch({
  channel: 'chrome',
  headless: true,
  args: ['--disable-dev-shm-usage']
});
const page = await browser.newPage();

try {
  await page.goto('file://' + fixture, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(300);

  const barVisible = await page.locator('#ttVoiceNavBar.is-visible').count();
  assert(barVisible === 1, 'green voice bar visible when admin+mock speech ready');

  const chips = await page.locator('#ttVoiceNavBar .ttvn-chip').allTextContents();
  assert(chips.some((c) => /edit contact/i.test(c)), 'page suggestion chip present');

  // Open form via simulated voice command
  await page.evaluate(() => window.TTVoiceNav.handleUtterance('Edit contact'));
  await page.waitForSelector('#personalInfoModal.show', { timeout: 3000 });
  assert(true, 'Edit contact opens personal info modal');

  await page.waitForTimeout(400);
  const formChips = await page.locator('#ttVoiceNavBar .ttvn-chip').allTextContents();
  assert(formChips.some((c) => /^Next$/i.test(c)), 'form chips show Next after modal open');

  // Fill name via voice
  await page.evaluate(() => window.TTVoiceNav.handleUtterance('name Test Student'));
  await page.waitForTimeout(200);
  const nameVal = await page.inputValue('#piName');
  assert(nameVal === 'Test Student', 'voice fills full name');

  // Invalid mobile → status error, field not advancing wrongly
  await page.evaluate(() => window.TTVoiceNav.handleUtterance('mobile 123'));
  await page.waitForTimeout(200);
  const status = await page.locator('[data-ttvn-status]').textContent();
  assert(/10-digit|mobile/i.test(status || ''), 'validation message in green box status');

  await page.evaluate(() => window.TTVoiceNav.handleUtterance('mobile 9876543210'));
  await page.waitForTimeout(200);
  const mobileVal = await page.inputValue('#piMobile');
  assert(mobileVal === '9876543210', 'valid mobile accepted');

  await page.evaluate(() => window.TTVoiceNav.handleUtterance('gender female'));
  await page.waitForTimeout(200);
  const genderVal = await page.inputValue('#piGender');
  assert(genderVal === '30', 'gender female mapped to select');

  // Busy disables mic during command — spot check via Help
  await page.evaluate(() => window.TTVoiceNav.handleUtterance('Help'));
  await page.waitForTimeout(150);
  const helpOpen = await page.locator('[data-ttvn-help].is-open').count();
  assert(helpOpen === 1, 'help panel opens from voice command');

  // Admin off hides on re-attach
  await page.evaluate(() => {
    window.TT_VOICE_TO_TEXT_ENABLED = false;
    window.TTVoiceNav.detach();
    window.TTVoiceNav.attach({ pageCommands: [], forms: [] });
  });
  const hidden = await page.locator('#ttVoiceNavBar.is-visible').count();
  assert(hidden === 0, 'bar hidden when admin disables voice');

  // Static asset from Django also loads
  const resp = await page.request.get('http://127.0.0.1:8002/static/js_new/tt-voice-nav.js');
  assert(resp.ok(), 'Django serves tt-voice-nav.js');
} catch (e) {
  failed += 1;
  console.error('FAIL: browser run error', e);
} finally {
  await browser.close();
}

if (failed) {
  console.error('\n' + failed + ' browser check(s) failed — leaving files for inspection');
  process.exit(1);
}
console.log('\nAll browser voice-nav checks passed');
