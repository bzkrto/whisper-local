"""Page-cited lexical PDF retrieval. No cloud uploads, LLM calls or model training."""
import hashlib,json,re,subprocess,sys,tempfile
from pathlib import Path
from ..common import fold,SOURCES

STOP={'bu','bir','ve','ile','icin','ne','neden','nasil','nedir','mi','bana','gore','hakkinda','pdf','belge'}

class DocumentMemory:
    def __init__(self,store):
        self.store=store
        with store.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,sha256 TEXT UNIQUE NOT NULL,
                pages INTEGER NOT NULL,text_pages INTEGER NOT NULL,created_at TEXT NOT NULL);
                CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks USING fts5(
                document_id UNINDEXED,page UNINDEXED,excerpt UNINDEXED,search_text,tokenize='unicode61');''')

    @staticmethod
    def result(text,spoken,status='success',**extra):
        return dict(status=status,response=text,spoken_response=spoken,source=SOURCES[0],
                    route={'target':'documents','reason':'Yerel PDF metni ve sayfa kaynakları'},**extra)

    def ingest(self,path):
        p=Path(path.strip().strip('"')).expanduser()
        if p.suffix.lower()!='.pdf' or not p.is_file():raise ValueError('Mevcut bir PDF dosyası seçin.')
        if p.stat().st_size>32*1024*1024:raise ValueError('PDF boyutu en fazla 32 MB olabilir.')
        with p.open('rb') as stream:raw=stream.read(32*1024*1024+1)
        if len(raw)>32*1024*1024:raise ValueError('PDF boyutu en fazla 32 MB olabilir.')
        if not raw.startswith(b'%PDF-'):raise ValueError('Dosya geçerli PDF başlığı içermiyor.')
        digest=hashlib.sha256(raw).hexdigest()
        with self.store.connect() as db:
            existing=db.execute('SELECT id FROM documents WHERE sha256=?',(digest,)).fetchone()
        if existing:return self.result(f'Bu PDF zaten kayıtlı. Belge {existing[0]}.','Bu belge zaten kayıtlı.')
        # Immutable snapshot prevents the source changing between hashing and parsing.
        with tempfile.TemporaryDirectory(prefix='whisper_pdf_') as td:
            snapshot=Path(td)/'input.pdf';snapshot.write_bytes(raw)
            with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
                try:
                    process=subprocess.run([sys.executable,'-X','utf8','-m','whisper.tools.pdf_worker'],
                        input=json.dumps({'path':str(snapshot)}).encode(),stdout=output,stderr=errors,
                        cwd=str(Path(__file__).resolve().parents[2]),timeout=45,check=False,
                        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                except subprocess.TimeoutExpired:raise ValueError('PDF okuma 45 saniyelik süre sınırını aştı; kayıt yapılmadı.')
                output.seek(0);data=output.read(32*1024*1024+1)
                errors.seek(0);diagnostic=errors.read(4096).decode('utf-8',errors='replace')
                if not data and 'No module named' in diagnostic:
                    raise ValueError('PDF okuyucu modülü bulunamadı. Güncellemedeki whisper klasörünü de mevcut proje klasörüne çıkarın.')
                if not data:
                    raise ValueError(f'PDF okuyucu çıktı üretmeden kapandı (çıkış kodu: {process.returncode}).')
                if len(data)>32*1024*1024:raise ValueError('PDF metin çıktısı sınırı aştı.')
        try:parsed=json.loads(data.decode('utf-8-sig'))
        except (ValueError,TypeError):raise ValueError('PDF okuyucunun UTF-8 JSON çıktısı okunamadı. PDF okuyucu güncellemesini uygulayın.')
        if parsed.get('error'):raise ValueError(parsed['error'])
        pages=parsed.get('pages',[])
        if not pages:raise ValueError('PDF içinde çıkarılabilir metin yok. Taranmış PDF için OCR henüz eklenmedi.')
        with self.store.connect() as db:
            did=db.execute('INSERT INTO documents(name,sha256,pages,text_pages,created_at) VALUES(?,?,?,?,?)',
                (p.name,digest,parsed['page_count'],len(pages),self.store.now())).lastrowid
            for page in pages:
                text=re.sub(r'\s+',' ',page['text']).strip()
                for start in range(0,len(text),1000):
                    chunk=text[start:start+1200]
                    db.execute('INSERT INTO document_chunks(document_id,page,excerpt,search_text) VALUES(?,?,?,?)',
                               (did,page['page'],chunk,fold(chunk)))
        blank=parsed['page_count']-len(pages)
        return self.result(f'Belge {did}: {p.name}. {len(pages)}/{parsed["page_count"]} sayfanın metni kaydedildi. Metinsiz {blank} sayfa; bu sayfalar aranamaz. Model eğitilmedi.',
                           'PDF metnini sayfa kaynaklarıyla kaydettim. Ayrıntılar ekranda.')

    def search(self,query,document_id=None,page=None):
        normalized=fold(query)
        tokens=list(dict.fromkeys(w for w in re.findall(r'\w+',normalized)
                                 if (len(w)>2 or w.isdigit()) and w not in STOP))[:12]
        if not tokens:return self.result('Aranacak konuyu belirtin.','Konuyu belirtin.','clarification')
        article=re.search(r'\bmadde\s*(\d+)\b',normalized)
        if article:
            # Phrase search retains the requested number; 87 must not match 870.
            expression='"madde '+article.group(1)+'"'
        else:
            # All meaningful words required. Numbers use exact tokens, no prefix.
            expression=' AND '.join('"'+w+'"'+('' if w.isdigit() else '*') for w in tokens)
        with self.store.connect() as db:
            scope='';params=[expression]
            if document_id is not None:
                scope+=' AND d.id=?';params.append(document_id)
            if page is not None:
                scope+=' AND c.page=?';params.append(page)
            rows=db.execute('''SELECT d.id,d.name,c.page,c.excerpt FROM document_chunks c
                JOIN documents d ON d.id=c.document_id WHERE document_chunks MATCH ?
                '''+scope+' ORDER BY bm25(document_chunks) LIMIT 100',params).fetchall()
        if article:
            # Prefer the article heading over table-of-contents/reference mentions.
            heading=re.compile(r'\bmadde\s*'+re.escape(article.group(1))+r'\s*[-–—:.]')
            rows.sort(key=lambda row:0 if heading.search(fold(row[3])) else 1)
        unique=[];seen=set()
        for row in rows:
            key=(row[0],row[2],row[3])
            if key not in seen:unique.append(row);seen.add(key)
            if len(unique)==4:break
        rows=unique
        if not rows:return self.result('Kayıtlı PDF metinlerinde sözcük eşleşmesi bulunamadı. Bu, konunun belgede kesinlikle olmadığı anlamına gelmez.',
                                       'PDF metninde eşleşme bulamadım.','unverified')
        sources=[dict(document_id=i,name=name,page=int(page),excerpt=text) for i,name,page,text in rows]
        text='PDF metninden ilgili alıntılar; otomatik cevap veya bağımsız doğrulama değildir.\n'
        text+='\n\n'.join(f'[{name}, sayfa {page}, belge {i}]\n{excerpt}' for i,name,page,excerpt in rows)
        return self.result(text,'PDF kaynaklarını sayfa numaralarıyla ekranda gösteriyorum.',document_sources=sources)

    def export_report(self,query):
        result=self.search(query)
        if not result.get('document_sources'):return result
        import uuid
        directory=Path(self.store.path).resolve().parent/'raporlar'
        directory.mkdir(exist_ok=True)
        destination=directory/('pdf_kaynak_raporu_'+uuid.uuid4().hex[:12]+'.md')
        body='# PDF kaynak raporu\n\nKonu: '+query+'\n\n'+result['response']+'\n\nBu rapor yerel sözcük aramasından bulunan alıntılardır; kapsamlı araştırma veya bağımsız doğrulama değildir.\n'
        with destination.open('x',encoding='utf-8') as f:f.write(body)
        return self.result('Kaynak raporu kaydedildi: '+str(destination), 'PDF kaynak raporu kaydedildi.', artifact_path=str(destination),document_sources=result['document_sources'])

    def intercept(self,command):
        t=fold(command)
        if t.startswith('pdf kaynak raporu:'):
            try:return self.export_report(command.split(':',1)[1].strip())
            except OSError:return self.result('Kaynak raporu yazılamadı.','Rapor kaydedilemedi.','error')
        if t.startswith('pdf ogren:'):
            try:return self.ingest(command.split(':',1)[1])
            except (ValueError,OSError) as exc:return self.result(str(exc),'PDF kaydedilemedi. Ayrıntılar ekranda.','error')
        if t in ('belgelerim','pdf listesi'):
            with self.store.connect() as db:rows=db.execute('SELECT id,name,pages,text_pages FROM documents ORDER BY id DESC LIMIT 30').fetchall()
            return self.result('\n'.join(f'{i}: {name} — {tp}/{p} sayfa metinli' for i,name,p,tp in rows) or 'Kayıtlı PDF yok.',f'{len(rows)} belge gösteriliyor.')
        if t.startswith(('pdf sor:','pdf cevap raporu:')):
            from .document_answer import parse_question
            question,did,page=parse_question(command.split(':',1)[1])
            result=self.search(question,document_id=did,page=page)
            if result.get('document_sources'):
                result['document_question']=question
                if t.startswith('pdf cevap raporu:'):
                    result['document_report_question']=question
            return result
        if t.startswith(('pdfde ara:','pdf\'de ara:','belgede ara:')):
            from .document_answer import parse_question
            question,did,page=parse_question(command.split(':',1)[1])
            return self.search(question,document_id=did,page=page)
        m=re.fullmatch(r'belgeyi unut\s*:\s*(\d+)',t)
        if m:
            with self.store.connect() as db:
                db.execute('DELETE FROM document_chunks WHERE document_id=?',(int(m[1]),))
                changed=db.execute('DELETE FROM documents WHERE id=?',(int(m[1]),)).rowcount
            return self.result('Belge metni bilgi tabanından silindi; özgün PDF dosyası korunuyor.' if changed else 'Belge bulunamadı.', 'Belge hafızadan silindi.' if changed else 'Belge bulunamadı.')
        return None
