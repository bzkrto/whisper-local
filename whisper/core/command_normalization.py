"""Normalize explicit Turkish control intents before the LLM, without rewriting content."""
import re
from ..common import fold

RESEARCH_CONTROLS = {
    'otomatik arastirmayi baslat': (
        'arastirmaya devam et', 'arastirmayi surdur', 'arastirmaya basla',
        'arastirmayi baslat', 'otomatik arastirmaya devam et',
        'arastirmaya devam eder misin', 'arastirmaya devam edebilir misin',
        'arastirmayi yeniden baslat'),
    'otomatik arastirmayi durdur': (
        'arastirmayi durdur', 'arastirmayi duraklat', 'arastirmaya ara ver',
        'otomatik arastirmayi duraklat', 'arastirmayi durdurur musun'),
    'otomatik arastirma durumu': (
        'arastirma durumunu goster', 'arastirma ne durumda', 'arastiriyor musun',
        'arastirmaya devam ediyor musun'),
    'bugun neler ogrendin': ('neler ogrendin', 'bugun ne arastirdin', 'bugun neleri ogrendin'),
}

def normalize_command(text):
    text = text.strip()
    # A direct address is not part of the task. Never strip a mention mid-sentence.
    prefix = re.match(r'^(?:hey[ ,]+)?(?:whisper|visper|wisper|vhisper)[!,:;.]+\s*', fold(text))
    if not prefix:
        prefix = re.match(r'^hey[ ,]+(?:whisper|visper|wisper|vhisper)\b\s*', fold(text))
    if prefix:
        text = text[prefix.end():].strip()
    t = fold(text)
    t = re.sub(r'^lutfen\s+|\s+lutfen$', '', t)
    for canonical, variants in RESEARCH_CONTROLS.items():
        if t == canonical or t in variants:
            return canonical
    return text
