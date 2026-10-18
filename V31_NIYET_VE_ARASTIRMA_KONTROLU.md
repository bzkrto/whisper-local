# Whisper V31 — Araştırma komutunu bilgi sorusundan ayırma

## Düzeltilen hata

V30'da `araştırma yapmaya devam et` gibi bir ifade kayıtlı bilgi kartıyla eşleşirse, araç planlaması yapılmadan karttan tanım üretiliyordu. Sözcük eşleşmesi, kullanıcının işlem yapma niyetinin önüne geçiyordu.

V31'de doğal girdiler için yerel LLM'in araç ve niyet planlaması, otomatik bilgi kartı yanıtından önce yapılır. Doğrudan ve açık komut yolları korunur. `Bilgilerinden yanıtla:` gibi açık kaynaklı cevap komutları da korunur.

Yeni `research_control` aracı, `start`, `pause`, `status` eylemlerini kabul eder. Araştırmayı sürdürme isteği yeni konu aramasıyla karıştırılmaz. Durum sorgusu, mevcut ayarı okur; araştırmayı kendiliğinden açmaz. İnternet kapalıysa başlatma isteği engellenir. Başlatma yanıtı yeni bilgi öğrenildiğini iddia etmez; ayarın değiştiğini bildirir. Araç çıktısında okunan ayar ve arka plan çalışanının mevcut durumu tutulur.

LLM, planlamada araştırmanın açık/kapalı durumunu ve internet özelliğinin kullanılabilirliğini görür. Araç ve argümanlar yürütülmeden doğrulanır. Bu düzeltme tek tek sanatçı veya komut ifadeleri için yeni bir anahtar kelime listesi oluşturmaz. Yerel modelin her ifadeyi doğru sınıflandırması yine model kalitesine bağlıdır.

## Ekran görüntüsünün gösterdiği durum

- `Bilgi işleme: processed`: kaynak bölümleri işleniyor.
- `Gelişim taslağı: draft`: V30 gelişim taslağı oluşturmuş; uygulanmış kod değişikliği değildir.
- `Komut sıraya alındı`: arka plan model çağrısı bitince kullanıcı komutu işleniyor.
- `Duyulan ham metin: (boş)`: o ses parçasından yazı çıkarılamamış. Bu görüntü tek başına mikrofon arızasını veya konuşma tanıma kalitesini kanıtlamaz.

## Kurulum

Whisper'ı kapatın, mevcut klasörün yedeğini alın. Bu ZIP'in tamamını mevcut klasöre çıkarıp aynı adlı kod dosyalarını değiştirin. Veritabanını, .venv klasörünü ve modelleri koruyun. Ollama açıkken WHISPER_BASLAT.cmd ile başlatın.

Kontrol için: `Araştırma yapmaya devam et`, ardından `Otomatik araştırma durumu`. Durumun açık olduğunu kontrol edin. Daha sonra `Araştırma nedir?` ile tanım sorusunu ayrı deneyin. `Gelişim durumu` ile mevcut taslaklara bakın. Sesli kullanımda her yeni komutta tetikleme sözcüğünü kullanın.

V30 odaklı araştırma ve V29 ses yedeği korunur. Model ağırlıkları eğitilmez. Taslaklar otomatik uygulanmaz. Testler denetimli model yanıtlarıyla Linux ortamında yürütülmüştür; gerçek Windows mikrofonu ve bilgisayarınızdaki Qwen yanıt kalitesi ayrıca denenmelidir.

Doğrulama: 388 otomatik test geçti; 8 yeni V31 testi dahil. Python sözdizimi, paket dosya hashleri ve ZIP bütünlüğü kontrol edildi.
