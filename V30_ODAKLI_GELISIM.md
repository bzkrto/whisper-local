# Whisper V30 — Odaklı araştırma ve gelişim taslakları

Bu güncelleme V29 üzerine kurulur. Yeni model indirmek veya Windows güvenliğini kapatmak gerekmez. Yerel Ollama ve Qwen3:8b ile çalışır.

## Kurulum

1. Whisper'ı kapatın. Mevcut klasörün yedeğini alın.
2. ZIP içindeki dosyaları mevcut Whisper klasörüne çıkarıp aynı isimli kod dosyalarını değiştirin. Mevcut veritabanını, .venv klasörünü ve modelleri silmeyin.
3. Ollama'yı açın; WHISPER_BASLAT.cmd ile Whisper'ı başlatın.
4. `Otomatik araştırma durumu` ve `Gelişim durumu` komutlarıyla kontrol edin. Sesli kullanımda tetikleme sözcüğünü söyleyin.

İlk V30 açılışında araştırma profili bir defaya mahsus geliştirme olarak ayarlanır. Önceden kapatılmış otomatik araştırma kapalı kalır. Eski konular ve kaynaklar korunur. Sonradan seçtiğiniz profil tekrar açılışta değiştirilmez.

## Öncelikler

On araştırma turunun hedefleri sırasıyla: bağlam, hafıza, ajan, bağlam, genel keşif, derin öğrenme, hafıza, ajan, bağlam, genel keşif. Bu, uygun kaynak varsa sekiz geliştirme turu ve iki genel keşif turudur; gerçekleşmiş öğrenme başarısı yüzdesi değildir. Hedef konuda o anda uygun belge yoksa diğer kaynaklar okunabilir.

- Türkçe niyet, varlık çıkarımı, çok turlu konuşma ve kısa cevapların bağlama bağlanması.
- Kaynaklı bilgi kartları, RAG, geri getirme ve hafıza değerlendirmesi.
- Araç çağırma, görev planlama, hata inceleme ve regresyon testleri.
- Derin öğrenme, transformer, veri kümesi, fine-tuning ve aşırı öğrenme değerlendirmesi.

Geliştirme konularında resmî teknik dokümantasyon ve akademik kaynaklar kullanılır. İlk kaynaklar Ollama'nın structured outputs, embeddings ve tool calling belgeleri ile PyTorch transfer learning eğitimidir. İngilizce kaynakların bilgi kartları Türkçe işlenir. Kaynak metni talimat veya doğrulanmış gerçek sayılmaz.

Belge işleme de aynı müfredatın sırasını kullanır; görev için özellikle seçilmiş kaynakların işlenmesine müdahale etmez. Önce bilgi kartı, sonra profil işleme yapılır. Çok sayıda işlenmemiş bölüm olduğunda yeni belge edinme duraklatılır. Yeni komut geldiğinde sonraki arka plan model çağrısı ertelenir; başlamış model çağrısı hemen kesilmeyebilir.

## Bilgiyi gelişime bağlama

Kaydedilmiş araç hataları ilgili genel araştırma konusunu yeniden gündeme alır. Kişisel konuşma metni bu arama sorgularına taşınmaz. Aynı deneyim her döngüde tekrar işlenmez. Eksik bilgi için normal bir netleştirme sorusu hata sayılmaz.

İşlenmiş geliştirme kaynaklarından yerel LLM bir küçük değişiklik önerisi üretir: problem, önerilen değişiklik, kullanıcı girdisi ve beklenen davranışı içeren 1–4 kabul testi, sınırlamalar. Kaynak ve bölüm kimliği tutulur. Taslak hazırlama en sık 10 dakikada bir yapılır; geçersiz yanıt en fazla bir kez yeniden istenir; başarısız iş en az bir saat bekler. Kalıcı iş durumları yeniden açılışta korunur.

Bu sürümün ürettiği taslaklar kodu otomatik değiştirmez ve testleri kendi başına çalıştırmaz. Mevcut kod üretimi/test ortamı ayrı yeteneklerdir. Taslak hazırlamayı beceri kazanımı olarak raporlamaz. Model ağırlıkları eğitilmez; RAG, semantik vektör arama veya fine-tuning belgelerinin okunması bunların uygulamaya kurulması anlamına gelmez. Bu sürüm yeni semantik vektör veritabanı kurmaz.

## Komutlar

- `Gelişim durumu` veya `Gelişim taslakları`: son kaynaklı değişiklik ve kabul testi taslakları.
- `Bilgi işleme durumu`: işlenen kaynaklar ve bekleyen bölümler.
- `Otomatik araştırma durumu`: profil, kaynaklar ve hatalar.
- `Araştırma profili: geliştirme`: odaklı araştırma.
- `Araştırma profili: dengeli`: geniş keşif.
- `Araştırma profili: siber güvenlik`: önceki güvenlik ağırlıklı profil.
- `Otomatik araştırmayı durdur` / `Otomatik araştırmayı başlat`.

## Doğrulama sınırı

Otomatik testler Linux ortamında ve denetimli model yanıtlarıyla yürütüldü. Gerçek Windows mikrofonu, masaüstü, ağ erişimi ve kurulu Qwen modelinin yanıt kalitesi bu ortamdan test edilmedi. Kullanıcının bilgisayarında araştırma kalitesi ve görev başarısı ayrıca ölçülmelidir. V29 ses yedeği ve tetikleme davranışı korunur.

Test sonucu: 380 otomatik test geçti (15 yeni V30 testi dahil). Paket dosya bütünlüğü, Python sözdizimi ve ZIP bütünlüğü kontrol edildi.
