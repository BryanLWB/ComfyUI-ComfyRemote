const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  try {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('http://127.0.0.1:8189', { waitUntil: 'networkidle', timeout: 60000 });
  console.log(JSON.stringify({ body: (await page.locator('body').innerText()).slice(0,3500), controls: await page.locator('[title],[aria-label]').evaluateAll(nodes => nodes.map(n => ({ tag:n.tagName, title:n.title, aria:n.getAttribute('aria-label') }))), errors }));
  await page.screenshot({ path: 'artifacts/sidebar-before.png' });
  await page.getByRole('button', { name: 'ComfyRemote', exact: true }).click({ timeout: 8000 });
  await page.screenshot({ path: 'artifacts/sidebar-desktop.png' });
  console.log(JSON.stringify({ text: await page.locator('.cr-connector').innerText(), errors }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
