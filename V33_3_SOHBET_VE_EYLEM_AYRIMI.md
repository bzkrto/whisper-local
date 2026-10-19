# V33.3 — Sohbet ve eylem ayrımı

Dal: `codex/dialogue-context-v33`. Ana dala birleştirme yok; ses çalışması askıda.

## Önceki düzeltmenin açık kalan kısmı

V33.2'de, sohbet sınıflandırıcısının tanımadığı mesajlar sırf yerel bir model bağlı olduğu için araç planlayıcısına gönderilebiliyordu. “Siber güvenlik” gibi bir konu adı ve küçük yazım hataları bu yolu tetikliyordu. Bekleyen bir araç sorusu da yeni bir selamlaşmanın araştırma konusu gibi yorumlanmasına neden olabiliyordu. Süresi dolmuş soru temizlenirken ayrıca tutulan `awaiting` bayrağı her zaman temizlenmiyordu.

Bunlar kullanıcının güncellemeyi yanlış kurmasıyla açıklanamaz. V33.2 testleri bu konuşma geçişlerini yeterince kapsamamıştı. Sadece toplam test sayısı uygulamanın günlük konuşmada doğru çalıştığının kanıtı değildir.

## Uygulama

Normal metnin varsayılanı sohbet oldu. “Yerel model bağlı” koşulu araç yönlendirmesinden kaldırıldı. Açık eylem sinyalleri ve gerçekten bekleyen sorunun yanıtları mevcut ActionAgent yoluna gider. Konu başlığı tek başına araştırma veya bilgisayar işlemi izni sayılmaz. Selamlaşma ve açık konu değişimi eski bekleyen araç ve tanışma sorularını bırakır; süresi bitmiş soru bayrağı uzlaştırılır. Kullanıcı metni modele aynen aktarılır. Tek düzenleme mesafesindeki yalın selamlaşma, yalnız bekleyen sorudan çıkışta tanınabilir; sabit yanıt üretilmez.

Eylem biçimleri ve konuşma sınıflandırıcısı aynı sinyali paylaşır. Birleşik uygulama/ses komutları, kaynaklı araştırma isteği ve ardından kısa konu yanıtı için tüm-plan doğrulaması korunur. Saat/tarih gibi doğrudan ölçümler korunurken selamlaşma cevap sözlüğü kaldırıldı. Mantık/analiz rolü sohbet yolu tarafından gereksiz yere silinmez. İlgili kartı bulunan yalın konu adları da zorunlu yapılandırılmış cevap üretimine alınmaz; normal sohbetin sınırlı veri bağlamını kullanabilir.

Native plan şeması, plan türünü adımlarla birlikte kısıtlayan `oneOf` dalları kullanır: `chat` ve `clarification` yalnız boş adım listesi, `action` ise 1–5 adım üretebilir. Alan boyutları plan isteminde de belirtilir. Sunucu şemayı görmezden gelse bile uygulamanın bağımsız `validate_plan` kontrolü geçerlidir. Çelişkili bir plandaki araç adımlarını sessizce silerek plan geçerli sayılmaz. Yeni araç, shell yetkisi veya güvenlik istisnası eklenmedi.

Durum sorgusunda son kod geliştirme engeli de gösterilir. Ekrandaki “Docker test imajı gerekli; testler çalıştırılmadı” kaydı ayrı bir engeldir. Bilgi kartı ve gelişim taslağı üretilebilir; test ortamı hazır olmadan kodun uygulandığı söylenemez. Paket indirmek Docker imajını kurmuş sayılmaz. Mevcut `WHISPER_GELISIM_BASLAT.cmd`, Docker Desktop Linux ortamı açıkken eksik test imajını hazırlayan ayrı akıştır; normal Whisper penceresiyle aynı anda çalıştırılmamalıdır.

## Doğrulama

- Başlangıçtaki yeni 9 test fonksiyonu, alt turlar dahil 17 başarısız doğrulama üretti. Sonradan eklenen yazım hatası/bekleyen soru, mevcut kartlı konu ve Docker engeli denetimleriyle tanışma sorusundan çıkış denetimi de eklenerek yeni test sayısı 13 oldu.
- Tam komut: `python -m unittest discover -s tests`. Sonuç: **561 test geçti, atlanan yok** (Linux/Python 3.12).
- Yeni 20 turlu açık konu senaryosu, önceki iki 20 turlu bağlam senaryosuyla birlikte korunur. Native istemcinin HTTP yükleri, konu/görev ayrımı, süre aşımı, selamlaşmayla çıkış, geçerli kısa cevap ve bozuk planın reddi denetlenir. `tests/test_dialogue.py`, `tests/test_conversation_v32.py` ve `tests/test_conversation_v3212.py` değiştirilmedi.

Bu kez gerçek yerel modeller de kullanıldı; model cevabı taklit edilmedi:

1. Mevcut Qwen2.5-0.5B modelinde üç mesaj normal sohbet yolunda ilerledi; Türkçe içerik zayıf ve bir konu açıklaması hatalı çıktı. Bu sonuç sohbet kalitesi başarısı olarak kabul edilmedi.
2. Mevcut Qwen2.5-Coder-1.5B Q4_K_M modelinde, llama.cpp CPU ve gerçek HTTP üzerinden sekiz mesajlık deneme yapıldı. Temiz, bekleyen sorulu, yazım hatalı ve süresi dolmuş durumlarda sekiz sohbet çağrısı, sıfır plan çağrısı ve sıfır araç yürütmesi görüldü. Yanıtlar hâlâ yer yer genel ifadeler içeriyor. [Gerçek deneme kaydı](evaluations/v33_3_cpu_routing.json), yönlendirme kanıtıdır; dil kalitesi veya doğruluk puanı değildir.
3. Gerçek 0.5B modeline yeni plan şemasıyla yapılan ayrı JSON denemesinde `kind=chat`, `steps=[]` çıktı; meta alanlar ve bütün plan uygulama doğrulamasından geçti. Bu, her modelin her araç isteğini doğru yorumlayacağı anlamına gelmez.

Kullanıcının Windows, Ollama ve Qwen3:8B birleşimi bu bulutta çalıştırılmadı. Native Ollama taşıması otomatik testlerde taklit HTTP ile, gerçek model denemesi OpenAI uyumlu llama.cpp üzerinden sınandı. İptal/arka plan önceliğinin V33.2 sınırları sürer. Serbest Türkçe eylem tespiti hâlâ örüntülere dayanır; her ifadenin niyetini doğru anlama garantisi yoktur.

Gerçek denemeyi yinelemek için `scripts/evaluate_dialogue.py` vardır. Mevcut yerel modele bağlanır; model indirmez, servis başlatmaz, kişisel veritabanını kullanmaz. Geçici hafıza ve çalıştırmayı reddeden araç yürütücüsü kullanır. Örnek: `python scripts/evaluate_dialogue.py --backend ollama --model qwen3:8b`. Çıktıdaki `routing_passed`, doğal Türkçe kalitesinin başarılı olduğu anlamına gelmez; `quality_scored` bilerek `false` kalır.
