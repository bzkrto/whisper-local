# V26 — Ses tanıma ipucu ve tekrar filtresi

Ekranda ses tanımanın “Whisper adlı bilgisayar asistanı” tanıma ipucunu aynen ürettiği ve “ışık” gibi kelimeleri tekrarladığı görüldü. Gerçek ses kaydı bu ortamda bulunmadığından kaynağın ortam konuşması, hoparlör yankısı veya modelin gürültüde metin uydurması olduğu kesin olarak belirlenemedi.

Varsayılan cümle biçimli initial_prompt kaldırıldı. Türkçe dil seçimi ve kelime ipuçları devam eder. Tamamen sessiz ve sayısal sıfıra çok yakın girişler ses yükseltilmeden önce elenir. Bir kelimenin art arda dört veya daha fazla tekrarlandığı tanıma segmenti elenir. Bu, gerçek konuşmadaki dört tekrarın da elenebileceği anlamına gelir; kusursuz konuşma ayrımı sağlamaz. VAD ve mevcut model kalite filtreleri korunur. Tetikleme kelimesi olmadan normal konuşma komut olarak yürütülmez.

V25 bekleyen kullanıcı komutu ve V24 kod üretimi dahildir. 310 otomatik test geçti. Testler sessiz girişin model çağırmaması, tekrarlayan çıktının elenmesi, gerçek tetikleme komutunun korunması ve Türkçe kelime ipuçlarının sürmesini kapsar. Gerçek mikrofon ve ortam gürültüsü bu ortamda test edilmedi.

Kurulum: Whisper'ı kapatıp klasörü yedekleyin. ZIP'in tamamını mevcut klasöre çıkarıp paket dosyalarını değiştirin. `.venv`, modeller ve hafıza veritabanını koruyun. Başlatırken mikrofon kalibrasyonu sırasında sessiz kalın. Denemede hoparlör yerine kulaklık kullanın.

Kontrol: 20 saniye sessiz bekleyin; ardından “Hey Whisper, saat kaç?” söyleyin. Tam sessizlikte anlamsız metinler veya tekrarlayan kelimeler sürüyorsa mikrofon aygıtı, kazanç, ortam gürültüsü ve model çıktısı birlikte incelenmelidir. “Kaynak” ve “LLM sunucu süreleri” satırları arka plan araştırmasına da ait olabilir; kendi başına sesli komut alındığı anlamına gelmez.
