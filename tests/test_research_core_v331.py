"""Offline queue regressions: focus selection and source-backed draft discovery."""
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from whisper.memory.research_memory import ResearchMemory
from whisper.learning.autonomy import AutonomousResearch
from whisper.learning.knowledge import KnowledgeProcessor
from whisper.learning.development import DevelopmentEngine
from whisper.learning.priorities import FOCUS_TOPICS

BODY='A useful original source passage for verification. '*10
CARD=dict(summary='Kaynaklı bağlam yönetimi ve kod testi için teknik özet.',concepts=['bağlam'],
          claims=[dict(text='Kaynaklı bir değerlendirme.',quote='A useful original source passage for verification.')],applications=[])
PROPOSAL=dict(problem='Bağlam davranışını test etmek gerekir.',
              change='Mevcut bağlam aktarımını kaynaklı kabul testiyle değerlendir.',
              acceptance_tests=[dict(input='Önceki konu neydi?',expected='Önceki konuya ilişkin kayıt kullanılır.')],
              limitations=['Henüz gerçek model testi yapılmadı.'])


class ResearchCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'research.db';self.now=100000
        self.memory=ResearchMemory(self.path)
        self.research=AutonomousResearch(self.memory,reader=Mock(),clock=lambda:self.now)
        self.research.set_profile('development')
        self.processor=KnowledgeProcessor(self.path,clock=lambda:self.now)
        self.engine=DevelopmentEngine(self.path,clock=lambda:self.now)
        self.model=SimpleNamespace(base_url='http://127.0.0.1:11434/v1',model='offline',chat=Mock(return_value=json.dumps(CARD)))

    def capture(self,title):
        return self.memory.capture(title,BODY,[{'url':'https://docs.ollama.com/'+str(title)}],'autonomous_document')

    def mark_done(self):
        self.processor.sync()
        with self.processor.connect() as db:
            db.execute("UPDATE knowledge_chunks SET state='done',card=?,processed_at=source_id",(json.dumps(CARD),))

    def test_development_priority_is_applied_before_500_row_window(self):
        for i in range(501):self.capture('General document '+str(i))
        wanted=self.capture('Türkçe diyalog bağlamı için özel araştırma konusu')
        result=self.processor.tick(self.model)
        self.assertEqual(result['status'],'processed')
        self.assertEqual(result['source_id'],wanted)
        self.assertEqual(self.model.chat.call_count,1)

    def test_explicit_source_filter_wins_over_curriculum_and_future_due_is_respected(self):
        chosen=self.capture('Genel fizik');focus=self.capture(FOCUS_TOPICS['context'])
        self.processor.sync()
        with self.processor.connect() as db:
            db.execute('UPDATE knowledge_chunks SET due=? WHERE source_id=?',(self.now+60,chosen))
        self.assertIsNone(self.processor.tick(self.model,source_ids=[chosen]))
        self.now+=61
        self.assertEqual(self.processor.tick(self.model,source_ids=[chosen])['source_id'],chosen)
        with self.processor.connect() as db:
            self.assertEqual(db.execute('SELECT state FROM knowledge_chunks WHERE source_id=?',(focus,)).fetchone()[0],'pending')

    def test_old_card_is_discovered_behind_201_already_queued_cards(self):
        wanted=self.capture(FOCUS_TOPICS['context'])
        newer=[self.capture('Python agent test '+str(i)) for i in range(201)]
        self.mark_done()
        with self.engine.connect() as db:
            db.executemany("INSERT INTO development_jobs(source_id,part,state,proposal) VALUES(?,0,'draft',?)",
                           [(sid,json.dumps(PROPOSAL)) for sid in newer])
        self.model.chat.return_value=json.dumps(PROPOSAL)
        result=self.engine.tick(self.model)
        self.assertIsNotNone(result)
        self.assertEqual(result['status'],'draft');self.assertEqual(result['source_id'],wanted)
        self.now+=601
        self.assertIsNone(self.engine.tick(self.model))
        self.model.chat.assert_called_once()

    def test_general_cards_do_not_hide_an_older_core_card(self):
        wanted=self.capture(FOCUS_TOPICS['agent'])
        for i in range(201):self.capture('General unrelated material '+str(i))
        self.mark_done();self.model.chat.return_value=json.dumps(PROPOSAL)
        result=self.engine.tick(self.model)
        self.assertIsNotNone(result);self.assertEqual(result['source_id'],wanted)
        with self.engine.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM development_jobs').fetchone()[0],1)

    def test_cancelled_draft_discovery_has_no_model_or_queue_side_effects(self):
        self.capture(FOCUS_TOPICS['agent']);self.mark_done()
        stop=threading.Event();stop.set()
        self.assertIsNone(self.engine.tick(self.model,stop))
        self.model.chat.assert_not_called()
        with self.engine.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM development_jobs').fetchone()[0],0)

    def test_reasoning_topic_has_a_real_curriculum_read_slot(self):
        self.research.search=Mock(return_value=[])
        self.research.reader.side_effect=lambda url,stop:dict(url=url,body=BODY,links=[],partial=False)
        with self.research.connect() as db:
            db.execute("UPDATE autonomous_settings SET value='8' WHERE key='tick_number'")
        result=self.research.tick()
        self.assertEqual(result['status'],'read')
        self.assertEqual(result['url'],'https://arxiv.org/abs/2203.11171')
        record=self.memory.get(result['source_id'])
        self.assertEqual(record['body'],BODY)
        self.research.search.assert_called_once()
        self.assertIn('Logical reasoning',self.research.search.call_args.args[0])
