import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from whisper.core.dialogue import DialogueState
from whisper.core.action_agent import ActionAgent, validate_plan


class DialogueTests(unittest.TestCase):
    def test_title_keeps_bir_and_composed_command_is_not_music_search(self):
        state = DialogueState()
        self.assertEqual(state.media('Bir Fırtına Tuttu Bizi şarkısını aç')['query'], 'Bir Fırtına Tuttu Bizi')
        self.assertIsNone(state.media('Şarkı aç ve Chrome aç'))
        state.media('şarkı aç')
        self.assertIsNone(state.media('Batarya teknolojisini araştır'))
    def test_music_question_then_title_preserves_turkish(self):
        state = DialogueState()
        self.assertEqual(state.media("YouTube'dan şarkı aç")['kind'], 'clarification')
        self.assertEqual(state.media('Barış Manço Gülpembe')['query'], 'Barış Manço Gülpembe')
        self.assertIsNone(state.get())

    def test_choice_is_offered_but_not_assumed(self):
        state = DialogueState()
        state.media('şarkı aç')
        result = state.media('anlamadım')
        self.assertEqual(result['kind'], 'clarification')
        self.assertIn('sen seç', result['message'])
        self.assertEqual(state.media('sen seç')['kind'], 'action')

    def test_cancel_expire_and_new_command_do_not_search(self):
        now = [0]
        state = DialogueState(clock=lambda: now[0])
        state.media('şarkı aç')
        self.assertEqual(state.media('vazgeç')['kind'], 'cancelled')
        state.media('şarkı aç')
        now[0] = 181
        self.assertIsNone(state.media('Gülpembe'))
        state.media('şarkı aç')
        self.assertIsNone(state.media('saat kaç'))
        self.assertIsNone(state.get())

    def test_negative_and_composed_requests_not_partially_executed(self):
        state = DialogueState()
        self.assertIsNone(state.media('şarkı açma'))
        self.assertIsNone(state.media('şarkı aç ve sesi ayarla'))

    def test_query_schema_and_encoded_url_input(self):
        for query in ('', 'x\nexit', 'x' * 201, 123):
            with self.assertRaises(ValueError):
                validate_plan({'kind': 'action', 'message': '', 'steps': [
                    {'tool': 'youtube_search', 'args': {'query': query}}]}, set())
        validate_plan({'kind': 'action', 'message': '', 'steps': [
            {'tool': 'youtube_search', 'args': {'query': 'Gülpembe & Barış'}}]}, set())

    def test_generic_followup_is_explicit_context_and_no_first_turn_effect(self):
        with tempfile.TemporaryDirectory() as folder:
            agent = ActionAgent(Path(folder) / 'db.sqlite')
            model = SimpleNamespace(base_url='http://localhost:11434/v1', chat=Mock())
            executor = Mock(return_value={'status': 'success', 'response': 'not kaydedildi'})
            model.chat.return_value = json.dumps({'kind': 'clarification', 'message': 'Ne kaydedeyim?', 'steps': []})
            agent.execute('Bir not al', model, [], executor)
            executor.assert_not_called()
            model.chat.return_value = json.dumps({'kind': 'action', 'message': '', 'steps': [
                {'tool': 'take_note', 'args': {'text': 'Yarın malzeme al'}}]})
            result = agent.execute('Yarın malzeme al', model, [], executor)
            payload = json.loads(model.chat.call_args.args[1])
            self.assertEqual(payload['pending_clarification']['request'], 'Bir not al')
            self.assertEqual(payload['current_request'], 'Yarın malzeme al')
            self.assertIsNone(agent.dialogue.get())
            self.assertIn('not kaydedildi', result['spoken_response'])
            executor.assert_called_once_with('take_note', {'text': 'Yarın malzeme al'})

    def test_cancel_pending_generic_has_no_model_or_tool_call(self):
        with tempfile.TemporaryDirectory() as folder:
            agent = ActionAgent(Path(folder) / 'db.sqlite')
            agent.ask_followup('Sesi ayarla', 'Kaç olsun?')
            model = SimpleNamespace(base_url='http://localhost:11434/v1', chat=Mock())
            executor = Mock()
            result = agent.execute('vazgeç', model, [], executor)
            self.assertEqual(result['status'], 'cancelled')
            model.chat.assert_not_called()
            executor.assert_not_called()
