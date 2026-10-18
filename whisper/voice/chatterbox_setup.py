"""Pinned, private Chatterbox V3 installation; no paid service or shared torch env."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import venv
import wave
import zipfile

from .reference_setup import (digest, verify, choose_source, convert_reference,
                              runtime_python, voice_home as legacy_home)

REVISION='5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18'
SOURCE_REVISION='5de7a54aa4e5e2baadb0182dde554908b48b85c2'
SOURCE_URL=('https://github.com/resemble-ai/chatterbox/archive/'+SOURCE_REVISION+
            '.zip#sha256=bb7363a76c0c0432a0305681fe2e533bbfb0f10fcf7b98d75a439d9a909f1576')
RUNTIME_TAG='chatterbox-v3-'+SOURCE_REVISION+'-torch2.8.0-r2'
FILES={
 've.pt':(5698626,'4b16d836bc598509860f6fa068165a8bb5e9ac84f05582dfcf278a5a372879f1'),
 's3gen.pt':(1057165844,'9b9ff07e60b20c136e2b1b3d7563a24604e8d2c4c267888d1ee929dd0151d2a3'),
 't3_mtl23ls_v3.safetensors':(2143989928,'5abca8321ede76f8e61f1cc0d19aea6c946b28871017ce8726f8a69203f05953'),
 'grapheme_mtl_merged_expanded_v1.json':(69989,'69632f47220a788a52ce2661d096453c5655e9bf25289d89a8d832c46ee07dbf'),
 'Cangjie5_TC.json':(1920163,'7073fd9de919443ae88e0bd2449917a65fe54898a4413ed1edcc4b67f28bce8c'),
}
TOKENIZER_URL='https://github.com/explosion/spacy-pkuseg/releases/download/v0.0.26/spacy_ontonotes.zip'
TOKENIZER_ZIP=(34567143,'b216e7f92de7ae285aeab8feba2faa8ea8216e5995ff6fb3d391cc8356db1bfe')
TOKENIZER_FILES={
 'features.msgpack':(22685181,'fd4322482a7018b9bce9216173ae9d2848efe6d310b468bbb4383fb55c874a18'),
 'weights.npz':(37508754,'5ada075eb25a854f71d6e6fa4e7d55e7be0ae049255b1f8f19d05c13b1b68c9e'),
}

def voice_home():
    custom=os.environ.get('WHISPER_CHATTERBOX_HOME')
    if custom:return Path(custom)
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local'/'share')))/'WhisperAstra'/'chatterbox-v3'

def torch_index():
    if not shutil.which('nvidia-smi'):return 'https://download.pytorch.org/whl/cpu'
    try:
        result=subprocess.run(['nvidia-smi','--query-gpu=driver_version','--format=csv,noheader'],
                              capture_output=True,text=True,timeout=5)
        drivers=[int(line.strip().split('.')[0]) for line in result.stdout.splitlines() if line.strip()]
        if result.returncode==0 and drivers:
            if max(drivers)>=570:return 'https://download.pytorch.org/whl/cu128'
            if max(drivers)>=560:return 'https://download.pytorch.org/whl/cu126'
    except (OSError,ValueError,subprocess.TimeoutExpired):pass
    return 'https://download.pytorch.org/whl/cpu'

def install_source(py,home):
    """Keep model code pinned; adapt only dependency metadata for RTX 50 support."""
    archive=Path(home)/'cache'/'chatterbox-source.zip'
    fetch_file(SOURCE_URL.split('#',1)[0],archive,1478295,
               'bb7363a76c0c0432a0305681fe2e533bbfb0f10fcf7b98d75a439d9a909f1576')
    with tempfile.TemporaryDirectory(dir=archive.parent,prefix='source-') as tmp:
        root=Path(tmp).resolve()
        with zipfile.ZipFile(archive) as zipped:
            if sum(i.file_size for i in zipped.infolist())>32000000:raise ValueError('Ses kaynak arşivi boyutu geçersiz.')
            for info in zipped.infolist():
                if not (root/info.filename).resolve().is_relative_to(root) or (info.external_attr>>16)&0o170000==0o120000:
                    raise ValueError('Ses kaynak arşivi yolu geçersiz.')
            zipped.extractall(root)
        source=root/('chatterbox-'+SOURCE_REVISION);project=source/'pyproject.toml'
        text=project.read_text(encoding='utf-8')
        for old,new in [('"torch==2.6.0;', '"torch==2.8.0;'),
                        ('"torchaudio==2.6.0;', '"torchaudio==2.8.0;'),
                        ('version = "0.1.7"','version = "0.1.7+whisper.torch28"')]:
            if text.count(old)!=1:raise ValueError('Sabit ses kaynağının bağımlılık bildirimi değişmiş.')
            text=text.replace(old,new)
        project.write_text(text,encoding='utf-8')
        subprocess.run([str(py),'-m','pip','install','--no-deps',str(source)],check=True)

def configure_runtime(home):
    home=Path(home)
    os.environ['HF_HOME']=str(home/'cache'/'huggingface')
    os.environ['PKUSEG_HOME']=str(home/'cache'/'pkuseg')
    os.environ['NUMBA_CACHE_DIR']=str(home/'cache'/'numba')
    os.environ['HF_HUB_OFFLINE']='1'
    os.environ['TRANSFORMERS_OFFLINE']='1'

def reference_valid(path):
    try:
        with wave.open(str(path),'rb') as audio:
            return (audio.getnchannels()==1 and audio.getsampwidth()==2 and
                    audio.getframerate()==24000 and 5<=audio.getnframes()/24000<=14.01)
    except (OSError,EOFError,wave.Error):return False

def ready(home=None):
    home=Path(home or voice_home())
    try:
        data=json.loads((home/'ready.json').read_text())
        return (data.get('revision')==REVISION and data.get('runtime')==RUNTIME_TAG and
                runtime_python(home).is_file() and (home/'packages.ready').read_text()==RUNTIME_TAG and
                reference_valid(home/'reference.wav') and data.get('reference_sha256')==digest(home/'reference.wav') and
                all((home/'model'/n).is_file() and (home/'model'/n).stat().st_size==v[0] for n,v in FILES.items()) and
                all((home/'cache'/'pkuseg'/'spacy_ontonotes'/n).is_file() and
                    (home/'cache'/'pkuseg'/'spacy_ontonotes'/n).stat().st_size==v[0] for n,v in TOKENIZER_FILES.items()) and
                (home/'cache'/'pkuseg'/'spacy_ontonotes.zip').is_file())
    except (OSError,ValueError):return False

@contextlib.contextmanager
def setup_lock(home):
    """OS locks release on process exit, including an interrupted installation."""
    home=Path(home);home.mkdir(parents=True,exist_ok=True)
    with (home/'setup.lock').open('a+b') as lock:
        if lock.tell()==0:lock.write(b'0');lock.flush()
        lock.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:raise RuntimeError('Ses kurulumu başka bir pencerede çalışıyor; o işlemin bitmesini bekleyin.') from None
        try:yield
        finally:
            lock.seek(0)
            if os.name=='nt':msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(lock.fileno(),fcntl.LOCK_UN)

def fetch_file(url,target,size,sha):
    import requests
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    if verify(target,size,sha):return
    print('Ses dosyası hazırlanıyor: '+target.name,flush=True)
    fd,tmp=tempfile.mkstemp(dir=target.parent,suffix='.part');started=time.monotonic();reported=started
    try:
        with os.fdopen(fd,'wb') as output:
            with requests.get(url,stream=True,timeout=(10,60)) as response:
                response.raise_for_status();total=0
                for chunk in response.iter_content(4*1024*1024):
                    total+=len(chunk)
                    if total>size or time.monotonic()-started>3600:raise RuntimeError('Ses dosyası indirme sınırı aşıldı.')
                    output.write(chunk)
                    if time.monotonic()-reported>5:
                        print(f'{target.name}: %{100*total/size:.0f}',flush=True);reported=time.monotonic()
            output.flush();os.fsync(output.fileno())
        if not verify(Path(tmp),size,sha):raise ValueError('Ses dosyası SHA256 doğrulaması başarısız: '+target.name)
        os.replace(tmp,target)
    finally:Path(tmp).unlink(missing_ok=True)

def prepare_model(home):
    home=Path(home)
    for name,(size,sha) in FILES.items():
        fetch_file(f'https://huggingface.co/ResembleAI/chatterbox/resolve/{REVISION}/{name}',home/'model'/name,size,sha)
    cache=home/'cache'/'pkuseg';archive=cache/'spacy_ontonotes.zip'
    fetch_file(TOKENIZER_URL,archive,*TOKENIZER_ZIP)
    with zipfile.ZipFile(archive) as zipped:
        for name,(size,sha) in TOKENIZER_FILES.items():
            target=cache/'spacy_ontonotes'/name
            if verify(target,size,sha):continue
            if zipped.getinfo(name).file_size!=size:raise ValueError('Ses tokenizer boyutu geçersiz.')
            target.parent.mkdir(parents=True,exist_ok=True)
            fd,tmp=tempfile.mkstemp(dir=target.parent,suffix='.part')
            try:
                with os.fdopen(fd,'wb') as output,zipped.open(name) as source:shutil.copyfileobj(source,output)
                if not verify(Path(tmp),size,sha):raise ValueError('Ses tokenizer SHA256 doğrulaması başarısız.')
                os.replace(tmp,target)
            finally:Path(tmp).unlink(missing_ok=True)
    # The pinned SDK resolves this optional mapping through the standard HF cache.
    # Use copies on Windows: creating symlinks can require administrator rights.
    cache=home/'model'/'models--ResembleAI--chatterbox'
    snapshot=cache/'snapshots'/REVISION;snapshot.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(home/'model'/'Cangjie5_TC.json',snapshot/'Cangjie5_TC.json')
    (cache/'refs').mkdir(exist_ok=True);(cache/'refs'/'main').write_text(REVISION)

def select_source(home,choose=False):
    if choose:return choose_source()
    for directory in (Path(home),legacy_home()):
        try:
            source=json.loads((directory/'source.json').read_text()).get('source','')
            if source and Path(source).is_file():return source
        except (OSError,ValueError):pass
        if reference_valid(directory/'reference.wav'):return str(directory/'reference.wav')
        # The previous reference mode accepted up to 20 seconds; trim it below.
        if (directory/'reference.wav').is_file():return str(directory/'reference.wav')
    return choose_source()

def prepare_reference(source,target):
    target=Path(target)
    if Path(source).resolve()==target.resolve() and reference_valid(target):return
    convert_reference(source,target)
    import soundfile as sf
    samples,rate=sf.read(str(target),frames=14*24000,dtype='float32')
    fd,tmp=tempfile.mkstemp(dir=target.parent,suffix='.wav');os.close(fd)
    try:sf.write(tmp,samples,rate,subtype='PCM_16');os.replace(tmp,target)
    finally:Path(tmp).unlink(missing_ok=True)
    if not reference_valid(target):raise ValueError('Ses referansı geçersiz.')

def prepare(home,source):
    home=Path(home);prepare_reference(source,home/'reference.wav');prepare_model(home)
    configure_runtime(home)
    # Confirm optional tokenizer initialization is completely local after setup.
    from spacy_pkuseg import pkuseg
    pkuseg()
    (home/'ready.json').write_text(json.dumps({'revision':REVISION,'runtime':RUNTIME_TAG,
                                             'reference_sha256':digest(home/'reference.wav')}))
    print('Seçilen Chatterbox V3 sesi hazır. CPU üretimi yavaştır; gerçek cihaz/süre ses testinde gösterilir.')

def setup(choose=False,repair=False):
    home=voice_home()
    with setup_lock(home):
        if not choose and not repair and ready(home):return 0
        source=select_source(home,choose)
        if not source:return 1
        if not (3,10)<=sys.version_info[:2]<(3,13):
            raise RuntimeError('Bu ses ortamı Python 3.10–3.12 gerektirir. Whisper için Python 3.11 veya 3.12 kullanın.')
        py=runtime_python(home)
        if not py.is_file():venv.EnvBuilder(with_pip=True).create(home/'venv')
        marker=home/'packages.ready'
        if repair or not marker.is_file() or marker.read_text()!=RUNTIME_TAG:
            install_source(py,home)
            index=torch_index()
            variant=index.rsplit('/',1)[-1]
            print('Ses çalışma paketi: PyTorch 2.8 / '+variant+'. Model dosyaları korunacak.',flush=True)
            subprocess.run([str(py),'-m','pip','install','torch==2.8.0+'+variant,'torchaudio==2.8.0+'+variant,'--index-url',index],check=True)
            requirements=Path(__file__).resolve().parents[2]/'requirements-chatterbox-voice.txt'
            subprocess.run([str(py),'-m','pip','install','-r',str(requirements)],check=True)
            subprocess.run([str(py),'-m','pip','check'],check=True)
            marker.write_text(RUNTIME_TAG)
        (home/'source.json').write_text(json.dumps({'source':str(source)}),encoding='utf-8')
        return subprocess.run([str(py),'-m','whisper.voice.chatterbox_setup','--prepare',str(source)],
                              cwd=Path(__file__).resolve().parents[2],check=False).returncode

def main():
    p=argparse.ArgumentParser();p.add_argument('--setup',action='store_true');p.add_argument('--choose',action='store_true');p.add_argument('--repair',action='store_true');p.add_argument('--prepare')
    args=p.parse_args()
    if args.prepare:prepare(voice_home(),args.prepare);return 0
    return setup(args.choose,args.repair)

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print('Chatterbox ses kurulumu tamamlanamadı: '+type(exc).__name__+': '+str(exc)[:250]);raise SystemExit(1)
