"""Bounded session dialogue. No database reads, model calls or tool execution."""
from collections import deque
import re
import threading
from ..common import fold


def token_bound(text):
    """Conservative UTF-8 byte upper budget, not a tokenizer measurement.

    Byte-fallback tokenizers can spend a token per byte. Counting bytes plus
    message overhead avoids assuming English token/character ratios for Turkish.
    """
    return len(text.encode('utf-8'))+12


def redact(text):
    text=re.sub(r'\b(?:sk[-_][A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,})\b','[gizli anahtar çıkarıldı]',str(text))
    text=re.sub(r'(?i)\b(?:şifre|sifre|parola|password|api[_ -]?key|token)\s*[:=]\s*\S+',
                '[gizli bilgi çıkarıldı]',text)
    text=re.sub(r'(?<!\w)[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?!\w)','[e-posta çıkarıldı]',text)
    return re.sub(r'(?<!\w)\+?\d[\d ()-]{8,}\d(?!\w)','[telefon çıkarıldı]',text)


def clip(text,budget):
    raw=str(text).encode('utf-8')
    if len(raw)<=budget:return str(text)
    marker=' […] '
    available=max(0,budget-len(marker.encode('utf-8')))
    left=available//2;right=available-left
    return raw[:left].decode('utf-8','ignore')+marker+(raw[-right:].decode('utf-8','ignore') if right else '') if budget>=len(marker.encode('utf-8')) else ''


def terms(text):
    return {w[:5] for w in re.findall(r'\w{3,}',fold(text))}-{'bir','daha','once','sonra','bunu','biraz','hangi','nedir','nasil'}


def messages(system,user,history=None):
    """History cannot supply privileged roles or tool calls to any adapter."""
    result=[{'role':'system','content':system}]
    for row in history or ():
        if (not isinstance(row,dict) or set(row)!={'role','content'}
                or row['role'] not in ('user','assistant') or not isinstance(row['content'],str)):
            raise ValueError('Geçmiş yalnız user/assistant metin mesajları içerebilir.')
        result.append(dict(row))
    result.append({'role':'user','content':user})
    return result


class ConversationWindow:
    def __init__(self,max_turns=24):
        self._turns=deque(maxlen=max_turns)
        self._lock=threading.RLock()

    def record(self,user,answer):
        if not user or not answer:return
        pair=({'role':'user','content':clip(redact(user),4096)},
              {'role':'assistant','content':clip(redact(answer),4096)})
        with self._lock:self._turns.append(pair)

    def history(self,query,budget):
        with self._lock:turns=list(self._turns)
        if not turns or budget<32:return []
        costs=[sum(token_bound(m['content']) for m in pair) for pair in turns]
        chosen={};remaining=budget
        # The immediately preceding reply is mandatory when it fits; never cut a
        # pair in half or let an old keyword match displace the latest correction.
        if costs[-1]>remaining:
            size=max(0,(remaining-24)//2)
            return [dict(m,content=clip(m['content'],size)) for m in turns[-1]] if size>=8 else []
        chosen[len(turns)-1]=turns[-1];remaining-=costs[-1]
        words=terms(query)
        order=sorted(range(len(turns)-1),key=lambda i:(-len(words & terms(turns[i][0]['content']+' '+turns[i][1]['content'])),-i))
        for index in order:
            if costs[index]<=remaining:
                chosen[index]=turns[index];remaining-=costs[index]
        return [dict(m) for i in sorted(chosen) for m in chosen[i]]
