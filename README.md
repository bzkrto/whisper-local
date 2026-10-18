# Whisper Astra — V32.13

Yerel Ollama modeliyle Türkçe sesli/yazılı asistan, kaynaklı hafıza ve test edilen otomatik kod geliştirme.

- [Windows güncellemesi ve sürüm notları](https://github.com/bzkrto/whisper-local/releases/tag/v32.13-astra)
- [Başlatma adımları](BASLATMA.txt)
- [Kurulum](WHISPER_KURULUM.md)
- [Araştırma ve otomatik kod geliştirme rehberi](V32_13_GELISIM_REHBERI.md)
- [Mimari ve sürüm geçmişi](V32_MIMARI_VE_KURULUM.md)

## Kullanım

Mevcut kurulumda normal kullanım `WHISPER_BASLAT.cmd` ile açılır.
Geliştirme için normal Whisper penceresini kapatın; Docker Desktop (Linux konteynerleri) ve Ollama açıkken `WHISPER_GELISIM_BASLAT.cmd` çalıştırın. Eski/eksik Docker test imajı ilk çalıştırmada internetten hazırlanır.

Geliştirme modu ses/STT yüklemeden tek kurulu yerel modelle çalışır. Siber güvenlik kaynaklarını önceliklendirir; kaynaklı taslağı ayrı kopyada oluşturur, Docker testleri geçerse yedekli uygular ve yeni süreçle devam eder. Gerçek ilerleme `WHISPER_GELISIM_RAPORU.json` dosyasına yazılır. Kaynak hafızası ve uygulama kodu gelişir; model ağırlıkları eğitilmez.

## Doğrulama

510 test normal Python ortamında ve ağsız, salt okunur, ayrı kullanıcıyla 2 CPU/2 GB RAM altında çalışan Docker konteynerinde geçti. Küçük ayrı projede gerçek yerel kod modeliyle taslak, test ve yedekli uygulama doğrulandı. Windows/GPU hızı bu CPU bulutunda ölçülmedi.

Veritabanları, mikrofon/ses profilleri, kişisel kayıtlar, API anahtarları, model ağırlıkları ve sanal ortamlar kaynak dağıtımına dahil değildir. Bunlar mevcut bilgisayarda korunmalıdır. Model/yazılım lisansları ilgili paket belgelerindedir.
