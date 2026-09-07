const {chromium}=require('playwright');
const assert=require('node:assert/strict');

(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try {
    const page=await browser.newPage({viewport:{width:430,height:932}});
    const workflow={id:'test',version:1,name:'History acceptance',description:'',fields:[],output_types:['image']};
    const makeJob=(id,status='queued')=>({id,status,workflow:{id:'test',version:1,name:'History '+id},parameters:{},progress:null,error:null,created_at:new Date().toISOString(),assets:[]});
    let rows=[];
    let held=null;
    let hold=false;
    let created=makeJob('new');
    await page.route('**/api/**',async route=>{
      const req=route.request(),path=new URL(req.url()).pathname;
      if(path==='/api/session') return route.fulfill({json:{email:'test@example.net',csrf_token:'test'}});
      if(path==='/api/manage/session') return route.fulfill({status:403,json:{detail:'no management'}});
      if(path==='/api/status') return route.fulfill({json:{bridge:'online',comfyui:'online',queue:{remote_pending:0,comfy_running:0,comfy_pending:0}}});
      if(path==='/api/workflows') return route.fulfill({json:[workflow]});
      if(path==='/api/workflows/test') return route.fulfill({json:workflow});
      if(path==='/api/workflows/test/options') return route.fulfill({json:{fields:{}}});
      if(path==='/api/history/workflows') return route.fulfill({json:[{id:'test',name:workflow.name}]});
      if(path==='/api/jobs' && req.method()==='POST') return route.fulfill({json:created});
      if(path==='/api/jobs') {
        if(hold){held=route;hold=false;return;}
        return route.fulfill({json:rows});
      }
      if(path.startsWith('/api/jobs/')) {
        if(req.method()==='DELETE') return route.fulfill({status:204});
        return route.fulfill({json:created});
      }
      return route.fulfill({json:[]});
    });
    await page.goto('http://127.0.0.1:8891/#/workflow/test',{waitUntil:'networkidle'});
    await page.getByRole('button',{name:'开始生成',exact:true}).click();
    await page.waitForURL('**/#/job/new');
    await page.evaluate(()=>location.hash='/history');
    await page.locator('.job-row').filter({hasText:'History new'}).waitFor();
    assert.equal(rows.length,0);
    await page.waitForResponse(r=>new URL(r.url()).pathname==='/api/jobs');
    assert.equal(await page.locator('.job-row').filter({hasText:'History new'}).count(),1);
    rows=[created]; hold=true;
    await page.waitForRequest(r=>new URL(r.url()).pathname==='/api/jobs');
    await page.locator('.job-row').filter({hasText:'History new'}).click();
    await page.getByRole('button',{name:'删除任务',exact:true}).click();
    await page.getByRole('button',{name:'删除',exact:true}).click();
    await page.waitForURL('**/#/history');
    if(held) await held.fulfill({json:rows});
    await page.waitForResponse(r=>new URL(r.url()).pathname==='/api/jobs');
    assert.equal(await page.locator('.job-row').filter({hasText:'History new'}).count(),0);
    rows=[created,makeJob('cross-device','succeeded')];
    await page.locator('.job-row').filter({hasText:'History cross-device'}).waitFor({timeout:15000});
    assert.equal(await page.locator('.job-row').filter({hasText:'History new'}).count(),0);
    await page.screenshot({path:'artifacts/012-history.png'});
    console.log(JSON.stringify({createdImmediately:true,delayedCloudPreserved:true,deletedNeverReturns:true,crossDevicePolling:true}));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
