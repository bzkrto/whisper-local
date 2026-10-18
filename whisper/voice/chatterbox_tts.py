"""Approved Turkish reference voice, isolated from the main application runtime."""
import re
from .reference_tts import ReferenceTTS
from . import chatterbox_setup as setup


class ChatterboxTTS(ReferenceTTS):
    name='Chatterbox V3 — seçilen ücretsiz referans ses'
    worker_module='whisper.voice.chatterbox_worker'

    def _home(self):return setup.voice_home()
    def _ready(self,home):return setup.ready(home)
    def _python(self,home):return setup.runtime_python(home)

    def speak(self,text):
        # The model has a bounded speech-token budget. Long sentences can omit words;
        # normalize before chunking, since verbalizing numbers expands the input.
        text=self.text_processor(text).strip()
        parts=[]
        while len(text)>220:
            breaks=list(re.finditer(r'[.!?;,]\s+|\s+',text[:221]))
            preferred=[m for m in breaks if m.start()>=100 and text[m.start()] in '.!?;,']
            cut=(preferred or breaks)[-1].end() if breaks else 220
            parts.append(text[:cut].strip());text=text[cut:].strip()
        if text:parts.append(text)
        for index,part in enumerate(parts):
            if index and self._cancelled():return False
            if not super().speak(part):return False
        return True

    def _cancelled(self):
        stop=getattr(self,'_warmup_stop',None)
        return super()._cancelled() or (stop is not None and stop.is_set())

    def warmup(self,stop_event=None):
        """Load once before the microphone reports readiness; do not play audio."""
        with self._lock:
            if stop_event is not None and stop_event.is_set():return False
            if getattr(self,'turn_cancelled',self._cancel).is_set():return False
            self._warmup_stop=stop_event
            self._cancel.clear();self._generating.set()
            try:
                self._start()
                return True
            except Exception as exc:
                self._kill()
                print('Seçilen ses açılamadı: '+type(exc).__name__+': '+str(exc)[:200])
                return False
            finally:self._generating.clear();self._warmup_stop=None
