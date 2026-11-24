"""Safety tests for the actual per-original promotion boundary."""
import copy
import unittest
from qualify_clean_originals import validate_contract, assert_unique_originals


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.e = {'candidate_id': 'one', 'source_annotation_sha256': 'label', 'source_image_sha256': 'photo',
                  'targets': [{'source_id': 'body'}], 'inherited_split': 'train', 'inherited_group': 'scene',
                  'split_assigned_before_derivation': True, 'ignore_intersections': 0, 'partial_body_intersections': 0}
        self.current = {'confirmed_body_ids': ['body'], 'annotation_sha256': 'label', 'image_sha256': 'photo',
                        'first_pass_reviewer': 'PC_AI', 'independent_reviewer': 'board_AI'}
        self.group = {'group_status': 'verified', 'annotation_sha256': 'label', 'image_sha256': 'photo',
                      'official_split': 'train', 'leakage_group': 'scene', 'license_status': 'verified', 'clean_original': 'verified'}
        self.manifest = {'original_split_release_verified': True}

    def validate(self, validated=None, visual=None):
        validate_contract(self.e, self.current, self.group, self.manifest,
                          {'one'} if validated is None else validated, {'one'} if visual is None else visual)

    def test_genuine_current_safe_original(self):
        self.validate()

    def test_stale_label_revokes_qualification(self):
        self.current['annotation_sha256'] = 'revised'
        with self.assertRaisesRegex(AssertionError, 'stale label'): self.validate()

    def test_cannot_reassign_crop_split(self):
        self.e['inherited_split'] = 'val'
        with self.assertRaisesRegex(AssertionError, 'wrong inherited split'): self.validate()

    def test_unreviewed_cannot_qualify(self):
        self.current = None
        with self.assertRaisesRegex(AssertionError, 'confirmation missing'): self.validate()

    def test_unvalidated_crop_cannot_qualify(self):
        with self.assertRaisesRegex(AssertionError, 'not validated'): self.validate(validated=set())

    def test_unviewed_crop_cannot_qualify(self):
        with self.assertRaisesRegex(AssertionError, 'visual QA'): self.validate(visual=set())

    def test_ignore_or_partial_body_cannot_be_background(self):
        self.e['ignore_intersections'] = 1
        with self.assertRaises(AssertionError): self.validate()

    def test_reencoded_capture_does_not_add_count(self):
        self.group['redundant_capture_of'] = 'other'
        with self.assertRaisesRegex(AssertionError, 'duplicate capture'): self.validate()

    def test_same_photo_variants_do_not_add_count(self):
        a = {'candidate_id': 'one', 'canonical_original_id': 'flickr123', 'source_image_sha256': 'small', 'leakage_group': 'scene', 'split': 'val'}
        b = dict(a, candidate_id='two', source_image_sha256='large')
        with self.assertRaisesRegex(AssertionError, 'duplicate original'): assert_unique_originals([a,b])

    def test_linked_photos_never_cross_splits(self):
        a = {'candidate_id': 'one', 'canonical_original_id': 'photo1', 'source_image_sha256': 'one', 'leakage_group': 'scene', 'split': 'train'}
        b = dict(a, candidate_id='two', canonical_original_id='photo2', source_image_sha256='two', split='val')
        with self.assertRaisesRegex(AssertionError, 'cross-split identity'): assert_unique_originals([a,b])


if __name__ == '__main__':
    unittest.main()
