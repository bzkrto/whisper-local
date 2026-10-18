"""Reports observed result metadata; never invents security incidents."""
import json

class SelfAnalysis:
    def __init__(self,store):self.store=store
    def report(self):
        with self.store.connect() as db:
            rows=db.execute('SELECT details FROM answer_sources ORDER BY id DESC LIMIT 50').fetchall()
        data=[json.loads(r[0]) for r in rows]
        failures=sum(d.get('status')=='error' for d in data)
        unverified=sum(d.get('status')=='unverified' for d in data)
        return f'Son {len(data)} kayıtlı komutta {failures} işlem hatası ve {unverified} doğrulanamayan cevap var. Mikrofon tanıma doğruluğu bu sayılardan ölçülemez. Hesap güvenliği olaylarını izleyecek bağlantım yok.'
