import io
import json
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from whisper.core.reasoning import conversational_turn
from whisper.voice.chatterbox_tts import ChatterboxTTS
from whisper.voice.reference_tts import ReferenceTTS
import test_pipeline_regression as pipeline
core=pipeline.core


class ConversationTests(unittest.TestCase):
    def test_standalone_social_turns_skip_planner_but_mixed_actions_do_not(self):
        for text in ('Ne yapıyorsun?','Merhaba!','Beni duyuyor musun?','Whisper, nasılsın?'):
            self.assertTrue(conversational_turn(text),text)
        for text in ('Merhaba, Chrome aç','Ne yapıyorsun, araştırmaya devam et','Nasılsın, ses seviyesini ayarla','Araştırma nedir?','Onu aç'):
            self.assertFalse(conversational_turn(text),text)

    def test_social_reply_is_one_model_call_with_bounded_context_and_no_source_card_answer(self):
        fixture=pipeline.Tests();fixture.setUp();self.addCleanup(fixture.tmp.cleanup)
        brain=fixture.brain;brain.cfg.tools_enabled=True
        brain.llm.base_url='http://127.0.0.1:11434/v1'
        brain.llm.chat.return_value='Şu an seninle sohbet ediyorum. Sen ne yapıyorsun?'
        brain.voice.speak=Mock(return_value=True)
        with patch.object(brain,'_select_role_model'),patch.object(brain.agent,'execute') as plan, \
             patch.object(brain.knowledge_processor,'recall',return_value=[dict(source_id=1,summary='Kaynak metni')]), \
             patch.object(brain.knowledge_processor,'answer') as answer,patch('sys.stdout',new=io.StringIO()):
            result=brain.process_command('Ne yapıyorsun?')
        self.assertEqual(result['status'],'success')
        plan.assert_not_called();answer.assert_not_called();brain.llm.chat.assert_called_once()
        system,user=brain.llm.chat.call_args.args
        self.assertEqual(user,'Ne yapıyorsun?')
        self.assertLess(len(system),2000)
        self.assertNotIn('ENVANTERİ',system)
        self.assertIn('profile',system)
        self.assertLessEqual(brain.llm.chat.call_args.kwargs['max_tokens'],96)

    def test_pending_clarification_still_reaches_planner_for_a_social_sounding_reply(self):
        fixture=pipeline.Tests();fixture.setUp();self.addCleanup(fixture.tmp.cleanup)
        brain=fixture.brain;brain.cfg.tools_enabled=True
        brain.llm.base_url='http://127.0.0.1:11434/v1'
        brain.agent.ask_followup('bir not al','Ne kaydedeyim?')
        with patch.object(brain,'_select_role_model'),patch.object(brain.agent,'execute',return_value=dict(status='success',response='Not kaydedildi.')) as plan,patch('sys.stdout',new=io.StringIO()):
            brain.process_command('Ne yapıyorsun?')
        plan.assert_called_once()


class SpeechTextTests(unittest.TestCase):
    def test_streamed_reply_retains_written_numbers_and_key_name_in_memory(self):
        fixture=pipeline.Tests();fixture.setUp();self.addCleanup(fixture.tmp.cleanup)
        brain=fixture.brain;brain.cfg.tts_sentence_stream=True
        original='Enter tuşuna bas. Bellek kullanımı %25.'
        brain.llm.chat_stream.return_value=iter([original])
        brain.voice.speak=Mock(return_value=True)
        with patch.object(brain,'_select_role_model'),patch('sys.stdout',new=io.StringIO()):
            result=brain.process_command('Ne yapıyorsun?')
        self.assertEqual(result['response'],original)
        self.assertEqual(brain.memory.recent_history(1)[0][1],original)
        self.assertIn('entır',core.speech_text_tr(original))
        self.assertIn('yüzde yirmi beş',core.speech_text_tr(original))

    def test_numbers_percent_decimal_thousands_and_dates(self):
        cases={'25':'yirmi beş','100':'yüz','1000':'bin','2026':'iki bin yirmi altı',
               '1.250,50':'bin iki yüz elli virgül elli','3,05 GB':'üç virgül sıfır beş gigabayt',
               '%25':'yüzde yirmi beş','25%':'yüzde yirmi beş','-12':'eksi on iki',
               '007':'sıfır sıfır yedi','17.10.2026':'on yedi Ekim iki bin yirmi altı',
               'Enter tuşuna bas.':'entır tuşuna bas.','23:02':'yirmi üçü iki geçiyor'}
        for text,expected in cases.items():
            with self.subTest(text=text):
                spoken=core.speech_text_tr(text)
                self.assertEqual(spoken,expected)
                self.assertEqual(core.speech_text_tr(spoken),spoken)

    def test_long_reference_speech_splits_without_omitting_words(self):
        engine=ChatterboxTTS.__new__(ChatterboxTTS)
        engine.text_processor=core.speech_text_tr;engine._cancel=threading.Event()
        text=' '.join(['Enter tuşuna bas ve 25 sayısını söyle.']*16)
        with patch.object(ReferenceTTS,'speak',return_value=True) as speak:
            self.assertTrue(engine.speak(text))
        chunks=[call.args[0] for call in speak.call_args_list]
        self.assertGreater(len(chunks),1)
        self.assertTrue(all(len(chunk)<=220 for chunk in chunks))
        self.assertEqual(' '.join(chunks),core.speech_text_tr(text))

    def test_chunk_failure_does_not_continue_or_replay_previous_audio(self):
        engine=ChatterboxTTS.__new__(ChatterboxTTS)
        engine.text_processor=str;engine._cancel=threading.Event()
        with patch.object(ReferenceTTS,'speak',return_value=False) as speak:
            self.assertFalse(engine.speak('Uzun bir cümle. '*60))
        speak.assert_called_once()


class MemoryBudgetTests(unittest.TestCase):
    def test_budget_after_voice_and_recognition_preserves_headroom(self):
        for free,expected in ((4096,8),(2560,4),(1600,0),(None,0)):
            with self.subTest(free=free):
                llm=core.OllamaLLM('http://127.0.0.1:11434/v1','qwen3:8b');llm.release_for_voice=Mock()
                cfg=core.Config(voice_gpu_priority=True)
                brain=SimpleNamespace(cfg=cfg,llm=llm,stt=object(),listener=None,
                    voice=SimpleNamespace(engine=SimpleNamespace(device='cuda',warmup=lambda stop:True),begin=lambda:None))
                with patch.object(core,'sd',Mock()),patch.object(core,'free_vram_mb',return_value=free), \
                     patch.object(core,'detect_input_device',side_effect=RuntimeError('stop before microphone')),patch('sys.stdout',new=io.StringIO()):
                    with self.assertRaisesRegex(RuntimeError,'stop before microphone'):
                        core.WhisperBrain._start_voice_loop(brain)
                self.assertEqual(cfg.voice_llm_gpu_layers,expected)
                self.assertEqual(llm._payload('system','hello',64,False)['options']['num_gpu'],expected)
                self.assertEqual(llm.context,2048)

    def test_ollama_allocation_error_retries_once_on_cpu_and_retains_disabled_gpu(self):
        model=core.OllamaLLM('http://127.0.0.1:11434/v1','qwen3:8b',gpu_layers=4)
        bad=Mock(status_code=500,text='CUDA out of memory');bad.__enter__=Mock(return_value=bad);bad.__exit__=Mock(return_value=False)
        good=Mock(status_code=200);good.__enter__=Mock(return_value=good);good.__exit__=Mock(return_value=False)
        good.json.return_value={'message':{'content':'Yanıt.'},'done':True}
        budgets=[]
        def post(*args,**kwargs):
            budgets.append(kwargs['json']['options']['num_gpu'])
            return bad if len(budgets)==1 else good
        with patch.object(core.requests,'post',side_effect=post),patch('sys.stdout',new=io.StringIO()):
            self.assertEqual(model.chat('s','u'),'Yanıt.')
        self.assertEqual(budgets,[4,0])
        self.assertEqual(model._payload('s','u',20,True)['options']['num_gpu'],0)

    def test_authentication_error_is_not_retried_as_a_memory_error(self):
        model=core.OllamaLLM('http://127.0.0.1:11434/v1','qwen3:8b',gpu_layers=4)
        response=Mock(status_code=401,text='Unauthorized');response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        with patch.object(core.requests,'post',return_value=response) as post,self.assertRaises(core.LLMError):
            model.chat('s','u')
        post.assert_called_once()
