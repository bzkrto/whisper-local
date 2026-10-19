"""Routing signals grant no tool authority; ordinary text defaults to dialogue."""
import re
from ..common import fold

# Explicit action morphology is shared with the conversation classifier. Names,
# domains and ordinary topic labels are not evidence of an execution request.
ACTION_WORDS=r'\b(?:ac|acar|acabilir|acalim|acman\w*|acilmas\w*|cal|calar|calabilir|baslat\w*|calistir\w*|hazirla\w*|getir\w*|ayarla\w*|kaydet\w*|olustur\w*|goster\w*|donustur\w*|aktar\w*|arastir|arastirir|arastirabilir|oku|okur|ogren|izle|takip|yaz|yazar|yazabilir|yazman\w*|kodla\w*|yap|yapar|yapabilir|yapman\w*|sil\w*|gonder\w*|yukle\w*|indir\w*|surdur\w*|basla\w*|durdur\w*|kapat\w*|kis|artir\w*|tikla\w*|kur|kurar|kurabilir|not al)\b'


def explicit_action(text):
    value=fold(text)
    return bool(re.search(ACTION_WORDS,value) or re.search(r'\b(?:devam (?:et|edelim|edebilir\w*)|ara ver)\b',value))


def greeting_turn(text):
    value=' '.join(re.findall(r'\w+',fold(text)))
    value=re.sub(r'^(?:hey )?whisper ','',value)
    greetings=('merhaba','selam','selamlar','nasilsin','nasilsiniz','gunaydin','iyi aksamlar','iyi geceler')
    if value in greetings:return True
    # Only an isolated greeting with one edit may abandon an old task. Preserve
    # the original user text; this is neither spelling replacement nor an answer.
    if not value.isalpha() or len(value)<6:return False
    for word in greetings:
        if ' ' in word or abs(len(value)-len(word))>1:continue
        if len(value)==len(word) and sum(a!=b for a,b in zip(value,word))==1:return True
        short,long=sorted((value,word),key=len)
        if len(long)==len(short)+1 and any(long[:i]+long[i+1:]==short for i in range(len(long))):return True
    return False


def changes_topic(text):
    return greeting_turn(text) or bool(re.search(r'\b(?:konuyu degistir|baska bir konu|yeni bir konu|bunu bosver)\b',fold(text)))
