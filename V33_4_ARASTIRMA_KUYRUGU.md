# V33.4 — Araştırma denetimi ve kuyruk kurtarma

Dal: `codex/dialogue-context-v33`; ses çalışması askıda, ana dala birleştirme yok.

## Ekrandaki belirtiler ve sınırlar

Kaynak bölümlerinin işlenmesi, yeni belge indirme ve kodun uygulanması ayrı aşamalardır. Aynı kaynak numarası birden fazla bölümü içerir. Bilgi kartı üretmek model ağırlıklarını eğitmez; kod taslağı üretmek de kodun uygulandığı anlamına gelmez.

Yeni belge toplama, işlem birikimi 12 bölüme ulaştığında bekler. Güvenlik profilinde mevcut ilgili kaynak istisnası korunur. Bu sürüm sınırsız belge toplamayı veya daha fazla eşzamanlı model çalıştırmayı açmaz. Hatalı bölümler mevcut 30 dakikalık bekleme politikasını korur.

Ekranda otomatik kod geliştirme, Docker/test imajı bulunamadığı için engellenmiş. Normal sohbet başlatıcısı test imajını kurmaz. Windows üzerinde Whisper kapatılmalı, Docker Desktop Linux konteynerleri açık olmalı ve mevcut `WHISPER_GELISIM_BASLAT.cmd` çalıştırılmalı. Bu başlatıcı ilk seferde test imajını hazırlar; kurulum ve model bağlantısı başarısızsa gerekçeyi yazıp durur. ZIP dosyası indirmek Windows bilgisayarındaki Docker kurulumunu değiştirmez.

## Düzeltmeler

- Yalnız başına verilen “araştırma yapmaya devam et” gibi açık araştırma denetimleri, modelin JSON planı üretmesine bağlı kalmadan mevcut `research_control` doğrulamasından geçer. İnternet izni korunur; mevcut araştırma denetimi bilgisayar açma/yazma izninden bağımsız kalır. Konulu veya birleşik istekler bu kısa yol tarafından tüketilmez. Başlatma doğrulaması yeni kaynak öğrenildiği iddiası değildir.
- Eski `blocked` kod işi, sıradaki yeni işi sürekli geride bırakmaz. Aynı taslağın çevre engeli yüzünden test edilememesi yeni kod üretme denemesini tüketmez: üçüncü taslak da test ortamı düzeldikten sonra yeniden sınanabilir. Üç başarısız kod üretimi sınırı, test makbuzu, korunan dosyalar ve geri alma kontrolleri korunur. Docker konteyneri başlamadığında dönen 125 kodu da artık kod hatası değil ortam engeli olarak kaydedilir; aynı taslak korunur. On dakikalık normal kod döngüsü ve ayrı geliştirme modunun bir dakikalık aralığı değiştirilmedi.
- “Neden araştırma yapmıyorsun?” model yorumu yerine kayıtlı durumu gösterir: birikim nedeniyle bekleme, son arama hatası, kaynak/bölüm bazında işleme hatası ve kod geliştirme engeli. Arama hizmetinin hatası, arka plan adaptöründe boş sonuç gibi yutulmadan kuyruğa aktarılır. Başarılı bir aramadan sonra eski arama hatası temizlenir. Günlük bölüm numarasını ve hata nedenini gösterir.

## Doğrulama

Düzeltmeden önce yazılan regresyonlar, model planına düşme, eksik durum alanları ve kuyruk kurtarma hatalarını gösterdi. Ek sınır testleriyle toplam on bir yeni test; model olmadan devam etme, eski sorudan çıkış, izinler, birleşik komutların korunması, birikim/arama hatası, profil istisnası, kuyruk adaleti ve üçüncü taslağın kurtarılmasını denetler. Üretilmiş kodun çalıştırılması/uygulanması bu testlerde taklit edilir; kullanıcı bilgisayarında kod uygulandığı iddia edilmez.

Tam Python ve ağsız Docker test sonuçları aşağıdaki mimari denetim kaydında belirtilir. Kullanıcının Windows/Ollama/Qwen3:8B kurulumu bu buluttan doğrudan denetlenemedi. Sürekli kendini geliştirme veya hız kazanımı garantisi verilmez; bu değişiklikler kanıtlanan kuyruk/denetim hatalarını giderir. Wi-Fi kırma kodu veya yetkisiz ağ işlemi eklenmedi.


## Mimari denetimi ve gerçek denemeler

| Katman | Mevcut uygulama ve doğrulanan davranış | Sınır |
| --- | --- | --- |
| Karar ve bağlam | `reasoning`, `ActionAgent`, gerçek rol geçmişi, üç 20 turlu senaryo; tüm regresyonlar | Modelin her Türkçe isteği doğru anlayacağı kanıtlanmadı. |
| Araştırma | Kalıcı URL/kaynak kuyruğu, sınırlı okuma, kaynaklı kartlar, işlem birikimi ve hata kayıtları | Buluttaki üretim belge okuyucusu yerel DNS çözümlemesinde engellendi. Windows sonucu bilinmiyor. |
| İşletim sistemi araçları | İzinli araçlar, doğrulanan bütün plan, birleşik komutlar, iptal ve süre sınırları | Modelden gelen serbest shell komutları ana bilgisayarda çalıştırılmaz. |
| Kod ve dosya yönetimi | Ayrı taslak, bütünlük hashleri, eski kod kontrolü, atomik değişim ve yedek | Otomatik taslak en fazla iki mevcut küçük modülü değiştirir; korunan dosyalara/yetkilere dokunamaz. |
| Öz düzeltme | Hata çıktısı sonraki kod denemesine aktarılır; üç başarısız taslak sınırı; çevre engelinden kurtarma | Bekleme aralığı ve model hesaplama süresi sürer; sonsuz veya sınırsız gelişim değildir. |
| Test ve etkinleştirme | Ağsız, salt okunur, ayrı kullanıcılı Docker; sıfır test/başarısız test uygulanmaz; yeniden başlatma | Regresyon geçmesi, her yeni hedefin kabul ölçütünün sağlandığını tek başına kanıtlamaz. |

Gerçek yerel Qwen2.5-Coder-1.5B Q4_K_M/llama.cpp CPU ile iki ayrı deneme yapıldı. İlkinde küçük deneme projesindeki sayı/zaman aşımı fonksiyonu üretildi; beş girdi içeren bir test gerçek Docker içinde geçti. Deneme projesine uygulama, yedek ve sürüm hashleri doğrulandı; örnek kişisel veri dosyası korundu. Süre 10,83 saniye. Kullanıcı projesine model üretimi değişiklik uygulanmadı.

İkincisinde üretim okuyucusu DNS hatası verdi. Ardından uygulamayı değiştirmeden, ayrı test girdisi edinimi için oturum proxy’si üzerinden TLS doğrulaması açık HTTPS isteğiyle resmî CPython `queue.rst` belgesi indirildi. Gerçek modele verilen ilk bölümden kaynak alıntıları uygulama tarafından doğrulanan kart ve gelişim taslağı çıktı; ikinci bölüm beklemede kaldı. Süre 75,34 saniye. Bu deney üretim okuyucusunun veya kesintisiz araştırma -> uygulama zincirinin çalıştığı iddiası değildir. [Makinece okunabilir deney kaydı](evaluations/v33_4_pipeline_checks.json).

`tests/test_v31.py` içinde yalnız açık devam komutunun artık model planı gerektirmediğine ilişkin eski taşıma beklentisi güncellendi; işlevsel başarı ve gerçek başlatma denetimleri korundu. Öncelikli üç diyalog test dosyası değiştirilmedi. Daha önce var olan bilgisayar araçları ile araştırma denetimi arasındaki izin ayrımı korundu. Kurulu bulut Docker imajı yeniden kullanıldı; yeni model indirilmedi, bulut yapılandırmasına değişiklik gerekmedi.

Son kontrol: `python -m unittest discover -s tests` ile **572 test geçti, atlanan yok**. Aynı 572 test gerçek Docker içinde `--network=none --read-only --user=65534:65534`, 2 CPU/2 GB bellek sınırı altında da geçti; atlanan yok. Python 3.12/Linux kullanıldı.
