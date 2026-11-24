"""M407: a single frozen Link receiver feeds the existing asynchronous NPU modules."""
import argparse, collections, copy, json, queue, secrets, signal, socket, sys, threading, time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
import cv2
import numpy as np

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'m406r2'))
sys.path.insert(0,str(BASE))
from file_demo import Demo
from traffic import fresh
from overlay import tile
from PIL import Image
from receiver_bridge import Bridge
from source_contract import load as load_source_contract,permits_real_result

def rgb565(raw):
    if len(raw)!=1280*720*2: raise ValueError('Invalid complete logical-front RGB565 byte count; check FPGA handoff')
    p=np.frombuffer(raw,dtype='<u2').reshape(720,1280)
    return np.stack(((p&31)*255//31,((p>>5)&63)*255//63,(p>>11)*255//31),axis=-1).astype(np.uint8)

class App(Demo):
    def __init__(self,args):
        self.events=queue.Queue(maxsize=2048);self.log_stop=threading.Event();self.log_dropped=0
        super().__init__(args)
        self.mode=args.mode;self.source_contract=load_source_contract();self.link=None;self.receiver=None;self.session=None;self.started=time.monotonic()
        self.slot=None;self.received=collections.OrderedDict();self.exact=collections.OrderedDict();self.frame_metadata={}
        self.skipped_complete=0;self.last_complete=None;self.invalidated=True;self.model_epoch=None
        self.process_raw=None;self.seen_components=set();self.receive_error=None
        self.writer=threading.Thread(target=self.write_events,name='event-log',daemon=True);self.writer.start()
        if self.mode=='LIVE_FRONT':self.video='实时前摄／FPGA网口1输入';self.reopen=False
    def record(self,kind,**kw):
        item=dict(type=kind,host_monotonic=time.monotonic(),source=getattr(self,'mode','FILE_TEST'),**kw)
        try:self.events.put_nowait(item)
        except queue.Full:self.log_dropped+=1
    def write_events(self):
        while not self.log_stop.is_set() or not self.events.empty():
            try:item=self.events.get(timeout=.2)
            except queue.Empty:continue
            self.log.write(json.dumps(item,ensure_ascii=False)+'\n');self.log.flush()
    def publish(self,fid,raw,received,board_timestamp=None):
        # Parent consumes an already complete shared-memory publication; no UDP socket here.
        with self.ready:
            if self.slot is not None:self.skipped_complete+=1
            key=(self.session,fid);self.received[key]=received
            self.frame_metadata[key]=dict(board_timestamp_ms=board_timestamp,host_complete_received_monotonic=received,
                                         frame_id_semantics='BOARD_NET_RX_COMPLETE_PUBLICATION_SERIAL')
            self.slot=(self.epoch,self.session,fid,raw,received)
            self.last_complete=received;self.invalidated=False
            self.prune(received);self.ready.notify_all()
    def prune(self,now):
        for store,limit in [(self.received,128),(self.exact,96)]:
            while store:
                first=next(iter(store.values()));at=first[0] if store is self.exact else first
                if len(store)<=limit and now-at<=2:break
                store.popitem(last=False)
        self.frame_metadata={k:v for k,v in self.frame_metadata.items() if k in self.received}
    def clear_live(self,session,now,reason):
        # Increment independent perception generation; old workers cannot republish.
        with self.ready:
            self.epoch+=1;self.session=session;self.slot=None;self.received.clear();self.exact.clear();self.frame_metadata.clear()
            self.jpeg=self.raw_image=self.obs=self.frame=None;self.evidence_at=0;self.last_complete=None
            self.invalidated=True;self.stamps.clear();self.sequence+=1;self.seen_components.clear();self.ready.notify_all()
        self.record('live_generation_reset',session=session,epoch=self.epoch,reason=reason)
    def reset_live(self,epoch,session,now,reason):self.clear_live(session,now,reason)
    def lookup(self,fid,now):
        with self.lock:
            if not permits_real_result(self.source_contract):return None
            x=self.exact.get((self.session,fid))
            return copy.deepcopy(x[1]) if x and now-x[0]<2 else None
    def frame_state(self,fid,now):
        with self.lock:
            key=(self.session,fid);r=self.received.get(key);x=self.exact.get(key)
            return dict(received=r is not None,received_monotonic=r,inference_complete=x is not None,
                        inference_stale=bool(x and now-x[0]>=2),exact_components=list(x[1]['exact_components']) if x else [])
    def collect_exact(self):
        # Only completed native-source outputs enter event history. Display warps/holds never do.
        with self.detector.lock:dt=self.detector.latest
        with self.road.cv:rd=self.road.result
        with self.lights.lock:tl=self.lights.latest
        rows=[('objects',dt[0] if dt else None,'frame_id'),('road',rd,'source_frame_id'),('traffic',tl,'source_frame_id')]
        notifications=[]
        with self.lock:
            for name,r,field in rows:
                if not r or r.get('epoch')!=self.epoch:continue
                fid=r[field];tag=(self.epoch,name,fid)
                if tag in self.seen_components:continue
                self.seen_components.add(tag);key=(self.session,fid);received=self.received.get(key)
                if received is None or time.monotonic()-received>=2:continue
                if key not in self.exact:
                    self.exact[key]=(received,dict(source='LIVE_FRONT',session=self.session,frame_id=fid,epoch=self.epoch,
                        received_monotonic=received,frame_metadata=copy.deepcopy(self.frame_metadata.get(key,{})),source_verification=self.source_contract['status'],exact_components={},
                        signal=dict(state='UNKNOWN',actions=[],confidence=0,reason='灯组控制方向尚未建立，不能依据看见的绿灯放行'),
                        lanes={'left':dict(state='UNKNOWN',confidence=0),'right':dict(state='UNKNOWN',confidence=0)}))
                obs=self.exact[key][1]
                # Compact identity evidence is sufficient for the unchanged conservative rule.
                obs['exact_components'][name]=dict(source_frame_id=fid,epoch=r['epoch'],completed=True,
                    color_states=[b['color'] for b in r.get('lights',[])],state=r.get('state'),count=r.get('count'))
                if name=='road':obs['lanes']=copy.deepcopy(r.get('lane_semantics') or obs['lanes'])
                obs['signal']['exact_identity']=dict(source='LIVE_FRONT',physical_source='NET_RX' if permits_real_result(self.source_contract) else 'UNVERIFIED',session=self.session,frame_id=fid,epoch=self.epoch,completed_components=list(obs['exact_components']))
                notifications.append((fid,self.session))
            self.prune(time.monotonic())
            # Bounded identity set, old entries cannot affect a fresh generation.
            if len(self.seen_components)>512:self.seen_components={x for x in self.seen_components if (self.session,x[2]) in self.received}
        for fid,session in notifications:
            self.link.feedback.inference_completed(fid,time.monotonic(),session=session)
    def status(self):
        if self.mode=='FILE_TEST':return dict(super().status(),mode='FILE_TEST',source='香橙派录像',link=None)
        now=time.monotonic()
        with self.lock:
            stamps=[t for t in self.stamps if now-t<=5];age=(now-self.evidence_at)*1000 if self.evidence_at else None
            stale=not self.last_complete or now-self.last_complete>.7
            perception=copy.deepcopy(self.obs) if self.obs and not stale else None
            if perception:
                perception['traffic']=fresh(perception.get('traffic'),now,self.epoch)
                for k,threshold in [('detection',350),('road',500)]:
                    r=perception.get(k,{})
                    at=r.get('decoded_monotonic',r.get('age_reference_monotonic'))
                    if at:
                        r['age_ms']=round((now-at)*1000,1)
                        if r['age_ms']>threshold:r['expired']=True
            state=dict(release='M4-07-r1-netrx-ready',mode=self.mode,source=self.source_contract['display_name'],logical_source='LIVE_FRONT',source_contract=copy.deepcopy(self.source_contract),vehicle='KEY_INTENT_SIMULATION_ONLY',
                instance=self.instance,control_token=self.token,session=self.session,epoch=self.epoch,frame_id=self.frame,
                frame_metadata=copy.deepcopy(self.frame_metadata.get((self.session,self.frame),{})),
                sequence=self.sequence,processed=self.processed,processed_fps=round((len(stamps)-1)/max(.001,now-stamps[0]),3) if len(stamps)>1 else 0,
                host_monotonic_ms=now*1000,age_ms=round(age,1) if age is not None else None,stale=stale,
                last_complete_age_ms=round((now-self.last_complete)*1000,1) if self.last_complete else None,
                perception=perception,skipped_complete_frames=self.skipped_complete,
                exact_cache=len(self.exact),received_cache=len(self.received),stage_ms=self.stage,
                stage_mean_ms={k:round(float(np.mean([x[k] for x in self.stage_history if k in x])),3) for k in self.stage},
                requested_front_fps=self.args.front_fps,target_process_fps=15,target_preview_fps=15,preview_width=self.width,
                traffic=self.lights.metrics(),road=self.road.metrics(),detection=self.detector.metrics(),
                error=self.last_error or self.receive_error or self.lights.error or self.road.error or self.detector.error,
                show_lights=self.show_lights,show_road=self.show_road,show_lane=self.show_lane,show_objects=self.show_objects,
                note='图龄从主机完整接收起算，非端到端延迟；叠加只在香橙派网页，未回传FPGA检测框。')
        # Never take feedback.lock while holding the frame lock: receiver uses reverse order.
        state['link']=self.link.snapshot() if self.link else None
        state['receive_thread_alive']=bool(self.receiver and self.receiver.is_alive())
        return state
    def control(self,data):
        if self.mode=='FILE_TEST':return super().control(data)
        allowed={'show_lights','show_objects','show_road','show_lane','snapshot','feedback_mode','selection','reload_source_contract'}
        if set(data)-allowed:raise ValueError('LIVE不能选录像、跳转、模拟注入按键或改变驾驶规则')
        if data.get('reload_source_contract'):
            source=load_source_contract()
            # Local evidence file only; no browser-supplied physical source declaration.
            if source!=self.source_contract:
                self.link.commands.put_nowait(dict(op='source_reset'))
                with self.ready:
                    self.source_contract=source;self.clear_live(self.session,time.monotonic(),'SOURCE_CONTRACT_RELOADED')
                self.record('source_contract_reloaded',source_contract=source)
            return dict(ok=True,source_contract=source)
        if 'feedback_mode' in data:
            return dict(ok=True,controls=self.link.feedback.configure(data['feedback_mode'],data.get('selection','unknown'),time.monotonic()))
        for k in ['show_lights','show_objects','show_road','show_lane']:
            if k in data:setattr(self,k,bool(data[k]))
        if data.get('snapshot'):
            with self.lock:
                if not self.raw_image is not None or not self.jpeg or self.invalidated:raise ValueError('没有当前有效完整帧')
                base=f'LIVE_s{self.session}_e{self.epoch}_f{self.frame}_{self.sequence}'
                raw=self.raw_image.copy();body=self.jpeg;raw565=self.process_raw
            cv2.imwrite(str(self.out/(base+'_raw.png')),raw);(self.out/(base+'_overlay.jpg')).write_bytes(body)
            if raw565:(self.out/(base+'.rgb565')).write_bytes(raw565)
            s=self.status();s.pop('control_token',None);(self.out/(base+'.json')).write_text(json.dumps(s,ensure_ascii=False,indent=2))
            return dict(ok=True,directory=str(self.out),snapshot=base,status=s)
        return dict(ok=True)
    def render(self,raw,obs,drive,sec,video,width):
        if self.mode=='FILE_TEST':return super().render(raw,obs,drive,sec,video,width)
        # Existing overlay geometry unchanged; replace only source label.
        from overlay import draw
        t=time.perf_counter();annotated=draw(raw,dict(obs,show_road=self.show_road,show_lane=self.show_lane,show_lights=self.show_lights,show_objects=self.show_objects),drive,width,video,sec)
        label_text='实时前摄／FPGA网口1输入' + (' · 待实物核验' if permits_real_result(self.source_contract) else ' · 来源待核对')
        pil=Image.fromarray(cv2.cvtColor(annotated,cv2.COLOR_BGR2RGB));label=tile(label_text,round(15*width/640),(130,220,255))
        from PIL import ImageDraw
        ImageDraw.Draw(pil).rectangle((0,0,round(355*width/640),round(23*width/640)),fill=(18,24,31));pil.paste(label,(8,2),label)
        annotated=cv2.cvtColor(np.array(pil),cv2.COLOR_RGB2BGR);u=time.perf_counter()
        body=cv2.imencode('.jpg',annotated,[cv2.IMWRITE_JPEG_QUALITY,70])[1].tobytes()
        return body,dict(overlay=round((u-t)*1000,3),jpeg=round((time.perf_counter()-u)*1000,3))
    def run(self):
        if self.mode=='FILE_TEST':
            try:super().run()
            finally:self.log_stop.set();self.writer.join(timeout=3)
            return
        self.link=Bridge(self.args,self.lookup,self.record);self.receiver=self.link.process
        self.http();self.record('startup',receiver_process=self.receiver.pid,mode='LIVE_FRONT',source_contract=self.source_contract)
        try:
            while not self.stop.wait(.003):
                incoming=self.link.take()
                with self.link.lock:wire_session=self.link.meta[0]
                if wire_session and wire_session!=self.session:
                    self.clear_live(wire_session,time.monotonic(),'RECEIVER_SESSION_CHANGED')
                if not self.receiver.is_alive():raise RuntimeError('唯一UDP接收进程已退出')
                if incoming:
                    session,link_epoch,fid,raw,received,board_timestamp,skipped=incoming
                    if self.session!=session:self.clear_live(session,time.monotonic(),'FRAME_SESSION_CHANGED')
                    self.skipped_complete+=skipped;self.publish(fid,raw,received,board_timestamp)
                with self.ready:
                    epoch=self.epoch
                    item=self.slot;self.slot=None
                    stale=self.last_complete is not None and time.monotonic()-self.last_complete>.7 and not self.invalidated
                if stale:
                    self.clear_live(self.session,time.monotonic(),'FRONT_STREAM_STALE');continue
                if self.model_epoch!=epoch:
                    self.detector.reset(epoch);self.road.reset(epoch);self.lights.reset(epoch);self.model_epoch=epoch
                self.collect_exact()
                if not item:continue
                generation,session,fid,raw,received=item
                if generation!=epoch:continue
                t=time.perf_counter();image=rgb565(raw);decoded=time.monotonic()
                obs=dict(signal=dict(state='UNKNOWN',actions=[],confidence=0,reason='灯组控制关系未知'),lanes={},stage_ms={},source='LIVE_FRONT',source_verification=self.source_contract['status'],session=session,frame_id=fid,epoch=epoch,complete_received_monotonic=received)
                obs['detection']=self.detector.update(image,epoch,fid,received);obs['detection']['age_reference_monotonic']=time.monotonic()
                obs['traffic']=self.lights.update(image,epoch,fid,received,obs['detection'].get('objects',[]))
                obs['road']=self.road.update(image,epoch,fid,received,obs['detection'].get('objects',[]))
                obs['lanes']=obs['road'].get('lane_semantics',{});self.road.relate(obs['detection'],obs['road'],image.shape)
                fb=self.link.feedback.snapshot(time.monotonic());event=(fb['recent_events'] or [{}])[-1];action=event.get('action',4)
                drive=dict(motion='STOPPED',intent={1:'left',2:'right',3:'straight',4:'stop'}.get(action,'stop'),forced=False,alarm=None,
                    reason='KEY意图与精确帧判定见事件面板；灯组控制关系未知，不自动放行')
                body,stage=self.render(image,obs,drive,0,self.video,self.width)
                stage.update(**obs['detection'].get('stage_ms',{}),**obs['road'].get('stage_ms',{}),**obs['traffic'].get('stage_ms',{}))
                stage.update(rgb565_decode=round((decoded-t)*1000,3),process_total=round((time.perf_counter()-t)*1000,3),complete_to_preview_ms=round((time.monotonic()-received)*1000,3))
                with self.ready:
                    if generation!=self.epoch or session!=self.session:continue
                    self.jpeg=body;self.raw_image=image;self.process_raw=raw;self.obs=obs;self.frame=fid;self.evidence_at=received;self.sequence+=1
                    self.processed+=1;self.stage=stage;self.stage_history.append(stage);self.stamps.append(time.monotonic());self.ready.notify_all()
                if time.monotonic()-self.last_log>=1:
                    self.record('live_observation',session=session,frame_id=fid,epoch=epoch,stage_ms=stage,exact=self.frame_state(fid,time.monotonic()));self.last_log=time.monotonic()
        except Exception as e:self.last_error=repr(e);self.record('processing_exception',error=repr(e));raise
        finally:
            self.stop.set();self.link.stop.set();self.receiver.join(timeout=3)
            self.lights.close();self.road.close();self.detector.close();self.server.shutdown();self.server.server_close()
            self.log_stop.set();self.writer.join(timeout=3);self.log.close()
    def http(self):
        app=self
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def log_message(self,*args):pass
            def setup(self):super().setup();self.connection.settimeout(3);self.connection.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
            def reply(self,body,kind='application/json; charset=utf-8',code=200,headers=None):
                self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store, no-cache, must-revalidate');self.send_header('Pragma','no-cache');self.send_header('Expires','0');self.send_header('Content-Length',str(len(body)))
                for k,v in (headers or {}).items():self.send_header(k,str(v))
                self.end_headers()
                try:self.wfile.write(body)
                except OSError:pass
            def do_GET(self):
                path=urlsplit(self.path).path
                if path=='/':self.reply((BASE/'m407/index.html').read_bytes(),'text/html; charset=utf-8')
                elif path=='/status.json':self.reply(json.dumps(app.status(),ensure_ascii=False).encode())
                elif path in ['/frame.jpg','/latest.jpg','/raw.jpg']:
                    after=parse_qs(urlsplit(self.path).query).get('after',[''])[0]
                    with app.ready:
                        if path=='/frame.jpg':app.ready.wait_for(lambda:app.stop.is_set() or (app.jpeg and str(app.sequence)!=after),timeout=.7)
                        stale=app.mode=='LIVE_FRONT' and (app.last_complete is None or time.monotonic()-app.last_complete>.7)
                        body=None if stale else app.jpeg;raw=None if stale else app.raw_image
                        seq=app.sequence;ident=f'{app.session}:{app.epoch}:{app.frame}';received=app.evidence_at
                    if path=='/raw.jpg' and raw is not None:body=cv2.imencode('.jpg',raw,[cv2.IMWRITE_JPEG_QUALITY,90])[1].tobytes()
                    if not body or (path=='/frame.jpg' and str(seq)==after):self.reply(b'','text/plain',204)
                    else:self.reply(body,'image/jpeg',headers={'X-Frame-Sequence':seq,'X-Frame-ID':ident,'X-Frame-Received-Ms':received*1000})
                else:self.reply(b'not found','text/plain',404)
            def do_POST(self):
                try:
                    if urlsplit(self.path).path!='/demo/control':raise ValueError('Unknown endpoint')
                    if not secrets.compare_digest(self.headers.get('X-M4-Control-Token',''),app.token):raise ValueError('刷新页面取得有效控制令牌')
                    n=int(self.headers.get('Content-Length',0))
                    if not 0<n<=2048:raise ValueError('Invalid request length')
                    result=app.control(json.loads(self.rfile.read(n)));self.reply(json.dumps(result,ensure_ascii=False).encode())
                except (ValueError,TypeError,KeyError) as e:self.reply(json.dumps(dict(ok=False,error=str(e)),ensure_ascii=False).encode(),code=400)
        self.server=ThreadingHTTPServer(('127.0.0.1',self.args.port),Handler);self.server.daemon_threads=True
        threading.Thread(target=self.server.serve_forever,daemon=True).start()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['LIVE_FRONT','FILE_TEST'],default='LIVE_FRONT');p.add_argument('--port',type=int,default=8084)
    p.add_argument('--preview-width',type=int,choices=[640,1280],default=640);p.add_argument('--front-fps',type=int,default=15)
    p.add_argument('--bind',default='192.168.60.1');p.add_argument('--peer',default='192.168.60.2');p.add_argument('--udp-port',type=int,default=50000);p.add_argument('--peer-port',type=int,default=50000)
    a=p.parse_args()
    if not 0<=a.front_fps<=30:p.error('front-fps out of range')
    app=App(a);signal.signal(signal.SIGINT,lambda *_:app.stop.set());signal.signal(signal.SIGTERM,lambda *_:app.stop.set());app.run()
