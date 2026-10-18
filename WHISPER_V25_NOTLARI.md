# V25 — Kullanıcı komutlarını bekletme

Ekran görüntüsünde kod komutu, “Sizi dinliyorum” seslendirmesi sırasında ortak işlem kilidi dolu olduğundan `busy` ile reddedilmişti. Arka plan kaynak işleme de aynı kilidi tutabiliyordu.

V25 devam eden işlem varken bir kullanıcı komutunu bekletir ve işlem tamamlanınca yürütür. Bekleme sırasında yeni kaynak işleme/zamanlanmış araştırma/hatırlatma turu başlamaz. Devam eden model çağrısı zorla kesilmez. Bekleme en fazla 120 saniyedir; bu süre dolarsa komutun çalıştırılmadığı bildirilir. İkinci bekleyen komut reddedilir; sınırsız bir kuyruk yoktur. `Dur` ve “Yanıtı kes” bekleyen isteği iptal eder; iptal edilen istek yeniden oynatılmaz.

V24 kod yönlendirme ve dosya üretme özellikleri dahildir. `Python ile pencereli bir hesap makinesi kodla` komutu kurulu yerel kod modeline gider, çıktılar `uretilen_kodlar` klasörüne kaydedilir. Kod otomatik çalıştırılmaz; Python AST kontrolü işlevsel test değildir.

Kurulum: Whisper'ı kapatıp klasörü yedekleyin; ZIP'in tamamını mevcut klasöre çıkarın, aynı adlı paket dosyalarını değiştirin. `.venv`, modeller ve hafıza veritabanını koruyun. `WHISPER_BASLAT.cmd` ile başlatın.

Deneme: yazılı `Araştırmayı duraklat` komutu ardından mikrofonu durdurup `Python ile pencereli bir hesap makinesi kodla` yazın. Kod üretimi doğrulandıktan sonra mikrofon ve araştırma tekrar açılabilir. Yazılı girişte tetikleme kelimesi gerekmez.

307 otomatik test geçti. Gerçek Windows/Ollama/mikrofon ve üretilen uygulamanın işlevselliği bu ortamda doğrulanmadı.
