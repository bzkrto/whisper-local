import json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock
from whisper.memory.research_memory import ResearchMemory
from whisper.learning.autonomy import AutonomousResearch
from whisper.learning.knowledge import KnowledgeProcessor
from whisper.learning.development import DevelopmentEngine
from whisper.learning.engine import LearningEngine
from whisper.learning.priorities import FOCUS_TOPICS,target,track

class FocusTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'memory.db';self.now=100000
        self.memory=ResearchMemory(self.path)
        self.reader=Mock(side_effect=lambda url,stop:dict(url=url,body='A useful original source passage for verification. '*20,partial=False,links=[]))
        self.worker=AutonomousResearch(self.memory,reader=self.reader,clock=lambda:self.now)
        self.processor=KnowledgeProcessor(self.path,clock=lambda:self.now)
        self.engine=DevelopmentEngine(self.path,clock=lambda:self.now)
        self.model=Mock();self.model.base_url='http://127.0.0.1:11434';self.model.model='qwen3:8b'
        self.stop=threading.Event()
    def card(self,title):
        sid=self.memory.capture(title,'A useful original source passage for verification. '*20,[{'url':'https://docs.ollama.com/capabilities/structured-outputs'}],'autonomous_document')
        self.processor.sync()
        card=dict(summary='Kaynaklı bilgi işleme ve bağlamı değerlendirme önerileri.',concepts=['bağlam'],claims=[dict(text='Kaynak değerlendirilir.',quote='A useful original source passage for verification.')],applications=[])
        with self.processor.connect() as db:db.execute("UPDATE knowledge_chunks SET state='done',card=?,processed_at=? WHERE source_id=?",(json.dumps(card),self.now,sid))
        return sid
    def test_migration_focus_once_preserves_disabled_and_later_choice(self):
        with self.worker.connect() as db:self.assertEqual(db.execute("SELECT value FROM autonomous_settings WHERE key='research_profile'").fetchone()[0],'development')
        self.worker.enable(False);self.worker.set_profile('security')
        new=AutonomousResearch(self.memory)
        self.assertFalse(new.enabled())
        with new.connect() as db:self.assertEqual(db.execute("SELECT value FROM autonomous_settings WHERE key='research_profile'").fetchone()[0],'security')
    def test_existing_install_migrates_without_deleting_topics(self):
        with self.worker.connect() as db:
            db.execute("DELETE FROM autonomous_settings WHERE key='v30_focus_migrated'")
            db.execute("UPDATE autonomous_settings SET value='balanced' WHERE key='research_profile'")
        self.worker.add_topic('Osmanın mevcut konusu')
        new=AutonomousResearch(self.memory)
        self.assertIn('Osmanın mevcut konusu',new.report());self.assertIn('development',new.report())
    def test_curriculum_proportions_and_classifications(self):
        self.assertEqual(sum(target(i)!='general' for i in range(10)),8)
        for category,title in FOCUS_TOPICS.items():self.assertEqual(track(title),category)
    def test_first_read_and_search_prioritize_context_over_old_queue(self):
        self.worker.search=Mock(return_value=[])
        result=self.worker.tick()
        self.assertEqual(result['status'],'read')
        self.assertIn('structured-outputs',result['url'])
        self.assertIn('intent detection',self.worker.search.call_args.args[0])
    def test_exploration_remains_available(self):
        with self.worker.connect() as db:db.execute("UPDATE autonomous_settings SET value='4' WHERE key='tick_number'")
        self.assertIn('tdk.gov.tr',self.worker.tick()['url'])
    def test_processing_prefers_context_over_older_general_source(self):
        self.memory.capture('Fizik', 'A useful original source passage for verification. '*20,[{'url':'https://docs.ollama.com/general'}],'autonomous_document')
        wanted=self.memory.capture(FOCUS_TOPICS['context'],'A useful original source passage for verification. '*21,[{'url':'https://docs.ollama.com/context'}],'autonomous_document')
        self.model.chat.return_value=json.dumps(dict(summary='Türkçe bağlam için yeterli uzunlukta kaynak özeti.',concepts=['bağlam'],claims=[dict(text='Kaynaklı bir değerlendirme.',quote='A useful original source passage for verification.')],applications=[]))
        self.assertEqual(self.processor.tick(self.model)['source_id'],wanted)
    def test_failure_schedules_generic_topic_once_without_private_query(self):
        learning=LearningEngine(self.path)
        learning.save('Özel telefon numaram 0555 gizli',[dict(tool='youtube_search',status='error',response='failure')],'error')
        self.assertEqual(self.engine.failures(self.worker),1)
        self.assertEqual(self.engine.failures(self.worker),0)
        self.assertNotIn('0555',self.worker.report())
        with self.worker.connect() as db:self.assertEqual(db.execute('SELECT next_search FROM autonomous_topics WHERE topic=?',(FOCUS_TOPICS['context'],)).fetchone()[0],0)
    def proposal(self):
        return dict(problem='Kısa yanıt bağlamını değerlendirmek gerekir.',change='Sanatçı cevabını bekleyen isteğe bağlamayı bir kabul testi ile incele.',acceptance_tests=[dict(input='Şarkı aç → Bergen',expected='Bergen sanatçısını bekleyen müzik isteğine bağlar.')],limitations=['Bu test henüz çalıştırılmadı; kaynak tek başına doğrulama değildir.'])
    def test_processed_card_generates_draft_once_not_applied(self):
        self.card(FOCUS_TOPICS['context']);self.model.chat.return_value=json.dumps(self.proposal())
        self.assertEqual(self.engine.tick(self.model,self.stop)['status'],'draft')
        self.now+=601
        self.assertIsNone(self.engine.tick(self.model,self.stop))
        self.model.chat.assert_called_once();self.assertIn('Taslaklar uygulanmadı',self.engine.report())
        self.assertIn('Bergen',self.engine.report())
    def test_general_card_does_not_consume_development_call(self):
        self.card('Tarih coğrafya');self.assertIsNone(self.engine.tick(self.model,self.stop));self.model.chat.assert_not_called()
    def test_cancel_after_generation_stores_no_draft(self):
        self.card(FOCUS_TOPICS['agent'])
        def answer(*a,**k):self.stop.set();return json.dumps(self.proposal())
        self.model.chat.side_effect=answer
        self.assertEqual(self.engine.tick(self.model,self.stop)['status'],'error')
        with self.engine.connect() as db:self.assertEqual(db.execute("SELECT count(*) FROM development_jobs WHERE state='draft'").fetchone()[0],0)
    def test_invalid_reply_retry_bounded_and_restart_keeps_backoff(self):
        self.card(FOCUS_TOPICS['memory']);self.model.chat.return_value='invalid'
        self.assertEqual(self.engine.tick(self.model,self.stop)['status'],'error')
        self.assertEqual(self.model.chat.call_count,2)
        self.now+=601
        self.assertIsNone(DevelopmentEngine(self.path,clock=lambda:self.now).tick(self.model,self.stop))
        self.assertEqual(self.model.chat.call_count,2)
    def test_focus_rejects_unofficial_and_redirected_sources(self):
        with self.assertRaises(ValueError):self.worker.enqueue('https://example.com/ai',FOCUS_TOPICS['agent'])
        self.reader.side_effect=lambda u,s:dict(url='https://example.com/copied-docs',body='text '*100,partial=False,links=[])
        result=self.worker.tick()
        self.assertEqual(result['status'],'error')
        self.assertIsNone(result['source_id'])

    def test_remote_model_not_used(self):
        self.card(FOCUS_TOPICS['context']);self.model.base_url='https://remote.example.com'
        self.assertIsNone(self.engine.tick(self.model,self.stop));self.model.chat.assert_not_called()

class PipelineTests(unittest.TestCase):
    def test_idle_processing_wires_development_and_yields_to_foreground(self):
        from test_pipeline_regression import core
        from types import SimpleNamespace
        from unittest.mock import patch
        worker=SimpleNamespace(stop_event=threading.Event())
        model=Mock();model.base_url='http://127.0.0.1:11434';model.model='qwen3:8b'
        brain=SimpleNamespace(_foreground_waiting=threading.Event(),_command_lock=threading.Lock(),llm=model,
            _select_role_model=Mock(),autonomous_research=worker,knowledge_processor=Mock(),development_engine=Mock())
        brain.knowledge_processor.tick.return_value={'status':'processed','source_id':1,'part':0}
        with patch('sys.stdout'):
            core.WhisperBrain._process_knowledge_idle(brain)
        brain.development_engine.failures.assert_called_once_with(worker)
        brain.development_engine.tick.assert_called_once_with(model,worker.stop_event)
        brain._foreground_waiting.set()
        core.WhisperBrain._process_knowledge_idle(brain)
        self.assertEqual(brain.development_engine.tick.call_count,1)
        self.assertFalse(brain._command_lock.locked())

    def test_status_and_profile_commands_reach_real_modules(self):
        from test_pipeline_regression import Tests
        fixture=Tests();fixture.setUp();self.addCleanup(fixture.tmp.cleanup);self.addCleanup(fixture.doCleanups)
        fixture.brain.llm.base_url='http://127.0.0.1:11434'
        response=fixture.ask('Gelişim durumu')
        self.assertIn('Taslaklar uygulanmadı',response['response'])
        response=fixture.ask('Araştırma profili: geliştirme')
        self.assertEqual(response['status'],'success')
        self.assertIn('development',fixture.brain.autonomous_research.report())

if __name__=='__main__':unittest.main()
