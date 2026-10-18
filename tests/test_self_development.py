import hashlib
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from whisper.learning.improvement_engine import ImprovementEngine
from whisper.learning.self_development import SelfDevelopment


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); (self.root/'whisper').mkdir(); (self.root/'tests').mkdir()
        self.source=self.root/'whisper/word.py'; self.source.write_text('def word():\n    return "eski"\n')
        (self.root/'tests/test_word.py').write_text('import unittest\n')
        (self.root/'personal.db').write_bytes(b'preserve personal data')
        version={'version':'fixture','files':{'whisper/word.py':self.digest(self.source)}}
        (self.root/'WHISPER_SURUM.json').write_text(json.dumps(version))
        self.engine=ImprovementEngine(self.root,self.root/'personal.db')
        self.model=SimpleNamespace(base_url='http://localhost:11434/v1',chat=Mock(return_value=json.dumps({
            'summary':'Düzeltme','changes':[{'path':'whisper/word.py','content':'def word():\n    return "yeni"\n'}]})))
        self.pid=self.engine.propose(self.model,'Kelime modülünü iyileştir')['proposal_id']

    @staticmethod
    def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

    def passed(self, transcript='Ran 4 tests in 0.2s\nOK\n'):
        with patch('whisper.learning.improvement_engine.shutil.which',return_value='/docker'), patch(
                'whisper.learning.improvement_engine.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='',stderr=transcript)):
            return self.engine.test(self.pid)

    def test_apply_requires_real_nonzero_test_receipt(self):
        self.assertEqual(self.engine.apply(self.pid)['status'],'blocked')
        self.assertEqual(self.passed('Ran 0 tests in 0.0s\nOK\n')['status'],'error')
        self.assertEqual(self.engine.apply(self.pid)['status'],'blocked')
        self.assertEqual(self.passed('OK\n')['status'],'error')

    def test_passed_code_updates_manifest_and_preserves_database_and_backup(self):
        old=self.source.read_bytes(); self.assertEqual(self.passed()['status'],'success')
        result=self.engine.apply(self.pid)
        self.assertTrue(result['live_code_changed']); self.assertTrue(result['restart_required'])
        self.assertIn('yeni',self.source.read_text())
        version=json.loads((self.root/'WHISPER_SURUM.json').read_text())
        self.assertEqual(version['files']['whisper/word.py'],self.digest(self.source))
        self.assertEqual((Path(result['backup_path'])/'whisper/word.py').read_bytes(),old)
        self.assertEqual((self.root/'personal.db').read_bytes(),b'preserve personal data')
        self.assertFalse((self.root/'.whisper-update.lock').exists())

    def test_changed_trusted_test_blocks_promotion(self):
        self.passed(); (self.root/'tests/test_word.py').write_text('changed test')
        with self.assertRaises(ValueError): self.engine.apply(self.pid)
        self.assertIn('eski',self.source.read_text())

    def test_changed_candidate_blocks_promotion(self):
        self.passed()
        (self.root/'iyilestirme_taslaklari'/self.pid/'whisper/word.py').write_text('tampered')
        with self.assertRaises(ValueError): self.engine.apply(self.pid)

    def test_stale_live_code_never_overwritten(self):
        self.passed(); self.source.write_text('user edit')
        self.assertEqual(self.engine.apply(self.pid)['status'],'blocked')
        self.assertEqual(self.source.read_text(),'user edit')

    def test_failed_commit_rolls_back_code_and_manifest(self):
        self.passed(); original=self.source.read_bytes(); version=(self.root/'WHISPER_SURUM.json').read_bytes()
        replace=self.engine._replace; calls=[]
        def fail_once(path,data):
            calls.append(path)
            if len(calls)==2: raise OSError('simulated disk failure')
            return replace(path,data)
        with patch.object(self.engine,'_replace',side_effect=fail_once),self.assertRaises(OSError):
            self.engine.apply(self.pid)
        self.assertEqual(self.source.read_bytes(),original)
        self.assertEqual((self.root/'WHISPER_SURUM.json').read_bytes(),version)
        self.assertFalse((self.root/'.whisper-update.lock').exists())

    def test_cancellation_and_existing_lock_block_changes(self):
        self.passed(); event=threading.Event(); event.set()
        self.assertEqual(self.engine.apply(self.pid,event)['status'],'cancelled')
        (self.root/'.whisper-update.lock').write_text('other update')
        self.assertEqual(self.engine.apply(self.pid)['status'],'blocked')
        self.assertIn('eski',self.source.read_text())


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.scheduler=SelfDevelopment(self.root,self.root/'memory.db',clock=lambda:100)
        self.scheduler.engine=Mock()
        self.scheduler.engine.propose.return_value={'proposal_id':'123456789abc'}
        self.scheduler.engine.test.return_value={'status':'success','response':'tests passed'}
        self.scheduler.engine.apply.return_value={'status':'success','response':'applied','live_code_changed':True,'restart_required':True}
        self.model=SimpleNamespace(base_url='http://localhost:11434/v1')

    def test_complete_pipeline_runs_once_and_waits_for_restart(self):
        self.scheduler.enqueue('Türkçe kelime anlamayı geliştir',origin='source:1')
        self.scheduler.enqueue('Türkçe kelime anlamayı geliştir',origin='source:1')
        result=self.scheduler.tick(self.model)
        self.assertTrue(result['live_code_changed'])
        self.scheduler.engine.propose.assert_called_once()
        self.scheduler.engine.test.assert_called_once_with('123456789abc')
        self.scheduler.engine.apply.assert_called_once()
        self.assertIsNone(self.scheduler.tick(self.model))
        self.assertIn('restart_required',self.scheduler.report())
        self.scheduler.resumed(); self.assertIn('active',self.scheduler.report())

    def test_failed_or_blocked_tests_never_apply(self):
        self.scheduler.enqueue('Yanlış kelimeyi düzelt')
        self.scheduler.engine.test.return_value={'status':'error','response':'tests failed'}
        self.assertEqual(self.scheduler.tick(self.model)['status'],'error')
        self.scheduler.engine.apply.assert_not_called()
        self.assertIn('failed',self.scheduler.report())

    def test_disabled_and_remote_model_do_not_generate_code(self):
        self.scheduler.enqueue('Türkçe anlamayı geliştir'); self.scheduler.enable(False)
        self.assertIsNone(self.scheduler.tick(self.model))
        self.scheduler.enable(True)
        self.assertIsNone(self.scheduler.tick(SimpleNamespace(base_url='https://example.com')))
        self.scheduler.engine.propose.assert_not_called()

    def test_stop_during_test_prevents_apply(self):
        self.scheduler.enqueue('Türkçe anlamayı geliştir')
        def stop(_):
            self.scheduler.enable(False)
            return {'status':'success','response':'tests passed'}
        self.scheduler.engine.test.side_effect=stop
        self.assertEqual(self.scheduler.tick(self.model)['status'],'cancelled')
        self.scheduler.engine.apply.assert_not_called()

    def test_invalid_goal_is_not_queued(self):
        with self.assertRaises(ValueError): self.scheduler.enqueue('')

    def test_failed_tests_feed_next_attempt_and_stop_after_three(self):
        now=[100];self.scheduler.clock=lambda:now[0]
        self.scheduler.enqueue('Türkçe anlamayı geliştir')
        self.scheduler.engine.test.return_value={'status':'error','response':'expected i, got dotted i'}
        for _ in range(3):
            self.scheduler.tick(self.model);now[0]+=601
        self.assertIsNone(self.scheduler.tick(self.model))
        self.assertEqual(self.scheduler.engine.propose.call_count,3)
        self.assertIn('expected i, got dotted i',self.scheduler.engine.propose.call_args.args[1])
        self.scheduler.engine.apply.assert_not_called()


if __name__=='__main__': unittest.main()
