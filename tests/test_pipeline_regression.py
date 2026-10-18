import sys,unittest,tempfile,importlib.util,io,json
from pathlib import Path
from unittest.mock import Mock,patch
# Load the native extension before patch.dict restores sys.modules after core import.
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
CORE_PATH=ROOT/'whisper_ses_v12.py' if (ROOT/'whisper_ses_v12.py').exists() else ROOT/'whisper_core.py'
with patch.dict(sys.modules,{'requests':Mock(),'sounddevice':Mock(),'speech_recognition':Mock()}):
    spec=importlib.util.spec_from_file_location('tested_whisper',CORE_PATH)
    core=importlib.util.module_from_spec(spec);sys.modules[spec.name]=core;spec.loader.exec_module(core)
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.model=Mock();self.model.model='qwen3:8b';self.model.name='fake';self.model.chat.return_value='Örnek bir açıklama.'
        cfg=core.Config(db_path=str(self.root/'test.db'),tts_engine='none',model='qwen3:8b',tts_sentence_stream=False)
        with patch.object(core,'detect_backend',return_value=self.model),patch('sys.stdout',new=io.StringIO()):self.brain=core.WhisperBrain(cfg)
    def test_v20_screenshot_website_uses_browser_not_file_or_model(self):
        self.brain.cfg.tools_enabled=True
        with patch('whisper.tools.browser.webbrowser.open',return_value=True) as launch, patch.object(self.brain,'file_manager',create=True) as finder:
            result=self.ask('x.com sitesini aç')
        launch.assert_called_once_with('https://x.com')
        finder.find_and_open.assert_not_called()
        self.assertEqual(result['status'],'dispatched')
        self.model.chat.assert_not_called()

    def test_v20_failed_browser_followup_uses_prior_url(self):
        self.brain.cfg.tools_enabled=True
        self.brain.cfg.allowed_apps={'brave':'C:/Apps/Brave.exe'}
        with patch('whisper.tools.browser.webbrowser.open',return_value=False):
            result=self.ask('www.x.com sitesini aç')
        self.assertEqual(result['status'],'clarification')
        with patch('whisper.tools.browser.subprocess.Popen') as launch:
            result=self.ask('brave kullan')
        launch.assert_called_once_with(['C:/Apps/Brave.exe','https://www.x.com'],shell=False)
        self.assertEqual(result['status'],'dispatched')
        self.assertIsNone(self.brain.agent.dialogue.get())

    def test_v20_wake_is_leading_explicit_single_turn(self):
        session=core.WakeSession('hey whisper')
        self.assertIsNone(session.accept('Whisper adlı bilgisayar asistanı.',1))
        self.assertIsNone(session.accept('Ben hey whisper dedim.',1))
        self.assertIsNone(session.accept('Osman yemek zamanı',1))
        self.assertEqual(session.accept('Hey Whisper, x.com sitesini aç',1),'x.com sitesini aç')
        session.refresh(2)
        self.assertIsNone(session.accept('Hadi yemek yiyelim',3))
        self.assertEqual(session.accept('Hey Whisper',4),'')
        session.arm(4)
        self.assertEqual(session.accept('Sistem bilgisi',5),'Sistem bilgisi')
        self.assertIsNone(session.accept('Başka biri konuşuyor',5.1))
        session.arm(10)
        self.assertIsNone(session.accept('Geç kaldım',16))
        self.assertEqual(core.Config().wake_word,'hey whisper')

    def test_v20_addressed_turkish_research_controls_skip_model(self):
        self.brain.cfg.internet=True
        self.brain.autonomous_research.enable(False)
        with patch.object(self.brain.autonomous_research,'start') as start:
            result=self.ask('whisper! araştırmaya devam et')
        self.assertEqual(result['status'],'success')
        self.assertTrue(self.brain.autonomous_research.enabled())
        start.assert_called_once()
        self.ask('Whisper, araştırmaya ara ver')
        self.assertFalse(self.brain.autonomous_research.enabled())
        self.model.chat.assert_not_called()

    def test_v21_music_mood_followup_reaches_encoded_youtube_search(self):
        self.brain.cfg.tools_enabled=True
        self.ask('şarkı aç')
        with patch.object(self.brain.tool_runner,'run',return_value='adres tarayıcıya gönderildi') as run:
            result=self.ask('dertli bir şey olsun')
        self.assertEqual(result['status'],'dispatched')
        from urllib.parse import parse_qs,urlsplit
        self.assertEqual(parse_qs(urlsplit(run.call_args.args[0].split('|',1)[1]).query)['search_query'],['Türkçe arabesk müzik'])
        self.model.chat.assert_not_called()
        self.assertEqual(self.brain.agent.task_context.for_request('aynısını aç')['actions'][0]['args']['query'],'Türkçe arabesk müzik')

    def test_v21_explicit_reference_is_sent_with_task_context_to_planner(self):
        self.brain.cfg.tools_enabled=True
        self.model.base_url='http://localhost:11434/v1'
        self.brain.agent.task_context.record('enerji raporu',{'status':'success','tool':'research_package','response':'Rapor hazır.'})
        self.model.chat.return_value=json.dumps({'kind':'action','message':'','steps':[{'tool':'export_report','args':{'format':'pdf'}}]})
        with patch.object(self.brain,'_agent_tool',return_value={'status':'success','response':'PDF hazır.'}) as run:
            result=self.ask('Aynısını PDF yap')
        payload=json.loads(self.model.chat.call_args.args[1])
        self.assertEqual(payload['referenced_task']['request'],'enerji raporu')
        run.assert_called_once_with('export_report',{'format':'pdf'})

    def test_v21_speech_mode_persists_without_changing_full_response(self):
        self.ask('Sesli yanıtları tam oku')
        self.assertEqual(self.brain.voice.policy.mode,'full')
        self.ask('Sesli yanıtları kısa tut')
        self.assertEqual(self.brain.voice.policy.mode,'short')
        import sqlite3
        with sqlite3.connect(self.brain.cfg.db_path) as db:
            self.assertEqual(db.execute("SELECT value FROM speech_preferences WHERE key='mode'").fetchone()[0],'short')

    def test_v21_listening_ack_can_speak_after_cancellation(self):
        self.brain.voice.cancel()
        with patch.object(self.brain.voice,'speak') as speak:
            self.brain._voice_notice('Sizi dinliyorum.')
        self.assertFalse(self.brain.voice.cancelled.is_set())
        speak.assert_called_once_with('Sizi dinliyorum.')

    def test_v22_desktop_tool_dispatches_only_when_enabled(self):
        self.brain.cfg.tools_enabled=True
        with patch('computer_control.ComputerControl.execute',return_value='Kaydırma gönderildi.') as run:
            result=self.brain._agent_tool('desktop',{'action':'scroll','value':-3})
        self.assertEqual(result['status'],'dispatched')
        run.assert_called_once_with('scroll',-3)
        self.brain.cfg.tools_enabled=False
        with patch('computer_control.ComputerControl.execute') as run:
            self.assertEqual(self.brain._agent_tool('desktop',{'action':'scroll','value':-3})['status'],'blocked')
        run.assert_not_called()

    def test_v22_background_model_processing_skips_busy_foreground(self):
        self.model.base_url='http://localhost:11434/v1'
        self.brain._command_lock.acquire()
        try:
            with patch.object(self.brain.knowledge_processor,'tick') as tick:
                self.assertIsNone(self.brain._process_knowledge_idle())
                tick.assert_not_called()
        finally:
            self.brain._command_lock.release()
        with patch.object(self.brain.knowledge_processor,'tick',return_value={'status':'processed'}) as tick:
            self.assertEqual(self.brain._process_knowledge_idle()['status'],'processed')
        tick.assert_called_once()

    def test_v22_learning_status_does_not_invent_processed_documents(self):
        result=self.ask('LLM öğrenme durumu')
        self.assertIn('0 tanesi',result['response'])
        self.model.chat.assert_not_called()

    def test_v23_vision_routes_and_restores(self):
        self.brain.cfg.tools_enabled=True;self.brain.cfg.screen_enabled=True
        vision=Mock();vision.model='qwen3-vl:4b';vision.base_url='http://localhost:11434/v1'
        vision.inspect_screen.return_value='Ekranda tarayıcı var.';original=self.brain.llm
        def choose(role):
            self.assertEqual(role,'vision');self.brain.llm=vision
        with patch.object(self.brain,'_select_role_model',side_effect=choose),patch('computer_control.ComputerControl.screenshot',return_value=b'jpeg'):
            result=self.brain._agent_tool('desktop',{'action':'inspect','value':'Ekranda ne var?'})
        self.assertEqual(result['model'],'qwen3-vl:4b');self.assertIs(self.brain.llm,original)
        vision.inspect_screen.assert_called_once_with(b'jpeg','Ekranda ne var?')

    def test_v23_missing_vision_does_not_capture(self):
        self.brain.cfg.tools_enabled=True;self.brain.cfg.screen_enabled=True;original=self.brain.llm
        with patch.object(self.brain,'_select_role_model'),patch('computer_control.ComputerControl.screenshot') as shot:
            result=self.brain._agent_tool('desktop',{'action':'inspect','value':'Ekranı oku'})
        self.assertEqual(result['status'],'blocked');shot.assert_not_called();self.assertIs(self.brain.llm,original)

    def test_v23_launcher_vision_role_is_valid(self):
        cfg=core.parse_args(['--role-model','chat=qwen3:8b','--role-model','code=qwen2.5-coder:7b','--role-model','vision=qwen3-vl:4b','--enable-screen'])
        self.assertEqual(cfg.model_roles['vision'],'qwen3-vl:4b');self.assertTrue(cfg.screen_enabled)

    def tearDown(self):self.tmp.cleanup()
    def test_profile_interview_does_not_capture_direct_pc_command(self):
        self.brain.cfg.tools_enabled=True
        self.ask('Tanışmaya başlayalım')
        with patch.object(self.brain.tool_runner,'run',return_value='adres tarayıcıya gönderildi'):
            self.ask('YouTube aç')
        self.assertEqual(self.brain.profile_interview.context(),'')
        self.ask('Osman')
        self.assertIn('hitap: Osman',self.brain.profile_interview.context())

    def test_service_start_refreshes_inventory_and_starts_worker_only_with_web(self):
        self.brain.cfg.internet=True
        with patch.object(self.brain.autonomous_research,'start') as start,patch.object(self.brain.voice,'speak') as speak,patch('whisper.tools.environment.inventory',return_value={'os':'Windows'}):
            self.brain.start_services()
        start.assert_called_once()
        self.assertEqual(self.brain.agent.environment_context,{'os':'Windows'})
        speak.assert_not_called()

    def test_local_model_prompt_receives_source_text_and_profile(self):
        self.model.base_url='http://localhost:11434/v1'
        self.brain.profile_interview.next_question()
        self.brain.profile_interview.handle('Osman')
        self.brain._knowledge_context=[{'source_id':4,'excerpt':'SQLite transactions','sources':[{'url':'https://docs.python.org/3.12/library/sqlite3.html'}]}]
        text=self.brain.system_prompt()
        self.assertIn('hitap: Osman',text)
        self.assertIn('SQLite transactions',text)
        self.model.base_url='https://example.com'
        text=self.brain.system_prompt()
        self.assertNotIn('SQLite transactions',text)
        self.assertNotIn('hitap: Osman',text)
    def test_learning_commands_feedback_approval_and_disable(self):
        engine=self.brain.agent.learning
        eid=engine.save('Sistem durumu',[{'tool':'system_info','status':'success','response':'ölçüldü'}],'review')
        self.assertEqual(self.ask(f'Deneyim sonucu: {eid}; başarısız')['status'],'success')
        self.assertIn('başarısız bulduğu: 1',self.ask('Öğrenme durumu')['response'])
        self.model.base_url='http://localhost:11434/v1'
        self.model.chat.return_value=json.dumps({'lessons':[{'source_ids':[eid],'lesson':'Sistem ölçümünün kapsamını kullanıcıyla netleştir.'}]})
        self.assertEqual(self.ask('Öğrenme analizi')['status'],'success')
        with engine.connect() as db:lid=db.execute("SELECT id FROM learning_lessons WHERE kind='hypothesis'").fetchone()[0]
        self.assertIn('Ders etkinleştirildi',self.ask(f'Dersi onayla: {lid}')['response'])
        self.assertIn(lid,[r['lesson_id'] for r in engine.context('Sistem durumu')])
        self.ask(f'Dersi pasifleştir: {lid}')
        self.assertNotIn(lid,[r['lesson_id'] for r in engine.context('Sistem durumu')])

    def test_five_direct_actions_create_experiences_and_automatic_draft_once(self):
        self.brain.cfg.tools_enabled=True
        self.model.base_url='http://localhost:11434/v1'
        self.model.chat.return_value=json.dumps({'lessons':[{'source_ids':[1],'lesson':'Sistem ölçümünün tarihini ve kapsamını göz önünde bulundur.'}]})
        with patch.object(self.brain.tool_runner,'run',return_value='disk boş alan 100 GB'),patch.object(self.brain.voice,'speak'):
            for _ in range(5):r=self.ask('sistem bilgisi')
        self.model.chat.assert_called_once()
        self.assertEqual(r['learning_analysis']['status'],'analyzed')
        self.assertEqual(len(r['learning_analysis']['draft_ids']),1)
        with self.brain.agent.learning.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM experiences').fetchone()[0],5)

    def test_invalid_short_correction_returns_message_without_crash(self):
        self.assertEqual(self.ask('Deneyim düzelt: 1; x')['status'],'clarification')
    def test_music_question_is_spoken_then_search_uses_encoded_title(self):
        self.brain.cfg.tools_enabled=True
        with patch.object(self.brain.voice,'speak') as speak,patch.object(self.brain.tool_runner,'run',return_value='adres tarayıcıya gönderildi') as run:
            result=self.ask("YouTube'dan şarkı aç")
            self.assertEqual(result['status'],'clarification')
            self.assertIn('hangi şarkıyı',speak.call_args.args[0])
            run.assert_not_called()
            result=self.ask('Barış Manço Gülpembe')
            self.assertEqual(result['status'],'dispatched')
            from urllib.parse import urlsplit,parse_qs
            query=parse_qs(urlsplit(run.call_args.args[0].split('|',1)[1]).query)
            self.assertEqual(query['search_query'],['Barış Manço Gülpembe'])
            self.assertFalse(result['playback_verified'])
            self.assertIn('arama sonuçlarını',speak.call_args.args[0])
        self.model.chat.assert_not_called()

    def test_disabled_music_and_new_direct_request_abandon_pending(self):
        with patch.object(self.brain.tool_runner,'run') as run:
            result=self.ask('şarkı aç')
        self.assertEqual(result['status'],'blocked');run.assert_not_called()
        self.brain.cfg.tools_enabled=True
        self.ask('şarkı aç')
        self.ask('Saat kaç?')
        self.assertIsNone(self.brain.agent.dialogue.get())

    def test_interrupt_clears_pending_question(self):
        self.brain.cfg.tools_enabled=True
        self.ask('şarkı aç')
        self.ask('Dur')
        self.assertIsNone(self.brain.agent.dialogue.get())

    def test_note_followup_reaches_model_with_pending_question_and_is_spoken(self):
        self.brain.cfg.tools_enabled=True
        self.model.base_url='http://localhost:11434/v1'
        self.model.chat.side_effect=[json.dumps({'kind':'clarification','message':'Ne not edeyim?','steps':[]}),
                                    json.dumps({'kind':'action','message':'','steps':[{'tool':'take_note','args':{'text':'Yarın malzeme al'}}]})]
        with patch.object(self.brain.voice,'speak') as speak,patch.object(self.brain,'_agent_tool',return_value={'status':'success','response':'Not kaydedildi.'}) as execute:
            self.assertEqual(self.ask('Bir not al')['status'],'clarification')
            execute.assert_not_called()
            self.assertEqual(speak.call_args.args[0],'Ne not edeyim?')
            self.assertEqual(self.ask('Yarın malzeme al')['status'],'success')
            payload=json.loads(self.model.chat.call_args.args[1])
            self.assertEqual(payload['pending_clarification']['request'],'Bir not al')
            self.assertIn('Not kaydedildi.',speak.call_args.args[0])
            execute.assert_called_once_with('take_note',{'text':'Yarın malzeme al'})
    def test_v24_calculator_skips_tool_planner_and_saves_python(self):
        self.brain.cfg.tools_enabled=True
        self.model.base_url='http://localhost:11434/v1'
        self.model.chat.return_value='```python\nprint(2 + 2)\n```'
        with patch.object(self.brain.agent,'execute') as planner, patch.object(self.brain,'_select_role_model', wraps=self.brain._select_role_model) as select:
            result=self.ask('bana bir hesap makinası kodlayabilir misin')
        planner.assert_not_called()
        self.assertIn(unittest.mock.call('code'),select.call_args_list)
        self.assertEqual(result['verification'],'file_written_not_executed')
        self.assertEqual(Path(result['artifacts'][0]['path']).read_text(),'print(2 + 2)\n')

    def test_v24_invalid_python_is_saved_as_text(self):
        self.model.base_url='http://localhost:11434/v1'
        self.model.chat.return_value='```python\nif (\n```'
        result=self.ask('Python kodu yaz')
        self.assertTrue(result['artifacts'][0]['path'].endswith('.txt'))
        self.assertIn('sözdizimi kontrolü başarısız',result['response'])

    def test_v24_coding_explanation_does_not_create_artifacts(self):
        self.model.base_url='http://localhost:11434/v1'
        result=self.ask('Python fonksiyonları nasıl çalışır?')
        self.assertEqual(result['artifacts'],[])
        self.assertFalse((self.root/'uretilen_kodlar').exists())

    def test_v25_code_request_waits_for_speech_or_background_lock(self):
        import threading
        self.model.base_url='http://localhost:11434/v1'
        self.model.chat.return_value='```python\nprint(4)\n```'
        self.brain._command_lock.acquire()
        results=[]
        worker=threading.Thread(target=lambda: results.append(self.ask('Python ile hesap makinesi kodla')))
        try:
            worker.start()
            self.assertTrue(self.brain._foreground_waiting.wait(2))
            self.model.chat.assert_not_called()
        finally:
            self.brain._command_lock.release()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results[0]['status'],'success')
        self.assertTrue(Path(results[0]['artifacts'][0]['path']).is_file())
        self.model.chat.assert_called_once()

    def test_v25_interrupt_cancels_waiting_request_without_replay(self):
        import threading
        self.brain._command_lock.acquire()
        results=[]
        worker=threading.Thread(target=lambda: results.append(self.ask('Python ile kod yaz')))
        try:
            worker.start()
            self.assertTrue(self.brain._foreground_waiting.wait(2))
            self.ask('Dur')
            worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertEqual(results[0]['status'],'cancelled')
            self.model.chat.assert_not_called()
            self.assertFalse(self.brain._foreground_waiting.is_set())
        finally:
            self.brain._command_lock.release()
            worker.join(2)

    def test_v25_background_learning_yields_to_waiting_user(self):
        self.brain._foreground_waiting.set()
        with patch.object(self.brain.knowledge_processor,'tick') as tick:
            self.assertIsNone(self.brain._process_knowledge_idle())
            tick.assert_not_called()
        self.assertEqual(self.brain.announce_reminders(),[])
        self.assertIsNone(self.brain.run_due_research())

    def test_v25_second_waiter_is_explicitly_rejected(self):
        self.brain._waiting_command_lock.acquire()
        try:
            result=self.ask('Python kodu yaz')
            self.assertEqual(result['status'],'busy')
            self.model.chat.assert_not_called()
        finally:
            self.brain._waiting_command_lock.release()

    def test_v27_disconnected_background_reconnects_before_processing(self):
        self.brain.llm=None
        def reconnect():
            self.model.base_url='http://localhost:11434/v1'
            self.brain.llm=self.model
            return True
        with patch.object(self.brain,'_ensure_llm',side_effect=reconnect) as ensure, patch.object(self.brain.knowledge_processor,'tick',return_value=None) as tick:
            self.brain._process_knowledge_idle()
        ensure.assert_called_once();tick.assert_called_once()

    def test_v27_processing_status_explains_disconnected_llm(self):
        self.brain.llm=None
        result=self.ask('Bilgi işleme durumu')
        self.assertIn('LLM bağlı değil',result['response'])

    def test_v27_explicit_knowledge_answer_bypasses_tool_planner(self):
        with patch.object(self.brain.knowledge_processor,'answer',return_value={'status':'not_found','response':'Kart yok.'}) as answer,patch.object(self.brain.agent,'execute') as planner:
            self.ask('Bilgilerinden yanıtla: parola güvenliği')
        answer.assert_called_once();planner.assert_not_called()

    def test_v27_natural_question_receives_cards_before_tool_planner(self):
        cards=[{'source_id':1,'summary':'Parola güvenliği ve kimlik doğrulama.'}]
        with patch.object(self.brain.knowledge_processor,'recall',return_value=cards),patch.object(self.brain.knowledge_processor,'answer',return_value={'status':'success','response':'Kaynaklı öneri.'}) as answer,patch.object(self.brain.agent,'execute') as planner:
            self.ask('Parola güvenliği nedir?')
        answer.assert_called_once();planner.assert_not_called()

    def test_v27_manual_processing_works_while_research_paused(self):
        self.model.base_url='http://localhost:11434/v1'
        self.brain.autonomous_research.enable(False)
        with patch.object(self.brain.knowledge_processor,'tick',return_value={'status':'processed','source_id':1}) as tick:
            self.assertEqual(self.ask('Bilgileri işle')['status'],'success')
        self.assertIs(tick.call_args.args[1],self.brain.voice.cancelled)

    def test_v28_natural_training_request_reaches_durable_task_brain(self):
        with patch('whisper.core.task_brain.TaskBrain.run',return_value={'status':'success','response':'Görev hazır','spoken_response':'Hazır','artifacts':[]}) as run:
            result=self.ask('Siber güvenlik eğitimi hazırla')
        self.assertEqual(result['status'],'success');run.assert_called_once()
        from whisper.core.task_brain import TaskBrain
        self.assertEqual(TaskBrain(self.brain.cfg.db_path).load(1)[0],'Siber güvenlik eğitimi hazırla')
    def test_v28_native_short_artist_request_uses_semantic_agent(self):
        class Model:
            base_url='http://127.0.0.1:11434/v1'
            model='qwen3:8b'
            name='Ollama'
            def chat_json(self,system,user,schema,max_tokens=None):
                return json.dumps({'intent':'play_music','entities':[{'type':'artist','value':'Bergen'}],
                    'missing_fields':[],'kind':'action','message':'Sanatçı araması',
                    'steps':[{'tool':'youtube_search','args':{'query':'Bergen şarkıları'}}]})
        self.brain.llm=Model();self.brain.cfg.tools_enabled=True
        with patch.object(self.brain,'_agent_tool',return_value={'status':'dispatched','response':'Arama gönderildi.'}) as tool:
            result=self.ask('Bergen aç')
        self.assertEqual(result['interpretation']['intent'],'play_music')
        tool.assert_called_once_with('youtube_search',{'query':'Bergen şarkıları'})

    def ask(self,text):
        with patch('sys.stdout',new=io.StringIO()):return self.brain.process_command(text)
    def test_production_command_requires_tools_enabled(self):
        self.brain.cfg.tools_enabled=False
        result=self.ask('PDF üretim paketi: karar değişimi')
        self.assertEqual(result['status'],'blocked')
        self.model.chat.assert_not_called()

    def test_research_package_requires_web_without_contact(self):
        self.brain.cfg.tools_enabled=True
        self.brain.cfg.internet=False
        with patch.object(self.brain.web,'search') as search:
            result=self.ask('Araştırma paketi: batarya')
        self.assertEqual(result['status'],'blocked')
        search.assert_not_called()
        self.model.chat.assert_not_called()

    def test_research_package_real_dispatch_and_record(self):
        self.brain.cfg.tools_enabled=True
        self.brain.cfg.internet=True
        with patch.object(self.brain.web,'search',return_value='Batarya kaynak özeti'), \
             patch.object(self.brain.web,'last_sources',[{'url':'https://example.com/batarya'}],create=True):
            result=self.ask('Araştırma paketi: batarya')
        self.assertEqual(result['status'],'success')
        self.assertEqual(len(result['artifacts']),4)
        self.assertIn('Erişim zamanı',Path(result['artifacts'][0]['path']).read_text())
        state=self.ask('Üretim durumu: '+str(result['run_id']))
        self.assertEqual(state['status'],'success')
        self.model.chat.assert_not_called()


    def test_goal_command_real_dispatch_and_feedback(self):
        self.brain.cfg.tools_enabled=True
        self.model.base_url='http://localhost:11434/v1'
        self.model.chat.side_effect=[json.dumps({'kind':'action','message':'','steps':[{'tool':'system_info','args':{}}]}),
                                    json.dumps({'kind':'chat','message':'İnceleme','steps':[]})]
        with patch.object(self.brain,'_agent_tool',return_value={'status':'success','response':'RAM ölçüldü'}):
            result=self.ask('Hedef: Sistem durumunu incele')
        self.assertEqual(result['status'],'review')
        self.assertEqual(self.ask('Deneyim düzelt: '+str(result['experience_id'])+'; Önce disk ölçümüne bak')['status'],'success')
        self.assertIn('Önce disk',self.ask('Deneyimlerim')['response'])

    def test_code_goal_dispatch_restores_model_and_restricts_tools(self):
        self.brain.cfg.tools_enabled=True
        self.model.base_url='http://localhost:11434/v1'
        self.model.chat.return_value=json.dumps({'kind':'action','message':'','steps':[{'tool':'set_volume','args':{'level':40}}]})
        with patch.object(self.brain,'_select_role_model'),patch.object(self.brain,'_agent_tool') as executor:
            result=self.ask('Kod geliştir: Türkçe yanıt temizleme modülünü düzelt')
        self.assertEqual(result['status'],'blocked');executor.assert_not_called()
        self.assertIs(self.brain.llm,self.model)
    def test_natural_name_memory_survives_reopen(self):
        for statement in ('Benim adım Osman. Bunu hatırla.', 'Benim adım Osman, bunu hafızana at ve hatırla.', 'İsmim Osman Bozkurt'):
            r=self.ask(statement);self.assertEqual(r['source'],'KAYNAK_HAFIZA')
        from whisper.core.reasoning import AssistantLayers
        reopened=AssistantLayers(self.root/'test.db')
        self.assertEqual('Adınız Osman Bozkurt.',reopened.intercept('Benim adım ne?')['response'])
        self.model.chat.assert_not_called()
    def test_questions_do_not_save_fake_names(self):
        self.ask('Benim adım ne?');self.ask('Adım neydi?')
        self.assertEqual(self.brain.layers.store.knowledge('personality'),[])
    def test_explicit_hardware_memory_without_model(self):
        self.ask('RTX 5070 kullanıyorum, bunu hatırla.')
        self.assertIn('RTX 5070',self.ask('Benim ekran kartım neydi?')['response'])
        self.model.chat.assert_not_called()
    def test_silence_setting_validated(self):
        cfg=core.parse_args(['--silence-seconds','0.5'])
        self.assertEqual(cfg.silence_seconds,0.5)
        with patch('sys.stderr',new=io.StringIO()),self.assertRaises(SystemExit):core.parse_args(['--silence-seconds','0'])
    def test_unexecuted_model_action_is_blocked(self):
        self.model.chat.return_value='Efendim, komutu çalıştırıyorum. [ARAÇ: calistir | x]'
        r=self.ask('Bir Python kod örneği ver')
        self.assertEqual(r['status'],'blocked');self.assertNotIn('çalıştırıyorum',r['response'])
    def test_powershell_install_never_goes_to_model(self):
        r=self.ask('python -m pip install pypdf')
        self.assertEqual(r['status'],'clarification');self.model.chat.assert_not_called()
    def test_stream_guard_suppresses_claim_before_speech(self):
        self.brain._last_model_action_blocked=False
        r=self.brain._guard_model_speech('Komutu çalıştırıyorum.')
        self.assertIn('çalıştırmadım',r)
        self.assertEqual(self.brain._guard_model_speech('Komutu çalıştırdım.'),'')
        self.assertEqual(self.brain._guard_model_speech('Python kodunu şöyle çalıştırabilirsiniz.'),'Python kodunu şöyle çalıştırabilirsiniz.')
    def test_time_bypasses_model(self):
        r=self.ask('Saat kaç?');self.assertTrue(r['fast']);self.model.chat.assert_not_called()
    def test_existing_file_route_bypasses_model(self):
        from whisper.tools.file_manager import FileManager
        p=self.root/'rapor.pdf';p.write_text('sample');opener=Mock()
        with patch('whisper.tools.file_manager.default_roots',return_value=[]):self.brain.file_manager=FileManager([self.root],opener)
        self.brain.cfg.tools_enabled=True
        r=self.ask('rapor dosyasını aç');self.assertEqual(r['tool'],'dosya_ac')
        opener.assert_called_once_with(str(p));self.model.chat.assert_not_called()
    def test_multi_action_sentence_reaches_agent_before_file_search(self):
        self.brain.cfg.tools_enabled=True
        self.model.base_url='http://127.0.0.1:11434/v1'
        self.model.chat.return_value=json.dumps({'kind':'action','message':'', 'steps':[
            {'tool':'open_app','args':{'name':'chrome'}}, {'tool':'set_volume','args':{'level':50}}]})
        with patch.object(self.brain,'_agent_tool',return_value={'status':'dispatched','response':'İstek gönderildi.'}) as execute:
            r=self.ask('Chrome aç ve sesi elliye getir')
        self.assertEqual(r['route']['target'],'agent');self.assertEqual(execute.call_count,2)
    def test_interrupt_bypasses_busy_command_lock(self):
        self.brain._command_lock.acquire()
        try:
            r=self.ask('Dur')
            self.assertEqual(r['status'],'cancelled');self.assertTrue(self.brain.voice.cancelled.is_set())
        finally:self.brain._command_lock.release()
    def test_speech_onset_callback_fires_before_recording_finishes(self):
        import numpy as np
        listener=core.MicListener(samplerate=16000,silence_seconds=0.3)
        onset=Mock()
        class Stream:
            def __enter__(self):
                for i in range(30):
                    listener._q.put(np.ones(480,dtype=np.float32)*(0.05 if i<18 else 0.0))
            def __exit__(self,*args):pass
        with patch.object(listener,'_active_stream',return_value=Stream()):
            audio=listener.listen_once(0.01,prompt='',start_timeout=1,on_speech_start=onset)
        onset.assert_called_once();self.assertIsNotNone(audio)
    def test_agent_export_records_written_file(self):
        self.brain.cfg.tools_enabled=True
        p=self.root/'raporlar'/'example.docx'
        with patch('whisper.tools.report_export.export_report',return_value=p) as export:
            result=self.brain._agent_tool('export_report',{'format':'word'})
        self.assertEqual(result['verification'],'file_written');self.assertEqual(export.call_args.args[2],'docx')
    def test_hardware_memory_bypasses_model(self):
        self.ask('Hafızaya kaydet: hardware = RTX 5070')
        r=self.ask('Benim ekran kartım neydi?');self.assertIn('RTX 5070',r['response']);self.model.chat.assert_not_called()
    def test_performance_report_no_invented_timings(self):
        r=self.ask('Performans durumu');self.assertIn('henüz ölçülmedi',r['response']);self.model.chat.assert_not_called()
    def test_short_complex_query_budget(self):
        r=self.ask('Bilgisayar neden yavaşlıyor?');self.assertEqual(self.model.chat.call_args.kwargs['max_tokens'],400)
        self.assertEqual(r['response'],'Örnek bir açıklama.')
    def test_current_information_failed_search_not_hallucinated(self):
        with patch.object(self.brain.web,'search',return_value=''):
            r=self.ask('Bugün NVIDIA ne duyurdu?')
        self.assertEqual(r['status'],'unverified');self.model.chat.assert_not_called()
    def test_native_stream_metrics_and_nonthinking_payload(self):
        llm=core.OllamaLLM('http://127.0.0.1:11434/v1','qwen3:8b')
        response=Mock();response.status_code=200;response.__enter__=Mock(return_value=response);response.__exit__=Mock()
        response.iter_lines.return_value=[json.dumps({'message':{'content':'Merhaba'}}).encode(),json.dumps({'done':True,'eval_duration':2000000000}).encode()]
        with patch.object(core.requests,'post',return_value=response) as post:
            self.assertEqual(''.join(llm.chat_stream('system','user')),'Merhaba')
        self.assertEqual(llm.last_metrics['eval_duration'],2)
        self.assertFalse(post.call_args.kwargs['json']['think'])
if __name__=='__main__':unittest.main()
