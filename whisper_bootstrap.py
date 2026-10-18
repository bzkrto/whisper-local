"""One entry point: verify the integrated package, then launch the existing environment."""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def verify_package():
    if (ROOT/'.whisper-update.lock').exists():
        raise RuntimeError('Kod güncellemesi devam ediyor; işlem tamamlandıktan sonra yeniden başlatın.')
    manifest=json.loads((ROOT/'WHISPER_SURUM.json').read_text(encoding='utf-8'))
    for name,expected in manifest['files'].items():
        path=ROOT/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise RuntimeError('Güncelleme eksik veya dosyalar farklı: '+name+'. ZIP içeriğinin tamamını aynı klasöre çıkarın.')
    return manifest

def main(argv=None):
    argv = list(argv or [])
    if any(arg not in ("--check-only", "--text", "--development", "--mobile", "--elevenlabs", "--reference", "--piper", "--test-voice") for arg in argv):
        print("Kullanım: whisper_bootstrap.py [--check-only] [--text | --development] [--mobile] [--test-voice] [--elevenlabs | --reference | --piper]")
        return 2
    if sum(flag in argv for flag in ('--elevenlabs','--reference','--piper'))>1:
        print('Tek bir ses modu seçin: --elevenlabs, --reference veya --piper.')
        return 2
    if '--text' in argv and any(flag in argv for flag in ('--development','--elevenlabs','--reference','--piper','--test-voice')):
        print('Yazılı mod ile ses testi veya farklı çalışma modu birlikte seçilemez.')
        return 2
    os.chdir(ROOT)
    try:
        manifest=verify_package()
    except (OSError, ValueError, RuntimeError) as exc:
        print('Başlatma durduruldu:', exc)
        return 1
    print('WHISPER '+manifest['version']+' · Paket bütünlüğü doğrulandı.')
    if '--text' in argv:
        if '--check-only' in argv:
            names=['numpy','requests','docx','reportlab','pypdf','psutil','tkinter','ddgs']
            missing=[name for name in names if importlib.util.find_spec(name) is None]
            print('Yazılı mod eksik modüller:',', '.join(missing) if missing else 'yok')
            return 1 if missing else 0
        print('Yazılı sohbet ve araştırma: mikrofon, STT ve ses modeli yüklenmez.',flush=True)
        command=[sys.executable,str(ROOT/'whisper_ses_v12.py'),'--gui','--no-voice','--tts','none',
                 '--model','qwen3:8b','--enable-tools','--enable-screen','--web',
                 '--role-model','chat=qwen3:8b','--role-model','code=qwen2.5-coder:7b',
                 '--role-model','vision=qwen3-vl:4b']
        if '--mobile' in argv:command.append('--server')
        return subprocess.call(command)
    if '--development' in argv:
        command=[sys.executable,'-m','whisper.learning.accelerated']
        if '--check-only' in argv:return subprocess.call(command+['--check-only'])
        from whisper.learning.accelerated import session_lock
        try:
            with session_lock(ROOT):
                while True:
                    code=subprocess.call(command+['--build-test-image'])
                    if code!=42:return code
                    manifest=verify_package()
                    print('Yeni kod doğrulandı: '+manifest['version'],flush=True)
        except (OSError,ValueError,RuntimeError) as exc:
            print('Geliştirme durduruldu: '+str(exc),flush=True);return 1
        except KeyboardInterrupt:return 130
    if '--check-only' in argv:
        # Read-only: no package installation, model download, microphone or app launch.
        names = ['numpy', 'requests', 'sounddevice', 'speech_recognition', 'faster_whisper',
                 'edge_tts', 'docx', 'reportlab', 'pypdf', 'psutil']
        if sys.platform == 'win32':
            names += ['pycaw', 'comtypes']
        missing = [name for name in names if importlib.util.find_spec(name) is None]
        voice_ready=True
        if not any(flag in argv for flag in ('--reference','--elevenlabs','--piper')):
            from whisper.voice.chatterbox_setup import ready
            voice_ready=ready()
            print('Seçilen ses ortamı:', 'kurulu' if voice_ready else 'kurulu değil; WHISPER_SES_TESTI.cmd ilk kurulumu yapar')
        print('Python:', sys.version.split()[0], '| Platform:', sys.platform)
        print('Eksik modüller:', ', '.join(missing) if missing else 'yok')
        print('Yalnız dosya bütünlüğü ve modül varlığı kontrol edildi. '
              'Windows güvenliği, GPU, model ve mikrofon çalışması doğrulanmadı.')
        return 1 if missing or not voice_ready else 0
    # Prepare the selected local voice package; preserve existing GPU/model setup.
    if sys.platform == 'win32':
        missing = [name for name in ('pycaw', 'comtypes') if importlib.util.find_spec(name) is None]
        packages=list(missing)
        if '--piper' in argv and importlib.util.find_spec('piper') is None:
            packages.append('piper-tts==1.8.0')
        if packages:
            print('Eksik ses paketleri kuruluyor:', ', '.join(packages))
            result = subprocess.run([sys.executable, '-m', 'pip', 'install', *packages])
            if result.returncode:
                print('Paket kurulamadı; Whisper başlatılmadı. Yukarıdaki kurulum hatasını kontrol edin.')
                return result.returncode
    if sys.platform == 'win32' and '--elevenlabs' in argv:
        from whisper.voice.elevenlabs_tts import load_key
        if not load_key():
            print('Seçtiğiniz ElevenLabs sesi için anahtar ayarı açılıyor.')
            setup_result=subprocess.call([sys.executable,'-m','whisper.voice.elevenlabs_tts'])
            if setup_result or not load_key():
                print('ElevenLabs anahtarı kaydedilmedi; WHISPER_ELEVENLABS_AYAR.cmd ile ayarlayabilirsiniz.')
                return 1
    if sys.platform == 'win32' and '--reference' in argv:
        from whisper.voice.reference_setup import ready
        if not ready():
            print('İndirdiğiniz MP3 kaydını seçin. İlk kurulumda yerel ses ortamı ve yaklaşık 1,9 GB model hazırlanır.')
            result=subprocess.call([sys.executable,'-m','whisper.voice.reference_setup','--setup'])
            if result or not ready():
                print('Referans ses kurulumu tamamlanmadı; WHISPER_SES_KAYDI.cmd ile devam edebilirsiniz.')
                return 1
    engine='reference' if '--reference' in argv else ('elevenlabs' if '--elevenlabs' in argv else ('piper' if '--piper' in argv else 'chatterbox'))
    if engine=='chatterbox':
        from whisper.voice.chatterbox_setup import ready,voice_home
        if not ready():
            if (voice_home()/'model').is_dir():
                print('Mevcut ses modeli korunarak PyTorch/CUDA çalışma paketi güncellenecek. Doğrulanmış model dosyaları yeniden indirilmez.')
            else:print('Beğendiğiniz ses için Chatterbox V3 hazırlanıyor. İlk kurulum yaklaşık 3,2 GB model ve ek çalışma paketleri indirir.')
            print('Önceki kayıt bulunamazsa orijinal MP3/WAV kaydını seçin. Referans yalnız bilgisayarınızda kalır.')
            result=subprocess.call([sys.executable,'-m','whisper.voice.chatterbox_setup','--setup'])
            if result or not ready():
                print('Seçilen ses kurulumu tamamlanmadı; WHISPER_SES_KAYDI.cmd ile devam edin.')
                return 1
        print('Seçilen ücretsiz ses: Chatterbox V3. Model mikrofon açılmadan hazırlanır; CPU üzerinde üretim yavaştır.')
    if engine=='piper':print('Ücretsiz yerel Türkçe ses: Fettah. İlk kullanımda yaklaşık 63 MB model indirilir; seslendirme çevrimdışı çalışır.')
    command = [sys.executable, str(ROOT/'whisper_ses_v12.py'), '--gui', '--model', 'qwen3:8b',
               '--tts', engine,
               '--whisper-device', 'auto', '--whisper-beam', '5', '--silence-seconds', '0.8',
               '--conversation-timeout', '20',
               '--enable-tools', '--enable-screen', '--web',
               '--role-model', 'chat=qwen3:8b', '--role-model', 'code=qwen2.5-coder:7b',
               '--role-model', 'vision=qwen3-vl:4b']
    if '--elevenlabs' in argv:command.append('--allow-cloud')
    if engine=='chatterbox':command.append('--voice-gpu-priority')
    if '--test-voice' in argv:command.append('--test-voice')
    if '--mobile' in argv:
        command.append('--server')
    return subprocess.call(command)

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
