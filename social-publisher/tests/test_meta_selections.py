import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import Hold
from settings import Settings
from workflow import Workflow,render

class MetaControls:
    def __init__(self,instagram=True,facebook=False,story=True):
        self.accounts={'boldstonesculpture':instagram,'Boldstone Sculpture':facebook}
        self.story=story;self.expanded=False;self.events=[];self.presses={}
    def call(self,name,request):
        self.events.append(copy.deepcopy(request));op=request['op']
        if op=='exists':
            selector=request['locator'][0]['selector']
            if 'aria-expanded=true' in selector:return {'exists':self.expanded}
            if 'aria-expanded=false' in selector:return {'exists':not self.expanded}
            return {'exists':True}
        if op=='assert':
            summary=' and '.join(k for k in ['Boldstone Sculpture','boldstonesculpture'] if self.accounts[k])
            for check in request['checks']:
                if 'checked' in check:
                    label=check['locator'][0]['name'];value=self.story if label=='Share to Facebook story' else self.accounts[label]
                    if value!=check['checked']:raise Hold('WRONG_SELECTED_ACCOUNT')
                if check.get('contains') and check['contains'] not in summary:raise Hold('TEXT_READBACK_CHANGED')
                if check.get('not_contains') and check['not_contains'] in summary:raise Hold('WRONG_SELECTED_ACCOUNT')
            return {'ok':True,'checks':request['checks']}
        if op=='click':self.expanded=not self.expanded;return {'ok':True}
        if op=='set_checked':
            label=request['locator'][0]['name'];self.presses[label]=self.presses.get(label,0)+1
            if label=='Share to Facebook story':self.story=request['value']
            else:self.accounts[label]=request['value']
            return {'ok':True}
        raise AssertionError(op)

class MetaSelectionTests(unittest.TestCase):
    def setUp(self):
        self.settings=Settings();self.profile=self.settings.profile('boldstone_instagram')
        self.recipe=self.settings.workflow(self.profile)
        self.destination=render(next(s for s in self.recipe['prepare'] if s['op']=='ensure_destination'),self.profile)
        self.story=[{'selector':'input[type=checkbox]','name':'Share to Facebook story'}]
    def exercise(self,controls):
        workflow=Workflow(self.settings,controls,Path('.'))
        workflow.ensure_destination('boldstone_instagram',self.destination)
        workflow.set_checked('boldstone_instagram',self.story,True)
    def test_instagram_and_story_already_on_are_never_pressed_or_opened(self):
        controls=MetaControls();self.exercise(controls);self.exercise(controls)
        self.assertEqual(controls.presses,{})
        self.assertFalse(any(e['op'] in {'click','set_checked'} for e in controls.events))
    def test_wrong_destination_and_story_off_are_corrected_once_then_left_alone(self):
        controls=MetaControls(instagram=False,facebook=True,story=False)
        self.exercise(controls);self.exercise(controls)
        self.assertEqual(controls.presses,{'boldstonesculpture':1,'Boldstone Sculpture':1,'Share to Facebook story':1})
        self.assertEqual(sum(e['op']=='click' for e in controls.events),2)
        self.assertEqual(controls.accounts,{'boldstonesculpture':True,'Boldstone Sculpture':False})
        self.assertTrue(controls.story)
    def test_instagram_already_selected_is_not_pressed_when_removing_extra_facebook_destination(self):
        controls=MetaControls(instagram=True,facebook=True,story=True)
        self.exercise(controls)
        self.assertEqual(controls.presses,{'Boldstone Sculpture':1})
    def test_unreadable_checkbox_does_not_trigger_a_blind_click(self):
        class Unreadable(MetaControls):
            def call(self,name,request):
                if request['op']=='assert':raise Hold('CHECKED_STATE_UNAVAILABLE')
                return super().call(name,request)
        controls=Unreadable()
        with self.assertRaises(Hold) as caught:Workflow(self.settings,controls,Path('.')).set_checked('boldstone_instagram',self.story,True)
        self.assertEqual(caught.exception.code,'CHECKED_STATE_UNAVAILABLE');self.assertEqual(controls.presses,{})
    def test_facebook_requires_story_on_before_upload_and_submit(self):
        recipe=self.settings.workflow(self.settings.profile('boldstone_facebook'))
        step=next(s for s in recipe['prepare'] if s['op']=='set_checked' and s['locator'][0].get('name')=='Share to Facebook story')
        guard=next(g for g in recipe['ready'] if g.get('purpose')=='story')
        self.assertTrue(step['value']);self.assertFalse(step.get('if_exists',False))
        self.assertTrue(guard['checked']);self.assertFalse(guard.get('if_exists',False))
        self.assertNotIn('confirmation',step)
        controls=MetaControls(story=False)
        with self.assertRaises(Hold):controls.call('boldstone_facebook',{'op':'assert','checks':[guard]})
    def test_instagram_enables_story_when_the_native_control_is_exposed(self):
        step=next(s for s in self.recipe['prepare'] if s['op']=='set_checked' and s['locator'][0].get('name')=='Share to Facebook story')
        self.assertTrue(step['value']);self.assertNotIn('confirmation',step)
        self.assertTrue(next(g for g in self.recipe['ready'] if g.get('purpose')=='story')['checked'])

if __name__=='__main__':unittest.main()
