# Whisper V32 — sohbet ve test edilen otomatik kod geliştirme

Güncel varsayılan ses V32.13'te kullanıcının beğendiği Chatterbox Multilingual V3 referans sesidir. Hızlı kurulum BASLATMA.txt dosyasında; aşağıdaki sürüm notları önceki denemeleri de içerir.

Bu sürüm yüklenen V31 dosyaları üzerine geliştirilmiştir. Whisper_OS_Mimari_Tasarim.pdf bir vizyon belgesidir; aşağıdaki tablo uygulanan parçaları ve gelecekte yapılacak işleri ayırır.

| Mimari parçası | V32'deki karşılığı |
| --- | --- |
| Core Brain / doğal sohbet | Aynı komut işleyicisi ses ve yazıyı karşılar; son sekiz konuşma turu bağlama girer. GUI'de Sohbet ve İşlem günlüğü ayrı sekmelerdir. |
| AI Router | chat, code, reason, vision ve fast rolleri; kurulu Ollama modelleri ve ayrı rol sunucuları. PDF'deki DeepSeek/Gemma adları zorunlu değildir. |
| Kalıcı hafıza | Kullanıcı beyanları, geçmiş konuşma, belge/kaynak kayıtları, deneyimler ve kaynaklı bilgi kartları. Gerçek anlamsal embedding veya bilgi grafiği bu güncellemede eklenmedi. |
| Learning / kod geliştirme | Kaynaklı gelişim taslağı veya açık kullanıcı hedefi -> ayrı kod taslağı -> Docker testleri -> yedekli kaynak ve sürüm bildirimi güncellemesi. |
| Ses / Türkçe | Chatterbox V3 ile seçilen ücretsiz referans ses; yerel Whisper; kalıcı kullanıcı terim sözlüğü; bağlamdaki tek kelimelik yanıtlar korunur. |
| Computer Control | Mevcut izinli araçlar, uygulama envanteri, ekran ve dosya işlemleri korunur. |
| Rapor / sunum / video | Mevcut Word/PDF/PowerPoint ve senaryo akışı korunur. Otomatik video render eklenmedi. |
| Security / Behavior / Order | Mevcut araç doğrulama ve hatırlatmalar korunur. Antivirüs, hesap güvenliği denetimi, alışkanlık çıkarımı veya satın alma ajanı eklenmedi. |

## Bilgisayarda kurulum

1. Whisper'ı kapatın. Mevcut whisper astra klasörünün yedeğini alın.
2. WHISPER_V32_GUNCELLEME.zip içeriğini mevcut proje klasörüne çıkarın; aynı adlı kod dosyalarını güncelleyin.
3. Paket kişisel veritabanını, mikrofon profilini, ses referanslarını, .venv ortamını veya modelleri içermez; bunları koruyun.
4. Ollama'yı açın. Mevcut qwen3:8b sohbet ve qwen2.5-coder:7b kod modeli kullanılır. Görsel model yalnız ekran isteğinde gereklidir.
5. Kod geliştirmede kullanılacak test imajını WHISPER_TEST_ORTAMI.cmd ile hazırlayın. Docker Desktop açık olmalıdır. İmaj hazırlanmamışsa kod güncellemesi uygulanmaz; durum günlüğünde görünür.
6. WHISPER_KONTROL.cmd ile paket kontrolünü, WHISPER_BASLAT.cmd ile uygulamayı açın.

## Karşılıklı konuşma

İlk komutta “Hey Whisper” deyin. Yanıt tamamlandıktan sonraki 20 saniye boyunca tekrar seslenmeden konuşabilirsiniz. Modelin yanıt üretme ve seslendirme süresi bu pencereyi tüketmez. “Sohbeti bitir”, “Dinlemeyi bitir” veya “Şimdilik bu kadar” bu pencereyi kapatır. “Dur / sus” yanıtı keser; “çıkış” uygulamayı kapatır.

İsterseniz CLI'de --single-turn ile her komut için tekrar seslenme davranışını seçebilirsiniz. --conversation-timeout 5–120 saniye aralığında ayarlanabilir. Mikrofon düğmesi ses girişini kapatır.

Genel bilgi soruları, “nedir / kaç” sözcükleri yüzünden internet kapalıyken engellenmez. Güncel fiyat/haber/hava gibi gerçekten dış kaynağa ihtiyaç duyan sorularda mevcut doğrulama akışı korunur. Kısa isim/uygulama yanıtları bir açıklama sorusuna cevap olduğunda rastgele kelime sayılıp atılmaz.

## Ses ve kelimeler

Windows başlatıcısı artık Microsoft EmelNeural ve normal hız kullanır. Önceki başlatıcıdaki AhmetNeural de Microsoft hizmetiydi; Google TTS kullanılmıyordu. İlk V32 açılışı yeni tercihi kaydeder; sonraki kullanıcı seçimleri korunur. “Ahmet sesini kullan”, “Emel sesini kullan”, “Normal hızda konuş” gibi komutlar kullanılabilir.

“Kelime öğret: Bergen” veya “Kelime öğret: bütçe raporu” terimi yerel ses sözlüğüne kaydeder. “Ses sözlüğü” kayıtları gösterir. Bu terimler sonraki Whisper tanımalarında ipucu olur; duyulmayan bir cümle yerine komut yazılmaz ve model ağırlıkları eğitilmez.

Edge hizmeti erişilemezse yalnız kurulu Türkçe Windows sesi yedek olarak kullanılır. Türkçe yerel ses yoksa İngilizce bir sesle yanlış telaffuz edilmez; metin yanıtı korunur. Windows oynatma ve fiziksel mikrofon/GPU doğruluğu bilgisayarınızda ayrıca kontrol edilmelidir.

## Kendi kodunu geliştirme

- “Kendini geliştir: Türkçe kısa yanıtların önceki soruya bağlanmasını iyileştir” açık bir geliştirme hedefi ekler.
- “Gelişim durumu” veya “Otomatik gelişim durumu” aşamaları gösterir.
- “Otomatik gelişimi durdur / başlat” kalıcı anahtarı değiştirir.
- Kaynaklı bilgi kartlarından üretilen gelişim hedefleri de otomatik sıraya alınır.

Program açıkken zamanlayıcı boşta, tek bir hedef üzerinde çalışır. Her hedef en fazla üç kod denemesi yapar; sonraki denemeye önceki test hatası veri olarak eklenir. İşlem aralığı en az on dakikadır. Öndeki kullanıcı komutu için ayrılan kilit ve iptal denetimleri korunur.

Her taslak en fazla iki küçük mevcut Python modülünü değiştirir; güncelleyici, izin kontrolleri, testler ve bağımlılıklar model tarafından değiştirilmez. Kod, ağ ve kişisel veriler bulunmayan, kaynak kopyası salt okunur Docker ortamında test edilir. Sıfır test çalışması başarı kabul edilmez. Başarısız veya iptal edilen taslak canlı koda yazılmaz. Test edilen içerik veya canlı kaynak arada değişirse uygulama durdurulur.

Başarılı güncellemede değişen dosyalar ve WHISPER_SURUM.json yedeklenir; dosyalar geçici dosya üzerinden değiştirilir, sürüm bildirimi en son yazılır. Normal yazma hatasında değişen dosyalar geri alınır. Güncelleme kilidi sırasında ikinci güncelleme ve yeni bootstrap açılışı engellenir. Güncellenen kod bir sonraki uygulama açılışında etkinleşir; mevcut Python nesneleri kendiliğinden yeniden yüklenmiş sayılmaz.

Yedekler veritabanı klasöründeki iyilestirme_taslaklari/<taslak>/backup dizinindedir. Süreç veya bilgisayar güncellemenin ortasında zorla kapanırsa kilit kalabilir: işlem artık çalışmıyorsa bu dizindeki yedekleri proje klasörüne geri koyup .whisper-update.lock dosyasını kaldırın. Başlatıcı bütünlük bozukken çalışmayı reddeder.

Bu akış kodu değiştirebilir; her değişikliğin yararlı olduğunu veya genel zekâyı artırdığını garanti etmez. Test kapsamı ve seçilen kod modelinin kalitesi belirleyicidir. Buluttaki küçük kod modeli Türkçe harf düzeltmesinde başarısız taslaklar üretti; testler bunların uygulanmasını engelledi. Model ağırlıkları eğitilmez.

## Bulut doğrulaması

Tüm otomatik testler son doğrulamada ayrıca raporlanır. Gerçek Microsoft Emel sesiyle MP3 üretildi; bu bilinen kısa örnek, gerçek CPU faster-whisper ile sıfır kelime hatasıyla tanındı. Bu ölçüm mikrofonunuzun doğruluk oranı değildir.

Bulut geliştirme için ayrı Qwen sohbet ve Qwen2.5-Coder CPU sunucuları, yerel faster-whisper-small ve izole Docker test imajı hazırlandı. Windows'taki qwen3:8b/qwen2.5-coder:7b modellerinin kalitesi ve GPU performansı bu kontrolün sonucu olarak gösterilmez.

## V32.1 tok erkek ses profili

Kullanıcı isteğiyle varsayılan ses Türkçe destekleyen Microsoft BrianMultilingualNeural erkek sesi olarak değiştirildi. Hız ve ton normaldir (+0%, +0Hz); sesin kendi doğal erkek tınısı kullanılır. İlk V32.1 açılışı bu profili kaydeder, sonraki kullanıcı tercihleri korunur. “Brian sesini kullan” veya “Erkek sesini kullan” bu sesi seçer. “Ahmet sesini kullan” ve “Emel sesini kullan” önceki seçeneklere döner. CLI --voice, --rate ve --pitch açıkça verilirse kayıtlı ayarı geçersiz kılar; ton tercihi de artık kalıcıdır.

Bu güncelleme aynı Microsoft Edge ses hizmetini kullanır; ücretli sağlayıcı veya ses klonlama eklenmemiştir. BrianMultilingualNeural adındaki en-US, ses kimliğinin adıdır; model Türkçe konuşabilir. Türkçe örnek çevrimiçi hizmetle gerçekten üretildi. Ahmet için denenen negatif hız/ton ayarlarında bu ortamda ses alınamadığından bunlar varsayılan yapılmadı. Tokluk ve aksan beğenisi kullanıcı tarafından örnek dinlenerek değerlendirilmelidir.

## V32.2 öğrenme durumu ve arama düzeltmesi

“Bugün neler öğrendin?” artık kısa bir günlük durum verir: bugün okunan kaynaklar ve bugün işlenen belge bölümleri ayrı sayılır. Eski kaynaktan bugün üretilen bilgi kartları günlük işleme sayısına dahildir. Bekleyen ve hatalı bölümler ayrı gösterilir; en fazla iki kısa kaynak özeti verilir. “Öğrenme günlüğü” ayrıntılı raporu korur. Biriken bölümler yüzünden yeni belge okuma bekletiliyorsa bunun nedeni açıkça yazılır.

Ekranda görülen “Bugün neler ağlandı?” ifadesi sessizce düzeltilmez: öğrenme sorusu olup olmadığı sorulur; “Evet” yanıtı günlük özeti açar. Başka bir komut bu bekleyen soruyu kapatır. Bu değişiklik akustik modeli eğitmez. Tanımaya öğrenme/araştırma kelime ipuçları eklendi.

Web araması Bing ve DuckDuckGo sağlayıcılarını sınırlı denemelerle kullanır. Bir sağlayıcı hata verirse diğeri denenir. Cloudflare bağlantı denemesi aramanın ön koşulu olmaktan çıkarıldı; Cloudflare erişilemese bile arama denenir. Her iki sağlayıcı da sonuç vermezse doğrulanmış bilgi uydurulmaz. Sağlayıcı hataları durum günlüğünde ayrılır. Ağ engeli, hizmet kesintisi veya Windows bağlantı sorunu bu değişiklikle otomatik olarak giderilmiş sayılmaz.

## V32.3: tekrarlayan hataların nedenleri

Önceki düzeltme yalnız bir yanlış tanınan cümleyi ele alıyordu. Bu sürüm öğrenme sorularını merkezi niyet sınıflandırıcısında tanır: “Bugün neler öğrendin”, “Bugün bana ne öğrendiğini anlat”, “Bugünkü öğrenmelerini özetle” ve benzeri iç raporlar web aramasına gitmez. “Bugün neler öğrendim” gibi kişi eki belirsizliği için onay istenir; “Evet” asistanın özetini açar. “Ben bugün ne öğrendim” sessizce asistanın öğrenmesine dönüştürülmez. Açık internet/haber/araştırma istekleri dış kaynak akışını korur.

Başlatıcı varsayılanı artık **yerel Piper Türkçe sesi**. İlk Windows açılışında eksikse piper-tts 1.8.0 kurulur, sabit kaynak sürümünden 63 MB Türkçe model ve yapılandırması indirilir; SHA256 ve boyut doğrulanır. Sonraki açılışlarda doğrulanmış yerel dosyalar kullanılır; ses üretimi çevrimiçi servise veya Windows Türkçe ses paketine bağlı değildir. Bu seçim Brian ile aynı tınıyı vaat etmez: farklı bir yerel sentetik sestir. Örnek dinlenerek değerlendirilmelidir. Piper sesi için lisans ve kaynak bilgisi whisper/voice/PIPER_MODEL_LICENSE.md dosyasındadır.

Önceki çevrimiçi Brian profili korunur ancak varsayılan başlatıcı onu kullanmaz. İsteğe bağlı --tts edge --allow-cloud çevrimiçi hizmeti seçer; hizmetin 403 yanıtını kodla ortadan kaldırma garantisi verilmez. Yerel ses modunda Brian/Emel değiştirme komutları başarılı olmuş gibi gösterilmez. Konuşmayı durdurma yerel sesin sonraki oynatma bloğunda uygulanır; geçici ses dosyası temizlenir.

Yapılandırılmış model çağrısında şemanın metin uzunlukları artık modele açıkça iletilir. Hata bildirimi alan yolunu, gelen uzunluğu ve beklenen aralığı söyler; bir düzeltme denemesinde geçersiz önceki çıktı veri olarak sunulur. Kabul testinde “0 -> 1” gibi kısa ve anlamlı değerler geçerlidir; boş değer, yanlış tür, eksik alan ve üst sınır ihlali hâlâ reddedilir. Aynı kaynak için gelişim taslağı üç analiz turunda üretilemezse kalıcı olarak durdurulur; modelin hatalı çıktısı canlı koda uygulanmaz. Bu, her yerel modelin mutlaka geçerli veya yararlı taslak üreteceğini garanti etmez.

Kurulum: Whisper’ı kapatın, klasörünü yedekleyin, V32.3 ZIP’in tamamını mevcut klasörün üzerine çıkarın ve WHISPER_BASLAT.cmd dosyasını açın. İlk yerel ses kurulumu için internet gerekir; model ZIP içinde değildir. Fiziksel mikrofon, Windows ses çıkışı ve GPU uygulaması bulut testleriyle doğrulanamaz.

V32.3 doğrulama: 435 otomatik test geçti; kaynak paketi kontrolü başarılı. Yerel Piper ile gerçek WAV üretildi; indirilmiş modelde ağ isteği engellendiğinde yeniden sentez başarılı oldu. Örnek gerçek Türkçe Whisper ile tanındı; ürün adında bir tanıma farkı olduğundan sıfır kelime hatası iddiası yoktur. Gerçek küçük yerel kod modeliyle şemaya uygun gelişim taslağı alındı; bu denemede canlı kod güncellenmedi. Fiziksel Windows ses çıkışı hâlâ doğrulanmadı.

## V32.4 seçilen ElevenLabs sesi

Varsayılan Windows başlatıcı artık kullanıcı tarafından seçilen ElevenLabs sesi lSX8MEhRyl5ZEeI3jfgm ile çalışır. Resmi /v1/text-to-speech API’si, eleven_multilingual_v2 modeli, Türkçe dil seçimi ve 24 kHz PCM çıktısı kullanılır. Seslendirilmek üzere hazırlanan metin ElevenLabs’e gönderilir; kullanım hesabın kotasından düşer. API anahtarı sohbet mesajına, kaynak koda veya kişisel hafıza veritabanına yazılmaz. Windows’ta LOCALAPPDATA/WhisperAstra/elevenlabs.dpapi dosyasında mevcut kullanıcı için DPAPI ile şifrelenir. Başka bilgisayarda yeniden ayarlanması gerekir. Linux/cloud için WHISPER_ELEVENLABS_API_KEY ortam değişkeni kullanılır.

İlk açılışta anahtar yoksa gizli giriş penceresi açılır. ElevenLabs hesabınızın Developers / API Keys bölümünden Text to Speech yetkili anahtar oluşturup bu pencereye yapıştırın. Anahtarı bu sohbete göndermeyin. İptal ederseniz uygulama farklı bir sesi kullanarak başlamaz. WHISPER_ELEVENLABS_AYAR.cmd anahtarı sonradan değiştirebilir. Seçilen ses hesabınızda erişilebilir olmalıdır; gerekirse https://elevenlabs.io/voices/lSX8MEhRyl5ZEeI3jfgm bağlantısından Voice Library’ye ekleyin. Hesap planı ve ses erişim koşulları ElevenLabs tarafından belirlenir.

Başarılı ses aynı çalışma oturumunda sınırlı önbelleğe alınır; aynı metni yeniden çalmak için ikinci ücretli istek yapılmaz. Başarısız/yarım istek otomatik tekrarlanmaz; kimlik, kota veya hizmet hatasında kısa bekleme uygulanır. Başka bir sese otomatik geçilmez, metin yanıtı ekranda kalır. Ses kesilince indirme/oynatma iptal edilir; geçici WAV silinir. Piper ve Microsoft seçenekleri CLI’de ayrı seçim olarak korunur ancak varsayılan Windows başlatıcı bunları kullanmaz.

Geliştirici doğrulaması seçilen ses kimliği, Türkçe/model parametreleri, anahtar gizliliği, ses önbelleği, iptal, kota hatası ve ilk kurulum iptali akışlarını kapsar. Gerçek ElevenLabs sesi API anahtarı sağlanmadan üretilmiş veya hesapta doğrulanmış sayılmaz. Windows DPAPI ve fiziksel hoparlör bu Linux bulut ortamında doğrulanmadı.

## V32.5: yüklenen kayıtla yerel referans ses

Varsayılan Windows başlatıcı artık referans kayıtla yerel XTTS-v2 sesini seçer; ElevenLabs API anahtarı istemez. WHISPER_BASLAT.cmd ilk açılışta bilgisayarınızdaki orijinal MP3/WAV kaydını seçtirir. Ana Python ortamına Torch/TTS kurulmaz: LOCALAPPDATA/WhisperAstra/reference/venv altında ayrı bir ses ortamı hazırlanır. Model yaklaşık 1,9 GB’dır; çalışma paketleri ayrıca indirilir. Uyumlu NVIDIA sürücüsü (560+) algılanırsa CUDA 12.6 Torch paketi, aksi durumda CPU paketi kurulur. Model ağırlıkları sabit upstream sürüm ve SHA256 ile doğrulanır. Bu ilk kurulum zaman alabilir; yarım indirmede doğru tamamlanmış dosyalar korunur.

Seçtiğiniz kaydın ilk uygun konuşma bölümünden en fazla 20 saniyelik mono 24 kHz referans üretilir. Referans ve orijinal dosya yolu yalnız yerel kullanıcı klasöründe saklanır; GitHub güncelleme paketine eklenmez. WHISPER_SES_KAYDI.cmd başka bir kayıt seçtirir. Windows’ta yerel dosya seçme işlemini kullanıcı yapar; bulut masaüstünüzü doğrudan okuyamaz.

Ses modeli ayrı, kalıcı bir işçi süreçte yüklenir ve konuşmacı koşullaması bir kez hesaplanır. CUDA mevcut ve en az 2,8 GB boş GPU belleği varsa GPU denenir; bellek hatasında CPU’ya döner. Modelin/STT/LLM’nin toplam GPU kullanımı bilgisayarda ayrıca ölçülmelidir. CPU yavaş olabilir: bulut denemesinde 5,47 saniyelik sesi üretmek 51,18 saniye sürdü. Bu CPU sonucu canlı sohbet hızı değildir; GPU performansı henüz doğrulanmadı. Referans kayıt orijinal ElevenLabs modeliyle aynı kaliteyi veya birebir sesi garanti etmez.

Ses üretiminde internet/API çağrısı yapılmaz. Aynı kısa metin sınırlı RAM önbelleğinden tekrar çalınabilir. İptal sırasında üretim süreci sonlandırılır; sonraki yeni üretimde model tekrar yüklenebilir. Oynatma küçük ses bloklarında iptal edilir. Kapanışta işçi kapatılır, geçici üretilmiş WAV dosyaları temizlenir. Ayrıntılı hata günlüğü yerel reference/worker.log dosyasındadır.

ElevenLabs API seçeneği korunur: whisper_bootstrap.py --elevenlabs ile önceki API modu açılır. Varsayılan referans modunda ücretli ElevenLabs isteği yapılmaz. Model Coqui Public Model License kapsamındadır; lisans ve kaynak bilgisi XTTS_MODEL_LICENSE.txt dosyasındadır.

V32.5 doğrulama: 453 otomatik test geçti. Gerçek yüklenen MP3 kaydı SDK ortamında açılıp mono 24 kHz WAV referansa dönüştürüldü. Gerçek ayrı işçiyle 4,13 saniyelik yeni ses 30,86 saniyede üretildi; model ilk açılışı dahil toplam 71,92 saniyeydi. Aynı metnin önbellekten tekrar hazırlanması ölçümde 0,0 saniyeydi. Üretilen WAV biçimi kontrol edildi ve işçi kapanışı doğrulandı; bu denemede fiziksel oynatma çağrısı başlıksız bulut nedeniyle atlandı. Windows/GPU sonucu ve insan tarafından ses benzerliği değerlendirmesi henüz doğrulanmadı.

## V32.6: orijinal ElevenLabs sesine dönüş

Kullanıcı referans-model denemesindeki ses rengini beğenmediği için Windows başlatıcı tekrar resmi ElevenLabs API’sini varsayılan kullanır. Son seçilen ses kimliği krLzmW3By9JzaVy294Ux olarak düzeltildi. API ses ayarları: stabilite 1,0; benzerlik 1,0; hız 0,96; stil 0; speaker boost açık. API anahtarı bilgisayardaki gizli giriş penceresine yazılır; başka bir sese otomatik geçilmez. Gerçek hesap erişimi ve ses sonucu API anahtarı olmadan doğrulanmadı. Dosyadaki ElevenLabs üretimiyle birebir eşleşme, kullanılan ElevenLabs modeli ve hesap ayarlarına da bağlıdır.

Varsayılan açılış artık yerel ses modeli indirmez veya MP3 seçtirmez. Önceki yerel referans modu isteğe bağlı whisper_bootstrap.py --reference ile kullanılabilir. Bu modda düşük ses benzerliği ve CPU gecikmesi ölçülmüştür; doğal sohbet kalitesi olarak sunulmaz. ElevenLabs anahtarı yoksa Developers / API Keys bölümünden Text to Speech yetkili anahtar oluşturup uygulamanın açtığı pencereye yapıştırın. Anahtarı sohbete göndermeyin.

## V32.7: ses başlangıcında komut kilidinin takılması

“Dinliyorum” satırından sonra bip üretmek için kullanılan bloklayan PortAudio çıkışı kaldırıldı. Bu çağrı mikrofon akışı açıkken sohbet kilidini tutuyordu; Windows ses sürücüsünde çıkış beklemesi komutları sırada bırakabiliyordu. Hazır bildirimi artık yalnız ekrana yazılır. WAV sesleri Windows'ta winsound ile asenkron çalınır; süre beklemesi iptal edilebilir ve çıkış hata verdiğinde hata ses motoruna iletilir. Windows mikrofon girdisi sounddevice ile devam eder. Linux çıkış yolu korunur.

Sesli mod başlatılmadan önce arka plan LLM bilgi/profil/kod işleme ve zamanlanmış model araştırması bekletilir. Mikrofon kapanınca bu işler devam eder; başlamış bir model çağrısı zorla kesilmez. İnternetten belge toplama ve kullanıcının açık araştırma komutları korunur. Bu sürümde sürekli açık mikrofon sırasında arka plandaki model analizi ilerlemez. Komut kilidi beklemesi 10 saniyeyle sınırlıdır; süresi dolan komut sonradan kendiliğinden çalıştırılmaz.

Kurulum ve ayrıştırılmış kontrol:

1. Whisper'ı kapatın, klasörünü yedekleyin ve V32.7 ZIP'in tamamını mevcut klasörün üzerine çıkarın.
2. WHISPER_SES_TESTI.cmd dosyasını açın. Bu test mikrofon, Ollama ve arka plan öğrenmesini açmadan seçilen ElevenLabs sesiyle bir cümle üretir. ElevenLabs anahtarı ve hesapta ses erişimi gerekir; normal API kotası kullanılır. Anahtar eksikse WHISPER_ELEVENLABS_AYAR.cmd ile yerel gizli pencereye girin.
3. WHISPER_BASLAT.cmd ile açın; ilk satırda 32.7-voice-startup-fix yazdığını doğrulayın. Hâlâ 32.4 yazıyorsa güncellenmemiş başka bir klasör açılmıştır.
4. Ses testi çalışıyor ancak konuşma algılanmıyorsa WHISPER_MIKROFON_TESTI.cmd ile ekrandaki beş cümleyi okuyun. Bu mod uygulama açmaz, TTS veya arka plan model analizi çalıştırmaz; mikrofon kaydını ve tanınan metni gösterir. Sessizlikte düşük mikrofon seviyesi tek başına mikrofon arızası kanıtı değildir.

Doğrulama: 459 otomatik test geçti. Ek kontroller komut bekleme süresinin dolmasını, bekleyen kilitlerin bırakılmasını, sesli modda arka plan modelinin başlamamasını, cihaz hatasında modun kapanmasını ve Windows asenkron oynatma/iptal/hata akışını kapsar. Windows API çağrıları taklit edilerek test edildi; gerçek Windows hoparlörü/mikrofonu ve kullanıcının ElevenLabs hesabı bu bulut ortamında doğrulanmadı.

## V32.8: ElevenLabs HTTP 400 ret nedenini gösterme

Yeni kullanıcı çıktısında konuşma kaydı ve tanıma tamamlandı, ElevenLabs ise HTTP 400 döndürdü. Bu durum ses oynatılmadan önce oluşur; mikrofon veya hoparlör arızası kanıtı değildir. Önceki sürüm servis açıklamasını gizlediği için gerçek ret nedeni bilinmiyordu. Sürüm 32.8 HTTP koduyla birlikte sağlayıcının hata kodunu ve kısa açıklamasını gösterir. Ücretli plan, kota, ses erişimi ve izin hataları ayrı açıklanır; HTTP 400 tek başına ücretli plan gerektiği şeklinde yorumlanmaz. Alan doğrulama hatalarında yalnız alan adı ve hata türü gösterilir. Bilinen API anahtarı ve sk_ biçimli değerler gizlenir; ham yanıt/istek gövdesi veya anahtar dosyası günlüğe dökülmez. Otomatik tekrar veya başka sese geçiş yapılmaz.

Bu değişiklik hesap planını veya ses erişimini değiştirmez, başarılı canlı sentez olarak sunulmaz. ZIP'i mevcut klasöre çıkardıktan sonra WHISPER_SES_TESTI.cmd çalıştırılmalı ve hata sürüyorsa HTTP kodu, hata kodu ve ElevenLabs açıklaması birlikte incelenmelidir. Ses sağlayıcı açıklamasında ücretli plan gerektiği açıkça belirtilmedikçe satın alma önerilmez. Anahtar değişikliği gerekiyorsa yalnız WHISPER_ELEVENLABS_AYAR.cmd gizli giriş penceresi kullanılır. Kullanıcı anahtarını sohbete göndermez.

CPU üzerinde geciken tanıma artık GPU güç sorunu olarak yazılmaz; CPU/GPU durumuna uygun bilgi verilir. Bu tanıma gecikmesi ile ElevenLabs HTTP 400 ayrı aşamalardır. 463 otomatik test geçti; gerçek hesap erişimi ve fiziksel Windows ses sonucu doğrulanmadı.

## V32.9: ücretsiz yerel Türkçe sese geçiş

Kullanıcı ücretli ses istemediği için WHISPER_BASLAT.cmd ve WHISPER_SES_TESTI.cmd artık Piper Fettah Türkçe profilini kullanır. Önceki beğenilmeyen DFKI ve XTTS referans profillerinden farklı bir modeldir. API anahtarı, abonelik veya seslendirme kotası gerekmez. Kaydedilmiş ElevenLabs anahtarı normal açılışta okunmaz. Ücretli seçenek yalnız açık whisper_bootstrap.py --elevenlabs isteğiyle kullanılabilir; otomatik geçiş yoktur. Varsayılan model çağrılarında --allow-cloud da kaldırılmıştır; yerel Ollama ve mevcut internet araştırması korunur.

İlk kullanımda eksikse piper-tts==1.8.0 ve yaklaşık 63 MB model indirilir. Model ve yapılandırma sabit upstream sürümden SHA256 kontrolüyle alınır. Sonraki ses üretimi internet istemez; eski ses dosyaları silinmez ve seçilmez. Modelin veri lisansı CC0, Piper yazılımı GPL-3.0; kaynaklar whisper/voice/PIPER_MODEL_LICENSE.md içindedir. Bu bir ElevenLabs ses klonu değildir; aynı tını ve kalite vaat edilmez. Üretilen örnekte otomatik tanıma Türkçe cümleleri büyük ölçüde geri okudu, Whisper özel adında hata yaptı. Sesin doğallığı dinleyerek değerlendirilmelidir.

Kurulum: Whisper'ı kapatın, klasörü yedekleyin, V32.9 ZIP'in tamamını mevcut klasöre çıkarın. Önce WHISPER_SES_TESTI.cmd dosyasını açın; ilk model indirmesinin bitmesini bekleyin. Bu test LLM, mikrofon ve öğrenme işçilerini açmadan ücretsiz sesi dener. Ardından WHISPER_BASLAT.cmd ile başlatın; ilk satırda 32.9-free-local-turkish-voice, motor satırında Piper Fettah görülmelidir. ElevenLabs anahtar ayarını açmanız gerekmez.

Doğrulama: 466 otomatik test geçti. Normal Windows başlatıcısının kaydedilmiş ücretli anahtarı okumadığı, piper eksikse kurduğu ve kurulum başarısızsa durduğu, ayrı ses testinin beyin/mikrofon başlatmadığı kontrol edildi. Upstream dosya kimlikleri doğrulandı. Gerçek model ile yaklaşık 9,85 saniyelik örnek 1,05 saniyede üretildi; model yükleme ayrıca 2,37 saniye sürdü. Ürün adaptöründe ağ GET/POST çağrıları engelliyken 2,66 saniyelik ses 0,234 saniyede üretildi; fiziksel oynatma bulutta atlandı. Bunlar bulut CPU ölçümleridir, kullanıcı bilgisayarı için hız garantisi değildir. Windows asenkron oynatma yolu V32.7'den korunur; fiziksel mikrofon/hoparlör kullanıcı bilgisayarında denenmelidir.

## V32.10: beğenilen Chatterbox V3 referans sesi

Normal Windows başlatıcı ve WHISPER_SES_TESTI.cmd artık kullanıcının beğendiği örnekle aynı Chatterbox Multilingual V3 modelini kullanır. Ayarlar exaggeration 0,35, cfg_weight 0,5, temperature 0,65 ve Türkçe dil kimliği tr olarak sabittir. Model ve yazılım sürümü ile kaynak arşivi SHA256 değeri sabittir. Model, tokenizer verileri ve referans bütünlüğü işçi açılmadan kontrol edilir. Ücretli API çağrısı, anahtar okuma veya başka sese otomatik geçiş yoktur.

Kurulum ana Whisper ortamını değiştirmez; Python 3.10–3.12 üzerinde LOCALAPPDATA/WhisperAstra/chatterbox-v3/venv altında ayrı Torch 2.6.0 ortamı kurulur. Uygun NVIDIA sürücüsü algılanırsa CUDA 12.6 paketi seçilir, aksi durumda CPU paketi kullanılır. İlk indirme yaklaşık 3,2 GB model, 35 MB tokenizer verisi ve ek çalışma paketleridir. Önceki referans kaydı bulunursa kullanılır; bulunamazsa orijinal MP3/WAV seçilir. İlk uygun konuşmadan en fazla 14 saniyelik mono 24 kHz kayıt yalnız kullanıcı bilgisayarında saklanır. Kayıt, kaynak yolu, API anahtarı ve model ağırlıkları ZIP'e eklenmez.

Model korunan ayrı süreçte kalıcı yüklenir ve referans koşullaması bir kez hesaplanır. Ana uygulama Torch/Chatterbox import etmez. Mikrofon hazır bildirimi öncesinde ses modeli hazırlanır; dosya kontrolü, cihaz seçimi, model yükleme ve kayıt hazırlama aşamaları ekranda görünür. Otomatik CUDA seçimi için o anda en az 6144 MB boş GPU belleği gerekir; bu eşik toplam kart belleği değildir, Ollama/STT kullanımı da hesaba girer. CUDA bellek veya destek hatasında aynı ses CPU üzerinde denenir; farklı ses kullanılmaz. Gerçek Windows/CUDA sonucu bu CPU bulutunda doğrulanmadı.

Aynı oturumda en fazla 16 kısa yanıt toplam 8 MB RAM sınırıyla önbelleğe alınır. Önbellek, motoru ve referansı sabit olan tek işçiye aittir; program kapanınca silinir. İptal, üreten işçiyi sonlandırır; sonraki yeni üretimde model yeniden yüklenebilir. Oynatma iptali Windows asenkron WAV yolunda korunur. Geçici çıktı dosyaları iş bitince/kapanınca temizlenir. Hata günlüğü yerel worker.log dosyasındadır.

Kurulum: Whisper'ı kapatın, klasörü yedekleyin, ZIP'in tamamını aynı klasöre çıkarın. WHISPER_SES_TESTI.cmd ile ilk kurulumu/ses denemesini tamamlayın; kayıt seçme penceresi açılırsa orijinal ElevenLabs MP3'ünü seçin. Ardından WHISPER_BASLAT.cmd açın. İlk satırda 32.10-approved-chatterbox-v3 ve motor satırında Chatterbox V3 görünmeli. Sonradan kayıt değiştirmek için WHISPER_SES_KAYDI.cmd, model/dependency kontrolünü yeniden yapmak için WHISPER_SES_ONAR.cmd kullanılır; ikisi de Whisper kapalıyken çalıştırılmalıdır. Onarım, doğru tamamlanmış model indirmelerini korur ve bozuk dosyaları tekrar indirir; eski Edge/SAPI paketlerini güncellemez.

478 otomatik test geçti. Gerçek kurulum hazırlığı önbellekteki doğrulanmış dosyalarla ve HTTP GET engelliyken tamamlandı. Ürün adaptörü gerçek ayrı işçiyle 3,96 saniyelik Türkçe ses üretti; otomatik tanıma “Merhaba Osman seni dinliyorum. Bugün birlikte ne yapıyoruz?” metnini geri okudu. Bulut CPU ölçümünde model/referans açılışı 56,39 saniye, yeni ses üretimi 47,53 saniye, aynı metnin önbellekten hazırlanması 0,001 saniyeydi; son ölçüm ses çalma süresini içermez. Yeni üretimde gerçek süreç iptali 0,165 saniyede tamamlandı. Ana işlemde Torch import edilmedi ve geçici WAV temizlendi. Fiziksel oynatma testte atlandı; Windows hoparlörü ve GPU hızı kullanıcı bilgisayarında ayrıca denenmelidir. Bu CPU süresi canlı sohbet hızı olarak sunulmaz. Lisans ve kaynaklar whisper/voice/CHATTERBOX_MODEL_LICENSE.md dosyasındadır.

## V32.11 — RTX 50 CUDA uyumluluğu ve GPU belleği

Gönderilen günlükte ses için 7013 MB boş VRAM ile CUDA seçildiği halde model CPU'ya düşüyordu.
Önceki Torch 2.6 / CUDA 12.6 paketi RTX 5070 mimarisine uygun değildi. Ayrı ses ortamı artık
Torch/torchaudio 2.8.0 kullanır; NVIDIA sürücüsü 570 ve üzerindeyse CUDA 12.8 paketi seçilir.
Tam paket varyantı sabitlenir: önceden kurulu CPU paketi CUDA yükseltmesini atlatamaz.
Model ağırlıkları ve referans korunur, geçerli model önbelleği yeniden indirilmez.

Normal başlatıcıda --voice-gpu-priority açıktır. Yalnız uygulamanın yapılandırılmış Ollama
modelleri VRAM'den boşaltılır; bu profil Ollama çıkarımını RAM/CPU'da çalıştırır. Ses modeli
STT'den önce yüklenir; STT kalan VRAM'i değerlendirir. Bu tercih LLM yanıtını yavaşlatabilir.
Ses CPU'ya düşerse Ollama kısıtı kaldırılır. CUDA hatasının ayrıntısı artık gizlenmez.
WHISPER_GPU_KONTROL.cmd sürücü, bellek, ayrı ses ortamı ve gerçek küçük CUDA kernel denemesini
WHISPER_GPU_RAPORU.txt içine yazar; API anahtarı veya kayıt okumaz.

“Bugün neler öğrendin?” için tam rapor ekranda kalır; yalnız kısa, gerçek işleme sayılarına
dayanan özet seslendirilir. Kaynak özetleme model ağırlığı eğitimi olarak sunulmaz.

Doğrulama: 484 test geçti. Windows Python 3.12 için Torch/torchaudio 2.8.0+cu128 paketlerinin
indirme dizininde bulunduğu doğrulandı. Gerçek model yeni Torch ile CPU'da 4,28 saniyelik
Türkçe ses üretti; metin geri tanımayla doğrulandı. İlk üretim 53,91 sn, aynı yanıtın
RAM önbelleğinden hazırlanması 0,001 sn sürdü (çalma hariç). Gerçek işçi iptali doğrulandı.
Bu bulutta NVIDIA GPU yoktur; Windows CUDA yüklemesi ve gecikmesi kullanıcı bilgisayarındaki
ses testiyle doğrulanmalıdır. Güncelleme belirli bir GPU hızını garanti etmez.

## V32.12 — sohbet gecikmesi, Türkçe sayılar ve telaffuz

Kullanıcının V32.11 ekranında STT 0,3–0,7 sn, ses üretimi CUDA'da yaklaşık 2 sn iken
“Ne yapıyorsun?” yanıtı 101 sn sürüyordu. Uzun görev planlama isteği ve ardından sohbet
isteği tamamen CPU'daki 8B modeli iki kez çalıştırıyordu. Tek başına sosyal cümleler artık
planlayıcıyı ve ilgisiz kaynak kartı yanıtlamasını atlar. Model yanıtı hazır şablon değildir;
son iki konuşma ve kısa kullanıcı profiliyle tek çağrıda üretilir. Karma eylem istekleri ve
bekleyen açıklama soruları bu kestirmeye girmez. Diğer soruların araç planlaması korunur.

Ses ve STT yüklendikten sonra kalan VRAM ölçülür. 1536 MB güvenlik payından sonra her
katman için ihtiyatlı 256 MB ayrılarak en fazla 8 Ollama katmanı GPU'ya verilir. Ollama'nın
kalan katmanları CPU'da kalır. Paylaşımlı profilin bağlamı en fazla 2048 tokendir. Bu tahmin
her modelin kesin bellek ölçümü değildir. Ollama ayırma hatası döndürürse yanıt başlamadan
bir kez CPU ile denenir; kimlik doğrulama hataları yeniden denenmez. Başlamış akış tekrarlanmaz.

“Beni duyuyorum” ekrandaki model metninde de görülen bir yanıt üretme hatasıdır. Kısa sohbet
isteminde özne/zamir kullanımı ve güncel soruya yanıt verme belirginleştirildi; genel dil
hatalarının tamamen giderildiği iddia edilmez. Metinde doğru olup seste yanlış okunan Enter
“entır” biçiminde gönderilir. Tam sayılar, Türkçe binlik/ondalık yazım, yüzde, geçerli tarih
ve saatler ses öncesinde yazıya çevrilir. Uzun Chatterbox metni normalizasyondan sonra en
fazla 220 karakterlik parçalara ayrılır; cümle ortasında tercihen noktalama/boşluk kullanılır.
Ekran ve hafızadaki metin korunur. Aynı ses, ağırlıklar ve örnekleme ayarları kullanılır.

494 test geçti. Gerçek Chatterbox işçisi CPU'da “Seni duyuyorum. Enter tuşuna bas. Bellek
kullanımı yüzde 25.” metninin normalleştirilmiş halini üretti. 4,84 sn ses üretimi 55,56 sn
sürdü; geri tanımada üç cümle de doğru döndü. Bu, genel telaffuz kalitesi veya Windows/GPU
hız ölçümü değildir. Kullanıcının GPU'su bu bulutta bulunmadığından toplam sohbet gecikmesi
bilgisayarda yeniden ölçülmelidir. V32.11 ses ortamı hazırsa yeni model/çalışma paketi indirilmez.

## V32.13 — tek modelli siber güvenlik geliştirme oturumu

WHISPER_GELISIM_BASLAT.cmd ses/STT ve GUI yüklemeden kurulu yerel kod modeliyle sürekli
geliştirme yürütür. Güvenlik kaynakları ve gelişim kartları önceliklendirilir; hedefe uygun
kaynak kodu ve kart özeti kod modeline aktarılır. Hazır bilgi kuyruğunda dakika araları yoktur.
Taslak/test/apply öncesindeki beklemeler bu modda 60 saniyedir; yeniden deneme sınırları,
yedekler, izin verilen modüller ve gerçek Docker test şartı korunur. Güncellemeden sonra
paket doğrulanarak yeni süreçle devam edilir. No-change sonucu sonsuz tekrar üretmez.

Tek model, sınırlı işlem grubu ve CPU iş parçacığı; boşta 30 sn sonrası Ollama modelini bırakma
isteğiyle kaynak tüketimi azaltılır. Model dosyası sıkıştırılmaz ve model ağırlığı eğitilmez.
Windows RAM/VRAM kazancı burada ölçülmedi. Eski test imajındaki eksik Türkçe yazı tipi ve
isteğe bağlı ses bağımlılıkları düzeltildi; imaj sürüm etiketiyle gerektiğinde otomatik yenilenir.
510 test ana ortamda ve gerçek 2 CPU/2 GB ağsız Docker'da geçti. Gerçek yerel 1.5B kod modeli
ayrı küçük projede değişiklik yazdı, gerçek Docker testi geçti, yedekli uygulandı; 39,17 sn.
Bu, kullanıcı bilgisayarındaki 7B model için genel başarı veya hız garantisi değildir.
Kurulum ve sınırlar V32_13_GELISIM_REHBERI.md dosyasında.
