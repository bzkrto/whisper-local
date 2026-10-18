"""Source-backed user declarations extracted locally; never a truth/permission store."""
import json
import re
import sqlite3
import time
from ..core.structured import request, obj, string, array
from ..core.action_agent import local_model

SCHEMA=obj({'facts':array(obj({'slot':string(2,80),'value':string(2,400),'quote':string(5,600)}),0,5)})

class ProfileMemory:
    def __init__(self,path,clock=time.time):
        self.path=str(path);self.clock=clock
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS profile_declarations(slot TEXT PRIMARY KEY,value TEXT,quote TEXT,conversation_id INTEGER,updated REAL);
                CREATE TABLE IF NOT EXISTS profile_extractions(conversation_id INTEGER PRIMARY KEY,state TEXT,due REAL,error TEXT);
                CREATE TABLE IF NOT EXISTS profile_declaration_history(slot TEXT,value TEXT,quote TEXT,conversation_id INTEGER,created REAL);''')
    def connect(self):return sqlite3.connect(self.path,timeout=10)
    def context(self,query=''):
        with self.connect() as db:rows=db.execute('SELECT slot,value,quote,conversation_id FROM profile_declarations ORDER BY updated DESC LIMIT 40').fetchall()
        return [{'slot':s,'value':v,'source_quote':q,'conversation_id':i,'verification':'user_declaration'} for s,v,q,i in rows]
    def clear(self):
        with self.connect() as db:
            db.execute('DELETE FROM profile_declarations');db.execute('DELETE FROM profile_declaration_history')
            # Mark existing conversation records so deleted profile facts do not return.
            db.execute("INSERT OR REPLACE INTO profile_extractions SELECT id,'done',0,'' FROM conversation_history")
    def tick(self,model,cancelled=None):
        if not local_model(model) or not callable(getattr(type(model),'chat_json',None)):return None
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='conversation_history'").fetchone():return None
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT id,user_command FROM conversation_history WHERE id>(SELECT COALESCE(MAX(id),0)-50 FROM conversation_history) AND id NOT IN (SELECT conversation_id FROM profile_extractions WHERE state='done' OR due>?) ORDER BY id DESC LIMIT 1",(self.clock(),)).fetchone()
            if not row:return None
            cid,text=row
            db.execute("INSERT OR REPLACE INTO profile_extractions VALUES(?,'running',?,'')",(cid,self.clock()+600))
        try:
            def grounded(data):
                for fact in data['facts']:
                    if not re.fullmatch('[a-z0-9_.]{2,80}',fact['slot']) or fact['quote'] not in text:raise ValueError('Profil bilgisi konuşmada dayanak bulamadı.')
                return data
            data=request(model,'Yalnız kullanıcının kendisi hakkında açıkça bildirdiği kalıcı bilgileri çıkar. '
                'Örnekler: donanım, kullanılan programlar, meslek, projeler, hedefler ve iletişim tercihleri. '
                'Slot adları tutarlı İngilizce anahtarlar olsun (hardware.ram, hardware.gpu, preferences.response_length gibi). '
                'Soru, varsayım, örnek, başkası hakkında bilgi, geçici müzik komutu veya araç yetkisi kalıcı kullanıcı bilgisi değildir. '
                'Şifre, API anahtarı ve hesap erişim bilgilerini çıkarma. Emin değilsen facts boş liste. '
                'quote kullanıcının mesajındaki aynen geçen ifadeden alınmalı; değer kullanıcı beyanıdır.',
                {'user_message':text,'existing_profile':self.context()},SCHEMA,tokens=900,cancelled=cancelled,check=grounded)
            with self.connect() as db:
                for fact in data['facts']:
                    db.execute('INSERT INTO profile_declarations VALUES(?,?,?,?,?) ON CONFLICT(slot) DO UPDATE SET value=excluded.value,quote=excluded.quote,conversation_id=excluded.conversation_id,updated=excluded.updated',
                        (fact['slot'],fact['value'],fact['quote'],cid,self.clock()))
                    db.execute('INSERT INTO profile_declaration_history VALUES(?,?,?,?,?)',(fact['slot'],fact['value'],fact['quote'],cid,self.clock()))
                db.execute("UPDATE profile_extractions SET state='done',due=0,error='' WHERE conversation_id=?",(cid,))
            return {'status':'processed','facts':len(data['facts']),'conversation_id':cid}
        except Exception as exc:
            with self.connect() as db:db.execute("UPDATE profile_extractions SET state='error',due=?,error=? WHERE conversation_id=?",(self.clock()+1800,str(exc)[:240],cid))
            return {'status':'error','detail':str(exc)[:240]}
