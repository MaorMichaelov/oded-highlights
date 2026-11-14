const {chromium}=require('/opt/node-tools/node_modules/playwright');
(async()=>{
 const t=Date.now();
 const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--no-sandbox']});
 const p=await b.newPage({viewport:{width:1280,height:720}});
 p.on('console',m=>console.log('console:',m.text().slice(0,200))); p.on('pageerror',e=>console.log('err',e.message));
 await p.goto('http://127.0.0.1:8765/index.html');
 await p.waitForFunction('window.__done===true',{timeout:150000});
 console.log('render ms',await p.evaluate('window.__ms'),'total s',(Date.now()-t)/1000);
 await p.locator('canvas').screenshot({path:process.argv[2]});
 await b.close();
})();
