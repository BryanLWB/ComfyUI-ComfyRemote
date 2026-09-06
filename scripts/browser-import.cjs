const { chromium } = require('playwright');
const fs = require('node:fs/promises');
const assert = require('node:assert/strict');
const path = require('node:path');
const files = process.argv.slice(2);
assert(files.length, 'Pass one or more workflow JSON paths');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  try {
    await page.goto('http://127.0.0.1:8189', { waitUntil: 'networkidle', timeout: 60000 });
    await page.getByRole('button', { name: 'ComfyRemote', exact: true }).click();
    const status = await (await page.request.get('http://127.0.0.1:8189/comfyremote/status')).json();
    if (!status.paired) {
      const session = await (await page.request.get('http://127.0.0.1:8892/admin/api/session')).json();
      const pairing = await page.request.post('http://127.0.0.1:8892/admin/api/connector/pairing', {
        headers: { Origin: 'http://127.0.0.1:8892', 'X-CSRF-Token': session.csrf_token },
      });
      assert.equal(pairing.status(), 200);
      const body = await pairing.json();
      await page.getByLabel('服务地址', { exact: true }).fill('http://127.0.0.1:8891');
      await page.getByLabel('配对码', { exact: true }).fill(body.code);
      await page.getByRole('button', { name: '连接', exact: true }).click();
    }
    await page.locator('.cr-status').filter({ hasText: '已连接' }).waitFor({ timeout: 65000 });
    for (const source of files) {
      const file = path.basename(source);
      const data = JSON.parse(await fs.readFile(source, 'utf8'));
      const summary = await page.evaluate(async (workflow) => {
        const { app } = await import('/scripts/app.js');
        await app.loadGraphData(workflow);
        const result = await app.graphToPrompt();
        window.connectorTestPrompt = result.output;
        return { nodes: Object.keys(result.output || {}).length, missing: (app.graph._nodes || []).filter(n => n.type && !globalThis.LiteGraph.registered_node_types[n.type]).map(n => n.type) };
      }, data);
      await fs.writeFile(`artifacts/${file.startsWith('Krea2') ? 'krea' : 'h3'}-api.json`, JSON.stringify(await page.evaluate(() => window.connectorTestPrompt), null, 2));
      console.log(JSON.stringify({ file, summary }));
      await page.getByLabel('工作流名称', { exact: true }).fill(`Connector test ${file.replace('.json','')}`);
      const imported = page.waitForResponse(r => r.url().endsWith('/comfyremote/workflow'), { timeout: 120000 });
      await page.getByRole('button', { name: '发送当前工作流', exact: true }).click();
      const response = await imported;
      const value = await response.json();
      console.log(JSON.stringify({ file, status: response.status(), result: value }));
      assert.equal(response.status(), 200);
    }
    await page.screenshot({ path: 'artifacts/sidebar-desktop.png' });
    await page.setViewportSize({ width: 430, height: 932 });
    await page.screenshot({ path: 'artifacts/sidebar-mobile.png' });
    console.log(JSON.stringify({ errors }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
