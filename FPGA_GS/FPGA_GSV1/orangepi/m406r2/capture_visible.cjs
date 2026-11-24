const fs=require('fs'),path=require('path');const{chromium}=require('C:/Users/YuHuang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{const b=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});try{
 const p=await b.newPage({viewport:{width:1120,height:1000}});await p.goto('http://127.0.0.1:18082/');await p.waitForFunction(()=>window.m403Metrics&&window.m403Metrics().newFrames>1);
 const ctrl=x=>p.evaluate(async x=>{const s=await(await fetch('/status.json')).json();return await(await fetch('/demo/control',{method:'POST',headers:{'Content-Type':'application/json','X-M4-Control-Token':s.control_token},body:JSON.stringify(x)})).json()},x);
 const out=path.join(__dirname,'evidence','visible');fs.mkdirSync(out,{recursive:true});
 for(const[label,seek,color]of[['red',99,'RED'],['green',107,'GREEN']]){
  await ctrl({video:'SC_YJ.mp4',seek,playing:true});
  await p.waitForFunction(c=>status?.perception?.traffic?.lights?.filter(b=>b.color===c).length>=2,color,{timeout:15000});
  await p.screenshot({path:path.join(out,label+'_page.png'),fullPage:true});
  const record=await ctrl({snapshot:true});fs.writeFileSync(path.join(out,label+'_snapshot.json'),JSON.stringify(record,null,2));
 }
 await ctrl({video:'SC_YJ.mp4',seek:98,playing:true});
}finally{await b.close()}})().catch(e=>{console.error(e);process.exitCode=1});
