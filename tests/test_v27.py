import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from whisper.learning.knowledge import KnowledgeProcessor
from whisper.learning.autonomy import AutonomousResearch,research_query
from whisper.memory.research_memory import ResearchMemory
from whisper.core.coding import produce_code

class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'memory.db'
        self.memory=ResearchMemory(self.path)
        self.processor=KnowledgeProcessor(self.path,clock=lambda:1000)
        self.quote='Use multi-factor authentication to protect account access.'
        self.data={'summary':'Parola güvenliğinde çok faktörlü kimlik doğrulama kullanılabilir.',
            'concepts':['parola','güvenlik','kimlik doğrulama'],
            'claims':[{'text':'Kaynak MFA öneriyor.','quote':self.quote}],
            'applications':[{'when':'Hesap güvenliğini planlarken','steps':['Çok faktörlü doğrulama seçeneklerini değerlendirin.'],'quote':self.quote}]}
        self.model=SimpleNamespace(base_url='http://localhost:11434/v1',model='qwen3:8b',chat=Mock(return_value=json.dumps(self.data)))
    def capture(self,body=None,kind='autonomous_document'):
        return self.memory.capture('password account security',body or self.quote,[{'url':'https://cheatsheetseries.owasp.org/example'}],kind)
    def test_english_source_becomes_turkish_card_with_application(self):
        sid=self.capture();self.assertEqual(self.processor.tick(self.model)['status'],'processed')
        card=self.processor.recall('parola güvenliği')[0]
        self.assertEqual(card['source_id'],sid)
        self.assertEqual(card['applications'][0]['quote'],self.quote)
        self.assertIn('İngilizce',self.model.chat.call_args.args[0])
    def test_all_saved_sections_are_processed_across_restarts(self):
        body=(self.quote+' ')*310
        self.capture(body)
        expected=len(range(0,len(body),8500))
        self.assertEqual(self.processor.backlog(),expected)
        for part in range(expected):
            result=self.processor.tick(self.model)
            self.assertEqual(result['part'],part)
            self.processor=KnowledgeProcessor(self.path,clock=lambda:1000)
        self.assertEqual(self.processor.backlog(),0)
        self.assertIsNone(self.processor.tick(self.model))
        self.assertIn('1 tanesi',self.processor.report())
    def test_old_first_section_card_is_preserved_and_remainder_queued(self):
        sid=self.capture((self.quote+' ')*310)
        with self.processor.connect() as db:
            db.execute('INSERT INTO knowledge_cards VALUES(?,?,?,?,?,?)',(sid,self.data['summary'],json.dumps(self.data['concepts']),json.dumps(self.data['claims']),'old-model',10))
            db.execute("INSERT INTO knowledge_jobs(source_id,state) VALUES(?,'done')",(sid,))
        self.processor.sync()
        with self.processor.connect() as db:
            self.assertEqual(db.execute('SELECT state,model FROM knowledge_chunks WHERE part=0').fetchone(),('done','old-model'))
        self.assertGreater(self.processor.backlog(),0)
        self.assertEqual(self.processor.tick(self.model)['part'],1)
    def test_search_snippets_are_not_promoted_but_articles_are_processed(self):
        self.capture(kind='search_excerpt')
        sid=self.capture(kind='article_snapshot')
        self.assertEqual(self.processor.tick(self.model)['source_id'],sid)
        self.assertIsNone(self.processor.tick(self.model))
    def test_fabricated_application_quote_rejected(self):
        self.capture();self.data['applications'][0]['quote']='An invented quote with no source evidence.'
        self.model.chat.return_value=json.dumps(self.data)
        self.assertEqual(self.processor.tick(self.model)['status'],'error')
        self.assertEqual(self.processor.recall('parola güvenliği'),[])
    def test_answer_uses_processed_card_and_returns_real_source(self):
        sid=self.capture();self.processor.tick(self.model)
        self.model.chat.return_value=json.dumps({'answer':'Kaynağa göre çok faktörlü doğrulamayı değerlendirebilirsiniz.','source_ids':[sid]})
        result=self.processor.answer('parola güvenliği',self.model)
        self.assertEqual(result['status'],'success');self.assertIn('cheatsheetseries.owasp.org',result['response'])
        self.assertFalse(result['answer_verified'])
    def test_unknown_answer_source_is_rejected(self):
        self.capture();self.processor.tick(self.model)
        self.model.chat.return_value=json.dumps({'answer':'Kaynağa göre bu iddia doğru.', 'source_ids':[999]})
        self.assertEqual(self.processor.answer('parola güvenliği',self.model)['status'],'error')
    def test_empty_recall_does_not_invent_knowledge(self):
        self.assertEqual(self.processor.answer('parola güvenliği',self.model)['status'],'not_found')
        self.model.chat.assert_not_called()
    def test_coder_receives_source_cards_without_executing_them(self):
        self.capture();self.processor.tick(self.model)
        self.model.chat.return_value='```python\nprint("draft")\n```'
        result=produce_code('Python ile parola formu yaz',self.model,self.path,threading.Event(),self.processor.recall('parola güvenliği'))
        self.assertIn(self.quote,self.model.chat.call_args.args[0])
        self.assertEqual(result['verification'],'file_written_not_executed')
    def test_research_backpressure_stops_new_documents(self):
        worker=AutonomousResearch(self.memory,reader=Mock())
        worker.processing_backlog=lambda:12
        self.assertEqual(worker.tick()['status'],'processing_backlog')
        worker.reader.assert_not_called()
    def test_security_sources_and_queries_use_primary_documentation(self):
        worker=AutonomousResearch(self.memory)
        with self.assertRaises(ValueError):worker.enqueue('https://example.com/course','Cybersecurity training')
        worker.enqueue('https://www.cisa.gov/resources-tools/resources/cyber-essentials','Cybersecurity training')
        self.assertIn('official cybersecurity',research_query('Siber güvenlik'))
        self.assertNotIn('belge dokümantasyon',research_query('OWASP security'))
        worker.set_profile('security')
        with worker.connect() as db:self.assertEqual(db.execute("SELECT value FROM autonomous_settings WHERE key='research_profile'").fetchone()[0],'security')
