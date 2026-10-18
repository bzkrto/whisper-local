import json, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from whisper.learning.improvement_engine import ImprovementEngine

class ImprovementTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'whisper').mkdir();(self.root/'tests').mkdir()
        self.live=self.root/'whisper'/'small.py';self.live.write_text('def value():\n    return 1\n')
        (self.root/'tests'/'test_small.py').write_text('import unittest\n')
        self.engine=ImprovementEngine(self.root,self.root/'user.db')
        self.model=SimpleNamespace(base_url='http://localhost:11434/v1',chat=Mock())
    def tearDown(self):self.tmp.cleanup()
    def propose(self,path='whisper/small.py',content='def value():\n    return 2\n'):
        self.model.chat.return_value=json.dumps({'summary':'Taslak','changes':[{'path':path,'content':content}]})
        return self.engine.propose(self.model,'küçük işlevi iyileştir')
    def test_proposal_changes_only_copy_preserves_tests_and_marks_not_tested(self):
        result=self.propose();proposal=self.root/'iyilestirme_taslaklari'/result['proposal_id']
        self.assertIn('return 1',self.live.read_text());self.assertIn('return 2',(proposal/'whisper/small.py').read_text())
        self.assertEqual((proposal/'tests/test_small.py').read_text(),'import unittest\n')
        manifest=json.loads((proposal/'manifest.json').read_text())
        self.assertEqual(manifest['test_status'],'not_run');self.assertFalse(manifest['live_code_changed'])
    def test_traversal_and_test_modification_rejected_without_staging(self):
        for name in ('../small.py','tests/test_small.py','whisper_core.py'):
            with self.assertRaises(ValueError):self.propose(path=name)
        self.assertFalse((self.root/'iyilestirme_taslaklari').exists())
    def test_invalid_generated_python_never_written(self):
        with self.assertRaises(SyntaxError):self.propose(content='def invalid(:')
        self.assertIn('return 1',self.live.read_text())
    def test_missing_docker_reports_not_run(self):
        result=self.propose()
        with patch('whisper.learning.improvement_engine.shutil.which',return_value=None):
            tested=self.engine.test(result['proposal_id'])
        self.assertEqual(tested['status'],'blocked')
    def test_tampered_snapshot_prevents_any_container_execution(self):
        result=self.propose();proposal=self.root/'iyilestirme_taslaklari'/result['proposal_id']
        (proposal/'tests/test_small.py').write_text('tampered')
        with patch('whisper.learning.improvement_engine.subprocess.run') as run, self.assertRaises(ValueError):
            self.engine.test(result['proposal_id'])
        run.assert_not_called()
    def test_container_uses_no_network_no_pull_readonly_and_never_promotes(self):
        result=self.propose()
        with patch('whisper.learning.improvement_engine.shutil.which',return_value='/docker'), \
             patch('whisper.learning.improvement_engine.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='Ran 3 tests in 0.1s\nOK\n',stderr='')) as run:
            tested=self.engine.test(result['proposal_id'])
        command=run.call_args_list[0].args[0]
        self.assertIn('--network=none',command);self.assertIn('--pull=never',command)
        self.assertIn('--read-only',command);self.assertIn('readonly',' '.join(command))
        self.assertEqual(tested['status'],'success');self.assertIn('return 1',self.live.read_text())
        self.assertEqual(run.call_args_list[-1].args[0][1:3],['rm','-f'])

    def test_review_includes_diff_and_detects_stale_live_file(self):
        result=self.propose()
        review=self.engine.review(result['proposal_id'])
        self.assertEqual(review['status'],'success')
        self.assertIn('-    return 1',Path(review['artifacts'][0]['path']).read_text())
        self.assertIn('+    return 2',Path(review['artifacts'][0]['path']).read_text())
        self.live.write_text('def value():\n    return 3\n')
        self.assertEqual(self.engine.review(result['proposal_id'])['status'],'blocked')

    def test_candidate_preserves_report_assets_and_bootstrap(self):
        folder=self.root/'whisper/tools/assets';folder.mkdir(parents=True)
        (folder/'blank_presentation.pptx').write_bytes(b'fixture')
        (self.root/'whisper_bootstrap.py').write_text('pass\n')
        result=self.propose()
        staged=self.root/'iyilestirme_taslaklari'/result['proposal_id']
        self.assertEqual((staged/'whisper/tools/assets/blank_presentation.pptx').read_bytes(),b'fixture')
        self.assertTrue((staged/'whisper_bootstrap.py').is_file())

    def test_package_requires_passed_test_and_preserves_live_code(self):
        import hashlib,zipfile
        version={'version':'test','files':{'whisper/small.py':hashlib.sha256(self.live.read_bytes()).hexdigest()}}
        (self.root/'WHISPER_SURUM.json').write_text(json.dumps(version))
        result=self.propose()
        self.assertEqual(self.engine.package(result['proposal_id'])['status'],'blocked')
        with patch('whisper.learning.improvement_engine.shutil.which',return_value='/docker'), \
             patch('whisper.learning.improvement_engine.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='Ran 3 tests in 0.1s\nOK\n',stderr='')):
            self.engine.test(result['proposal_id'])
        packaged=self.engine.package(result['proposal_id'])
        self.assertEqual(packaged['status'],'success')
        self.assertIn('return 1',self.live.read_text())
        with zipfile.ZipFile(packaged['artifacts'][0]['path']) as z:
            self.assertIn('return 2',z.read('whisper/small.py').decode())
            new=json.loads(z.read('WHISPER_SURUM.json'))
            self.assertEqual(new['files']['whisper/small.py'],hashlib.sha256(z.read('whisper/small.py')).hexdigest())

    def test_edited_live_source_prevents_packaging(self):
        import hashlib
        (self.root/'WHISPER_SURUM.json').write_text(json.dumps({'version':'test','files':{
            'whisper/small.py':hashlib.sha256(self.live.read_bytes()).hexdigest()}}))
        result=self.propose()
        with patch('whisper.learning.improvement_engine.shutil.which',return_value='/docker'), \
             patch('whisper.learning.improvement_engine.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='Ran 3 tests in 0.1s\nOK\n',stderr='')):
            self.engine.test(result['proposal_id'])
        self.live.write_text('def value():\n    return 7\n')
        self.assertEqual(self.engine.package(result['proposal_id'])['status'],'blocked')

if __name__=='__main__':unittest.main()
