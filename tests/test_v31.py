import json,unittest
from unittest.mock import Mock,patch
import test_pipeline_regression as pipeline
from whisper.core.action_agent import validate_plan

class IntentModel:
    base_url='http://127.0.0.1:11434'
    model='qwen3:8b'
    def __init__(self,action='start',chat=False):self.action,self.chat=action,chat;self.payloads=[]
    def chat_json(self,system,user,schema,max_tokens=None):
        self.payloads.append(json.loads(user))
        return json.dumps(dict(intent='definition' if self.chat else 'manage_background_research',entities=[],missing_fields=[],
            kind='chat' if self.chat else 'action',message='',steps=[] if self.chat else [dict(tool='research_control',args=dict(action=self.action))]))

class ResearchIntentTests(unittest.TestCase):
    def setUp(self):
        self.fixture=pipeline.Tests();self.fixture.setUp()
        self.addCleanup(self.fixture.tmp.cleanup)
        self.brain=self.fixture.brain;self.brain.cfg.tools_enabled=True;self.brain.cfg.internet=True
        self.brain.autonomous_research.enable(False)
    def ask(self,text,model):
        self.brain.llm=model
        with patch.object(self.brain,'_select_role_model'),patch.object(self.brain.knowledge_processor,'recall',return_value=[dict(source_id=2,summary='Araştırma kelimesinin açıklaması.')]),patch.object(self.brain.knowledge_processor,'answer') as answer,patch.object(self.brain.autonomous_research,'start') as start,patch('sys.stdout'):
            result=self.brain.process_command(text)
        return result,answer,start
    def test_resume_with_keyword_matching_card_executes_control_not_definition(self):
        model=IntentModel()
        result,answer,start=self.ask('araştırma yapmaya devam et',model)
        self.assertEqual(result['status'],'success');self.assertTrue(self.brain.autonomous_research.enabled())
        answer.assert_not_called();start.assert_called_once()
        self.assertEqual(result['route']['target'],'research_control')
        self.assertEqual(model.payloads,[])  # Explicit process control needs no model plan.
    def test_other_resume_phrases_use_semantic_control(self):
        for text in ('Kaldığın yerden araştırmayı sürdür','Arka planda öğrenmeye devam edebilirsin','Araştırmaya yeniden başla'):
            self.brain.autonomous_research.enable(False)
            result,answer,start=self.ask(text,IntentModel())
            self.assertEqual(result['status'],'success');answer.assert_not_called();start.assert_called_once()
    def test_pause_persists_and_does_not_answer_source_card(self):
        self.brain.autonomous_research.enable(True)
        result,answer,start=self.ask('Araştırmaya biraz ara ver',IntentModel('pause'))
        self.assertFalse(self.brain.autonomous_research.enabled());self.assertTrue(self.brain.autonomous_research.stop_event.is_set())
        answer.assert_not_called();start.assert_not_called()
    def test_offline_control_does_not_claim_started(self):
        self.brain.cfg.internet=False
        result,answer,start=self.ask('Araştırma yapmaya devam et',IntentModel())
        self.assertEqual(result['status'],'blocked');self.assertFalse(self.brain.autonomous_research.enabled())
        answer.assert_not_called();start.assert_not_called()
    def test_status_reads_settings_without_enabling(self):
        result,answer,start=self.ask('Araştırma şu an ne durumda?',IntentModel('status'))
        self.assertEqual(result['status'],'success');self.assertIn('kapalı',result['response'])
        self.assertFalse(self.brain.autonomous_research.enabled());start.assert_not_called();answer.assert_not_called()
    def test_definition_still_reaches_knowledge_after_intent(self):
        model=IntentModel(chat=True);self.brain.llm=model
        with patch.object(self.brain,'_select_role_model'),patch.object(self.brain.knowledge_processor,'recall',return_value=[dict(source_id=2,summary='Araştırma açıklaması.')]),patch.object(self.brain.knowledge_processor,'answer',return_value=dict(status='success',response='Kaynaklı tanım.')) as answer,patch.object(self.brain.autonomous_research,'start') as start,patch('sys.stdout'):
            result=self.brain.process_command('Araştırma nedir?')
        self.assertEqual(result['response'],'Kaynaklı tanım.');answer.assert_called_once();start.assert_not_called()
    def test_invalid_control_is_rejected_before_action(self):
        for action in ('shell','download_and_execute',123):
            with self.assertRaises(ValueError):validate_plan(dict(kind='action',message='',steps=[dict(tool='research_control',args=dict(action=action))]),set())
    def test_direct_control_does_not_need_pc_permissions(self):
        self.brain.cfg.tools_enabled=False
        result=self.brain._agent_tool('research_control',dict(action='status'))
        self.assertEqual(result['status'],'success')

if __name__=='__main__':unittest.main()
