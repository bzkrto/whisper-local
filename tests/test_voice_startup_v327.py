import io
import sys
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from test_pipeline_regression import core
from whisper.voice import playback


class VoiceStartupTests(unittest.TestCase):
    def test_voice_mode_defers_background_models_before_services_start(self):
        for args, expected in (([], True), (['--text'], False)):
            with self.subTest(args=args), tempfile.TemporaryDirectory() as tmp:
                cfg = core.parse_args(['--tts', 'none'] + args)
                cfg.db_path = str(Path(tmp) / 'test.db')
                with patch.object(core, 'detect_backend', return_value=None), patch('sys.stdout', new=io.StringIO()):
                    brain = core.WhisperBrain(cfg)
                self.assertEqual(brain._background_models_paused, expected)
                if expected:
                    with patch.object(brain, '_ensure_llm') as connect:
                        self.assertIsNone(brain._process_knowledge_idle())
                        self.assertIsNone(brain.run_due_research())
                    connect.assert_not_called()
                    self.assertTrue(brain._command_lock.acquire(blocking=False))
                    brain._command_lock.release()

    def test_voice_exit_restores_background_even_on_device_error(self):
        brain = SimpleNamespace(_background_models_paused=False)
        def fail(stop):
            self.assertTrue(brain._background_models_paused)
            raise RuntimeError('input device failed')
        brain._start_voice_loop = fail
        with self.assertRaisesRegex(RuntimeError, 'input device failed'):
            core.WhisperBrain.start_voice_loop(brain)
        self.assertFalse(brain._background_models_paused)

    def test_command_timeout_releases_waiter_without_replaying(self):
        brain = SimpleNamespace(_waiting_command_lock=threading.Lock(),
                                _command_lock=threading.Lock(),
                                _foreground_waiting=threading.Event(),
                                _interrupt_epoch=0, _command_queue_timeout=.01)
        brain._command_lock.acquire()
        with patch('sys.stdout', new=io.StringIO()):
            result = core.WhisperBrain._acquire_command_slot(brain)
        self.assertEqual(result['status'], 'busy')
        self.assertFalse(brain._foreground_waiting.is_set())
        self.assertTrue(brain._waiting_command_lock.acquire(False))
        brain._waiting_command_lock.release()
        brain._command_lock.release()
        self.assertIsNone(core.WhisperBrain._acquire_command_slot(brain))
        brain._command_lock.release()


class WindowsPlaybackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / 'speech.wav')
        with wave.open(self.path, 'wb') as output:
            output.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            output.writeframes(b'\x00\x00' * 24)
        self.native = SimpleNamespace(PlaySound=Mock(), SND_FILENAME=1,
                                      SND_ASYNC=2, SND_NODEFAULT=4)

    def test_windows_plays_async_without_portaudio_and_cleans_up(self):
        with patch.object(playback.os, 'name', 'nt'), patch.dict(sys.modules, {'winsound': self.native, 'sounddevice': None}):
            self.assertTrue(playback.play_wav(self.path, lambda: False))
        self.assertEqual(self.native.PlaySound.call_args_list[0].args, (self.path, 7))
        self.assertEqual(self.native.PlaySound.call_args_list[-1].args, (None, 0))

    def test_interrupt_stops_native_playback(self):
        cancelled = Mock(side_effect=[False, True])
        with patch.object(playback.os, 'name', 'nt'), patch.dict(sys.modules, {'winsound': self.native}):
            self.assertFalse(playback.play_wav(self.path, cancelled))
        self.native.PlaySound.assert_any_call(None, 0)

    def test_output_device_error_propagates_and_cleans_up(self):
        self.native.PlaySound.side_effect = [RuntimeError('output unavailable'), None]
        with patch.object(playback.os, 'name', 'nt'), patch.dict(sys.modules, {'winsound': self.native}):
            with self.assertRaisesRegex(RuntimeError, 'output unavailable'):
                playback.play_wav(self.path, lambda: False)
        self.native.PlaySound.assert_any_call(None, 0)
