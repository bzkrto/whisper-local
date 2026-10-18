import io,json,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from test_pipeline_regression import core
from whisper.core.action_agent import ActionAgent
class Tests(unittest.TestCase):
    def test_explicit_edge_on_windows_has_offline_backup(self):
        with patch.object(core.sys,'platform','win32'),patch.object(core,'EdgeTTS') as edge,patch.object(core,'SapiTTS') as sapi:
            edge.return_value.name='edge';sapi.return_value.name='sapi'
            result=core.build_tts(core.Config(tts_engine='edge',allow_cloud=True))
        self.assertIsInstance(result,core.ChainTTS)
        self.assertEqual(result.engines,[edge.return_value,sapi.return_value])
    def test_403_not_retried_and_service_skipped_for_next_utterance(self):
        with patch.dict('sys.modules',{'edge_tts':Mock()}):engine=core.EdgeTTS()
        class Forbidden(Exception):status=403
        async def generate(*args):raise Forbidden('403 Invalid response status')
        with patch.object(engine,'_generate',side_effect=generate) as call,patch.object(core.time,'monotonic',return_value=100),patch('sys.stdout',new=io.StringIO()):
            self.assertFalse(engine.speak('Hangi şarkıyı açmak istersiniz?'));self.assertFalse(engine.speak('Bergen araması.'))
        self.assertEqual(call.call_count,1);self.assertEqual(engine._unavailable_until,400)
    def test_failed_engine_falls_back_without_losing_question(self):
        first=Mock();first.name='edge';first.speak.side_effect=RuntimeError('service')
        backup=Mock();backup.name='sapi';backup.speak.return_value=True
        self.assertTrue(core.ChainTTS([first,backup]).speak('Hangi şarkıyı açmak istersiniz?'))
        backup.speak.assert_called_once_with('Hangi şarkıyı açmak istersiniz?')
    def test_cancel_during_online_failure_does_not_start_backup(self):
        stop=threading.Event();first=Mock();first.name='edge'
        def failed(text):stop.set();return False
        first.speak.side_effect=failed;backup=Mock();backup.name='sapi'
        chain=core.ChainTTS([first,backup]);chain.turn_cancelled=stop
        self.assertFalse(chain.speak('Soru'));backup.speak.assert_not_called()
    def test_sapi_initialized_and_used_on_own_worker_thread(self):
        calls=[]
        class Engine:
            def getProperty(self,key):return [SimpleNamespace(id='turkish',name='Turkish',languages=['tr-TR'])]
            def setProperty(self,key,value):
                self.assert_voice=(key,value)
                calls.append(('voice',threading.get_ident()))
            def say(self,text):calls.append(('say',threading.get_ident()))
            def startLoop(self,external):pass
            def iterate(self):pass
            def isBusy(self):return False
            def endLoop(self):pass
        def factory():calls.append(('init',threading.get_ident()));return Engine()
        with patch.dict('sys.modules',{'pyttsx3':SimpleNamespace(init=factory)}):
            engine=core.SapiTTS();self.assertTrue(engine.speak('Birinci soru'));self.assertTrue(engine.speak('İkinci soru'))
        self.assertEqual(len({i for _,i in calls}),1);self.assertNotIn(threading.get_ident(),{i for _,i in calls})
        self.assertEqual([name for name,_ in calls],['init','voice','say','say'])
    def test_sapi_initialization_failure_returns_promptly(self):
        with patch.dict('sys.modules',{'pyttsx3':SimpleNamespace(init=Mock(side_effect=RuntimeError('no voice')))}):
            engine=core.SapiTTS();self.assertFalse(engine.speak('Soru'));self.assertFalse(engine.speak('Soru'))
    def test_native_followup_carries_pending_music_intent(self):
        with tempfile.TemporaryDirectory() as folder:
            agent=ActionAgent(Path(folder)/'test.db')
            class Model:
                base_url='http://127.0.0.1:11434/v1'
                def __init__(self):self.calls=[]
                def chat_json(self,system,user,schema,max_tokens=None):
                    data=json.loads(user);self.calls.append(data)
                    if len(self.calls)==1:
                        return json.dumps({'intent':'play_music','entities':[{'type':'platform','value':'youtube'}],
                            'missing_fields':['artist_or_track'],'kind':'clarification','message':'Hangi şarkıyı veya sanatçıyı istersiniz?','steps':[]})
                    return json.dumps({'intent':'play_music','entities':[{'type':'artist','value':'Bergen'}],
                        'missing_fields':[],'kind':'action','message':'Sanatçı araması','steps':[{'tool':'youtube_search','args':{'query':'Bergen şarkıları'}}]})
            model=Model();execute=Mock(return_value={'status':'dispatched','response':'Arama açıldı.'})
            first=agent.execute("Youtube'dan bir şarkı açabilir misin?",model,[],execute)
            self.assertEqual(first['status'],'clarification')
            self.assertEqual(agent.dialogue.get()['interpretation']['intent'],'play_music')
            result=agent.execute('Bergen',model,[],execute)
            pending=model.calls[-1]['pending_clarification']
            self.assertEqual(pending['interpretation']['entities'][0]['value'],'youtube')
            self.assertEqual(pending['request'],"Youtube'dan bir şarkı açabilir misin?")
            execute.assert_called_once_with('youtube_search',{'query':'Bergen şarkıları'});self.assertEqual(result['status'],'success')
    def test_wake_acknowledgment_does_not_grant_ambient_permission(self):
        session=core.WakeSession('hey whisper');self.assertFalse(session.acknowledged)
        session.arm(10);self.assertTrue(session.acknowledged);self.assertTrue(session.active(11))
        self.assertEqual(session.accept('Bergen',11),'Bergen');self.assertFalse(session.active(12));self.assertIsNone(session.accept('Bergen',12))
