const {chromium,expect}=require('playwright/test');
const assert=require('node:assert/strict');

(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try {
    const page=await browser.newPage({viewport:{width:430,height:932}});
    const makeJob=(id)=>({id,status:'succeeded',workflow:{id:'test',version:1,name:id},parameters:{},progress:null,error:null,created_at:new Date().toISOString(),assets:[]});
    let rows=Array.from({length:125},(_,i)=>makeJob('page-'+i));
    let held,hold=false;
    const requests=[];
    await page.route('**/api/**',async route=>{
      const req=route.request(),url=new URL(req.url()),path=url.pathname;
      if(path==='/api/session') return route.fulfill({json:{email:'test@example.net',csrf_token:'test'}});
      if(path==='/api/manage/session') return route.fulfill({status:403,json:{detail:'no management'}});
      if(path==='/api/status') return route.fulfill({json:{bridge:'online',comfyui:'online',queue:{}}});
      if(path==='/api/jobs') {
        requests.push(url);
        if(hold){held=route;hold=false;return;}
        const selected=url.searchParams.get('media_type')==='video'?[makeJob('video-result')]:rows;
        const offset=Number(url.searchParams.get('offset')),limit=Number(url.searchParams.get('limit'));
        return route.fulfill({json:selected.slice(offset,offset+Math.min(100,limit))});
      }
      if(path.startsWith('/api/jobs/') && req.method()==='DELETE') return route.fulfill(path.endsWith('/keep-failed')?{status:503,json:{detail:'Simulated deletion failure'}}:{status:204});
      return route.fulfill({json:[]});
    });
    await page.goto('http://127.0.0.1:8891/#/history',{waitUntil:'networkidle'});
    while(await page.locator('.job-row').count()<125) {
      const previous=await page.locator('.job-row').count();
      await page.locator('.history-load-more-btn').scrollIntoViewIfNeeded();
      await expect.poll(()=>page.locator('.job-row').count()).toBeGreaterThan(previous);
    }
    requests.length=0;
    await page.getByRole('button',{name:'刷新历史',exact:true}).click();
    await expect.poll(()=>requests.length).toBeGreaterThanOrEqual(2);
    await expect(page.locator('.job-row')).toHaveCount(125);
    assert(requests.every(url=>Number(url.searchParams.get('limit'))<=100));
    hold=true;
    await page.getByRole('button',{name:'刷新历史',exact:true}).click();
    await expect.poll(()=>Boolean(held)).toBe(true);
    await page.locator('.history-filter-group').getByRole('button',{name:'视频',exact:true}).click();
    await expect(page.locator('.job-row')).toHaveCount(1);
    await held.fulfill({json:[makeJob('stale-old-filter')]});
    await expect(page.locator('.job-row')).toHaveText(/video-result/);
    rows=[makeJob('delete-success'),makeJob('keep-failed')];
    await page.locator('.history-filter-group').first().getByRole('button',{name:'全部',exact:true}).click();
    await expect(page.locator('.job-row')).toHaveCount(2);
    await page.getByRole('button',{name:'选择',exact:true}).click();
    await page.getByRole('button',{name:'全选',exact:true}).click();
    await page.locator('.floating-history-dock').getByRole('button',{name:'删除',exact:true}).click();
    await page.getByRole('button',{name:'删除 2 项',exact:true}).click();
    await expect(page.locator('.job-row')).toHaveCount(1);
    await expect(page.locator('.job-row')).toHaveText(/keep-failed/);
    await page.getByRole('button',{name:'取消',exact:true}).last().click();
    await page.getByRole('button',{name:'刷新历史',exact:true}).click();
    await expect(page.locator('.job-row')).toHaveCount(1);
    console.log(JSON.stringify({pagination125:true,refreshRetainsAllPages:true,staleFilterDiscarded:true,batchPartialFailure:true}));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
