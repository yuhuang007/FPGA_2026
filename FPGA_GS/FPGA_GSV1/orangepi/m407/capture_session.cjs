// Actual webpage session, bounded record. Repeated canvas paints are not new frames.
const fs=require('fs'),path=require('path');
const{chromium}=require('C:/Users/YuHuang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const phase=process.argv[2]||'provenance',seconds=Number(process.argv[3]||120);
if(!/^[a-z0-9_-]+$/.test(phase)||seconds<1||seconds>600)throw Error('Invalid recording request');
const out=path.join(__dirname,'evidence','netrx361',phase);fs.mkdirSync(out,{recursive:true});
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});try{
 const page=await browser.newPage({viewport:{width:1120,height:1120}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.goto('http://127.0.0.1:18084/');await page.waitForFunction(()=>window.m407Metrics&&typeof status!=='undefined'&&status?.mode==='LIVE_FRONT');
 const get=()=>page.evaluate(async()=>{const s=await(await fetch('/status.json')).json();delete s.control_token;return s});
 await page.evaluate(()=>{window.chunks=[];window.recorder=new MediaRecorder(document.getElementById('video').captureStream(15),{mimeType:'video/webm;codecs=vp8',videoBitsPerSecond:1500000});window.recorder.ondataavailable=e=>{if(e.data.size)window.chunks.push(e.data)};window.recorder.start(500)});
 const started=Date.now(),initial=await get(),metrics0=await page.evaluate(()=>window.m407Metrics());let samples=[],lastState='',snapshots=0;
 while(Date.now()-started<seconds*1000){
  const s=await get(),m=await page.evaluate(()=>window.m407Metrics());samples.push({status:s,browser:m,elapsed_seconds:(Date.now()-started)/1000});
  fs.writeFileSync(path.join(out,'samples.json'),JSON.stringify(samples));
  const state=[s.session,s.epoch,s.stale,!!s.frame_id,(s.link.feedback?.recent_events||[]).length].join(':');
  if(state!==lastState&&snapshots<12){await page.screenshot({path:path.join(out,'transition_'+snapshots+'.png'),fullPage:true});snapshots++;lastState=state;console.log(phase,'transition',state)}
  await page.waitForTimeout(1000);
 }
 const end=await get(),metrics1=await page.evaluate(()=>window.m407Metrics());
 const recording=await page.evaluate(async()=>{await new Promise(r=>{window.recorder.onstop=r;window.recorder.stop()});const bytes=new Uint8Array(await new Blob(window.chunks).arrayBuffer());let s='';for(let i=0;i<bytes.length;i+=8192)s+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(s)});
 fs.writeFileSync(path.join(out,'operation.webm'),Buffer.from(recording,'base64'));await page.screenshot({path:path.join(out,'final_page.png'),fullPage:true});
 const duration=(end.host_monotonic_ms-initial.host_monotonic_ms)/1000,delta=(key,obj='link')=>(end[obj]?.[key]||0)-(initial[obj]?.[key]||0);
 const report={phase,seconds:duration,initial,end,browserStart:metrics0,browserEnd:metrics1,errors,
  sameSession:initial.session===end.session,completeFrames:delta('complete_frames'),completeFps:delta('complete_frames')/duration,
  processedFps:(end.processed-initial.processed)/duration,previewNewFrameFps:(metrics1.newFrames-metrics0.newFrames)/duration,
  objectHz:delta('detection_runs','detection')/duration,roadHz:delta('completed','road')/duration,trafficHz:delta('completed','traffic')/duration,
  assemblyDropped:delta('assembly_dropped'),activeSkipped:end.skipped_complete_frames-initial.skipped_complete_frames,
  maxSampledImageAgeMs:Math.max(...samples.map(x=>x.status.age_ms||0)),staleSamples:samples.filter(x=>x.status.stale).length,
  note:'Actual LIVE_FRONT webpage via SSH; new frame fps counts identity changes. Recording includes waiting/stale canvas; not a claim that all recorded frames are new input.'};
 fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({...report,initial:undefined,end:undefined,browserStart:undefined,browserEnd:undefined}));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
