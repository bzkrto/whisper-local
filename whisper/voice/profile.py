"""Microphone energy profile and measured pronunciation examples, not STT training."""
import json
from pathlib import Path
import numpy as np
from whisper.common import fold

READING_SENTENCES=(
 'Merhaba, benim adım Osman. Bugün sakin ve anlaşılır konuşuyorum.',
 'Whisper, Brave uygulamasını aç ve beni dinlemeye devam et.',
 'Hesap makinesini aç. Belgeler klasöründeki bütçe raporunu bul.',
 'Şimdi üç, beş, sekiz ve on iki sayılarını söylüyorum.',
 'Çocuklar bahçede oynuyor, küçük kuşlar ağaçların üstünde ötüyor.',
 'Görevlerimi hatırla. Yarın saat onda bana çalışmamı hatırlat.')

def energy_observation(audio, sample_rate):
    values=np.asarray(audio,dtype=np.float32)/32768.
    block=max(1,int(sample_rate*.03))
    trimmed=values[:len(values)//block*block]
    if not trimmed.size:return {'speech_level':0.,'clipping_percent':0.}
    levels=np.sqrt(np.mean(trimmed.reshape(-1,block)**2,axis=1))
    return {'speech_level':float(np.percentile(levels,85)),
            'clipping_percent':float(np.mean(np.abs(values)>=.99)*100)}

def recommended_threshold(observations):
    levels=[r['speech_level'] for r in observations if r['speech_level']>0 and r['clipping_percent']<1]
    if len(levels)<3:return None
    return max(.0005,min(.02,float(np.median(levels))*.2))

def apply_profile(path,device,sample_rate,ambient,fallback):
    try:
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        threshold=data['threshold']
        if data['device']!=device or data['sample_rate']!=sample_rate:return fallback
        if not isinstance(threshold,(int,float)) or not .0005<=threshold<=.02:return fallback
        return max(float(threshold),ambient*3,.0005)
    except (OSError,ValueError,KeyError,TypeError):return fallback

def uncertain_fragment(text, contextual=False, known_words=()):
    import re
    words=re.findall(r'\w+',fold(text))
    allowed={'merhaba','selam','nasilsin','tesekkurler','tamam','evet','hayir','iptal','vazgec',
             'neden','nasil','ne','devam',
             'cikis','kapat','dur','gorusuruz','bir','iki','uc','dort','bes','alti','yedi','sekiz','dokuz','on'}
    known = {fold(str(word)) for word in known_words}
    # A single artist/app/name is meaningful when replying to a clarification.
    # Raw one-word noise outside a conversation still asks for repetition.
    return (len(words)==1 and not contextual and words[0] not in allowed
            and words[0] not in known and not words[0].isdigit())
