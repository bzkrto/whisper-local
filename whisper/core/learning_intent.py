"""Internal learning questions are never inferred as current-news web requests."""
import re
from ..common import fold

def learning_intent(text):
    value=' '.join(re.findall(r'\w+',fold(text)))
    if value in ('ogrenme gunlugu','ayrintili ogrenme gunlugu'):return 'details'
    # Explicit external questions stay external, even when they mention learning.
    if re.search(r'\b(?:haber|fiyat|internette|internet|google|arastir)\b',value):return None
    if value in ('bugun neler aglandi','bugun ne aglandi'):return 'clarify'
    if re.search(r'\b(?:ogrendim|ogrendik|ogrenmisim)\b',value) and re.search(r'\b(?:bugun|ne|neler)\b',value):
        return 'clarify'
    learned=re.search(r'\b(?:ogrendin|ogrendiniz|ogrendiklerin|ogrendiklerini|ogrendigin|ogrendigini|ogrenmelerini|ogrenme ozeti)\b',value)
    question=re.search(r'\b(?:bugun|bugunku|ne|neler|anlat|ozetle|soyle)\b',value)
    if learned and question:return 'summary'
    if value in ('ogrenme ozeti','bugunku ogrenme durumu'):return 'summary'
    return None
