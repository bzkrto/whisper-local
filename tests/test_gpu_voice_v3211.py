import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
import zipfile
from whisper.voice import chatterbox_setup as setup
from test_pipeline_regression import core


class CompatibilityTests(unittest.TestCase):
    def test_modern_nvidia_driver_selects_blackwell_capable_cuda128(self):
        for driver,expected in [('576.52','cu128'),('560.94','cu126'),('550.1','cpu')]:
            with self.subTest(driver=driver),patch.object(setup.shutil,'which',return_value='nvidia-smi'), \
                 patch.object(setup.subprocess,'run',return_value=Mock(returncode=0,stdout=driver+'\n')):
                self.assertTrue(setup.torch_index().endswith('/'+expected))

    def test_source_patch_updates_dependency_metadata_without_changing_model_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            def archive(url,path,*args):
                path.parent.mkdir(parents=True,exist_ok=True)
                prefix='chatterbox-'+setup.SOURCE_REVISION+'/'
                with zipfile.ZipFile(path,'w') as z:
                    z.writestr(prefix+'pyproject.toml','version = "0.1.7"\n"torch==2.6.0; python_version < \'3.14\'"\n"torchaudio==2.6.0; python_version < \'3.14\'"\n')
                    z.writestr(prefix+'model.py','original model code')
            def install(args,**kwargs):
                source=Path(args[-1]);text=(source/'pyproject.toml').read_text()
                self.assertIn('torch==2.8.0;',text);self.assertIn('torchaudio==2.8.0;',text)
                self.assertIn('0.1.7+whisper.torch28',text)
                self.assertEqual((source/'model.py').read_text(),'original model code')
                self.assertIn('--no-deps',args)
            with patch.object(setup,'fetch_file',side_effect=archive),patch.object(setup.subprocess,'run',side_effect=install) as pip:
                setup.install_source('python',home)
            pip.assert_called_once()
            self.assertEqual(list((home/'cache').glob('source-*')),[])


class ResourceTests(unittest.TestCase):
    def test_ollama_cpu_request_is_explicit_and_does_not_change_normal_mode(self):
        model=core.OllamaLLM('http://127.0.0.1:11434/v1','qwen3:8b',gpu_layers=0)
        payload=model._payload('system','hello',120,True)
        self.assertEqual(payload['options']['num_gpu'],0)
        self.assertEqual(payload['options']['num_predict'],120)
        self.assertFalse(payload['think'])
        model.gpu_layers=None
        self.assertNotIn('num_gpu',model._payload('system','hello',120,True)['options'])

    def test_voice_warms_before_recognition_and_only_reserves_gpu_when_it_works(self):
        for device in ('cuda','cpu'):
            with self.subTest(device=device):
                events=[];llm=core.OllamaLLM('http://127.0.0.1:11434/v1','qwen3:8b',gpu_layers=0)
                llm.release_for_voice=lambda names:events.append('unload')
                engine=SimpleNamespace(device=device,warmup=lambda stop:(events.append('voice') or True))
                brain=SimpleNamespace(cfg=core.Config(voice_gpu_priority=True),llm=llm,stt=None,
                                      voice=SimpleNamespace(engine=engine,begin=lambda:None))
                def stt(cfg):events.append('stt');raise RuntimeError('stop before microphone')
                with patch.object(core,'build_stt',side_effect=stt),patch.object(core,'sd',Mock()),patch('sys.stdout',new=io.StringIO()):
                    with self.assertRaisesRegex(RuntimeError,'stop before microphone'):
                        core.WhisperBrain._start_voice_loop(brain,threading.Event())
                self.assertEqual(events,['unload','voice','stt'])
                self.assertEqual(brain.cfg.voice_gpu_priority,device=='cuda')
                self.assertEqual(llm.gpu_layers,0 if device=='cuda' else None)

    def test_resource_release_keeps_unrelated_ollama_models(self):
        model=core.OllamaLLM('http://127.0.0.1:11434/v1','qwen3:8b')
        response=Mock();response.json.return_value={'models':[{'name':'qwen3:8b'},{'name':'unrelated:7b'}]}
        post=Mock(status_code=200);post.__enter__=Mock(return_value=post);post.__exit__=Mock(return_value=False)
        with patch.object(core.requests,'get',return_value=response),patch.object(core.requests,'post',return_value=post) as send:
            self.assertEqual(model.release_for_voice(['qwen3:8b','qwen2.5-coder:7b']),['qwen3:8b'])
        send.assert_called_once()
        self.assertEqual(send.call_args.kwargs['json'],{'model':'qwen3:8b','keep_alive':0})

    def test_learning_report_speaks_short_truthful_summary_and_keeps_full_text(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'detect_backend',return_value=None),patch('sys.stdout',new=io.StringIO()):
            brain=core.WhisperBrain(core.Config(db_path=str(Path(tmp)/'memory.db'),tts_engine='none'))
            brain.voice.speak=Mock(return_value=True)
            result=brain.process_command('Bugün neler öğrendin?')
        self.assertIn('Toplam ilerleme',result['response'])
        self.assertIn('yeni bilgi kartı oluşturmadım',result['spoken_response'])
        self.assertLess(len(result['spoken_response']),120)
        brain.voice.speak.assert_called_once_with(result['spoken_response'])
