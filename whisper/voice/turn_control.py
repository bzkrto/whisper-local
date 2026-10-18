"""Cooperative turn cancellation; stopping audio does not undo desktop actions."""
import threading

class TurnCancelled(Exception):
    pass

class TurnSpeech:
    def __init__(self, engine, policy=None):
        self.policy = policy
        self.engine = engine
        self.cancelled = threading.Event()
        self.engine.turn_cancelled = self.cancelled
        for child in getattr(engine, 'engines', []):
            child.turn_cancelled = self.cancelled
        self.speaking = threading.Event()
        self._lock = threading.Lock()
        self.name = engine.name

    def begin(self):
        self.cancelled.clear()
        if self.policy:
            self.policy.reset()

    def cancel(self):
        self.cancelled.set()
        stop = getattr(self.engine, 'stop', None)
        if stop:
            stop()

    def check(self):
        if self.cancelled.is_set():
            raise TurnCancelled()

    def speak(self, text):
        with self._lock:
            if self.cancelled.is_set():
                return False
            if self.policy:
                text = self.policy.render(text)
                if not text:
                    return True
            self.speaking.set()
            try:
                return self.engine.speak(text)
            finally:
                self.speaking.clear()
