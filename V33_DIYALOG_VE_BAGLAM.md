# V33 — Türkçe diyalog ve oturum bağlamı

Geliştirme dalı: `codex/dialogue-context-v33`. Başlangıç: V32.13 (`6e4f25b`) ve dalın `AGENTS.md` talimatları (`47bd876`). Bu çalışma ana dala birleştirilmez; Windows dağıtımı yayımlanmış değildir.

## Doğrulanan sorun

V32.13 istemcisi Ollama'ya yalnızca `system` ve güncel `user` gönderiyordu. Önceki konuşmalar sistem istemindeki düz metne ekleniyordu; kısa sohbet yolunda yalnız iki eski tur vardı. Dar sohbet sınıflandırması takip sorularını araç planlayıcısına veya web aramasına gönderebiliyordu. İlgisiz kalıcı kullanıcı bilgileri de sıradan sohbette taşınıyordu.

Düzeltmeden önce yeni dört test fonksiyonu bu davranışları başarısız olarak doğruladı: gerçek mesaj rolleri, takip sorusunun yönü, ilgisiz kalıcı veriler ve 20 turlu bağlam aktarımı. Alt testler dahil toplam 23 başarısız doğrulama vardı.

## Uygulama

- Normal sohbet ve akışlı yanıt aynı yapılandırılmış geçmişi kullanır. Ollama/OpenAI uyumlu istemcilerde gerçek `user`/`assistant` rolleri, Gemini'de `user`/`model` rolleri gönderilir. Güncel kullanıcı mesajı en sonda kalır. İstemcilere isteğe bağlı `history` parametresi eklendi; önceki çağrı biçimi korunur. Yeni parametreyi desteklemeyen özel istemcilere geçmiş zorlanmaz.
- Yeni `ConversationWindow` en fazla 24 tamamlanmış tur tutar. Her mesaj en fazla 4096 UTF-8 bayt saklanır. İstek geçmişi en fazla 3072 bütçe birimidir; model bağlamından sistem, güncel soru, çıktı payı ve ek tampon düşülür. Türkçe için iyimser karakter/token oranı yerine UTF-8 baytları ve mesaj ek yükü sayılır. Bu, gerçek tokenizer ölçümü değildir; muhafazakâr bir üst bütçedir.
- Son tamamlanmış tur önceliklidir. Önceki turlar sorgudaki sözcük örtüşmesi ve yakınlığa göre seçilir, kronolojik sırada ve kullanıcı/yanıt çifti olarak gönderilir. Büyük son tur başından ve sonundan kısaltılır. Bu mekanizma anlamsal özet veya sınırsız hafıza değildir; küçük bütçede eski ayrıntılar elenebilir.
- Yeni Brain örneği boş konuşma penceresiyle başlar. Veritabanındaki eski oturumlar sıradan sohbete otomatik eklenmez. İlgili kullanıcı kayıtları, hitap tercihleri ve kaynak parçaları ayrı etiketli veri mesajında, sınırlı boyutta taşınır. Yaygın anahtar/şifre, e-posta ve telefon biçimleri geçmişte maskelenir; kalıcı kayıtta hassas biçim eşleşen veri alınmaz. Bu kurallar tüm kişisel veri türlerini tanıyan bir gizlilik sınıflandırıcısı değildir. Güncel kullanıcının sorusu değiştirilmez.
- Sistem talimatı normal sohbette sabittir; geçmiş konuşma sistem yetkisi kazanmaz. Geçmiş API'si `system`, `tool`, ek araç çağrısı alanları veya metin dışı içerik kabul etmez. Araç sonuçları etiketli uygulama kaydı olarak tutulur; yeniden araç çalıştırmaz. Mevcut inceleme amaçlı parametresiz `system_prompt()` arayüzü korunur; olağan sohbet bu yolu kullanmaz.
- “Biraz açar mısın?”, “Onu kastetmedim”, konuya dönüş ve kısa takipler sohbet olarak yönlendirilir; hazır yanıt üretilmez. Açık araç fiilleri ve birleşik eylemler mevcut ActionAgent akışına gider. Bekleyen açıklama sorusu varsa kısa yanıt planlayıcıya ulaşır. Kod üretimi, kaynak kartı yanıtları ve güncel bilgi doğrulaması korunur. Açıklama isteyen karmaşık soruların çıktı bütçesi kısa sohbet sınırına düşürülmez.
- İptal edilen model yanıtı ve tamamlanmamış kullanıcı turu tamamlanmış geçmişe eklenmez. İptal komutu ve gerçek iptal kaydı tutulur. Başlamış bilgisayar eylemleri geri alınmış gibi gösterilmez.

Sınıflandırma Türkçe örüntülerine dayanır ve bütün serbest ifadeler için anlamsal doğruluk garantisi vermez. Araç çalıştırma yetkisi, doğrulayıcılar, izin denetimleri ve güvenlik kontrolleri genişletilmedi.

## Test kanıtı

Komut: `python -m unittest discover -s tests` (Linux, Python 3.12, mevcut test bağımlılıkları).

Sonuç: **526 test geçti, atlanan yok**. Mevcut diyalog/V32/V32.12 testleri değiştirilmedi.

Yeni `tests/test_dialogue_context_v33.py` içinde 16 test bulunur:

- İki ayrı 20 turlu konuşma: isim/görev takibi, zamirli takip, konu değişimi, isim düzeltmeleri ve özet isteği. İkinci senaryo gerçek ActionAgent doğrulamasıyla birleşik iki eylemi ve iptal komutunu kapsar; işletim sistemi yürütücüsü taklittir.
- Gerçek istemcinin HTTP yükünde mesaj rolleri, son kullanıcı sorusu, önceki yanıtlar, düzeltilen isimler ve uygulama kayıtları denetlenir. Model çıktıları önceden belirlenmiştir; bu testler modelin kendisinin Türkçe akıl yürütmesini ölçmez.
- Ayrı eşzamanlı test, üretim sürerken iptali ve yarım yanıtın sonraki bağlama sızmamasını doğrular.
- Kısa açıklama yanıtı, kapalı araç izni, yeni Brain/aynı veritabanı sınırı, toplam istek bütçesi, Unicode kısaltma, pencere boyutu, ilgili isimlerin seçimi, kopya izolasyonu ve ayrıcalıklı rol reddi sınanır.
- Ollama/OpenAI uyumlu akışlı ve normal taşıma ile Gemini rol dönüşümü çevrimdışı sınanır.

Gerçek Ollama model kalitesi, Windows mikrofonu, TTS doğallığı, GPU gecikmesi ve V33 Docker çalıştırması bu çalışmada sınanmadı. Bu değişiklik yeni model indirmez ve model ağırlıklarını eğitmez. Otomatik kod geliştirme, siber araçlar veya Android kapsamı genişletilmedi.
