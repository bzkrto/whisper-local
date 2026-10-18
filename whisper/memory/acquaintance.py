"""User-controlled, one-question-at-a-time local profile interview."""
import sqlite3
from ..common import fold

QUESTIONS = [
    ('hitap', 'Size nasıl hitap etmemi istersiniz?'),
    ('is', 'Ne iş yapıyorsunuz veya hangi alanda çalışmak istiyorsunuz?'),
    ('projeler', 'Şu sıralar üzerinde çalıştığınız en önemli projeler neler?'),
    ('hedef', 'Önümüzdeki üç ayda ulaşmak istediğiniz en önemli hedef nedir?'),
    ('destek', 'Günlük hayatınızda en çok hangi işlerde yardımcı olmamı istersiniz?'),
    ('ilgi', 'Hangi konulara ilgi duyuyorsunuz?'),
    ('ogrenme', 'Öğrenmek veya geliştirmek istediğiniz beceriler neler?'),
    ('deneyim', 'Hangi konularda deneyimlisiniz, hangilerine yeni başlıyorsunuz?'),
    ('anlatim', 'Yanıtlarım kısa mı, ayrıntılı mı, örneklerle mi olsun?'),
    ('uslup', 'Sizinle resmi mi, samimi mi konuşmamı tercih edersiniz?'),
    ('dil', 'Hangi dillerde iletişim kurmak veya pratik yapmak istersiniz?'),
    ('calisma', 'Genellikle hangi saatlerde çalışır, hangi saatlerde dinlenirsiniz?'),
    ('sessizlik', 'Hangi saatlerde sesli bildirim istemezsiniz? Bu tercih kayıt olur; otomatik sessiz saat uygulaması henüz yok.'),
    ('planlama', 'İşlerinizi günlük planla mı yoksa ihtiyaç çıktıkça mı yürütürsünüz?'),
    ('zorluk', 'İşlerinizi yaparken en sık karşılaştığınız güçlük nedir?'),
    ('uygulamalar', 'Bilgisayarda en sık kullandığınız programlar hangileri?'),
    ('dosyalar', 'Çalışma dosyalarınızı nasıl düzenlemeyi tercih edersiniz?'),
    ('arastirma', 'Hangi konulardaki gelişmeleri takip etmemi istersiniz? Bu yanıt tercih olarak saklanır; araştırma konusu ekle komutuyla gündeme alınır.'),
    ('kaynaklar', 'Güvendiğiniz yayınlar veya bilgi kaynakları hangileri?'),
    ('karar', 'Önerilerimde maliyet, hız, kalite veya başka hangi ölçüt öncelikli olsun?'),
    ('hobiler', 'Boş zamanlarınızda neler yapmaktan hoşlanırsınız?'),
    ('muzik', 'Hangi müzik türlerini veya sanatçıları seversiniz?'),
    ('yer', 'Yerel öneriler için hangi şehir veya bölgeyi esas almamı istersiniz? İsterseniz bu soruyu geçebilirsiniz.'),
    ('iletisim', 'Sizden açıklama isterken seçenek sunmamı mı, açık uçlu soru sormamı mı tercih edersiniz?'),
    ('sinirlar', 'Sormamamı veya hafızada tutmamamı istediğiniz konular var mı?'),
    ('ek', 'Sizi daha iyi tanımam için eklemek istediğiniz başka bir şey var mı?'),
]


class Acquaintance:
    def __init__(self, path):
        self.path = str(path)
        self.pending = None
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS acquaintance_answers(key TEXT PRIMARY KEY,answer TEXT,state TEXT);
                CREATE TABLE IF NOT EXISTS acquaintance_settings(key TEXT PRIMARY KEY,value TEXT);
                INSERT OR IGNORE INTO acquaintance_settings VALUES('paused','0');''')

    def connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def next_question(self, resume=False):
        with self.connect() as db:
            if resume:
                db.execute("UPDATE acquaintance_settings SET value='0' WHERE key='paused'")
            if db.execute("SELECT value FROM acquaintance_settings WHERE key='paused'").fetchone()[0] == '1':
                return None
            answered = {r[0] for r in db.execute('SELECT key FROM acquaintance_answers')}
        for key, question in QUESTIONS:
            if key not in answered:
                self.pending = key
                return question + ' İsterseniz “geç” veya “tanışmayı durdur” diyebilirsiniz.'
        self.pending = None
        return None

    def context(self):
        with self.connect() as db:
            rows = db.execute("SELECT key,answer FROM acquaintance_answers WHERE state='answered'").fetchall()
        return '\n'.join(f'{k}: {a[:250]}' for k, a in rows)[:4500]

    def handle(self, text, is_command=False):
        t = fold(text).strip().rstrip('.!?')
        if t.startswith('cevabim:'):
            text = text.split(':', 1)[1].strip()
            t = fold(text).strip().rstrip('.!?')
            is_command = False
        if t in ('tanismaya baslayalim', 'beni tani', 'tanismaya devam', 'tanismaya devam edelim'):
            return self.next_question(True) or 'Tanışma soruları tamamlandı. Profilimi göster diyebilirsiniz.'
        if t in ('tanismayi durdur', 'sonra devam edelim', 'simdi degil'):
            self.pending = None
            with self.connect() as db:
                db.execute("UPDATE acquaintance_settings SET value='1' WHERE key='paused'")
            return 'Tanışmayı durdurdum. Tanışmaya devam diyebilirsiniz.'
        if t == 'profilimi goster':
            return self.context() or 'Henüz tanışma yanıtı kaydedilmedi.'
        if t == 'profilimi unut':
            with self.connect() as db:
                db.execute('DELETE FROM acquaintance_answers')
                db.execute("UPDATE acquaintance_settings SET value='1' WHERE key='paused'")
            self.pending = None
            return 'Tanışma yanıtlarını sildim. Diğer konuşma ve deneyim kayıtları bu komutun kapsamı dışındadır.'
        if not self.pending or is_command:
            return None
        if '?' in text or t in ('merhaba', 'selam', 'nasilsin'):
            return 'Tanışma sorusunu sonra yanıtlayabilirsiniz. ' + dict(QUESTIONS)[self.pending]
        if not 1 <= len(text.strip()) <= 1200:
            return 'Yanıtınızı 1200 karakterden kısa söyleyebilir misiniz?'
        skip = t in ('gec', 'bunu gec', 'cevaplamak istemiyorum')
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO acquaintance_answers VALUES(?,?,?)',
                       (self.pending, '' if skip else text.strip(), 'skipped' if skip else 'answered'))
        self.pending = None
        return ('Soruyu geçtim. ' if skip else 'Yanıtınızı kaydettim. ') + (self.next_question() or 'Tanışma soruları tamamlandı.')
