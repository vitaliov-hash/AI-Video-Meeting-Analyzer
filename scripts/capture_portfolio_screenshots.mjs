import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdtempSync, readFileSync, rmSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { extname, join, resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const output = resolve(root, 'dist/portfolio-review/screenshots');
const frontend = resolve(root, 'frontend-dist');
const chrome = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
if (!existsSync(chrome)) throw new Error('Chrome is required for screenshots');
const mime = {'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8'};
const server = createServer((request,response) => {
  const pathname = new URL(request.url, 'http://localhost').pathname;
  const path = resolve(frontend, `.${pathname === '/' ? '/index.html' : pathname}`);
  if (!path.startsWith(frontend)) { response.writeHead(403).end(); return; }
  try { const body=readFileSync(path); response.writeHead(200, {'Content-Type':mime[extname(path)]||'application/octet-stream'}).end(body); }
  catch { response.writeHead(404).end(); }
});
await new Promise(done => server.listen(0,'127.0.0.1',done));
const profile = mkdtempSync(join(tmpdir(),'portfolio-chrome-'));
const child = spawn(chrome,['--headless=new','--no-first-run','--disable-extensions','--remote-debugging-port=0',`--user-data-dir=${profile}`,'about:blank'],{stdio:'ignore',windowsHide:true});
const pause = ms => new Promise(done => setTimeout(done,ms));
async function cdp(url) {
  const socket = new WebSocket(url);
  await new Promise((done,reject) => { socket.addEventListener('open',done,{once:true}); socket.addEventListener('error',reject,{once:true}); });
  let nextId=0;
  const pending=new Map();
  socket.addEventListener('message',event=>{ const msg=JSON.parse(event.data); const waiter=pending.get(msg.id); if(waiter){pending.delete(msg.id);msg.error?waiter.reject(new Error(msg.error.message)):waiter.resolve(msg.result);} });
  return {send(method,params={}) { const id=++nextId; return new Promise((resolve,reject)=>{pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));}); },close(){socket.close();}};
}
try {
  const portFile=join(profile,'DevToolsActivePort');
  for(let i=0;i<100&&!existsSync(portFile);i++) await pause(100);
  if(!existsSync(portFile)) throw new Error('Chrome DevTools did not start');
  const [port]=readFileSync(portFile,'utf8').split(/\r?\n/);
  const browserInfo=await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();
  const browser=await cdp(browserInfo.webSocketDebuggerUrl);
  const url=`http://127.0.0.1:${server.address().port}/`;
  await browser.send('Target.createTarget',{url});
  await pause(400);
  const targets=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const page=await cdp(targets.find(target=>target.url===url).webSocketDebuggerUrl);
  await page.send('Page.enable');
  await page.send('Runtime.enable');
  mkdirSync(output,{recursive:true});
  for (const [locale,meeting,width,height] of [
    ['en','sample-en-product-01',1440,1000],['ru','sample-ru-planning-01',1440,1000],
    ['es','sample-es-museum-01',1440,1000],['pt-BR','sample-ptbr-community-01',1440,1000],
    ['es','sample-es-museum-01',390,844],['pt-BR','sample-ptbr-community-01',390,844],
  ]) {
    await page.send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});
    await page.send('Runtime.evaluate',{expression:`localStorage.setItem('meeting-analyzer-ui-language',${JSON.stringify(locale)});localStorage.setItem('meeting-analyzer-showcase-selected',${JSON.stringify(meeting)});`});
    await page.send('Page.reload',{ignoreCache:true});
    await pause(550);
    const metrics=await page.send('Runtime.evaluate',{expression:'JSON.stringify({width:innerWidth,scroll:document.documentElement.scrollWidth,lang:document.documentElement.lang,meetings:document.querySelectorAll(".meeting").length})',returnByValue:true});
    const actual=JSON.parse(metrics.result.value);
    assert.equal(actual.lang,locale);
    assert.equal(actual.meetings,4);
    assert.ok(actual.scroll<=actual.width,`${locale} ${width}px horizontal overflow: ${actual.scroll}`);
    const shot=await page.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});
    const name=`showcase-${locale.toLowerCase()}-${width}.png`;
    writeFileSync(join(output,name),Buffer.from(shot.data,'base64'));
    console.log(`${name}: ${actual.width}px viewport, ${actual.scroll}px content`);
  }
  page.close();browser.close();
} finally {
  child.kill(); server.close();
  // Chrome profile is temporary and contains only synthetic Showcase data.
  const resolved=resolve(profile); const base=resolve(tmpdir());
  if(resolved.startsWith(base)&&resolved.includes('portfolio-chrome-')) {
    for(let attempt=0;attempt<10;attempt++) {
      try { rmSync(profile,{recursive:true,force:true}); break; }
      catch(error) { if(attempt===9) console.warn(`Temporary Chrome profile could not be removed: ${error.code}`); else await pause(300); }
    }
  }
}
