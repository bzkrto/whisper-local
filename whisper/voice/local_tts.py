"""Pinned Turkish Piper voice; synthesis and playback do not need online TTS."""
import hashlib
import os
from pathlib import Path
import tempfile
import threading
import time
import wave

REVISION='375a0fe641dea077c2a47b4e9a056d6da521eed3'
MODEL_NAME='tr_TR-fettah-medium.onnx'
BASE=f'https://huggingface.co/rhasspy/piper-voices/resolve/{REVISION}/tr/tr_TR/fettah/medium/'
FILES={
 MODEL_NAME: ('5d14d5222f36aea2b8fc8dba097fcb18dcf8f5b33e5b2aa76b5e0b44602aa8d7',63201294),
 MODEL_NAME+'.json': ('0738ecd770d4102fa967a784ae89f64d846b1b5f104076e410c978fefa70b3e7',4877),
}

def verified(path, digest, size):
    if not path.is_file() or path.stat().st_size!=size:return False
    h=hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()==digest

def prepare_voice(directory, fetch=None, cancelled=None):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    if fetch is None:
        import requests
        fetch=requests.get
    for name,(digest,size) in FILES.items():
        path=directory/name
        if verified(path,digest,size):continue
        if cancelled and cancelled.is_set():raise InterruptedError('Ses kurulumu iptal edildi.')
        print('Yerel Türkçe ses dosyası hazırlanıyor: '+name,flush=True)
        fd,tmp=tempfile.mkstemp(prefix=name+'.',suffix='.part',dir=directory)
        deadline=time.monotonic()+300
        try:
            with os.fdopen(fd,'wb') as output:
                with fetch(BASE+name,stream=True,timeout=(10,30)) as response:
                    response.raise_for_status()
                    total=0
                    for chunk in response.iter_content(1024*1024):
                        if (cancelled and cancelled.is_set()) or time.monotonic()>deadline:
                            raise InterruptedError('Ses dosyası indirme durduruldu.')
                        total+=len(chunk)
                        if total>size:raise ValueError('Ses dosyası boyutu beklenenden büyük.')
                        output.write(chunk)
                output.flush();os.fsync(output.fileno())
            if not verified(Path(tmp),digest,size):raise ValueError('Ses dosyası SHA256 doğrulaması başarısız.')
            os.replace(tmp,path)
        finally:
            Path(tmp).unlink(missing_ok=True)
    return directory/MODEL_NAME

class PiperTTS:
    name='Piper Fettah — ücretsiz yerel Türkçe ses'
    def __init__(self,directory):
        from piper import PiperVoice,SynthesisConfig
        model=prepare_voice(directory)
        self.voice=PiperVoice.load(model,use_cuda=False)
        self.config=SynthesisConfig(length_scale=1.0,noise_scale=.5,noise_w_scale=.65)
        self._cancel=threading.Event()
        self._lock=threading.Lock()

    def stop(self):self._cancel.set()

    def _cancelled(self):
        return self._cancel.is_set() or getattr(self,'turn_cancelled',self._cancel).is_set()

    def synthesize(self,text,path):
        with wave.open(str(path),'wb') as output:
            self.voice.synthesize_wav(text,output,syn_config=self.config)
        with wave.open(str(path),'rb') as source:
            if source.getnframes()==0:raise ValueError('Yerel ses boş üretildi.')

    def _play(self,path):
        from .playback import play_wav
        return play_wav(path,self._cancelled)

    def speak(self,text):
        if getattr(self,'turn_cancelled',threading.Event()).is_set():return False
        with self._lock:
            self._cancel.clear()
            fd,name=tempfile.mkstemp(suffix='.wav');os.close(fd)
            try:
                self.synthesize(text,name)
                if self._cancelled():return False
                return self._play(name)
            except Exception as exc:
                print('Yerel Türkçe ses üretimi/oynatma başarısız: '+type(exc).__name__)
                return False
            finally:Path(name).unlink(missing_ok=True)
