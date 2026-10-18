import unittest
from threading import Event
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from whisper.core.coding import coding_request, produce_code

class CodingTests(unittest.TestCase):
    def test_natural_requests_and_existing_workflow(self):
        for request in ('Hesap makinesi kodla', 'bana hesap makinası kodlayabilir misin', 'HTML ile form yaz', 'Python öğrenmek istiyorum'):
            self.assertTrue(coding_request(request),request)
        for request in ('Kod geliştir: Whisper modülü', 'Kod paketle: 5', 'taslak incele: 2', 'Chrome aç', 'YouTube’dan şarkı aç', 'Python dosyasını aç'):
            self.assertFalse(coding_request(request),request)

    def test_cancelled_code_never_writes_or_executes(self):
        stop=Event();stop.set()
        model=Mock(base_url='http://localhost:11434/v1')
        model.chat.return_value='```python\nraise RuntimeError("executed")\n```'
        with TemporaryDirectory() as directory:
            result=produce_code('Kod yaz',model,Path(directory)/'memory.db',stop)
            self.assertEqual(result['status'],'cancelled')
            self.assertEqual(list(Path(directory).iterdir()),[])

    def test_remote_model_is_not_used(self):
        model=Mock(base_url='https://example.com/v1')
        result=produce_code('Kod yaz',model,'memory.db',Event())
        self.assertEqual(result['status'],'blocked')
        model.chat.assert_not_called()
