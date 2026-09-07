const {chromium} = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const admin = 'http://127.0.0.1:33743/admin/api';
    const rows = await (await page.request.get(admin+'/workflows')).json();
    const originals = rows.filter(w=>w.name.startsWith('Connector test '));
    const originalFields = {};
    for (const row of originals) {
      const w = await (await page.request.get(admin+'/workflows/'+row.id)).json();
      originalFields[row.id] = w.versions.map(v=>({version:v.version,fields:v.fields}));
    }
    await page.goto('http://127.0.0.1:8189',{waitUntil:'networkidle'});
    await page.getByRole('button',{name:'ComfyRemote',exact:true}).click();
    await page.locator('.cr-status').filter({hasText:'已连接'}).waitFor({timeout:65000});
    assert.match(await page.locator('.cr-account').innerText(), /@/);
    await page.evaluate(() => {
      const a=window.comfyAPI.app.app;
      const t=a.extensionManager.workflow.activeWorkflow.changeTracker;
      t.beforeChange();
      const node=globalThis.LiteGraph.createNode('EmptyImage');
      node.title='Unsaved acceptance marker';
      a.rootGraph.add(node);
      t.afterChange();
    });
    const snapshot = () => page.evaluate(() => {
      const a=window.comfyAPI.app.app,w=a.extensionManager.workflow,t=w.activeWorkflow.changeTracker;
      return JSON.stringify({graph:a.rootGraph.serialize(),active:w.activeWorkflow.path,
        tabs:w.openWorkflows.map(x=>x.path),modified:w.activeWorkflow._isModified,
        undo:t.undoQueue,redo:t.redoQueue,changeCount:t.changeCount});
    });
    const before = await snapshot();
    const state = JSON.parse(before);
    assert(state.undo.length > 0);
    assert(state.modified);
    const paths=await page.locator('.cr-workflow input').evaluateAll(nodes=>nodes.map(n=>n.value).filter(Boolean));
    for (const path of paths) {
      const expected=originals.find(w=>path.startsWith('Krea') ? w.name.includes('Krea') : w.name.includes('Minimax'));
      assert(expected);
      await page.locator('.cr-workflow input').evaluateAll((nodes,value)=>nodes.find(n=>n.value===value).click(),path);
      for (let attempt=0;attempt<2;attempt++) {
        const response=page.waitForResponse(r=>r.url().endsWith('/comfyremote/workflow'),{timeout:60000});
        await page.getByRole('button',{name:'发送所选工作流',exact:true}).click();
        const res=await response, value=await res.json();
        assert.equal(res.status(),200,JSON.stringify(value));
        assert.equal(value.duplicate,true);
        assert(value.review_path.includes(expected.id));
        assert.equal(await snapshot(),before);
        console.log(JSON.stringify({sample:path.startsWith('Krea')?'Krea':'H3',attempt:attempt+1,duplicate:true,unchangedCanvasTabsUndo:true}));
      }
    }
    assert.equal((await (await page.request.get(admin+'/workflows')).json()).length,rows.length);
    for (const row of originals) {
      const w=await (await page.request.get(admin+'/workflows/'+row.id)).json();
      assert.deepEqual(w.versions.map(v=>({version:v.version,fields:v.fields})),originalFields[row.id]);
    }
    await page.screenshot({path:'artifacts/011-staging-sidebar.png'});
    console.log(JSON.stringify({ownerEmail:true,existingFieldsPreserved:true,noExtraDrafts:true}));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
