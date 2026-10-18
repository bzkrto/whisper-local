import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from test_pipeline_regression import core
from whisper.memory.turkish import TurkishMemory, concepts
from whisper.memory.research_memory import ResearchMemory
from whisper.learning.autonomy import AutonomousResearch, read_document, public_url


class TurkishTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.path=Path(t.name)/'db'
        core.MemoryEngine(str(self.path))
        self.memory=TurkishMemory(self.path)
        self.research=ResearchMemory(self.path)
        self.worker=AutonomousResearch(self.research,clock=lambda:200000)

    def test_phrase_survives_restart_but_is_not_automatically_executed(self):
        self.memory.teach('Çalışma alanımı getir','Chrome aç')
        self.assertEqual(TurkishMemory(self.path).meaning('çalışma alanımı getir!'),'Chrome aç')
        self.assertIsNone(self.memory.meaning('farklı istek'))

    def test_concept_recall_remembers_equivalent_terms(self):
        core.MemoryEngine(str(self.path)).save_interaction('Bellek sorunu konuşalım','RAM ölçümünü kontrol et.')
        rows=self.memory.recall('Hafıza hatası')
        self.assertEqual(len(rows),1)
        self.assertIn('RAM',rows[0]['assistant'])

    def test_hotwords_only_use_name_and_app_catalog(self):
        hints=self.memory.hints('hitap: Osman\nis: Mühendis\nhedef: gizli hedef',['Chrome','VS Code'])
        self.assertIn('Osman',hints);self.assertIn('Chrome',hints);self.assertNotIn('gizli',hints)

    def test_no_daily_cap_and_security_profile_has_priority(self):
        with self.worker.connect() as db:
            self.assertEqual(db.execute("SELECT value FROM autonomous_settings WHERE key='daily_limit'").fetchone()[0],'0')
        reader=Mock(side_effect=lambda url,stop:{'url':url,'body':'Cybersecurity security source text '*30,'links':[],'partial':False})
        self.worker.reader=reader
        self.worker.set_profile('security')
        self.worker.tick()
        self.assertIn('learn.microsoft.com',reader.call_args.args[0])

    def test_daily_report_uses_today_actual_sources_and_rejects_fake_model_source(self):
        sid=self.research.capture('Türkçe','Yazım bilgisi '*40,[{'url':'https://yazim.tdk.gov.tr/'}],'autonomous_document')
        with self.worker.connect() as db:
            db.execute("INSERT INTO autonomous_reads(url,at,status,source_id,detail) VALUES(?,?,'read',?,'')",('https://yazim.tdk.gov.tr/',200000,sid))
        model=SimpleNamespace(base_url='http://localhost:11434',chat=Mock(return_value=json.dumps({'items':[{'source_id':999,'summary':'Uydurulmuş bilgi içeriyor.'}]})))
        report=self.worker.today(model)
        self.assertIn('1 farklı kaynak',report);self.assertIn('özeti alınamadı',report);self.assertNotIn('Uydurulmuş',report)

    def test_no_documents_report_does_not_claim_learning_or_call_model(self):
        model=Mock(base_url='http://localhost:11434')
        self.assertIn('henüz',self.worker.today(model));model.chat.assert_not_called()

    def test_new_public_domains_allowed_but_private_dns_rejected(self):
        self.assertEqual(public_url('https://example.org/belge'),'https://example.org/belge')
        fake=Mock()
        with patch.dict('sys.modules',{'requests':fake}),patch('socket.getaddrinfo',return_value=[(2,1,6,'',('192.168.1.2',443))]),self.assertRaises(ValueError):
            read_document('https://example.org/belge',threading.Event())
        fake.get.assert_not_called()

    def test_pace_is_persistent(self):
        self.worker.pace(120)
        with self.worker.connect() as db:
            self.assertEqual(db.execute("SELECT value FROM autonomous_settings WHERE key='interval_seconds'").fetchone()[0],'120')


class MobileTests(unittest.TestCase):
    def setUp(self):
        self.brain=SimpleNamespace(process_command=Mock(return_value={'status':'success','response':'aynı beyin yanıtı'}))
        handler=type('TestBridge',(core._BridgeHandler,),{'brain':self.brain,'token':'test-secret','artifacts':{}})
        self.server=core.ThreadingHTTPServer(('127.0.0.1',0),handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)

    def request(self,method,path,body=None,auth=True):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        headers={'Authorization':'Bearer test-secret'} if auth else {}
        if body is not None:headers['Content-Type']='application/json'
        c.request(method,path,body=json.dumps(body) if body is not None else None,headers=headers)
        r=c.getresponse();data=r.read();status=r.status;c.close();return status,data

    def test_ui_contains_no_embedded_token_or_model_generated_html(self):
        status,body=self.request('GET','/',auth=False)
        self.assertEqual(status,200);self.assertNotIn(b'test-secret',body);self.assertIn(b'textContent',body)

    def test_unauthenticated_command_never_reaches_brain(self):
        status,_=self.request('POST','/mesaj',{'text':'YouTube aç'},auth=False)
        self.assertEqual(status,401);self.brain.process_command.assert_not_called()

    def test_authenticated_mobile_uses_same_command_processor(self):
        with patch.object(core,'_bridge_rate_limited',return_value=False):
            status,data=self.request('POST','/mesaj',{'text':'Bugün neler öğrendin?'})
        self.assertEqual(status,200);self.assertEqual(json.loads(data)['yanit'],'aynı beyin yanıtı')
        self.brain.process_command.assert_called_once_with('Bugün neler öğrendin?')

    def test_stop_is_not_throttled(self):
        with patch.object(core,'_bridge_rate_limited',return_value=True):
            status,_=self.request('POST','/mesaj',{'text':'Dur'})
        self.assertEqual(status,200);self.brain.process_command.assert_called_once_with('Dur')

    def test_only_registered_artifact_can_be_downloaded_with_auth(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'report.txt';path.write_text('rapor')
            self.brain.process_command.return_value={'status':'success','response':'hazır','artifacts':[{'path':str(path)}]}
            with patch.object(core,'_bridge_rate_limited',return_value=False):
                _,raw=self.request('POST','/mesaj',{'text':'rapor oluştur'})
            url=json.loads(raw)['dosyalar'][0]['url']
            self.assertEqual(self.request('GET',url,auth=False)[0],401)
            self.assertEqual(self.request('GET',url),(200,b'rapor'))
            self.assertEqual(self.request('GET','/dosya/../../secret')[0],404)
