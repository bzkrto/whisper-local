"""Durable research-to-artifact workflow. Completed checkpoints survive restart.

Research, learning and production use existing adapters. A model cannot mark a
stage complete or invent a URL; only successful adapter receipts do that.
"""
import json
import hashlib
import zipfile
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from ..common import fold
from ..memory.research_memory import ResearchMemory
from ..learning.knowledge import KnowledgeProcessor
from ..learning.autonomy import read_document, public_url, security_topic, SECURITY_HOSTS, research_query
from ..tools.report_export import export_report
from .action_agent import local_model
from .structured import request, obj, string, array

STAGES=('Plan', 'Araştır', 'Oku', 'Bilgiyi işle', 'Kaynakları karşılaştır', 'İçerik üret', 'Dosyaları oluştur', 'Kontrol et')


def command_intent(command):
    text=fold(command).rstrip('.!?')
    if text=='gorevlerim':return ('list',None)
    m=re.fullmatch(r'gorev durumu\s*:\s*(\d+)',text)
    if m:return ('show',int(m[1]))
    m=re.fullmatch(r'goreve devam et\s*:\s*(\d+)',text)
    if m:return ('resume',int(m[1]))
    if text.startswith('gorev olustur:'):return ('create',command.split(':',1)[1].strip())
    if re.search(r'\b(?:egitim\w*|rapor\w*|fizibilite\w*|sunum\w*|video senaryosu)\b',text) and re.search(r'\b(?:hazirla|olustur)\b',text):
        return ('create',command)
    return None


class TaskBrain:
    def __init__(self,path,clock=time.time):
        self.path=str(path);self.clock=clock
        self.research=ResearchMemory(path);self.knowledge=KnowledgeProcessor(path)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS brain_tasks(id INTEGER PRIMARY KEY,goal TEXT NOT NULL,state TEXT NOT NULL,checkpoint TEXT NOT NULL,error TEXT NOT NULL,updated REAL NOT NULL,owner TEXT,lease REAL DEFAULT 0)')
            db.execute('CREATE TABLE IF NOT EXISTS brain_task_events(id INTEGER PRIMARY KEY,task_id INTEGER,stage TEXT,state TEXT,detail TEXT,created REAL)')
    def connect(self):return sqlite3.connect(self.path,timeout=10)
    def create(self,goal,kind=None):
        if not isinstance(goal,str) or not 3<=len(goal.strip())<=1000:raise ValueError('Görev 3–1000 karakter olmalı.')
        kind=kind or ('training' if 'egitim' in fold(goal) else 'video' if 'video' in fold(goal) else 'report')
        if kind not in ('training','video','report','answer'):raise ValueError('Görev türü geçersiz.')
        cp={'kind':kind,'plan':[s for s in STAGES if kind!='answer' or s not in ('Dosyaları oluştur','Kontrol et')],'completed':[],'sources':[],'reads':[],'cards':[],'artifacts':[]}
        with self.connect() as db:
            return db.execute('INSERT INTO brain_tasks(goal,state,checkpoint,error,updated) VALUES(?,?,?,?,?)',
                (goal.strip(),'pending',json.dumps(cp,ensure_ascii=False),'',self.clock())).lastrowid
    def load(self,tid):
        if type(tid) is not int or tid<1:raise ValueError('Görev numarası geçersiz.')
        with self.connect() as db:row=db.execute('SELECT goal,state,checkpoint,error FROM brain_tasks WHERE id=?',(tid,)).fetchone()
        if not row:raise ValueError('Görev bulunamadı.')
        return row[0],row[1],json.loads(row[2]),row[3]
    def result(self,tid):
        goal,state,cp,error=self.load(tid)
        missing=[a['path'] for a in cp['artifacts'] if not Path(a['path']).is_file() or hashlib.sha256(Path(a['path']).read_bytes()).hexdigest()!=a['sha256']]
        status='success' if state=='completed' and not missing else 'partial' if state=='completed' else state
        text=f'Görev {tid}: {goal}\nDurum: {status}\n'+'\n'.join(f"{i+1}. {s}: {'Tamamlandı' if s in cp['completed'] else 'Bekliyor'}" for i,s in enumerate(cp['plan']))
        if error:text+='\nAçıklama: '+error
        text+='\nDosyalar:\n'+('\n'.join(a['path'] for a in cp['artifacts']) or 'Henüz yok.')
        if missing:text+='\nEksik/değişmiş dosyalar: '+', '.join(missing)
        if state!='completed':text+=f'\nDevam komutu: Göreve devam et: {tid}'
        if state=='completed' and cp['kind']=='answer':
            content=cp['content']
            text='\n\n'.join(section['title']+'\n'+'\n'.join(section['paragraphs']) for section in content['sections'])
            text+='\n\nKapsam: '+' '.join(content['limitations'])
            for sid in sorted({c['source_id'] for c in cp['cards']}):
                snapshot=self.research.get(sid)
                text+='\nKaynak: '+', '.join(s['url'] for s in snapshot['sources'])
        return {'status':status,'response':text,'spoken_response':text[:450] if cp['kind']=='answer' and status=='success' else f'Görev {tid} tamamlandı. Rapor ve sunum dosyaları hazır.' if status=='success' else f'Görev {tid}: {status}. Ayrıntılar ekranda.',
            'verification':cp.get('verification'),'task_id':tid,'artifacts':cp['artifacts'],'sources':cp['sources'],'answer_verified':False,
            'route':{'target':'task_brain','reason':'Plan, araştırma, öğrenme ve üretim ortak görevi'}}
    def list(self):
        with self.connect() as db:rows=db.execute('SELECT id,goal,state FROM brain_tasks ORDER BY id DESC LIMIT 20').fetchall()
        return {'status':'success','response':'\n'.join(f'{i}: {goal} | {state}' for i,goal,state in rows) or 'Henüz görev yok.'}
    def run(self,tid,model,search,cancelled=None,reader=read_document,exporter=export_report):
        goal,state,cp,error=self.load(tid)
        if state=='completed':return self.result(tid)
        if not local_model(model):return {'status':'blocked','response':'Görev için yerel LLM bağlantısı gerekli.','task_id':tid}
        cancelled=cancelled if cancelled is not None else threading.Event()
        owner=uuid.uuid4().hex
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            changed=db.execute('UPDATE brain_tasks SET owner=?,lease=?,state=? WHERE id=? AND (owner IS NULL OR lease<=?)',
                (owner,self.clock()+900,'running',tid,self.clock())).rowcount
        if not changed:return {'status':'busy','response':'Bu görev zaten çalışıyor.','task_id':tid}
        # Reload after acquisition so a concurrent completion is never replayed.
        goal,state,cp,error=self.load(tid)
        def save(state='running',error=''):
            with self.connect() as db:
                n=db.execute('UPDATE brain_tasks SET checkpoint=?,state=?,error=?,updated=?,lease=? WHERE id=? AND owner=?',
                    (json.dumps(cp,ensure_ascii=False),state,error,self.clock(),self.clock()+900,tid,owner)).rowcount
                if not n:raise RuntimeError('Görev yürütme sahipliği değişti.')
        def check():
            if cancelled.is_set():raise InterruptedError('Görev durduruldu; kayıtlar korundu.')
        def event(stage,status,detail=''):
            with self.connect() as db:db.execute('INSERT INTO brain_task_events(task_id,stage,state,detail,created) VALUES(?,?,?,?,?)',(tid,stage,status,detail[:400],self.clock()))
        stage=STAGES[0]
        try:
            for stage in cp['plan']:
                check()
                if stage in cp['completed']:continue
                event(stage,'running');print(f'🧠 Görev {tid} | {stage}',flush=True)
                if stage=='Plan':
                    cp['scope']='Kaynaklı eğitim' if cp['kind']=='training' else 'Kaynaklı video senaryosu' if cp['kind']=='video' else 'Kaynaklı rapor'
                elif stage=='Araştır':
                    found=search(research_query(goal[:180]));check()
                    if found.get('status')!='success':raise ValueError(found.get('response','Araştırma başarısız.'))
                    cp['search_id']=found.get('research_id');unique=[]
                    for source in found.get('sources',[]):
                        try:
                            url=public_url(source.get('url'))
                            if security_topic(goal) and urlsplit(url).hostname not in SECURITY_HOSTS:continue
                            if url not in [s['url'] for s in unique]:unique.append({'url':url,'title':str(source.get('title','Kaynak'))[:200]})
                        except (ValueError,TypeError):continue
                    cp['sources']=unique[:3]
                    if not cp['sources']:raise ValueError('Okunabilir kaynak bulunamadı. Siber güvenlik görevlerinde resmi kaynaklar aranır.')
                elif stage=='Oku':
                    for source in cp['sources']:
                        check()
                        if any(r['url']==source['url'] and r.get('source_id') for r in cp['reads']):continue
                        cp['reads']=[r for r in cp['reads'] if r['url']!=source['url']]
                        try:
                            page=reader(source['url'],cancelled);check()
                            if security_topic(goal) and urlsplit(page['url']).hostname not in SECURITY_HOSTS:raise ValueError('Yönlendirme resmi kaynaktan ayrıldı.')
                            sid=self.research.capture(goal,page['body'],[{'url':page['url'],'title':source['title'],'truncated':bool(page.get('partial'))}],'autonomous_document')
                            cp['reads'].append({'url':source['url'],'source_id':sid,'partial':bool(page.get('partial'))})
                        except InterruptedError:raise
                        except Exception as exc:cp['reads'].append({'url':source['url'],'error':str(exc)[:200]})
                        save()
                    if not any(r.get('source_id') for r in cp['reads']):raise ValueError('Hiçbir kaynak okunamadı; arama özeti rapor yerine kullanılmadı.')
                elif stage=='Bilgiyi işle':
                    ids=[r['source_id'] for r in cp['reads'] if r.get('source_id')]
                    self.knowledge.sync()
                    with self.knowledge.connect() as db:
                        db.execute("UPDATE knowledge_chunks SET due=0 WHERE state='error' AND source_id IN ("+','.join('?' for _ in ids)+')',ids)
                    # Three snapshots have at most twelve sections. Other background
                    # jobs cannot consume this task's processing budget.
                    for _ in range(12):
                        check();out=self.knowledge.tick(model,cancelled,source_ids=ids)
                        if out is None:break
                        save()
                        if out['status']=='error':event(stage,'source_error',out.get('detail',''))
                    check()
                    with self.knowledge.connect() as db:
                        rows=db.execute("SELECT source_id,part,card FROM knowledge_chunks WHERE state='done' AND source_id IN ("+','.join('?' for _ in ids)+') ORDER BY source_id,part',ids).fetchall()
                    cp['cards']=[{'source_id':sid,'part':part,**json.loads(card)} for sid,part,card in rows]
                    if not cp['cards']:raise ValueError('Kaynaklar işlendi olarak doğrulanamadı; içerik üretimi durduruldu.')
                elif stage=='Kaynakları karşılaştır':
                    from ..learning.verification import assess
                    selected=[]
                    for sid in sorted({c['source_id'] for c in cp['cards']}):
                        selected.extend([c for c in cp['cards'] if c['source_id']==sid][:2])
                    cp['verification']=assess(model,selected,self.research,cancelled)
                elif stage=='İçerik üret':
                    ids=sorted({c['source_id'] for c in cp['cards']})
                    cite=array({'type':'integer','enum':ids},1,3)
                    schema=obj({'title':string(5,150),'sections':array(obj({'title':string(3,120),'paragraphs':array(string(20,800),1,3),'source_ids':cite}),1 if cp['kind']=='answer' else 3,3 if cp['kind']=='answer' else 6),
                        'limitations':array(string(10,400),1,5)})
                    selected=[]
                    for sid in ids:
                        selected.extend([c for c in cp['cards'] if c['source_id']==sid][:2])
                    cp['content']=request(model,'Türkçe, işe yarayan kapsamlı içerik üret. Eğitimde öğrenme hedefi, konu anlatımı, '
                        'uygulama örneği ve değerlendirme bölümleri; video isteğinde senaryo ve sahne akışı oluştur. '
                        'Kaynakların desteklemediği rakamları, güncel fiyatları ve yapılmamış işlemleri uydurma. '
                        'Kaynak karşılaştırmasındaki conflict ve insufficient bilgilerini kesin gerçek gibi sunma; sınırlamaları açıkla. Eksik bilgiler ve varsayımlar limitations içinde. Her bölüm için yalnız verilen source_ids kullan.',
                        {'goal':goal,'kind':cp['kind'],'cards':selected,'user_profile':self.profile_context(),'verification':cp['verification']},schema,tokens=1800 if cp['kind']=='answer' else 4096,cancelled=cancelled)
                elif stage=='Dosyaları oluştur':
                    folder=Path(self.path).resolve().parent/'raporlar'
                    if folder.is_symlink() or getattr(folder,'is_junction',lambda:False)():raise ValueError('Rapor klasörü bağlantı olamaz.')
                    folder.mkdir(exist_ok=True)
                    if not cp.get('report_name'):
                        cp['report_name']='arastirma_raporu_'+uuid.uuid4().hex[:12]+'.md';save()
                    dest=folder/cp['report_name']
                    content=cp['content'];text='# '+content['title']+'\n\nSoru: '+goal+'\n\n'
                    for section in content['sections']:
                        text+='## '+section['title']+'\n\n'+'\n\n'.join(section['paragraphs'])+'\n\nDayanak kaynak kayıtları: '+', '.join(map(str,section['source_ids']))+'\n\n'
                    text+='## Kaynak karşılaştırması\n\n'
                    for item in cp['verification']['checks']:
                        text+=item['claim']+' | '+item['assessment']+' | '+item['reason']+'\n'
                    text+='Bağımsız kaynak alanı: '+str(cp['verification']['independent_domains'])+'; bu bir model eleştirisidir, bağımsız doğruluk teyidi değildir.\n\n'
                    text+='## Eksikler ve kapsam\n\n'+'\n'.join(content['limitations'])+'\n\n'
                    text+='Okuma/işleme kapsamı: '+str(len(cp['cards']))+' bölüm. Model özeti bağımsız doğruluk denetimi değildir.\n'
                    text+='\n'.join(f"Okuma kaydı: {r['url']} | "+('kısmi' if r.get('partial') else 'okundu') if r.get('source_id') else f"Okunamadı: {r['url']} | {r.get('error','')}" for r in cp['reads'])
                    text+='\n\nKaynaklar:\n'
                    for sid in sorted({c['source_id'] for c in cp['cards']}):
                        snapshot=self.research.get(sid)
                        text+=f'Kayıt {sid}: '+', '.join(s['url'] for s in snapshot['sources'])+'\n'
                    if not any(a['format']=='md' for a in cp['artifacts']):
                        if dest.exists():
                            if dest.is_symlink() or dest.read_text(encoding='utf-8')!=text:raise ValueError('Görev rapor dosyası değişmiş.')
                        else:
                            with dest.open('x',encoding='utf-8') as stream:stream.write(text)
                        cp['artifacts'].append(self.artifact(dest,'md'));save()
                    for fmt in ('docx','pdf','pptx'):
                        check()
                        if any(a['format']==fmt and Path(a['path']).is_file() for a in cp['artifacts']):continue
                        output=exporter(self.path,dest.name,fmt)
                        cp['artifacts'].append(self.artifact(output,fmt));save()
                elif stage=='Kontrol et':
                    if {a['format'] for a in cp['artifacts']}!={'md','docx','pdf','pptx'}:raise ValueError('Çıktı biçimleri eksik.')
                    for a in cp['artifacts']:
                        if self.artifact(a['path'],a['format'])['sha256']!=a['sha256']:raise ValueError('Çıktı dosyası değişmiş.')
                    cp['validation']='Dosyalar mevcut ve boş değil; içerik doğruluğu ve Office görünümü bağımsız doğrulanmadı.'
                check();cp['completed'].append(stage);save();event(stage,'done')
            save('completed');event('Görev','completed')
        except Exception as exc:
            status='cancelled' if cancelled.is_set() or isinstance(exc,InterruptedError) else 'error'
            save(status,stage+': '+str(exc)[:400]);event(stage,status,str(exc))
        finally:
            with self.connect() as db:db.execute('UPDATE brain_tasks SET owner=NULL,lease=0 WHERE id=? AND owner=?',(tid,owner))
        return self.result(tid)
    def profile_context(self):
        from ..memory.profile_fusion import ProfileMemory
        return ProfileMemory(self.path).context()
    @staticmethod
    def artifact(path,fmt):
        path=Path(path)
        if path.is_symlink() or not path.is_file() or path.stat().st_size<=0:raise ValueError('Çıktı dosyası doğrulanamadı.')
        raw=path.read_bytes()
        if fmt=='pdf' and not raw.startswith(b'%PDF-'):raise ValueError('PDF başlığı geçersiz.')
        if fmt in ('docx','pptx'):
            with zipfile.ZipFile(path) as archive:
                if archive.testzip() is not None:raise ValueError('Office dosyası bozuk.')
                required='word/document.xml' if fmt=='docx' else 'ppt/presentation.xml'
                if required not in archive.namelist():raise ValueError('Office dosyasının ana belgesi eksik.')
        return {'format':fmt,'path':str(path.resolve()),'name':path.name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
