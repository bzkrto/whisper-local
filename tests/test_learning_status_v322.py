import json
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from test_pipeline_regression import core


class StatusTests(unittest.TestCase):
    def brain(self, path):
        with patch.object(core, 'detect_backend', return_value=None):
            return core.WhisperBrain(core.Config(db_path=str(path), tts_engine='none'))

    def test_misheard_daily_question_requests_confirmation_without_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.brain(Path(tmp)/'memory.db')
            with patch.object(b.web,'search') as search, patch.object(b.agent,'execute') as handle:
                result=b.process_command('Bugün neler ağlandı?')
                self.assertEqual(result['status'],'clarification')
                self.assertIn('Evet',result['response'])
                search.assert_not_called(); handle.assert_not_called()
                answer=b.process_command('Evet')
                self.assertEqual(answer['status'],'success')
                self.assertIn('belge bölümünü',answer['response'])
                search.assert_not_called()

    def test_confirmation_is_cleared_by_a_different_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.brain(Path(tmp)/'memory.db')
            b.process_command('Bugün neler ağlandı?')
            b.process_command('Saat kaç?')
            self.assertFalse(b._learning_summary_clarification)

    def test_today_processing_counts_old_sources_without_claiming_new_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.brain(Path(tmp)/'memory.db')
            sid=b.research_memory.capture('Türkçe bağlam','kaynak '*300,[{'url':'https://docs.python.org/'}],'autonomous_document')
            b.knowledge_processor.sync()
            card=json.dumps({'summary':'Kaynak destekli kısa açıklama.','concepts':[],'claims':[],'applications':[]})
            with sqlite3.connect(b.cfg.db_path) as db:
                db.execute("UPDATE knowledge_chunks SET state='done',card=?,processed_at=? WHERE source_id=?",(card,time.time(),sid))
            with patch.object(b.autonomous_research,'today') as detailed:
                result=b.process_command('Bugün neler öğrendin?')
            detailed.assert_not_called()
            self.assertIn('Bugün 0',result['response'])
            self.assertIn('Bugün 1 belge bölümünü',result['response'])
            self.assertIn('Kaynak destekli kısa açıklama',result['response'])
            self.assertLess(len(result['response']),900)

    def test_backlog_explains_why_no_new_documents_are_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.brain(Path(tmp)/'memory.db')
            with patch.object(b.knowledge_processor,'backlog',return_value=20):
                b.autonomous_research.processing_backlog=b.knowledge_processor.backlog
                status=b.autonomous_research.daily_status()
            self.assertIn('biriken belgeleri',status)
            b.autonomous_research.enable(False)
            self.assertNotIn('bekletiyorum',b.autonomous_research.daily_status())

    def test_today_ignores_processing_from_yesterday(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.brain(Path(tmp)/'memory.db')
            sid=b.research_memory.capture('Eski belge','kaynak '*300,[{'url':'https://docs.python.org/'}],'autonomous_document')
            b.knowledge_processor.sync()
            card=json.dumps({'summary':'Eski bilgi kartının açıklaması.'})
            with sqlite3.connect(b.cfg.db_path) as db:
                db.execute("UPDATE knowledge_chunks SET state='done',card=?,processed_at=? WHERE source_id=?",(card,time.time()-172800,sid))
            summary=b.knowledge_processor.daily_summary()
            self.assertIn('Bugün 0',summary)
            self.assertNotIn('Eski bilgi kartının',summary)


class SearchTests(unittest.TestCase):
    def test_fallback_backend_succeeds_and_uses_only_its_sources(self):
        memory=Mock(); memory.cache_get.return_value=None
        search=core.WebSearch(memory,core.Config(internet=True))
        calls=[]
        class Engine:
            def __init__(self,**kwargs): pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def text(self,query,**kwargs):
                calls.append(kwargs['backend'])
                if kwargs['backend']=='bing':raise RuntimeError('engine unavailable')
                return [{'title':'Belge','body':'Kaynak özeti','href':'https://docs.python.org/'}]
        with patch.dict(sys.modules,{'ddgs':SimpleNamespace(DDGS=Engine)}), patch.object(core,'check_internet',return_value=False) as probe:
            result=search.search('Python belge')
        self.assertIn('Kaynak özeti',result)
        self.assertEqual(calls,['bing','duckduckgo'])
        self.assertEqual(len(search.last_sources),1)
        probe.assert_not_called()
        memory.cache_set.assert_called_once()

    def test_all_failed_searches_remain_unverified_and_uncached(self):
        memory=Mock();memory.cache_get.return_value=None
        search=core.WebSearch(memory,core.Config(internet=True))
        class Engine:
            def __init__(self,**kwargs): pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def text(self,*args,**kwargs):raise RuntimeError('engine unavailable')
        with patch.dict(sys.modules,{'ddgs':SimpleNamespace(DDGS=Engine)}):
            self.assertEqual(search.search('Güncel haber'),'')
        self.assertEqual(search.last_sources,[])
        self.assertIn('bing',search.last_error)
        self.assertIn('duckduckgo',search.last_error)
        memory.cache_set.assert_not_called()
