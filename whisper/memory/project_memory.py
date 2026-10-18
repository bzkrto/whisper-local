"""Project state describes implementation availability, not successful real-world execution."""
import json
from datetime import datetime, timezone

class ProjectMemory:
    ROADMAP={
        'goal_brain':'LLM tek-adım hedef döngüsü, araç gözlemi ve deneyim hafızası; model ağırlıkları eğitilmez',
        'code_review':'taslak diff, izole test, açık kullanıcı komutuyla ZIP; manuel kurulum',
        'mission':'Araştır → Planla → Üret → Sun → Hatırla; sınırlı PDF ve araştırma üretim zincirleri var',
        'planner':'şablon planlar ve ayrı yerel model ajanı var; ajan en fazla beş doğrulanan araç adımını yürütür',
        'research_agent':'web araması, kaynak hafızası, sınırlı makale okuma ve dört biçimde kaynak dökümü var; derin sentez planlandı',
        'pdf_rag':'yerel PDF metni, sözcük araması, kaynak kontrollü kısa LLM cevabı var; OCR ve semantik arama yok',
        'report_agent':'Markdown/Word/PDF üretimi ve görev kaydı var; kapsamlı fizibilite ve uzun rapor planlandı',
        'presentation_agent':'kaynak raporunu temel PowerPoint biçiminde dışa aktarır; özgün eğitim/sunum tasarımı planlandı',
        'video_agent':'planlandı; senaryo, sahne/görsel listesi, seslendirme metni, storyboard ve thumbnail fikri',
        'video_generation':'ileri aşama; gerçek video üretimi hazır değil',
        'coding_agent':'ayrı klasörde sınırlı kod taslağı ve isteğe bağlı Docker testi; canlı sürüme geçiş yok',
        'finance_agent':'planlandı; kaynaklı maliyet, yatırım ve geri dönüş hesapları',
        'personal_agent':'temel görev/hafıza var; çok aşamalı kişisel asistan planlandı',
        'system_health':'uygulandı; 1 saniyelik CPU, RAM, disk boşluğu ve RAM kullanan süreçler; salt okunur',
        'relationships':'kategorili hafıza eklendi; yalnız açıkça kaydedilen bilgiler',
        'stt':'Türkçe model, otomatik GPU ve yerel okuma/mikrofon profili; STT kişiye özel eğitilmedi',
        'voice_output':'uyandırma için kısa işaret sesi; XTTS tekrar ayarı; isteğe bağlı Microsoft Türkçe ses',
        'reasoning_router':'uygulandı; kural tabanlı görev yönlendirmesi',
        'computer_control':'izinli araçlar ve adla dosya/klasör bulma uygulandı; tüm Windows uygulamaları kapsanmaz',
        'file_manager':'yerel dosya adlarıyla arama; varsayılan kullanıcı klasörleri, seçim ve ek arama klasörleri',
        'tasks':'uygulandı; hatırlatma yalnız Whisper açıkken',
        'sources':'uygulandı; model cevabı doğrulanmış sayılmaz',
        'github':'salt okunur yerel Git ve isteğe bağlı herkese açık GitHub API',
        'project_memory':'uygulandı',
        'multiple_models':'kurulu Ollama rolleri; kod için isteğe bağlı LM Studio',
        'gui':'ses ve yazı ortak arayüzü eklendi; ham metin, işlem yolu ve süreler; gerçek Windows ses testi bekliyor',
        'security_monitor':'hesap/cihaz oturumu takibi planlandı; bağlantı ve olay verisi yok',
        'behavior':'planlandı; açık izinli veri toplama gerekir',
        'consumption':'planlandı; tüketim kayıtları yok',
        'finance':'planlandı; harcama kayıtları yok',
        'health':'planlandı; aktivite kayıtları yok',
        'conditional_agent':'kullanıcının istediği konu takibi uygulama açıkken var; bağımsız servis yok',
        'orders':'planlandı; sipariş/ödeme otomasyonu yok',
        'self_editing':'canlı kodu değiştirme kapalı; ayrı kopyada taslak hazırlama var',
        'android':'planlandı; istemci ve güvenli köprü hazır değil',
        'pdf_learning':'uygulandı; seçilen PDF metninin yerel kaydı; model eğitilmez',
        'behavior_sources':'planlandı; insan davranışı kaynaklarından atıflı özet',
        'knowledge_base':'kategorili hafıza, yerel PDF parçaları ve araştırma kaynak kayıtları var',
        'habits':'planlandı; yalnız açık izinli ve kullanıcı sağladığı kayıtlarla',
        'order_suggestions':'planlandı; ürün araştırması/öneri, otomatik ödeme yok',
        'camera_analysis':'planlandı; açık izinli kamera/tek görüntü analizi',
        'plate_ocr':'planlandı; görüntüden plaka metni okuma',
        'face_identity':'kapsam dışı; yüz kimliği veya aynı kişi doğrulaması yapılmaz',
        'object_recognition':'planlandı; görüntüden nesne/araç/ürün tanıma',
        'behavior_patterns':'planlandı; kimlik belirlemeyen örüntü analizi'}
    def __init__(self,store):
        self.store=store
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS project_memory (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)')
            for k,v in self.ROADMAP.items():
                db.execute('INSERT INTO project_memory VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at',
                           (k,v,datetime.now(timezone.utc).isoformat()))
    def report(self):
        return '; '.join(f'{k}: {v}' for k,v in self.ROADMAP.items())
