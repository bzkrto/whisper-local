import tempfile
import unittest
from pathlib import Path
from whisper.core.dialogue import DialogueState
from whisper.core.task_context import TaskContext

class ContextualMusicTests(unittest.TestCase):
    def test_missing_title_offers_piano_then_acceptance_uses_offer(self):
        state=DialogueState()
        first=state.media('şarkı aç')
        self.assertEqual(first['kind'],'clarification')
        self.assertIn('soft piyano',first['message'])
        self.assertEqual(state.media('olur')['query'],'soft piyano müziği')
        self.assertIsNone(state.get())
    def test_music_mood_and_activity_followups(self):
        for answer,expected in [('dertli bir şey olsun','Türkçe arabesk müzik'),('dertliyim','Türkçe arabesk müzik'),
                                ('soft piyano','soft piyano müziği'),('ders çalışıyorum','sözsüz odaklanma piyano müziği'),
                                ('uyuyacağım','sakin uyku müziği'),('spor yapıyorum','hareketli spor müziği')]:
            with self.subTest(answer=answer):
                state=DialogueState();state.media('şarkı aç')
                self.assertEqual(state.media(answer)['query'],expected)
    def test_direct_style_and_mood_statement_outside_music(self):
        state=DialogueState()
        self.assertEqual(state.media('dertli bir şey aç')['query'],'Türkçe arabesk müzik')
        self.assertIsNone(state.media('dertliyim'))
        self.assertIsNone(state.media('ders çalışıyorum'))
    def test_rejecting_offer_asks_new_choice_without_action(self):
        state=DialogueState();state.media('şarkı aç')
        self.assertEqual(state.media('hayır')['kind'],'clarification')
        self.assertEqual(state.media('Barış Manço Gülpembe')['query'],'Barış Manço Gülpembe')
    def test_artist_and_title_not_overridden_by_mood_word(self):
        state=DialogueState();state.media('şarkı aç')
        self.assertEqual(state.media('Dertli Dolap')['query'],'Dertli Dolap')
        self.assertEqual(state.media('Dertli Dolap şarkısını aç')['query'],'Dertli Dolap')
    def test_new_task_negative_and_expiry_never_select_music(self):
        now=[0];state=DialogueState(clock=lambda:now[0]);state.media('şarkı aç')
        self.assertIsNone(state.media('Chrome aç'))
        state.media('şarkı aç');self.assertIsNone(state.media('müzik açma'))
        state.media('şarkı aç');now[0]=181
        self.assertIsNone(state.media('olur'))
    def test_piano_refusal_is_not_confirmation(self):
        state=DialogueState();state.media('şarkı aç')
        self.assertEqual(state.media('piyano değil')['kind'],'clarification')

class TaskReferenceTests(unittest.TestCase):
    def test_reference_requires_explicit_word_and_expires(self):
        now=[0];context=TaskContext(clock=lambda:now[0])
        context.record('rapor oluştur',{'status':'success','tool':'research_package','args':{'query':'enerji'},'response':'Dosya üretildi'})
        self.assertEqual(context.for_request('aynısını PDF yap')['actions'][0]['tool'],'research_package')
        self.assertIsNone(context.for_request('hava nasıl'))
        now[0]=601;self.assertIsNone(context.for_request('bunu PDF yap'))
    def test_failure_never_becomes_completed_task(self):
        context=TaskContext();context.record('rapor oluştur',{'status':'error','tool':'research_package','response':'hata'})
        self.assertIsNone(context.for_request('bunu PDF yap'))

class SpeechPolicyTests(unittest.TestCase):
    def test_short_mode_preserves_short_answer_and_drops_long_detail(self):
        from whisper.voice.speech_policy import SpeechPolicy
        p=SpeechPolicy()
        self.assertEqual(p.render('İşlem yapılmadı.'),'İşlem yapılmadı.')
        p.reset()
        value=p.render('Dosya bulunamadı. ' + 'Aranan klasörler ve sonuçlar. '*100)
        self.assertTrue(value.startswith('Dosya bulunamadı.'))
        self.assertLess(len(value),400)
        self.assertEqual(p.render('Daha fazla ayrıntı.'),'')
    def test_full_mode_preserves_requested_reading(self):
        from whisper.voice.speech_policy import SpeechPolicy
        text='Uzun açıklama. '*100
        self.assertEqual(SpeechPolicy('full').render(text),text)
    def test_url_and_code_are_not_read_as_raw_in_short_mode(self):
        from whisper.voice.speech_policy import SpeechPolicy
        result=SpeechPolicy().render('Kaynak: https://example.com/long\n```python\nprint(1)\n```\nİşlem yapılmadı.')
        self.assertNotIn('https',result);self.assertNotIn('print',result)
        self.assertIn('İşlem yapılmadı',result)
    def test_stream_budget_resets_on_new_turn(self):
        from whisper.voice.speech_policy import SpeechPolicy
        from whisper.voice.turn_control import TurnSpeech
        from types import SimpleNamespace
        from unittest.mock import Mock
        engine=SimpleNamespace(name='test',speak=Mock(return_value=True),stop=Mock())
        voice=TurnSpeech(engine,SpeechPolicy(budget=40))
        voice.begin();voice.speak('Kısa cevap.');voice.speak('Uzun bir açıklama. '*10)
        calls=engine.speak.call_count;voice.speak('Eski ayrıntı')
        self.assertEqual(engine.speak.call_count,calls)
        voice.begin();voice.speak('Yeni cevap.')
        self.assertEqual(engine.speak.call_args.args[0],'Yeni cevap.')
