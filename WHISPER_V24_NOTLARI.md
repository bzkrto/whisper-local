# V24 — Doğrudan kod üretimi

V23'te doğal kod istekleri genel araç planlayıcısına gidiyor ve desteklenmeyen araç hatası alabiliyordu. V24 kodlama ve programlama sorularını kod modeline yönlendirir. `Kod geliştir:` mevcut Whisper modüllerinde taslak geliştirme akışını kullanmaya devam eder.

Örnek: `Bana bir hesap makinası kodlayabilir misin?` veya `Python ile bir hesap makinesi kodla`.

Kurulu `qwen2.5-coder:7b` kullanılır. Model bulunamazsa ana yerel modele dönüş mümkündür; işlem kaydında seçilen model gösterilir. Kullanıcı koduna otomatik çalıştırma yapılmaz. Python kodunda AST sözdizimi kontrolü uygulanır; başarısız Python taslağı `.txt` olarak saklanır. Bu kontrol işlevsellik veya güvenlik doğrulaması değildir.

Markdown kod blokları hafıza veritabanının yanındaki `uretilen_kodlar` klasöründe ayrı iş klasörlerine kaydedilir. Kullanım metni de saklanır. Birden çok kod bloğu en fazla 10 ayrı dosya olarak kaydedilir; dosyalar arasındaki bağlantılar otomatik kurulmaz. Model yanıtı sınırlı olduğundan büyük projeler bölümlere ayrılmalıdır. Kod açıklamalarında kod bloğu yoksa dosya oluşturulmaz.

Mobil bağlantıda dosyalar mevcut indirme sistemi üzerinden sunulur. Sesli yanıt yalnızca kısa üretim bilgisini okur; kod metni ekranda kalır.

Kurulum: Whisper'ı kapatıp klasörü yedekleyin. ZIP içeriğinin tamamını mevcut klasöre çıkarıp aynı adlı paket dosyalarını değiştirin. `.venv`, modeller ve kişisel hafıza veritabanını silmeyin. `WHISPER_BASLAT.cmd` ile açın.

Doğrulama: 303 otomatik test; kod isteğinin planlayıcıyı atlaması, dosyanın gerçekten kaydedilmesi, geçersiz Python'un metin olarak kalması ve iptal edilen üretimin dosya oluşturmaması. Gerçek Ollama/Windows/mikrofon ve üretilen hesap makinesi işlevselliği bu ortamda test edilmedi.
