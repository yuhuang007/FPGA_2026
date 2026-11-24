"""One Link socket in an isolated process. Fixed latest-frame memory, bounded IPC.

Frozen Link/EventFeedback and protocol are imported unchanged. Inference never
shares their GIL. No image, inference or disk operation runs on their receive path.
"""
import collections,copy,multiprocessing as mp,queue,time,threading,secrets
from link import Link
from vendor.protocol import FRONT_RAW

SIZE=1280*720*2
def receive_process(args,raw,meta,lock,commands,updates,logs,stop):
    received=collections.OrderedDict();observations=collections.OrderedDict()
    intervals=collections.deque(maxlen=2048);last_complete=[None]
    def record(kind,**kw):
        try:logs.put_nowait(dict(kind=kind,data=kw))
        except queue.Full:pass
    def prune(now):
        for store in [received,observations]:
            while store:
                at=next(iter(store.values()));at=at[0] if store is observations else at
                if len(store)<=128 and now-at<2:break
                store.popitem(last=False)
    def lookup(fid,now):
        x=observations.get(fid)
        return x[1] if x and now-x[0]<2 else None
    def frame_state(fid,now):
        x=observations.get(fid);at=received.get(fid)
        return dict(received=at is not None,received_monotonic=at,inference_complete=x is not None,
                    inference_stale=bool(x and now-x[0]>=2))
    def publish(fid,image,now):
        if last_complete[0] is not None:intervals.append((now-last_complete[0])*1000)
        last_complete[0]=now;received[fid]=now;prune(now)
        with lock:
            memoryview(raw).cast('B')[:]=image
            meta[0]=link.session;meta[1]=link.epoch;meta[2]=fid;meta[3]=int(now*1e9);meta[4]+=1;meta[5]=link.current_video_timestamp
    def reset(epoch,session,now,reason):
        received.clear();observations.clear();intervals.clear();last_complete[0]=None
        with lock:meta[0]=session;meta[1]=epoch;meta[3]=0;meta[4]+=1;meta[5]=0
    class Receiver(Link):
        def receive(self,msg,now):
            # Synchronous frozen publish callback sees the last fragment's board timestamp.
            # This is a board clock value, never subtracted from a host clock.
            if msg.kind==FRONT_RAW:self.current_video_timestamp=msg.timestamp
            super().receive(msg,now)
        def tick(self,now):
            super().tick(now)
            if now<getattr(self,'ipc_due',0):return
            self.ipc_due=now+.005
            for _ in range(64):
                try:c=commands.get_nowait()
                except queue.Empty:break
                if c['op']=='observation':
                    obs=c['observation'];fid=obs['frame_id'];at=received.get(fid)
                    if obs['session']==self.session and at is not None and now-at<2:
                        observations[fid]=(at,obs);self.feedback.inference_completed(fid,now,session=self.session)
                elif c['op']=='configure':
                    try:controls=self.feedback.configure(c['mode'],c['selection'],now);reply=dict(id=c['id'],ok=True,controls=controls)
                    except ValueError as e:reply=dict(id=c['id'],ok=False,error=str(e))
                    try:updates.put_nowait(dict(reply=reply))
                    except queue.Full:record('ipc_config_reply_dropped',request_id=c['id'])
                elif c['op']=='source_reset':
                    observations.clear();self.feedback.cancel('SOURCE_PROVENANCE_CHANGED',now)
            if now>=getattr(self,'snapshot_due',0):
                self.snapshot_due=now+.25;prune(now);s=self.snapshot();s['receiver_process_pid']=__import__('os').getpid()
                v=sorted(intervals)
                s['complete_arrival_intervals_ms']=dict(count=len(v),median=v[len(v)//2] if v else None,p95=v[min(len(v)-1,int(len(v)*.95))] if v else None,max=max(v) if v else None)
                try:updates.put_nowait(dict(status=s))
                except queue.Full:pass
    link=Receiver((args['bind'],args['udp_port']),(args['peer'],args['peer_port']),publish,lookup,record,
                  front_fps=args['front_fps'],frame_state=frame_state,reset_live=reset)
    link.stop=stop
    with lock:meta[0]=link.session
    try:link.run()
    except Exception as e:record('receiver_exception',error=repr(e))

class FeedbackProxy:
    def __init__(self,bridge):self.bridge=bridge
    def snapshot(self,now):
        self.bridge.poll();return copy.deepcopy(self.bridge.cached.get('feedback',dict(recent_events=[],controls={'mode':'REAL'},counts={})))
    def inference_completed(self,fid,now,session=None):
        obs=self.bridge.lookup(fid,now)
        if obs and obs['session']==session:
            try:self.bridge.commands.put_nowait(dict(op='observation',observation=obs))
            except queue.Full:self.bridge.ipc_dropped+=1
    def configure(self,mode,selection,now):
        ident=secrets.token_hex(8)
        self.bridge.commands.put_nowait(dict(op='configure',mode=mode,selection=selection,id=ident))
        end=time.monotonic()+2
        while time.monotonic()<end:
            self.bridge.poll()
            with self.bridge.guard:r=self.bridge.replies.pop(ident,None)
            if r:
                if not r['ok']:raise ValueError(r['error'])
                return r['controls']
            time.sleep(.01)
        raise ValueError('接收进程未确认模式切换，不能假定已应用')

class Bridge:
    def __init__(self,args,lookup,log):
        ctx=mp.get_context('spawn');self.raw=ctx.RawArray('B',SIZE);self.meta=ctx.RawArray('Q',6);self.lock=ctx.Lock()
        self.commands=ctx.Queue(maxsize=128);self.updates=ctx.Queue(maxsize=8);self.logs=ctx.Queue(maxsize=256);self.stop=ctx.Event()
        self.guard=threading.RLock();self.cached={};self.replies={};self.lookup=lookup;self.log=log;self.last_serial=0;self.ipc_dropped=0
        self.process=ctx.Process(target=receive_process,args=(vars(args),self.raw,self.meta,self.lock,self.commands,self.updates,self.logs,self.stop),name='sole-gsv3-receiver')
        self.process.start();self.feedback=FeedbackProxy(self)
    def poll(self):
        with self.guard:
            while True:
                try:x=self.updates.get_nowait()
                except queue.Empty:break
                if 'status' in x:self.cached=x['status']
                if 'reply' in x:self.replies[x['reply']['id']]=x['reply']
            while True:
                try:x=self.logs.get_nowait()
                except queue.Empty:break
                self.log(x['kind'],**x['data'])
    def snapshot(self):
        self.poll()
        with self.guard:return dict(copy.deepcopy(self.cached),ipc_observation_dropped=self.ipc_dropped)
    def take(self):
        self.poll()
        with self.lock:
            session,epoch,fid,ns,serial,board_timestamp=list(self.meta)
            if serial==self.last_serial or not ns:return None
            skipped=max(0,serial-self.last_serial-1) if self.last_serial else 0
            self.last_serial=serial;raw=bytes(self.raw)
        return session,epoch,fid,raw,ns/1e9,board_timestamp,skipped
