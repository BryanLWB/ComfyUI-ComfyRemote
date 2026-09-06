const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const origin = process.env.COMFYREMOTE_ADMIN || 'http://127.0.0.1:8892';

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    const list = await (await page.request.get(origin + '/admin/api/workflows')).json();
    const workflow = list.find(w => w.name.includes('Krea2'));
    assert(workflow);
    await page.goto(`${origin}/#/workflow/${workflow.id}`, {waitUntil:'networkidle'});
    await page.getByRole('heading', {name:'候选字段',exact:true}).waitFor();
    const search = page.getByRole('searchbox', {name:'搜索候选字段'});
    await search.fill('100');
    const rows = page.locator('.connector-candidate-list label');
    const count = await rows.count();
    assert(count > 0);
    await rows.first().getByRole('checkbox').check();
    await page.getByRole('button',{name:'添加选中字段（1）'}).click();
    const saved = page.waitForResponse(response => response.request().method() === 'PUT' && response.url().includes(`/workflows/${workflow.id}/versions/`));
    await page.getByRole('button', {name:'保存修改',exact:true}).click();
    assert.equal((await saved).status(), 200);
    await page.reload({waitUntil:'networkidle'});
    await page.screenshot({path:'artifacts/review-desktop.png',fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:'artifacts/review-mobile.png',fullPage:true});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),false);
    console.log(JSON.stringify({candidateRows:count,errors}));
    assert.equal(errors.length,0);
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
