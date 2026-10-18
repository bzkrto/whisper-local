# Güncel sürüm: V15
Önce WHISPER_V15_NOTLARI.md dosyasını okuyun.

# Güncel sürüm: V14
Kurulum ve yeni komutlar için önce WHISPER_V14_NOTLARI.md okuyun.

# Güncel sürüm: V13

Yeni kurulum ve gerçek yetenek sınırları için WHISPER_V13_NOTLARI.md dosyasını okuyun.
Başlatma: `.\.venv\Scripts\python.exe .\whisper_bootstrap.py`.
Aşağıdaki V12 bölümleri önceki sürüm geçmişidir.

## V12 performans ve ilişkiler hafızası güncellemesi

`Bilgisayarım yavaşladı` veya `Performans kontrolü yap`: 1 saniyelik işlemci
kullanımı, RAM doluluğu, kullanıcı klasörünün bulunduğu diskte boş alan ve RAM
kullanan ilk üç süreci ölçer. Sonuç `KAYNAK_SISTEM` olur; LLM/web kullanılmaz.
Ekranda ayrıntılı değerlendirme, seste kısa ölçüm özeti verilir. İşlemci/RAM
%90 veya üzerindeyse ya da boş disk alanı %10 altındaysa gözden geçirme önerisi
verilir. Bunlar bu örneğin eşikleridir; kesin arıza nedeni veya disk hızı değildir.
Sıcaklık, disk gecikmesi ve kötü amaçlı yazılım ölçülmez. Süreç sonlandırma,
dosya silme veya sistem ayarı değişikliği yapılmaz. Ölçülemeyen veride başarı
iddiası yerine hata raporlanır. Süreç adları ölçüm kanıtıyla yerelde saklanır.

İlişkiler kategorisi: `Hafızaya kaydet: relationships = Ali proje arkadaşım`;
sorgu `Hafıza: relationships`. Sadece senin açıkça verdiğin kayıtlar tutulur.

`WHISPER_V12_GUNCELLEME.zip` içindeki dosyaları mevcut klasöre birleştir;
aynı adlı dosyaları değiştir. Yeni kurulum veya model indirme yok. Bu güncelleme
önceki ses/Chrome düzeltmesini de içerir. 73 otomatik test geçti; gerçek Windows
performansı ve mikrofon doğruluğu burada ölçülmedi.

## V12 ses/komut düzeltmesi

Son ekranda tanınan `goggle chrome aç` için sınırlı Chrome eşlemesi eklendi.
Başlatma yanıtı kısa ve düz: `Chrome başlatıldı.` XTTS'ye gönderilen gerçek
metin `Seslendirme metni:` satırında görünür. Model ağırlıkları ve ses seçimi
korundu. Bu değişiklik bir telaffuz/akustik doğruluk testi değildir; yazıda
olmayan ek heceler sürerse referans ses/XTTS kalitesi ayrıca incelenmelidir.
67 otomatik test geçti. `WHISPER_V12_SES_DUZELTME.zip` yalnız mevcut
`whisper_ses_v12.py` dosyasını değiştirir; yeniden kurulum veya indirme gerekmez.

# WHISPER V12 — Türkçe tanıma ve modüler katmanlar

`BASLATMA.txt` içindeki komutu kullan. ZIP'teki `whisper` klasörü dahil bütün
kod dosyalarını mevcut klasöre çıkar; mevcut `.venv` ve kişisel veritabanını koru.
`.cmd` Windows Akıllı Uygulama Denetimi tarafından engellenirse güvenliği kapatmadan
Python komutuyla başlat. Bu sürüm V11 yönergesinin yerine geçer.

## Ses tanıma

Varsayılan artık `vincespeed/faster-whisper-large-v3-turbo-turkish` (CPU int8,
beam 5, `language=tr`, `task=transcribe`). Bu model Selim Çavaş'ın Türkçe Common
Voice verisiyle uyarladığı turbo modelinin CTranslate2 dönüştürmesidir.
Yaklaşık 1.6 GB; ilk açılışta internetten indirilir, sonraki çıkarım yereldir.
Kaynaklar:
https://huggingface.co/selimc/whisper-large-v3-turbo-turkish
https://huggingface.co/vincespeed/faster-whisper-large-v3-turbo-turkish

Komut kelimeleri `hotwords` ipucu olarak verilir (destekleyen faster-whisper
sürümlerinde). Kişisel hafıza tanıma ipucuna eklenmez. Düşük model skoru olan
sesler yürütülmez; tekrar istenir. Skor kalibre edilmiş doğruluk yüzdesi değildir.
Belirsiz `Chrome Watch/Edge` komutları araştırma veya eyleme dönüştürülmez.
Bu eşik doğru bazı cümleleri de reddedebilir. Mikrofon ses kaydı olmadan gerçek
kelime hata oranını ve modelin önceki modele üstünlüğünü bu ortamdan ölçemedik.
CPU'da gecikme sürebilir. `--whisper-model large-v3-turbo` önceki modele dönüş
seçeneğidir. Model ağırlıkları pakete dahil değildir; otomatik indirilir.
Hotwords kaynak: https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py

## Katmanlar ve örnekler

- Reasoning Router: deterministik görev seçimi; saat/tarih ve izinli PC
  işlemleri LLM'e gitmez. Genel bilgi yerel modele, güncel soru web aramasına gider.
  Kural tabanlı yönlendirme genel bir muhakeme modeli veya işletim sistemi değildir.
- Kaynak takibi: her cevap `KAYNAK_HAFIZA`, `KAYNAK_INTERNET`,
  `KAYNAK_SISTEM` veya `KAYNAK_TAHMIN` etiketiyle kaydedilir. Modelin hafızayı
  görmesi tek başına cevabının oradan türediğini kanıtlamaz; genel model cevabı
  temkinli biçimde tahmin etiketlenir. Web sonucu da bağımsız doğrulama değildir.
- Kategorili hafıza: personality/projects/goals/hardware/preferences.
  Kaydetme ve sorgulama doğrudan yapılır. Kategorili bellek yeni bir tablodur;
  eski düz profil korunur, eski bilgiler otomatik kategorilere dağıtılmaz.
- Proje hafızası: uygulanan/planlanan özelliklerin açık durumları saklanır.
  Davranış/finans/sağlık/tüketim ve koşullu web izleme hazırmış gibi raporlanmaz.
- Vektör hafıza: yerel karakter üçlüleri ve kosinüs benzerliğiyle kayıt arama.
  Bu sözcüksel aramadır; semantik embedding modeli veya öğrenilmiş hafıza değildir.
- Görevler ve hatırlatmalar: SQLite'ta kalıcı; İstanbul saatiyle tarih hesaplanır.
  Whisper kapalıyken işletim sistemi bildirimi yok; açıkken/gecikmişse bildirilir.
  Yoğun model/TTS işlemi devam ederken bildirim sıra bekler. Bildirim yapılan
  görev manuel tamamlanana kadar listede kalır.
- Çoklu Ollama rolleri: kurulu Qwen/Gemma/DeepSeek/Phi adlarına göre aday seçer.
  Bulunmayan rolde seçili ana model kullanılır. Otomatik model indirme yok.
  İsim seçimi modelin göreve uygunluğunu ölçmez; kullanıcı tam adı sabitleyebilir.
- Kod için LM Studio: isteğe bağlı `--coding-backend lmstudio`; sunucu yoksa
  Ollama'ya döner. Olağan kullanımda Ollama sürer. Gemini/Edge sağlayıcıları
  eski açık izinli seçeneklerle korunur; web kullanımı Gemini'yi otomatik açmaz.
- Basit GUI: yazıyla iletişim ve kaynak etiketi; mikrofon arayüzü henüz yok.
- Hata analizi: yalnız kayıtlı sonuç durumlarını sayar; STT doğruluğu,
  zararlı dosya veya hesap güvenliği olayları tespit etmiş gibi davranmaz.

```text
Saat kaç?
Google Chrome aç
YouTube'u aç
Dosyalarımı aç
Discord aç
VS Code aç
Steam aç
Ekran görüntüsü al
Ses seviyesini artır
Bilgisayarı yeniden başlat
Hafızaya kaydet: hardware = RTX 5070 kullanıyorum
Benim ekran kartım neydi?
Hafızaya kaydet: projects = Whisper geliştiriyorum
Hafıza: projects
Hafızada ara: ekran kartı
Bu bilgiyi nereden öğrendin?
Görev ekle: Whisper GUI ses entegrasyonu
Yarın saat 10:00’da bana hatırlat: toplantı
Görevlerim
Görevi tamamla: 1
Proje durumu
Hataları analiz et
Eksikler ne?
```

Yeniden başlatma 60 saniyelik açık onay ister; araya farklı komut girerse
onay iptal edilir. `--enable-tools` kapalıysa onay da eylem başlatamaz.
Ekran görüntüsü yalnız açık komutla `Pictures/Whisper` içine kaydedilir.
Uygulamalar yalnız sabit kurulum konumlarından/izin listesinden bulunur;
kurulu olmayan uygulama indirilmeye çalışılmaz. Discord/Steam/VS Code gerçek
Windows kurulumunda burada denenmedi. Araç sonuçları işlem isteğini raporlar;
her uygulamanın açılmış olduğunu ekranla doğrulamaz.

## Git ve GitHub

Yerel Git için `--repo "C:\proje\whisper"` ekle:
`Repo durumu ne?`, `Son commit ne yaptı?`.
Git kurulu olmalı. Yazma/commit/push yok; takip edilmeyen dosyalar status özetinde yok.

Herkese açık GitHub için `--github-repo OWNER/REPO --web` ekle:
`GitHub son commit`, `GitHub görevleri`. Salt okunur public API; özel repo veya
hesap/cihaz oturumuna erişim yok. Liste ilk 10 issue/PR girdisinden issue'ları
gösterir; eksiksiz liste veya güvenlik taraması değildir. GitHub kotası olabilir.
Bu ortamda gerçek GitHub ağı yerine API yanıtları simüle edilerek kontrol edildi.

Tam rol adı seçimi: `--role-model code=KURULU_MODEL_ADI`.
Birden çok model aynı anda isteğe gönderilmez; Ollama/LM Studio kendi bellek
politikasını yönetir. Donanım kapasitesinde tüm modellerin birlikte sığdığı varsayılmaz.

## Onaylı geliştirme ve güvenlik

`Eksikler ne?` öneri sunar; 60 saniye içinde `evet` yalnız geliştirme görevlerini
kaydeder. Kendi kodunu değiştirmez. Ödeme, sipariş ve paylaşım araçları eklenmedi.
Hesap oturumu, bilinmeyen site veya indirilen dosya için otomatik tehdit
algılama bağlantısı yok. Bunlar proje hafızasında planlanan aşamalardır.

İlk şema genişletmesinde mevcut veritabanının SQLite yedeği
`whisper_memory.db.pre_v12.bak` olarak alınır; var olan yedek üzerine yazılmaz.
Kişisel veritabanı/yedek bu ZIP'e dahil değildir. Yeni testler geçici veritabanı
kullanır. Tam bağımsız güvenlik denetimi yapılmadı.

## Nihai hedef

Araştır → Planla → Üret → Sun → Hatırla. Planner, kaynaklı araştırma,
büyük PDF belgeleri için sayfa bazlı RAG, Word/PDF rapor ajanı, PowerPoint
sunum/eğitim ajanı, video senaryosu/storyboard ajanı ve ileride video üretimi
proje hafızasına planlandı olarak kaydedildi. Şu anda gerçek belge/video
çıktı üretimi uygulanmadı. Yol haritası aşamaları paket sürüm numaralarıyla aynı şey değildir.

## Ek hedefler

PDF öğrenme, kaynaklı davranış özetleri, belge bilgi tabanı, alışkanlık/örüntü analizi,
sipariş önerileri, kamera/nesne/araç/ürün analizi ve plaka OCR proje hafızasına
planlanan aşamalar olarak kaydedildi. Yüz kimliği veya aynı kişi karşılaştırması
eklenmez. `WHISPER_YOL_HARITASI.md` güncel durumları listeler.

66 otomatik test geçti; gerçek ses modeli/GPU, Windows araçları ve GUI görsel
kontrolü bu ortamda yapılmadı. Yerel Git gerçek geçici depoda test edildi; model,
web ve GitHub yanıtları simüle edildi.

## Modüler kaynak düzeni

```text
whisper/core/reasoning.py
whisper/memory/user_memory.py
whisper/memory/project_memory.py
whisper/memory/vector_memory.py
whisper/ai/router.py
whisper/tools/task_manager.py
whisper/tools/github_manager.py
whisper/learning/self_analysis.py
whisper/ui/desktop_gui.py
```

Çalışan eski ses/model adaptörleri ve ana beyin `whisper_ses_v12.py` içindedir;
hepsini bir anda ayırarak çalışan ses kurulumunu değiştirmedik. Kökteki
`assistant_layers.py` ve `whisper_gui.py` uyumluluk girişleridir.

---

# WHISPER V11 — tek dosyayla başlatma

Mevcut Windows kurulumu için: WHISPER_SES_V11.zip içindeki **tüm dosyaları**
masaüstündeki `whisper astra` klasörüne çıkar; `.venv` bu klasörde kalmalı.
Çalışan eski WHISPER penceresini Ctrl+C ile kapat. Ollama açıkken
`WHISPER_BASLAT.cmd` dosyasına çift tıkla. Mevcut kurulumu yeniden kurma.

Başlatıcı mikrofon sürücüsünü, ses bağımlılıklarını, internet arama paketini ve
kurulu `qwen3:8b` modelini kontrol eder; eksik varsa hatayı açık pencerede gösterir.
Bu kontrol gerçek tanıma doğruluğu ya da internet sağlayıcısının erişilebilirliği testi değildir.
İlk açılışta `large-v3-turbo` otomatik indirilir; internet ve disk alanı gerekir.
İndirme/model yükleme sırasında pencereyi kapatma. Sonraki açılışlar önbelleği kullanır.

## Bu pakette değişenler

- Konuşma tanıma: `small` yerine yerel, Türkçe `large-v3-turbo`.
- Mikrofon sinyalinde DC ofseti temizliği ve int16 taşma düzeltmesi; VAD için
  daha düşük eşik ve hece başı/sonu payı. Tanıma ipucuna kişisel hafıza eklenmez.
- `Whisper`, `Visper`, `Wisper`, `Vhisper` tam sözcükleri tetikleyebilir.
  Yanıttan sonra 5 saniye içinde yeni konuşmada tekrar tetikleme gerekmez.
- `Google Chrome uygulamasını aç`, `Microsoft Edge programını aç`,
  `lütfen hesap makinesini aç`, `not defterini açabilir misin` doğrudan
  izinli PC aracına gider. `Esap makinesini aç` için sınırlı yazım eşlemesi vardır.
- Sohbet Qwen3:8b, tanıma Whisper, seslendirme XTTS-v2/Craig Gutsy ile yapılır.
  İnternet araması başlatıcıda açıktır; arama sorgusu dış sağlayıcıya gönderilir.
  Google mikrofon tanıması ve bulut sohbet açılmaz.
- Kurulum sorunlarını çalışma başlamadan gösteren tek başlatıcı eklendi.

Daha güçlü tanıma modeli CPU'da `small` modelinden yavaş olabilir. Bu paket
STT ve XTTS için CPU kullanır; Qwen Ollama'nın mevcut donanım ayarını kullanır.
RTX 5070 üzerinde CUDA/STT sürücüsü ve ortak VRAM kullanımını burada ölçemedik.
Kesin hız veya Google düzeyinde doğruluk garantisi verilemez.
Ses karakteri mevcut çalışan Craig Gutsy olarak korundu; referans ses ile değiştirilebilir.

Tam çıkış Ctrl+C. Beş saniye sessizlik sohbet oturumunu kapatır; yeniden sesle
uyanmak için mikrofon dinlemesi sürer. Gerçekten tüm dinlemeyi kapatırsan yeniden
sesle uyanamaz; ayrı düşük güçlü wake-word motoru henüz eklenmedi.
Android istemci henüz hazır değil.

## Gerektiğinde tek başına tanıma ölçümü

Normal kullanım için yukarıdaki başlatıcı yeterli. Tanıma sorununu ayırmak
istersen aşağıdaki komut üç kısa kayıtta tanınan metni, kayıt seviyesini ve süreyi
ölçer; sohbet/seslendirme/PC işlemlerini başlatmaz, kayıt dosyası oluşturmaz:

```powershell
.\.venv\Scripts\python.exe whisper_ses_v11.py --test-stt --stt whisper --whisper-model large-v3-turbo --whisper-device cpu
```

Kod yolları ve hata durumları simüle testlerle kontrol edildi. Gerçek Windows
mikrofonu, yeni model ve XTTS birlikte bu ortamdan çalıştırılamadı.

---

# WHISPER — yerel model ve kayıtlı görevler

## Mimari

Yerel Ollama / LM Studio / llama.cpp modeli + SQLite hafıza + yerel Whisper
konuşma tanıma + izinli PC işlemleri. Model eğitimi yapılmaz. Varsayılan:
Ollama, yerel Whisper STT, Windows SAPI ses, kapalı web/bulut/ağ erişimi.
Bu geliştirme sürümüdür; bağımsız güvenlik denetimi yapılmadı.

## Windows kurulumu

Python 3.11/3.12 ve Ollama kurulu olmalı. Ollama modelini RAM/VRAM kapasitesine
göre seçip önce indir. Model indirme internet kullanır. Model adı `ollama list`
çıktısındaki kurulu modelle aynı olmalı; `YEREL_MODEL_ADI` aşağıda yer tutucudur.

Ollama'nın kendi bulut geçişini kapatmak için Windows kullanıcı ortam değişkenine
`OLLAMA_NO_CLOUD=1` ekle ve Ollama'yı tamamen kapatıp yeniden başlat.
Sadece WHISPER terminaline değişken eklemek, zaten açık Ollama'yı etkilemez.
Kaynak: https://docs.ollama.com/faq

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama list
.\.venv\Scripts\python.exe whisper_core.py --backend ollama --model YEREL_MODEL_ADI --enable-tools
```

Yerel modeli burada kurmadık/indirmedik; kullanıcının bilgisayarında yapılmalı.
Ekran analizi için görüntü destekleyen yerel model ve `--enable-screen` ekle.
Uyumlu görüntü API'si: https://docs.ollama.com/api/openai-compatibility

Ollama metin sohbeti `/api/chat` kullanır; `think: false` ile Qwen3 düşünme
modu kapatılır. Yanıt token sınırı `num_predict`, bağlam `num_ctx` olarak
gönderilir. Boş veya yarıda kesilen yanıt başarı olarak kaydedilmez.
Kaynak: https://docs.ollama.com/capabilities/thinking

İlk metin testi (qwen3:8b kuruluysa):

```powershell
.\.venv\Scripts\python.exe whisper_core.py --backend ollama --model qwen3:8b --text --tts none
```

Ardından `Fotosentezi Türkçe iki cümlede açıkla.` yaz. Bu sürümün API davranışı
simüle edilmiş yanıtlarla test edildi; gerçek model/GPU/ses testi bilgisayarında
yapılmalıdır. Yanıt yavaşsa ayrı PowerShell'de `ollama ps` ile CPU/GPU kullanımını kontrol et.

## Veri akışı ve ses

### Tanıma düzeltmesi ve özel yerel ses

- Hafıza girdileri STT ipucuna eklenmez; yanlış kelimenin tanımaya geri beslenmesi engellenir.
- Düşük güvenli/sessizlik içeren segmentler elenir; tanıma süresi ayrıca gösterilir.
- Mikrofon eşiğinin alt sınırı 0.002, ön kayıt payı 420 ms; kısık hecelerin kesilmesini azaltmak amaçlanır.
- Varsayılan beam 3; `--whisper-beam 1` daha az arama yapar, doğruluk düşebilir.
- Yalnız kişisel ifade içeren komutlardan modelin kişisel bilgi kaydı kabul edilir.
- Yanlış kaydı kaldırmak için metin modunda `Bilgiyi unut: sadkac` yazılabilir.

XTTS-v2 referans sesi kullanarak Türkçe özel ses üretir; sohbet ve ses üretimi
yereldir, ilk model indirmesi internet gerektirir. 10–20 saniye temiz, tek kişi,
müziksiz WAV referansı kullan. Model lisansı indirme sırasında ayrıca gösterilir;
otomatik kabul edilmez. Kaynak: https://huggingface.co/coqui/XTTS-v2

Referans kayıt zorunlu değildir: `--xtts-speaker "Craig Gutsy"` hazır ses seçer.
Bu başlangıç adayıdır; sesin genç/bariton karakteri dinlenerek değerlendirilmeli.
Diğer deneme adayları: `Dionisio Schuyler`, `Luis Moray`.
Kaynak: https://coqui-tts.readthedocs.io/en/latest/models/xtts.html

İsteğe bağlı paketler (büyük indirmeler; mevcut ses kurulumu için zorunlu değil):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ses.txt
.\.venv\Scripts\python.exe whisper_core.py --test-voice --tts xtts --xtts-speaker "Craig Gutsy" --xtts-device cpu
.\.venv\Scripts\python.exe whisper_core.py --test-voice --tts xtts --speaker-wav referans.wav --xtts-device cpu
```

CPU ile ses üretimi yavaş olabilir; CUDA seçimi uygun PyTorch/CUDA kurulumu ve
boş VRAM ister. Qwen + STT + XTTS aynı GPU'da belleği paylaşır; donanımda ölçmeden
hız garantisi yok. Referans özellikleri bir kez hesaplanıp oturum boyunca kullanılır.
XTTS bağlantısı simüle API ile doğrulandı.
Kullanıcı bilgisayarında Craig Gutsy ses denemesi çalıştı; telaffuz ve hız
iyileştirmeleri sürüyor. Coqui 0.27.5 için Transformers 4.57.6 sabitlendi;
Transformers 5.x `isin_mps_friendly` import hatası verebilir.
Kaynak: https://github.com/idiap/coqui-ai-TTS/issues/558
Saat seslendirmede yazıya çevrilir (`23:02`: `yirmi üçü iki geçiyor`).
PC komutları `hesap makinesini aç`, `hesap makinasını aç`, `not defterini aç`
gibi ekli adları da doğrudan izinli araca yönlendirir; modelin yanıtı beklenmez.
Gerçek STT doğruluğu ve yeni mikrofon eşiği kullanıcının sesinde ölçülmelidir.

- Varsayılan sohbet/hafıza/görüntü yerel model sunucusuna gönderilir. Model
  sunucusunun kendisi de yerel model kullanmalı; localhost tek başına bunu kanıtlamaz.
- `--web`: arama sorguları ve hava durumu şehir sorguları dış sağlayıcılara gider.
  Aramaya tüm sohbet hafızası eklenmez; sorunun kendisi kişisel veri içerebilir.
  Ücretsiz sohbet siteleri kazınmaz; DDGS ve Open-Meteo kullanılır. Hizmetlerin
  erişimi/kotası veya ücretsizliği garanti edilmez. Sonuçlar tam doğrulama sayılmaz.
- `--allow-cloud --tts edge`: daha doğal Microsoft Ahmet sesini açar; okunacak
  yanıt Microsoft'a gönderilir. Yerel SAPI sesi bu kalitede olmayabilir.
- Gemini isteğe bağlı korunur: `--allow-cloud --backend gemini` ve
  `GEMINI_API_KEY` gerekir. Bu modda sohbet bağlamı/hafıza da Gemini'ye gönderilir.
- `--test-voice` yalnız sesi dener. `--tts none` sesi kapatır.

Whisper ile uyanır; yanıt sonrası 5 saniye sessizlikte sohbet oturumu kapanır.
Tekrar uyanabilmek için mikrofon/STT çalışmaya devam eder. Düşük güçlü özel wake-word,
yankı kontrolü ve konuşurken söz kesme henüz yok. Android istemci henüz yok.

## Hafızadan çok adımlı görevler

```text
Görevi kaydet: hazırlık = not defteri aç; belgeler aç; sistem bilgisi
Görevi çalıştır: hazırlık
```

İlk komut yalnız kaydeder, ikincisi yürütür. Aynı ad yeniden kaydedilirse güncellenir.
Görevler SQLite içinde saklanır; 1–5 adım içerir. Her çalıştırmada yeniden doğrulanır.
Yalnız uygulama/klasör açma ve sistem bilgisi desteklenir. Model çıktısı kendi
kendine görev oluşturamaz. Bu, öğrenilmiş sınırsız bir ajan değil; kullanıcı
komutlarıyla kaydedilmiş sınırlı rutinlerdir. Her adım sonucu raporlanır; uygulamanın
amacı tamamladığı ekranla henüz doğrulanmaz. Bir adım hatalıysa sonraki adımlar yine denenir.

## Tek adımlı komutlar

Not defteri aç / Hesap makinesi aç / Chrome aç / Edge aç / Belgeler aç /
İndirilenler aç / Masaüstü aç / Sistem bilgisi / Ekranı kilitle /
Not al: ... / Tarayıcıda ara: ...

Ekranı incele / Ekranı incele: bu hata ne? / Tıkla 500 300 /
Aşağı kaydır 3 / Yukarı kaydır 3 / Ekrana yaz: Merhaba Osman /
Sonraki alana geç / Önceki alana geç / Sekmeyi değiştir / Esc tuşuna bas

Ekran analizi yalnız komutla yapılır, görüntü diske/hafızaya kaydedilmez.
Tıklama ana ekranın gerçek piksel koordinatını ister. Analiz görüntüsü 1600 piksele
küçültülür; modelin söylediği koordinatı doğrudan kullanma. Metin odaktaki alana
yapıştırılır; odak doğru olmalı. Enter otomatik basılmaz. Metin panosu geri
yüklenir; resim gibi metin dışı pano biçimleri korunmayabilir.

## Güvenlik sınırları

Bulut varsayılan kapalı; model URL'si yerel adresle sınırlandırılır. Model API'si
HTTP yönlendirmelerini izlemez. Model/web çıktısı shell kodu çalıştıramaz.
Masaüstü işlemleri açık kullanıcı komutları ve `--enable-tools` gerektirir.
Ses sahibini doğrulama yok: ortamdan duyulan komut da tetikleyebilir. Bu nedenle
kritik/para transferi/silme gibi otonom iş akışları bu sürümde eklenmedi.
`--allow-app` verilen uygulamanın güvenilirliğini kullanıcının sağlaması gerekir.

HTTP mobil köprü yalnız loopback'te kullanılabilir. `--allow-network` engellenir;
Android erişimi için TLS/VPN ve ek yetkilendirme katmanı hazırlanmalı.
SQLite hafıza şifreli değildir; işletim sistemi hesabı ve disk erişimi korunmalı.
Paket kişisel veritabanını içermez: mevcut whisper_memory.db dosyanı yerelde yedekle.
Fareyi ekran köşesine götürmek sonraki PyAutoGUI çağrısında fail-safe tetikler.
Tam çıkış Ctrl+C. Bunlar sıfır güvenlik açığı garantisi değildir.

## Doğrulama

Mock testleri: komut ayrıştırma, yerel/bulut sınırları, görev kaydı ve doğrulaması,
HTTP bozuk girdi, hafıza güncelleme, token sınırı, görsel JPEG dönüştürme, pano
metni geri yükleme. Gerçek Windows mikrofon/ses, model, ekran ve ağ ortamıyla
uçtan uca test yapılmadı. Bağımlılık sürümleri bu testten sonra sabitlenmeli.

## Ek başlatma testi

Gerçek Python modülü ve çekirdek sınıfı; ses/model kapalı olarak geçici SQLite
veritabanıyla çalıştırıldı. Selamlaşma, saat, çevrimdışı güncel bilgi reddi, görev
kaydetme/çalıştırma ve gerçek disk sorgusu geçti. PortAudio bulunmadığında yazı
modunun açılmasını engelleyen hata düzeltildi. Model üretimi/ses testi değildir.

### Brave ve Chrome açma düzeltmesi
- “Whisper, Brave uygulamasını aç” sabit Brave kurulum yollarını kullanır.
- Chrome bulunamazsa kurulum dosyasının bulunamadığı açıkça belirtilir.
- “Whisper, tarayıcıyı aç” varsayılan tarayıcıyı açar.
- Ses modeli, seslendirme ve kişisel hafıza değişmez.

### Ses ve yazıyı birlikte test etme
Mevcut klasörde PowerShell: ` .\.venv\Scripts\python.exe .\whisper_ses_v12.py --gui --model qwen3:8b --tts xtts --enable-tools --web `
- Mikrofon otomatik hazırlanır. Durdur/başlat düğmesi vardır; bas-konuş değildir.
- Ses: “Whisper, Brave uygulamasını aç”. Yazı kutusu: “Brave uygulamasını aç”.
- Yazılı komutta tetikleme sözcüğü aranmaz; ses ve yazı aynı beyin/araçlar/hafızayı kullanır.
- Ham tanıma metni ve model skoru ses tanımasını, işlem yolu ve yanıt komut işlemeyi, seslendirme metni telaffuzu incelemek içindir. Komut süresi seslendirmeyi de kapsar.
- Aynı anda gelen iki komut çalıştırılmaz; meşgul uyarısında yeniden gönder. Yazılı yanıt sırasında alınan ses atlanır.
- Mikrofon hatası pencerede görünür; yazı kutusu çalışmaya devam eder.
- `--gui --no-voice` mikrofonu otomatik başlatmadan yazı penceresini açar.
- Pencere kapatılırken mikrofonun kapanması mevcut kayıt/tanıma işleminin bitmesini bekleyebilir.

### İsmi söylenen dosyayı bul ve aç
- “Bütçe raporu dosyasını aç”, “Fizibilite PDF aç”, “Proje notları klasörünü aç”.
- Masaüstü, Belgeler ve İndirilenler ile Windows/OneDrive yönlendirilmiş kullanıcı klasörleri aranır. Dosyalar tek tek kaydedilmez.
- Tam adla tek sonuçta açma isteği gönderilir. Kısmi veya çoklu sonuçlarda ekrandaki konumu kontrol edip “Dosya seç: 1” yaz veya “Whisper, bir numaralı dosyayı aç” de. Seçim 60 saniye geçerlidir; başka komut seçimi iptal eder.
- Ek arama klasörü: başlatma komutuna `--file-root "D:\Projeler"` ekle. Parametre birden fazla kez kullanılabilir.
- Tarama en fazla 8 klasör derinliği, 20.000 girdi ve 3 saniye sınırıyla yapılır; süre/girdi sınırında otomatik açılmaz. Model ve hafızaya dosya içerikleri gönderilmez.
- Belgeler, görseller, medya ve klasörler açılabilir. Çalıştırılabilir dosyalar, komut dosyaları ve kısayollar otomatik açılmaz; uygulama komutları mevcut izinli uygulama modülünü kullanır.
- Windows varsayılan uygulamasına açma isteği gönderilir; pencerenin gerçekten açıldığı doğrulanmaz.

### Performans ve cevap kalitesi güncellemesi
- Ses tanıma cihazı varsayılan `auto`: CUDA görülür ve en az 2500 MB boş GPU belleği varsa GPU denenir; sentetik sessiz kayıtla gerçek çıkarım testi başarısızsa CPU int8 kullanılır. Sentetik test çıktısı hiçbir araca gönderilmez.
- Başlatıcı artık CPU zorlamaz. Eski komutundaki `--whisper-device cpu` parametresini `auto` yap.
- GPU çalışması uygun sürücü, CUDA/cuDNN ve boş bellek gerektirir; bu güncelleme bu paketleri otomatik kurmaz. CPU’ya dönüş hız artışını garanti etmez.
- Türkçe tanıma modeli ve beam=5 korunur. Mikrofon doğruluğu için ` .\.venv\Scripts\python.exe .\whisper_ses_v12.py --test-stt --whisper-device auto `: ekrandaki beş cümleyi oku. Kayıtlar saklanmaz, bilgisayar eylemi çalıştırılmaz. Her cümlede tanıma süresi ve referans metne göre sözcük hata oranı yazılır. Bu değerler genel Türkçe doğruluğu ölçmez.
- `Performans durumu` yazılı/sesli komutu, gerçek STT cihazını ve varsa son Ollama sunucu sürelerini gösterir.
- XTTS kısa yanıtları yalnız oturum belleğinde en fazla 8 MB önbelleğe alır. Aynı metin/ses tekrarlandığında yeniden ses üretmez. İlk üretim ve oynatma süreleri ayrı gösterilir.
- LLM yükleme, girdi işleme ve cevap üretme süreleri yalnız sunucu sağladıysa gösterilir. Konuşma bağlamı 4096 olarak sınırlandı.
- 25 kelimelik sabit yanıt sınırı kaldırıldı. Açıklama, plan ve kod gibi kısa ama karmaşık sorulara 400 token bütçesi verilir; basit sohbet kısa kalır. Bu değişiklik modelin bilgisini veya muhakeme yeteneğini garanti etmez.
- Paket içindeki `tests` dizini donanım bağımsız testleri içerir; gerçek GPU/mikrofon veya XTTS kalitesi ölçümü değildir.

### Türkçe okuma ve akıcı ses
1. Whisper’ı kapat. ` .\.venv\Scripts\python.exe .\whisper_ses_v12.py --calibrate-voice --whisper-device auto ` çalıştır.
2. Her cümlede Enter’a bas, sonra yalnız gösterilen cümleyi normal sesinle oku. Altı kısa Türkçe cümle ekrana gelir. Mikrofon ölçümleri `voice_profile.json`, temiz tanınan seslerden referans `voice_reference_TARIH_SAAT.wav` olarak yerelde saklanır. Hiçbir araç çalışmaz, ses internete gönderilmez.
3. Sonraki sesli açılış aynı mikrofon ve örnekleme hızına mikrofon eşiğini uygular; ortam gürültüsü artmışsa eşik yeniden yükseltilir. Bu işlem kişisel STT eğitimi veya konuşmacı kimliği doğrulaması yapmaz. Tek kayıt tüm tanıma hatalarını çözmez.
4. Kendi sesinde XTTS istersen sonradan konsolun gösterdiği `--speaker-wav` parametresini kullan. Varsayılan sesi bu kayıt otomatik değiştirmez.
5. Uzun “Dinliyorum Osman” ve başlangıç sesleri kaldırıldı; 80 ms işaret sesi kullanılır. “Rik” gibi tek sözcüklü belirsiz ses, LLM’e gönderilmez. Yazılı girdiler bu filtreden etkilenmez.
6. XTTS tekrar/uzatma ayarı ve kısa cümle bütünlüğü düzenlendi; gerçek ses kalitesi dinleyerek doğrulanmalıdır.
7. Daha akıcı Türkçe için çevrimiçi Microsoft sesini seçebilirsin: ` .\.venv\Scripts\python.exe .\whisper_ses_v12.py --gui --model qwen3:8b --tts edge --voice tr-TR-AhmetNeural --allow-cloud --whisper-device auto --enable-tools --web `. Yalnız seslendirilecek yanıt metni Microsoft hizmetine gider; bu komut Google STT veya Gemini’yi etkinleştirmez. İnternet erişimi gerekir; hizmet erişilebilirliği garanti değildir.
8. Tam yerel kullanım için aynı komutta `--tts xtts` kullan ve `--allow-cloud` parametresini çıkar.

## Hafıza ve konuşma gecikmesi düzeltmesi — 4 Ekim

“Benim adım Osman. Bunu hatırla.” ve “Benim adım Osman, bunu hafızana at ve hatırla.” doğrudan SQLite kategorili hafızaya kaydedilir; modelin sözlü kaydetme iddiasına güvenilmez. Açık “bunu hatırla” bilgileri de kaydedilir. İsim soruları kayıt oluşturmaz. Kayıt tekrar açılışta okunur.

Cümle sonu sessizlik varsayılanı 0.6 saniye. `--silence-seconds 0.8` ile uzun duraklamalara dönülebilir. Yerel tanıma süresi, cihaz ve beam logda görünür. `Performans durumu` son tanıma süresini gösterir. Hız karşılaştırmasında `--whisper-beam 3` kullan; doğruluk düşerse 5'e dön. CUDA sorunu varsa uygulama CPU'ya dönebilir; bu yüzden cihaz bilgisine bak. Bu değişiklik tam çift yönlü, konuşurken kesilebilir ses akışı sağlamaz.

```powershell
.\.venv\Scripts\python.exe .\whisper_ses_v12.py --gui --model qwen3:8b --tts edge --voice tr-TR-AhmetNeural --allow-cloud --whisper-device auto --whisper-beam 3 --silence-seconds 0.6 --enable-tools --web
```

Edge seslendirme yanıt metnini çevrimiçi işler. STT yereldir. Yeni paket tüm güncelleme dosyalarıyla çıkarılmalı; .venv, SQLite, modeller ve voice_profile.json silinmez. Yazı kutusundan önce isim kaydı, sonra isim sorgusu; uygulamayı kapat/açıp tekrar sorgula. Ardından aynı komutları sesle ölç. Gerçek mikrofon/Windows/GPU testleri kullanıcı bilgisayarında yapılır.

## Doğal Türkçe hatırlatmalar

Desteklenen örnekler:
- Bir dakika sonra bana hatırlat: ses testi
- On dakika sonra bana hatırlat: toplantı
- Yarın sabah saat onda bana hatırlat: Whisper projesinde çalış
- Yarın akşam sekizde bana hatırlat: İngilizce çalış
- Yarın saat 10:30’da bana hatırlat: toplantı

Sabah/akşam belirtilmeyen 1–12 saatleri belirsiz sayılır; konu ve net zamanla yeniden söyleyin. Geçmiş zaman ve eksik konu kaydedilmez. Görevlerim ve Görev tamamla: 1 komutları kullanılabilir. Sayıyla süreler 1–365, sözcükle temel sayılar ve on/yirmi birleşimleri desteklenir; her Türkçe tarih ifadesi henüz desteklenmez. Saat dilimi Türkiye UTC+3. Kayıt yerel SQLite'ta tutulur; bildirim uygulama açıkken veya sonraki açılışta gecikmiş olarak gelir. Tekrarlı hatırlatma ve kapalı uygulamada Windows bildirimi henüz yok.

## Planlama katmanı

Şablon temelli yerel plan taslağı; otomatik araştırma, repo tarama, kod düzenleme veya dosya üretimi yapmaz. Mevcut modül bildirilerine göre eksik/koşullu adımları gösterir; bunlar bilgisayardaki gerçek kurulum taraması değildir. Planlar SQLite'a ayrı plans/plan_steps tablolarıyla kaydedilir, önceki hafıza ve görevler korunur.

Komutlar:
- Whisper projesinin eksiklerini analiz et ve geliştirme planı oluştur
- Plan oluştur: Elektrikli araç şarj istasyonu fizibilitesi
- Planlarım
- Plan durumu: 1
- Plan adımı tamamla: 1 2

Son komut Plan 1'in Adım 2'sini kullanıcı bildirimine göre işaretler; bağımsız iş sonucu doğrulanmış sayılmaz. Plan içeriğinde komut bulunması araç çalıştırma yetkisi vermez. Araçlar adımlarla ilişkilendirilir ama çağrılmaz. PDF/Word/PowerPoint üretimi hâlâ eksiktir. Uzun görev listeleri ekranda gösterilir ve sayısı seslendirilir; hatırlatma kayıt yanıtı da kısa seslendirilir.

## Plan adımını gerçek sonuçla çalıştırma

`Plan adımını çalıştır: 1 1` Plan 1'in ilk adımını çalıştırır. Şu anda yalnız self_analysis için çalıştırıcı bağlıdır; diğer araçlar işlem yapmadan blocked döner. Hata analizi sonucu, zaman damgası ve KAYNAK_SISTEM etiketi plan_steps.evidence alanında saklanır. `Plan adımı sonucu: 1 1` kayıtlı sonucu gösterir. `Plan durumu: 1` kullanıcı bildirimini ve gerçek araç çalışmasını ayrı gösterir. Analizin çalışması hataların giderildiği veya cevapların doğru olduğunun kanıtı değildir. Başarısız analiz adımı tamamlamaz. Tamamlanan analiz yeniden çağrılırsa kayıtlı sonucu gösterir, tekrar çalıştırmaz.

GUI'de katman cevabının ve yazılı yanıtın tekrarları azaltıldı. Direkt hata analizinin sesli yanıtı da kısaltıldı. Ayrıntılar ekranda, tanılama bilgileri korunur; bu değişiklik LLM/STT hızını değiştirmez.

## PDF kaynak hafızası ve ilk kaynak raporu

Bir kez sanal ortamda `python -m pip install "pypdf>=5,<7"` kurun; ses/model bağımlılıklarını yeniden kurmayın. GUI'deki **PDF seç** düğmesi yalnız seçtiğiniz dosyayı aktarır. Alternatif: `PDF öğren: C:\Users\...\Belge.pdf`.

- Belgelerim: kayıtlı PDF'ler
- PDFde ara: karar değişimi
- PDF sor: karar değişimi (ilk sürümde aynı kaynak araması; LLM cevabı değildir)
- PDF kaynak raporu: karar değişimi
- Belgeyi unut: 1

Metin yerel SQLite FTS5'ta sayfa ve parçalar halinde saklanır. Arama sözcük eşleşmesidir; eşanlamlı ve anlamsal arama henüz yoktur. PDF adı, gerçek sayfa sırası (1'den başlar) ve bulunan alıntı gösterilir. PDF'nin içeride basılı sayfa etiketi farklı olabilir. Eşleşme bulunmaması konunun kesinlikle belgede olmadığı anlamına gelmez. PDF içeriği modele/buluta gönderilmez; asistan modeli eğitilmez. Yanıt metninin kısa seslendirmesi Edge seçilmişse Microsoft'a gider; aranan konu ve alıntılar bu modülün seslendirmesine dahil edilmez.

En fazla 32 MB/1000 sayfa/5 milyon çıkarılmış karakter. Okuma ayrı işlemde 45 saniye sınırıyla yapılır; bu süreyi aşan dosya kaydedilmez. Şifreli PDF ve OCR desteklenmez. Metinsiz sayfa sayısı açıkça bildirilir; kısmen taranmış PDF'nin yalnız metinli sayfaları aranabilir. PDF eylemleri, JavaScript ve gömülü dosyalar çalıştırılmaz; bu, tüm PDF'ler için güvenlik garantisi değildir. Aynı dosya içeriği tekrar eklenmez. Kayıt silinince indeks kaldırılır, özgün PDF korunur. Unutma işlemi daha önce dışa aktarılmış raporları veya geçmiş kaynak kayıtlarını silmez.

Kaynak raporu yalnız eşleşen alıntıları Markdown `.md` olarak hafıza veritabanı klasörü altındaki `raporlar` klasörüne yazar. Word/PDF/PowerPoint üretimi veya kapsamlı araştırma/özet henüz yok. Sorgu başlığı ve PDF içeriği Markdown'da kaynak verisidir, çalıştırma talimatı değildir. Paket belge metni, kişisel veritabanı veya modeller içermez.

## Yanıt tutarlılığı ve performans kontrolü

Model çıktısı araç çalıştırmaz. Modelin birinci tekil şahıs “açıyorum/açtım/çalıştırıyorum/çalıştırdım/kaydettim” gibi belirli eylem iddiaları seslendirmeden önce engellenir; bu sözcük kontrolü her yanlış iddiayı veya paraphrase'i yakalayamaz. Araç etiketi üreten model cevabı success sayılmaz, blocked olarak kaydedilir. Doğrudan araç/hafıza işlemleri kendi sonuçlarını okumaya devam eder. Eski model talimatındaki araç etiketi üretme önerisi kaldırıldı.

Python/pip/Whisper başlatma komutları PowerShell'de çalıştırılır; Whisper yazı kutusu kurulum kabuğu değildir. Yanlış kutuya girilen tanınan komut modele gönderilmez.

Tanıma cihazı cpu görünüyorsa daha önce CUDA'da ölçülen sürelerle karşılaştırılmamalı. Whisper açıkken ikinci bir PowerShell'de `ollama ps` ve `nvidia-smi` çıktısını alın; açık model ve GPU bellek kullanımını gösterir. Bunlar salt okunur ölçümlerdir, ayar değiştirmez. CPU seçiminin nedeni başlangıç loglarında veya GPU bellek durumunda araştırılmalı; zorla CUDA seçmek bellek hatası doğurabilir. Uzun LLM load_duration model yükleme süresidir; tekrar isteklerde ölçülmelidir.


## Türkçe algılama güncellemesi — 5 Ekim 2026

- 60 ms ardışık ses ile kayıt başlar; tek darbe konuşma başlatmaz.
- Konuşma sonu eşiği başlangıç eşiğinin %55'i: kısık heceler kaydı erken bitirmez.
- VAD kenar payı 400 ms, sessizlik birleştirme 500 ms.
- Türkçe bilgisayar/bellek/RAM/GPU/uygulama terimleri bağlam ipuçlarına eklendi. İpuçları doğruluk garantisi veya model eğitimi değildir. Ham metin otomatik RAM/REM değiştirilmez.
- Adaptör bağlıyken kontrollü GPU denemesi: `--whisper-device cuda --whisper-beam 5 --silence-seconds 0.8`. CUDA başlangıç testi başarısızsa mevcut CPU yedeği kullanılır. GPU ve Qwen'in toplam VRAM kullanımını izleyin.
- Bu güncelleme model indirmez, ses profilini veya hafızayı silmez. Mevcut V12 klasörüne ZIP içeriğini çıkarıp aynı adlı kod dosyalarını değiştirin.
- Başlatma (klasörde PowerShell):

```powershell
.\.venv\Scripts\python.exe .\whisper_ses_v12.py --gui --model qwen3:8b --tts edge --voice tr-TR-AhmetNeural --allow-cloud --whisper-device cuda --whisper-beam 5 --silence-seconds 0.8 --enable-tools --web
```

71 yerel test geçti; gerçek Windows mikrofon doğruluğu burada ölçülmedi. Uygulamada `Whisper, bilgisayar belleği ne işe yarar?` ve `Whisper, hesap makinesini aç.` cümlelerini karşılaştırın. GUI yazı alanı STT'yi atlayarak aynı komutun kod yolunu test eder.


## PDF Windows kodlama düzeltmesi — 5 Ekim 2026

PDF alt işlemi UTF-8 modunda başlatılır; giriş JSON'u UTF-8 byte olarak okunur, çıkış ASCII kaçışlı JSON byte olarak yazılır. Böylece Windows cp1254/cp1252 konsol kodlaması Türkçe veya başka dillerdeki PDF metnini bozmaz. Eksik okuyucu modülü ve çıktısız işlem ayrı hata olarak bildirilir. 74 yerel test geçti; cp1254 ortam değişkeni ile Türkçe, Yunanca, Çince ve emoji aktarımı test edildi. Kullanıcının hatalı PDF'si burada mevcut değil; aynı dosya Windows'ta yeniden seçilerek doğrulanmalı.

Güncellemedeki `whisper` klasörünü de mevcut `whisper astra` içine kopyalayın ve aynı adlı kod dosyalarını değiştirin. `pypdf` kuruluysa yeniden kurulum gerekmez. Hafıza veritabanını silmeyin.


## PDF numaralı arama düzeltmesi — 5 Ekim 2026

`PDF'de ara: MADDE 87` artık 87 sayısını atmaz; madde ve sayı aynı ifade olarak aranır. 870 gibi farklı sayılar eşleşmez. Başlık biçimindeki eşleşmeler ilk 100 aday arasında içindekiler/atıfların önüne alınır. Genel aramada anlamlı tüm sözcükler birlikte aranır; kısa sayılar korunur ve sayı önek araması yapılmaz. Daha sıkı eşleşme nedeniyle sonuç yoksa daha kısa anahtar sözcük kullanın. Mevcut PDF veritabanı uyumludur; belgeyi yeniden yüklemeyin. 77 yerel test geçti. Bu sürüm kaynaklı alıntı aramasıdır; LLM ile kaynaklı cevap üretimi henüz eklenmedi.


## 5 Ekim 2026 — mikrofon işlenirken SciPy engeli

`_linalg_pythran.cp312-win_amd64.pyd` Uygulama Denetimi tarafından engellendiğinde model yüklenebilse de mikrofon kaydı işlenemiyordu. Mikrofonun 44.1/48 kHz kaydını 16 kHz'e dönüştüren yol artık NumPy ile pencere uygulanmış sinc filtresi kullanır; bu adım SciPy yüklemez. Windows güvenliğini kapatmak veya tüm ortamı yeniden kurmak gerekmez. Diğer isteğe bağlı ses özellikleri hâlâ SciPy kullanabilir.

Whisper'ı kapatın. WHISPER_V12_GUNCELLEME.zip içeriğini mevcut proje klasörüne çıkarıp aynı adlı kod dosyalarını değiştirin. .venv, hafıza veritabanı ve ses profillerini silmeyin. Adaptör bağlıyken PowerShell'de başlatın:

```powershell
.\.venv\Scripts\python.exe .\whisper_ses_v12.py --gui --model qwen3:8b --tts edge --voice tr-TR-AhmetNeural --allow-cloud --whisper-device cuda --whisper-beam 5 --silence-seconds 0.8 --enable-tools --web
```

Sesli test: “Whisper, saat kaç?” ardından “Hesap makinesini aç.” Başka bir bileşen engellenirse hata metnini paylaşın. Yerel doğrulama: 80 test geçti; bu doğrulama gerçek Windows mikrofon/GPU testi değildir.


## 5 Ekim 2026 — yerel PDF cevapları

`PDF sor:` artık ilgili alıntıları yerel modele gönderir. Yalnız localhost/127.0.0.1/::1 model adresleri kabul edilir; Gemini veya uzak API'ye PDF metni gönderilmez. Model ayrı bir istekle çalışır; kişisel hafıza ve sohbet geçmişi eklenmez. PDF içindeki talimatlar veri olarak işaretlenir, bu yoldan araç çalıştırılmaz.

Örnekler:
- `PDF'de ara: MADDE 87` — alıntı listesi, model çağrısı yok.
- `PDF sor: belge 1; sayfa 67; MADDE 87 ne anlatıyor?` — belirtilen belge ve sayfadan yerel model cevabı.
- `Bu bilgiyi nereden öğrendin` — önceki cevabın dosya/sayfa kaynakları.

Belge ve sayfa kapsamı isteğe bağlıdır, soru başında noktalı virgülle ayrılır. Arama hâlâ sözcük temellidir; semantik arama ve OCR eklenmedi. Kaynak bulunamazsa model çağrılmaz. Model çıktısı JSON olarak denetlenir: her kaynak kimliği bulunmalı ve her alıntı ilgili PDF metninde birebir yer almalıdır. Uydurulmuş kaynak/alıntı, bozuk JSON, yetersiz bağlam veya bağlantı hatasında cevap yerine açıklama gösterilir. Alıntı doğrulaması model yorumunun doğruluğunu kanıtlamaz; bunun bilgisi ekranda ve kaynak kaydında tutulur. Hukuki metinlerin güncelliği bu özellik tarafından doğrulanmaz.

Güncellemeyi uygularken `whisper` klasörünü de mevcut proje klasörüne çıkarın. PDF'yi tekrar yüklemeyin; veritabanı korunur. Modelin gerçek Windows cevabını yukarıdaki sayfa 67 komutuyla kontrol edin. Yerel kod doğrulaması: 88 test geçti, gerçek model/mikrofon testi kullanıcı bilgisayarında yapılır.


## 5 Ekim 2026 — kaynaklı cevap raporu

Kullanıcı bilgisayarında PDF sor komutu yerel Qwen ile cevap ve sayfa 67 alıntısı üretti; kaynak sorusu aynı dosya/sayfayı gösterdi. Bu gözlem modelin tüm yorumlarını bağımsız olarak doğrulamaz.

Yeni komut: `PDF cevap raporu: belge 1; sayfa 67; MADDE 87 ne anlatıyor?`

Önce mevcut kaynak denetimiyle cevap üretilir. Yalnız başarılı cevap, hafıza veritabanının yanındaki `raporlar` klasörüne benzersiz `pdf_cevap_raporu_....md` adıyla UTF-8 metin dosyası olarak kaydedilir. Soru, oluşturulma zamanı, model, cevap, kaynak alıntıları ve sayfa numaraları dosyaya eklenir. Bu aşama Markdown raporudur; Word, PDF ve PowerPoint dışa aktarma henüz yoktur. Başarısız/yetersiz kaynaklı cevap dosyaya kaydedilmez. Dosya yazılamazsa açık hata verilir; var olan dosyalar üzerine yazılmaz.

Kaynak sorusunun sesli cevabı kısaltıldı: uzun PDF dosya adları ve sayfa listesi ekranda kalır. Modelin kaynaklı cevabının tamamı normal PDF sor komutunda seslendirilir. Yeni paket mevcut veritabanı, PDF kayıtları, ses profili ve .venv korunarak aynı proje klasörüne çıkarılır; whisper klasörü de birleştirilmelidir. Yerel doğrulama: 91 kod testi geçti.


## 5 Ekim 2026 — Word ve PDF dışa aktarma

Kayıtlı Markdown raporu, yeniden model çağrısı yapılmadan Word veya PDF'ye dönüştürülür. Dosya yalnız veritabanının yanındaki raporlar klasöründen okunur. Kaynak metin ve sayfa numaraları korunur; özgün Markdown değişmez. Çıktılar aynı klasöre benzersiz adla kaydedilir, var olan dosyalar üzerine yazılmaz. HTML benzeri içerik düz metindir, dış bağlantı/komut çalıştırılmaz.

Güncelleme paketinin whisper klasörünü de proje klasörüne çıkarın. Yeni iki paketi yalnız PowerShell'de kurun:

```powershell
.\.venv\Scripts\python.exe -m pip install python-docx reportlab
```

Whisper yazı kutusunda (dosya adını kendi raporunuzdan alın):

```text
Raporu Word yap: pdf_cevap_raporu_d3ccdeb3b7a6.md
Raporu PDF yap: pdf_cevap_raporu_d3ccdeb3b7a6.md
```

Bu komutlara tam yol değil yalnız dosya adı verilir. Çıktı yolu ekranda gösterilir. Word kurulu olmadan .docx oluşturulabilir; açmak için uyumlu belge okuyucu gerekir. PDF, Windows Fonts klasöründeki Arial yazı tipini gömer; bulunamazsa Türkçe bozuk çıktı üretmek yerine açık hata verir. Linux geliştirme testlerinde DejaVu kullanılır.

Yerel doğrulama: 95 test geçti; DOCX ve PDF metinlerinde Türkçe karakterler/kaynaklar kontrol edildi, örnek sayfalar görsel olarak incelendi. Windows çıktısı kullanıcı bilgisayarında ayrıca doğrulanmalıdır. Bu özellik kayıtlı raporun biçimini değiştirir; yeni araştırma/bağımsız doğrulama yapmaz.


## 5 Ekim 2026 — PowerPoint ve son rapor seçimi

`Raporlarım` kayıtlı Markdown raporlarının son 20 dosya adını listeler. `son rapor`, raporlar klasöründeki en son değiştirilmiş geçerli Markdown raporudur. Word/PDF/PPTX çıktıları bu seçime dahil edilmez.

Whisper yazı kutusunda:

```text
Raporu sunum yap: son rapor
Raporu Word yap: son rapor
Raporu PDF yap: son rapor
```

PowerPoint çıktısı düzenlenebilir metin kutuları içerir: kapak sorusu, rapor içeriği ve kaynaklar. Uzun metinler kesilmeden sonraki slayta aktarılır. En fazla 30 slayt desteklenir. Tasarım sade metin sunumudur; görsel üretimi, grafikler, yeni araştırma ve yeni LLM özeti yoktur. Modelin önceki doğrulanmamış yorumuna ilişkin açıklama sunumda kalır.

Sunum dışa aktarma Python standart kütüphanesi ile Open XML yazar. Yeni paket kurmak gerekmez. Dağıtılan boş PowerPoint şablonu ve lisansı whisper/tools/assets içinde bulunur; bu klasör de güncellemede birleştirilmelidir. Özgün Markdown ve önceki Word/PDF çıktıları korunur.

98 kod testi geçti. PPTX paket bütünlüğü kontrolü geçti, örnek 3 slayt LibreOffice ile açılıp render edildi ve her slayt görsel olarak incelendi. Gerçek Windows PowerPoint testi henüz yapılmadı.

## 5 Ekim 2026 — PDF alıntı doğrulaması ve sayfalı ham arama

PowerPoint çıktısının kullanıcı bilgisayarında açıldığı doğrulandı. Sayfa 202 sorusunda model alıntısı doğrulanamadı; ham PDF araması aynı sayfada metin buldu. Modelin özgün JSON çıktısı bulunmadığından reddin kesin nedeni henüz bilinmiyor.

Alıntı uzunluğu, bilinmeyen kaynak kimliği ve metin uyuşmazlığı artık farklı mesajlar verir. Kaynağa birebir uyan 401–1200 karakterlik alıntılar gereksiz yere reddedilmez; modelden yine 15–400 karakter istenir. En fazla modele verilen 1200 karakterlik kaynak içinde, yalnız boşlukları normalize ederek birebir eşleşme aranır. Yorumun doğruluğu bağımsız doğrulanmış sayılmaz.

Reddedilen kaynak alıntılarında model cevabı sunulmaz; aynı istekte getirilen ham PDF alıntıları ekranda gösterilir, sesli olarak uzun alıntılar okunmaz. Ek model çağrısı yapılmaz.

Ham aramada da sayfa/belge kapsamı desteklenir. Komutları tek tek gönderin:

```text
PDF'de ara: belge 1; sayfa 202; MADDE 87
PDF sor: belge 1; sayfa 202; MADDE 87 ne anlatıyor?
```

Bu güncelleme için yeniden paket veya model kurulumu gerekmez. Whisper kapalıyken güncel whisper klasörünü mevcut proje klasörüne birleştirin; hafıza ve rapor dosyalarını silmeyin. Adaptör takılıyken PowerShell'de:

```powershell
cd "$env:USERPROFILE\Desktop\whisper astra"
.\.venv\Scripts\python.exe .\whisper_ses_v12.py --gui --model qwen3:8b --tts edge --voice tr-TR-AhmetNeural --allow-cloud --whisper-device cuda --whisper-beam 5 --silence-seconds 0.8 --enable-tools --web
```

## 5 Ekim 2026 — PDF kaynak alıntısını kimlikle seçme

Kullanıcı bilgisayarında uygulama açıldı ve yeni hata tanısı çalıştı: 202. sayfa sorusunda gerçek metin uyuşmazlığı görüldü; yalnız uzunluk sınırı değildi. Modelin özgün JSON cevabı elimizde olmadığı için hangi sözcüğü değiştirdiği bilinmiyor.

Yeni istemde model serbest kaynak alıntısı yazmaz. Her 1200 karakterlik kaynak kesiti, kod tarafından en fazla 400 karakterlik özgün metin parçalarına ayrılır; model yalnız S1/Q1 gibi kaynak ve parça kimliklerini seçer. Gösterilen alıntı doğrudan kayıtlı PDF metninden alınır. Bilinmeyen kimlik veya kimlikle birlikte serbest alıntı reddedilir. Eski JSON biçimi gelirse önceki birebir doğrulama korunur. Ek model çağrısı yapılmaz. Bu yöntem kaynak alıntısının kökenini korur; model özetinin tüm iddialarının doğru olduğunu bağımsız olarak kanıtlamaz.

104 test geçti. Gerçek yerel model ve Windows testi kullanıcı bilgisayarında yapılmalıdır. Başlatma için yukarıdaki normal komutu kullanın; 30 saniyelik tanılama komutu sürekli kullanım için gerekli değildir.

## 5 Ekim 2026 — Türkçe ses seviyesi komutları

Ses tanıma, kullanıcının “Ses seviyesine elliye getir” ve “Bilgisayarın sesini elliye getir” sözlerini metne çevirdi; eski araç ayrıştırıcısı bunları sohbete gönderdi. Yeni dar dilbilgisi bu ifadeleri doğrudan ses_ayarla aracına yönlendirir. Sıfır–yüz Türkçe sayılar, onlar/birler birleşimleri, sayılardaki yönelme ekleri ve yüzde/50 biçimleri desteklenir. YouTube gibi uygulamalara özel komutlar sistem sesine dönüştürülmez; olumsuz komutlar ve belirsiz “yarıya getir” ifadeleri tahmin edilmez.

“Sesi kıs”, “Sesini azalt” göreli Windows ses azaltma komutuna eklendi. Kesin yüzde ayarında güncel pycaw EndpointVolume erişimi ve eski Activate erişimi desteklenir; GUI iş parçacığında COM başlatma/kapatma dengelenir. Aralık dışı değerler 100'e yükseltilmez; reddedilir.

Resmî pycaw örneği: https://github.com/AndreMiras/pycaw
109 test geçti. Windows uç noktası çağrısı sahte nesneyle kontrol edildi; gerçek Windows ses seviyesi kullanıcının bilgisayarında doğrulanmalıdır.

Güncellemeyi Whisper kapalıyken mevcut klasöre çıkarın. Yüzde ayarı için iki küçük paketi PowerShell'de kurun:

```powershell
.\.venv\Scripts\python.exe -m pip install pycaw comtypes
```

Sonra normal başlatma komutuyla açın ve önce yazılı, ardından sesli deneyin:

```text
Bilgisayarın sesini elliye getir
```
