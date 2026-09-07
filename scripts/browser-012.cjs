const {chromium} = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    await page.route('**/comfyremote/status',route=>route.fulfill({json:{paired:true,online:true,owner_email:'owner@example.net',service:'https://example.net'}}));
    await page.route('**/userdata?*',route=>route.fulfill({json:Array.from({length:15},(_,i)=>`目录${i}/这是用于检查长名称省略显示的工作流文件.json`)}));
    await page.goto('http://127.0.0.1:8189',{waitUntil:'networkidle'});
    await page.getByRole('button',{name:'ComfyRemote',exact:true}).click();
    await page.getByRole('button',{name:'解除配对',exact:true}).waitFor();
    let confirmed=false;
    page.once('dialog',async dialog=>{confirmed=true;await dialog.dismiss();});
    await page.getByRole('button',{name:'解除配对',exact:true}).click();
    assert(confirmed);
    assert.equal(await page.getByRole('button',{name:'解除配对',exact:true}).count(),1);
    assert.equal(await page.locator('.cr-workflow small').count(),0);
    assert.equal(await page.locator('.cr-workflow').count(),16);
    assert.equal(await page.locator('.cr-workflows').evaluate(n=>n.clientHeight<=360 && n.scrollHeight>n.clientHeight),true);
    await page.screenshot({path:'artifacts/012-sidebar.png'});
    await page.setViewportSize({width:430,height:932});
    assert.equal(await page.locator('.cr-connector').evaluate(n=>n.scrollWidth>n.clientWidth),false);
    await page.screenshot({path:'artifacts/012-sidebar-mobile.png'});
    const preview=await browser.newPage({viewport:{width:1100,height:780}});
    await preview.route('**/comfyremote/status',route=>route.fulfill({json:{paired:false,online:false}}));
    await preview.route('**/comfyremote/pair',route=>route.abort());
    await preview.goto('http://127.0.0.1:8189',{waitUntil:'networkidle'});
    await preview.getByRole('button',{name:'ComfyRemote',exact:true}).click();
    await preview.getByRole('button',{name:'连接',exact:true}).waitFor();
    await preview.locator('.cr-status').filter({hasText:'未连接'}).waitFor();
    await preview.screenshot({path:'artifacts/012-unpaired.png'});
    console.log(JSON.stringify({tenRows:true,singleFilename:true,narrowHeader:true,unpairedPreview:true}));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
