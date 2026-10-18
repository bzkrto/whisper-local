# Whisper Astra — Codex geliştirme talimatları

Bu depo Whisper Astra V32.13 sürümüdür. Ana dalı doğrudan değiştirme; **codex/dialogue-context-v33** dalında ilerle. Önce mevcut kodu ve testleri incele, çalışmayan davranışı kanıtlayan test yaz, ardından en küçük güvenli düzeltmeyi uygula.

## Öncelik 1: Doğal Türkçe diyalog ve gerçek bağlam

- Kullanıcı "Ne yapıyorsun?", "Biraz önce ne konuşuyorduk?", "Onu kastetmedim", "Biraz açar mısın?" gibi serbest ifadeler kurduğunda sohbet doğal ilerlesin. Kelime kalıbına göre hazır cevap verme. Mevcut `whisper/core/reasoning.py::conversational_turn` yalnızca dar bir ifade kümesini tanıyor: gerçek bir çok-turlu diyalog için sınıflandırmayı, güvenli araç yönlendirmeyi bozmadan yeniden değerlendir.
- `whisper_ses_v12.py` içindeki Ollama/model istemcisini, sohbet isteği oluşturmayı ve `WhisperBrain.process_command` akışını denetle. Önceki sürümlerde konuşma geçmişi düzleştirilerek sistem istemine ekleniyor ve Ollama'ya yalnızca system+user gönderiliyordu. **Bu sorunun V32.13'te halen var olup olmadığını koddan doğrula**; varsa uygun geçmişi gerçek `user`/`assistant` rolleriyle aktar. Sistem talimatı ve araç çıktısını ayrı tut. Mevcut istemci arayüzü ve testleri bozmadan geriye dönük uyumluluk sağla.
- Oturumdaki son konuşma turları için açık, yapılandırılmış ve token-sınırlı pencere oluştur. Çeşitli kullanıcı niyetlerini, önemli isimleri ve kısa takip sorularını koru. Kalıcı hafıza sadece ilgili bilgi gerektiğinde gelsin; hassas verileri gelişi güzel modele taşıma.
- Kullanıcı bir araç eylemi isterse mevcut `ActionAgent`, doğrulama ve izin akışı geçerli olsun; konuşma sınıflandırıcısı araca gitmesi gereken birleşik komutları yutmasın.
- Kullanıcı Türkçe, kısa ve gündelik sorular sorabilir. Yapay "efendim" kalıplarını zorunlu kılma; sistemin kullanıcı tercihlerini uygulamasını sağla.

## Öncelik 2: Ölçülebilir değerlendirme

- Mevcut `tests/test_dialogue.py`, `tests/test_conversation_v32.py`, `tests/test_conversation_v3212.py` testlerini koru.
- Çevrimdışı ve deterministik en az 15-20 turlu bir konuşma testi yaz: konu takibi, zamir çözümleme, düzeltme, söz kesme/iptal, komut+sohbet ayrımı. Mock modelden son mesaj dizisini doğrula; yalnızca kural bazlı cümle testleri yeterli değil.
- `python -m unittest discover -s tests` testlerini çalıştır (gerekli bağımlılıklar yoksa hangilerinin atlandığını açık yaz). Gerçek Windows ses ve GPU testleri yapılmadıysa yapıldı deme.

## Sonraki aşamalar — önce mimari plan, onay almadan riskli canlı işleme geçme

1. Geliştirme ajanı: görevi planla -> yerel kod modeli -> ayrı çalışma ağacı -> ağsız Docker testleri -> insan onayı -> Git commit/PR -> geri alma; hiçbir zaman belirsiz model çıktısını doğrudan ana makinede çalıştırma.
2. Yetkili siber güvenlik analizi: yerel repo ve açıkça izinli laboratuvar kapsamı, bağımlılık denetimi, savunma ve bulgu raporu.
3. Bilgi toplama: kaynak ve tarih kaydı, çapraz doğrulama, bilgi kartları, halüsinasyon azaltma; internet erişimiyle kod yürütmeyi ayır.
4. Kaynakları ölçerek yöneten tek-seferde-tek-model yönlendiricisi; 8 GB VRAM ve 32 GB RAM hedefi.
5. Wake word, Türkçe STT, araya girme, 5 saniye sessizlikten sonra oturum kapatma, doğal TTS; bunları ayrıca Windows üzerinde dene.
6. Android istemci: güvenli eşleştirme/kimlik doğrulama, ağ erişimi ve masaüstü bağlantısı; PC kapalıyken bulut kullanımı ayrı karar.

Her PR'da: hata veya gereksinim -> uygulanan değişiklik -> test kanıtı -> bilinen sınırlar. `README.md` ve sürüm notlarını sadece doğrulanmış gelişmeler için güncelle. Şifre, token, .env, kişisel DB, ses profili, model ağırlığı veya makineye özgü dosyaları commit etme.
