# V27 — Araştırmayı kullanılabilir bilgiye dönüştürme

Görüntüde LLM kapalıyken web araması çalışıyordu. Bu durumda belge kaydı yapılabiliyor, model ile işleme yapılamıyordu. V27 boşta işleme döngüsünde yerel model bağlantısını yeniden dener ve bağlantı yoksa sebebi açıkça bildirir. Ollama uygulamasının çalışması gerekir; bir modelin disk üzerinde kurulu olması sunucunun açık olduğu anlamına gelmez.

## Araştırma

Türkçe konu önceliği kaldırıldı. Varsayılan dengeli profilde üç döngüden birinde siber güvenlik, kalanlarda genel konular öncelik alır. Siber güvenlik profilinde bu oran üçte ikidir. Mevcut konular ve eski kayıtlar silinmez. Türkçe dışındaki teknik kaynaklar da aranır; model kartı Türkçe üretir, alıntı özgün dilde tutulur.

NIST, CISA ve OWASP için başlangıç belgeleri eklenir. Siber güvenlik başlıklı kaynaklarda NIST/CISA/OWASP/Microsoft Learn/MITRE resmî alan adları kullanılır; yönlendirme sonrası alan adı da kontrol edilir. Başka konulardaki kaynaklar için mevcut genel belge okuyucu sürer. Kaynak adresleri bilgi yetkisi veya bağımsız doğruluk garantisi vermez.

## İşleme ve hafıza

Kaydedilen belge metni 9.000 karakterlik, 500 karakter örtüşmeli bölümlere ayrılır. Döngü başına bir bölüm yerel LLM ile işlenir. Özet, kavramlar, kaynak alıntıları ve varsa kullanım durumları/öneri adımları kalıcı SQLite kartlarında tutulur. Önerilerin alıntısı kaynak bölümünde bulunmalıdır; iddia veya adımların alıntı tarafından mantıksal olarak desteklenmesi bağımsız doğrulanmaz.

Önceden işlenmiş ilk bölüm kartları korunur; kalan bölümler kuyruğa eklenir. Tam makale metni olan `article_snapshot` kayıtları da işlenir. `search_excerpt` arama parçaları tam belge gibi yükseltilmez. Okuyucunun sınırı hâlâ kaynak başına 30.000 karakter, PDF için 30 sayfadır; kayıtlı sınırın ötesindeki içerik işlenmiş sayılmaz. OCR yoktur.

İşlenmemiş bölüm sayısı 12 veya üstündeyse yeni otomatik belge okumak yerine işleme döngüsüne devam edilir. Hatalı bölümler 30 dakika sonra yeniden denenir. Arka plan kullanıcı komutlarından sonra sıra alır. Uygulama ve Ollama açıkken işleme sürer; araştırma duraklatılırsa otomatik işleme de durur. Elle `Bilgileri işle` araştırma duraklatılmışken de bir bölümü işleyebilir.

## Bilgiyi kullanma

İlgili kartlar, konu sorularında kaynaklı cevap yoluna, kod üretiminde kod modelinin bağlamına ve görev planlayıcısının kaynak bağlamına aktarılır. Kart ile eşleşen bir bilgi sorusu araç planlayıcısına gitmeden cevaplanır. Eşleştirme Türkçe/İngilizce kavram eş anlamlıları ve sözcük örtüşmesi kullanır; embedding tabanlı semantik arama değildir. Son 500 işlenmiş bölüm arasından en fazla üç kart alınır. Kaynak cevaplarında modelin verdiği kayıt numaraları gerçekten getirilen kartlarla sınırlanır ve kaynak URL'leri uygulama tarafından eklenir. Yanıt doğruluğu yine bağımsız doğrulanmış değildir.

Komutlar:

- `Araştırma profili: siber güvenlik`
- `Araştırma profili: dengeli`
- `Bilgi işleme durumu` — bağlı model, tam işlenen belgeler, bölüm ilerlemesi, hatalar
- `Bilgileri işle` — bir bölüm; sonuç ve kuyruk durumunu gösterir
- `Bilgilerinden yanıtla: parola güvenliği için kontrol listesi hazırla`
- `Bugün neler öğrendin?` — okunan kaynaklar ve işlenen bölüm durumu
- `Python ile parola güvenliğini kontrol eden bir örnek kod yaz` — eşleşen kartlar kod modeline aktarılır; kod otomatik çalıştırılmaz

Bir kartın bulunması veya öneri üretilmesi, bir Windows ayarının değiştirildiği ya da bir güvenlik testinin yapıldığı anlamına gelmez. Model ağırlıkları eğitilmez; belgeler kaynaklı hafızaya işlenir.

## Kurulum ve deneme

Whisper'ı kapatıp klasörü yedekleyin. ZIP'in tamamını mevcut klasöre çıkarıp aynı adlı paket dosyalarını değiştirin. `.venv`, indirilen modeller ve hafıza veritabanını koruyun. Ollama uygulamasını açın; `WHISPER_BASLAT.cmd` ile başlatın. Önce `Bilgi işleme durumu`, sonra `Araştırma profili: siber güvenlik` yazın. İşleme kayıtları “🧠 Bilgi işleme: processed” şeklinde görünür. Kaynak kartı oluşmadan kaynaklı soruya bilgi bulunduğu iddia edilmez.

326 otomatik test geçti. Testler İngilizce metin/kaynak alıntısı, uygulama kartı, uzun belge bölümleri, yeniden başlama/eskiden işlenmiş kartların korunması, uydurma alıntı ve kayıt numarasının reddi, arama parçasının belge sayılmaması, kod modeline bağlam aktarımı, LLM yeniden bağlanması ve okuma birikimini kapsar. Gerçek Windows, yerel Ollama yanıtları ve kaynak web erişimi bu ortamda uçtan uca çalıştırılmadı.
