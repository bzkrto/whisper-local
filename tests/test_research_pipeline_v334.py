"""Research control and durable queue recovery without executing generated code."""
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import test_pipeline_regression as pipeline
from whisper.learning.self_development import SelfDevelopment
from whisper.core import research_status


class ResearchControlTests(unittest.TestCase):
    def setUp(self):
        fixture=pipeline.Tests();fixture.setUp();self.addCleanup(fixture.tmp.cleanup)
        self.brain=fixture.brain;self.brain.cfg.tools_enabled=True;self.brain.cfg.internet=True
        self.brain.voice.speak=Mock()

    def test_resume_bypasses_model_and_stale_clarification(self):
        b=self.brain;b.autonomous_research.enable(False)
        b.agent.ask_followup('Bir uygulama hazırla','Hangi uygulama?')
        with patch.object(b.agent,'execute',side_effect=AssertionError('model not needed')),patch.object(b.autonomous_research,'start') as start:
            result=b.process_command('araştırma yapmaya devam et')
        self.assertEqual(result['status'],'success');self.assertTrue(b.autonomous_research.enabled())
        start.assert_called_once();self.assertFalse(b.agent.awaiting)

    def test_resume_respects_internet_permission_and_keeps_pc_controls_separate(self):
        b=self.brain;b.cfg.internet=False;b.autonomous_research.enable(False)
        with patch.object(b.autonomous_research,'start') as start:
            result=b.process_command('araştırma yapmaya devam et')
        self.assertEqual(result['status'],'blocked');start.assert_not_called()
        self.assertFalse(b.autonomous_research.enabled())
        b.cfg.internet=True;b.cfg.tools_enabled=False
        with patch.object(b.autonomous_research,'start') as start:
            result=b.process_command('araştırma yapmaya devam et')
        self.assertEqual(result['status'],'success');start.assert_called_once()
        self.assertFalse(b.cfg.tools_enabled)

    def test_why_question_reports_backpressure_and_actual_error_without_model(self):
        b=self.brain
        for number in range(12):
            sid=b.research_memory.capture('Python bağlam yönetimi '+str(number),'kaynak '*200,[{'url':'https://docs.python.org/3/'+str(number)}],'autonomous_document')
        b.knowledge_processor.sync()
        with b.knowledge_processor.connect() as db:
            db.execute("UPDATE knowledge_chunks SET state='error',error='Alıntı kaynakta bulunamadı' WHERE source_id=? AND part=0",(sid,))
        with patch.object(b.agent,'execute',side_effect=AssertionError('read only')):
            result=b.process_command('neden araştırma yapmıyorsun')
        self.assertEqual(result['status'],'success')
        self.assertTrue(result['research_status']['collection_waiting_for_processing'])
        self.assertIn('birikmiş',result['response']);self.assertIn('Alıntı kaynakta bulunamadı',result['response'])

    def test_security_profile_does_not_claim_pause_for_unrelated_backlog(self):
        b=self.brain;b.autonomous_research.set_profile('security')
        for number in range(12):
            b.research_memory.capture('Genel konu '+str(number),'kaynak '*200,[{'url':'https://docs.python.org/3/'+str(number)}],'autonomous_document')
        b.knowledge_processor.sync()
        self.assertFalse(research_status.snapshot(b)['collection_waiting_for_processing'])

    def test_control_parser_does_not_swallow_combined_actions_or_topics(self):
        for text in ('araştırma yapmaya devam et ve tarayıcıyı aç','Python araştırmaya devam et','araştırma nedir'):
            self.assertIsNone(research_status.control_request(text))

    def test_search_error_is_exposed_and_cleared_after_a_successful_search(self):
        b=self.brain;worker=b.autonomous_research
        with worker.connect() as db:
            db.execute("INSERT OR REPLACE INTO autonomous_settings VALUES('last_search_error','DDGSException')")
        self.assertIn('DDGSException',research_status.answer(b)['response'])
        worker.search=Mock(return_value=[])
        worker.reader=Mock(side_effect=ValueError('fixture read failure'))
        worker.tick()
        worker.search.assert_called_once()
        self.assertIsNone(research_status.snapshot(b)['last_search_error'])


class QueueRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.now=[100.0]
        self.worker=SelfDevelopment(Path(self.tmp.name),Path(self.tmp.name)/'queue.db',clock=lambda:self.now[0])
        self.worker.engine=Mock()
        self.worker.engine.propose.return_value={'proposal_id':'123456789abc'}
        self.worker.engine.test.return_value={'status':'blocked','response':'Docker eksik'}
        self.model=SimpleNamespace(base_url='http://localhost:11434/v1')

    def test_blocked_job_does_not_monopolize_later_pending_work(self):
        first=self.worker.enqueue('Birinci modülü incele');second=self.worker.enqueue('İkinci modülü incele')
        self.assertEqual(self.worker.tick(self.model)['job_id'],first)
        self.now[0]+=601
        self.assertEqual(self.worker.tick(self.model)['job_id'],second)
        self.worker.engine.apply.assert_not_called()

    def test_third_candidate_blocked_on_environment_can_resume_without_regeneration(self):
        jid=self.worker.enqueue('Bağlam modülünü incele')
        with self.worker.connect() as db:
            db.execute("UPDATE self_development_jobs SET attempts=3,state='blocked',proposal_id='123456789abc' WHERE id=?",(jid,))
        self.assertTrue(self.worker.ready())
        self.worker.engine.test.return_value={'status':'success','response':'Testler geçti'}
        self.worker.engine.apply.return_value={'status':'success','response':'uygulandı','live_code_changed':True}
        self.assertTrue(self.worker.tick(self.model)['live_code_changed'])
        self.worker.engine.propose.assert_not_called();self.worker.engine.test.assert_called_once_with('123456789abc')

    def test_three_failed_candidates_remain_exhausted(self):
        jid=self.worker.enqueue('Bağlam modülünü incele')
        with self.worker.connect() as db:
            db.execute("UPDATE self_development_jobs SET attempts=3,state='failed',proposal_id='123456789abc' WHERE id=?",(jid,))
        self.assertFalse(self.worker.ready());self.assertIsNone(self.worker.tick(self.model))
        self.worker.engine.test.assert_not_called()


class ContainerFailureTests(unittest.TestCase):
    def test_missing_image_is_environment_blocker_not_failed_code(self):
        from test_self_development import ApplyTests
        fixture=ApplyTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        failure=SimpleNamespace(returncode=125,stdout='',stderr='Unable to find image whisper-test:local locally')
        with patch('whisper.learning.improvement_engine.shutil.which',return_value='/docker'),patch('whisper.learning.improvement_engine.subprocess.run',return_value=failure):
            result=fixture.engine.test(fixture.pid)
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(fixture.engine.apply(fixture.pid)['status'],'blocked')


class SearchReceiptTests(unittest.TestCase):
    def test_background_adapter_preserves_search_failure_receipt(self):
        fixture=pipeline.Tests();fixture.setUp();self.addCleanup(fixture.tmp.cleanup)
        b=fixture.brain
        def failed_search(client,*args,**kwargs):
            client.last_sources=[];client.last_error='bing: DDGSException; duckduckgo: timeout'
            return 'Sonuç alınamadı'
        with patch.object(pipeline.core.WebSearch,'search',failed_search):
            with self.assertRaisesRegex(RuntimeError,'DDGSException'):
                b.autonomous_research.search('Python belge')
