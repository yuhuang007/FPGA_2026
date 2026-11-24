"""Adversarial geometry checks, not recognition training or a CUDA smoke run."""
import unittest
from pilot_clean_crops import candidates,intersects,contains

def body(id,b,truncated=False):return {'id':id,'type':'body','kind':'motor_vehicle','bbox_xyxy':b,'truncated':truncated}
def label(objects):return {'image_size':[1920,1080],'objects':objects}
def final(objects):return {'confirmed_body_ids':[o['id'] for o in objects if o['type']=='body']}

class SafeCropChecks(unittest.TestCase):
    def test_all_visible_bodies_labelled_not_just_anchor(self):
        objects=[body('a',[500,300,530,390]),body('b',[900,300,930,390])]
        c,_=candidates(label(objects),final(objects));self.assertEqual({o['id'] for o in c['bodies']},{'a','b'})
    def test_ignore_overlapping_positive_fails_closed(self):
        objects=[body('a',[500,300,530,390]),{'id':'i','type':'ignore','bbox_xyxy':[490,290,540,400]}]
        c,_=candidates(label(objects),final(objects));self.assertIsNone(c)
    def test_standalone_emitter_is_not_background(self):
        objects=[body('a',[500,300,530,390]),{'id':'e','type':'emitter','bbox_xyxy':[800,300,810,320]}]
        c,obs=candidates(label(objects),final(objects));self.assertTrue(any(o['id']=='e' for o in obs));self.assertFalse(any(intersects(c['crop_xyxy'],o['padded_bbox']) for o in obs))
    def test_truncated_body_never_becomes_complete_body(self):
        objects=[body('a',[500,300,530,390]),body('cut',[1900,100,1920,250],True)]
        c,obs=candidates(label(objects),final(objects));self.assertEqual([o['id'] for o in c['bodies']],['a']);self.assertFalse(intersects(c['crop_xyxy'],objects[1]['bbox_xyxy']))
    def test_unconfirmed_body_is_an_obstacle(self):
        objects=[body('a',[500,300,530,390]),body('unreviewed',[800,300,830,390])]
        c,obs=candidates(label(objects),{'confirmed_body_ids':['a']});self.assertFalse(intersects(c['crop_xyxy'],objects[1]['bbox_xyxy']))
    def test_no_safe_context_does_not_force_crop(self):
        objects=[body('a',[654,228,739,266]),{'id':'near','type':'ignore','bbox_xyxy':[764,226,843,264]},
            {'id':'far','type':'ignore','bbox_xyxy':[886,380,917,402]}]
        c,_=candidates(label(objects),final(objects));self.assertIsNone(c)
    def test_complete_large_head_keeps_all_available_original_edge_context(self):
        objects=[body('complete',[40,100,440,230])]
        c,_=candidates(label(objects),final(objects))
        self.assertIsNotNone(c)
        self.assertEqual(c['crop_xyxy'],[0,0,1920,1080])

if __name__=='__main__':unittest.main()
