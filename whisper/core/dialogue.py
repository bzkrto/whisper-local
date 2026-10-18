"""Short-lived, explicit clarification state; never replays old actions."""
import re
import time
from ..common import fold


class DialogueState:
    def __init__(self, clock=time.monotonic, ttl=180):
        self.clock, self.ttl = clock, ttl
        self.pending = None

    def clear(self):
        self.pending = None

    def get(self):
        if self.pending and self.clock() - self.pending['created'] >= self.ttl:
            self.clear()
        return self.pending

    def ask(self, request, question, domain='action'):
        self.pending = dict(request=request[:2000], question=question[:400],
                            domain=domain, created=self.clock())

    def media(self, text):
        """Only resolves music requests, not other commands or general conversation."""
        t = fold(text).strip().rstrip('.!?')
        pending = self.get()
        active = bool(pending and pending['domain'] == 'music')
        if t in ('vazgec', 'iptal', 'iptal et', 'bosver') and active:
            self.clear()
            return {'kind': 'cancelled', 'message': 'Şarkı isteğini iptal ettim.'}
        negative = bool(re.search(r'\b(?:acma|calma|istemiyorum|dinlemek istemiyorum)\b', t))
        if re.search(r'\b(?:sevdigim|favori|tercih ettigim)\b', t):
            self.clear()
            return None
        style = music_style(t)
        music = bool(re.search(r'\b(?:sarki(?:yi|sini)?|muzik|muzigi|turku(?:yu)?|parca(?:yi)?)\b', t))
        action = bool(re.search(r'\b(?:ac|cal|dinle|dinlemek|acar|calabilir|istiyorum)\b', t))
        if negative:
            if active:
                self.clear()
            return None
        # A clearly different request abandons the old music question.
        if active and (re.search(r'\b(?:saat|hava|sistem|dosya|klasor|not|rapor|gorev)\b', t)
                       or re.search(r'\b(?:kaydet|ayarla|hazirla|goster|baslat|arastir|hesapla|olustur)\b', t)
                       or re.search(r'\b(?:chrome|brave|edge|firefox|uygulama|program)\b.*\b(?:ac|kullan)\b', t)
                       or t.startswith(('hedef:', 'kod gelistir:', 'deneyim'))):
            self.clear()
            return None
        if not active and not ((music or style) and action):
            return None
        # A composed command belongs to the validated multi-tool planner.
        if re.search(r'\bve\b', t) and len(re.findall(r'\b(?:ac|cal|kaydet|ayarla|hazirla|goster|baslat)\b', t)) > 1:
            self.clear()
            return None
        # An explicitly named unsupported platform must not silently become YouTube.
        if re.search(r'\b(?:spotify|apple music|deezer)\b', t):
            self.ask(pending['request'] if active else text,
                     'Bu müzik hizmetinde oynatma bağlantım yok. YouTube kullanabiliriz; hangi şarkıyı veya tarzı istersiniz?', 'music')
            return {'kind':'clarification', 'message':self.pending['question']}
        if active and t in ('hayir', 'hayir baska', 'baska bir sey', 'onu istemiyorum'):
            self.ask(pending['request'], 'Nasıl bir şey istersiniz: Türkçe arabesk, hareketli müzik veya belirli bir sanatçı?', 'music')
            return {'kind':'clarification', 'message':self.pending['question']}
        if active and t in ('evet', 'olur', 'tamam', 'ac', 'acabilirsin', 'iyi olur') and pending.get('proposal'):
            query = pending['proposal']
            self.clear()
            return {'kind':'action', 'query':query}
        # Mood/setting is meaningful here because music intent has already been established.
        if style and not re.search(r'\b(?:degil|istemiyorum|olmasin|haric)\b', t):
            self.clear()
            return {'kind':'action', 'query':style}
        choose = t in ('sen sec', 'fark etmez', 'herhangi biri', 'bir seyler', 'rastgele') or bool(
            re.search(r'\b(?:herhangi bir|rastgele bir) (?:sarki|muzik|turku|parca)\b', t))
        if choose:
            query = 'soft piyano müziği'
        elif active and not action:
            query = text.strip(' .!?')
        else:
            # Preserve titles/artists rather than converting Turkish spelling.
            query = re.sub(r"(?i)youtube(?:['’]?(?:dan|den|da|de))?", '', text)
            query = re.sub(r'(?i)\b(?:şarkı|şarkıyı|şarkısını|müzik|müziği|türkü|türküyü|parça|parçayı|bana|lütfen)\b', '', query)
            query = re.sub(r'(?i)\s+(?:aç|çal|açar mısın|çalabilir misin|dinlemek istiyorum)[.!?]*$', '', query)
            query = re.sub(r'(?i)^(?:aç|çal)\s*$', '', query)
            query = re.sub(r'\s+', ' ', query).strip(' .!?')
            if fold(query) in ('bir', 'bir sey', 'bir seyler'):
                query = ''
        if not query or (active and (t in ('anlamadim', 'anlamadin', 'tekrar', 'ne', 'evet', 'bilmiyorum') or re.search(r'\b(?:degil|istemiyorum|olmasin|haric)\b', t))):
            question = ('Hangi şarkıyı veya sanatçıyı istersiniz? İsterseniz “sen seç” diyebilirsiniz.'
                        if active else 'YouTube’dan hangi şarkıyı veya tarzı istersiniz? İsterseniz soft piyano açabilirim.')
            self.ask(pending['request'] if active else text, question, 'music')
            self.pending['proposal'] = 'soft piyano müziği'
            return {'kind': 'clarification', 'message': question}
        if len(query) > 200 or '\n' in text or '\r' in text:
            question = 'Şarkı veya sanatçı adını kısa bir şekilde tekrar söyler misiniz?'
            self.ask(pending['request'] if active else text, question, 'music')
            return {'kind': 'clarification', 'message': question}
        self.clear()
        return {'kind': 'action', 'query': query}


def music_style(text):
    """Contextual suggestions are music queries, never diagnoses or permanent preferences."""
    rules = [
        (r'\b(?:soft piyano|piyano|piano)\b', 'soft piyano müziği'),
        (r'\b(?:dertli|dertliyim|arabesk|huzunlu|kederli)\b', 'Türkçe arabesk müzik'),
        (r'\b(?:ders calisiyorum|ders calismak|odaklanmak|odaklanma|konsantre|calisma muzigi)\b', 'sözsüz odaklanma piyano müziği'),
        (r'\b(?:uyuyacagim|uyumak|uyku)\b', 'sakin uyku müziği'),
        (r'\b(?:spor yapiyorum|antrenman|hareketli|enerjik)\b', 'hareketli spor müziği'),
        (r'\b(?:sakin|rahatlatici|dinlendirici)\b', 'sakin enstrümantal müzik'),
    ]
    # Explicit titles/artists take precedence over a word which might also be a mood.
    if re.search(r"['’\"]|\b(?:sarkisi|sarkisini|sanatci)\b", text):
        return None
    for pattern, query in rules:
        if re.search(pattern, text):
            remainder = re.sub(pattern, ' ', text)
            words = set(re.findall(r'\w+', remainder))
            generic = {'bir','sey','seyler','ac','cal','olsun','istiyorum','dinlemek','muzik','muzigi','sarki','bana','lutfen','bugun','biraz','cok','ben','turkce','youtube','dan','den','acar','misin','acabilir'}
            if words <= generic:
                return query
    return None
