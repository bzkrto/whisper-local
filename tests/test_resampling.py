"""Gerçek mikrofon oranları, konuşma bandı ve engellenmiş SciPy testi."""
import ast
import builtins
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / 'whisper_ses_v12.py'
if not CORE.exists():
    CORE = ROOT / 'whisper_core.py'
node = next(n for n in ast.parse(CORE.read_text()).body
            if getattr(n, 'name', '') == 'resample_int16')
ns = {'np': np}
exec(compile(ast.Module(body=[node], type_ignores=[]), str(CORE), 'exec'), ns)
resample = ns['resample_int16']

class ResamplingTests(unittest.TestCase):
    def test_blocked_scipy_and_microphone_rates(self):
        original = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name.startswith('scipy'):
                raise ImportError('Uygulama Denetimi bu dosyayı engelledi')
            return original(name, *args, **kwargs)
        with patch('builtins.__import__', side_effect=guarded):
            for rate in (44100, 48000):
                result = resample(np.full(rate // 10, 12000, np.int16), rate)
                self.assertEqual(result.size, 1600)
                self.assertEqual(result.dtype, np.int16)
                np.testing.assert_array_equal(result, 12000)

    def test_preserves_speech_band_and_rejects_alias(self):
        for rate in (44100, 48000):
            t = np.arange(rate // 5) / rate
            for frequency in (300, 1000, 4000):
                result = resample((12000 * np.sin(2*np.pi*frequency*t)).astype(np.int16), rate)
                expected = 12000 * np.sin(2*np.pi*frequency*np.arange(result.size)/16000)
                rms_error = np.sqrt(np.mean((result[100:-100] - expected[100:-100])**2))
                self.assertLess(rms_error, 30)
            high = resample((12000*np.sin(2*np.pi*10000*t)).astype(np.int16), rate)
            self.assertLess(np.sqrt(np.mean(high[100:-100].astype(float)**2)), 100)

    def test_empty_same_rate_and_invalid_rate(self):
        audio = np.array([-32768, 0, 32767], np.int16)
        self.assertIs(resample(audio, 16000), audio)
        self.assertEqual(resample(np.array([], np.int16), 44100).size, 0)
        with self.assertRaises(ValueError):
            resample(audio, 0)

if __name__ == '__main__':
    unittest.main()
