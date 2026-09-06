const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const origin = process.env.COMFYREMOTE_ADMIN || 'http://127.0.0.1:33743';

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    for (const mobile of [false, true]) {
      const context = await browser.newContext({
        viewport: mobile ? { width: 430, height: 932 } : { width: 1440, height: 1000 },
        isMobile: mobile, hasTouch: mobile,
      });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/admin/api/**', route => {
        if (!['GET', 'HEAD'].includes(route.request().method())) return route.abort();
        return route.continue();
      });
      await page.goto(origin, { waitUntil: 'networkidle' });
      const first = page.locator('.admin-workflow-wrapper').first();
      const id = await first.getAttribute('data-workflow-id');
      const button = first.locator('.admin-row-clickable-area');
      if (mobile) await button.tap(); else await button.click();
      await page.waitForURL(`**/#/workflow/${id}/*`, { timeout: 5000 });
      await page.getByRole('button', { name: '返回工作流', exact: true }).waitFor();
      await page.screenshot({ path: `artifacts/navigation-${mobile ? 'mobile' : 'desktop'}.png` });
      await page.goto(origin, { waitUntil: 'networkidle' });
      if (!mobile) {
        const box = await page.locator('.admin-row-clickable-area').first().boundingBox();
        await page.mouse.move(box.x + 170, box.y + box.height / 2);
        await page.mouse.down();
        await page.mouse.move(box.x + 100, box.y + box.height / 2, { steps: 10 });
        await page.mouse.up();
        assert.equal(new URL(page.url()).hash, '');
        await page.waitForTimeout(500);
        await page.locator('.admin-row-clickable-area').first().click();
        assert.equal(new URL(page.url()).hash, '');
        await page.locator('.admin-row-clickable-area').first().click();
        await page.waitForURL(`**/#/workflow/${id}/*`);
      }
      assert.deepEqual(errors, []);
      console.log(JSON.stringify({ mobile, navigation: 'passed', errors }));
      await context.close();
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
