"""Guard incremental review refresh against revoking an identical old accept."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import integrate_remaining_reviews as integration


class ExistingReviewPreservationTests(unittest.TestCase):
    def setUp(self):
        self.raw={'decision':'accept','reviewer_id':'independent_AI','PC_arbitration_required':['site linkage remains a data condition']}
        self.review={'annotation_sha256':'label','source_file':'review.jsonl','source_file_sha256':'file','line':1}
        self.entry={'annotation_sha256':'label','PC_resolution':'Body accepted; site reviewed separately.',
            'original_arbitration_requests':self.raw['PC_arbitration_required'],
            'independent_review_source':{'file':'review.jsonl','sha256':'file','line':1}}

    def test_same_adjudicated_accept_survives_refresh(self):
        self.assertTrue(integration.existing_accept_covers_same_record(self.entry,self.review,self.raw))

    def test_changed_label_or_later_disagreement_is_not_inherited(self):
        self.assertFalse(integration.existing_accept_covers_same_record(self.entry,dict(self.review,annotation_sha256='new'),self.raw))
        self.assertFalse(integration.existing_accept_covers_same_record(self.entry,self.review,dict(self.raw,decision='needs_modify')))

    def test_aggregate_copy_must_match_every_field(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);p=root/'aggregate.jsonl';p.write_text(json.dumps(self.raw)+'\n',encoding='utf-8')
            entry=dict(self.entry,independent_review_source={'file':p.name,'sha256':integration.sha(p),'line':1})
            with patch.object(integration,'R',root):
                self.assertTrue(integration.existing_accept_covers_same_record(entry,self.review,self.raw))
                self.assertFalse(integration.existing_accept_covers_same_record(entry,self.review,dict(self.raw,reviewer_id='different_AI')))


if __name__=='__main__':unittest.main()
