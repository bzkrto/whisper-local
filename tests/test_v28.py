import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock
from whisper.core.task_brain import TaskBrain, command_intent, STAGES
from whisper.core.structured import parse_object, request, obj, string, grounded_card

class LocalModel:
    base_url='http://127.0.0.1:11434/v1'
    model='qwen3:8b'
    def __init__(self):self.calls=[]
    def chat_json(self,system,user,schema,max_tokens=None):
        payload=json.loads(user);self.calls.append(payload)
        if 'source_domains' in payload:
            return json.dumps({'checks':[{'claim':'Çok faktörlü doğrulama öneriliyor.','source_ids':[payload['cards'][0]['source_id']],
                'assessment':'agreement','reason':'Verilen kaynak kartında bu öneri bulunuyor.'}]})
        if 'evidence' in payload:
            key=int(next(iter(payload['evidence'])))
            return json.dumps({'summary':'Çok faktörlü doğrulama, hesap güvenliğini güçlendirmeye yardımcı olur.',
                'concepts':['hesap güvenliği','çok faktörlü doğrulama'],
                'claims':[{'text':'Çok faktörlü doğrulama kullanılması öneriliyor.','evidence_id':key}],
                'applications':[{'when':'Hesap erişimini korumak için','steps':['Çok faktörlü doğrulama seçeneğini değerlendirin.'],'evidence_id':key}]})
        return json.dumps({'title':'Hesap güvenliği eğitimi','sections':[
            {'title':heading,'paragraphs':['Kaynakta çok faktörlü doğrulamanın hesap erişimini korumak için kullanılması öneriliyor.'],
             'source_ids':[payload['cards'][0]['source_id']]} for heading in ('Öğrenme hedefleri','Konu anlatımı','Uygulama ve değerlendirme')],
            'limitations':['Bu çalışma okunabilen kaynaklarla sınırlıdır; gerçek sistem üzerinde işlem yapılmadı.']})

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'test.db';self.brain=TaskBrain(self.path);self.model=LocalModel()
        self.search=Mock(return_value={'status':'success','research_id':1,'sources':[{'url':'https://www.nist.gov/cyberframework','title':'NIST'}]})
        self.body=('Use multi-factor authentication to protect account access. '*8)
        self.reader=Mock(return_value={'url':'https://www.nist.gov/cyberframework','body':self.body,'partial':False})
    def run_task(self,tid,**kw):return self.brain.run(tid,self.model,self.search,reader=self.reader,**kw)
    def test_full_workflow_creates_real_office_and_pdf_files(self):
        tid=self.brain.create('Siber güvenlik eğitimi hazırla');out=self.run_task(tid)
        self.assertEqual(out['status'],'success',out['response'])
        artifacts={a['format']:Path(a['path']) for a in out['artifacts']}
        self.assertEqual(set(artifacts),{'md','docx','pdf','pptx'})
        self.assertTrue(artifacts['pdf'].read_bytes().startswith(b'%PDF'))
        from docx import Document
        self.assertIn('Hesap güvenliği',Document(artifacts['docx']).paragraphs[0].text)
        from pypdf import PdfReader
        self.assertGreater(len(PdfReader(artifacts['pdf']).pages),0)
        with zipfile.ZipFile(artifacts['pptx']) as z:
            self.assertIsNone(z.testzip());self.assertTrue(any(n.startswith('ppt/slides/slide') for n in z.namelist()))
        self.assertIn('https://www.nist.gov',artifacts['md'].read_text())
        self.assertEqual(self.brain.load(tid)[2]['completed'],list(STAGES))
    def test_restart_resumes_export_without_research_or_llm_replay(self):
        from whisper.tools.report_export import export_report
        failed=[False]
        def exporter(db,name,fmt):
            if fmt=='pdf' and not failed[0]:failed[0]=True;raise RuntimeError('Simüle edilmiş disk hatası')
            return export_report(db,name,fmt)
        tid=self.brain.create('Siber güvenlik eğitimi hazırla')
        out=self.run_task(tid,exporter=exporter);self.assertEqual(out['status'],'error')
        calls=len(self.model.calls);self.brain=TaskBrain(self.path)
        out=self.run_task(tid,exporter=exporter)
        self.assertEqual(out['status'],'success',out['response']);self.assertEqual(len(self.model.calls),calls)
        self.search.assert_called_once();self.reader.assert_called_once()
        self.assertEqual(len(out['artifacts']),4)
    def test_unread_sources_cannot_become_report(self):
        self.reader.side_effect=ValueError('Kaynak erişilemiyor')
        tid=self.brain.create('Siber güvenlik eğitimi hazırla');out=self.run_task(tid)
        self.assertEqual(out['status'],'error');self.assertEqual(out['artifacts'],[]);self.assertEqual(self.model.calls,[])
    def test_cancelled_task_can_resume(self):
        cancel=threading.Event();cancel.set();tid=self.brain.create('Eğitim hazırla')
        self.assertEqual(self.run_task(tid,cancelled=cancel)['status'],'cancelled')
        cancel.clear();self.assertEqual(self.run_task(tid,cancelled=cancel)['status'],'success')
    def test_active_owner_prevents_duplicate_execution(self):
        tid=self.brain.create('Eğitim hazırla')
        with self.brain.connect() as db:db.execute('UPDATE brain_tasks SET owner=?,lease=? WHERE id=?',('other',self.brain.clock()+100,tid))
        self.assertEqual(self.run_task(tid)['status'],'busy');self.search.assert_not_called()
    def test_expired_owner_recovers(self):
        tid=self.brain.create('Eğitim hazırla')
        with self.brain.connect() as db:db.execute('UPDATE brain_tasks SET owner=?,lease=? WHERE id=?',('old',1,tid))
        self.assertEqual(self.run_task(tid)['status'],'success')
    def test_completed_task_is_not_reexecuted_and_missing_file_is_reported(self):
        tid=self.brain.create('Eğitim hazırla');out=self.run_task(tid)
        Path(out['artifacts'][0]['path']).unlink()
        self.assertEqual(self.run_task(tid)['status'],'partial');self.search.assert_called_once()
    def test_security_rejects_unofficial_search_sources(self):
        self.search.return_value['sources']=[{'url':'https://example.com/security'}]
        out=self.run_task(self.brain.create('Siber güvenlik eğitimi hazırla'))
        self.assertEqual(out['status'],'error');self.reader.assert_not_called()
    def test_synthesis_cannot_invent_source_ids(self):
        original=self.model.chat_json
        def bad(system,user,schema,max_tokens=None):
            raw=original(system,user,schema,max_tokens)
            if 'cards' in json.loads(user):
                data=json.loads(raw);data['sections'][0]['source_ids']=[999];return json.dumps(data)
            return raw
        self.model.chat_json=bad
        out=self.run_task(self.brain.create('Eğitim hazırla'))
        self.assertEqual(out['status'],'error');self.assertEqual(out['artifacts'],[])
    def test_native_cards_bind_original_english_quotes(self):
        card=grounded_card(self.model,self.body)
        self.assertIn(card['claims'][0]['quote'],self.body)
        self.assertNotIn('evidence_id',card['claims'][0])
    def test_json_think_fence_and_prefix(self):
        self.assertEqual(parse_object('<think>reasoning</think>\n```JSON\n{"answer":"ok"}\n```'),{'answer':'ok'})
        self.assertEqual(parse_object('Yanıt: {"answer":"ok"}'),{'answer':'ok'})
        for bad in ('', '{"a":', '{"a":1}{"b":2}', '<think>{"a":1}</think>'):
            with self.assertRaises(ValueError):parse_object(bad)
    def test_structured_repair_is_bounded(self):
        model=Mock();model.chat.side_effect=['not JSON','{"answer":"İkinci yanıt geçerli"}']
        self.assertEqual(request(model,'Test',{},obj({'answer':string()}))['answer'],'İkinci yanıt geçerli')
        self.assertEqual(model.chat.call_count,2)
        model=Mock();model.chat.return_value=''
        with self.assertRaises(ValueError):request(model,'Test',{},obj({'answer':string()}))
        self.assertEqual(model.chat.call_count,2)
    def test_goal_detection_and_status_commands(self):
        self.assertEqual(command_intent('Siber güvenlik eğitimi hazırla')[0],'create')
        self.assertEqual(command_intent('Göreve devam et: 12'),('resume',12))
        self.assertIsNone(command_intent('YouTube aç'))
        self.assertIsNone(command_intent('PDF üretim paketi: belge 1; öğrenme'))

    def test_unrelated_background_source_does_not_replace_task_evidence(self):
        other=self.brain.research.capture('Fizik', 'Unrelated physics source text. '*15,[{'url':'https://example.com/physics'}],'autonomous_document')
        tid=self.brain.create('Siber güvenlik eğitimi hazırla');out=self.run_task(tid)
        self.assertEqual(out['status'],'success')
        self.assertNotIn(other,{c['source_id'] for c in self.brain.load(tid)[2]['cards']})
        with self.brain.knowledge.connect() as db:
            self.assertEqual(db.execute('SELECT state FROM knowledge_chunks WHERE source_id=?',(other,)).fetchone()[0],'pending')
    def test_same_size_artifact_tampering_is_detected(self):
        tid=self.brain.create('Eğitim hazırla');out=self.run_task(tid)
        path=Path(out['artifacts'][0]['path']);raw=path.read_bytes();path.write_bytes(b'x'+raw[1:])
        self.assertEqual(self.brain.result(tid)['status'],'partial')
    def test_failed_read_can_resume_without_search_replay(self):
        self.reader.side_effect=ValueError('Geçici erişim hatası');tid=self.brain.create('Eğitim hazırla')
        self.assertEqual(self.run_task(tid)['status'],'error')
        self.reader.side_effect=None
        self.assertEqual(self.run_task(tid)['status'],'success');self.search.assert_called_once()
    def test_cancel_during_inference_does_not_promote_knowledge(self):
        cancel=threading.Event();original=self.model.chat_json
        def interrupted(*args,**kwargs):
            raw=original(*args,**kwargs);cancel.set();return raw
        self.model.chat_json=interrupted
        tid=self.brain.create('Eğitim hazırla');out=self.run_task(tid,cancelled=cancel)
        self.assertEqual(out['status'],'cancelled');self.assertEqual(out['artifacts'],[])
        with self.brain.knowledge.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM knowledge_chunks WHERE state='done'").fetchone()[0],0)
    def test_broken_office_export_is_not_marked_complete(self):
        def exporter(db,name,fmt):
            path=Path(self.tmp.name)/('broken.'+fmt);path.write_text('not an office document');return path
        tid=self.brain.create('Eğitim hazırla');out=self.run_task(tid,exporter=exporter)
        self.assertEqual(out['status'],'error');self.assertNotIn('Dosyaları oluştur',self.brain.load(tid)[2]['completed'])

class SemanticTests(unittest.TestCase):
    def setUp(self):
        from whisper.core.action_agent import ActionAgent
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.agent=ActionAgent(Path(self.tmp.name)/'test.db')
        class Planner:
            base_url='http://127.0.0.1:11434/v1'
            model='qwen3:8b'
            def __init__(self):self.inputs=[];self.output={}
            def chat_json(self,system,user,schema,max_tokens=None):
                self.inputs.append(json.loads(user));return json.dumps(self.output)
        self.model=Planner();self.executor=Mock(return_value={'status':'dispatched','response':'YouTube araması tarayıcıya gönderildi.'})
    def plan(self,query,artist='Bergen'):
        return {'intent':'play_music','entities':[{'type':'artist','value':artist}], 'missing_fields':[],
            'kind':'action','message':'Sanatçı için müzik ara','steps':[{'tool':'youtube_search','args':{'query':query}}]}
    def test_short_artist_request_extracts_entities_and_dispatches_validated_tool(self):
        self.model.output=self.plan('Bergen şarkıları')
        result=self.agent.execute('Bergen aç',self.model,[],self.executor)
        self.executor.assert_called_once_with('youtube_search',{'query':'Bergen şarkıları'})
        self.assertEqual(result['interpretation']['entities'][0]['value'],'Bergen')
        self.assertNotIn('çalınıyor',result['response'])
    def test_change_music_receives_previous_task_and_conversation(self):
        self.model.output=self.plan('Bergen şarkıları');self.agent.execute('Bergen aç',self.model,[],self.executor)
        self.model.output=self.plan('Müslüm Gürses şarkıları','Müslüm Gürses')
        self.agent.execute('Değiştir, başkasını aç',self.model,[],self.executor,
            context=[{'user':'Bergen aç','assistant':'YouTube araması gönderildi.'}])
        payload=self.model.inputs[-1]
        self.assertEqual(payload['referenced_task']['actions'][0]['args']['query'],'Bergen şarkıları')
        self.assertEqual(payload['recent_conversation'][0]['user'],'Bergen aç')
    def test_ambiguous_entity_asks_without_execution(self):
        self.model.output={'intent':'ambiguous','entities':[{'type':'name','value':'Bergen'}], 'missing_fields':['entity_type'],
            'kind':'clarification','message':'Bergen adlı sanatçıyı mı yoksa şehri mi kastediyorsunuz?','steps':[]}
        result=self.agent.execute('Bergen',self.model,[],self.executor)
        self.assertEqual(result['status'],'clarification');self.executor.assert_not_called()
    def test_extracted_intent_cannot_bypass_tool_validation(self):
        self.model.output=self.plan('Bergen');self.model.output['steps']=[{'tool':'shell','args':{'command':'bad'}}]
        result=self.agent.execute('Bergen aç',self.model,[],self.executor)
        self.assertEqual(result['status'],'error');self.executor.assert_not_called()

class TransportTests(unittest.TestCase):
    setUp = Tests.setUp
    # Exercise the actual HTTP adapter and the full durable pipeline together.
    def test_ollama_http_format_and_full_task_pipeline(self):
        from urllib.request import Request, urlopen
        class HTTPTransport:
            @staticmethod
            def post(url,json,headers,timeout,allow_redirects):
                import json as codec
                response=urlopen(Request(url,codec.dumps(json).encode(),headers,method='POST'),timeout=timeout)
                class Response:
                    status_code=response.status
                    text=response.read().decode()
                    def json(self):return codec.loads(self.text)
                    def __enter__(self):return self
                    def __exit__(self,*args):response.close()
                return Response()
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        from unittest.mock import patch
        from test_pipeline_regression import core
        fixture=self.model;received=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                received.append((self.path,payload))
                raw=fixture.chat_json(payload['messages'][0]['content'],payload['messages'][1]['content'],payload.get('format'))
                output=json.dumps({'message':{'content':raw},'done':True,'done_reason':'stop'}).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(output)));self.end_headers();self.wfile.write(output)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            model=core.OllamaLLM(f'http://127.0.0.1:{server.server_port}/v1','qwen3:8b',timeout=3)
            with patch.object(core,'requests',HTTPTransport):
                result=self.brain.run(self.brain.create('Siber güvenlik eğitimi hazırla'),model,self.search,reader=self.reader)
            self.assertEqual(result['status'],'success',result['response'])
            self.assertEqual(len(received),3)
            for path,payload in received:
                self.assertEqual(path,'/api/chat');self.assertIsInstance(payload['format'],dict)
                self.assertFalse(payload['think']);self.assertFalse(payload['stream']);self.assertEqual(payload['options']['temperature'],0)
        finally:server.shutdown();server.server_close();thread.join(2)

class ProfileTests(unittest.TestCase):
    def setUp(self):
        from whisper.memory.profile_fusion import ProfileMemory
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'profile.db';self.profile=ProfileMemory(self.path,clock=lambda:1000)
        with self.profile.connect() as db:db.execute('CREATE TABLE conversation_history(id INTEGER PRIMARY KEY,user_command TEXT)')
        class Model:
            base_url='http://127.0.0.1:11434/v1'
            model='qwen3:8b'
            def chat_json(self,*args,**kw):return json.dumps(self.data)
        self.model=Model();self.model.data={'facts':[{'slot':'hardware.ram','value':'32 GB RAM','quote':'32 GB RAM kullanıyorum'}]}
    def say(self,text):
        with self.profile.connect() as db:db.execute('INSERT INTO conversation_history(user_command) VALUES(?)',(text,))
    def test_profile_extraction_persists_and_updates_from_real_user_quote(self):
        self.say('Bilgisayarımda 32 GB RAM kullanıyorum.')
        self.assertEqual(self.profile.tick(self.model)['status'],'processed')
        self.assertEqual(self.profile.context()[0]['value'],'32 GB RAM')
        self.say('Artık 64 GB RAM kullanıyorum.');self.model.data['facts'][0].update(value='64 GB RAM',quote='64 GB RAM kullanıyorum')
        self.profile.tick(self.model);self.assertEqual(self.profile.context()[0]['value'],'64 GB RAM')
        self.assertIsNone(self.profile.tick(self.model))
    def test_fabricated_user_fact_is_rejected(self):
        self.say('Bergen aç')
        self.assertEqual(self.profile.tick(self.model)['status'],'error');self.assertEqual(self.profile.context(),[])
    def test_forget_prevents_relearning_old_conversations(self):
        self.say('32 GB RAM kullanıyorum');self.profile.tick(self.model);self.profile.clear()
        self.assertEqual(self.profile.context(),[]);self.assertIsNone(self.profile.tick(self.model))
    def test_empty_profile_does_not_invent_hardware(self):
        self.say('Sistemimde çalışır mı?');self.model.data={'facts':[]}
        self.assertEqual(self.profile.tick(self.model)['status'],'processed');self.assertEqual(self.profile.context(),[])

class ResearchAnswerTests(unittest.TestCase):
    setUp=Tests.setUp
    def test_knowledge_gap_research_answers_without_unrequested_files(self):
        tid=self.brain.create('Hesap güvenliği nasıl sağlanır?',kind='answer')
        result=self.brain.run(tid,self.model,self.search,reader=self.reader)
        self.assertEqual(result['status'],'success',result['response'])
        self.assertEqual(result['artifacts'],[]);self.assertIn('https://www.nist.gov',result['response'])
        self.assertNotIn('Dosyaları oluştur',self.brain.load(tid)[2]['plan'])

class VerificationTests(unittest.TestCase):
    setUp=Tests.setUp
    def test_single_domain_never_promoted_to_cross_verified_truth(self):
        tid=self.brain.create('Eğitim hazırla');result=self.brain.run(tid,self.model,self.search,reader=self.reader)
        self.assertEqual(result['verification']['checks'][0]['assessment'],'insufficient')
        self.assertFalse(result['verification']['truth_verified']);self.assertTrue(result['verification']['review_needed'])
