const fs=require('fs'),path=require('path');const{chromium}=require('C:/Users/YuHuang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{const b=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});try{
 const p=await b.newPage();await p.goto('http://127.0.0.1:18082/');await p.waitForFunction(()=>typeof status!=='undefined'&&status?.control_token);
 const ctrl=x=>p.evaluate(async x=>{const s=await(await fetch('/status.json')).json();return await(await fetch('/demo/control',{method:'POST',headers:{'Content-Type':'application/json','X-M4-Control-Token':s.control_token},body:JSON.stringify(x)})).json()},x);
 const a=await p.evaluate(()=>status);await ctrl({seek:a.duration-.4,loop:true,playing:true});
 await p.waitForFunction(n=>status.loop_count>n,a.loop_count,{timeout:15000});
 const z=await p.evaluate(()=>status);
 if((z.perception?.traffic?.lights||[]).some(x=>x.epoch!==z.epoch))throw Error('Old lights survived loop');
 fs.writeFileSync(path.join(__dirname,'evidence/browser/candidate/loop_check.json'),JSON.stringify({passed:true,beforeEpoch:a.epoch,afterEpoch:z.epoch,beforeLoops:a.loop_count,afterLoops:z.loop_count,position:z.position,no_old_epoch_lights:true},null,2));
 await ctrl({video:'SC_YJ.mp4',seek:98,playing:true});
}finally{await b.close()}})().catch(e=>{console.error(e);process.exitCode=1});
