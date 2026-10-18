from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
import wave
import whisper_bootstrap
from test_pipeline_regression import core
from whisper.voice import elevenlabs_tts as el

class ElevenLabsTests(unittest.TestCase):
    def response(self,status=200,data=b'\x01\x00'*100,kind='audio/pcm'):
        r=Mock();r.status_code=status;r.headers={'Content-Type':kind}
        r.iter_content.return_value=[data];r.json.return_value={}
        r.__enter__=Mock(return_value=r);r.__exit__=Mock(return_value=False)
        return r

    def test_cloud_voice_requires_explicit_cloud_setting(self):
        with redirect_stdout(io.StringIO()),patch('sys.stderr',new=io.StringIO()):
            with self.assertRaises(SystemExit):core.parse_args(['--tts','elevenlabs'])
        cfg=core.parse_args(['--tts','elevenlabs','--allow-cloud'])
        self.assertEqual(cfg.elevenlabs_voice_id,'krLzmW3By9JzaVy294Ux')

    def test_missing_key_does_not_fall_back_to_another_voice(self):
        with patch.object(el,'load_key',return_value=''),patch.object(core,'EdgeTTS') as edge,patch.object(core,'SapiTTS') as sapi:
            with self.assertRaises(SystemExit):core.build_tts(core.Config(tts_engine='elevenlabs',allow_cloud=True))
        edge.assert_not_called();sapi.assert_not_called()

    def test_selected_voice_and_turkish_model_are_sent_once(self):
        engine=el.ElevenLabsTTS(api_key='test-secret')
        with patch('requests.post',return_value=self.response()) as post:
            data=engine._fetch('Merhaba')
        self.assertEqual(data,b'\x01\x00'*100)
        self.assertEqual(post.call_args.args[0],el.SERVICE+'/v1/text-to-speech/krLzmW3By9JzaVy294Ux')
        kwargs=post.call_args.kwargs
        self.assertEqual(kwargs['json']['language_code'],'tr')
        self.assertEqual(kwargs['json']['model_id'],'eleven_multilingual_v2')
        self.assertEqual(kwargs['params']['output_format'],'pcm_24000')
        self.assertEqual(kwargs['json']['voice_settings']['stability'],1.0)
        self.assertEqual(kwargs['json']['voice_settings']['similarity_boost'],1.0)
        self.assertEqual(kwargs['json']['voice_settings']['speed'],0.96)
        self.assertFalse(kwargs['allow_redirects']);post.assert_called_once()

    def test_same_text_replays_cache_without_second_paid_request(self):
        engine=el.ElevenLabsTTS(api_key='test-secret');paths=[]
        def play(path):
            paths.append(Path(path))
            with wave.open(path,'rb') as audio:
                self.assertEqual((audio.getframerate(),audio.getsampwidth(),audio.getnchannels()),(24000,2,1))
                self.assertEqual(audio.getnframes(),100)
            return True
        engine._play=play
        with patch('requests.post',return_value=self.response()) as post:
            self.assertTrue(engine.speak('Merhaba'));self.assertTrue(engine.speak('Merhaba'))
        post.assert_called_once();self.assertEqual(len(paths),2)
        self.assertTrue(all(not p.exists() for p in paths))

    def test_quota_failure_has_no_retry_no_secret_leak_and_no_cache(self):
        engine=el.ElevenLabsTTS(api_key='secret-never-print');r=self.response(status=401)
        r.json.return_value={'detail':{'status':'quota_exceeded','message':'secret-never-print'}}
        output=io.StringIO()
        with patch('requests.post',return_value=r) as post,redirect_stdout(output):
            self.assertFalse(engine.speak('Merhaba'));self.assertFalse(engine.speak('Tekrar'))
        post.assert_called_once();self.assertEqual(len(engine._cache),0)
        self.assertIn('kotası',output.getvalue());self.assertNotIn('secret-never-print',output.getvalue())

    def test_cancelled_audio_is_not_played_or_cached(self):
        engine=el.ElevenLabsTTS(api_key='test-secret');engine.turn_cancelled=threading.Event()
        r=self.response()
        def chunks(*args):
            engine.turn_cancelled.set();yield b'\x00\x00'
        r.iter_content.side_effect=chunks;engine._play=Mock()
        with patch('requests.post',return_value=r):self.assertFalse(engine.speak('Merhaba'))
        engine._play.assert_not_called();self.assertFalse(engine._cache)

    def test_http_400_preserves_actual_provider_reason_without_retry(self):
        engine=el.ElevenLabsTTS(api_key='private-test-key');engine._play=Mock()
        r=self.response(status=400)
        r.json.return_value={'detail':{'status':'paid_plan_required','message':'This voice requires a paid plan.'}}
        output=io.StringIO()
        with patch('requests.post',return_value=r) as post,redirect_stdout(output):
            self.assertFalse(engine.speak('Merhaba'))
            self.assertFalse(engine.speak('Tekrar'))
        post.assert_called_once();engine._play.assert_not_called()
        self.assertIn('paid_plan_required',output.getvalue())
        self.assertIn('This voice requires a paid plan.',output.getvalue())

    def test_error_details_redact_key_and_strip_terminal_controls(self):
        r=self.response(status=400)
        r.json.return_value={'detail':{'status':'unknown','message':'Bad private-test-key\n\x1b[31m sk_anotherkey'}}
        message=el.api_error(r,'private-test-key')
        self.assertNotIn('private-test-key',message)
        self.assertNotIn('sk_anotherkey',message)
        self.assertNotIn('\x1b',message)
        self.assertIn('HTTP 400',message)

    def test_validation_error_reports_fields_without_request_or_key(self):
        r=self.response(status=422)
        r.json.return_value={'detail':[{'loc':['body','voice_settings','speed'], 'type':'less_than_equal',
                                       'input':{'text':'private request','key':'private-test-key'}}]}
        message=el.api_error(r,'private-test-key')
        self.assertIn('body.voice_settings.speed',message)
        self.assertNotIn('private request',message)
        self.assertNotIn('private-test-key',message)

    def test_non_json_and_nonstandard_errors_remain_actionable(self):
        for detail in ('Invalid voice setting', ['not a validation object'], 10):
            r=self.response(status=400);r.json.return_value={'detail':detail}
            self.assertIn('HTTP 400',el.api_error(r,'private-test-key'))
        r=self.response(status=500);r.json.side_effect=ValueError('not JSON')
        self.assertIn('HTTP 500',el.api_error(r,'private-test-key'))

    def test_json_or_partial_pcm_is_not_accepted_as_audio(self):
        for data,kind in [(b'{}','application/json'),(b'\x00','audio/pcm'),(b'','audio/pcm')]:
            engine=el.ElevenLabsTTS(api_key='test-secret');engine._play=Mock()
            with patch('requests.post',return_value=self.response(data=data,kind=kind)),redirect_stdout(io.StringIO()):
                self.assertFalse(engine.speak('Merhaba'))
            engine._play.assert_not_called();self.assertFalse(engine._cache)

    def test_secret_file_contains_only_protected_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'elevenlabs.dpapi'
            with patch.object(el,'key_path',return_value=path),patch.object(el,'_protect',return_value=b'encrypted') as protect:
                el.save_key('test-secret')
            self.assertEqual(path.read_bytes(),b'encrypted')
            self.assertEqual(protect.call_args.args[0],b'test-secret')
            self.assertEqual(list(path.parent.glob('*.tmp')),[])

    def test_cancelled_first_setup_does_not_launch_assistant(self):
        with patch.object(whisper_bootstrap.sys,'platform','win32'),patch.object(whisper_bootstrap.os,'chdir'),patch.object(whisper_bootstrap.importlib.util,'find_spec',return_value=object()),patch.object(el,'load_key',return_value=''),patch.object(whisper_bootstrap.subprocess,'call',return_value=1) as launch:
            self.assertEqual(whisper_bootstrap.main(['--elevenlabs']),1)
        launch.assert_called_once()
        self.assertIn('whisper.voice.elevenlabs_tts',launch.call_args.args[0])
