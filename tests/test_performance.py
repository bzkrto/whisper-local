import ast,io,sys,time,threading,typing,os,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
CORE_PATH=ROOT/'whisper_ses_v12.py' if (ROOT/'whisper_ses_v12.py').exists() else ROOT/'whisper_core.py'
from whisper.voice.runtime import load_stt_model
from whisper.voice.audio_cache import AudioCache
from whisper.voice.evaluation import word_error_rate
source=ast.parse((CORE_PATH).read_text())
ns=dict(vars(typing),np=np,time=time,threading=threading,os=os,sys=sys,Path=Path,Config=object,
    sd=Mock(),speech_text_tr=lambda text:text,is_speakable=lambda text:bool(text),
    normalize_tr=lambda text:text.lower().replace('ı','i').replace('ç','c').replace('ş','s').replace('ö','o').replace('ü','u').replace('ğ','g'),
    re=__import__('re'))
classes=[n for n in source.body if getattr(n,'name','') in ('XttsTTS','OllamaLLM','LLMError','OpenAICompatLLM')]
# Extract only tested methods to avoid importing hardware-dependent code.
brain=next(n for n in source.body if getattr(n,'name','')=='WhisperBrain')
mini=ast.ClassDef(name='Brain',bases=[],keywords=[],body=[n for n in brain.body if getattr(n,'name','')=='_dynamic_max_tokens'],decorator_list=[])
ollama=next(n for n in source.body if getattr(n,'name','')=='OllamaLLM')
metric=ast.ClassDef(name='Metrics',bases=[],keywords=[],body=[n for n in ollama.body if getattr(n,'name','')=='_record_metrics'],decorator_list=[])
xtts=next(n for n in source.body if getattr(n,'name','')=='XttsTTS')
voice=ast.ClassDef(name='Voice',bases=[],keywords=[],body=[n for n in xtts.body if getattr(n,'name','')=='speak'],decorator_list=[])
exec(compile(ast.fix_missing_locations(ast.Module(body=[mini,metric,voice],type_ignores=[])),'selected','exec'),ns)
class Tests(unittest.TestCase):
    def test_gpu_probe_consumes_lazy_generator(self):
        consumed=[]
        def segments():consumed.append(True);yield SimpleNamespace(text='discarded')
        model=SimpleNamespace(transcribe=Mock(return_value=(segments(),None)))
        factory=Mock(return_value=model)
        actual,device=load_stt_model(factory,'local-model','cuda')
        self.assertIs(actual,model);self.assertEqual(device,'cuda');self.assertEqual(consumed,[True])
    def test_lazy_cudnn_failure_falls_back(self):
        def fail():raise RuntimeError('missing cudnn');yield
        gpu=SimpleNamespace(transcribe=Mock(return_value=(fail(),None)))
        cpu=Mock();factory=Mock(side_effect=[gpu,cpu])
        model,device=load_stt_model(factory,'local-model','cuda')
        self.assertIs(model,cpu);self.assertEqual(device,'cpu')
        self.assertEqual(factory.call_args.kwargs['compute_type'],'int8')
    def test_gpu_constructor_failure_falls_back(self):
        cpu=Mock();factory=Mock(side_effect=[RuntimeError('oom'),cpu])
        self.assertEqual(load_stt_model(factory,'model','cuda'),(cpu,'cpu'))
    def test_cpu_failure_not_masked(self):
        with self.assertRaises(RuntimeError):load_stt_model(Mock(side_effect=RuntimeError('bad model')),'model','cpu')
    def test_cpu_skips_probe(self):
        model=Mock();load_stt_model(Mock(return_value=model),'model','cpu');model.transcribe.assert_not_called()
    def test_audio_cache_memory_bound_and_lru(self):
        cache=AudioCache(16);a=np.zeros(2,np.float32)
        cache.put('a',a);cache.put('b',a);cache.get('a');cache.put('c',a)
        self.assertIsNone(cache.get('b'));self.assertIs(cache.get('a'),a);self.assertLessEqual(cache.bytes,16)
    def test_audio_cache_replacement_and_oversize(self):
        cache=AudioCache(16);cache.put('a',np.zeros(2,np.float32));cache.put('a',np.zeros(1,np.float32))
        self.assertEqual(cache.bytes,4);cache.put('big',np.zeros(20,np.float32));self.assertEqual(cache.bytes,4)
    def test_xtts_repeat_uses_cache_still_plays(self):
        v=ns['Voice']();v.conditioning=None;v.selected_voice='test';v.engine=Mock()
        v.engine.tts.return_value=[.1,.2,.3]
        ns['sd'].play.reset_mock()
        self.assertTrue(v.speak('Chrome başlatıldı.'));self.assertTrue(v.speak('Chrome başlatıldı.'))
        v.engine.tts.assert_called_once();self.assertEqual(ns['sd'].play.call_count,2)
    def test_xtts_empty_audio_not_cached(self):
        v=ns['Voice']();v.conditioning=None;v.selected_voice='test';v.engine=Mock();v.engine.tts.return_value=[]
        self.assertFalse(v.speak('test'));self.assertFalse(v.speak('test'));self.assertEqual(v.engine.tts.call_count,2)
    def test_complex_short_question_has_full_budget(self):
        b=ns['Brain']();b.cfg=SimpleNamespace(max_tokens=400,short_query_max_tokens=120,short_query_words=5);b._active_route=None
        for q in ('Neden yavaşlıyor?','Nasıl çözerim?','Plan oluştur','Python kod yaz'):
            self.assertEqual(b._dynamic_max_tokens(q),400)
        self.assertEqual(b._dynamic_max_tokens('Merhaba'),96)
    def test_code_route_budget(self):
        b=ns['Brain']();b.cfg=SimpleNamespace(max_tokens=400);b._active_route=SimpleNamespace(role='code')
        self.assertEqual(b._dynamic_max_tokens('Bunu düzelt'),400)
    def test_only_server_metrics_are_reported(self):
        m=ns['Metrics']();m._record_metrics({'load_duration':1e9,'prompt_eval_duration':2e9,'eval_duration':3e9})
        self.assertEqual(m.last_metrics,{'load_duration':1.,'prompt_eval_duration':2.,'eval_duration':3.})
        m._record_metrics({});self.assertEqual(m.last_metrics,{})
    def test_word_error_rate(self):
        self.assertEqual(word_error_rate('Hesap makinesini aç','hesap makinesini aç!'),0)
        self.assertAlmostEqual(word_error_rate('Hesap makinesini aç','hesap makinesini ac'),0)
        self.assertAlmostEqual(word_error_rate('Brave uygulamasını aç','Chrome uygulamasını aç'),1/3)
        self.assertEqual(word_error_rate('Whisper saat kaç',''),1)
    def test_fixed_25_word_limit_removed(self):
        self.assertNotIn('toplam 25 kelimeyi geçme',(CORE_PATH).read_text())
        if (ROOT/'whisper_bootstrap.py').exists():
            import whisper_bootstrap
            with patch.object(whisper_bootstrap.sys,'platform','linux'), \
                 patch('whisper.voice.chatterbox_setup.ready',return_value=True), \
                 patch.object(whisper_bootstrap.os,'chdir'), \
                 patch.object(whisper_bootstrap.subprocess,'call',return_value=0) as launch:
                self.assertEqual(whisper_bootstrap.main(),0)
            args=launch.call_args.args[0]
            self.assertIn(args[args.index('--whisper-device')+1],('cuda','auto'))
            self.assertEqual(args[args.index('--tts')+1],'chatterbox')
            self.assertIn('whisper_bootstrap.py',(ROOT/'WHISPER_BASLAT.cmd').read_text())
        else:
            self.assertIn('--whisper-device auto',(ROOT/'WHISPER_BASLAT.cmd').read_text())
if __name__=='__main__':unittest.main()
