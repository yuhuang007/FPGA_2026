"""Narrow tests: image evidence, duplicate frame, transition, epoch/TTL."""
import unittest,time
from unittest.mock import patch
from pathlib import Path
import cv2,numpy as np
import traffic
class Tests(unittest.TestCase):
 def test_different_image_confirmation_and_transition(self):
  m=traffic.Lights(neural=False);image=np.zeros((60,100,3),np.uint8);b=dict(box=[10,10,55,28],body_source='TEST',color='RED')
  with patch.object(traffic,'candidates',return_value=([b],{})),patch.object(traffic,'color_check',side_effect=lambda im,x:x):
   r=m.analyze(image,1,10,100.)
   self.assertEqual(r['lights'][0]['color'],'UNKNOWN')
   r=m.analyze(image,1,10,100.)
   self.assertEqual(r['lights'][0]['color'],'UNKNOWN')
   r=m.analyze(image,1,11,100.25)
   self.assertEqual(r['lights'][0]['color'],'RED');old=r['lights'][0]['id']
   b['color']='GREEN';r=m.analyze(image,1,12,100.5)
   self.assertEqual(r['lights'][0]['color'],'UNKNOWN');self.assertEqual(r['lights'][0]['observed_color'],'GREEN')
   r=m.analyze(image,1,13,100.75)
   self.assertEqual(r['lights'][0]['color'],'GREEN');self.assertEqual(r['lights'][0]['id'],old);self.assertEqual(len(r['transitions']),1)
   self.assertEqual(traffic.fresh(r,101.36,1)['lights'],[])
   self.assertEqual(traffic.fresh(r,100.8,2)['lights'],[])
   m.reset();self.assertEqual(m.tracks,[]);self.assertEqual(m.patches,{})
 def test_real_fixed_night_and_LED(self):
  for filename,expected in [('SC_YJ_099_raw.png','RED'),('SC_YJ_103_raw.png','RED'),('SC_YJ_107_raw.png','GREEN'),('LED_GREEN_raw.jpg','GREEN')]:
   image=cv2.imread(str(Path(__file__).parent/'inputs'/filename));self.assertIsNotNone(image)
   bs,_=traffic.candidates(image);rows=[traffic.color_check(image,b)for b in bs if not traffic.dense_context(image,b['box'])[0]]
   self.assertEqual([x['color']for x in rows],[expected,expected],filename)
   self.assertTrue(all(b['box'][0]>image.shape[1]*.5 for b in rows),'LED text must not appear as a left image lamp')
   self.assertTrue(all(b['control_relation']=='UNKNOWN'for b in rows))
 def test_crop_edge_is_not_confirmed_color(self):
  image=np.zeros((50,100,3),np.uint8);b=dict(box=[10,10,40,30],body_source='YOLO',confidence=.9,crop_edge=True)
  r=traffic.color_check(image,b);self.assertEqual(r['color'],'UNKNOWN');self.assertIn('裁剪边缘',r['reason'])
if __name__=='__main__':unittest.main(verbosity=2)
