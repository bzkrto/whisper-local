from __future__ import annotations
import json, re, sqlite3, subprocess, time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

class TaskManager:

    def task(self, title, due_at=None):
        title = title.strip()
        if not 1 <= len(title) <= 1000:
            raise ValueError('Görev başlığı 1–1000 karakter olmalı.')
        with self.connect() as db:
            return db.execute('INSERT INTO tasks(title,due_at,created_at) VALUES(?,?,?)', (title, due_at, self.now())).lastrowid

    def tasks(self):
        with self.connect() as db:
            return db.execute("SELECT id,title,due_at FROM tasks WHERE state='pending' ORDER BY id LIMIT 30").fetchall()

    def complete(self, task_id):
        with self.connect() as db:
            return db.execute("UPDATE tasks SET state='done' WHERE id=? AND state='pending'", (task_id,)).rowcount > 0

    def due(self):
        with self.connect() as db:
            return db.execute("SELECT id,title FROM tasks WHERE state='pending' AND due_at IS NOT NULL AND due_at<=? AND notified_at IS NULL ORDER BY due_at LIMIT 10", (self.now(),)).fetchall()

    def notified(self, task_id):
        with self.connect() as db:
            db.execute('UPDATE tasks SET notified_at=? WHERE id=?', (self.now(), task_id))
