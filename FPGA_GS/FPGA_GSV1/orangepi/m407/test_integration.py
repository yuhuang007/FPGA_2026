"""Integration identity tests only. No NPU model, sockets, or FPGA test events."""
import collections,threading,time,unittest
from types import SimpleNamespace as NS
import numpy as np
from app import App,rgb565
from receiver_bridge import Bridge,FeedbackProxy
import multiprocessing as mp,queue
from unittest.mock import patch
from source_contract import load as load_source_contract,EXPECTED_PROFILE
import tempfile,json

class Tests(unittest.TestCase):
    def app(self):
        a=App.__new__(App);a.lock=threading.RLock();a.ready=threading.Condition(a.lock)
        a.source_contract=dict(physical_source_verified=True,status='UNIT_TEST_ONLY')
        a.epoch=4;a.session=70;a.received=collections.OrderedDict();a.exact=collections.OrderedDict();a.seen_components=set()
        a.detector=NS(lock=threading.Lock(),latest=None);a.road=NS(cv=threading.Condition(),result=None);a.lights=NS(lock=threading.Lock(),latest=None)
        a.notified=[];a.link=NS(feedback=NS(inference_completed=lambda *args,**kw:a.notified.append((args,kw))))
        a.slot=None;a.skipped_complete=0;a.stamps=collections.deque();a.sequence=0;a.frame_metadata={};a.record=lambda *args,**kw:None
        return a
    def test_rgb565_little_endian_bgr_and_exact_size(self):
        p=np.zeros((720,1280),dtype='<u2');p[0,:3]=[0xf800,0x07e0,0x001f]
        im=rgb565(p.tobytes());self.assertEqual(im[0,:3].tolist(),[[0,0,255],[0,255,0],[255,0,0]])
        self.assertEqual(im.shape,(720,1280,3))
        with self.assertRaises(ValueError):rgb565(b'bad')
    def test_latest_slot_and_exact_identity(self):
        a=self.app();now=time.monotonic();a.publish(100,b'x',now);a.publish(101,b'y',now)
        self.assertEqual(a.skipped_complete,1);self.assertEqual(a.slot[2],101)
        a.detector.latest=({'epoch':4,'frame_id':100,'count':2},None,now,None)
        a.road.result={'epoch':3,'source_frame_id':101};a.lights.latest={'epoch':4,'source_frame_id':999}
        a.collect_exact();self.assertIsNotNone(a.lookup(100,now));self.assertIsNone(a.lookup(101,now));self.assertIsNone(a.lookup(999,now))
        obs=a.lookup(100,now);self.assertEqual(obs['signal']['actions'],[]);self.assertEqual(obs['session'],70)
        self.assertEqual(list(obs['exact_components']),['objects'])
        self.assertEqual(a.frame_state(100,now)['inference_complete'],True)
        a.session=71;self.assertIsNone(a.lookup(100,now))
    def test_reset_rejects_old_worker_and_bounded_history(self):
        a=self.app();now=time.monotonic();a.publish(7,b'raw',now);a.jpeg=b'old';a.obs={};a.frame=7
        a.detector.latest=({'epoch':4,'frame_id':7},None,now,None);a.collect_exact();self.assertTrue(a.exact)
        a.clear_live(71,now,'SESSION_CHANGED');self.assertEqual(a.epoch,5);self.assertIsNone(a.jpeg);self.assertFalse(a.exact)
        a.collect_exact();self.assertFalse(a.exact)
        for i in range(200):a.publish(i,b'raw',now)
        self.assertLessEqual(len(a.received),128)
        a.prune(now+3);self.assertFalse(a.received)
    def test_shared_latest_slot_counts_skip_not_partial_frames(self):
        b=Bridge.__new__(Bridge);ctx=mp.get_context('spawn');b.raw=ctx.RawArray('B',1280*720*2);b.meta=ctx.RawArray('Q',6);b.lock=ctx.Lock();b.last_serial=0;b.poll=lambda:None
        with b.lock:b.meta[:]=[70,2,123,10000000000,10,4567]
        x=b.take();self.assertEqual(x[:3],(70,2,123));self.assertEqual(x[4],10);self.assertEqual(len(x[3]),1843200);self.assertIsNone(b.take())
        self.assertEqual(x[5],4567)
        with b.lock:b.meta[2]=126;b.meta[4]=13
        self.assertEqual(b.take()[-1],2)
    def test_only_real_exact_observation_is_forwarded_to_receiver(self):
        b=NS(commands=queue.Queue(maxsize=2),ipc_dropped=0,lookup=lambda fid,now:None);f=FeedbackProxy(b)
        f.inference_completed(4,time.monotonic(),session=70);self.assertTrue(b.commands.empty())
        b.lookup=lambda fid,now:dict(source='LIVE_FRONT',session=70,frame_id=fid)
        f.inference_completed(4,time.monotonic(),session=71);self.assertTrue(b.commands.empty())
        f.inference_completed(4,time.monotonic(),session=70);self.assertEqual(b.commands.get_nowait()['observation']['frame_id'],4)
    def test_file_run_never_constructs_business_bridge(self):
        a=App.__new__(App);a.mode='FILE_TEST';a.log_stop=threading.Event();a.writer=NS(join=lambda **kw:None)
        with patch('file_demo.Demo.run') as file_run,patch('app.Bridge',side_effect=AssertionError('FILE socket forbidden')):
            a.run();file_run.assert_called_once()
    def test_unverified_source_cannot_feed_real_event_lookup(self):
        a=self.app();now=time.monotonic();a.publish(100,b'raw',now)
        a.detector.latest=({'epoch':4,'frame_id':100,'count':2},None,now,None)
        a.source_contract={'physical_source_verified':False,'status':'WAITING_FPGA_HANDOFF'}
        a.collect_exact();self.assertTrue(a.exact);self.assertIsNone(a.lookup(100,now))
        self.assertEqual(a.exact[(70,100)][1]['signal']['exact_identity']['physical_source'],'UNVERIFIED')
    def test_source_contract_pending_and_incompatible_handoff(self):
        current=load_source_contract();self.assertFalse(current['physical_source_verified']);self.assertFalse(current['physical_acceptance_passed'])
        data=dict(current,physical_source_verified=True,runtime_source_evidence={'method':'UNIT_TEST_NOT_REAL'},fpga_handoff_summary='UNIT_TEST_NOT_REAL',reviewed_wire_profile=dict(EXPECTED_PROFILE,width=640),reviewed_event_frame_origin='NET_RX_COMPLETE_FRAME')
        with tempfile.TemporaryDirectory() as d:
            p=__import__('pathlib').Path(d)/'source.json';p.write_text(json.dumps(data))
            self.assertFalse(load_source_contract(p)['physical_source_verified'])
            data['reviewed_wire_profile']=EXPECTED_PROFILE;p.write_text(json.dumps(data))
            self.assertTrue(load_source_contract(p)['physical_source_verified'])
            self.assertFalse(load_source_contract(p)['physical_acceptance_passed'])
    def test_board_publication_identity_and_timestamp_are_not_sender_clock(self):
        a=self.app();now=time.monotonic();a.publish(7,b'raw',now,123456789)
        a.detector.latest=({'epoch':4,'frame_id':7,'count':0},None,now,None);a.collect_exact()
        obs=a.lookup(7,now);self.assertEqual(obs['frame_id'],7)
        self.assertEqual(obs['frame_metadata']['board_timestamp_ms'],123456789)
        self.assertEqual(obs['frame_metadata']['host_complete_received_monotonic'],now)
        self.assertNotIn('one_way_latency_ms',obs['frame_metadata'])

if __name__=='__main__':unittest.main(verbosity=2)
