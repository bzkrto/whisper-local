"""Private reference-voice adapter; no torch packages loaded into the app process."""
import atexit
from collections import OrderedDict
import json
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
import wave
from .reference_setup import voice_home,runtime_python,ready

class ReferenceTTS:
    name='Referans kayıtla Türkçe ses (yerel)'
    worker_module='whisper.voice.reference_worker'

    def _home(self):return voice_home()
    def _ready(self,home):return ready(home)
    def _python(self,home):return runtime_python(home)

    def __init__(self,text_processor=str,home=None):
        self.home=Path(home or self._home())
        if not self._ready(self.home):raise RuntimeError('Referans ses hazır değil. WHISPER_SES_KAYDI.cmd dosyasını açın.')
        self.text_processor=text_processor
        self._cancel=threading.Event();self._lock=threading.Lock();self._generating=threading.Event()
        self._process=None;self._log=None;self._cache=OrderedDict()
        self._directory=tempfile.TemporaryDirectory(prefix='whisper-reference-')
        self._events=queue.Queue();self.device='unknown'
        atexit.register(self.close)

    def _cancelled(self):return self._cancel.is_set() or getattr(self,'turn_cancelled',self._cancel).is_set()

    def _wait(self,seconds):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            if self._cancelled():raise InterruptedError('Ses işlemi iptal edildi.')
            try:
                data=self._events.get(timeout=.1)
                if data.get('type')=='error':raise RuntimeError(data.get('error','Ses işçisi hatası.'))
                if data.get('type')=='progress':
                    print(data.get('message','Ses hazırlanıyor…'),flush=True)
                    continue
                return data
            except queue.Empty:pass
        raise RuntimeError('Yerel ses üretimi zaman aşımına uğradı.')

    def _start(self):
        if self._process and self._process.poll() is None:return
        self._kill();self._events=queue.Queue()
        print(self.name+' modeli yükleniyor; ilk hazırlık zaman alabilir.',flush=True)
        self._log=(self.home/'worker.log').open('ab')
        self._process=subprocess.Popen([str(self._python(self.home)),'-u','-m',self.worker_module,str(self.home),self._directory.name],
            cwd=Path(__file__).resolve().parents[2],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self._log,
            text=True,encoding='utf-8',bufsize=1)
        process=self._process;events=self._events
        def read():
            try:
                for line in process.stdout:
                    try:events.put(json.loads(line))
                    except ValueError:continue
            finally:events.put({'type':'error','error':'Ses işçisi kapandı; worker.log dosyasını kontrol edin.'})
        threading.Thread(target=read,daemon=True).start()
        status=self._wait(180)
        if status.get('type')!='ready':raise RuntimeError('Yerel ses modeli hazır olamadı.')
        self.device=status['device']
        print(self.name+' hazır: '+self.device+('. İşlemcide üretim yavaş olabilir.' if self.device=='cpu' else ''),flush=True)
        if status.get('reason'):print(status['reason'],flush=True)

    def _kill(self):
        process=self._process;self._process=None
        if process:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            for stream in (process.stdin,process.stdout):
                if stream:
                    try:stream.close()
                    except OSError:pass
        if self._log:self._log.close();self._log=None

    def stop(self):
        self._cancel.set()
        if self._generating.is_set():self._kill()

    def close(self):
        self._cancel.set();self._kill()
        try:self._directory.cleanup()
        except (OSError,AttributeError):pass

    def _play(self,path):
        from .local_tts import PiperTTS
        return PiperTTS._play(self,path)

    def speak(self,text):
        if getattr(self,'turn_cancelled',threading.Event()).is_set():return False
        with self._lock:
            self._cancel.clear();text=self.text_processor(text).strip()
            if not text:return True
            path=Path(self._directory.name)/'speech.wav'
            try:
                data=self._cache.get(text)
                if data is None:
                    self._generating.set()
                    self._start()
                    if self._cancelled():raise InterruptedError('Ses işlemi iptal edildi.')
                    print('Seçilen ses üretiliyor: '+self.device,flush=True)
                    process=self._process
                    if process is None:raise InterruptedError('Ses işlemi iptal edildi.')
                    process.stdin.write(json.dumps({'text':text,'output':str(path)},ensure_ascii=True)+'\n');process.stdin.flush()
                    status=self._wait(300)
                    if status.get('type')!='done':raise RuntimeError('Ses çıktısı tamamlanmadı.')
                    self.device=status.get('device',self.device)
                    if status.get('reason'):print(status['reason'])
                    print(f'Referans ses üretimi: {status["seconds"]} sn | {self.device}')
                    self._generating.clear()
                    with wave.open(str(path),'rb') as audio:
                        if audio.getnframes()==0 or audio.getframerate()!=24000 or audio.getsampwidth()!=2 or audio.getnchannels()!=1:raise ValueError('Ses çıktısı bozuk.')
                    if path.stat().st_size<=8000000:
                        data=path.read_bytes();self._cache[text]=data
                        while len(self._cache)>16 or sum(map(len,self._cache.values()))>8000000:self._cache.popitem(last=False)
                else:self._cache.move_to_end(text);path.write_bytes(data)
                if self._cancelled():return False
                return self._play(str(path))
            except InterruptedError:self._kill();return False
            except Exception as exc:
                self._kill()
                if not self._cancelled():print('Referans ses hatası: '+type(exc).__name__+': '+str(exc)[:200])
                return False
            finally:
                self._generating.clear()
                try:path.unlink(missing_ok=True)
                except OSError:pass
