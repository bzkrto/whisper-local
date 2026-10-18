import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from whisper.learning.autonomy import AutonomousResearch, public_url, read_document
from whisper.memory.research_memory import ResearchMemory
from whisper.memory.acquaintance import Acquaintance, QUESTIONS


class AutonomyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'memory.db'
        self.memory = ResearchMemory(self.path)
        self.now = [1000000]
        self.reader = Mock(side_effect=lambda url, stop: {'url': url,
            'body': 'Python sqlite transactions and database memory. ' * 20, 'partial': False,
            'links': ['https://docs.python.org/3.12/library/sqlite3.html']})
        self.worker = AutonomousResearch(self.memory, reader=self.reader, clock=lambda: self.now[0])
        # General-source fixtures start on a balanced general-topic turn.
        with self.worker.connect() as db:
            db.execute("UPDATE autonomous_settings SET value='1' WHERE key='tick_number'")

    def test_first_tick_reads_document_without_user_prompt_and_discovers_link(self):
        result = self.worker.tick()
        self.assertEqual(result['status'], 'read')
        self.assertEqual(self.memory.get(result['source_id'])['source_type'], 'autonomous_document')
        with self.worker.connect() as db:
            self.assertIsNotNone(db.execute('SELECT 1 FROM autonomous_queue WHERE url LIKE ?', ('%sqlite3.html',)).fetchone())
        rows = self.worker.recall('Python sqlite')
        self.assertTrue(rows)
        self.assertEqual(rows[0]['sources'][0]['url'], result['url'])

    def test_filter_rejects_local_hosts_credentials_schemes_and_executables(self):
        for url in ('http://docs.python.org/x', 'https://127.0.0.1/x', 'file:///a',
                    'https://printer.local/x', 'https://user:pass@docs.python.org/x',
                    'https://docs.python.org/setup.exe', 'https://docs.python.org:444/x'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                public_url(url)

    def test_disable_persists_and_prevents_reading(self):
        self.worker.enable(False)
        self.assertIsNone(self.worker.tick())
        self.reader.assert_not_called()
        new = AutonomousResearch(self.memory, reader=self.reader)
        self.assertFalse(new.enabled())
        self.worker.enable(True)
        self.assertEqual(self.worker.tick()['status'], 'read')

    def test_daily_cap_survives_restart_and_counts_failed_attempts(self):
        with self.worker.connect() as db:
            db.execute("UPDATE autonomous_settings SET value='12' WHERE key='daily_limit'")
            for _ in range(12):
                db.execute("INSERT INTO autonomous_reads(url,at,status,detail) VALUES('x',?,'error','')", (self.now[0],))
        other = AutonomousResearch(self.memory, reader=self.reader, clock=lambda: self.now[0])
        self.assertIsNone(other.tick())
        self.reader.assert_not_called()

    def test_read_failure_is_reported_and_not_immediately_retried(self):
        self.reader.side_effect = RuntimeError('offline')
        result = self.worker.tick()
        self.assertEqual(result['status'], 'error')
        self.assertIn('offline', self.worker.report())
        with self.worker.connect() as db:
            due = db.execute('SELECT due FROM autonomous_queue WHERE url=?', (result['url'],)).fetchone()[0]
        self.assertGreater(due, self.now[0])

    def test_cancellation_during_read_does_not_store_document(self):
        def read(url, stop):
            stop.set()
            return {'url': url, 'body': 'x'*500, 'links': [], 'partial': False}
        self.worker.reader = read
        self.assertEqual(self.worker.tick()['status'], 'error')
        with self.memory.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM research_sources').fetchone()[0], 0)

    def test_search_discovers_only_supported_documents(self):
        self.worker.search = Mock(return_value=[{'url': 'https://docs.ollama.com/api/introduction'}, {'url': 'https://printer.local/page'}])
        self.worker.tick()
        self.worker.search.assert_called_once()
        with self.worker.connect() as db:
            urls = [r[0] for r in db.execute('SELECT url FROM autonomous_queue')]
        self.assertIn('https://docs.ollama.com/api/introduction', urls)
        self.assertNotIn('https://printer.local/page', urls)

    def test_redirect_is_revalidated_before_request(self):
        response = Mock(status_code=302, headers={'Location':'https://127.0.0.1/private'})
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        import sys
        requests = Mock()
        requests.get.return_value = response
        with patch.dict(sys.modules, {'requests':requests}), patch('socket.getaddrinfo',return_value=[(2,1,6,'',('1.1.1.1',443))]), self.assertRaises(ValueError):
            read_document('https://docs.python.org/3.12/', threading.Event())
        requests.get.assert_called_once()

    def test_html_parser_discards_script_and_marks_partial(self):
        response = Mock(status_code=200, headers={'Content-Type':'text/html'}, encoding='utf-8')
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.iter_content.return_value = [('<script>evil script</script><p>' + 'Python docs '*4000 + '</p>').encode()]
        import sys
        requests = Mock()
        requests.get.return_value = response
        with patch.dict(sys.modules, {'requests':requests}), patch('socket.getaddrinfo',return_value=[(2,1,6,'',('1.1.1.1',443))]):
            result = read_document('https://docs.python.org/3.12/', threading.Event())
        self.assertNotIn('evil script', result['body'])
        self.assertTrue(result['partial'])


class ProfileTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'memory.db'
        self.profile = Acquaintance(self.path)

    def test_one_question_and_restart_continues_without_repeat(self):
        self.assertIn('hitap', self.profile.next_question())
        self.assertIn('Ne iş', self.profile.handle('Osman'))
        self.assertIn('hitap: Osman', self.profile.context())
        self.assertIn('Ne iş', Acquaintance(self.path).next_question())

    def test_task_not_saved_as_personal_answer(self):
        self.profile.next_question()
        self.assertIsNone(self.profile.handle('Chrome aç', is_command=True))
        self.assertEqual(self.profile.context(), '')

    def test_skip_pause_resume_and_forget(self):
        self.profile.next_question()
        self.profile.handle('geç')
        self.assertNotIn('hitap:', self.profile.context())
        self.profile.handle('sonra devam edelim')
        self.assertIsNone(Acquaintance(self.path).next_question())
        self.assertIn('Ne iş', self.profile.handle('tanışmaya devam'))
        self.profile.handle('Mühendisim')
        self.assertIn('Mühendisim', self.profile.handle('profilimi göster'))
        self.profile.handle('profilimi unut')
        self.assertEqual(self.profile.context(), '')

    def test_explicit_answer_can_contain_action_words(self):
        self.profile.next_question()
        self.profile.handle('Cevabım: Bana Osman de', is_command=True)
        self.assertIn('Osman', self.profile.context())

    def test_question_bank_completes_and_does_not_repeat(self):
        self.profile.next_question()
        for _ in QUESTIONS:
            result = self.profile.handle('geç')
        self.assertIn('tamamlandı', result)
        self.assertIsNone(self.profile.next_question())
