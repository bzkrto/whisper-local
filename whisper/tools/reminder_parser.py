"""Bounded Turkish reminder parsing; never asks an LLM to invent a date."""
from dataclasses import dataclass
from datetime import timedelta
import re
from ..common import fold

NUMBERS = {
    'sifir':0,'bir':1,'iki':2,'uc':3,'dort':4,'bes':5,'alti':6,'yedi':7,'sekiz':8,'dokuz':9,'on':10,
    **{'on '+w:n+10 for w,n in {'bir':1,'iki':2,'uc':3,'dort':4,'bes':5,'alti':6,'yedi':7,'sekiz':8,'dokuz':9}.items()},
    'yirmi':20,'yirmi bir':21,'yirmi iki':22,'yirmi uc':23,'otuz':30,'kirk':40,'elli':50,'altmis':60}

@dataclass
class Reminder:
    title: str = ''
    due: object = None
    error: str = ''

def number(value):
    return int(value) if value.isdigit() else NUMBERS.get(value)

def parse_reminder(command, now):
    t = fold(command)
    if not re.search(r'\bhatirlat\b',t):
        return None
    m = re.fullmatch(r'(.+?) (dakika|saat|gun) sonra (?:bana )?hatirlat\s*:?\s*(.*)',t)
    if m:
        count = number(m[1])
        if count is None or not 1 <= count <= 365:
            return Reminder(error='Süreyi 1–365 arasında belirtin; örnek: On dakika sonra bana hatırlat: toplantı.')
        title = command.strip()[m.start(3):m.end(3)].strip(' .')
        if not title:return Reminder(error='Neyi hatırlatayım? Konuyu aynı cümlede belirtin.')
        due = now + timedelta(**{ {'dakika':'minutes','saat':'hours','gun':'days'}[m[2]]:count})
        return Reminder(title,due)
    m = re.fullmatch(r'(bugun|yarin) (?:(sabah|aksam|gece|ogle) )?(?:saat )?(.+?) (?:bana )?hatirlat\s*:?\s*(.*)',t)
    if not m:
        return Reminder(error='Zaman ve konuyu belirtin: Yarın sabah saat onda bana hatırlat: toplantı.')
    clock = re.sub(r"['’]?(?:da|de|ta|te)$",'',m[3]).strip()
    # Turkish vowel buffer: on-da, iki-de, alti-da are handled by suffix removal.
    numeric = re.fullmatch(r'(\d{1,2})(?::(\d{2}))?',clock)
    hour = int(numeric[1]) if numeric else number(clock)
    minute = int(numeric[2] or 0) if numeric else 0
    if hour is None or hour > 23 or minute > 59:
        return Reminder(error='Saat geçersiz. Örnek: Yarın saat 10:30’da bana hatırlat: toplantı.')
    period = m[2]
    if period:
        if not 1 <= hour <= 12:
            return Reminder(error='Sabah/akşam ile saat 1–12 arasında olmalı; ya da 24 saat biçimini kullanın.')
        hour = hour % 12 + (12 if period in ('aksam','ogle') else 0)
        if period == 'gece' and 6 <= hour <= 11:hour += 12
    elif 1 <= hour <= 12 and not (numeric and numeric[2] is not None):
        return Reminder(error=f'Saat {hour:02d}:00 mı, {hour%12+12:02d}:00 mı? Sabah/akşam belirtin veya 24 saat biçiminde yazın.')
    title = command.strip()[m.start(4):m.end(4)].strip(' .')
    if not title:return Reminder(error='Neyi hatırlatayım? Konuyu aynı cümlede belirtin.')
    due = now.replace(hour=hour,minute=minute,second=0,microsecond=0) + timedelta(days=m[1]=='yarin')
    if due <= now:return Reminder(error='Bu saat geçmişte. Gelecekteki zamanı belirtin.')
    return Reminder(title,due)
