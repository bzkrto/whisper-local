"""Keep full answers on screen while bounding spoken detail per turn."""
import re

class SpeechPolicy:
    def __init__(self, mode='short', budget=360):
        self.mode, self.budget = mode, budget
        self.reset()
    def reset(self):
        self.used = 0
        self.notified = False
    def render(self, text):
        if self.mode == 'full':
            return text
        if self.notified:
            return ''
        text = re.sub(r'```[\s\S]*?```', 'Kod ekranda.', str(text))
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'(?m)^\s*(?:Kaynak:|Kayıt \d+:|Ajan görevi \d+|read \||error \|).*$', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        room = self.budget - self.used
        if len(text) <= room:
            self.used += len(text)
            return text
        # Prefer complete sentences; never invent a success summary.
        sentences = re.split(r'(?<=[.!?])\s+', text)
        output = ''
        for sentence in sentences:
            if len(output) + len(sentence) + 1 > room:
                break
            output += (' ' if output else '') + sentence
        if not output and self.used == 0:
            output = 'Yanıt uzun; ayrıntıları ekranda gösteriyorum.'
        elif output:
            output += ' Ayrıntılar ekranda.'
        else:
            output = 'Devamı ekranda.'
        self.notified = True
        return output
