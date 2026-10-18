import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import wave

import whisper_bootstrap
from whisper.voice import chatterbox_setup as setup
from whisper.voice import chatterbox_worker as worker
from whisper.voice.chatterbox_tts import ChatterboxTTS
from test_pipeline_regression import core


class SetupTests(unittest.TestCase):
    def test_cancelled_recording_selection_installs_nothing(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(setup,'voice_home',return_value=Path(tmp)), \
             patch.object(setup,'select_source',return_value=''), \
             patch.object(setup.venv,'EnvBuilder') as create,patch.object(setup.subprocess,'run') as install:
            self.assertEqual(setup.setup(),1)
        create.assert_not_called();install.assert_not_called()

    def test_repair_does_not_trust_existing_ready_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);py=setup.runtime_python(home);py.parent.mkdir(parents=True);py.touch()
            (home/'packages.ready').write_text(setup.RUNTIME_TAG)
            with patch.object(setup,'voice_home',return_value=home),patch.object(setup,'ready',return_value=True), \
                 patch.object(setup,'select_source',return_value='existing.wav'), \
                 patch.object(setup,'install_source'), \
                 patch.object(setup,'torch_index',return_value='https://download.pytorch.org/whl/cu128'), \
                 patch.object(setup.subprocess,'run',return_value=Mock(returncode=0)) as run:
                self.assertEqual(setup.setup(repair=True),0)
            self.assertIn('--prepare',run.call_args_list[-1].args[0])
            self.assertTrue(any('check' in call.args[0] for call in run.call_args_list))
            self.assertTrue(any('torch==2.8.0+cu128' in call.args[0] for call in run.call_args_list))

    def test_installation_lock_prevents_double_install_and_releases_after_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'cancel'):
                with setup.setup_lock(tmp):
                    with self.assertRaisesRegex(RuntimeError,'başka bir pencerede'):
                        with setup.setup_lock(tmp):self.fail('second install entered')
                    raise ValueError('cancel')
            with setup.setup_lock(tmp):pass

    def test_invalid_download_preserves_existing_file_and_removes_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'model.pt';target.write_bytes(b'previous')
            response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
            response.iter_content.return_value=[b'bad']
            with patch('requests.get',return_value=response),self.assertRaisesRegex(ValueError,'SHA256'):
                setup.fetch_file('https://example.invalid/model',target,3,'incorrect')
            self.assertEqual(target.read_bytes(),b'previous')
            self.assertEqual(list(Path(tmp).glob('*.part')),[])

    def test_reference_changes_invalidate_ready_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);py=setup.runtime_python(home);py.parent.mkdir(parents=True);py.touch()
            ref=home/'reference.wav'
            with wave.open(str(ref),'wb') as output:
                output.setparams((1,2,24000,0,'NONE','not compressed'));output.writeframes(b'\x01\x00'*24000*6)
            (home/'packages.ready').write_text(setup.RUNTIME_TAG)
            (home/'ready.json').write_text(json.dumps({'revision':setup.REVISION,'runtime':setup.RUNTIME_TAG,'reference_sha256':setup.digest(ref)}))
            cache=home/'cache'/'pkuseg';cache.mkdir(parents=True);(cache/'spacy_ontonotes.zip').touch()
            with patch.object(setup,'FILES',{}),patch.object(setup,'TOKENIZER_FILES',{}):
                self.assertTrue(setup.ready(home))
                data=ref.read_bytes();ref.write_bytes(data[:-2]+b'\x02\x00')
                self.assertFalse(setup.ready(home))

    def test_failed_default_setup_never_launches_app_or_reads_paid_key(self):
        with patch.object(whisper_bootstrap.sys,'platform','win32'), \
             patch.object(whisper_bootstrap.os,'chdir'), \
             patch.object(whisper_bootstrap.importlib.util,'find_spec',return_value=object()), \
             patch.object(setup,'ready',return_value=False), \
             patch('whisper.voice.elevenlabs_tts.load_key',side_effect=AssertionError('paid key accessed')), \
             patch.object(whisper_bootstrap.subprocess,'call',return_value=1) as launch, \
             patch('sys.stdout',new=io.StringIO()):
            self.assertEqual(whisper_bootstrap.main([]),1)
        launch.assert_called_once();self.assertIn('whisper.voice.chatterbox_setup',launch.call_args.args[0])


class DeviceTests(unittest.TestCase):
    def torch(self,available=True,free_mb=8000):
        return SimpleNamespace(cuda=SimpleNamespace(is_available=lambda:available,
                               mem_get_info=lambda:(free_mb*1024*1024,12000*1024*1024)))

    def test_cuda_selection_accounts_for_models_already_using_vram(self):
        self.assertEqual(worker.select_device(self.torch(), 'auto')[0],'cuda')
        device,reason=worker.select_device(self.torch(free_mb=3000),'auto')
        self.assertEqual(device,'cpu');self.assertIn('3000 MB',reason)
        self.assertEqual(worker.select_device(self.torch(available=False),'auto')[0],'cpu')
        with self.assertRaises(RuntimeError):worker.select_device(self.torch(available=False),'cuda')
        with self.assertRaises(ValueError):worker.select_device(self.torch(),'untrusted')

    def test_jobs_cannot_escape_output_directory_or_send_unbounded_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            text,path=worker.validate_job({'text':'Merhaba','output':str(root/'speech.wav')},root)
            self.assertEqual(text,'Merhaba');self.assertEqual(path,root/'speech.wav')
            for job in ({'text':'','output':str(path)}, {'text':'x'*1501,'output':str(path)},
                        {'text':'Merhaba','output':str(root.parent/'outside.wav')},[],
                        {'text':'Merhaba','output':str(root/'speech.mp3')}):
                with self.assertRaises(ValueError):worker.validate_job(job,root)


class AdapterTests(unittest.TestCase):
    def test_separate_worker_and_memory_cache_reuse_selected_voice(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(setup,'ready',return_value=True):
            engine=ChatterboxTTS(home=tmp);self.addCleanup(engine.close)
            process=Mock();process.poll.return_value=None
            process.stdout=iter([json.dumps({'type':'progress','message':'Loading model'}),
                                 json.dumps({'type':'ready','device':'cpu','reason':'test CPU'}),
                                 json.dumps({'type':'done','device':'cpu','seconds':1.5})])
            def write(line):
                path=json.loads(line)['output']
                with wave.open(path,'wb') as out:
                    out.setparams((1,2,24000,0,'NONE','not compressed'));out.writeframes(b'\x01\x00'*2400)
            process.stdin.write.side_effect=write
            engine._play=Mock(return_value=True)
            with patch('whisper.voice.reference_tts.subprocess.Popen',return_value=process) as launch, \
                 patch('sys.stdout',new=io.StringIO()):
                self.assertTrue(engine.speak('Merhaba Osman.'))
                self.assertTrue(engine.speak('Merhaba Osman.'))
            self.assertIn('whisper.voice.chatterbox_worker',launch.call_args.args[0])
            self.assertEqual(process.stdin.write.call_count,1)
            self.assertEqual(engine._play.call_count,2)
            self.assertFalse((Path(engine._directory.name)/'speech.wav').exists())
            # The mock stdout is an iterator rather than a real closable pipe.
            process.stdout=None

    def test_cancelled_warmup_does_not_start_or_leave_generation_flag_set(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(setup,'ready',return_value=True):
            engine=ChatterboxTTS(home=tmp);self.addCleanup(engine.close)
            stop=threading.Event();stop.set()
            with patch.object(engine,'_start') as start:
                self.assertFalse(engine.warmup(stop))
            start.assert_not_called();self.assertFalse(engine._generating.is_set())

    def test_stop_between_worker_start_and_submission_never_sends_text(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(setup,'ready',return_value=True):
            engine=ChatterboxTTS(home=tmp);self.addCleanup(engine.close)
            process=Mock();process.poll.return_value=None;engine._process=process
            with patch.object(engine,'_start',side_effect=engine.stop),patch('sys.stdout',new=io.StringIO()) as output:
                self.assertFalse(engine.speak('Bu cümle iptal edildi.'))
            process.stdin.write.assert_not_called()
            self.assertNotIn('AttributeError',output.getvalue())
            self.assertFalse(engine._cache)

    def test_local_selected_voice_needs_no_cloud_permission(self):
        cfg=core.parse_args(['--tts','chatterbox'])
        with patch('whisper.voice.chatterbox_tts.ChatterboxTTS') as voice, \
             patch.object(core,'EdgeTTS') as edge,patch.object(core,'SapiTTS') as sapi:
            self.assertIs(core.build_tts(cfg),voice.return_value)
        self.assertFalse(cfg.allow_cloud);edge.assert_not_called();sapi.assert_not_called()
