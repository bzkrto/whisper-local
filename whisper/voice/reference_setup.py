"""Private reference recording and an isolated XTTS runtime, without API keys."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import time
import venv

REVISION='6c2b0d75eae4b7047358e3b6bd9325f857d43f77'
FILES={
 'model.pth':(1867929118,'c7ea20001c6a0a841c77e252d8409f6a74fb423e79b3206a0771ba5989776187'),
 'config.json':(4368,'ef262b1454dd2a77e1461b0b2cd53e19b8a7624cc131b837d36df67356bc75e8'),
 'vocab.json':(361219,'928260878a59da8a72a2a5b7687fea29d5106137669d90945430fe17e415304a'),
 'speakers_xtts.pth':(7754818,'f0f6137c19a4eab0cbbe4c99b5babacf68b1746e50da90807708c10e645b943b'),
 'LICENSE.txt':(4014,'190f6d7c19b8984f91b97712b94ce92d2b2e640fc677dacab966e955ece9d043'),
}

def voice_home():
    custom=os.environ.get('WHISPER_REFERENCE_HOME')
    if custom:return Path(custom)
    base=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local'/'share')))
    return base/'WhisperAstra'/'reference'

def runtime_python(home=None):
    home=Path(home or voice_home())
    return home/'venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def verify(path,size,sha):return path.is_file() and path.stat().st_size==size and digest(path)==sha

def ready(home=None):
    home=Path(home or voice_home())
    try:
        metadata=json.loads((home/'ready.json').read_text())
        return (metadata.get('revision')==REVISION and runtime_python(home).is_file()
                and (home/'reference.wav').is_file()
                and all((home/'model'/n).is_file() and (home/'model'/n).stat().st_size==v[0] for n,v in FILES.items()))
    except (OSError,ValueError):return False

def prepare_model(directory):
    import requests
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    for name,(size,sha) in FILES.items():
        target=directory/name
        if verify(target,size,sha):continue
        print('Ses modeli hazırlanıyor: '+name,flush=True)
        fd,tmp=tempfile.mkstemp(dir=directory,suffix='.part');started=time.monotonic();reported=started
        try:
            with os.fdopen(fd,'wb') as output:
                with requests.get(f'https://huggingface.co/coqui/XTTS-v2/resolve/{REVISION}/{name}',stream=True,timeout=(10,30)) as response:
                    response.raise_for_status();total=0
                    for chunk in response.iter_content(1024*1024):
                        total+=len(chunk)
                        if total>size or time.monotonic()-started>3600:raise RuntimeError('Ses modeli indirme sınırı aşıldı.')
                        output.write(chunk)
                        if time.monotonic()-reported>5:
                            print(f'{name}: %{100*total/size:.0f}',flush=True);reported=time.monotonic()
                output.flush();os.fsync(output.fileno())
            if not verify(Path(tmp),size,sha):raise ValueError('Ses modelinin SHA256 doğrulaması başarısız: '+name)
            os.replace(tmp,target)
        finally:Path(tmp).unlink(missing_ok=True)

def convert_reference(source,target):
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    from math import gcd
    source=Path(source)
    if not source.is_file() or source.stat().st_size>64000000:raise ValueError('Ses kaydı bulunamadı veya 64 MB sınırını aştı.')
    info=sf.info(source)
    if info.duration<6 or not 8000<=info.samplerate<=192000 or not 1<=info.channels<=8:
        raise ValueError('En az 6 saniyelik, desteklenen biçimde konuşma kaydı seçin.')
    a,sr=sf.read(source,frames=min(info.frames,30*info.samplerate),dtype='float32',always_2d=True)
    a=a.mean(axis=1)
    if not np.isfinite(a).all():raise ValueError('Ses kaydında geçersiz örnek var.')
    peak=float(np.max(abs(a)))
    if peak<.001:raise ValueError('Ses kaydı sessiz veya çok kısık.')
    indices=np.flatnonzero(abs(a)>max(.005,.05*peak))
    if not len(indices):raise ValueError('Konuşma bulunamadı.')
    start=max(0,int(indices[0]) - int(.15*sr));a=a[start:start+20*sr]
    if len(a)<5*sr:raise ValueError('Yeterli referans konuşması bulunamadı.')
    a=a*(.8/max(float(np.max(abs(a))),.001));g=gcd(sr,24000)
    a=resample_poly(a,24000//g,sr//g)
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=target.parent,suffix='.wav');os.close(fd)
    try:sf.write(tmp,a,24000,subtype='PCM_16');os.replace(tmp,target)
    finally:Path(tmp).unlink(missing_ok=True)

def choose_source():
    import tkinter as tk
    from tkinter import filedialog
    root=tk.Tk();root.withdraw()
    try:return filedialog.askopenfilename(title='Whisper için indirdiğin ses kaydını seç',filetypes=[('Ses kaydı','*.mp3 *.wav *.flac'),('Tüm dosyalar','*.*')])
    finally:root.destroy()

def torch_index():
    # CUDA 12.6 wheels need a sufficiently recent NVIDIA driver.
    if not shutil.which('nvidia-smi'):return 'https://download.pytorch.org/whl/cpu'
    try:
        result=subprocess.run(['nvidia-smi','--query-gpu=driver_version','--format=csv,noheader'],capture_output=True,text=True,timeout=5)
        if result.returncode==0 and any(int(line.strip().split('.')[0])>=560 for line in result.stdout.splitlines() if line.strip()):
            return 'https://download.pytorch.org/whl/cu126'
    except (OSError,ValueError,subprocess.TimeoutExpired):pass
    return 'https://download.pytorch.org/whl/cpu'

def setup(force_choose=False):
    home=voice_home();home.mkdir(parents=True,exist_ok=True)
    source=''
    if not force_choose:
        try:source=json.loads((home/'source.json').read_text()).get('source','')
        except (OSError,ValueError):pass
    if not source or not Path(source).is_file():source=choose_source()
    if not source:return 1
    (home/'source.json').write_text(json.dumps({'source':source}),encoding='utf-8')
    py=runtime_python(home)
    if not py.is_file():venv.EnvBuilder(with_pip=True).create(home/'venv')
    # Select CUDA only when a compatible NVIDIA driver was actually detected.
    if not (home/'packages.ready').exists():
        subprocess.run([str(py),'-m','pip','install','torch==2.8.0','torchaudio==2.8.0','--index-url',torch_index()],check=True)
        requirements=Path(__file__).resolve().parents[2]/'requirements-reference-voice.txt'
        subprocess.run([str(py),'-m','pip','install','-r',str(requirements)],check=True)
        (home/'packages.ready').write_text('coqui-tts=0.27.5;torch=2.8.0;transformers=4.57.6')
    result=subprocess.run([str(py),'-m','whisper.voice.reference_setup','--prepare',str(source)],check=False)
    return result.returncode

def main():
    p=argparse.ArgumentParser();p.add_argument('--setup',action='store_true');p.add_argument('--choose',action='store_true');p.add_argument('--prepare');a=p.parse_args()
    if a.prepare:
        home=voice_home();prepare_model(home/'model');convert_reference(a.prepare,home/'reference.wav')
        (home/'ready.json').write_text(json.dumps({'revision':REVISION,'reference_sha256':digest(home/'reference.wav')}))
        print('Referans ses hazır. İşlemcide ses üretimi yavaş olabilir; durum günlüğündeki süreyi kontrol edin.')
        return 0
    return setup(a.choose)

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print('Referans ses kurulumu tamamlanamadı: '+type(exc).__name__+': '+str(exc)[:200]);raise SystemExit(1)
