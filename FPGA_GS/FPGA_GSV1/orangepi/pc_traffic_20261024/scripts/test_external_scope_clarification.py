import copy
import json
import unittest
from pathlib import Path
from intake_external_scene_reviews import R, validate_body_scope_clarification


class ExactScopeClarificationTests(unittest.TestCase):
    def setUp(self):
        self.raw=json.loads((R/'review_stage2/independent_external_scene_r1/clarification_external_china_shanghai_r2.jsonl').read_text('utf-8'))
        path=R/self.raw['prior_review_evidence']['path']
        self.old=next(json.loads(s) for s in path.read_text('utf-8').splitlines()
                      if json.loads(s)['candidate_id']==self.raw['candidate_id'])
        self.prior={'decision':self.old['decision'],'candidate_id':self.old['candidate_id'],
            'annotation_sha256':self.old['reviewed_annotation_sha256'],'raw_record':self.old}
        mp=R/self.old['revision_manifest'];m=json.loads(mp.read_text('utf-8'))
        entry=next(e for e in m['entries'] if e['candidate_id']==self.raw['candidate_id'])
        self.label=json.loads((mp.parent/entry['annotation']).read_text('utf-8'))

    def test_actual_same_sha_optional_note_does_not_create_new_review(self):
        validate_body_scope_clarification(self.raw,self.prior,self.label)
        self.assertEqual(self.raw['new_sample_count'],0)

    def test_stale_label_and_extra_real_disputes_fail_closed(self):
        raw=copy.deepcopy(self.raw);raw['reviewed_annotation_sha256']='changed'
        with self.assertRaises(AssertionError):validate_body_scope_clarification(raw,self.prior,self.label)
        prior=copy.deepcopy(self.prior);prior['raw_record']['PC_arbitration_required'].append('Actual missing target')
        with self.assertRaises(AssertionError):validate_body_scope_clarification(self.raw,prior,self.label)

    def test_scope_note_cannot_reverse_uncertainty_or_claim_new_review(self):
        prior=copy.deepcopy(self.prior);prior['decision']='uncertain'
        with self.assertRaises(AssertionError):validate_body_scope_clarification(self.raw,prior,self.label)
        raw=copy.deepcopy(self.raw);raw['new_visual_review_performed']=True
        with self.assertRaises(AssertionError):validate_body_scope_clarification(raw,self.prior,self.label)


if __name__=='__main__':unittest.main()
