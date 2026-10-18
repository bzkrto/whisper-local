import io
import unittest
from unittest.mock import patch, Mock

import whisper_bootstrap
from whisper.voice import elevenlabs_tts
from whisper.voice import chatterbox_setup
from test_pipeline_regression import core


class FreeVoiceTests(unittest.TestCase):
    def launch_default(self, args=None):
        with patch.object(whisper_bootstrap.sys, 'platform', 'win32'), \
             patch.object(whisper_bootstrap.os, 'chdir'), \
             patch.object(whisper_bootstrap.importlib.util, 'find_spec', return_value=object()), \
             patch.object(elevenlabs_tts, 'load_key', side_effect=AssertionError('paid key accessed')), \
             patch.object(chatterbox_setup, 'ready', return_value=True), \
             patch.object(whisper_bootstrap.subprocess, 'call', return_value=0) as launch, \
             patch('sys.stdout', new=io.StringIO()):
            self.assertEqual(whisper_bootstrap.main(args or []), 0)
        launch.assert_called_once()
        return launch.call_args.args[0]

    def test_default_launch_ignores_saved_paid_key_and_disallows_cloud_models(self):
        args = self.launch_default()
        cfg = core.parse_args(args[2:])
        self.assertEqual(cfg.tts_engine, 'chatterbox')
        self.assertFalse(cfg.allow_cloud)
        self.assertTrue(cfg.internet)

    def test_sound_test_uses_same_free_voice_and_early_test_mode(self):
        args = self.launch_default(['--test-voice'])
        cfg = core.parse_args(args[2:])
        self.assertTrue(cfg._test_voice)
        self.assertEqual(cfg.tts_engine, 'chatterbox')
        with patch.object(core, 'build_tts', return_value=Mock()) as voice, \
             patch.object(core, 'WhisperBrain', side_effect=AssertionError('brain started')), \
             patch.object(core, 'build_stt', side_effect=AssertionError('microphone started')), \
             patch('sys.stdout', new=io.StringIO()):
            core.main(args[2:])
        voice.return_value.speak.assert_called_once()

    def test_failed_missing_piper_install_never_launches_assistant(self):
        with patch.object(whisper_bootstrap.sys, 'platform', 'win32'), \
             patch.object(whisper_bootstrap.os, 'chdir'), \
             patch.object(whisper_bootstrap.importlib.util, 'find_spec', side_effect=lambda name: None if name=='piper' else object()), \
             patch.object(whisper_bootstrap.subprocess, 'run', return_value=Mock(returncode=1)) as install, \
             patch.object(whisper_bootstrap.subprocess, 'call') as launch, \
             patch('sys.stdout', new=io.StringIO()):
            self.assertEqual(whisper_bootstrap.main(['--piper']), 1)
        self.assertIn('piper-tts==1.8.0', install.call_args.args[0])
        launch.assert_not_called()
