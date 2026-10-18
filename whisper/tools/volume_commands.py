"""Narrow Turkish system-volume grammar; no LLM or guessed app targets."""
import re
from ..common import fold

ONES={'sifir':0,'bir':1,'iki':2,'uc':3,'dort':4,'dord':4,'bes':5,
      'alti':6,'yedi':7,'sekiz':8,'dokuz':9}
TENS={'on':10,'yirmi':20,'otuz':30,'kirk':40,'elli':50,
      'altmis':60,'yetmis':70,'seksen':80,'doksan':90}

def _number(text):
    if text.isdigit():return int(text)
    words=text.split()
    if len(words)==1:
        return {**ONES,**TENS,'yuz':100}.get(words[0])
    if len(words)==2 and words[0] in TENS and words[1] in ONES:
        return TENS[words[0]]+ONES[words[1]]
    return None

def volume_level(command):
    text=re.sub(r'\s+',' ',fold(command)).strip().rstrip('.!?')
    text=re.sub(r'^lutfen\s+|\s+lutfen$','',text)
    match=re.fullmatch(
        r'(?:(?:bilgisayarin|bilgisayarimin|sistemin) )?'
        r'(?:sesi|sesini|ses seviyesi(?:ni|ne)?) '
        r'(?:yuzde |%)?(.+?)(?: (?:yap|ayarla|getir|cikar|indir))?',text)
    if not match:return None
    raw=match[1].replace("'",'').replace('’','').strip()
    candidates=[raw]
    for suffix in ('ye','ya','e','a'):
        if raw.endswith(suffix):candidates.append(raw[:-len(suffix)])
    for candidate in candidates:
        value=_number(candidate)
        if value is not None:return value
    return None
