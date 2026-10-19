"""User-reported dialogue with a real native adapter and hostile plan fixtures."""
import copy
import io
import json
import unittest
from unittest.mock import Mock,patch
import test_pipeline_regression as pipeline
core=pipeline.core


class TurnRoutingTests(unittest.TestCase):
    def setUp(self):
        self.fixture=pipeline.Tests();self.fixture.setUp();self.addCleanup(self.fixture.tmp.cleanup)
        self.brain=self.fixture.brain;self.brain.cfg.tools_enabled=True
        self.brain.llm=core.OllamaLLM('http://127.0.0.1:11434/v1','qwen3:8b')
        self.payloads=[];self.invalid=False;self.planned_tools=[]
        self.reply='Konuyu birlikte ele alabiliriz; hangi yönünü merak ediyorsun?'
        def post(url,**kw):
            payload=copy.deepcopy(kw['json']);self.payloads.append(payload)
            if 'format' in payload:
                data=json.loads(payload['messages'][-1]['content']);pending=data.get('pending_clarification')
                if self.invalid:
                    plan={'kind':'chat','message':'Sohbet','steps':[{'tool':'research','args':{'query':'siber güvenlik'}}]}
                elif self.planned_tools:
                    plan={'kind':'action','message':'','steps':self.planned_tools}
                elif pending:
                    plan={'kind':'action','message':'','steps':[{'tool':'research','args':{'query':data['current_request']}}]}
                else:plan={'kind':'clarification','message':'Hangi konuyu araştırmamı istiyorsun?','steps':[]}
                content=json.dumps({'intent':'research','entities':[],'missing_fields':[],**plan})
            else:content=self.reply
            response=Mock(status_code=200)
            response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
            response.json.return_value={'message':{'content':content},'done':True}
            return response
        for item in (patch.object(core.requests,'post',side_effect=post),patch.object(self.brain,'_select_role_model'),patch('sys.stdout',new=io.StringIO())):
            item.start();self.addCleanup(item.stop)
        self.brain.voice.speak=Mock(return_value=True)

    def ask(self,text):return self.brain.process_command(text)

    def test_bare_topic_is_dialogue_not_permission_to_research(self):
        self.invalid=True
        with patch.object(self.brain,'_agent_tool') as execute:
            result=self.ask('siber güvenlik')
        self.assertEqual(result['status'],'success')
        self.assertEqual(result['response'],self.reply)
        self.assertTrue(self.payloads);self.assertNotIn('format',self.payloads[-1])
        execute.assert_not_called()

    def test_greeting_abandons_unrelated_pending_research_before_topic(self):
        self.brain.agent.ask_followup('Araştır','Hangi konuyu araştırayım?')
        with patch.object(self.brain,'_agent_tool') as execute:
            first=self.ask('nasılsın')
            second=self.ask('siber güvenlik')
        self.assertEqual(first['response'],self.reply)
        self.assertEqual(second['response'],self.reply)
        self.assertIsNone(self.brain.agent.dialogue.get())
        self.assertFalse(self.brain.agent.awaiting)
        self.assertFalse(any('format' in p for p in self.payloads));execute.assert_not_called()

    def test_unrecognized_smalltalk_does_not_default_to_tool_planning(self):
        self.invalid=True
        with patch.object(self.brain,'_agent_tool') as execute:
            result=self.ask('nasilssin')
        self.assertEqual(result['response'],self.reply)
        self.assertFalse(any('format' in p for p in self.payloads));execute.assert_not_called()

    def test_expired_clarification_cannot_capture_new_topic(self):
        now=[0.0];self.brain.agent.dialogue.clock=lambda:now[0]
        self.brain.agent.ask_followup('Araştır','Hangi konu?');now[0]=181
        self.invalid=True
        result=self.ask('siber güvenlik')
        self.assertEqual(result['response'],self.reply)
        self.assertFalse(any('format' in p for p in self.payloads))
        self.assertFalse(self.brain.agent.awaiting)

    def test_explicit_research_then_short_topic_still_uses_validated_agent(self):
        with patch.object(self.brain,'_agent_tool',return_value={'status':'success','response':'Kaynaklı araştırma kaydedildi.'}) as execute:
            self.assertEqual(self.ask('Bir konuyu araştır')['status'],'clarification')
            self.assertEqual(self.ask('siber güvenlik')['status'],'success')
        execute.assert_called_once_with('research',{'query':'siber güvenlik'})
        request=json.loads(self.payloads[-1]['messages'][-1]['content'])
        self.assertEqual(request['pending_clarification']['request'],'Bir konuyu araştır')

    def test_mixed_greeting_actions_keep_whole_plan_validation(self):
        self.planned_tools=[{'tool':'open_app','args':{'name':'chrome'}},{'tool':'set_volume','args':{'level':50}}]
        with patch.object(self.brain.tool_runner,'available_apps',return_value=['chrome']),patch.object(self.brain,'_agent_tool',return_value={'status':'dispatched','response':'İstek gönderildi.'}) as execute:
            self.assertEqual(self.ask('Nasılsın, Chrome aç ve sesi yüzde 50 yap')['status'],'success')
        self.assertEqual([c.args[0] for c in execute.call_args_list],['open_app','set_volume'])

    def test_inconsistent_plan_is_rejected_without_silently_dropping_steps(self):
        self.invalid=True
        with patch.object(self.brain,'_agent_tool') as execute:
            self.assertEqual(self.ask('Bir konuyu araştır')['status'],'error')
        execute.assert_not_called()
        self.assertEqual(sum('format' in p for p in self.payloads),2)

    def test_twenty_turn_open_topic_dialogue_stays_out_of_action_schema(self):
        self.invalid=True
        turns=['nasılsın','siber güvenlik','uygulama güvenliği','giriş doğrulaması','tehdit modeli',
               'savunma','loglar','günlük kayıtları','yedekleme','mantıksal tutarlılık',
               'çelişki','öncül ve sonuç','bağlam','biraz daha ayrıntı','hayır onu kastetmedim',
               'aynı konu','daha kısa','örnek üzerinden','önceki konuya dönelim','özetle']
        with patch.object(self.brain,'_agent_tool') as execute:
            for turn,text in enumerate(turns,1):
                with self.subTest(turn=turn):
                    self.assertEqual(self.ask(text)['status'],'success')
                    self.assertEqual(self.payloads[-1]['messages'][-1],{'role':'user','content':text})
                    self.assertNotIn('format',self.payloads[-1])
        execute.assert_not_called()
        self.assertTrue(any(m['role']=='assistant' for m in self.payloads[-1]['messages']))

    def test_clock_remains_a_deterministic_tool_not_model_guess(self):
        result=self.ask('Saat kaç?')
        self.assertTrue(result['fast']);self.assertEqual(self.payloads,[])

    def test_typo_greeting_also_exits_pending_research_without_rewriting_it(self):
        self.brain.agent.ask_followup('Araştır','Hangi konuyu araştırayım?')
        result=self.ask('nasilssin')
        self.assertEqual(result['response'],self.reply)
        self.assertEqual(self.payloads[-1]['messages'][-1]['content'],'nasilssin')
        self.assertNotIn('format',self.payloads[-1])
        self.assertIsNone(self.brain.agent.dialogue.get())

    def test_bare_topic_with_existing_cards_does_not_force_structured_answer(self):
        cards=[{'source_id':7,'summary':'Siber güvenlikte kaynaklı günlük analizi.'}]
        with patch.object(self.brain.knowledge_processor,'recall',return_value=cards),patch.object(self.brain.knowledge_processor,'answer') as answer:
            self.assertEqual(self.ask('siber güvenlik')['response'],self.reply)
        answer.assert_not_called()
        self.assertFalse(any('format' in p for p in self.payloads))

    def test_blocked_docker_job_is_explained_by_status(self):
        job=self.brain.self_development.enqueue('Giriş doğrulama modülünü incele')
        with self.brain.self_development.connect() as db:
            db.execute("UPDATE self_development_jobs SET state='blocked',detail='Docker test imajı yok; testler çalıştırılmadı.' WHERE id=?",(job,))
        result=self.ask('Araştırma yapıyor musun?')
        self.assertIn('Docker test imajı yok',result['response'])
        self.assertEqual(result['research_status']['code']['blocked'],1)
        self.assertEqual(self.payloads,[])

    def test_profile_interview_cannot_capture_greeting_and_next_topic(self):
        self.brain.profile_interview.next_question()
        self.assertIsNotNone(self.brain.profile_interview.pending)
        self.assertEqual(self.ask('nasılsın')['response'],self.reply)
        self.assertEqual(self.ask('siber güvenlik')['response'],self.reply)
        self.assertIsNone(self.brain.profile_interview.pending)
        self.assertEqual(self.brain.profile_interview.context(),'')
