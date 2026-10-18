import unittest
from unittest.mock import patch
import whisper_bootstrap
from whisper.voice import chatterbox_setup

class CheckTests(unittest.TestCase):
    def test_check_mode_never_installs_or_launches(self):
        with patch.object(whisper_bootstrap.os,'chdir'), \
             patch.object(whisper_bootstrap.sys,'platform','win32'), \
             patch.object(whisper_bootstrap.importlib.util,'find_spec',return_value=object()), \
             patch.object(chatterbox_setup,'ready',return_value=True), \
             patch.object(whisper_bootstrap.subprocess,'run') as install, \
             patch.object(whisper_bootstrap.subprocess,'call') as launch:
            self.assertEqual(whisper_bootstrap.main(['--check-only']),0)
        install.assert_not_called();launch.assert_not_called()

    def test_missing_module_fails_check_without_install(self):
        with patch.object(whisper_bootstrap.os,'chdir'), \
             patch.object(whisper_bootstrap.importlib.util,'find_spec',return_value=None), \
             patch.object(whisper_bootstrap.subprocess,'run') as install:
            self.assertEqual(whisper_bootstrap.main(['--check-only']),1)
        install.assert_not_called()

    def test_tampered_package_stops_before_launch(self):
        with patch.object(whisper_bootstrap.os,'chdir'), \
             patch.object(whisper_bootstrap.hashlib,'sha256') as digest, \
             patch.object(whisper_bootstrap.subprocess,'call') as launch:
            digest.return_value.hexdigest.return_value='mismatch'
            self.assertEqual(whisper_bootstrap.main([]),1)
        launch.assert_not_called()
