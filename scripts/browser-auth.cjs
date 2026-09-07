const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const origin = 'http://127.0.0.1:8891';
const admin = 'http://127.0.0.1:33743';

(async () => {
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try {
    const page=await browser.newPage();
    await page.addInitScript(() => sessionStorage.setItem('comfyremote-management','1'));
    const rows=await (await page.request.get(admin+'/admin/api/workflows')).json();
    const source=rows.find(w=>w.name.startsWith('Connector test Krea'));
    const workflow=await (await page.request.get(admin+'/admin/api/workflows/'+source.id)).json();
    const health=await (await page.request.get(admin+'/admin/api/health')).json();
    const version=workflow.versions.find(v=>v.version===1);
    version.fields=[]; version.status='draft'; version.test_status=null;
    const session={email:'owner@example.net',role:'owner',management_available:true,csrf_token:'test',capabilities:['manage','owner_actions']};
    let failed=false;
    await page.route('**/api/**', async route=>{
      const path=new URL(route.request().url()).pathname;
      if(path==='/api/session' || path==='/api/manage/session') return route.fulfill({json:session});
      if(path==='/api/manage/health') return route.fulfill({json:health});
      if(path==='/api/manage/workflows/'+source.id) return route.fulfill({json:workflow});
      if(failed && path.startsWith('/api/manage/')) return route.abort();
      return route.fulfill({json:[]});
    });
    await page.goto(origin+'/#/manage/workflow/'+source.id+'/1',{waitUntil:'networkidle'});
    await page.locator('.connector-candidate-list input').first().check();
    await page.getByRole('button',{name:'添加选中字段（1）',exact:true}).click();
    const label=page.locator('.binding-card .form-field').filter({has:page.getByText('手机端标签',{exact:true})}).locator('input');
    await label.fill('Unsaved edit survives network failure');
    failed=true;
    await page.getByRole('button',{name:'保存修改',exact:true}).click();
    await page.getByText('请求未完成，请检查网络或重新登录。未保存修改仍保留在当前页面。',{exact:false}).waitFor();
    assert.equal(await label.inputValue(),'Unsaved edit survives network failure');
    await page.close();
    for(const kind of ['auth','network','bridge']) {
      const p=await browser.newPage();
      await p.route('**/api/session',route=>kind==='network' ? route.abort() : route.fulfill({status:kind==='auth'?401:503,json:{detail:{code:kind==='auth'?'AUTH_REQUIRED':'BRIDGE_OFFLINE',message:kind==='auth'?'Login required':'Bridge is offline'}}}));
      await p.goto(origin,{waitUntil:'networkidle'});
      await p.getByRole('heading',{name:kind==='auth'?'需要重新登录':'无法连接 ComfyRemote'}).waitFor();
      if(kind==='auth') await p.getByRole('button',{name:'重新登录',exact:true}).waitFor();
      if(kind==='bridge') assert.equal(await p.getByText('Bridge is offline',{exact:true}).isVisible(),true);
      if(kind==='network') assert.equal((await p.locator('body').innerText()).includes('本机服务'),false);
      await p.close();
    }
    console.log(JSON.stringify({auth:true,network:true,bridge:true,unsavedEditorPreserved:true}));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
