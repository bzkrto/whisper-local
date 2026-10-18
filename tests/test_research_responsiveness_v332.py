"""Status queries and background work must not monopolize written dialogue."""
import copy
import io
import json
import threading
import unittest
from unittest.mock import Mock,patch
import test_pipeline_regression as pipeline
core=pipeline.core


class ResponsivenessTests(unittest.TestCase):
    def setUp(self):
        self.fixture=pipeline.Tests();self.fixture.setUp();self.addCleanup(self.fixture.tmp.cleanup)
        self.brain=self.fixture.brain;self.brain.voice.speak=Mock(return_value=True)
        self.brain.llm.base_url='http://127.0.0.1:11434/v1'
        self.brain.cfg.tools_enabled=True
        self.brain._command_queue_timeout=.02
        self.output=patch('sys.stdout',new=io.StringIO());self.output.start();self.addCleanup(self.output.stop)

    def test_research_question_reads_truthful_status_without_model_planning(self):
        self.brain.autonomous_research.enable(False)
        with patch.object(self.brain,'_select_role_model') as select,patch.object(self.brain.agent,'execute') as planner:
            result=self.brain.process_command('Araştırma yapıyor musun?')
        self.assertEqual(result['status'],'success')
        self.assertFalse(result['research_status']['enabled'])
        self.assertIn('kapalı',result['response'])
        select.assert_not_called();planner.assert_not_called();self.brain.llm.chat.assert_not_called()

    def test_status_is_available_while_background_model_lock_is_held(self):
        self.brain._command_lock.acquire()
        try:
            with patch.object(self.brain,'_select_role_model') as select:
                result=self.brain.process_command('Araştırma ne durumda?')
            self.assertEqual(result['status'],'success')
            self.assertTrue(self.brain._command_lock.locked())
            select.assert_not_called();self.brain.llm.chat.assert_not_called()
        finally:self.brain._command_lock.release()

    def test_status_counts_real_cards_and_drafts_without_claiming_code_changed(self):
        body='A useful original source passage for verification. '*10
        sid=self.brain.research_memory.capture('Türkçe bağlam',body,[{'url':'https://docs.ollama.com/'}],'autonomous_document')
        self.brain.knowledge_processor.sync()
        with self.brain.knowledge_processor.connect() as db:
            db.execute("UPDATE knowledge_chunks SET state='done',card='{}' WHERE source_id=?",(sid,))
            db.execute("INSERT INTO development_jobs(source_id,part,state,proposal) VALUES(?,0,'draft','{}')",(sid,))
        result=self.brain.process_command('Ne araştırıyorsun?')
        snapshot=result['research_status']
        self.assertEqual(snapshot['knowledge']['done'],1)
        self.assertEqual(snapshot['drafts']['draft'],1)
        self.assertEqual(snapshot['code'].get('active',0),0)
        self.assertIn('uygulanmış kod değişikliği: 0',result['response'])

    def test_empty_code_queue_does_not_select_or_unload_models(self):
        with patch.object(self.brain,'_select_role_model') as select,patch.object(self.brain.self_development,'tick') as tick:
            self.assertIsNone(self.brain._develop_code_idle())
        select.assert_not_called();tick.assert_not_called()
        self.assertFalse(self.brain._command_lock.locked())

    def test_waiting_foreground_blocks_starting_code_work(self):
        self.brain.self_development.enqueue('Bağlam aktarımını test et')
        self.brain._foreground_waiting.set()
        with patch.object(self.brain,'_select_role_model') as select:
            self.assertIsNone(self.brain._develop_code_idle())
        select.assert_not_called()

    def test_streamed_background_card_yields_to_written_greeting(self):
        self.brain._command_queue_timeout=2
        model=core.OllamaLLM('http://127.0.0.1:11434/v1','qwen3:8b')
        self.brain.llm=model
        body='A useful original source passage for verification. '*10
        sid=self.brain.research_memory.capture('Türkçe bağlam',body,[{'url':'https://docs.ollama.com/'}],'autonomous_document')
        ready=threading.Event();payloads=[];outcomes=[]
        response=Mock(status_code=200)
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        def chunks():
            yield b'{"message":{"content":"{\\\"summary\\\":\\\""},"done":false}'
            ready.set()
            if not self.brain._foreground_waiting.wait(2):raise AssertionError('Foreground never arrived')
            yield b'{"message":{"content":"unfinished"},"done":false}'
            yield b'{"done":true}'
        response.iter_lines.side_effect=lambda **kw:chunks()
        done=Mock(status_code=200)
        done.__enter__=Mock(return_value=done);done.__exit__=Mock(return_value=False)
        done.json.return_value={'message':{'content':'İyiyim, sen nasılsın?'},'done':True}
        def post(url,**kw):
            payloads.append(copy.deepcopy(kw['json']))
            return response if len(payloads)==1 else done
        with patch.object(core.requests,'post',side_effect=post),patch.object(self.brain,'_select_role_model'),patch.object(self.brain.agent,'execute') as planner:
            thread=threading.Thread(target=lambda:outcomes.append(self.brain._process_knowledge_idle()))
            thread.start()
            try:
                self.assertTrue(ready.wait(2))
                result=self.brain.process_command('Nasılsın?')
            finally:
                self.brain._foreground_waiting.set();thread.join(3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(result['status'],'success')
            planner.assert_not_called()
        self.assertTrue(payloads[0]['stream']);self.assertFalse(payloads[-1]['stream'])
        response.__exit__.assert_called_once()
        with self.brain.knowledge_processor.connect() as db:
            self.assertEqual(db.execute('SELECT state FROM knowledge_chunks WHERE source_id=?',(sid,)).fetchone()[0],'pending')
        self.assertEqual(outcomes[0]['status'],'cancelled')

    def test_status_grammar_does_not_swallow_actions_or_external_questions(self):
        from whisper.core.research_status import status_question
        for text in ('Araştırma yapıyor musun?','Şu an ne araştırıyorsun?','Araştırıyor musun?',
                     'Kendi kodunu geliştiriyor musun?','Whisper, araştırma ne durumda?'):
            self.assertTrue(status_question(text),text)
        for text in ('Araştırma yapıyor musun, Chrome aç','Ne araştırıyorsun ve sesi kıs',
                     'İnternette araştırma yap','Nasılsın?','Araştırmaya devam et','Araştırma nedir?'):
            self.assertFalse(status_question(text),text)

    def test_code_preflight_handles_due_disabled_and_restart_states(self):
        scheduler=self.brain.self_development;scheduler.clock=lambda:100
        self.assertFalse(scheduler.ready())
        job=scheduler.enqueue('Bağlam davranışını incele')
        self.assertTrue(scheduler.ready())
        scheduler.enable(False);self.assertFalse(scheduler.ready());scheduler.enable(True)
        with scheduler.connect() as db:
            db.execute("UPDATE self_development_settings SET value='101' WHERE key='next_run'")
        self.assertFalse(scheduler.ready())
        scheduler.clock=lambda:102
        self.assertTrue(scheduler.ready())
        with scheduler.connect() as db:
            db.execute("UPDATE self_development_jobs SET state='restart_required' WHERE id=?",(job,))
        self.assertFalse(scheduler.ready())

    def test_real_queued_job_still_selects_code_model(self):
        self.brain.self_development.enqueue('Türkçe bağlam için kabul testi yaz')
        outcome={'status':'no_change','response':'Gerekli değişiklik bulunmadı.'}
        with patch.object(self.brain,'_select_role_model') as select,patch.object(self.brain.self_development,'tick',return_value=outcome):
            self.assertEqual(self.brain._develop_code_idle(),outcome)
        select.assert_called_once_with('code')
        self.assertFalse(self.brain._command_lock.locked())
        self.assertEqual(self.brain._background_phase,'')

    def test_interrupted_code_proposal_is_retryable_without_using_an_attempt(self):
        scheduler=self.brain.self_development
        scheduler.enqueue('Kaynaklı bağlam düzeltmesi hazırla');scheduler.engine=Mock()
        scheduler.engine.propose.side_effect=InterruptedError('Ön plan bekliyor')
        self.assertEqual(scheduler.tick(self.brain.llm)['status'],'cancelled')
        with scheduler.connect() as db:
            self.assertEqual(db.execute('SELECT state,attempts FROM self_development_jobs').fetchone(),('pending',0))
        scheduler.engine.test.assert_not_called();scheduler.engine.apply.assert_not_called()

    def test_background_native_json_keeps_schema_and_requires_complete_output(self):
        from whisper.core.background import background_inference
        model=core.OllamaLLM('http://127.0.0.1:11434/v1','qwen3:8b');self.brain.llm=model
        schema={'type':'object','properties':{'value':{'type':'string'}},'required':['value'],'additionalProperties':False}
        response=Mock(status_code=200)
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.iter_lines.return_value=[json.dumps({'message':{'content':'{"value":"ok"}'},'done':False}).encode(),b'{"done":true}']
        with patch.object(core.requests,'post',return_value=response) as post,background_inference(self.brain,'proposal',threading.Event()):
            self.assertEqual(model.chat_json('schema','source',schema),'{'+'"value":"ok"'+'}')
        self.assertEqual(post.call_args.kwargs['json']['format'],schema)
        self.assertTrue(post.call_args.kwargs['stream'])
        self.assertEqual(post.call_args.kwargs['timeout'],(3,8))
        self.assertIsNone(model._background_cancel)
        response.iter_lines.return_value=[b'{"message":{"content":"partial"},"done":false}']
        with patch.object(core.requests,'post',return_value=response),background_inference(self.brain,'knowledge',threading.Event()):
            with self.assertRaises(core.LLMError):model.chat('s','u')

    def test_timeout_is_retryable_and_does_not_leave_model_in_background_mode(self):
        class TestTimeout(Exception):pass
        model=core.OllamaLLM('http://127.0.0.1:11434/v1','qwen3:8b');self.brain.llm=model
        sid=self.brain.research_memory.capture('Bağlam','Original source words for a grounded card. '*20,[{'url':'https://docs.ollama.com/'}],'autonomous_document')
        with patch.object(core.requests,'Timeout',TestTimeout),patch.object(core.requests,'post',side_effect=TestTimeout('stalled')),patch.object(self.brain,'_select_role_model'):
            outcome=self.brain._process_knowledge_idle()
        self.assertEqual(outcome['status'],'cancelled')
        with self.brain.knowledge_processor.connect() as db:
            self.assertEqual(db.execute('SELECT state,due FROM knowledge_chunks WHERE source_id=?',(sid,)).fetchone(),('pending',0))
        self.assertIsNone(model._background_cancel)
        self.assertFalse(self.brain._command_lock.locked())

    def test_greeting_uses_contextual_model_reply_instead_of_fixed_map(self):
        self.brain.llm.chat.return_value='Biraz önce konuştuğumuz konuya devam edebiliriz.'
        with patch.object(self.brain,'_select_role_model'),patch.object(self.brain.agent,'execute') as planner:
            result=self.brain.process_command('Nasılsın?')
        self.assertEqual(result['response'],'Biraz önce konuştuğumuz konuya devam edebiliriz.')
        self.brain.llm.chat.assert_called_once();planner.assert_not_called()
