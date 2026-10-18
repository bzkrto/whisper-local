from __future__ import annotations
import json, re, sqlite3, subprocess, time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from ..common import *
from ..tools.task_manager import TaskManager

class LayerStore(TaskManager):

    def __init__(self, path):
        self.path = str(path)
        if Path(self.path).is_file():
            backup_path = Path(self.path).with_name(Path(self.path).name + '.pre_v12.bak')
            with self.connect() as original:
                migrated = original.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge'").fetchone()
                if not migrated and (not backup_path.exists()):
                    with sqlite3.connect(backup_path) as backup:
                        original.backup(backup)
        with self.connect() as db:
            db.executescript("\n            CREATE TABLE IF NOT EXISTS knowledge (\n              category TEXT NOT NULL, fact TEXT NOT NULL, source TEXT NOT NULL,\n              evidence TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL,\n              PRIMARY KEY(category, fact));\n            CREATE TABLE IF NOT EXISTS tasks (\n              id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,\n              due_at TEXT, state TEXT NOT NULL DEFAULT 'pending',\n              created_at TEXT NOT NULL, notified_at TEXT);\n            CREATE TABLE IF NOT EXISTS answer_sources (\n              id INTEGER PRIMARY KEY AUTOINCREMENT, command TEXT NOT NULL,\n              source TEXT NOT NULL, details TEXT NOT NULL, created_at TEXT NOT NULL);\n            ")

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat()

    def remember(self, category, fact, evidence=''):
        if category not in CATEGORIES or not 2 <= len(fact.strip()) <= 1000:
            raise ValueError('Kategori veya bilgi geçersiz.')
        with self.connect() as db:
            db.execute('INSERT INTO knowledge VALUES(?,?,?,?,?) ON CONFLICT(category,fact) DO UPDATE SET evidence=excluded.evidence, updated_at=excluded.updated_at', (category, fact.strip(), SOURCES[0], evidence[:1000], self.now()))

    def forget(self, fact):
        with self.connect() as db:
            return db.execute('DELETE FROM knowledge WHERE fact=?', (fact.strip(),)).rowcount

    def knowledge(self, category=None):
        with self.connect() as db:
            rows = db.execute('SELECT category,fact,source FROM knowledge' + (' WHERE category=?' if category else '') + ' ORDER BY updated_at DESC LIMIT 50', (category,) if category else ()).fetchall()
        return [{'category': c, 'fact': f, 'source': s} for c, f, s in rows]

    def receipt(self, command, source, details):
        if source not in SOURCES:
            raise ValueError('Bilinmeyen kaynak.')
        with self.connect() as db:
            db.execute('INSERT INTO answer_sources(command,source,details,created_at) VALUES(?,?,?,?)', (command, source, json.dumps(details, ensure_ascii=False), self.now()))
