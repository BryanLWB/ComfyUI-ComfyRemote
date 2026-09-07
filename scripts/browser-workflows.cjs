const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');

(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto('http://127.0.0.1:8189', {waitUntil:'networkidle'});
    await page.getByRole('button',{name:'ComfyRemote',exact:true}).click();
    await page.locator('.cr-status').filter({hasText:'已连接'}).waitFor({timeout:65000});
    const before = await page.evaluate(() => JSON.stringify(window.comfyAPI.app.app.rootGraph.serialize()));
    const navigationBefore = await page.evaluate(() => {
      const app = window.comfyAPI.app.app;
      return {name: app.extensionManager?.workflow?.activeWorkflow?.name,
        tabs: [...document.querySelectorAll('[role="tab"]')].map(n=>n.textContent),
        undo: JSON.stringify(app.extensionManager?.workflow?.activeWorkflow?.changeTracker?.undoQueue)};
    });
    const files = await page.locator('.cr-workflow input').evaluateAll(nodes => nodes.map(n=>n.value).filter(value => /^(Krea2-Turbo|Minimax_h3)/.test(value)));
    assert(files.length >= 2);
    for (const file of files) {
      await page.locator('.cr-workflow input').filter({visible:true}).evaluateAll((nodes,path)=>{nodes.find(n=>n.value===path).click();}, file);
      await page.route('**/comfyremote/workflow', async route => {
        const payload = route.request().postDataJSON();
        const kind = file.startsWith('Krea') ? 'krea' : 'h3';
        const expected = JSON.parse(await fs.readFile(`artifacts/${kind}-api.json`,'utf8'));
        assert.equal(Object.keys(payload.prompt).length, Object.keys(expected).length);
        for (const [id, node] of Object.entries(expected)) {
          assert.equal(payload.prompt[id].class_type, node.class_type);
          assert.deepEqual(payload.prompt[id].inputs, node.inputs, `Inputs for ${id}`);
        }
        console.log(JSON.stringify({file,nodes:Object.keys(payload.prompt).length}));
        await route.fulfill({json:{review_path:'/#/manage/workflow/test/1',candidate_count:1}});
      });
      const sent = page.waitForResponse(r=>r.url().endsWith('/comfyremote/workflow'));
      await page.getByRole('button',{name:'发送所选工作流',exact:true}).click();
      await sent;
      assert.equal(await page.evaluate(() => JSON.stringify(window.comfyAPI.app.app.rootGraph.serialize())), before);
      assert.deepEqual(await page.evaluate(() => {
        const app = window.comfyAPI.app.app;
        return {name:app.extensionManager?.workflow?.activeWorkflow?.name,
          tabs:[...document.querySelectorAll('[role="tab"]')].map(n=>n.textContent),
          undo:JSON.stringify(app.extensionManager?.workflow?.activeWorkflow?.changeTracker?.undoQueue)};
      }), navigationBefore);
      await page.unroute('**/comfyremote/workflow');
    }
    await page.screenshot({path:'artifacts/011-sidebar-desktop.png'});
    await page.setViewportSize({width:430,height:932});
    await page.screenshot({path:'artifacts/011-sidebar-mobile.png'});
    assert.equal(await page.locator('.cr-connector').evaluate(n=>n.scrollWidth>n.clientWidth),false);
    assert.deepEqual(errors,[]);
    const fixture = {last_node_id:1,last_link_id:0,nodes:[{id:1,type:'EmptyImage',pos:[0,0],size:[270,130],flags:{},order:0,mode:0,inputs:[],outputs:[{name:'IMAGE',type:'IMAGE',links:null,slot_index:0}],properties:{},widgets_values:[256,256,1,0]}],links:[],groups:[],config:{},extra:{},version:0.4};
    let fixturePaths = ['测试A/同名.json', '测试B/同名.json'];
    await page.route('**/userdata?*', route => route.fulfill({json:fixturePaths}));
    await page.route('**/userdata/*', route => route.fulfill({json:fixture}));
    await page.getByRole('button',{name:'刷新工作流列表',exact:true}).click();
    await page.getByRole('searchbox',{name:'搜索工作流',exact:true}).fill('测试B');
    await page.getByRole('radio',{name:'测试B/同名.json',exact:true}).check();
    fixture.nodes[0].widgets_values[0] = 384;
    let payload;
    await page.route('**/comfyremote/workflow', async route => {payload=route.request().postDataJSON();await route.fulfill({json:{review_path:'/#/manage/workflow/test/1',candidate_count:1}});});
    const sent = page.waitForResponse(r=>r.url().endsWith('/comfyremote/workflow'));
    await page.getByRole('button',{name:'发送所选工作流',exact:true}).click(); await sent;
    assert.equal(payload.prompt['1'].inputs.width,384);
    await page.unroute('**/comfyremote/workflow');
    let unexpectedSend = 0;
    await page.route('**/comfyremote/workflow', route => {unexpectedSend++;return route.abort();});
    await page.unroute('**/userdata/*');
    await page.route('**/userdata/*', route => route.fulfill({status:404}));
    await page.getByRole('button',{name:'发送所选工作流',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'工作流文件已不存在'}).waitFor();
    await page.unroute('**/userdata/*');
    await page.route('**/userdata/*', route => route.fulfill({json:{...fixture,nodes:[{type:'NotInstalledConnectorTest'}]}}));
    await page.getByRole('button',{name:'发送所选工作流',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'工作流缺少节点'}).waitFor();
    fixturePaths=[];
    await page.getByRole('button',{name:'刷新工作流列表',exact:true}).click();
    await page.getByText('所选文件已不存在，请重新选择。',{exact:true}).waitFor();
    await page.locator('.cr-primary:disabled').filter({hasText:'发送所选工作流'}).waitFor();
    assert.equal(await page.getByRole('button',{name:'发送所选工作流',exact:true}).isDisabled(),true);
    assert.equal(unexpectedSend,0);
    assert.equal(await page.evaluate(() => JSON.stringify(window.comfyAPI.app.app.rootGraph.serialize())), before);
    console.log(JSON.stringify({savedPaths:true,latestFile:true,missingFile:true,missingNode:true,noFallback:true}));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
