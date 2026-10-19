"""Read-only operational status; never asks a model to invent its own activity."""
from pathlib import Path
import re
import sqlite3
from ..common import fold


def status_question(text):
    value=' '.join(re.findall(r'\w+',fold(text)))
    value=re.sub(r'^(?:whisper |reis |peki |su an |simdi )+', '',value)
    return bool(re.fullmatch(
        r'(?:(?:neden|niye) arastirma yapmiyorsun|arastirma neden (?:yapmiyorsun|durdu)|arastirma (?:yapiyor musun|yapiyor musunuz|(?:su an )?ne durumda|durumu nedir|devam ediyor mu)|'
        r'(?:ne|neler|hangi konulari) arastiriyorsun|arastiriyor musun|'
        r'kendi kodunu (?:yaziyor|gelistiriyor) musun|kod yaziyor musun|kendini gelistiriyor musun)',value))


def control_request(text):
    # Only a complete control request; never swallow a topic or a second action.
    value=' '.join(re.findall(r'\w+',fold(text)))
    value=re.sub(r'^lutfen ', '',value)
    if re.fullmatch(r'(?:otomatik )?arastirma(?:ya|yi| yapmaya)? (?:devam et|baslat|surdur)',value):return 'start'
    if re.fullmatch(r'(?:otomatik )?arastirma(?:yi|ya)? (?:durdur|duraklat|ara ver)',value):return 'pause'
    return None


def snapshot(brain):
    # No sync/ingest, source text, inference, write transaction or model lock.
    with sqlite3.connect(Path(brain.cfg.db_path).resolve().as_uri()+'?mode=ro',uri=True,timeout=.2) as db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        def counts(table,column='state'):
            return dict(db.execute(f'SELECT {column},count(*) FROM {table} GROUP BY {column}')) if table in tables else {}
        settings=dict(db.execute('SELECT key,value FROM autonomous_settings')) if 'autonomous_settings' in tables else {}
        topics=[r[0] for r in db.execute('SELECT topic FROM autonomous_topics ORDER BY id LIMIT 12')] if 'autonomous_topics' in tables else []
        sources=db.execute('SELECT count(*) FROM research_sources').fetchone()[0] if 'research_sources' in tables else 0
        latest=db.execute('SELECT query FROM research_sources ORDER BY id DESC LIMIT 1').fetchone() if sources else None
        blocked=db.execute("SELECT detail FROM self_development_jobs WHERE state IN ('blocked','failed') AND detail!='' ORDER BY updated DESC,id DESC LIMIT 1").fetchone() if 'self_development_jobs' in tables else None
        knowledge_error=db.execute("SELECT source_id,part,error FROM knowledge_chunks WHERE state='error' AND error!='' ORDER BY due DESC,source_id DESC,part DESC LIMIT 1").fetchone() if 'knowledge_chunks' in tables else None
        knowledge=counts('knowledge_chunks')
        backlog=sum(n for state,n in knowledge.items() if state!='done')
        relevant_backlog=backlog
        if settings.get('research_profile')=='security' and 'knowledge_chunks' in tables and 'research_sources' in tables:
            relevant_backlog=db.execute("SELECT count(*) FROM knowledge_chunks k JOIN research_sources s ON s.id=k.source_id WHERE k.state!='done' AND (lower(s.query) LIKE '%security%' OR lower(s.query) LIKE '%siber%' OR lower(s.query) LIKE '%owasp%' OR lower(s.query) LIKE '%nist%')").fetchone()[0]
        data={'enabled':settings.get('enabled')=='1','profile':settings.get('research_profile','unknown'),
              'collection_waiting_for_processing':backlog>=12 and relevant_backlog>=12,
              'last_knowledge_error':{'source_id':knowledge_error[0],'part':knowledge_error[1],'detail':knowledge_error[2][:240]} if knowledge_error else None,
              'last_search_error':settings.get('last_search_error') or None,
              'last_code_blocker':blocked[0][:400] if blocked else None,'sources':sources,'last_topic':latest[0] if latest else None,'knowledge':knowledge,'drafts':counts('development_jobs'),
              'code':counts('self_development_jobs'),'topics':topics}
    data.update(internet_available=bool(brain.cfg.internet),
                phase=getattr(brain,'_background_phase',''),
                background_paused=bool(getattr(brain,'_background_models_paused',False)),
                research_io_active=brain.autonomous_research.tick_lock.locked())
    return data


def answer(brain):
    try:data=snapshot(brain)
    except sqlite3.Error:
        return {'status':'busy','response':'Durum veritabanı şu an okunamadı; araştırma yaptığıma dair doğrulanmış durum veremiyorum.',
                'source':'KAYNAK_SISTEM','fast':True}
    phases={'knowledge':'Şu an bir kaynak bölümünü bilgi kartına dönüştürüyorum.',
            'profile':'Şu an açık kullanıcı beyanlarını profil kaydına işliyorum.',
            'proposal':'Şu an kaynak kartından geliştirme taslağı hazırlıyorum.',
            'code':'Şu an sıradaki kod geliştirme işi işleniyor; sonucu henüz kesinleşmedi.'}
    text='Otomatik araştırma '+('açık.' if data['enabled'] else 'kapalı.')
    if not data['internet_available']:text+=' İnternet araştırması bu oturumda kapalı.'
    phase=data['phase']
    if phase in phases:text+=' '+phases[phase]
    elif data['research_io_active']:text+=' Şu an kaynak arama/okuma döngüsü çalışıyor.'
    elif data['background_paused']:text+=' Arka plan model işleri duraklatılmış.'
    else:text+=' Şu an çalışan bir araştırma/model işi gözlenmiyor; ayarın açık olması sürekli işlem yapıldığı anlamına gelmez.'
    text+=f"\nAraştırma profili: {data['profile']}."
    if data['last_topic']:text+=' Son kayıtlı konu: '+data['last_topic'][:160]+'.'
    k=data['knowledge'];d=data['drafts'];c=data['code']
    if data['enabled'] and data['collection_waiting_for_processing']:
        text+='\nYeni belge toplama, birikmiş kaynak bölümleri işlenene kadar bekletiliyor (eşik: 12 bölüm).'
    if data['last_search_error']:text+='\nSon kaynak arama hatası: '+data['last_search_error'][:240]
    if data['last_knowledge_error']:
        error=data['last_knowledge_error']
        text+=f"\nBilgi işleme hatası: kaynak {error['source_id']}, bölüm {error['part']}: {error['detail']}"
    text+=f"\nKayıtlı kaynak: {data['sources']}. Bilgi bölümleri: {k.get('done',0)} işlendi, {k.get('pending',0)} bekliyor, {k.get('running',0)} işlemde, {k.get('error',0)} hatalı."
    text+=f"\nGeliştirme taslağı: {d.get('draft',0)}. Kod işi: {sum(c.values())}; uygulanmış kod değişikliği: {c.get('active',0)+c.get('restart_required',0)}."
    if data['last_code_blocker']:
        text+='\nSon kod geliştirme engeli: '+data['last_code_blocker']
        if 'docker' in data['last_code_blocker'].lower() or 'whisper-test:local' in data['last_code_blocker']:
            text+='\nTest ortamını hazırlamak için: Whisper’ı kapatın, Docker Desktop Linux konteynerlerini açın ve WHISPER_GELISIM_BASLAT.cmd dosyasını çalıştırın.'
    text+='\nBilgi kartı ve geliştirme taslağı, kodun değiştiği veya modelin eğitildiği anlamına gelmez.'
    return {'status':'success','response':text,'source':'KAYNAK_SISTEM','fast':True,'research_status':data,
            'route':{'target':'status','reason':'Kayıtlı araştırma ve geliştirme durumu'}}
