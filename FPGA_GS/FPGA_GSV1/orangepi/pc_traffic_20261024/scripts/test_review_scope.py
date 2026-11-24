"""Reject semantic changes concealed inside geometry/occlusion-only rechecks."""
import copy,unittest
from intake_independent_reviews import validate_preserved_semantics,preserved_check_is_traceable

class ScopeChecks(unittest.TestCase):
    def setUp(self):
        self.old={'objects':[{'id':'body','type':'body','kind':'motor_vehicle','bbox_xyxy':[10,10,30,50],
            'occlusion':'none','quality_flags':[]},{'id':'lamp','type':'emitter','parent_id':'body',
            'bbox_xyxy':[12,12,25,24],'state':'red','color_readable':True}]}
    def test_actual_occlusion_recheck_preserves_unchanged_kind(self):
        new=copy.deepcopy(self.old);new['objects'][0]['occlusion']='partial'
        validate_preserved_semantics(self.old,new,['body.occlusion'],False,True)
    def test_geometry_recheck_cannot_hide_color_change(self):
        new=copy.deepcopy(self.old);new['objects'][1]['bbox_xyxy']=[11,11,26,25];new['objects'][1]['state']='yellow'
        with self.assertRaises(AssertionError):validate_preserved_semantics(self.old,new,['lamp.bbox_xyxy'],False,False)
    def test_declared_kind_change_still_requires_real_kind_check(self):
        new=copy.deepcopy(self.old);new['objects'][0]['kind']='pedestrian'
        with self.assertRaises(AssertionError):validate_preserved_semantics(self.old,new,['body.kind'],False,True)
    def test_attributes_cannot_change_on_a_geometry_only_record(self):
        new=copy.deepcopy(self.old);new['objects'][0]['occlusion']='partial'
        with self.assertRaises(AssertionError):validate_preserved_semantics(self.old,new,['body.occlusion'],False,False)
    def test_unchecked_geometry_cannot_change(self):
        new=copy.deepcopy(self.old);new['objects'][0]['bbox_xyxy']=[9,9,30,50]
        with self.assertRaises(AssertionError):validate_preserved_semantics(self.old,new,['body.bbox_xyxy'],True,True,False)

    def test_new_nonemitting_ignore_uses_real_kind_bounds_without_fake_attributes(self):
        new=copy.deepcopy(self.old);new['objects'].append(dict(id='upper',type='ignore',kind='unknown',bbox_xyxy=[40,10,50,20],reason='Unresolved display'))
        validate_preserved_semantics(self.old,new,['upper'],True,False,True)
        with self.assertRaises(AssertionError):validate_preserved_semantics(self.old,new,['upper'],False,False,True)

    def test_new_ignore_cannot_smuggle_unchecked_state(self):
        new=copy.deepcopy(self.old);new['objects'].append(dict(id='upper',type='ignore',kind='unknown',bbox_xyxy=[40,10,50,20],state='red'))
        with self.assertRaises(AssertionError):validate_preserved_semantics(self.old,new,['upper'],True,False,True)

    def test_explicit_unknown_ignore_type_scope_does_not_fake_global_kind_check(self):
        new=copy.deepcopy(self.old);new['objects'].append(dict(id='upper',type='ignore',bbox_xyxy=[40,10,50,20],reason='Unresolved visible patch'))
        scope=[dict(object_id='upper',fields=['existence_of_unresolved_visible_patch','type','bbox_xyxy','reason'],bbox_xyxy=[40,10,50,20],type='ignore')]
        validate_preserved_semantics(self.old,new,['upper'],False,False,True,scope)
        scope[0]['bbox_xyxy']=[0,0,1,1]
        with self.assertRaises(AssertionError):validate_preserved_semantics(self.old,new,['upper'],False,False,True,scope)

    def test_unknown_ignore_scope_cannot_smuggle_a_class(self):
        new=copy.deepcopy(self.old);new['objects'].append(dict(id='upper',type='ignore',kind='motor_vehicle',bbox_xyxy=[40,10,50,20],reason='Unresolved'))
        scope=[dict(object_id='upper',fields=['existence_of_unresolved_visible_patch','type','bbox_xyxy','reason'],bbox_xyxy=[40,10,50,20],type='ignore')]
        with self.assertRaises(AssertionError):validate_preserved_semantics(self.old,new,['upper'],False,False,True,scope)

    def test_new_positive_or_undeclared_object_cannot_pass_narrow_scope(self):
        new=copy.deepcopy(self.old);new['objects'].append(dict(id='upper',type='body',kind='motor_vehicle',bbox_xyxy=[40,10,50,20]))
        with self.assertRaises(AssertionError):validate_preserved_semantics(self.old,new,['upper'],True,False,True)
        with self.assertRaises(AssertionError):validate_preserved_semantics(self.old,new,['body.bbox_xyxy'],True,True,True)

    def chain(self):
        a=dict(candidate_id='x',image_sha256='image',annotation_sha256='v1',source_file='first',source_file_sha256='s1',line=1,
            kind_recertified_this_record=True,attributes_recertified_this_record=True,bounds_recertified_this_record=True)
        b=dict(a,annotation_sha256='v2',source_file='second',source_file_sha256='s2',kind_recertified_this_record=False,
            attributes_recertified_this_record=False,unchanged_semantics_prior_review={k:a[k] for k in
                ('source_file','source_file_sha256','line','annotation_sha256')})
        return a,b

    def test_second_geometry_revision_keeps_genuine_prior_semantic_chain(self):
        a,b=self.chain()
        self.assertTrue(preserved_check_is_traceable(b,[a,b],'attributes'))
        self.assertFalse(b['attributes_recertified_this_record'])

    def test_trace_cannot_cross_image_or_label_sha(self):
        a,b=self.chain();b['image_sha256']='different_image'
        self.assertFalse(preserved_check_is_traceable(b,[a,b],'kind'))
        a,b=self.chain();b['unchanged_semantics_prior_review']['annotation_sha256']='unreviewed'
        self.assertFalse(preserved_check_is_traceable(b,[a,b],'attributes'))

    def test_missing_or_cyclic_check_does_not_pass(self):
        a,b=self.chain();b['unchanged_semantics_prior_review']={k:b[k] for k in
            ('source_file','source_file_sha256','line','annotation_sha256')}
        self.assertFalse(preserved_check_is_traceable(b,[a,b],'attributes'))
        b.pop('unchanged_semantics_prior_review')
        self.assertFalse(preserved_check_is_traceable(b,[a,b],'kind'))

if __name__=='__main__':unittest.main()
