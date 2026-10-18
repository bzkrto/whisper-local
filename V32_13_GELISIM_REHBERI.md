# V32.13 — tek modelle siber güvenlik ve kod geliştirme

## Başlatma

1. Normal Whisper/GUI penceresini kapatın. Geliştirme oturumunu sesli oturumla aynı anda çalıştırmayın.
2. Docker Desktop'ı Linux konteynerleriyle açın. Kurulu değilse resmi kurulum: https://www.docker.com/products/docker-desktop/ . Windows sanallaştırma/WSL gereksinimleri bilgisayarda tamamlanmalıdır; bu buluttan bilgisayarınıza Docker kurulmadı.
3. Ollama açık olsun. Mevcut qwen2.5-coder:7b, yoksa qwen3:8b kullanılır. Yeni LLM veya ses modeli indirilmez.
4. WHISPER_GELISIM_BASLAT.cmd dosyasını açın. Eski/eksik test imajı otomatik yenilenir; bu ilk işlem Python test paketleri ve yazı tipleri için internet gerektirir.
5. Pencere açık kaldığı sürece geliştirme sürer. Ctrl+C durdurur. Normal sesli kullanım için geliştirmeyi kapatıp WHISPER_BASLAT.cmd açın.

Test ortamını indirme/işlem yapmadan kontrol etmek için:
`.venv\Scripts\python.exe whisper_bootstrap.py --development --check-only`

## Çalışan döngü

Sıradaki kod işi önce ele alınır. Sonra zamanı gelen araştırma, bir belge bölümünü bilgi kartına dönüştürme ve kaynaklı geliştirme önerisi aşamaları yürür. İşlemler tek modelde sırayladır; ses, STT, GUI veya ek model işçileri başlatılmaz.

- Araştırma kontrolü en fazla dakikada bir yapılır. Hazır bilgi işleme işleri arasında bir dakikalık boş bekleme yoktur.
- Gelişim analizi ve kod işleri arasındaki eski 600 saniyelik bekleme bu oturumda 60 saniyeye iner; modelin üretim/test süresi buna eklenir. Hatalı işler için tekrar sınırları korunur.
- Siber güvenlik kaynakları, eski genel belgelerin önüne alınır. Kaynakta kanıtlı güvenli kodlama, giriş doğrulama, günlük analizi ve bağımlılık güvenliği kartları geliştirme önerisine dönüşebilir.
- Genel belge kuyruğu doluyken güvenlik kaynaklarının ilk toplanması engellenmez; 12 güvenlik bölümü birikince önce bunlar işlenir. Kaynak toplama sınırsız biçimde belleği doldurmaz.
- Kod işi ilgili kaynak kartını ve hedefe en uygun küçük modülleri alır. Uygulanabilir değişiklik yoksa `no_change` kaydı tutulur; aynı hedef için sonsuz model çağrısı yapılmaz.
- Taslak ayrı klasörde hazırlanır. Güvenilir mevcut testler Docker'da geçmeden canlı kod değiştirilmez. En fazla iki izin verilen Python modülü güncellenir; yedek ve SHA256 kayıtları korunur.
- Güncellemeden sonra başlatıcı bütünlük kontrolünü yapar, yeni Python süreci açar ve kaldığı kuyruktan devam eder. Yeni kod eski importlarla yeniden değiştirilmez.

Yeni görev eklemek için normal Whisper oturumunda `Kendini geliştir: ...` komutu kullanılabilir. Ardından normal oturumu kapatıp geliştirme modunu açın. Kaynak kartlarından çıkan işler de kalıcı kuyruğa otomatik girer. Her kaynak mutlaka kod değişikliği doğurmaz.

## Bellek ve işlem kullanımı

Geliştirme modunda Chatterbox ve Whisper STT ağırlıkları yüklenmez. Tek kurulu model kullanılır; sohbet/kod modeli geçişiyle iki büyük modelin yerleşimi önlenir. Ollama otomatik GPU yerleşimini yönetir; donanımda ne kadarının GPU'ya sığdığı burada ölçülmedi.

Ollama'ya 128 token işlem grubu, en fazla 4 CPU iş parçacığı ve 6144 token bağlam istenir. Kod için ayrılan kaynak metni bağlam boyutuna göre sınırlandırılır. Son istekten sonra 30 saniye boşta kalan modelin bırakılması istenir. Aktif kuyrukta modelin bellekte kalması normaldir. Docker testleri 2 CPU ve 2 GB RAM ile sınırlıdır; ağları kapalıdır.

Bunlar model ağırlıklarını yeniden sıkıştırma, eğitim veya GPU kullanım yüzdesini sınırlama işlemi değildir. Gerçek toplam RAM/VRAM kazancı Windows bilgisayarda ölçülmelidir. Daha küçük işlem grubu/iş parçacığı sayısı bazı işleri yavaşlatabilir.

## Gerçek ilerleme

`WHISPER_GELISIM_RAPORU.json` son aşamayı, oturumda işlenen bölüm/taslak sayılarını, geçmiş uygulanmış iş sayısını, son model sürelerini ve son sonucu tutar. `application_rss_mb` yalnız Whisper istemcisinin RAM ölçümüdür; ayrı Ollama sunucusunu veya VRAM'i kapsamaz. `no_change`, bekleyen, hata ve uygulanmış işler birbirinden ayrılır.

Kaynakları okumak ve bilgi kartı çıkarmak model ağırlıklarını eğitmez. Regresyon testlerinin geçmesi de yeni özelliğin her koşulda doğru olduğunun kanıtı değildir. Hedefe özgü kabul ölçütleri ve değerlendirmeler gereklidir.

## Yol haritasındaki mimarinin karşılığı

Beyin, araçlar, kod düzenleme ve öz düzeltme ayrımı uygundur. Modelin ürettiği `shell=True` komutlarını ana bilgisayarda çalıştırmak veya canlı dosyayı önce `.bak` adına taşıyıp üzerine yazmak bu uygulamada kullanılmaz. Sabit test komutu, ayrı taslak, atomik dosya değişimi, sınırlı tekrar ve yeniden başlatma vardır. Git ayrıca eklenebilir; veritabanı ve ayar yedeklerinin yerini tutmaz. Mevcut masaüstü klasörü için Git kurulduğu iddia edilmez.

## Doğrulama

510 test normal bulut Python ortamında ve gerçek Docker konteynerinde geçti. Docker çalışması ağsız, salt okunur, ayrı kullanıcıyla, 2 CPU/2 GB RAM altında tamamlandı; atlanan test yoktu. Önceki imajda eksik Türkçe yazı tipi yüzünden başarısız olan 15 kontrol düzeltildi; isteğe bağlı ses testlerinin bağımlılığı da imaja eklendi.

Ayrı küçük deneme projesinde gerçek yerel Qwen2.5-Coder 1.5B modeli bir sayı/zaman aşımı doğrulama fonksiyonunu yazdı. Beş girdiyi kontrol eden bir test gerçek Docker'da geçti; kod, sürüm bildirimi ve yedek doğrulandı, deneme veritabanı korundu. Akış CPU'da 39,17 saniye sürdü. Bu küçük deneme, kullanıcının 7B modelinin tüm görevleri başaracağını veya aynı sürede çalışacağını göstermez. Gerçek masaüstü donanımı ve uygulama kuyruğu bu buluttan çalıştırılmadı.
