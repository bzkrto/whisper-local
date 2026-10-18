"""Short-lived task reference context; never executes or replays a previous action."""
import re
import time
from ..common import fold

DEFAULTS = {
    'music': {'platform': 'youtube', 'unspecified': 'Offer soft piano and ask once; do not assume acceptance.',
              'mood': 'Interpret a mood as a music preference only within an explicit music request.'},
    'website': {'browser': 'default'},
    'report': {'missing_topic': 'Ask for topic; infer from an explicit reference to the current task only.'},
    'note': {'missing_text': 'Ask what to save; keep the reply attached to that question.'},
    'file': {'ambiguous_match': 'Offer the actual matching files; do not invent a path.'},
}

class TaskContext:
    def __init__(self, clock=time.monotonic, ttl=600):
        self.clock, self.ttl = clock, ttl
        self.last = None

    def record(self, request, result):
        if result.get('status') not in ('success', 'dispatched'):
            return
        steps = result.get('steps', [])
        actions = [{'tool': r.get('tool'), 'args': r.get('args', {}), 'status': r.get('status')}
                   for r in steps[-5:]]
        if not actions and result.get('tool'):
            actions = [{'tool': result['tool'], 'args': result.get('args', {}), 'status': result['status']}]
        if actions or result.get('artifacts'):
            self.last = {'request': request[:1000], 'actions': actions,
                         'result': result.get('response', '')[:600],
                         'artifacts': result.get('artifacts', [])[:5], 'at': self.clock()}

    def for_request(self, request):
        if not self.last or self.clock() - self.last['at'] >= self.ttl:
            self.last = None
            return None
        if not re.search(r'\b(?:onu|bunu|onun|bunun|aynisini|aynisi|ayni|orada|onceki|son rapor|son dosya|degistir|baskasini|baska)\b', fold(request)):
            return None
        return {key: value for key, value in self.last.items() if key != 'at'}
