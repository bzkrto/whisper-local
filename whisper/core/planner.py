"""Persistent planning drafts; this module never executes plan steps."""
import re
from ..common import fold, SOURCES

class Planner:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT, goal TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS plan_steps (
                plan_id INTEGER NOT NULL, step_no INTEGER NOT NULL, title TEXT NOT NULL,
                tool TEXT NOT NULL, capability TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
                evidence TEXT NOT NULL DEFAULT '', PRIMARY KEY(plan_id,step_no));''')

        with store.connect() as db:
            db.execute("UPDATE plan_steps SET capability=? WHERE tool='pdf_rag'", ('kısmen hazır: PDF metni/sayfa araması; OCR ve LLM sentezi eksik',))

    @staticmethod
    def result(text, spoken, status='success'):
        return dict(status=status,response=text,spoken_response=spoken,source=SOURCES[0],
                    route={'target':'planner','reason':'Yerel plan taslağı ve ilerleme kaydı'})

    def draft(self, goal):
        t = fold(goal)
        if 'whisper' in t and re.search(r'eksik|gelistir|proje',t):
            steps = [
                ('Kayıtlı hata sonuçlarını incele','self_analysis','hazır: kayıtlı hatalar; ses doğruluğu ölçülmez'),
                ('Yerel depo durumunu incele','github_manager','koşullu: Git deposu seçilmeli'),
                ('PDF kaynak okuma ve sayfa atıflarını geliştir','pdf_rag','kısmen hazır: PDF metni/sayfa araması; OCR ve LLM sentezi eksik'),
                ('Araştırma sonucundan Word/PDF üretimini geliştir','report_agent','eksik: rapor üretimi henüz yok'),
                ('PowerPoint üretimini geliştir','presentation_agent','eksik: sunum üretimi henüz yok'),
                ('Güvenli Android bağlantısını tasarla ve test et','android','eksik: mobil köprü henüz yok')]
        else:
            steps = [('Hedefi, kapsamı ve teslim biçimini netleştir','user','kullanıcı bilgisi gerekli'),
                     ('Kaynakları araştır ve tarihlerini kaydet','web_search','koşullu: web açık ve sonuçlar doğrulanmalı'),
                     ('Bulguları ve varsayımları değerlendir','local_llm','koşullu: yerel model açık; taslak doğrulanmalı'),
                     ('Çıktıyı hazırla ve kontrol et','report_agent','eksik: otomatik belge üretimi henüz yok')]
        with self.store.connect() as db:
            pid = db.execute('INSERT INTO plans(goal,created_at) VALUES(?,?)',(goal,self.store.now())).lastrowid
            db.executemany('INSERT INTO plan_steps(plan_id,step_no,title,tool,capability) VALUES(?,?,?,?,?)',
                           [(pid,i,title,tool,cap) for i,(title,tool,cap) in enumerate(steps,1)])
        return self.show(pid)

    def show(self, pid):
        with self.store.connect() as db:
            plan = db.execute('SELECT goal FROM plans WHERE id=?',(pid,)).fetchone()
            rows = db.execute('SELECT step_no,title,tool,capability,state,evidence FROM plan_steps WHERE plan_id=? ORDER BY step_no',(pid,)).fetchall()
        if not plan:return self.result('Bu numarada plan yok.','Plan bulunamadı.', 'error')
        text = f'Plan {pid}: {plan[0]}\nŞablon tabanlı taslak; kod/depo taraması yapılmadı. Adımlar otomatik çalıştırılmaz.\n'
        text += '\n'.join(f'{i}. {title} | Araç: {tool} | {cap} | '+ ('Araç çalıştı; sonuç kaydedildi' if state=='tool_done' else 'Kullanıcı tamamlandı bildirdi' if state=='user_done' else 'Bekliyor') for i,title,tool,cap,state,evidence in rows)
        done = sum(r[4]=='user_done' for r in rows)
        verified = sum(r[4]=='tool_done' for r in rows)
        return self.result(text,f'Plan {pid}: {verified} araç sonucu, {done} kullanıcı bildirimi. Ayrıntılar ekranda.')

    def execute(self, pid, step):
        with self.store.connect() as db:
            row = db.execute('SELECT tool,state,evidence FROM plan_steps WHERE plan_id=? AND step_no=?',(pid,step)).fetchone()
        if not row:return self.result('Plan veya adım bulunamadı.','Adım bulunamadı.','error')
        if row[1]=='tool_done':
            return self.result('Bu adım daha önce çalıştırıldı. Kayıtlı sonuç:\n'+row[2], 'Adımın kayıtlı sonucunu gösteriyorum.')
        if row[0] != 'self_analysis':
            return self.result('Bu adım için doğrulanmış çalıştırıcı henüz bağlı değil. Adım bekliyor; işlem yapılmadı.', 'Bu adım henüz çalıştırılamıyor.', 'blocked')
        from ..learning.self_analysis import SelfAnalysis
        try:
            answer = SelfAnalysis(self.store).report()
        except Exception as exc:
            return self.result('Analiz tamamlanamadı: '+type(exc).__name__, 'Analiz tamamlanamadı.', 'error')
        evidence = self.store.now() + ' | KAYNAK_SISTEM | self_analysis\n' + answer
        with self.store.connect() as db:
            db.execute("UPDATE plan_steps SET state='tool_done',evidence=? WHERE plan_id=? AND step_no=?",(evidence,pid,step))
        result = self.result(f'Plan {pid}, adım {step}: araç çalıştı.\n{evidence}\nBu sonuç hataların giderildiği anlamına gelmez.', 'Hata analizi yapıldı ve sonucu plana kaydedildi.')
        result['source'] = SOURCES[2]
        return result

    def intercept(self, command):
        t = fold(command)
        m = re.fullmatch(r'plan adim(?:i|ini) calistir\s*:?\s*(\d+)\s+(\d+)',t)
        if m:return self.execute(int(m[1]),int(m[2]))
        m = re.fullmatch(r'plan adimi sonucu\s*:?\s*(\d+)\s+(\d+)',t)
        if m:
            with self.store.connect() as db:
                row=db.execute('SELECT evidence FROM plan_steps WHERE plan_id=? AND step_no=?',(int(m[1]),int(m[2]))).fetchone()
            return self.result(row[0] if row and row[0] else 'Kayıtlı adım sonucu yok.', 'Adım sonucunu ekranda gösteriyorum.')
        if t == 'whisper projesinin eksiklerini analiz et ve gelistirme plani olustur':
            return self.draft('Whisper projesinin geliştirme planı')
        m = re.fullmatch(r'plan olustur\s*:\s*(.+)',t)
        if m:
            goal=command.split(':',1)[1].strip()
            if not 3 <= len(goal) <= 1000:return self.result('Hedef 3–1000 karakter olmalı.','Hedefi netleştirin.','clarification')
            return self.draft(goal)
        if t in ('planlarim','plan listesi'):
            with self.store.connect() as db:rows=db.execute('SELECT id,goal FROM plans ORDER BY id DESC LIMIT 20').fetchall()
            return self.result('\n'.join(f'{i}: {goal}' for i,goal in rows) or 'Kayıtlı plan yok.',f'{len(rows)} plan gösteriliyor.' if rows else 'Kayıtlı plan yok.')
        m = re.fullmatch(r'plan durumu\s*:?\s*(\d+)',t)
        if m:return self.show(int(m[1]))
        m = re.fullmatch(r'plan adimi tamamla\s*:?\s*(\d+)\s+(\d+)',t)
        if m:
            with self.store.connect() as db:
                changed=db.execute("UPDATE plan_steps SET state='user_done',evidence=? WHERE plan_id=? AND step_no=? AND state!='tool_done'",(command,int(m[1]),int(m[2]))).rowcount
            return self.result('Adım sizin bildiriminize göre tamamlandı olarak işaretlendi; uygulama sonucu bağımsız doğrulamadı.' if changed else 'Plan veya adım bulunamadı.', 'Adım tamamlandı olarak işaretlendi.' if changed else 'Adım bulunamadı.', 'success' if changed else 'error')
        return None
