# V33.1 — Araştırma, çekirdek kod ve yazılı sohbet

Çalışma dalı: `codex/dialogue-context-v33`. Kullanıcının isteğiyle ses çalışması askıdadır. Ayrı saklanan ses gecikmesi denemeleri bu pakete dahil edilmedi.

## Kullanım

- `WHISPER_BASLAT.cmd`: mevcut arayüzde yazılı sohbet. Paket bütünlüğü doğrulanır; mikrofon, STT, Chatterbox/TTS modeli veya ses kurulumu başlatılmaz. Önceki ses dosyaları silinmez. Olağan arka plan araştırma ve geliştirme servisleri mevcut ayarlarıyla çalışır; ön plandaki yazılı istekler mevcut kilit/iptal akışından geçer.
- `WHISPER_GELISIM_BASLAT.cmd`: mevcut tek-model araştırma/kod geliştirme oturumu. Normal Whisper penceresini kapatıp Docker Desktop Linux konteynerleri ve Ollama açıkken çalıştırın. Ayrıntılı durum `WHISPER_GELISIM_RAPORU.json` içinde tutulur. Aynı anda iki geliştirme oturumu açılmaz.
- Salt kontrol: `.venv\Scripts\python.exe whisper_bootstrap.py --text --check-only`. Dosya/modül kontrolü yapar; model indirmez, uygulama veya kurulum başlatmaz.

Yazılı arayüz tek başına yeni mantıksal yetenek garantisi değildir. V33'ün yapılandırılmış oturum geçmişi, düzeltmeler ve sınırlı bağlam penceresi kullanılmaya devam eder.

## Doğrulanan kuyruk sorunları ve düzeltmeler

Gelişim profilinde bilgi işleme, ilk 500 uygun bölüm getirildikten sonra konu sıralaması yapıyordu. Öncelikli bir konu 501 eski bölümün arkasındaysa seçilmiyordu. Konu sınıflandırması artık tüm uygun kayıtlar üzerinde SQL sıralamasında uygulanır; ardından tek bölüm alınır. Özel Türkçe konu adları da aynı `track` sınıflandırıcısından geçer. Açıkça verilen kaynak listesi, bekleme zamanları, iptal ve kaynak-alıntı doğrulaması korunur.

Taslak üretimi sürekli en yeni 200 tamamlanmış karta bakıyordu. Bunlar zaten sıraya alınmış veya ilgisiz olduğunda daha eski, ilgili kartlar hiç keşfedilmiyordu. Keşif artık yalnız henüz geliştirme kaydı olmayan ilgili kartları seçer; her geçişte en fazla 200 yeni kayıt ekler. Mevcut taslaklar tekrar üretilmez. Bu değişiklik canlı kod uygulama izinlerini veya test sınırlarını genişletmez.

## Araştırma gündemi

Siber güvenlik/güvenli kodlama, bağımlılık ve günlük analizi; Türkçe diyalog ve bağlam; kaynaklı hafıza; araç planlama ve regresyon testleri; derin öğrenme gündemi korunur.

Gelişim müfredatına ayrıca mantıksal akıl yürütme, öncül-sonuç ilişkisi, çelişki ve tutarlılık değerlendirmesi eklendi. İlk kaynak `https://arxiv.org/abs/2203.11171` makale sayfasıdır. Gelişim profilindeki 10 turdan 8'i odak konularına, 2'si genel keşfe ayrılır; mantıksal tutarlılığın ayrı odak sırası vardır. Kaynak bulunmaması, bekleme süreleri, profil ve okuma limitleri gerçek çalışmayı etkiler. Yazılı sohbette `Araştırma profili: geliştirme` komutuyla gelişim müfredatını seçebilirsiniz. Varsayılan ayrı geliştirme oturumu `security` profilini korur; yeni mantık sırası `development` profiline aittir.

Araştırma kartları uygulama fikri ve kabul testi taslağına dayanak sağlar. Kaynak özeti, doğruluğu bağımsız doğrulanmış bilgi veya model eğitimi değildir. Gerçek mantıksal başarıyı ölçmek için bir sonraki değerlendirmede önceden belirlenmiş beklenen sonuçlar, kullanıcı düzeltmeleri ve çelişki örnekleriyle gerçek yerel model ölçümü gerekir. Henüz böyle bir başarı oranı raporlanmadı.

## Boyut ve sıkıştırma

Güncelleme kayıpsız sıkıştırılmış kaynak ZIP'i olarak sunulur. Kişisel veritabanları, ses kayıtları, API anahtarları, sanal ortamlar ve model ağırlıkları kaynak paketinin dışındadır. Çalışan veritabanı biçimi ve kaynak metinler bu güncellemede değiştirilmez; eski kayıtlardan veri silinmez. Model ağırlığı küçültme/kuantizasyonu bu paket sıkıştırmasından ayrıdır ve burada uygulanmadı.

## Test kanıtı

`python -m unittest discover -s tests`: **535 test geçti; atlanan yok** (Linux/Python 3.12).

Yeni kuyruk testlerinde 501 eski bölümün arkasındaki Türkçe odak kaynağı seçildi; 201 yeni kartın arkasındaki eski ilgili kart taslağa dönüştü. Yeni kartların zaten taslak olduğu ve genel konulardan oluştuğu iki ayrı durum denetlendi. Kaynak filtresi, gelecekteki bekleme zamanı, iptal, tekrar üretmeme ve mantık konusunun gerçek araştırma sırası doğrulandı. İlk kuyruk testleri düzeltmeden önce üç başarısızlık gösterdi.

Yazılı başlatıcı testleri ses kurulumu çağrılmadığını, TTS kapalı ve mikrofon döngüsünün devre dışı olduğunu, salt kontrolün ses bağımlılıklarını gerektirmediğini doğrular. Mevcut V33 diyalog ve güvenlik testleri korunur. Testlerde ağ okuması ve model yanıtları taklittir; Windows, gerçek model kalitesi, GPU ve V33.1 Docker çalıştırması sınanmadı.
