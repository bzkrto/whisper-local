from __future__ import annotations
import json, re, sqlite3, subprocess, time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

TR = str.maketrans('çğıöşüÇĞİÖŞÜ', 'cgiosuCGIOSU')

TZ = timezone(timedelta(hours=3), 'Europe/Istanbul')

CATEGORIES = ('personality', 'projects', 'goals', 'hardware', 'relationships', 'preferences')

SOURCES = ('KAYNAK_HAFIZA', 'KAYNAK_INTERNET', 'KAYNAK_SISTEM', 'KAYNAK_TAHMIN')

def fold(text):
    return text.translate(TR).lower().strip().rstrip('.!?')
