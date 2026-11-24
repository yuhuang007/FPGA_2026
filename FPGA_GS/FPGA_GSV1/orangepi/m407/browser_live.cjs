// Application browser acceptance/recording; unique source identities, never HTTP count.
const fs=require('fs'),path=require('path');const{chromium}=require('C:/Users/YuHuang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const out=path.join(__dirname,'evidence');fs.mkdirSync(out,{recursive:true});
(async()=>{const b=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});try{
 const p=await b.newPage({viewport:{width:1120,height:1080}}),jsErrors=[];p.on('pageerror',e=>jsErrors.push(String(e)));
 await p.goto('http://127.0.0.1:18084/');await p.waitForFunction(()=>window.m407Metrics?.().newFrames>3);
 const get=()=>p.evaluate(async()=>{const s=await(await fetch('/status.json')).json();delete s.control_token;return s});
 const ctrl=d=>p.evaluate(async d=>{let s=await(await fetch('/status.json')).json();return await(await fetch('/demo/control',{method:'POST',headers:{'Content-Type':'application/json','X-M4-Control-Token':s.control_token},body:JSON.stringify(d)})).json()},d);
 await p.evaluate(()=>{window.chunks=[];window.rec=new MediaRecorder(document.getElementById('video').captureStream(15),{mimeType:'video/webm;codecs=vp8',videoBitsPerSecond:1500000});window.rec.ondataavailable=e=>{if(e.data.size)window.chunks.push(e.data)};window.rec.start(500)});
 const a=await get(),ma=await p.evaluate(()=>window.m407Metrics());let samples=[];fs.writeFileSync(path.join(out,'browser_start.json'),JSON.stringify(a,null,2));
 const started=Date.now();
 while(Date.now()-started<60000){await p.waitForTimeout(1000);samples.push(await get());fs.writeFileSync(path.join(out,'live_samples.json'),JSON.stringify(samples));if(samples.length%10===0){await p.screenshot({path:path.join(out,'live_'+samples.length+'.png'),fullPage:true});console.log('live recording seconds',Math.round((Date.now()-started)/1000),'frames',samples.at(-1).processed)}}
 const z=await get(),mz=await p.evaluate(()=>window.m407Metrics()),dt=(z.host_monotonic_ms-a.host_monotonic_ms)/1000;
 const data=await p.evaluate(async()=>{await new Promise(r=>{window.rec.onstop=r;window.rec.stop()});let bytes=new Uint8Array(await new Blob(window.chunks).arrayBuffer()),s='';for(let i=0;i<bytes.length;i+=8192)s+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(s)});
 fs.writeFileSync(path.join(out,'real_live_operation.webm'),Buffer.from(data,'base64'));await p.screenshot({path:path.join(out,'live_page.png'),fullPage:true});
 let report={seconds:dt,mode:z.mode,sessionStart:a.session,sessionEnd:z.session,sameSession:a.session===z.session,completeFrames:z.link.complete_frames-a.link.complete_frames,
 completeFps:(z.link.complete_frames-a.link.complete_frames)/dt,processingFps:(z.processed-a.processed)/dt,previewNewFrameFps:(mz.newFrames-ma.newFrames)/dt,
 objectHz:(z.detection.detection_runs-a.detection.detection_runs)/dt,roadHz:(z.road.completed-a.road.completed)/dt,trafficHz:(z.traffic.completed-a.traffic.completed)/dt,
 assemblyDropped:z.link.assembly_dropped-a.link.assembly_dropped,activeSkipped:z.skipped_complete_frames-a.skipped_complete_frames,
 previewDuplicates:mz.duplicates-ma.duplicates,maxInflight:mz.maxInflight,jsErrors,stageMeanMs:z.stage_mean_ms,
 maxImageAgeMs:Math.max(...samples.map(s=>s.age_ms||0)),maxLightAgeMs:Math.max(...samples.map(s=>s.perception?.traffic?.age_ms||0)),
 maxRoadAgeMs:Math.max(...samples.map(s=>s.perception?.road?.age_ms||0)),start:a,end:z};
 fs.writeFileSync(path.join(out,'live_60s.json'),JSON.stringify(report,null,2));
 const snap=await ctrl({snapshot:true});fs.writeFileSync(path.join(out,'live_snapshot.json'),JSON.stringify(snap,null,2));
 console.log(JSON.stringify({...report,start:undefined,end:undefined}));
}finally{await b.close()}})().catch(e=>{console.error(e);process.exitCode=1});
