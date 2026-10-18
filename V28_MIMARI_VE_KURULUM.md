# Whisper V28 — ortak görev beyni

Bu paket V27 üzerine kod güncellemesidir. Mevcut kullanıcı veritabanını, modelleri ve .venv ortamını silmez.

## Kurulum

1. Whisper'ı kapatın. Mevcut Whisper klasörünüzün yedeğini alın.
2. ZIP'in bütün içeriğini mevcut Whisper klasörüne çıkarın; aynı adlı kod dosyalarını değiştirin. .venv, modeller ve kullanıcı .db dosyalarını silmeyin.
3. Ollama'yı açın. WHISPER_KONTROL.cmd ile paket kontrolünü, WHISPER_BASLAT.cmd ile uygulamayı başlatın.
4. Sesli komutları mevcut tetikleme sözüyle söyleyin: “Hey Whisper, Bergen aç” veya “Hey Whisper, siber güvenlik eğitimi hazırla”. Yazılı/mobil komutta tetikleme sözü gerekmez.
5. Yeni bağımlılık eklenmedi. Mevcut gereksinimler requests, python-docx, reportlab ve pypdf dahil kurulu olmalı.

## Birleştirilen mimari

- Brain/Planner: kalıcı SQLite görev durumu, aşama kayıtları ve yürütme sahipliği. Tamamlanan adımlar tekrar edilmeden devam edilir. Ağ isteği tam başarılıyken kayıt öncesi kapanma halinde okuma tekrar gerekebilir; tam olarak bir kez çalıştırma garantisi yoktur.
- Intent/Context: yerel Ollama JSON şemasıyla intent, entities, missing_fields ve araç planını birlikte üretir. Sanatçı listesi veya sanatçı başına ayrı kural yoktur. Son konuşma ve önceki görev sonucu modele verilir. Belirsizlikte açıklama ister. Envanter/argüman doğrulaması yapılmadan araç çalışmaz.
- Research/Learning: görev için en fazla üç kaynak seçilir, genel HTTPS belge okuyucuyla okunur, kaynak metni kaydedilir ve yalnız bu görevin kaynakları LLM ile işlenir. Arama özeti, okunmuş belge gibi gösterilmez.
- Memory/User Profiling: boşta çalışan yerel LLM, son 50 konuşma içinden sırayla açık kullanıcı beyanlarını çıkarır. Alıntının kullanıcının mesajında bulunduğu doğrulanır. Donanım, program, proje ve tercih alanları güncellenir; değişiklik geçmişi tutulur. Varsayım ve sorular gerçek kullanıcı bilgisi sayılmaz. “Profil hafızası” görüntüler, “Profilimi unut” bu yeni profil kayıtlarını da siler. Konuşma geçmişi ve diğer eski hafıza kayıtları ayrı kalır.
- Context Fusion: kullanıcı profil beyanları konuşma ve araç planlama bağlamına eklenir. get_user_profile aracı gerçek kayıtları döndürür; örnek donanım sabit yazılmamıştır.
- Knowledge Gap: LLM investigate aracını seçerse aynı görev zinciri araştırır, okur, bilgi kartına işler ve kaynaklı yanıt üretir; dosya üretimi istenmediyse dosya oluşturmaz.
- Production: eğitim/rapor/sunum ve video senaryosu isteğinden kaynaklı bölüm içeriği üretir. Markdown, Word, PDF ve düzenlenebilir PowerPoint dosyaları oluşturur. Görsel sunum tasarımı ve otomatik video render bu sürümün kapsamı dışındadır.
- Verification: bilgi kartları için ayrı eleştirel LLM çağrısı, kaynak alanı sayımı, olası çelişki/yetersiz kanıt işaretleri. Aynı sitenin alt alanları bağımsız kaynak sayılmaz. Farklı alanlar da bağımsız yazarlığı garanti etmez. İnsan inceleme ihtiyacı işaretlenir; kullanıcı adına teyit verilmez. JSON şeması, kaynak kimlikleri, alıntı eşleşmesi, dosya hash'i, Office ZIP bütünlüğü ve PDF başlığı kontrol edilir. Modelin içerik doğruluğu bağımsız doğrulanmış sayılmaz. Modelin güven puanı kullanılmaz.
- Mobile: mevcut aynı komut köprüsü ve dosya indirme mekanizması üzerinden görevler kullanılabilir. PC'den bağımsız bulut barındırma eklenmedi.

## Örnek kullanım

- Siber güvenlik eğitimi hazırla.
- Yapay zekâ hakkında video senaryosu hazırla.
- Görev oluştur: Elektrikli araç şarj istasyonu fizibilitesi hazırla.
- Görevlerim
- Görev durumu: 1
- Göreve devam et: 1
- Profil hafızası
- Bilgi işleme durumu
- Bergen aç
- Değiştir, başkasını aç

“Bergen aç” YouTube sanatçı aramasına yönlenebilir. Mevcut araç otomatik oynatma sağlamaz; çalınıyor diye bildirilmez. Sanatçı/şehir ayrımının gerçek Qwen modelindeki kalitesi PC'de ölçülmelidir.

## Görev ve öğrenme sınırları

Bir kaynak okuma: 2 MB, yaklaşık 25 saniye, PDF için en fazla 30 sayfa; metin en fazla 30.000 karakter. Görev en fazla üç kaynak ve on iki metin bölümü işler. Kısmi/okunamayan kaynaklar raporda belirtilir. Finansal fiyat, yatırım ve geri dönüş hesapları gerçek veriler olmadan doğrulanmış fizibilite sayılmaz.

Bu sürüm model ağırlıklarını eğitmez; kalıcı kaynak/deneyim/profil hafızasını geliştirir. Mevcut vektör araması karakter tabanlı sözcüksel aramadır; gerçek anlamsal embedding veya bilgi grafiği bu güncellemede eklenmedi. Ayrı uzman finans ajanı, genel güvenli kod çalıştırma ortamı ve onay sonrası canlı araç yükleme ayrıca geliştirilecek bileşenlerdir. Önceki ayrı taslak/Docker test sistemi korunmuştur.

Görevler kendiliğinden yeniden başlamaz. Kapanmış oturumun yürütme sahipliği en fazla 15 dakika, kaynak işleme rezervasyonu en fazla 30 dakika içinde sona erer; normal hata/iptalde görev sahipliği hemen bırakılır. “Göreve devam et” kaydedilmiş sonuçları kullanır. Aktif LLM isteği anında kesilemeyebilir; iptal sonrasında yeni bilgi/çıktı tamamlandı diye kaydedilmez.

## Testlerin anlamı

Testler kalıcı görev aşamalarını, yeniden başlatma/devam, iptal, yanlış kaynak kimliği, kaynak okunamaması, bozuk Office çıktısı, dosya değişikliği, profil alıntısı ve niyet-plan doğrulamasını kapsar. Gerçek dosyalar python-docx, reportlab ve pypdf ile üretilip açılır. Ollama HTTP adaptörü yerel bir test sunucusunda JSON şeması ve tam görev akışıyla sınanır; sunucu yanıtı kontrollü test verisidir. Gerçek Qwen çıkarımı, Windows mikrofonu/GPU'su, Office görüntüsü ve internet kaynaklarının canlı erişimi bu ortamda test edilmemiştir.

Ollama format alanı için resmi kaynak: https://docs.ollama.com/capabilities/structured-outputs

Bu mimari özel Python modülleri, SQLite ve yerel Ollama adaptörüyle uygulanmıştır; LangChain/LangGraph kurulması gerekmez. Zaman ve saat dilimi, mevcut konuşma, son görev ve kullanıcı profili birlikte planlama bağlamına verilir.

Son otomatik kontrol: 357 test geçti (2026-10-10). Test sonucu kontrollü model/arama yanıtlarıyla elde edildi; gerçek Qwen yanıt kalitesi için canlı PC testi gerekir.
