import copy
from types import SimpleNamespace
import unittest
import torch
from source_partial_yolo import SourceBCE,assert_safe_augmentation,validate_release_entries


class SparseSourceSafetyTests(unittest.TestCase):
    def test_source_positives_override_unknown_and_complete_background_survives(self):
        x=torch.zeros(2,3,2,requires_grad=True);target=torch.zeros_like(x);target[0,0,0]=.8
        bce=SourceBCE();bce.sparse_rows=[True,False];bce(x,target).sum().backward()
        self.assertLess(x.grad[0,0,0],0)
        self.assertEqual(torch.count_nonzero(x.grad[0]).item(),1)
        self.assertTrue((x.grad[1]>0).all())

    def test_empty_sparse_image_cannot_create_negative_examples(self):
        x=torch.randn(1,5,2,requires_grad=True);bce=SourceBCE();bce.sparse_rows=[True]
        bce(x,torch.zeros_like(x)).sum().backward();self.assertEqual(torch.count_nonzero(x.grad).item(),0)

    def test_missing_source_identity_fails(self):
        with self.assertRaises(AssertionError):SourceBCE()(torch.zeros(1,2,2),torch.zeros(1,2,2))

    def test_mixed_image_augmentation_is_rejected(self):
        for flag in ('mosaic','mixup','copy_paste','translate','scale','perspective'):
            with self.assertRaises(AssertionError):assert_safe_augmentation(SimpleNamespace(**{flag:.1}))
        assert_safe_augmentation(SimpleNamespace(fliplr=.5))

    def fixture(self):
        return [{'candidate_id':str(i),'canonical_original_id':'original'+str(i),'image_sha256':'sha'+str(i),
            'image_absolute':'/image'+str(i)+'.jpg','split':'train' if i<299 else 'val',
            'leakage_group':'train_scene' if i<299 else 'val_scene',
            'supervision':'positive_only' if i<299 else 'complete'} for i in range(300)]

    def test_native_partial_images_cannot_enter_ordinary_validation(self):
        entries=self.fixture();validate_release_entries(entries);entries[-1]['supervision']='positive_only'
        with self.assertRaises(AssertionError):validate_release_entries(entries)

    def test_three_hundred_crops_cannot_stand_for_one_original(self):
        entries=self.fixture()
        for e in entries:e['canonical_original_id']='one_photo'
        with self.assertRaisesRegex(AssertionError,'Duplicate original'):validate_release_entries(entries)

    def test_scene_group_never_crosses_splits(self):
        entries=self.fixture();entries[-1]['leakage_group']='train_scene'
        with self.assertRaisesRegex(AssertionError,'Cross-split'):validate_release_entries(entries)


if __name__=='__main__':unittest.main()
