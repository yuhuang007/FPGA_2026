import copy
import unittest
from intake_body_detection_reviews import validate_scope


class BodyDetectionScopeTests(unittest.TestCase):
    def setUp(self):
        self.task={'candidate_id':'one','image_sha256':'photo','annotation_sha256':'label',
                   'label_version':'r1','first_pass_reviewer':'PC_AI'}
        self.annotation={'objects':[{'id':'body','type':'body','kind':'motor_vehicle'},
                                    {'id':'unknown','type':'ignore'},{'id':'emitter','type':'emitter','state':'unknown'}]}
        self.raw=dict(candidate_id='one',request_sha256='request',image_sha256='photo',reviewed_annotation_sha256='label',
            label_version='r1',reviewer_type='AI',independent_from_first_pass=True,reviewer_id='board_AI',
            human_signoff=False,training_approval=False,auxiliary_emitter_findings_preserved=True,
            attributes_accepted_for_training=False,body_detection_decision='accept',actual_method=['fixture'],
            findings=['fixture'],viewed_evidence=['fixture'],reviewed_at='2026-10-25T04:00:00+00:00',
            body_full_original_checked=True,body_omission_search_completed=True,body_kind_checked=True,
            body_bounds_checked=True,ignore_coverage_checked=True,confirmed_body_ids=['body'],confirmed_ignore_ids=['unknown'])

    def validate(self):validate_scope(self.raw,self.task,self.annotation,'request')

    def test_body_only_accept_does_not_require_or_certify_color(self):self.validate()

    def test_stale_label_rejected(self):
        self.raw['reviewed_annotation_sha256']='old'
        with self.assertRaises(AssertionError):self.validate()

    def test_cannot_drop_ignore(self):
        self.raw['confirmed_ignore_ids']=[]
        with self.assertRaises(AssertionError):self.validate()

    def test_cannot_omit_an_existing_body(self):
        self.raw['confirmed_body_ids']=[]
        with self.assertRaises(AssertionError):self.validate()

    def test_cannot_certify_auxiliary_attributes(self):
        self.raw['attributes_accepted_for_training']=True
        with self.assertRaises(AssertionError):self.validate()

    def test_missing_actual_body_omission_search_rejected(self):
        self.raw['body_omission_search_completed']=False
        with self.assertRaises(AssertionError):self.validate()

    def test_same_first_reviewer_cannot_sign_independent_scope(self):
        self.raw['reviewer_id']='PC_AI'
        with self.assertRaises(AssertionError):self.validate()


if __name__=='__main__':unittest.main()
