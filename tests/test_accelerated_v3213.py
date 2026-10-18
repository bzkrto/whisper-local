from contextlib import nullcontext
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
from whisper.learning import accelerated
from whisper.learning.priorities import FOCUS_TOPICS,track
from whisper.learning.autonomy import AutonomousResearch
from whisper.learning.knowledge import KnowledgeProcessor
from whisper.learning.improvement_engine import ImprovementEngine
from whisper.learning.self_development import SelfDevelopment
from whisper.memory.research_memory import ResearchMemory
import whisper_bootstrap
import test_pipeline_regression as pipeline
core=pipeline.core


class SourcePriorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'memory.db';self.memory=ResearchMemory(self.path)
        self.research=AutonomousResearch(self.memory,reader=Mock(return_value=dict(url='https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html',body='A useful original source passage for verification. '*10,links=[],partial=False)))
        self.research.set_profile('security');self.processor=KnowledgeProcessor(self.path)
        self.model=SimpleNamespace(base_url='http://localhost:11434/v1',chat=Mock(return_value=json.dumps(dict(summary='Giriş doğrulama ve günlük kaydı için kaynaklı teknik özet.',concepts=['güvenlik'],claims=[dict(text='Kaynaklı bir değerlendirme.',quote='A useful original source passage for verification.')],applications=[]))))

    def test_security_cards_are_a_development_track_and_official_seeds_are_accepted(self):
        self.assertEqual(track(FOCUS_TOPICS['security']),'security')
        self.assertEqual(track('Siber güvenlik günlük analizi'),'security')
        self.research.enqueue('https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html',FOCUS_TOPICS['security'])

    def test_new_security_source_is_not_stuck_after_500_older_chunks(self):
        body='A useful original source passage for verification. '*10
        for number in range(501):self.memory.capture('General source '+str(number),body,[{'url':'https://docs.python.org/'+str(number)}],'autonomous_document')
        wanted=self.memory.capture(FOCUS_TOPICS['security'],body,[{'url':'https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html'}],'autonomous_document')
        result=self.processor.tick(self.model)
        self.assertEqual(result['source_id'],wanted)
        self.assertEqual(result['status'],'processed')

    def test_unrelated_backlog_does_not_prevent_collecting_first_security_document(self):
        self.research.processing_backlog=lambda:314
        self.assertEqual(self.research.tick()['status'],'read')
        self.research.reader.assert_called_once()

    def test_security_backlog_still_prevents_unbounded_document_collection(self):
        self.research.processing_backlog=lambda:314
        body='A useful original source passage for verification. '*10
        for number in range(12):self.memory.capture('Cybersecurity '+str(number),body,[{'url':'https://docs.python.org/security'+str(number)}],'autonomous_document')
        self.processor.sync()
        self.assertEqual(self.research.tick()['status'],'processing_backlog')
        self.research.reader.assert_not_called()


class DevelopmentFlowTests(unittest.TestCase):
    def setUp(self):
        self.fixture=pipeline.Tests();self.fixture.setUp();self.addCleanup(self.fixture.tmp.cleanup)
        self.brain=self.fixture.brain
        self.session=accelerated.DevelopmentSession(self.brain,clock=lambda:100)

    def test_queued_code_runs_before_more_sources_and_restart_returns_immediately(self):
        outcome=dict(status='success',live_code_changed=True,restart_required=True)
        with patch.object(self.brain.self_development,'tick',return_value=outcome) as code,patch.object(self.brain.knowledge_processor,'tick') as knowledge,patch.object(self.brain.autonomous_research,'tick') as research:
            self.assertEqual(self.session.step(),outcome)
        knowledge.assert_not_called();research.assert_not_called()
        self.assertEqual(code.call_args.kwargs['interval'],60)
        self.assertEqual(self.session.updates,1)
        self.assertTrue(callable(code.call_args.kwargs['knowledge_provider']))

    def test_knowledge_continues_without_minute_delay_and_network_reads_are_paced(self):
        with patch.object(self.brain.self_development,'tick',return_value=None),patch.object(self.brain.knowledge_processor,'tick',return_value=dict(status='processed')) as knowledge,patch.object(self.brain.development_engine,'tick',return_value=None),patch.object(self.brain.autonomous_research,'tick',return_value=None) as research:
            self.session.step();self.session.step()
        self.assertEqual(knowledge.call_count,2);research.assert_called_once()
        self.assertEqual(self.session.processed,2)

    def test_cancelled_session_never_starts_another_model_call(self):
        self.session.stop.set()
        with patch.object(self.brain.self_development,'tick') as code:
            self.assertIsNone(self.session.step())
        code.assert_not_called()

    def test_single_model_memory_profile_limits_batch_threads_and_idle_residency(self):
        model=core.OllamaLLM('http://127.0.0.1:11434/v1','qwen2.5-coder:7b',context=6144)
        normal=model._payload('s','u',100,False)
        self.assertNotIn('num_batch',normal['options']);self.assertNotIn('keep_alive',normal)
        model.low_memory=True;payload=model._payload('s','u',100,False)
        self.assertEqual(payload['options']['num_batch'],128)
        self.assertLessEqual(payload['options']['num_thread'],4)
        self.assertEqual(payload['keep_alive'],'30s');self.assertNotIn('num_gpu',payload['options'])

    def test_code_job_receives_relevant_cards_instead_of_last_conversation_context(self):
        scheduler=self.brain.self_development;scheduler.engine=Mock()
        scheduler.engine.propose.return_value={'proposal_id':'123456789abc'}
        scheduler.engine.test.return_value={'status':'blocked','response':'test unavailable'}
        scheduler.enqueue('Giriş doğrulama davranışını geliştir')
        cards=[dict(source_id=7,summary='Kaynaklı güvenli giriş doğrulama özeti.')]
        provider=Mock(return_value=cards)
        scheduler.tick(SimpleNamespace(base_url='http://localhost:11434/v1'),knowledge_provider=provider,interval=60)
        provider.assert_called_once_with('Giriş doğrulama davranışını geliştir')
        self.assertEqual(scheduler.engine.propose.call_args.args[2],cards)
        scheduler.engine.apply.assert_not_called()

    def test_no_change_does_not_retry_forever_or_execute_tests(self):
        scheduler=self.brain.self_development;scheduler.engine=Mock()
        scheduler.engine.propose.return_value={'status':'no_change','response':'Hedef için değişiklik gerekmiyor.'}
        scheduler.enqueue('Kaynak kartına göre mevcut kodu incele')
        model=SimpleNamespace(base_url='http://localhost:11434/v1')
        self.assertEqual(scheduler.tick(model)['status'],'no_change')
        self.assertIsNone(scheduler.tick(model))
        scheduler.engine.propose.assert_called_once();scheduler.engine.test.assert_not_called();scheduler.engine.apply.assert_not_called()


class LaunchTests(unittest.TestCase):
    def test_missing_docker_blocks_before_any_model_call(self):
        with patch.object(accelerated.shutil,'which',return_value=None),patch.object(accelerated.subprocess,'run') as run:
            self.assertEqual(accelerated.test_environment('/tmp')['status'],'blocked')
        run.assert_not_called()

    def test_failed_image_build_is_reported_and_does_not_start_development(self):
        results=[SimpleNamespace(returncode=0,stdout='linux'),SimpleNamespace(returncode=1),SimpleNamespace(returncode=1)]
        with patch.object(accelerated.shutil,'which',return_value='docker'),patch.object(accelerated.subprocess,'run',side_effect=results) as run,patch('sys.stdout',new=io.StringIO()):
            self.assertEqual(accelerated.test_environment('/tmp',build=True)['status'],'blocked')
        self.assertEqual(run.call_count,3)

    def test_dedicated_launcher_skips_voice_setup_and_reverifies_after_update(self):
        with patch.object(whisper_bootstrap,'verify_package',return_value={'version':'fixture'}) as verify,patch.object(whisper_bootstrap.os,'chdir'),patch.object(accelerated,'session_lock',return_value=nullcontext()),patch.object(whisper_bootstrap.subprocess,'call',side_effect=[42,0]) as child,patch('whisper.voice.chatterbox_setup.ready',side_effect=AssertionError('voice must not load')),patch('sys.stdout',new=io.StringIO()):
            self.assertEqual(whisper_bootstrap.main(['--development']),0)
        self.assertEqual(verify.call_count,2);self.assertEqual(child.call_count,2)
        self.assertIn('whisper.learning.accelerated',child.call_args.args[0])

    def test_session_lock_rejects_second_instance_and_releases_on_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            with accelerated.session_lock(tmp):
                with self.assertRaisesRegex(RuntimeError,'zaten açık'):
                    with accelerated.session_lock(tmp):self.fail('duplicate session')
            with accelerated.session_lock(tmp):pass


class SourceSelectionTests(unittest.TestCase):
    def test_no_change_proposal_creates_no_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'whisper').mkdir();(root/'whisper/rule.py').write_text('def value():\n    return 1\n')
            model=SimpleNamespace(base_url='http://localhost:11434/v1',chat=Mock(return_value=json.dumps(dict(summary='Mevcut davranış yeterli.',changes=[]))))
            result=ImprovementEngine(root,root/'memory.db').propose(model,'Mevcut davranışı kontrol et')
            self.assertEqual(result['status'],'no_change')
            self.assertFalse((root/'iyilestirme_taslaklari').exists())

    def test_goal_named_module_is_selected_first_and_card_summary_reaches_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'whisper').mkdir();(root/'tests').mkdir()
            (root/'whisper/aaa.py').write_text('def value():\n    return 1\n')
            (root/'whisper/log_parser.py').write_text('def value():\n    return 1\n')
            model=SimpleNamespace(base_url='http://localhost:11434/v1',chat=Mock(return_value=json.dumps(dict(summary='Fix',changes=[dict(path='whisper/log_parser.py',content='def value():\n    return 2\n')]))))
            engine=ImprovementEngine(root,root/'memory.db')
            engine.propose(model,'Improve whisper/log_parser.py input validation',[dict(source_id=8,summary='Kaynaklı günlük ayrıştırma özeti.',claims=[])])
            payload=json.loads(model.chat.call_args.args[1])
            self.assertEqual(next(iter(payload['sources'])),'whisper/log_parser.py')
            self.assertEqual(payload['research_context'][0]['excerpt'],'Kaynaklı günlük ayrıştırma özeti.')
