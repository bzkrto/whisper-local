import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from whisper.learning.engine import LearningEngine
from whisper.core.action_agent import ActionAgent


class LearningTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'memory.db'
        self.learning = LearningEngine(self.path)
        self.stop = threading.Event()
        self.model = SimpleNamespace(base_url='http://localhost:11434/v1', chat=Mock())

    def save(self, status='success', goal='Sistem durumunu kontrol et'):
        return self.learning.save(goal, [{'tool': 'system_info', 'status': status, 'response': 'RAM ölçümü'}], 'review')

    def proposal(self, eid, body='Sistem durumunu değerlendirirken ölçüm sonucunu kontrol et.'):
        self.model.chat.return_value = json.dumps({'lessons': [{'source_ids': [eid], 'lesson': body}]})
        return self.learning.reflect(self.model, self.stop)[0]

    def test_automatic_observation_has_source_and_does_not_claim_goal_success(self):
        eid = self.save()
        row = self.learning.context('Sistem durumu')[0]
        self.assertEqual(row['source_ids'], [eid])
        self.assertIn('ayrıca değerlendirilmelidir', row['text'])

    def test_dispatch_never_becomes_verified_completion(self):
        self.save('dispatched')
        self.assertIn('tamamlanma doğrulanmadı', self.learning.context('Sistem durumu')[0]['text'])

    def test_reopen_migrates_old_experiences_without_duplicate_observations(self):
        self.save()
        LearningEngine(self.path)
        LearningEngine(self.path)
        with self.learning.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM learning_lessons').fetchone()[0], 1)

    def test_llm_draft_excluded_until_approved_and_can_be_disabled(self):
        eid = self.save()
        lid = self.proposal(eid)
        self.assertNotIn(lid, [r['lesson_id'] for r in self.learning.context('Sistem durumu')])
        self.learning.change_state(lid, 'active')
        self.assertIn(lid, [r['lesson_id'] for r in self.learning.context('Sistem durumu')])
        self.learning.change_state(lid, 'disabled')
        self.assertNotIn(lid, [r['lesson_id'] for r in self.learning.context('Sistem durumu')])

    def test_feedback_invalidates_approved_hypothesis_and_updates_observation(self):
        eid = self.save()
        lid = self.proposal(eid)
        self.learning.change_state(lid, 'active')
        self.learning.correct(eid, 'Disk bilgisini de kontrol et.')
        self.assertIn('Disk bilgisini', self.learning.context('Sistem durumu')[0]['text'])
        with self.assertRaises(ValueError):
            self.learning.change_state(lid, 'active')
        newer = self.proposal(eid)
        self.assertNotEqual(newer, lid)

    def test_user_negative_outcome_is_visible_and_not_replaced_by_tool_success(self):
        eid = self.save()
        self.learning.rate(eid, 'başarısız')
        self.assertIn('Kullanıcı değerlendirmesi: başarısız', self.learning.context('Sistem durumu')[0]['text'])
        self.assertIn('başarısız bulduğu: 1', self.learning.report())

    def test_no_relevant_context_for_unrelated_goal(self):
        self.save()
        self.assertEqual(self.learning.context('Gülpembe şarkısı'), [])

    def test_model_cannot_activate_draft_or_invent_source(self):
        eid = self.save()
        for lessons in ([{'source_ids': [999], 'lesson': 'Bu kaynak aslında mevcut değil.'}],
                        [{'source_ids': [eid], 'lesson': 'Yeterince uzun örnek ders.', 'state': 'active'}]):
            self.model.chat.return_value = json.dumps({'lessons': lessons})
            with self.assertRaises(ValueError):
                self.learning.reflect(self.model, self.stop)
        with self.learning.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM learning_lessons WHERE kind='hypothesis'").fetchone()[0], 0)

    def test_entire_proposal_batch_validated_before_write(self):
        eid = self.save()
        self.model.chat.return_value = json.dumps({'lessons': [
            {'source_ids': [eid], 'lesson': 'Geçerli uzun örnek öneri.'},
            {'source_ids': [False], 'lesson': 'Geçersiz kaynak örneği.'}]})
        with self.assertRaises(ValueError):
            self.learning.reflect(self.model, self.stop)
        self.assertNotIn('hypothesis', self.learning.report(True))

    def test_cancellation_and_remote_model_prevent_contact(self):
        self.save()
        self.stop.set()
        self.assertEqual(self.learning.reflect(self.model, self.stop), [])
        self.model.chat.assert_not_called()
        self.stop.clear()
        self.model.base_url = 'https://example.org'
        with self.assertRaises(ValueError):
            self.learning.reflect(self.model, self.stop)
        self.model.chat.assert_not_called()

    def test_cancel_after_model_returns_does_not_save_hypotheses(self):
        eid = self.save()
        def generate(*args, **kwargs):
            self.stop.set()
            return json.dumps({'lessons': [{'source_ids': [eid], 'lesson': 'Örnek yeterince uzun öneri.'}]})
        self.model.chat.side_effect = generate
        self.assertEqual(self.learning.reflect(self.model, self.stop), [])
        self.assertNotIn('hypothesis', self.learning.report(True))

    def test_five_new_experiences_trigger_one_analysis_and_failures_do_not_loop(self):
        for _ in range(4):
            self.save()
        self.assertEqual(self.learning.maybe_reflect(self.model, self.stop)['status'], 'waiting')
        self.save()
        self.model.chat.side_effect = RuntimeError('offline')
        self.assertEqual(self.learning.maybe_reflect(self.model, self.stop)['status'], 'error')
        self.assertEqual(self.learning.maybe_reflect(self.model, self.stop)['status'], 'waiting')
        self.model.chat.assert_called_once()

    def test_disabled_observation_stays_disabled_after_restart(self):
        self.save()
        lid = self.learning.context('Sistem durumu')[0]['lesson_id']
        self.learning.change_state(lid, 'disabled')
        self.assertEqual(LearningEngine(self.path).context('Sistem durumu'), [])

    def test_agent_uses_approved_lessons_and_preserves_tool_allowlist(self):
        eid = self.save()
        lid = self.proposal(eid, 'Sistem değerlendirmesinde önce disk ölçümünü de incele.')
        self.learning.change_state(lid, 'active')
        agent = ActionAgent(self.path)
        self.model.chat.return_value = json.dumps({'kind': 'action', 'message': '', 'steps': [{'tool': 'shell', 'args': {'command': 'x'}}]})
        execute = Mock()
        result = agent.execute('Sistem durumunu kontrol et', self.model, [], execute)
        self.assertEqual(result['status'], 'error')
        execute.assert_not_called()
        payload = json.loads(self.model.chat.call_args.args[1])
        self.assertIn(lid, [r['lesson_id'] for r in payload['learned_context']])

    def test_reflection_deduplicates_same_source_and_body(self):
        eid = self.save()
        self.assertEqual(self.proposal(eid), self.proposal(eid))
