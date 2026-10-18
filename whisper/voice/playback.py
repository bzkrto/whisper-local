"""WAV output: asynchronous Windows playback independent of PortAudio input."""
import os
import threading
import time
import wave

def play_wav(path,cancelled):
    with wave.open(str(path),'rb') as source:
        if source.getsampwidth()!=2 or source.getnframes()==0:raise ValueError('PCM ses çıktısı geçersiz.')
        rate,channels=source.getframerate(),source.getnchannels()
        duration=source.getnframes()/rate
    if cancelled():return False
    if os.name=='nt':
        import winsound
        try:
            winsound.PlaySound(str(path),winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
            deadline=time.monotonic()+duration+.05
            wait=threading.Event()
            while time.monotonic()<deadline:
                if cancelled():return False
                wait.wait(min(.02,max(0,deadline-time.monotonic())))
            return not cancelled()
        finally:winsound.PlaySound(None,0)
    import sounddevice as sd
    with wave.open(str(path),'rb') as source:
        with sd.RawOutputStream(samplerate=rate,channels=channels,dtype='int16') as output:
            while True:
                if cancelled():output.abort();return False
                block=source.readframes(1024)
                if not block:break
                output.write(block)
    return not cancelled()
