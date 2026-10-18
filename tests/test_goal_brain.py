import json,sys,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from whisper.core.action_agent import ActionAgent
from whisper.core.goal_brain import GoalBrain
from whisper.learning.experience import ExperienceMemory

def action(tool,args):return json.dumps({'kind':'action','message':'','steps':[{'tool':tool,'args':args}]})
def done():return json.dumps({'kind':'chat','message':'İncelemeye hazır.','steps':[]})

class GoalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'memory.db'
        self.brain=GoalBrain(ActionAgent(self.path),self.path)
        self.stop=threading.Event()
        self.model=Mock(base_url='http://localhost:11434')
    def run_goal(self,executor,goal='Sistem durumunu kontrol et'):
        return self.brain.run(goal,self.model,[],executor,self.stop)
    def test_observes_tool_result_before_next_plan(self):
        self.model.chat.side_effect=[action('system_info',{}),done()]
        execute=Mock(return_value={'status':'success','response':'RAM yüzde 30'})
        result=self.run_goal(execute)
        self.assertEqual(result['status'],'review');self.assertFalse(result['goal_verified'])
        self.assertIn('RAM yüzde 30',self.model.chat.call_args_list[1].args[1])
        execute.assert_called_once()
    def test_duplicate_action_blocked_even_if_model_repeats_it(self):
        self.model.chat.side_effect=[action('take_note',{'text':'not'}),action('take_note',{'text':'not'})]
        execute=Mock(return_value={'status':'success','response':'not kaydedildi'})
        result=self.run_goal(execute)
        self.assertEqual(result['status'],'blocked');execute.assert_called_once()
    def test_failure_can_choose_different_tool(self):
        self.model.chat.side_effect=[action('system_info',{}),action('repo_status',{}),done()]
        execute=Mock(side_effect=[{'status':'error','response':'ölçüm başarısız'}, {'status':'success','response':'depo temiz'}])
        result=self.run_goal(execute)
        self.assertEqual(result['status'],'review');self.assertEqual(execute.call_count,2)
        self.assertIn('ölçüm başarısız',self.model.chat.call_args_list[1].args[1])
    def test_permission_block_stops_replanning(self):
        self.model.chat.return_value=action('system_info',{})
        result=self.run_goal(Mock(return_value={'status':'blocked','response':'Araçlar kapalı'}))
        self.assertEqual(result['status'],'blocked');self.model.chat.assert_called_once()
    def test_pre_cancel_never_calls_model(self):
        self.stop.set()
        result=self.run_goal(Mock())
        self.assertEqual(result['status'],'cancelled');self.model.chat.assert_not_called()
    def test_cancel_during_tool_prevents_next_plan(self):
        self.model.chat.return_value=action('system_info',{})
        def tool(*args):self.stop.set();return {'status':'success','response':'ölçüldü'}
        result=self.run_goal(tool)
        self.assertEqual(result['status'],'cancelled');self.model.chat.assert_called_once()
    def test_step_budget_stops(self):
        self.brain.max_steps=1
        self.model.chat.return_value=action('system_info',{})
        result=self.run_goal(Mock(return_value={'status':'success','response':'ölçüldü'}))
        self.assertEqual(result['status'],'budget_exhausted');self.model.chat.assert_called_once()
    def test_feedback_persists_and_is_separate_context(self):
        self.model.chat.side_effect=[action('system_info',{}),done()]
        result=self.run_goal(Mock(return_value={'status':'error','response':'boş çıktı'}))
        memory=ExperienceMemory(self.path)
        self.assertTrue(memory.correct(result['experience_id'],'Önce RAM ölçümüne bak.'))
        self.model.chat.side_effect=[done()]
        self.run_goal(Mock())
        payload=json.loads(self.model.chat.call_args.args[1])
        self.assertEqual(payload['observations']['past_experiences'][0]['feedback'],'Önce RAM ölçümüne bak.')
        self.assertFalse(memory.correct(999,'bulunmayan deneyim'))
    def test_code_generation_receipt_id_guides_testing(self):
        self.model.chat.side_effect=[action('propose_improvement',{'goal':'küçük modülü düzelt'}),
            action('test_improvement',{'id':'abcdef123456'}),done()]
        execute=Mock(side_effect=[{'status':'success','response':'taslak','proposal_id':'abcdef123456'},
                                {'status':'blocked','response':'Docker gerekli'}])
        result=self.run_goal(execute,'Kod geliştir')
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(execute.call_args.args,('test_improvement',{'id':'abcdef123456'}))
        self.assertIn('abcdef123456',self.model.chat.call_args_list[1].args[1])
    def test_multiple_steps_rejected_before_execution(self):
        self.model.chat.return_value=json.dumps({'kind':'action','message':'','steps':[
            {'tool':'system_info','args':{}},{'tool':'repo_status','args':{}}]})
        execute=Mock();result=self.run_goal(execute)
        self.assertEqual(result['status'],'error');execute.assert_not_called()
    def test_remote_model_rejected_without_sending_experience(self):
        self.model.base_url='https://example.com'
        self.assertEqual(self.run_goal(Mock())['status'],'blocked')
        self.model.chat.assert_not_called()
    def test_two_errors_stop_loop(self):
        self.model.chat.side_effect=[action('system_info',{}),action('repo_status',{})]
        result=self.run_goal(Mock(return_value={'status':'error','response':'hata'}))
        self.assertEqual(result['status'],'error');self.assertEqual(self.model.chat.call_count,2)

    def test_code_mode_cannot_change_volume_or_use_unrelated_proposal(self):
        for plan in (action('set_volume',{'level':50}),action('test_improvement',{'id':'abcdef123456'})):
            self.model.chat.return_value=plan
            execute=Mock()
            result=self.brain.run('Kod hedefi',self.model,[],execute,self.stop,code_mode=True)
            self.assertEqual(result['status'],'blocked');execute.assert_not_called()

if __name__=='__main__':unittest.main()
