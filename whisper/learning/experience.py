"""Tool receipts and explicit user corrections; no automatic model weight training."""
import json
import re
import sqlite3
from datetime import datetime, timezone
from ..common import fold

class ExperienceMemory:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS experiences(id INTEGER PRIMARY KEY,goal TEXT NOT NULL,receipts TEXT NOT NULL,state TEXT NOT NULL,feedback TEXT NOT NULL DEFAULT "",created_at TEXT NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def save(self, goal, receipts, state):
        with self.connect() as db:
            return db.execute('INSERT INTO experiences(goal,receipts,state,created_at) VALUES(?,?,?,?)',
                (goal, json.dumps(receipts, ensure_ascii=False), state, datetime.now(timezone.utc).isoformat())).lastrowid

    def correct(self, experience_id, text):
        if type(experience_id) is not int or not isinstance(text, str) or not 3 <= len(text.strip()) <= 1000:
            raise ValueError('Deneyim numarası ve 3–1000 karakterlik düzeltme gerekli.')
        with self.connect() as db:
            return bool(db.execute('UPDATE experiences SET feedback=? WHERE id=?',(text.strip(),experience_id)).rowcount)

    def recall(self, goal):
        words=set(re.findall(r'\w{3,}',fold(goal)))
        with self.connect() as db:
            rows=db.execute('SELECT id,goal,receipts,state,feedback FROM experiences ORDER BY id DESC LIMIT 200').fetchall()
        ranked=[]
        for i, old_goal, receipts, state, feedback in rows:
            score=len(words & set(re.findall(r'\w{3,}',fold(old_goal))))
            if score:
                # Bounded records are untrusted context, never permissions or executable instructions.
                ranked.append((score, {'id':i,'goal':old_goal,'state':state,'feedback':feedback,
                    'receipts':[{'tool':r.get('tool'),'args':r.get('args'), 'status':r.get('status'),
                                 'response':str(r.get('response',''))[:500]} for r in json.loads(receipts)[-6:]]}))
        ranked.sort(key=lambda x:x[0],reverse=True)
        return [item for _,item in ranked[:3]]

    def history(self):
        with self.connect() as db:
            rows=db.execute('SELECT id,goal,state,feedback FROM experiences ORDER BY id DESC LIMIT 15').fetchall()
        return '\n'.join(f'{i}: {goal} | {state}' + (' | Düzeltme: '+feedback if feedback else '')
                         for i,goal,state,feedback in rows) or 'Kayıtlı deneyim yok.'
