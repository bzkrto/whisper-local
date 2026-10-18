# V29 — ses kesintisi ve takip bağlamı

Ekrandaki kayıt müzik isteğinin anlaşıldığını ve “Hangi şarkıyı açmak istersiniz?” sorusunun üretildiğini gösteriyor. Edge TTS websocket isteği 403 ile reddedildiği için soru sesli okunmamış. Bu ekran tek başına takip cevabının yanlış yorumlandığını göstermiyor.

Düzeltmeler:
- Windows'ta açıkça --tts edge seçildiğinde de SAPI yerel ses yedeği eklenir.
- 401/403/429 durumunda hizmete aynı metinle üç kez yüklenilmez. Beş dakika çevrimiçi ses denenmez; kullanılabilir yerel motora geçilir. Sonrasında çevrimiçi ses yeniden denenebilir.
- Motor çökerse de yedek denenir; kullanıcı iptal ettiyse yedek konuşmaya başlamaz.
- SAPI kendi tek iş parçacığında oluşturulur ve konuşur. Başlatma hatası ve zaman aşımı metin yanıtını veya bekleyen soruyu silmez.
- Bekleyen sorunun özgün isteği, niyeti, varlıkları ve takip cevapları yeniden modele gönderilir. LLM'e sanatçı başına ayrı kural eklenmedi.
- Ayrı “Hey Whisper” seslenişine yanıt verdikten hemen sonra gelen komutta ikinci “Sizi dinliyorum” okunmaz.

Kurulum: Whisper'ı kapatın, klasörünüzü yedekleyin, ZIP'in tamamını mevcut klasöre çıkarıp aynı adlı kod dosyalarını değiştirin. .venv, modeller ve kullanıcı .db dosyalarını silmeyin. WHISPER_BASLAT.cmd ile açın.

Çevrimiçi sesin kurulu kütüphanesini güncellemek isterseniz WHISPER_SES_ONAR.cmd dosyası yalnız bu projenin .venv ortamındaki edge-tts ve pyttsx3 paketlerini günceller. Yönetici yetkisi veya Windows güvenliğini kapatma gerekmez. Güncelleme uzak hizmetin erişim reddini kesin olarak gidereceği anlamına gelmez; yedek bu nedenle eklendi.

Deneme:
1. “Hey Whisper, YouTube'dan bir şarkı açabilir misin?”
2. Soru geldikten sonra “Hey Whisper, Bergen.”
3. Sistem mevcut YouTube arama aracıyla sanatçının arama sonuçlarını açar; gerçek oynatma doğrulanmadığı için “çalınıyor” demez.

Sesli her yeni komut için tetikleme sözü hâlâ gerekir. Tek başına sesleniş, yalnız bir sonraki kısa komut için bekleme penceresi açar. Yazı testinde tetikleme sözü gerekmez.

Windows'ta Türkçe yerel ses kurulmamışsa motor mevcut varsayılan sesi kullanabilir; Edge ile aynı ses kalitesi garanti edilmez. Gerçek Windows ses donanımı ve gerçek Qwen yorumlama kalitesi bu Linux test ortamında sınanamadı.

Resmi proje hata kaydı: https://github.com/rany2/edge-tts/issues/463

Son kontrol: 365 otomatik test geçti. 403, motor çökmesi, yerel yedeğe geçiş, iptal ve müzik isteği → sanatçı cevabı senaryoları kontrollü testlerle sınandı.
