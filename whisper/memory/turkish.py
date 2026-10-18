"""Turkish concept recall and user-approved phrase meanings; no acoustic retraining."""
import re
import sqlite3
from ..common import fold

GROUPS = [('hafiza', 'bellek', 'memory', 'hatirla', 'hatirlama'),
          ('arastirma', 'arastir', 'incele', 'research'),
          ('yazilim', 'programlama', 'kodlama', 'programming', 'software'),
          ('ogrenme', 'ogren', 'learning', 'egitim'),
          ('hata', 'sorun', 'problem', 'error'),
          ('ses', 'konusma', 'speech', 'audio'),
          ('guvenlik', 'security', 'koruma'),
          ('dosya', 'belge', 'document', 'file'),
          ('yazim', 'imla', 'spelling'),
          ('kelime', 'sozcuk', 'word'),
          ('siber', 'cybersecurity', 'cyber'),
          ('parola', 'sifre', 'password', 'passwords'),
          ('kimlik', 'authentication', 'dogrulama'),
          ('yedekleme', 'backup', 'backups'),
          ('guvenlikduvari', 'firewall'),
          ('oltalama', 'phishing')]


def concepts(text):
    words = set(re.findall(r'\w{3,}', fold(text))) - {'bir', 'icin', 'bana', 'nasil', 'nedir', 'anlat', 'lutfen', 'bugun'}
    result = set(words)
    for group in GROUPS:
        if words.intersection(group):
            result.update(group)
    return result


class TurkishMemory:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS turkish_phrases(phrase TEXT PRIMARY KEY,meaning TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS speech_vocabulary(key TEXT PRIMARY KEY,term TEXT NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def teach(self, phrase, meaning):
        if not 2 <= len(phrase.strip()) <= 160 or not 2 <= len(meaning.strip()) <= 300:
            raise ValueError('İfade 2–160, anlamı 2–300 karakter olmalı.')
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO turkish_phrases VALUES(?,?)', (fold(phrase.strip()).rstrip('.!?'), meaning.strip()))

    def meaning(self, text):
        with self.connect() as db:
            row = db.execute('SELECT meaning FROM turkish_phrases WHERE phrase=?', (fold(text.strip()).rstrip('.!?'),)).fetchone()
        return row[0] if row else None

    def recall(self, text):
        words = concepts(text)
        if not words:
            return []
        with self.connect() as db:
            rows = db.execute('SELECT id,user_command,response,timestamp FROM conversation_history ORDER BY id DESC LIMIT 500').fetchall()
        ranked = []
        for i, user, answer, stamp in rows:
            score = len(words & concepts(user or ''))
            if score >= 2:
                ranked.append((score, i, {'id': i, 'user': (user or '')[:350], 'assistant': (answer or '')[:600], 'at': stamp}))
        ranked.sort(key=lambda x: x[:2], reverse=True)
        return [r[2] for r in ranked[:3]]

    def hints(self, profile, apps):
        # Only names already provided by the user / installed app catalog enter STT hints.
        raw = [line.split(':', 1)[1] for line in profile.splitlines() if line.startswith('hitap:')]
        with self.connect() as db:
            raw.extend(r[0] for r in db.execute('SELECT term FROM speech_vocabulary ORDER BY rowid DESC LIMIT 24'))
        raw.extend(apps[:20])
        clean = [re.sub(r'[^\w çğıöşüÇĞİÖŞÜ.-]', '', str(value))[:50] for value in raw]
        return ', '.join(dict.fromkeys(v for v in clean if v))[:600]

    def teach_word(self, term):
        term = term.strip()
        if not 2 <= len(term) <= 50 or not re.fullmatch(r"[\w çğıöşüÇĞİÖŞÜ.'’-]+", term):
            raise ValueError('Sözlük terimi 2–50 karakterlik bir kelime veya kısa isim olmalı.')
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO speech_vocabulary VALUES(?,?)', (fold(term),term))

    def vocabulary(self):
        with self.connect() as db:
            return [r[0] for r in db.execute('SELECT term FROM speech_vocabulary ORDER BY term')]
