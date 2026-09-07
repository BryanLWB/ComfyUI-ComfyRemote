const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const origin = process.env.COMFYREMOTE_ADMIN || 'http://127.0.0.1:33743';

(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  try {
    for (const mobile of [false,true]) {
      const page = await browser.newPage({viewport: mobile ? {width:430,height:932} : {width:1440,height:1000}});
      const errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      const list=await (await page.request.get(origin+'/admin/api/workflows')).json();
      const source=list.find(w=>w.name.startsWith('Connector test Krea'));
      assert(source);
      const workflow=await (await page.request.get(origin+'/admin/api/workflows/'+source.id)).json();
      const version=workflow.versions.find(v=>v.version===1);
      version.fields=[];
      version.status='draft'; version.validation=null; version.test_status=null;
      version.package_manifest.connector_candidates=version.package_manifest.connector_candidates.slice(0,3);
      await page.route('**/admin/api/workflows/'+source.id,route=>route.fulfill({json:workflow}));
      await page.route('**/admin/api/workflows/'+source.id+'/versions/1',async route=>{
        assert.equal(route.request().method(),'PUT');
        Object.assign(version,route.request().postDataJSON());
        await route.fulfill({json:version});
      });
      await page.goto(origin+'/#/workflow/'+source.id+'/1',{waitUntil:'networkidle'});
      assert.equal(await page.getByText('还没有公开字段',{exact:true}).isVisible(),true);
      const search=page.getByRole('searchbox',{name:'搜索候选字段'});
      await search.fill('zzzz no matching fields');
      assert.equal(await page.getByText('没有匹配的候选字段',{exact:true}).isVisible(),true);
      await search.fill('');
      await page.locator('.connector-candidate-list input').first().check();
      await page.getByRole('button',{name:'添加选中字段（1）',exact:true}).click();
      await page.locator('.binding-card .binding-grid').waitFor();
      assert.equal(await page.getByText('还没有公开字段',{exact:true}).count(),0);
      const label = page.locator('.binding-card .form-field').filter({has:page.getByText('手机端标签',{exact:true})}).locator('input');
      await label.fill('Edited before save');
      for (const checkbox of await page.locator('.connector-candidate-list input').all()) await checkbox.check();
      await page.getByRole('button',{name:'添加选中字段（2）',exact:true}).click();
      assert.equal(await page.locator('.binding-card .binding-grid').count(),3);
      assert.equal(await label.first().inputValue(),'Edited before save');
      assert.equal(await page.getByText('候选字段已全部添加',{exact:true}).isVisible(),true);
      await page.getByRole('button',{name:'全部收起',exact:true}).click();
      await page.locator('.field-drag-handle').last().press('ArrowUp');
      await page.getByRole('button',{name:'全部展开',exact:true}).click();
      await page.getByRole('button',{name:'移除字段',exact:true}).last().click();
      await page.getByRole('button',{name:'移除',exact:true}).click();
      assert.equal(await page.locator('.binding-card').count(),2);
      const saved=page.waitForResponse(r=>r.request().method()==='PUT');
      await page.getByRole('button',{name:'保存修改',exact:true}).click(); await saved;
      await page.reload({waitUntil:'networkidle'});
      assert.equal(await page.locator('.binding-card .binding-grid').count(),2);
      assert.equal(await label.first().inputValue(),'Edited before save');
      await page.locator('.binding-card').first().evaluate(node=>node.scrollIntoView({block:'start'}));
      await page.screenshot({path:`artifacts/011-fields-${mobile?'mobile':'desktop'}.png`});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      assert.deepEqual(errors,[]);
      console.log(JSON.stringify({mobile,fields:version.fields.length,immediateDisplay:true,saved:true}));
      await page.close();
    }
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
