# V33.2 — Gerçek araştırma durumu ve yazılı sohbete öncelik

Dal: `codex/dialogue-context-v33`. Ana dala birleştirme ve ses geliştirmesi yapılmadı.

## Sorun ve gözlenen davranış

“Araştırma yapıyor musun?” bilgi sorusu araç planlayıcısına gidiyordu. Modelin uygun olmayan planı iki kez üretilip doğrulanabiliyor; ayrıca hata deneyimine bağlı öğrenme analizi çalışabiliyordu. Sonuç, araştırma durumunu açıklamayan bir plan hatasıydı.

“Nasılsın?” arka plandaki bilgi işleme işleminin tuttuğu model kilidini bekliyordu. Ön plan kuyruğunun 10 saniyelik sınırı dolduğunda mesaj yanıtlanmadan düşüyordu.

Kod geliştirme arka plan döngüsü her 30 saniyede bir, işin varlığını ve çalışma zamanını kontrol etmeden önce kod modelini seçiyordu. ModelPool rol değişiminde önceki modeli boşalttığı için, boş veya zamanı gelmemiş kuyruk bile gereksiz model değişimi ve sonraki sohbet/kart isteğinde yeniden yüklemeye neden olabiliyordu.

## Değişiklik

- Salt durum soruları ayrı ve salt okunur bir yoldan yanıtlanır. Bu yol model kilidi, LLM, web araması, araç planı veya öğrenme analizi çağırmaz. Araştırma ayarı/profili, gözlenen arka plan aşaması, kaynak/bölüm sayıları, son kayıtlı konu, taslak ve kod işi durumları SQLite kayıtlarından okunur. Araştırmanın açık olmasıyla o anda çalışan iş birbirinden ayrılır. Taslak sayısı uygulanmış kod değişikliği gibi sunulmaz. SQLite okunamıyorsa doğrulanamayan durum uydurulmaz.
- Durum tanıma yalnız salt sorular içindir. “Araştırma yapıyor musun, Chrome aç” gibi birleşik eylemler bu yola alınmaz; mevcut araç doğrulama ve izin akışı korunur.
- Boş, devre dışı, yeniden başlatma bekleyen veya henüz zamanı gelmemiş kod kuyruğunda kod modeli seçilmez. Yeni kaynak taslaklarının kuyruğa alınması idempotent olarak devam eder. Gerçek işi bulunan kuyruk kod modelini kullanır.
- Arka plan Ollama metin/JSON üretimi akışlı taşınır. JSON şeması aynen korunur; yalnız eksiksiz çıktı kabul edilir. Yazılı mesaj beklemeye girdiğinde akış kapatılır, model kilidi bırakılır ve yazılı istek sırayı alır. Aynı anda ikinci model isteği başlatılmaz. Rol değiştirme veya yeni araç yetkisi bu mekanizmanın parçası değildir.
- Arka plan HTTP bağlantısı için 3 saniye bağlantı ve en fazla 8 saniye okuma bekleme sınırı vardır. Bu toplam üretim süresi sınırı değildir; tokenlar geldikçe uzun işler devam edebilir. İlk veri beklemesi sınırı aşılırsa iş yeniden denenebilir duruma döner. Ön planın model istek süresi değiştirilmedi.
- Kesilen bilgi kartı, profil çıkarımı veya taslak üretimi hata/backoff kaydı yerine yeniden denenebilir bekleme durumuna alınır. Yarım çıktı kabul edilmez. İptal edilen kod önerisinin deneme hakkı tüketilmez; test/uygulama adımları başlatılmaz. Hazır taslak korunabilir.
- Normal selamlaşma sohbeti artık sabit GREETING_MAP cevabıyla sonlandırılmaz; gerçek konuşma geçmişiyle model yanıtı alınır. Saat/tarih gibi deterministik araç yanıtları korunur.

## Ekrandaki kayıtlar ne anlama geliyor?

`Bilgi işleme: processed | kaynak ...` kaynak bölümünün bilgi kartına işlendiğini gösterir. `Profil işleme` açık kullanıcı beyanlarını ayrıştırır. `Gelişim taslağı: draft` inceleme/kod hedefi için taslak üretildiğini gösterir. Bunların hiçbiri tek başına canlı kodun değiştirildiği veya model ağırlıklarının eğitildiği anlamına gelmez.

## Doğrulama ve sınırlar

`python -m unittest discover -s tests`: **548 test geçti; atlanan yok** (Linux/Python 3.12). Yeni 13 test; gerçek kuyruk/veritabanı, native Ollama HTTP yükü, iki eşzamanlı iş parçacığı ve taklit HTTP yanıtlarıyla çalışır. Arka plan kart üretimi sürerken yazılı sohbetin başarıyla tamamlanması, yarım kartın kaydedilmemesi, yeniden deneme durumu ve HTTP akışının kapatılması denetlenir.

Başlangıçtaki yeni 6 test, düzeltme öncesinde 2 başarısız doğrulama ve henüz bulunmayan yeni davranışlara ait 4 hata verdi. Önceki iki iptal testi, `error` yerine `cancelled` sonucunu bekleyecek şekilde güncellendi; kart/taslak kaydedilmeme kontrolleri korundu ve kuyruk/deneme kontrolleri güçlendirildi. V33 diyalog testleri değiştirilmedi.

Gerçek Ollama/Windows/GPU gecikmesi ve Docker testleri bu çalışmada ölçülmedi. Akışlı öncelik verme native Ollama model üretimine aittir; başlamış Docker testi veya canlı dosya uygulaması bu değişiklikle zorla kesilmez. Bu nedenle her işlem türü için anlık yanıt veya sabit saniye hedefi garanti edilmez. Başka özel model istemcilerinin eski iptal parametresi arayüzü korunur.

Whisper'ı kapatıp mevcut klasörü yedekleyin; ZIP içindeki proje dosyalarını mevcut klasöre kopyalayın. Kişisel DB ve ses dosyalarını silmeyin. `WHISPER_BASLAT.cmd` ile yazılı arayüzü açın; “Araştırma yapıyor musun?” ve “Ne araştırıyorsun?” durum soruları doğrudan mevcut kayıtları gösterir.
