// Local application's browser acceptance test, using the existing project runtime.
const fs=require('fs'),path=require('path');
const {chromium}=require('C:/Users/YuHuang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const version=process.argv[2]||'candidate',port=version==='baseline'?18083:18082;
const out=path.join(__dirname,'evidence','browser',version);fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1120,height:1050}});await page.goto('http://127.0.0.1:'+port+'/');
  await page.waitForFunction(()=>window.m403Metrics&&window.m403Metrics().newFrames>3);
  const status=()=>page.evaluate(async()=>await(await fetch('/status.json')).json());
  const ctrl=x=>page.evaluate(async x=>{const s=await(await fetch('/status.json')).json();return await(await fetch('/demo/control',{method:'POST',headers:{'Content-Type':'application/json','X-M4-Control-Token':s.control_token},body:JSON.stringify(x)})).json()},x);
  let rows=[];
  for(const[video,seek,seconds]of [['SC_YJ.mp4',98,11],['SC_BT.mp4',48,8],['SC_BT2.mp4',17,8],['SC_YJ2.mp4',42,8]]){
   const before=await status();await ctrl({video,seek,playing:true,width:640,mode:'intersection'});
   await page.waitForFunction(({v,e})=>typeof status!=='undefined'&&status.video===v&&status.epoch>e&&status.perception?.traffic?.epoch===status.epoch&&window.m403Metrics().newFrameFps>4,{v:video,e:before.epoch});
   await page.evaluate(()=>{window.chunks=[];window.rec=new MediaRecorder(document.getElementById('video').captureStream(15),{mimeType:'video/webm;codecs=vp8',videoBitsPerSecond:1500000});window.rec.ondataavailable=e=>{if(e.data.size)window.chunks.push(e.data)};window.rec.start(250)});
   const a=await status(),ma=await page.evaluate(()=>window.m403Metrics());let samples=[];
   for(let i=0;i<seconds*2;i++){await page.waitForTimeout(500);samples.push(await status())}
   const z=await status(),mz=await page.evaluate(()=>window.m403Metrics()),dt=(z.host_monotonic_ms-a.host_monotonic_ms)/1000;
   if(samples.some(s=>s.video!==video||s.epoch!==a.epoch)||z.epoch!==a.epoch)throw Error('Epoch/video changed; measurement invalid');
   const data=await page.evaluate(async()=>{await new Promise(r=>{window.rec.onstop=r;window.rec.stop()});const bytes=new Uint8Array(await new Blob(window.chunks).arrayBuffer());let s='';for(let i=0;i<bytes.length;i+=8192)s+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(s)});
   const name=video.slice(0,-4);fs.writeFileSync(path.join(out,name+'.webm'),Buffer.from(data,'base64'));await page.screenshot({path:path.join(out,name+'_page.png'),fullPage:true});
   const snapshot=await ctrl({snapshot:true});fs.writeFileSync(path.join(out,name+'_snapshot.json'),JSON.stringify(snapshot,null,2));
   let row={video,seek,actualStartPosition:a.position,actualEndPosition:z.position,seconds:dt,release:z.release,PID_not_in_browser:true,
    processedFps:(z.processed-a.processed)/dt,previewNewFrameFps:(mz.newFrames-ma.newFrames)/dt,
    objectHz:(z.detection.detection_runs-a.detection.detection_runs)/dt,roadHz:(z.road.completed-a.road.completed)/dt,
    trafficHz:(z.traffic.completed-a.traffic.completed)/dt,trafficSkipped:z.traffic.skipped_source_observations-a.traffic.skipped_source_observations,
    maxInflight:mz.maxInflight,duplicates:mz.duplicates-ma.duplicates,stageMeanMs:z.stage_mean_ms,samples};
   rows.push(row);fs.writeFileSync(path.join(out,'performance.json'),JSON.stringify(rows,null,2));console.log(JSON.stringify({...row,samples:undefined}),true);
  }
  if(version==='candidate'){
   await ctrl({playing:false});const stopped=await status();await page.waitForTimeout(800);const paused=await status();
   if(paused.perception?.traffic?.lights?.length)throw Error('Traffic lights survived pause TTL');
   await ctrl({video:'SC_YJ2.mp4',seek:43,playing:true});await page.waitForFunction(e=>status.epoch>e,stopped.epoch);const changed=await status();
   if((changed.perception?.traffic?.lights||[]).some(b=>b.epoch!==changed.epoch))throw Error('old epoch light survived video switch');
   fs.writeFileSync(path.join(out,'expiry_switch_checks.json'),JSON.stringify({pauseCleared:true,videoEpochCleared:true,pausedEpoch:paused.epoch,newEpoch:changed.epoch},null,2));
   await ctrl({video:'SC_YJ.mp4',seek:98,playing:true});
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
