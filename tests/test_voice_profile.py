import unittest,tempfile,json,sys,ast,typing,time,threading,io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from whisper.voice.profile import *
CORE_PATH=ROOT/'whisper_ses_v12.py' if (ROOT/'whisper_ses_v12.py').exists() else ROOT/'whisper_core.py'
source=ast.parse(CORE_PATH.read_text())
ns=dict(vars(typing),np=np,time=time,threading=threading,sd=Mock(),print=Mock())
brain=next(n for n in source.body if getattr(n,'name','')=='WhisperBrain')
node=ast.ClassDef(name='Brain',bases=[],keywords=[],decorator_list=[],body=[n for n in brain.body if getattr(n,'name','')=='_wake_chime'])
exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'chime','exec'),ns)
class Tests(unittest.TestCase):
    def test_fragments_rejected_without_guessing(self):
        for text in ('Rik!','Zort','Chrome'):self.assertTrue(uncertain_fragment(text))
    def test_valid_commands_and_selection_preserved(self):
        for text in ('Brave aç','merhaba','evet','bir','3','neden','nasıl'):
            self.assertFalse(uncertain_fragment(text))
    def test_energy_and_clipping(self):
        obs=energy_observation(np.ones(16000,dtype=np.int16)*1000,16000)
        self.assertAlmostEqual(obs['speech_level'],1000/32768,places=5)
        self.assertEqual(obs['clipping_percent'],0)
        self.assertEqual(energy_observation(np.ones(16000,dtype=np.int16)*32767,16000)['clipping_percent'],100)
    def test_threshold_requires_three_usable_readings(self):
        self.assertIsNone(recommended_threshold([{'speech_level':.01,'clipping_percent':0}]*2))
        value=recommended_threshold([{'speech_level':.001,'clipping_percent':0}]*3)
        self.assertEqual(value,.0005)
    def test_profile_matches_device_and_noise(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'profile.json';p.write_text(json.dumps({'threshold':.0005,'device':1,'sample_rate':44100}))
            self.assertEqual(apply_profile(p,1,44100,.0001,.002),.0005)
            self.assertEqual(apply_profile(p,2,44100,.0001,.002),.002)
            self.assertEqual(apply_profile(p,1,48000,.0001,.002),.002)
            self.assertEqual(apply_profile(p,1,44100,.004,.002),.012)
    def test_corrupt_or_unsafe_profile_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'profile.json';p.write_text('not json')
            self.assertEqual(apply_profile(p,1,44100,0,.002),.002)
            p.write_text(json.dumps({'threshold':float('nan'),'device':1,'sample_rate':44100}))
            self.assertEqual(apply_profile(p,1,44100,0,.002),.002)
    def test_ready_notification_never_opens_audio_or_takes_command_lock(self):
        b=ns['Brain']();b._command_lock=threading.Lock();b.voice=Mock()
        ns['sd'].reset_mock()
        b._wake_chime();b.voice.speak.assert_not_called()
        ns['sd'].play.assert_not_called()
        self.assertTrue(b._command_lock.acquire(blocking=False))
        b._command_lock.release()
    def test_chime_does_not_overlap_active_command(self):
        b=ns['Brain']();b._command_lock=threading.Lock();b._command_lock.acquire()
        ns['sd'].play.reset_mock();b._wake_chime();ns['sd'].play.assert_not_called()
    def test_xtts_controls_present_in_both_voice_paths(self):
        s=CORE_PATH.read_text();self.assertEqual(s.count('temperature=0.65, repetition_penalty=3.0, speed=1.0'),2)
    def test_enrollment_saves_local_metrics_and_reference(self):
        from datetime import datetime
        node=next(n for n in source.body if getattr(n,'name','')=='calibrate_voice')
        listener=Mock();listener.last_ambient=.0001;listener.calibrate.return_value=.002
        listener.listen_once.return_value=np.ones(16000,dtype=np.int16)*1000
        stt=Mock();stt.transcribe.side_effect=list(READING_SENTENCES)
        with tempfile.TemporaryDirectory() as tmp:
            local=dict(ns,Config=object,Path=Path,BASE_DIR=Path(tmp),json=json,datetime=datetime,
                       build_stt=lambda cfg:stt,detect_input_device=lambda cfg:(1,44100,False),
                       MicListener=lambda **kw:listener,input=Mock(return_value=''),
                       resample_int16=lambda audio,rate:audio)
            exec(compile(ast.Module(body=[node],type_ignores=[]),'enroll','exec'),local)
            local['calibrate_voice'](SimpleNamespace())
            data=json.loads((Path(tmp)/'voice_profile.json').read_text())
            self.assertEqual(len(data['observations']),6)
            self.assertLessEqual(data['threshold'],.002)
            self.assertEqual(data['observations'][0]['word_error_rate'],0)
            self.assertTrue((Path(tmp)/data['reference_wav']).exists())
            listener.close.assert_called_once()
    def test_enrollment_text_is_not_tool_execution(self):
        node=next(n for n in source.body if getattr(n,'name','')=='calibrate_voice')
        names=[n.attr for n in ast.walk(node) if isinstance(n,ast.Attribute)]
        self.assertNotIn('process_command',names);self.assertNotIn('run',names)
if __name__=='__main__':unittest.main()
