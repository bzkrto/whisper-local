from __future__ import annotations
import json, re, sqlite3, subprocess, time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from ..common import *

class ModelPool:
    """Selects installed names only. A role map may pin an exact name."""
    PREFIXES = {'chat': ('qwen',), 'reason': ('gemma',), 'code': ('qwen2.5-coder', 'qwen3-coder', 'deepseek'), 'vision': ('qwen3-vl', 'qwen2.5vl', 'llava'), 'fast': ('phi',)}

    def __init__(self, base, list_models, factory, role_map=None):
        self.base, self.list_models, self.factory = (base, list_models, factory)
        self.role_map = role_map or {}
        self.names, self.checked, self.instances = ([], 0.0, {})
        self.selection = {'role': 'chat', 'model': getattr(base, 'model', ''), 'fallback': False}

    def select(self, role):
        if not self.base:
            return None
        if getattr(self.base, 'name', '').lower() != 'ollama':
            return self.base
        if time.monotonic() - self.checked > 60 or not self.checked:
            try:
                self.names = self.list_models()
                self.checked = time.monotonic()
            except Exception:
                self.names = []
        desired = self.role_map.get(role) or (self.base.model if role == 'chat' else None)
        if not desired:
            desired = next((n for n in self.names if n.lower().startswith(self.PREFIXES.get(role, ()))), None)
        if desired not in self.names:
            if role == 'vision':
                self.selection = {'role': role, 'model': None, 'fallback': True}
                return None
            desired = self.base.model
        previous_name = self.selection.get('model')
        if desired != previous_name and previous_name:
            previous = self.base if previous_name == self.base.model else self.instances.get(previous_name)
            release = getattr(previous, 'unload', None)
            if callable(release):
                try:
                    release()
                except Exception:
                    print('ℹ️ Önceki model için bellek boşaltma isteği başarısız; Ollama bellek yönetimi devam edecek.')
        self.selection = {'role': role, 'model': desired, 'fallback': role != 'chat' and desired == self.base.model}
        if desired == self.base.model:
            return self.base
        if desired not in self.instances:
            self.instances[desired] = self.factory(desired)
        return self.instances[desired]
