import json
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
import wave
import numpy as np
import whisper_bootstrap
from whisper.voice import reference_setup as setup
from whisper.voice.reference_tts import ReferenceTTS

class PreparationTests(unittest.TestCase):
    def wav(self,path,seconds=8,silent=False):
        sr=16000;x=np.zeros(sr*seconds,dtype=np.int16) if silent else (np.sin(np.arange(sr*seconds)*.1)*10000).astype(np.int16)
        with wave.open(str(path),'wb') as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(sr);w.writeframes(np.column_stack([x,x]).tobytes())

    @unittest.skipUnless(importlib.util.find_spec('soundfile') is not None, 'İsteğe bağlı ses ortamı: soundfile')
    def test_reference_is_private_mono_24khz_wav(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'original.wav';b=Path(tmp)/'private'/'reference.wav';self.wav(a)
            setup.convert_reference(a,b)
            with wave.open(str(b),'rb') as w:
                self.assertEqual((w.getframerate(),w.getnchannels(),w.getsampwidth()),(24000,1,2))
                self.assertGreater(w.getnframes(),24000*5)
            self.assertTrue(a.is_file());self.assertEqual(list(b.parent.glob('*.tmp')),[])

    @unittest.skipUnless(importlib.util.find_spec('soundfile') is not None, 'İsteğe bağlı ses ortamı: soundfile')
    def test_short_and_silent_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for seconds,silent in [(3,False),(8,True)]:
                a=Path(tmp)/'source.wav';self.wav(a,seconds,silent)
                with self.assertRaises(ValueError):setup.convert_reference(a,Path(tmp)/'out.wav')

    def test_ready_requires_runtime_reference_and_model_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            self.assertFalse(setup.ready(home))
            py=setup.runtime_python(home);py.parent.mkdir(parents=True);py.touch()
            (home/'reference.wav').write_bytes(b'voice');(home/'model').mkdir();(home/'model'/'model.pth').write_bytes(b'model')
            (home/'ready.json').write_text(json.dumps({'revision':setup.REVISION}))
            with patch.object(setup,'FILES',{'model.pth':(5,'unused')}):self.assertTrue(setup.ready(home))
            (home/'reference.wav').unlink();self.assertFalse(setup.ready(home))

    def test_cuda_is_selected_only_after_compatible_driver_probe(self):
        with patch.object(setup.shutil,'which',return_value='nvidia-smi'),patch.object(setup.subprocess,'run',return_value=Mock(returncode=0,stdout='572.12\n')):
            self.assertTrue(setup.torch_index().endswith('/cu126'))
        with patch.object(setup.shutil,'which',return_value='nvidia-smi'),patch.object(setup.subprocess,'run',side_effect=subprocess.TimeoutExpired('nvidia-smi',5)):
            self.assertTrue(setup.torch_index().endswith('/cpu'))

    def test_cancelled_selection_installs_nothing(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(setup,'voice_home',return_value=Path(tmp)),patch.object(setup,'choose_source',return_value=''),patch.object(setup.venv,'EnvBuilder') as create,patch.object(setup.subprocess,'run') as install:
            self.assertEqual(setup.setup(),1)
        create.assert_not_called();install.assert_not_called()

class AdapterTests(unittest.TestCase):
    def make_engine(self,home):
        with patch('whisper.voice.reference_tts.ready',return_value=True):engine=ReferenceTTS(home=home)
        self.addCleanup(engine.close)
        engine._start=Mock();engine._process=Mock();engine._process.poll.return_value=0
        engine._wait=Mock(return_value={'type':'done','seconds':1.5})
        def write(line):
            output=json.loads(line)['output']
            with wave.open(output,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\0\0'*2400)
        engine._process.stdin.write.side_effect=write
        engine._play=Mock(return_value=True)
        return engine

    def test_synthesis_is_cached_and_temporary_output_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine=self.make_engine(tmp);writer=engine._process.stdin.write
            self.assertTrue(engine.speak('Merhaba'));self.assertTrue(engine.speak('Merhaba'))
            self.assertEqual(writer.call_count,1);self.assertEqual(engine._play.call_count,2)
            self.assertFalse((Path(engine._directory.name)/'speech.wav').exists())

    def test_cancelled_turn_does_not_start_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine=self.make_engine(tmp);engine.turn_cancelled=threading.Event();engine.turn_cancelled.set()
            self.assertFalse(engine.speak('Merhaba'));engine._start.assert_not_called();engine._play.assert_not_called()

    def test_worker_error_is_not_cached_as_speech(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine=self.make_engine(tmp);engine._wait.side_effect=RuntimeError('worker failure')
            self.assertFalse(engine.speak('Merhaba'));self.assertFalse(engine._cache);engine._play.assert_not_called()

    def test_cancelled_default_setup_does_not_launch_assistant_or_ask_api_key(self):
        with patch.object(whisper_bootstrap.sys,'platform','win32'),patch.object(whisper_bootstrap.os,'chdir'),patch.object(whisper_bootstrap.importlib.util,'find_spec',return_value=object()),patch.object(setup,'ready',return_value=False),patch.object(whisper_bootstrap.subprocess,'call',return_value=1) as launch:
            self.assertEqual(whisper_bootstrap.main(['--reference']),1)
        launch.assert_called_once();self.assertIn('whisper.voice.reference_setup',launch.call_args.args[0])
