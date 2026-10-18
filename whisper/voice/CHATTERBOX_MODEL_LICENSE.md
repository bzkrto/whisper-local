# Seçilen ücretsiz Chatterbox V3 sesi

Yazılım: https://github.com/resemble-ai/chatterbox
Sabit yazılım sürümü: 5de7a54aa4e5e2baadb0182dde554908b48b85c2 (0.1.7).
V32.11 yerel paket sürümü: 0.1.7+whisper.torch28. Yalnız pyproject.toml içindeki
Torch/torchaudio 2.6 sabitlemeleri 2.8 olarak uyarlanır; model kaynak kodu değiştirilmez.
Kurulum bağımlılık tutarlılığı pip check ile denetlenir.
Yazılım lisansı: MIT; lisans metni kurulan dağıtımda bulunur.
Model: https://huggingface.co/ResembleAI/chatterbox
Sabit model sürümü: 5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18.
Model kartında belirtilen lisans: MIT.

Türkçe dil kimliği tr; Chatterbox Multilingual V3, 500 milyon parametre.
Beğenilen örnekle aynı ayarlar: exaggeration 0.35, cfg_weight 0.5, temperature 0.65.
Modelin yerel Perth filigran işlemi korunur.

Kullanıcının seçtiği referans kayıt yalnız kendi bilgisayarında tutulur; güncelleme
paketinde, GitHub kaynaklarında veya model indirme isteğinde gönderilmez.
Model ve paketlerin ilk indirmesi internet gerektirir; ses üretimi yereldir.
ElevenLabs veya başka ücretli ses API'si kullanılmaz.

Windows başlatıcısı tek bir kod ortamını değiştirmek yerine ayrı bir ses ortamı
kurar. Ağırlıklar, tokenizer verileri ve sabit yazılım arşivi SHA256 ile doğrulanır.
Bağımlılıkların kendi lisansları kurulan paketlerle birlikte geçerlidir.
