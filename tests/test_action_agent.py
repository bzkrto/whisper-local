import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from whisper.core.action_agent import ActionAgent, validate_plan, local_model
from whisper.tools.app_catalog import AppCatalog
from whisper.voice.turn_control import TurnSpeech, TurnCancelled

def plan(*steps, kind='action', message=''):
    return {'kind': kind, 'message': message, 'steps': [{'tool': tool, 'args': args} for tool, args in steps]}

class AgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'memory.sqlite'
        self.agent = ActionAgent(self.path)
        self.executor = Mock(return_value={'status': 'dispatched', 'response': 'İstek gönderildi.'})
        self.model = SimpleNamespace(base_url='http://127.0.0.1:11434/v1', chat=Mock())
    def tearDown(self):
        self.tmp.cleanup()
    def ask(self, data, **kwargs):
        self.model.chat.return_value = json.dumps(data, ensure_ascii=False)
        return self.agent.execute('Çalışma ortamımı hazırla', self.model, ['chrome'], self.executor, **kwargs)

    def test_composed_plan_executes_in_order_and_records_actual_results(self):
        result = self.ask(plan(('open_app', {'name': 'chrome'}), ('set_volume', {'level': 50}), ('system_info', {})))
        self.assertEqual(result['status'], 'success')
        self.assertEqual([c.args[0] for c in self.executor.call_args_list], ['open_app', 'set_volume', 'system_info'])
        with sqlite3.connect(self.path) as db:
            rows = db.execute('SELECT state,evidence FROM agent_steps ORDER BY step_no').fetchall()
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r[0] == 'dispatched' and 'İstek' in r[1] for r in rows))

    def test_entire_plan_rejected_before_any_action(self):
        result = self.ask(plan(('open_app', {'name': 'chrome'}), ('shell', {'command': 'anything'})))
        self.assertEqual(result['status'], 'error'); self.executor.assert_not_called()

    def test_failed_step_stops_following_steps(self):
        self.executor.side_effect = [{'status': 'dispatched', 'response': 'Açma isteği gönderildi'},
                                     {'status': 'error', 'response': 'Ses paketi eksik'}]
        result = self.ask(plan(('open_app', {'name': 'chrome'}), ('set_volume', {'level': 50}), ('system_info', {})))
        self.assertEqual(result['status'], 'error'); self.assertEqual(self.executor.call_count, 2)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT state FROM agent_steps WHERE step_no=3').fetchone()[0], 'pending')

    def test_ambiguous_file_does_not_continue_chain(self):
        self.executor.return_value = {'status': 'choice', 'response': 'İki dosya var'}
        result = self.ask(plan(('open_file', {'name': 'rapor'}), ('open_app', {'name': 'chrome'})))
        self.assertEqual(result['status'], 'choice'); self.assertEqual(self.executor.call_count, 1)

    def test_cancel_during_plan_does_not_execute(self):
        stop = threading.Event(); stop.set()
        result = self.ask(plan(('set_volume', {'level': 50})), cancelled=stop)
        self.assertEqual(result['status'], 'cancelled'); self.executor.assert_not_called()

    def test_cancel_between_steps_prevents_remaining_actions(self):
        stop = threading.Event()
        def execute(tool, args):
            stop.set(); return {'status': 'dispatched', 'response': 'İstek gönderildi'}
        self.executor.side_effect = execute
        result = self.ask(plan(('open_app', {'name': 'chrome'}), ('system_info', {})), cancelled=stop)
        self.assertEqual(result['status'], 'cancelled'); self.assertEqual(self.executor.call_count, 1)

    def test_unsupported_requests_and_chat_never_execute(self):
        self.assertIsNone(self.ask(plan(kind='chat')))
        result = self.ask(plan(kind='clarification', message='Hangi dosya?'))
        self.assertTrue(self.agent.awaiting)
        self.assertEqual(result['status'], 'clarification'); self.executor.assert_not_called()

    def test_bad_arguments(self):
        for step in [('set_volume', {'level': True}), ('set_volume', {'level': 101}),
                     ('set_volume', {'level': 50, 'shell': 'x'}), ('open_app', {'name': 'unknown'}),
                     ('open_file', {'name': '../secret'}), ('open_site', {'name': 'http://evil'}),
                     ('open_folder', {'name': 'C:\\'}), ('take_note', {'text': ''})]:
            with self.subTest(step=step), self.assertRaises(ValueError):
                validate_plan(plan(step), {'chrome'})

    def test_remote_model_is_blocked_without_contact(self):
        self.model.base_url = 'https://example.org/v1'
        result = self.agent.execute('Chrome aç', self.model, ['chrome'], self.executor)
        self.assertEqual(result['status'], 'blocked'); self.model.chat.assert_not_called()
        for base in ('http://localhost.evil', 'http://user@localhost', 'file:///tmp/x', None):
            self.assertFalse(local_model(SimpleNamespace(base_url=base)))

    def test_restart_marks_inflight_interrupted_and_never_replays(self):
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO agent_runs(goal,plan,state,created_at) VALUES('x','{}','running','now')")
        new_agent = ActionAgent(self.path)
        self.assertIn('interrupted', new_agent.history()['response']); self.executor.assert_not_called()

    def test_context_is_passed_separately_from_current_request(self):
        self.ask(plan(kind='clarification', message='Hangisi?'), context=[{'user': 'Chrome aç', 'assistant': 'Hangi sayfa?'}])
        payload = json.loads(self.model.chat.call_args.args[1])
        self.assertEqual(payload['current_request'], 'Çalışma ortamımı hazırla')
        self.assertEqual(payload['recent_conversation'][0]['user'], 'Chrome aç')

class RuntimeTests(unittest.TestCase):
    def test_cancel_stops_engine_and_discards_queued_speech_until_new_turn(self):
        engine = SimpleNamespace(name='test', stop=Mock(), speak=Mock(return_value=True))
        voice = TurnSpeech(engine); voice.begin(); voice.speak('bir')
        voice.cancel(); self.assertFalse(voice.speak('eski devam'))
        engine.stop.assert_called_once(); self.assertEqual(engine.speak.call_count, 1)
        with self.assertRaises(TurnCancelled): voice.check()
        voice.begin(); self.assertTrue(voice.speak('yeni cevap'))

    def test_app_discovery_rejects_commands_and_ambiguous_registrations(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / 'editor.exe'; a.write_bytes(b'')
            b = Path(tmp) / 'other.exe'; b.write_bytes(b'')
            shell = Path(tmp) / 'powershell.exe'; shell.write_bytes(b'')
            catalog = AppCatalog(lambda: [('editor', str(a)), ('shell', str(shell)),
                                         ('injected', str(a)+' --args'), ('duplicate', str(a)), ('duplicate', str(b))])
            self.assertEqual(catalog.entries(), {'editor': str(a)})
            a.unlink(); self.assertIsNone(catalog.resolve('editor'))

if __name__ == '__main__': unittest.main()
