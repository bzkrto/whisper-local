# Whisper Astra — V33.1 araştırma ve çekirdek geliştirme

Yerel Ollama modeliyle Türkçe sesli/yazılı asistan, kaynaklı hafıza ve test edilen otomatik kod geliştirme.

- [V33.1 yazılı kullanım ve araştırma odağı](V33_1_ARASTIRMA_VE_CEKIRDEK.md)
- [V33 diyalog ve bağlam değişiklikleri](V33_DIYALOG_VE_BAGLAM.md)
- [V32.13 Windows güncellemesi ve sürüm notları](https://github.com/bzkrto/whisper-local/releases/tag/v32.13-astra)
- [Başlatma adımları](BASLATMA.txt)
- [Kurulum](WHISPER_KURULUM.md)
- [Araştırma ve otomatik kod geliştirme rehberi](V32_13_GELISIM_REHBERI.md)
- [Mimari ve sürüm geçmişi](V32_MIMARI_VE_KURULUM.md)

## Kullanım

Normal kullanım `WHISPER_BASLAT.cmd` ile yazılı sohbet arayüzünü açar. Mikrofon, STT ve TTS modeli yüklenmez. Sesli geliştirme askıdadır.
Geliştirme için normal Whisper penceresini kapatın; Docker Desktop (Linux konteynerleri) ve Ollama açıkken `WHISPER_GELISIM_BASLAT.cmd` çalıştırın. Eski/eksik Docker test imajı ilk çalıştırmada internetten hazırlanır.

Geliştirme modu ses/STT yüklemeden tek kurulu yerel modelle çalışır. Siber güvenlik kaynaklarını önceliklendirir; kaynaklı taslağı ayrı kopyada oluşturur, Docker testleri geçerse yedekli uygular ve yeni süreçle devam eder. Gerçek ilerleme `WHISPER_GELISIM_RAPORU.json` dosyasına yazılır. Kaynak hafızası ve uygulama kodu gelişir; model ağırlıkları eğitilmez.

## Doğrulama

V33.1 için `python -m unittest discover -s tests` ile 535 test geçti; atlanan test yok. V33'ün iki ayrı 20 turlu konuşma testi korunur. Ek testler; 500'den büyük kaynak birikiminde konu seçimini, eski kartların taslak kuyruğuna geçişini, mantıksal araştırma sırasını ve ses yüklemeyen yazılı başlatıcıyı denetler. Model yanıtları taklittir; gerçek modelin mantıksal başarı oranı ve Windows arayüzü bu çalışmada ölçülmedi.

V32.13 tabanında 510 test ayrıca ağsız Docker ortamında geçmişti. V33 için Docker testi bu çalışmada tekrarlanmadı.

Veritabanları, mikrofon/ses profilleri, kişisel kayıtlar, API anahtarları, model ağırlıkları ve sanal ortamlar kaynak dağıtımına dahil değildir. Bunlar mevcut bilgisayarda korunmalıdır. Model/yazılım lisansları ilgili paket belgelerindedir.
