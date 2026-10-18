"""Official ElevenLabs API; selected voice only, without automatic paid retries."""
from collections import OrderedDict
import ctypes
from ctypes import wintypes
import getpass
import hashlib
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import wave

VOICE_ID='krLzmW3By9JzaVy294Ux'
SERVICE='https://api.elevenlabs.io'
KEY_VARIABLE='WHISPER_ELEVENLABS_API_KEY'

def api_error(response,secret):
    """Keep the provider's diagnosis, but never echo the credential or raw body."""
    status,message='', ''
    try:
        body=response.json()
        detail=body.get('detail',{}) if isinstance(body,dict) else {}
        if isinstance(detail,dict):
            status=detail.get('status','')
            message=detail.get('message','')
        elif isinstance(detail,str):message=detail
        elif isinstance(detail,list):
            # Validation errors can contain the entire request under `input`.
            # Show only field names and error types, never that request.
            fields=[]
            for item in detail[:5]:
                if not isinstance(item,dict):continue
                location=item.get('loc',[])
                if not isinstance(location,list):continue
                fields.append('.'.join(str(v) for v in location)+': '+str(item.get('type','invalid')))
            message='Geçersiz alan: '+'; '.join(fields) if fields else ''
    except (ValueError,AttributeError):pass
    def clean(value,limit):
        if not isinstance(value,str):return ''
        if secret:value=value.replace(secret,'[anahtar gizlendi]')
        value=re.sub(r'(?i)\bsk_[A-Za-z0-9_-]+','[anahtar gizlendi]',value)
        value=re.sub(r'[\x00-\x1f\x7f-\x9f]',' ',value)
        return value[:limit]
    status=clean(status,100);message=clean(message,500)
    if status in ('quota_exceeded','insufficient_credits'):
        reason='ElevenLabs kullanım kotası yetersiz; hesabındaki kotayı kontrol et.'
    elif status in ('paid_plan_required','payment_required','subscription_required'):
        reason='ElevenLabs bu işlem için ücretli plan istiyor. Seçilen sesin API erişimini hesap planından kontrol et.'
    elif status in ('voice_not_found','voice_not_in_library') or response.status_code==404:
        reason='Seçilen ElevenLabs sesi hesapta bulunamadı; bağlantıdaki sesi Voice Library’den hesabına ekle.'
    elif response.status_code in (401,403) or status in ('missing_permissions','invalid_api_key'):
        reason='ElevenLabs anahtarı veya Text to Speech izni kabul edilmedi; ses ayarını kontrol et.'
    elif response.status_code==429:
        reason='ElevenLabs istek sınırına ulaşıldı; bir süre sonra tekrar dene.'
    else:reason='ElevenLabs ses isteğini reddetti.'
    result=f'{reason} [HTTP {response.status_code}'+(f'; kod: {status}' if status else '')+']'
    if message:result+='\nElevenLabs açıklaması: '+message
    return result

class Blob(ctypes.Structure):
    _fields_=[('length',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]

def key_path():
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData'/'Local')))/'WhisperAstra'/'elevenlabs.dpapi'

def _protect(data,decrypt=False):
    if os.name!='nt':raise RuntimeError('Kalıcı anahtar kaydı yalnız Windows kullanıcı şifrelemesiyle desteklenir.')
    buffer=ctypes.create_string_buffer(data)
    source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)))
    target=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    function=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    function.restype=wintypes.BOOL
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    if not function(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target)):
        raise RuntimeError('Windows anahtar şifrelemesi başarısız.')
    try:return ctypes.string_at(target.data,target.length)
    finally:kernel.LocalFree(ctypes.cast(target.data,ctypes.c_void_p))

def load_key():
    value=os.environ.get(KEY_VARIABLE,'').strip()
    if value:return value
    if os.name!='nt' or not key_path().is_file():return ''
    try:return _protect(key_path().read_bytes(),decrypt=True).decode('utf-8').strip()
    except (OSError,RuntimeError,UnicodeError):return ''

def save_key(value):
    value=value.strip()
    if not value or len(value)>512 or any(c.isspace() for c in value):raise ValueError('API anahtarı boş veya geçersiz.')
    encrypted=_protect(value.encode('utf-8'))
    path=key_path();path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=path.parent,suffix='.tmp')
    try:
        with os.fdopen(fd,'wb') as f:f.write(encrypted);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    finally:Path(name).unlink(missing_ok=True)

def setup_key():
    root=None
    try:
        import tkinter as tk
        from tkinter import simpledialog,messagebox
        root=tk.Tk();root.withdraw()
        value=simpledialog.askstring('Whisper — ElevenLabs sesi','ElevenLabs hesabında API Keys bölümünden oluşturduğun anahtarı yapıştır.\nText to Speech izni açık olmalı.\nAnahtar bu bilgisayarda Windows kullanıcı şifrelemesiyle saklanır.',show='*',parent=root)
        if not value:return False
        save_key(value)
        messagebox.showinfo('Whisper','ElevenLabs anahtarı kaydedildi. Seçtiğin sesle devam edilecek.',parent=root)
        return True
    except ImportError:
        value=getpass.getpass('ElevenLabs API anahtarı (gizli giriş): ')
        if not value:return False
        save_key(value);return True
    finally:
        if root is not None:root.destroy()

class ElevenLabsTTS:
    name='ElevenLabs (seçilen ses)'
    def __init__(self,voice_id=VOICE_ID,text_processor=str,api_key=None):
        if not re.fullmatch(r'[A-Za-z0-9]{16,64}',voice_id):raise ValueError('ElevenLabs ses kimliği geçersiz.')
        self.voice_id=voice_id
        self._key=api_key if api_key is not None else load_key()
        if not self._key:raise RuntimeError('ElevenLabs anahtarı yok. WHISPER_ELEVENLABS_AYAR.cmd dosyasını açın.')
        self.text_processor=text_processor
        self._cancel=threading.Event();self._lock=threading.Lock()
        self._blocked_until=0.;self._cache=OrderedDict()

    def stop(self):self._cancel.set()
    def _cancelled(self):return self._cancel.is_set() or getattr(self,'turn_cancelled',self._cancel).is_set()

    def _fetch(self,text):
        import requests
        payload={'text':text,'model_id':'eleven_multilingual_v2','language_code':'tr',
                 'voice_settings':{'stability':1.0,'similarity_boost':1.0,'style':0.0,'use_speaker_boost':True,'speed':0.96}}
        with requests.post(SERVICE+'/v1/text-to-speech/'+self.voice_id,
             params={'output_format':'pcm_24000'},json=payload,
             headers={'xi-api-key':self._key,'Accept':'audio/pcm'},
             timeout=(5,30),stream=True,allow_redirects=False) as response:
            if response.status_code!=200:
                self._blocked_until=time.monotonic()+60
                raise RuntimeError(api_error(response,self._key))
            kind=response.headers.get('Content-Type','').split(';')[0].lower()
            if kind not in ('audio/pcm','audio/x-pcm','application/octet-stream'):
                raise RuntimeError('ElevenLabs beklenen PCM ses biçimini döndürmedi.')
            data=bytearray();deadline=time.monotonic()+60
            for chunk in response.iter_content(65536):
                if self._cancelled():raise InterruptedError('Ses isteği iptal edildi.')
                if time.monotonic()>deadline:raise RuntimeError('Ses indirme süresi doldu.')
                data.extend(chunk)
                if len(data)>10000000:raise RuntimeError('Ses boyut sınırı aşıldı.')
        if not data or len(data)%2:raise RuntimeError('ElevenLabs boş veya bozuk ses döndürdü.')
        return bytes(data)

    def _play(self,path):
        # Reuse the PCM WAV playback loop; no Piper SDK/model is loaded here.
        from .local_tts import PiperTTS
        return PiperTTS._play(self,path)

    def speak(self,text):
        if getattr(self,'turn_cancelled',threading.Event()).is_set():return False
        with self._lock:
            self._cancel.clear()
            text=self.text_processor(text).strip()
            if not text:return True
            if time.monotonic()<self._blocked_until:return False
            digest=hashlib.sha256(text.encode('utf-8')).hexdigest()
            name=None
            try:
                data=self._cache.get(digest)
                if data is None:
                    data=self._fetch(text)
                    if self._cancelled():return False
                    self._cache[digest]=data
                    while len(self._cache)>16 or sum(map(len,self._cache.values()))>8000000:self._cache.popitem(last=False)
                else:self._cache.move_to_end(digest)
                if self._cancelled():return False
                fd,name=tempfile.mkstemp(suffix='.wav');os.close(fd)
                with wave.open(name,'wb') as wav:
                    wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000);wav.writeframes(data)
                return self._play(name)
            except InterruptedError:return False
            except RuntimeError as exc:
                print(str(exc));return False
            except Exception as exc:
                print('ElevenLabs ses üretimi/oynatma başarısız: '+type(exc).__name__)
                return False
            finally:
                if name:Path(name).unlink(missing_ok=True)

if __name__=='__main__':
    try:raise SystemExit(0 if setup_key() else 1)
    except Exception as exc:
        print('ElevenLabs ayarı kaydedilemedi: '+type(exc).__name__)
        raise SystemExit(1)
