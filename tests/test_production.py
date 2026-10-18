"""Real store/retrieval/export integration with a deterministic model double."""
import ast
import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from whisper.core.production import ProductionWorkflow
from whisper.memory.document_memory import DocumentMemory
from whisper.common import fold

from whisper.memory.user_memory import LayerStore as StoreFixture

class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = StoreFixture(Path(self.tmp.name) / 'memory.db')
        DocumentMemory(self.store)
        self.workflow = ProductionWorkflow(self.store)
        self.llm = Mock(base_url='http://127.0.0.1:11434/v1', model='test-model')
        self.llm.chat.return_value = json.dumps({'answer': 'Karar değişimi yeni bilgiyle ilişkili olabilir.',
            'insufficient': False, 'citations': [{'id':'S1','quote_id':'Q1'}]}, ensure_ascii=False)
        with self.store.connect() as db:
            db.execute("INSERT INTO documents VALUES(1,'davranış.pdf','hash',2,2,'now')")
            for page in (1, 2):
                text = 'Karar değişimi yeni bilgi ve koşullarla ilişkili olabilir. Şüphe, ölçüm ve öğrenme.'
                db.execute('INSERT INTO document_chunks VALUES(?,?,?,?)', (1,page,text,fold(text)))

    def run_package(self): return self.workflow.run('belge 1; sayfa 2; karar değişimi', self.llm)

    def test_four_real_files_sources_and_persistent_status(self):
        from docx import Document
        from pypdf import PdfReader
        result = self.run_package()
        self.assertEqual(result['status'], 'success')
        paths = {a['format']: Path(a['path']) for a in result['artifacts']}
        self.assertEqual(set(paths), {'md','docx','pdf','pptx'})
        self.assertTrue(all(p.is_file() for p in paths.values()))
        word = '\n'.join(p.text for p in Document(paths['docx']).paragraphs)
        pdf = '\n'.join(p.extract_text() for p in PdfReader(paths['pdf']).pages)
        with zipfile.ZipFile(paths['pptx']) as z:
            self.assertIsNone(z.testzip())
            text = ' '.join(n.text or '' for name in z.namelist() if name.startswith('ppt/slides/slide') and name.endswith('.xml')
                            for n in ET.fromstring(z.read(name)).iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t'))
        for body in (word,pdf,text):
            self.assertIn('davranış.pdf',body)
            self.assertIn('sayfa 2',body)
        fresh = ProductionWorkflow(self.store).show(result['run_id'])
        self.assertEqual(fresh['artifacts'], result['artifacts'])
        self.assertFalse(fresh['answer_verified'])
        self.llm.chat.assert_called_once()

    def test_no_sources_does_not_call_model_or_export(self):
        result = self.workflow.run('uzay kolonileri', self.llm)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['artifacts'], [])
        self.llm.chat.assert_not_called()

    def test_fabricated_citation_does_not_create_files(self):
        self.llm.chat.return_value=json.dumps({'answer':'Yanıt','insufficient':False,
                                              'citations':[{'id':'S99','quote_id':'Q1'}]})
        result=self.run_package()
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(result['artifacts'],[])

    def test_remote_model_not_given_document(self):
        self.llm.base_url='https://example.com/v1'
        self.assertEqual(self.run_package()['status'],'blocked')
        self.llm.chat.assert_not_called()

    def test_model_exception_or_bad_json_no_false_success(self):
        self.llm.chat.side_effect=TimeoutError()
        self.assertEqual(self.run_package()['status'],'blocked')
        self.llm.chat.side_effect=None
        self.llm.chat.return_value='bad JSON'
        self.assertEqual(self.run_package()['status'],'blocked')

    def test_partial_export_keeps_other_outputs(self):
        with patch('whisper.tools.report_export._word',side_effect=ImportError('docx')):
            result=self.run_package()
        self.assertEqual(result['status'],'partial')
        self.assertEqual({a['format'] for a in result['artifacts']},{'md','pdf','pptx'})
        self.assertIn('python-docx',result['response'])
        self.assertNotIn('Dört dosya hazır',result['spoken_response'])

    def test_failed_markdown_prevents_exports(self):
        with patch('whisper.core.production.save_answer_report',return_value={'status':'error'}), \
             patch('whisper.core.production.export_report') as export:
            result=self.run_package()
        self.assertEqual(result['status'],'error')
        export.assert_not_called()

    def test_deleted_output_no_longer_reported_ready(self):
        result=self.run_package()
        Path(result['artifacts'][0]['path']).unlink()
        fresh=self.workflow.show(result['run_id'])
        self.assertEqual(fresh['status'],'partial')
        self.assertEqual(len(fresh['missing_artifacts']),1)
        self.assertNotIn('Dört dosya hazır',fresh['spoken_response'])

    def test_routes_and_empty_input(self):
        self.assertIsNone(self.workflow.intercept('merhaba'))
        self.assertEqual(self.workflow.intercept('PDF üretim paketi:  ')['status'],'clarification')
        result=self.workflow.intercept('PDF üretim paketi: belge 1; karar değişimi')
        self.assertEqual(result['production_request'],'belge 1; karar değişimi')
        self.assertEqual(self.workflow.intercept('Üretim durumu: 999')['status'],'error')
        self.assertEqual(self.workflow.intercept('Üretimlerim')['response'],'Kayıtlı üretim yok.')

    def test_repeated_runs_do_not_overwrite_files(self):
        first=self.run_package(); second=self.run_package()
        self.assertNotEqual(first['run_id'],second['run_id'])
        self.assertFalse({a['path'] for a in first['artifacts']} & {a['path'] for a in second['artifacts']})

    def test_symlink_output_directory_rejected(self):
        external=Path(self.tmp.name)/'external';external.mkdir()
        (Path(self.tmp.name)/'raporlar').symlink_to(external,target_is_directory=True)
        result=self.run_package()
        self.assertEqual(result['status'],'error')
        self.assertEqual(list(external.iterdir()),[])
        self.llm.chat.assert_not_called()

    def test_interrupted_record_not_reported_complete(self):
        with self.store.connect() as db:
            rid=db.execute('INSERT INTO production_runs(request,created_at,state,steps,artifacts,sources) '
                           'VALUES(?,?,?,?,?,?)',('konu','now','running','[]','[]','[]')).lastrowid
        result=self.workflow.show(rid)
        self.assertEqual(result['status'],'running')
        self.assertIn('tamamlandı sayılmaz',result['response'])

    def test_existing_command_pipeline_hook_executes_workflow(self):
        # Extract the real layer-handling branch without importing absent desktop/audio modules.
        tree=ast.parse((ROOT/'whisper_ses_v12.py').read_text())
        branch=next(n for n in ast.walk(tree) if isinstance(n,ast.If) and ast.unparse(n.test)=='layer is not None')
        method=ast.FunctionDef(name='dispatch',args=ast.arguments(posonlyargs=[],args=[ast.arg(arg='self'),ast.arg(arg='layer')],
            kwonlyargs=[],kw_defaults=[],defaults=[]),body=[branch],decorator_list=[])
        namespace={};exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),'pipeline','exec'),namespace)
        app=SimpleNamespace(layers=SimpleNamespace(store=self.store),llm=self.llm,voice=Mock())
        app._agent_tool=lambda tool,args: self.workflow.run(args['query'],self.llm)
        result=namespace['dispatch'](app,{'production_request':'karar değişimi'})
        self.assertEqual(result['status'],'success')
        app.voice.speak.assert_called_once()

    def test_cancel_before_start_calls_no_model_and_writes_no_artifacts(self):
        import threading
        stop=threading.Event();stop.set()
        result=self.workflow.run('karar değişimi',self.llm,cancelled=stop)
        self.assertEqual(result['status'],'cancelled')
        self.assertEqual(result['artifacts'],[])
        self.llm.chat.assert_not_called()

    def test_cancel_during_model_prevents_report(self):
        import threading
        stop=threading.Event()
        reply=self.llm.chat.return_value
        def respond(*a,**k):
            stop.set()
            return reply
        self.llm.chat.side_effect=respond
        result=self.workflow.run('karar değişimi',self.llm,cancelled=stop)
        self.assertEqual(result['status'],'cancelled')
        self.assertEqual(result['artifacts'],[])

    def test_cancel_after_word_preserves_it_and_skips_other_formats(self):
        import threading
        from whisper.tools.report_export import export_report
        stop=threading.Event()
        def export(*args):
            path=export_report(*args);stop.set();return path
        with patch('whisper.core.production.export_report',side_effect=export):
            result=self.workflow.run('karar değişimi',self.llm,cancelled=stop)
        self.assertEqual(result['status'],'cancelled')
        self.assertEqual({a['format'] for a in result['artifacts']},{'md','docx'})

    def test_research_uses_exact_record_not_latest(self):
        from whisper.memory.research_memory import ResearchMemory
        memory=ResearchMemory(self.store.path)
        rid=memory.capture('batarya','Batarya araştırma özeti.',[{'url':'https://example.com/batarya','title':'Batarya'}])
        memory.capture('alakasız','ALAKASIZ KAYIT',[{'url':'https://example.com/other'}])
        researcher=Mock(return_value={'status':'success','research_id':rid})
        result=self.workflow.run('batarya',self.llm,research=researcher)
        self.assertEqual(result['status'],'success')
        self.assertEqual(len(result['artifacts']),4)
        md=Path(result['artifacts'][0]['path']).read_text()
        self.assertIn('Batarya araştırma özeti.',md)
        self.assertIn('https://example.com/batarya',md)
        self.assertNotIn('ALAKASIZ',md)
        self.assertIn('Erişim zamanı',md)
        self.assertEqual(result['document_sources'],[])
        self.assertEqual(result['sources'][0]['url'],'https://example.com/batarya')
        self.llm.chat.assert_not_called()

    def test_research_failure_or_missing_identity_no_files(self):
        for evidence in ({'status':'blocked','response':'Web kapalı'}, {'status':'success'},
                         {'status':'success','research_id':999}):
            result=self.workflow.run('batarya',self.llm,research=Mock(return_value=evidence))
            self.assertNotEqual(result['status'],'success')
            self.assertEqual(result['artifacts'],[])

    def test_invalid_research_url_not_exported(self):
        from whisper.memory.research_memory import ResearchMemory
        memory=ResearchMemory(self.store.path)
        rid=memory.capture('batarya','özet',[{'url':'file:///private'}])
        result=self.workflow.run('batarya',self.llm,research=Mock(return_value={'status':'success','research_id':rid}))
        self.assertEqual(result['status'],'error')
        self.assertEqual(result['artifacts'],[])

    def test_research_exception_on_cancel_stays_cancelled(self):
        import threading
        stop=threading.Event()
        def search(query):
            stop.set();raise RuntimeError('cancel')
        result=self.workflow.run('batarya',self.llm,research=search,cancelled=stop)
        self.assertEqual(result['status'],'cancelled')

    def test_semantic_plan_accepts_package_but_rejects_extra_actions(self):
        from whisper.core.action_agent import validate_plan
        for name in ('pdf_package','research_package'):
            plan={'kind':'action','message':'','steps':[{'tool':name,'args':{'query':'batarya'}}]}
            self.assertEqual(validate_plan(plan,set()),plan)
            plan['steps'][0]['args']['shell']='anything'
            with self.assertRaises(ValueError):validate_plan(plan,set())

    def test_agent_preserves_partial_result_and_stops_later_steps(self):
        from whisper.core.action_agent import ActionAgent
        plan={'kind':'action','message':'','steps':[{'tool':'pdf_package','args':{'query':'karar'}},
                                                  {'tool':'take_note','args':{'text':'bitti'}}]}
        model=Mock(base_url='http://localhost:11434',chat=Mock(return_value=json.dumps(plan)))
        executor=Mock(return_value={'status':'partial','response':'Word yok','artifacts':[{'format':'md','path':'example'}]})
        result=ActionAgent(self.store.path).execute('PDF raporu hazırla',model,[],executor)
        self.assertEqual(result['status'],'partial')
        executor.assert_called_once()
        self.assertEqual(len(result['artifacts']),1)

if __name__=='__main__': unittest.main()
