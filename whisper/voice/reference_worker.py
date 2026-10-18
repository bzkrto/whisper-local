"""JSON-lines synthesis worker. Runs only in the isolated voice environment."""
import contextlib
import json
import os
from pathlib import Path
import sys
import time
from .reference_setup import FILES,verify

def send(data):print(json.dumps(data,ensure_ascii=True),flush=True)

def main():
    home=Path(sys.argv[1]).resolve();output=Path(sys.argv[2]).resolve()
    os.environ.setdefault('MPLCONFIGDIR',str(home/'cache'/'matplotlib'))
    os.environ.setdefault('XDG_CACHE_HOME',str(home/'cache'))
    with contextlib.redirect_stdout(sys.stderr):
        import torch
        import soundfile as sf
        from TTS.tts.configs.xtts_config import XttsConfig
        from TTS.tts.models.xtts import Xtts
        for name,(size,sha) in FILES.items():
            if not verify(home/'model'/name,size,sha):raise ValueError('Ses modeli doğrulanamadı: '+name)
        torch.set_num_threads(4)
        cfg=XttsConfig();cfg.load_json(str(home/'model'/'config.json'))
        model=Xtts.init_from_config(cfg);model.load_checkpoint(cfg,checkpoint_dir=str(home/'model'),eval=True)
        device='cpu'
        if torch.cuda.is_available():
            free,_=torch.cuda.mem_get_info()
            if free>=2800*1024*1024:
                try:model.to('cuda');device='cuda'
                except torch.cuda.OutOfMemoryError:model.to('cpu');torch.cuda.empty_cache()
        conditioning,embedding=model.get_conditioning_latents(audio_path=[str(home/'reference.wav')])
    send({'type':'ready','device':device})
    for line in sys.stdin:
        try:
            job=json.loads(line);text=job['text'];path=Path(job['output']).resolve()
            if not isinstance(text,str) or not 1<=len(text)<=1500:raise ValueError('Ses metni boyutu geçersiz.')
            if path.parent!=output or path.suffix!='.wav':raise ValueError('Ses çıktı yolu geçersiz.')
            started=time.monotonic()
            with contextlib.redirect_stdout(sys.stderr),torch.inference_mode():
                result=model.inference(text,'tr',conditioning,embedding,temperature=.65,repetition_penalty=3.,enable_text_splitting=True)
                sf.write(str(path),result['wav'],24000,subtype='PCM_16')
            send({'type':'done','seconds':round(time.monotonic()-started,2)})
        except Exception as exc:send({'type':'error','error':type(exc).__name__+': '+str(exc)[:200]})

if __name__=='__main__':
    try:main()
    except Exception as exc:send({'type':'error','error':type(exc).__name__+': '+str(exc)[:200]});raise SystemExit(1)
