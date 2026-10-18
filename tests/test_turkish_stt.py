import ast, queue, time, typing, unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'whisper_ses_v12.py'
if not p.exists(): p=ROOT/'whisper_core.py'
tree=ast.parse(p.read_text())
ns=dict(vars(typing), np=np, queue=queue, time=time, os=__import__('os'),
        normalize_int16=lambda a:a)
classes=[n for n in tree.body if getattr(n,'name','') in ('WhisperSTT','MicListener')]
exec(compile(ast.Module(body=classes,type_ignores=[]),'voice','exec'),ns)

class Tests(unittest.TestCase):
    def listener(self, levels):
        obj=ns['MicListener'].__new__(ns['MicListener'])
        obj.samplerate=16000; obj.block=480; obj.silence_seconds=.3; obj.max_seconds=3
        @contextmanager
        def active():
            for level in levels: obj._q.put(np.full(obj.block,level,np.float32))
            yield
        obj._active_stream=active
        return obj
    def test_weak_syllables_do_not_end_recording(self):
        # Quiet speech above the end threshold must survive a >300ms lull.
        obj=self.listener([.004]*3+[.0015]*12+[.004]*3+[0]*12)
        audio=obj.listen_once(.002,prompt='',start_timeout=.01)
        self.assertIsNotNone(audio)
        self.assertGreater(len(audio),480*20)
    def test_single_impulse_not_speech(self):
        obj=self.listener([0]*2+[.01]+[0]*10)
        self.assertIsNone(obj.listen_once(.002,prompt='',start_timeout=.01))
    def test_preroll_retains_quiet_initial_sound(self):
        obj=self.listener([.0015]*4+[.004]*3+[0]*12)
        audio=obj.listen_once(.002,prompt='',start_timeout=.01)
        self.assertGreater(np.max(np.abs(audio[:480*4])),0)
    def test_decode_hints_and_filters_preserve_raw_rem(self):
        obj=ns['WhisperSTT'].__new__(ns['WhisperSTT'])
        obj.language='tr'; obj.beam_size=5; obj.initial_prompt=obj.TURKISH_CONTEXT
        seg=SimpleNamespace(text='REM uykusu nedir?',avg_logprob=-.2,no_speech_prob=.1,compression_ratio=1.)
        obj.model=SimpleNamespace(transcribe=Mock(return_value=(iter([seg]),None)))
        self.assertEqual(obj.transcribe(np.full(16000,500,np.int16)),'REM uykusu nedir?')
        kw=obj.model.transcribe.call_args.kwargs
        self.assertIn('RAM',kw['hotwords']); self.assertIn('bilgisayar belleği',kw['hotwords'])
        self.assertEqual(kw['language'],'tr'); self.assertEqual(kw['beam_size'],5)
        self.assertFalse(kw['condition_on_previous_text'])
        self.assertIsNone(kw['initial_prompt'])
        self.assertEqual(kw['vad_parameters']['speech_pad_ms'],400)
    def test_silence_not_accepted_with_context(self):
        obj=ns['WhisperSTT'].__new__(ns['WhisperSTT'])
        obj.language='tr'; obj.beam_size=5; obj.initial_prompt=obj.TURKISH_CONTEXT
        seg=SimpleNamespace(text='Whisper RAM',avg_logprob=-.2,no_speech_prob=.9,compression_ratio=1.)
        obj.model=SimpleNamespace(transcribe=Mock(return_value=(iter([seg]),None)))
        self.assertEqual(obj.transcribe(np.full(16000,500,np.int16)),'')

    def test_v26_silence_skips_model_before_gain(self):
        obj=ns['WhisperSTT'].__new__(ns['WhisperSTT'])
        obj.model=Mock()
        for audio in (np.zeros(16000,np.int16),np.array([],np.int16),np.ones(16000,np.int16)):
            self.assertEqual(obj.transcribe(audio),'')
        obj.model.transcribe.assert_not_called()
        self.assertEqual(obj.last_quality['reason'],'silence')

    def test_v26_four_repeated_words_are_filtered(self):
        obj=ns['WhisperSTT'].__new__(ns['WhisperSTT'])
        obj.language='tr'; obj.beam_size=5; obj.initial_prompt=None
        seg=SimpleNamespace(text='Aşağı, ışık, ışık, ışık, ışık, ışık',avg_logprob=-.47,no_speech_prob=.1,compression_ratio=1.)
        obj.model=SimpleNamespace(transcribe=Mock(return_value=(iter([seg]),None)))
        self.assertEqual(obj.transcribe(np.full(16000,500,np.int16)),'')

    def test_v26_real_wake_command_is_preserved(self):
        obj=ns['WhisperSTT'].__new__(ns['WhisperSTT'])
        obj.language='tr'; obj.beam_size=5; obj.initial_prompt=None
        seg=SimpleNamespace(text='Hey Whisper, ışığı aç.',avg_logprob=-.47,no_speech_prob=.1,compression_ratio=1.)
        obj.model=SimpleNamespace(transcribe=Mock(return_value=(iter([seg]),None)))
        self.assertEqual(obj.transcribe(np.full(16000,500,np.int16)),'Hey Whisper, ışığı aç.')

if __name__=='__main__': unittest.main()
