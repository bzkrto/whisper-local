import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import whisper_ses_v12 as core
from whisper.voice.profile import uncertain_fragment
from whisper.memory.turkish import TurkishMemory


class ConversationTests(unittest.TestCase):
    def test_conversation_follows_up_without_repeating_wake_word(self):
        s=core.WakeSession('hey whisper',timeout=20,conversation=True)
        self.assertIsNone(s.accept('Merhaba',1))
        self.assertEqual(s.accept('Hey Whisper, merhaba',2),'merhaba')
        s.refresh(40)  # Model/TTS time does not consume the user's response interval.
        self.assertEqual(s.accept('Biraz daha anlat',45),'Biraz daha anlat')
        s.refresh(50)
        self.assertIsNone(s.accept('Ortam konuşması',71))

    def test_end_conversation_closes_followup(self):
        s=core.WakeSession('hey whisper',timeout=20,conversation=True)
        s.arm(1)
        self.assertEqual(s.accept('Sohbeti bitir',2),'__conversation_end__')
        s.refresh(3)
        self.assertFalse(s.active(4)); self.assertIsNone(s.accept('Başka biri',4))

    def test_single_turn_mode_still_requires_new_activation(self):
        s=core.WakeSession('hey whisper',conversation=False)
        self.assertEqual(s.accept('Hey Whisper, merhaba',1),'merhaba')
        s.refresh(2); self.assertIsNone(s.accept('Yeni komut',3))

    def test_names_and_short_replies_preserved_with_context(self):
        self.assertTrue(uncertain_fragment('Bergen'))
        self.assertFalse(uncertain_fragment('Bergen',contextual=True))
        self.assertFalse(uncertain_fragment('Chrome',known_words=['Chrome']))
        self.assertTrue(uncertain_fragment('Zort'))

    def test_cli_voice_selection_and_conversation_settings(self):
        cfg=core.parse_args(['--tts','none','--voice','tr-TR-EmelNeural','--conversation-timeout','30'])
        self.assertTrue(cfg._voice_explicit); self.assertTrue(cfg.conversation_mode)
        self.assertEqual(cfg.conversation_timeout,30)
        self.assertFalse(core.parse_args(['--single-turn']).conversation_mode)

    def test_vocabulary_survives_restart_and_enriches_local_stt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'memory.db'; memory=TurkishMemory(path)
            memory.teach_word('Bergen'); memory.teach_word('Türkçe bağlam')
            reopened=TurkishMemory(path)
            self.assertIn('Bergen',reopened.hints('',[]))
            self.assertIn('Türkçe bağlam',reopened.vocabulary())
            with self.assertRaises(ValueError): reopened.teach_word('x\nkomut')

    def test_general_questions_use_local_model_without_internet(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg=core.Config(db_path=str(Path(tmp)/'memory.db'),tts_engine='none',tts_sentence_stream=False)
            model=Mock(base_url='http://localhost:11434/v1',model='test',name='test')
            model.chat.return_value='Su, normal basınçta sıfır santigrat derecede donar.'
            with patch.object(core,'detect_backend',return_value=model): brain=core.WhisperBrain(cfg)
            with patch.object(brain.web,'search') as search:
                result=brain.process_command('Su kaç derecede donar?')
            self.assertEqual(result['status'],'success'); search.assert_not_called(); model.chat.assert_called()
            self.assertFalse(brain.web.needs_internet('Python nedir?'))
            self.assertTrue(brain.web.needs_internet('Bugün hava nasıl?'))

    def test_v321_migrates_saved_emel_to_male_profile_once(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/'memory.db')
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE speech_preferences(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
                db.executemany('INSERT INTO speech_preferences VALUES(?,?)', [('voice','tr-TR-EmelNeural'),('rate','+0%'),('voice_revision','32')])
            with patch.object(core,'detect_backend',return_value=None):
                brain=core.WhisperBrain(core.Config(db_path=path,tts_engine='none'))
            self.assertEqual((brain.cfg.voice,brain.cfg.voice_rate,brain.cfg.voice_pitch),('en-US-BrianMultilingualNeural','+0%','+0Hz'))
            with sqlite3.connect(path) as db:
                db.executemany('INSERT OR REPLACE INTO speech_preferences VALUES(?,?)', [('voice','tr-TR-EmelNeural'),('rate','+0%'),('pitch','+0Hz')])
            with patch.object(core,'detect_backend',return_value=None):
                reopened=core.WhisperBrain(core.Config(db_path=path,tts_engine='none'))
            self.assertEqual((reopened.cfg.voice,reopened.cfg.voice_rate,reopened.cfg.voice_pitch),('tr-TR-EmelNeural','+0%','+0Hz'))

    def test_explicit_pitch_overrides_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/'memory.db')
            with patch.object(core,'detect_backend',return_value=None):
                core.WhisperBrain(core.Config(db_path=path,tts_engine='none'))
                cfg=core.parse_args(['--tts','none','--pitch=-4Hz'])
                cfg.db_path=path
                selected=core.WhisperBrain(cfg)
                reopened=core.WhisperBrain(core.Config(db_path=path,tts_engine='none'))
            self.assertEqual(selected.cfg.voice_pitch,'-4Hz')
            self.assertEqual(reopened.cfg.voice_pitch,'-4Hz')

    def test_explicit_voice_overrides_old_saved_preference(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'memory.db'
            import sqlite3
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE speech_preferences(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
                db.execute("INSERT INTO speech_preferences VALUES('voice','tr-TR-AhmetNeural')")
            cfg=core.parse_args(['--tts','none','--voice','tr-TR-EmelNeural'])
            cfg.db_path=str(path)
            with patch.object(core,'detect_backend',return_value=None): brain=core.WhisperBrain(cfg)
            self.assertEqual(brain.cfg.voice,'tr-TR-EmelNeural')

    def test_selected_voice_persists_after_v32_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/'memory.db')
            with patch.object(core,'detect_backend',return_value=None):
                brain=core.WhisperBrain(core.Config(db_path=path,tts_engine='none'))
            import sqlite3
            with sqlite3.connect(path) as db:
                db.execute("INSERT OR REPLACE INTO speech_preferences VALUES('voice','tr-TR-AhmetNeural')")
            with patch.object(core,'detect_backend',return_value=None):
                reopened=core.WhisperBrain(core.Config(db_path=path,tts_engine='none'))
            self.assertEqual(reopened.cfg.voice,'tr-TR-AhmetNeural')

    def test_chat_view_receives_both_turns(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(core,'detect_backend',return_value=None):
                brain=core.WhisperBrain(core.Config(db_path=str(Path(tmp)/'memory.db'),tts_engine='none'))
            observer=Mock();brain.conversation_observer=observer
            result=brain.process_command('Saat kaç?')
            self.assertEqual(observer.call_args_list[0].args,('user','Saat kaç?'))
            self.assertEqual(observer.call_args_list[-1].args,('assistant',result['response']))

    def test_separate_coding_endpoint_is_local_and_selected(self):
        cfg=core.parse_args(['--tts','none','--role-model','code=qwen-coder',
                            '--role-base-url','code=http://127.0.0.1:8081/v1'])
        with tempfile.TemporaryDirectory() as tmp:
            cfg.db_path=str(Path(tmp)/'memory.db')
            with patch.object(core,'detect_backend',return_value=Mock()):brain=core.WhisperBrain(cfg)
            brain._select_role_model('code')
            self.assertEqual(brain.llm.model,'qwen-coder')
            self.assertEqual(brain.llm.base_url,'http://127.0.0.1:8081/v1')

    def test_decoder_schema_keeps_structure_and_validation_retains_bounds(self):
        from whisper.core.structured import transport_schema,validate,obj,string
        schema=obj({'code':string(1,16000)})
        transport=transport_schema(schema)
        self.assertNotIn('maxLength',transport['properties']['code'])
        self.assertEqual(schema['properties']['code']['maxLength'],16000)
        with self.assertRaises(ValueError):validate({'code':'x'*16001},schema)

    def test_local_backup_never_reads_turkish_with_an_english_voice(self):
        from types import SimpleNamespace
        engine=Mock();engine.getProperty.return_value=[SimpleNamespace(id='english',name='English',languages=['en-US'])]
        with patch.dict('sys.modules',{'pyttsx3':SimpleNamespace(init=lambda:engine)}):
            voice=core.SapiTTS()
            self.assertFalse(voice.speak('Türkçe bir cümle'))
        engine.say.assert_not_called()


if __name__=='__main__': unittest.main()
