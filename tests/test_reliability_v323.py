import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import wave
from test_pipeline_regression import core
from whisper.core.learning_intent import learning_intent
from whisper.core.structured import obj,request,string,validate
from whisper.learning.development import DevelopmentEngine
from whisper.voice import local_tts

class LearningIntentTests(unittest.TestCase):
    def test_assistant_questions_are_internal_with_optional_polite_words(self):
        for text in ('Bugün neler öğrendin?', 'Bugün bana ne öğrendiğini anlat.', 'Bugünkü öğrenmelerini özetle.', 'Neler öğrendin söyle bakalım', 'Bugün ne öğrendiniz?', 'Öğrenme özeti'):
            with self.subTest(text=text):
                self.assertEqual(learning_intent(text),'summary')
                self.assertFalse(core.WebSearch(Mock(),core.Config(internet=True)).needs_internet(text))

    def test_person_confusion_asks_without_web(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(core,'detect_backend',return_value=None):
                b=core.WhisperBrain(core.Config(db_path=str(Path(tmp)/'db'),tts_engine='none',internet=True))
            with patch.object(b.web,'search') as search,patch.object(b.agent,'execute') as execute:
                result=b.process_command('Bugün neler öğrendim?')
                self.assertEqual(result['status'],'clarification')
                result=b.process_command('Evet')
                self.assertEqual(result['status'],'success')
                self.assertIn('belge bölümünü',result['response'])
                search.assert_not_called();execute.assert_not_called()

    def test_user_learning_and_external_news_are_not_silently_rewritten(self):
        self.assertEqual(learning_intent('Ben bugün ne öğrendim?'),'clarify')
        for text in ('Bugün Python öğrenmek için internette kaynak araştır', 'Bugün neler oldu?', 'Bugün öğrenme hakkında haberleri araştır', 'Yarın ne öğreneceğim?'):
            self.assertIsNone(learning_intent(text))

class StructuredTests(unittest.TestCase):
    def test_validation_identifies_nested_field_and_actual_length(self):
        from whisper.learning.development import SCHEMA
        data={'problem':'Yeterli uzunlukta sorun.','change':'Yeterli uzunlukta değişiklik önerisi.','acceptance_tests':[{'input':'evet','expected':'Önceki isteğe bağlanır.'}],'limitations':['x']}
        with self.assertRaisesRegex(ValueError,r'\$\.limitations\[0\].*1.*3'):
            validate(data,SCHEMA)

    def test_concrete_short_test_values_are_valid_but_empty_values_are_rejected(self):
        from whisper.learning.development import SCHEMA
        data={'problem':'Sayaç hatası.','change':'Sayacı bir artır.','acceptance_tests':[{'input':'0','expected':'1'}],'limitations':['Yalnız sayaç kapsamı.']}
        self.assertIs(validate(data,SCHEMA),data)
        data['acceptance_tests'][0]['expected']=''
        with self.assertRaises(ValueError):validate(data,SCHEMA)

    def test_native_repair_receives_bounds_and_bad_field(self):
        class Native:
            def __init__(self):self.calls=[]
            def chat_json(self,system,user,schema,**kwargs):
                self.calls.append((system,user))
                return json.dumps({'answer':'x' if len(self.calls)==1 else 'Düzeltilmiş yeterli açıklama.'})
        model=Native()
        data=request(model,'Yanıt ver',{},obj({'answer':string(10,100)}))
        self.assertIn('Düzeltilmiş',data['answer'])
        self.assertEqual(len(model.calls),2)
        self.assertIn('minLength',model.calls[0][0])
        self.assertIn('$.answer',model.calls[1][0])
        previous=json.loads(model.calls[1][1].split('\n')[-1].split(': ',1)[1])
        self.assertEqual(json.loads(previous),{'answer':'x'})

    def test_repeated_invalid_draft_is_stopped_and_survives_restart(self):
        from whisper.memory.research_memory import ResearchMemory
        from whisper.learning.knowledge import KnowledgeProcessor
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db';core.MemoryEngine(str(path));memory=ResearchMemory(path)
            sid=memory.capture('Python yazılım ajan planlama','Belge kaynak metni '*100,[{'url':'https://docs.python.org/'}],'autonomous_document')
            processor=KnowledgeProcessor(path);processor.sync()
            with sqlite3.connect(path) as db:
                db.execute("UPDATE knowledge_chunks SET state='done',card=? WHERE source_id=?",(json.dumps({'summary':'Kaynak açıklaması.'}),sid))
            now=[200000.];model=Mock();model.base_url='http://127.0.0.1:11434'
            with patch('whisper.learning.development.request',side_effect=ValueError('$.change: metin boyutu')) as infer:
                for attempt in range(3):
                    result=DevelopmentEngine(path,clock=lambda:now[0]).tick(model)
                    self.assertEqual(result['status'],'blocked' if attempt==2 else 'error')
                    now[0]+=3601
                self.assertIsNone(DevelopmentEngine(path,clock=lambda:now[0]).tick(model))
                self.assertEqual(infer.call_count,3)
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT state,attempts,proposal FROM development_jobs').fetchone(),('blocked',3,None))

class LocalVoiceTests(unittest.TestCase):
    def test_default_engine_uses_no_online_or_sapi_provider(self):
        with patch.object(local_tts,'PiperTTS') as local,patch.object(core,'EdgeTTS') as edge,patch.object(core,'SapiTTS') as sapi:
            engine=core.build_tts(core.Config())
        self.assertIs(engine,local.return_value)
        edge.assert_not_called();sapi.assert_not_called()

    def test_verified_cache_needs_no_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);payload=b'verified voice bytes'
            (directory/'tr_TR-fettah-medium.onnx').write_bytes(payload)
            files={'tr_TR-fettah-medium.onnx':(hashlib.sha256(payload).hexdigest(),len(payload))}
            fetch=Mock()
            with patch.object(local_tts,'FILES',files):
                self.assertEqual(local_tts.prepare_voice(directory,fetch=fetch),directory/'tr_TR-fettah-medium.onnx')
            fetch.assert_not_called()

    def test_bad_download_does_not_replace_old_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);name='tr_TR-fettah-medium.onnx';(directory/name).write_bytes(b'old')
            response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
            response.iter_content.return_value=[b'bad']
            files={name:(hashlib.sha256(b'good').hexdigest(),4)}
            with patch.object(local_tts,'FILES',files),self.assertRaises(ValueError):
                local_tts.prepare_voice(directory,fetch=Mock(return_value=response))
            self.assertEqual((directory/name).read_bytes(),b'old')
            self.assertEqual(list(directory.glob('*.part')),[])

    def test_cancelled_turn_does_not_play_and_cleans_temp_audio(self):
        voice=local_tts.PiperTTS.__new__(local_tts.PiperTTS)
        voice._cancel=threading.Event();voice._lock=threading.Lock();voice.turn_cancelled=threading.Event()
        paths=[]
        def synthesize(text,path):
            paths.append(Path(path));voice.turn_cancelled.set()
        voice.synthesize=synthesize;voice._play=Mock()
        self.assertFalse(voice.speak('Merhaba'))
        voice._play.assert_not_called()
        self.assertTrue(all(not path.exists() for path in paths))

    def test_playback_stops_at_next_audio_block(self):
        voice=local_tts.PiperTTS.__new__(local_tts.PiperTTS);voice._cancel=threading.Event()
        writes=[];aborted=[]
        class Output:
            def __init__(self,**kwargs):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def write(self,data):writes.append(data);voice.stop()
            def abort(self):aborted.append(True)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'test.wav'
            with wave.open(str(path),'wb') as wav:
                wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(22050);wav.writeframes(b'\0'*8192)
            with patch.dict(sys.modules,{'sounddevice':SimpleNamespace(RawOutputStream=Output)}):
                self.assertFalse(voice._play(path))
        self.assertEqual(len(writes),1);self.assertEqual(aborted,[True])
