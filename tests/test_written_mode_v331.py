"""Written launch must never provision or load voice models."""
import unittest
from unittest.mock import patch
import whisper_bootstrap as boot
from whisper.voice import chatterbox_setup
import test_pipeline_regression as pipeline


class WrittenModeTests(unittest.TestCase):
    def test_written_launch_uses_existing_gui_without_voice_or_install(self):
        with patch.object(boot,'verify_package',return_value={'version':'test'}),patch.object(boot.os,'chdir'), \
             patch.object(boot.sys,'platform','win32'),patch.object(boot.subprocess,'call',return_value=0) as launch, \
             patch.object(boot.subprocess,'run') as install,patch.object(chatterbox_setup,'ready') as voice:
            self.assertEqual(boot.main(['--text']),0)
        install.assert_not_called();voice.assert_not_called();launch.assert_called_once()
        cfg=pipeline.core.parse_args(launch.call_args.args[0][2:])
        self.assertEqual(cfg.tts_engine,'none');self.assertFalse(cfg.voice_loop_enabled)
        self.assertFalse(cfg.voice_gpu_priority);self.assertTrue(cfg._gui)
        self.assertTrue(cfg.tools_enabled);self.assertTrue(cfg.internet)

    def test_written_check_does_not_require_voice_dependencies(self):
        voice_names={'sounddevice','speech_recognition','faster_whisper','edge_tts','pycaw','comtypes'}
        with patch.object(boot,'verify_package',return_value={'version':'test'}),patch.object(boot.os,'chdir'), \
             patch.object(boot.importlib.util,'find_spec',side_effect=lambda name:None if name in voice_names else object()), \
             patch.object(boot.subprocess,'call') as launch,patch.object(boot.subprocess,'run') as install, \
             patch.object(chatterbox_setup,'ready') as voice:
            self.assertEqual(boot.main(['--text','--check-only']),0)
        launch.assert_not_called();install.assert_not_called();voice.assert_not_called()

    def test_written_and_voice_flags_cannot_silently_override_each_other(self):
        with patch.object(boot.subprocess,'call') as launch:
            self.assertEqual(boot.main(['--text','--test-voice']),2)
        launch.assert_not_called()
