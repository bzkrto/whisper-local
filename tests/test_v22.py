import json
import tempfile
import unittest
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from whisper.learning.knowledge import KnowledgeProcessor
from whisper.memory.research_memory import ResearchMemory
from whisper.tools.desktop_actions import validate_desktop,execute_desktop

class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'db.sqlite';self.memory=ResearchMemory(self.path)
        self.quote='Veriler kaynak adresi ile birlikte saklanır.'
        self.sid=self.memory.capture('Hafıza',self.quote+' Ek açıklama. '*40,[{'url':'https://example.com/doc'}],'autonomous_document')
        self.processor=KnowledgeProcessor(self.path,clock=lambda:1000)
        self.model=SimpleNamespace(base_url='http://localhost:11434/v1',model='qwen3:8b',chat=Mock(return_value=json.dumps({'summary':'Kaynaklı hafıza verileri adresleriyle birlikte tutar.','concepts':['hafıza','kaynak'], 'claims':[{'text':'Kayıt kaynak adresi içerir.','quote':self.quote}]})))
    def test_source_card_is_saved_recalled_and_not_reprocessed(self):
        self.assertEqual(self.processor.tick(self.model)['status'],'processed')
        self.assertIsNone(self.processor.tick(self.model))
        self.model.chat.assert_called_once()
        self.assertEqual(self.processor.recall('kaynak hafıza')[0]['source_id'],self.sid)
        self.assertIn('qwen3:8b',self.processor.report())
    def test_fabricated_quote_is_rejected_and_retry_delayed(self):
        self.model.chat.return_value=json.dumps({'summary':'Modelin kaynaksız uzun açıklaması.','concepts':[], 'claims':[{'text':'Uydurma iddia','quote':'Bu alıntı kaynakta kesinlikle bulunmuyor.'}]})
        self.assertEqual(self.processor.tick(self.model)['status'],'error')
        self.assertIsNone(self.processor.tick(self.model))
        self.assertEqual(self.processor.recall('kaynak hafıza'),[])
    def test_cloud_and_cancelled_calls_do_not_send_source(self):
        self.model.base_url='https://example.com'
        self.assertIsNone(self.processor.tick(self.model));self.model.chat.assert_not_called()
        self.model.base_url='http://localhost:11434/v1';stop=threading.Event();stop.set()
        self.assertIsNone(self.processor.tick(self.model,stop));self.model.chat.assert_not_called()
    def test_cancel_after_model_does_not_save_card(self):
        stop=threading.Event();value=self.model.chat.return_value
        self.model.chat.side_effect=lambda *a,**kw:(stop.set() or value)
        self.assertEqual(self.processor.tick(self.model,stop)['status'],'error')
        self.assertEqual(self.processor.recall('kaynak hafıza'),[])
    def test_malformed_output_reported_not_promoted(self):
        self.model.chat.return_value='[]'
        self.assertEqual(self.processor.tick(self.model)['status'],'error')
        self.assertIn('0 tanesi',self.processor.report())

class DesktopTests(unittest.TestCase):
    def test_invalid_actions_are_rejected_before_dispatch(self):
        for args in ({'action':'shell','value':'cmd'}, {'action':'click','value':[True,1]},
                     {'action':'type','value':'text\ncommand'}, {'action':'keys','value':'win_r'},
                     {'action':'scroll','value':100}, {'action':'capture','value':'arbitrary/path'}):
            with self.subTest(args=args),self.assertRaises(ValueError):validate_desktop(args)
    def test_actual_screen_bounds_and_dispatch_evidence(self):
        controller=Mock();controller._gui.return_value.size.return_value=(1920,1080)
        self.assertEqual(execute_desktop({'action':'click','value':[2000,10]},controller)['status'],'error')
        controller.execute.assert_not_called()
        controller.execute.return_value='Kaydırma gönderildi.'
        result=execute_desktop({'action':'scroll','value':-3},controller)
        self.assertEqual(result['status'],'dispatched')
        self.assertIn('not_goal_verified',result['verification'])
