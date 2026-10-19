"""Turn source-backed learning into reviewable changes and acceptance criteria."""
import json
import sqlite3
import time
from .priorities import FOCUS_TOPICS, track
from ..core.structured import request, obj, string, array
from ..core.action_agent import local_model

# A precise expected value may be a single character (e.g. input 0 -> output 1).
# Keep required fields and upper bounds without rejecting meaningful short receipts.
SCHEMA=obj({'problem':string(5,500),'change':string(10,1200),
            'acceptance_tests':array(obj({'input':string(1,300),'expected':string(1,500)}),1,4),
            'limitations':array(string(3,300),1,3)})

class DevelopmentEngine:
    def __init__(self,path,clock=time.time):
        self.path,self.clock=str(path),clock
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS development_jobs(source_id INTEGER,part INTEGER,state TEXT,due REAL DEFAULT 0,error TEXT DEFAULT '',proposal TEXT,PRIMARY KEY(source_id,part));
            CREATE TABLE IF NOT EXISTS development_meta(key TEXT PRIMARY KEY,value REAL NOT NULL);
            INSERT OR IGNORE INTO development_meta VALUES('last_failure_id',0);
            INSERT OR IGNORE INTO development_meta VALUES('next_analysis',0);
            CREATE TABLE IF NOT EXISTS development_demands(experience_id INTEGER PRIMARY KEY,track TEXT NOT NULL,created REAL NOT NULL);
            ''')
            columns={r[1] for r in db.execute('PRAGMA table_info(development_jobs)')}
            if 'attempts' not in columns:
                db.execute('ALTER TABLE development_jobs ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0')
    def connect(self):return sqlite3.connect(self.path,timeout=10)

    def failures(self,research):
        """Map tool receipts to curriculum; never upload personal dialogue in searches."""
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='experiences'").fetchone():return 0
            last=int(db.execute("SELECT value FROM development_meta WHERE key='last_failure_id'").fetchone()[0])
            rows=db.execute('SELECT id,receipts,state FROM experiences WHERE id>? ORDER BY id LIMIT 50',(last,)).fetchall()
            demands=[]
            for eid,raw,state in rows:
                receipts=json.loads(raw)
                failed=[r for r in receipts if isinstance(r,dict) and r.get('status') in ('error','not_found','partial')]
                if not failed and state not in ('error','not_found','partial'):continue
                tools={r.get('tool') for r in failed}
                category='context' if tools & {'youtube_search','play_music','open_website','open_app'} else 'memory' if tools & {'investigate','learn_article','recall_research'} else 'agent'
                db.execute('INSERT OR IGNORE INTO development_demands VALUES(?,?,?)',(eid,category,self.clock()))
                demands.append(category)
        # Separate commits avoid opening two writing connections to the same database.
        # Replay is idempotent if shutdown happens before advancing the cursor.
        for category in set(demands):
            research.add_topic(FOCUS_TOPICS[category])
            with research.connect() as target_db:
                target_db.execute('UPDATE autonomous_topics SET next_search=0 WHERE topic=?',(FOCUS_TOPICS[category],))
        if rows:
            with self.connect() as db:
                db.execute("UPDATE development_meta SET value=? WHERE key='last_failure_id'",(rows[-1][0],))
        return len(demands)

    def tick(self,model,cancelled=None,interval=600):
        if not local_model(model) or (cancelled and cancelled.is_set()):return None
        now=self.clock()
        with self.connect() as db:
            if db.execute("SELECT value FROM development_meta WHERE key='next_analysis'").fetchone()[0]>now:return None
            # Discover only unseen, relevant cards. Re-reading the same latest
            # 200 cards forever starves older work, even when those are finished.
            db.create_function('research_track',1,track,deterministic=True)
            db.execute("""INSERT OR IGNORE INTO development_jobs(source_id,part,state)
                SELECT k.source_id,k.part,'pending' FROM knowledge_chunks k
                JOIN research_sources s ON s.id=k.source_id
                LEFT JOIN development_jobs j ON j.source_id=k.source_id AND j.part=k.part
                WHERE k.state='done' AND j.source_id IS NULL AND research_track(s.query)!='general'
                ORDER BY k.processed_at DESC,k.source_id,k.part LIMIT 200""")
            db.execute('BEGIN IMMEDIATE') if not db.in_transaction else None
            profile=db.execute("SELECT value FROM autonomous_settings WHERE key='research_profile'").fetchone() if db.execute("SELECT 1 FROM sqlite_master WHERE name='autonomous_settings'").fetchone() else None
            priority="CASE WHEN lower(s.query) LIKE '%security%' OR lower(s.query) LIKE '%siber%' OR lower(s.query) LIKE '%owasp%' OR lower(s.query) LIKE '%nist%' THEN 0 ELSE 1 END," if profile and profile[0]=='security' else ''
            job=db.execute("SELECT j.source_id,j.part,k.card,s.query FROM development_jobs j JOIN knowledge_chunks k ON k.source_id=j.source_id AND k.part=j.part JOIN research_sources s ON s.id=j.source_id WHERE j.state IN ('pending','error','running') AND j.attempts<3 AND j.due<=? ORDER BY "+priority+"j.source_id,j.part LIMIT 1",(now,)).fetchone()
            if not job:return None
            sid,part,raw,title=job
            db.execute("UPDATE development_jobs SET state='running',due=?,attempts=attempts+1 WHERE source_id=? AND part=?",(now+1800,sid,part))
            db.execute("UPDATE development_meta SET value=? WHERE key='next_analysis'",(now+max(30,interval),))
            failures=db.execute('SELECT experience_id,track FROM development_demands ORDER BY experience_id DESC LIMIT 5').fetchall()
        try:
            proposal=request(model,
                'Whisper kişisel asistanı için uygulanabilir gelişim taslağı hazırla. Türkçe niyet, çok turlu bağlam, öncül-sonuç tutarlılığı, kullanıcı düzeltmeleri, kaynaklı hafıza ve araç sonucunu doğrulamayı önceliklendir. '
                'Siber güvenlik kartlarında güvenli kodlama, giriş doğrulama, bağımlılık güvenliği ve günlük analizini değerlendir. '
                'Verilen bilgi kartındaki alıntılara dayan. Bu kart bağımsız doğrulanmış gerçek değildir. '
                'Mevcut uygulamanın kaynak kodunu görmüyorsun; bir özelliğin kesinlikle eksik veya hatalı olduğunu iddia etme. '
                'Tek küçük değişiklik öner; kullanıcı girdisi ve gözlenebilir beklenen davranış içeren kabul testleri oluştur. '
                'Testler henüz çalıştırılmadı. Güvenlik kapatma veya yeni yetki önerme. Kod ve komut çalıştırma.',
                {'source_id':sid,'part':part,'topic':title,'card':json.loads(raw),'related_failure_categories':failures},
                SCHEMA,tokens=1800,cancelled=cancelled)
            if cancelled and cancelled.is_set():raise InterruptedError('İptal edildi.')
            with self.connect() as db:
                db.execute("UPDATE development_jobs SET state='draft',proposal=?,error='' WHERE source_id=? AND part=?",(json.dumps(proposal,ensure_ascii=False),sid,part))
            return {'status':'draft','source_id':sid,'part':part}
        except InterruptedError as exc:
            with self.connect() as db:
                db.execute("UPDATE development_jobs SET state='pending',error='',due=0,attempts=max(0,attempts-1) WHERE source_id=? AND part=?",(sid,part))
                db.execute("UPDATE development_meta SET value=? WHERE key='next_analysis'",(self.clock()+30,))
            return {'status':'cancelled','source_id':sid,'detail':str(exc)[:240]}
        except Exception as exc:
            with self.connect() as db:
                attempts=db.execute('SELECT attempts FROM development_jobs WHERE source_id=? AND part=?',(sid,part)).fetchone()[0]
                state='blocked' if attempts>=3 else 'error'
                db.execute("UPDATE development_jobs SET state=?,error=?,due=? WHERE source_id=? AND part=?",(state,str(exc)[:300],self.clock()+3600,sid,part))
            return {'status':state,'detail':str(exc)[:300]}

    def report(self):
        with self.connect() as db:
            counts=dict(db.execute('SELECT state,count(*) FROM development_jobs GROUP BY state'))
            demands=db.execute('SELECT count(*) FROM development_demands').fetchone()[0]
            rows=db.execute("SELECT source_id,part,proposal FROM development_jobs WHERE state='draft' ORDER BY source_id DESC LIMIT 5").fetchall()
        lines=[f'Gelişim: {counts.get("draft",0)} kaynaklı taslak; {demands} hata bağlantılı araştırma kaydı; {counts.get("error",0)} analiz hatası; {counts.get("blocked",0)} durdurulan taslak.',
               'Taslaklar uygulanmadı; kabul testleri çalıştırılmadı; model ağırlıkları değiştirilmedi.']
        for sid,part,raw in rows:
            p=json.loads(raw)
            lines.append(f'Kaynak {sid}, bölüm {part}: '+p['problem']+'\nÖneri: '+p['change'])
            lines.extend('Test: '+t['input']+' → '+t['expected'] for t in p['acceptance_tests'])
            lines.append('Sınırlar: '+'; '.join(p['limitations']))
        return '\n'.join(lines)
