// Run with Playwright installed: node tests/test_web_rows.cjs
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:900}});
    const failures=[];page.on('pageerror',e=>failures.push(e.message));
    await page.route('http://127.0.0.1:9876/**', async route => {
      const name=new URL(route.request().url()).pathname;
      if(name.startsWith('/api/'))return route.fulfill({status:503,contentType:'application/json',body:'{"error":"Test fixture"}'});
      const file=path.join(__dirname,'../seagreen/web',name==='/'?'index.html':name);
      return route.fulfill({path:file});
    });
    await page.goto('http://127.0.0.1:9876/');
    await page.evaluate(() => {
      window.fixture=(processes)=>{state={sample:{processes,inaccessible:0}};renderProcesses();};
      window.proc=(pid,cpu,created=10)=>({pid,cpu,created,name:'Application '+pid,memory:104857600,readRate:0,writeRate:0,protected:false});
      fixture([proc(1,90),proc(2,10)]);
      document.querySelectorAll('.page').forEach(n=>n.hidden=n.id!=='applications');
      window.originalRow=$('process-rows').children[0];
      window.originalButton=originalRow.children[5].children[0];originalButton.focus();window.buttonPosition=originalButton.getBoundingClientRect().x;
      fixture([proc(2,95),proc(1,5)]);
    });
    assert.deepEqual(await page.locator('#process-rows tr td:nth-child(2)').allTextContents(),['1','2']);
    assert.equal(await page.evaluate(()=>originalButton.getBoundingClientRect().x===buttonPosition),true);
    assert.equal(await page.evaluate(()=>originalRow===$('process-rows').children[0]&&originalButton===document.activeElement),true);
    assert.equal(await page.locator('#process-rows tr').first().locator('td').nth(4).textContent(),'5.0%');
    await page.evaluate(()=>fixture([proc(2,50),proc(1,20,11),proc(3,null)]));
    assert.deepEqual(await page.locator('#process-rows tr td:nth-child(2)').allTextContents(),['1','2','1','3']);
    assert.equal(await page.locator('#process-rows tr').first().locator('button').first().isDisabled(),true);
    assert.equal(await page.locator('#process-rows tr').nth(2).locator('button').first().isDisabled(),false);
    await page.locator('#search').fill('Application 2');
    assert.equal(await page.locator('#process-rows tr:visible').count(),1);
    await page.locator('#search').fill('');
    assert.equal(await page.evaluate(()=>originalRow===$('process-rows').children[0]),true);
    await page.locator('#refresh-processes').click();
    assert.deepEqual(await page.locator('#process-rows tr td:nth-child(2)').allTextContents(),['2','1','3']);
    // Actions use the current identity, including process creation time.
    await page.evaluate(()=>{window.clicked=null;controlProcess=(p)=>window.clicked=p;});
    await page.locator('#process-rows tr').nth(1).locator('button').first().click();
    assert.equal(await page.evaluate(()=>clicked.created),11);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    if(process.env.SEAGREEN_SCREENSHOT)await page.screenshot({path:process.env.SEAGREEN_SCREENSHOT,fullPage:true});
    assert.deepEqual(failures,[]);
    console.log('PASS: stable nodes/order/focus, live values, stopped rows, PID reuse, filtering, explicit refresh and control identity.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
