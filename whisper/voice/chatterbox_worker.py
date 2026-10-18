"""Local JSON-lines Chatterbox V3 worker with bounded output and CUDA fallback."""
import contextlib
import gc
import json
import os
from pathlib import Path
import random
import sys
import time

from . import chatterbox_setup as setup

def send(data):print(json.dumps(data,ensure_ascii=True),file=sys.__stdout__,flush=True)

def select_device(torch,requested='auto'):
    if requested not in ('auto','cpu','cuda'):raise ValueError('WHISPER_CHATTERBOX_DEVICE auto, cpu veya cuda olmalı.')
    if requested=='cpu':return 'cpu','CPU ses cihazı elle seçildi.'
    if not torch.cuda.is_available():
        if requested=='cuda':raise RuntimeError('CUDA ses ortamında bulunamadı.')
        return 'cpu','CUDA ses ortamında bulunamadı; CPU kullanılacak. CPU üzerinde yeni cümle üretimi yavaştır.'
    try:free,_=torch.cuda.mem_get_info()
    except RuntimeError:
        if requested=='cuda':raise
        return 'cpu','CUDA boş bellek bilgisi alınamadı; CPU kullanılacak.'
    free_mb=int(free/(1024*1024))
    if free_mb<6144:
        if requested=='cuda':raise RuntimeError(f'Ses için boş GPU belleği yetersiz: {free_mb} MB; en az 6144 MB gerekli.')
        return 'cpu',f'Boş GPU belleği {free_mb} MB; ses için en az 6144 MB ayrılmalı. CPU kullanılacak.'
    return 'cuda',f'Ses için CUDA seçildi; başlangıçtaki boş GPU belleği {free_mb} MB.'

def cuda_failure(torch,exc):
    return isinstance(exc,torch.cuda.OutOfMemoryError) or any(s in str(exc).lower() for s in
        ('cuda out of memory','no kernel image','not compiled with cuda','cuda-capable device','driver version is insufficient'))

def validate_job(job,output):
    if not isinstance(job,dict):raise ValueError('Ses işi nesne olmalı.')
    text=job.get('text')
    if not isinstance(text,str) or not 1<=len(text.strip())<=1500:raise ValueError('Ses metni boyutu geçersiz.')
    if not isinstance(job.get('output'),str):raise ValueError('Ses çıktı yolu geçersiz.')
    path=Path(job['output']).resolve()
    if path.parent!=output or path.suffix!='.wav':raise ValueError('Ses çıktı yolu geçersiz.')
    return text,path

def load_model(torch,model_type,home,device):
    # A local model never downloads or calls a paid API during synthesis.
    model=model_type.from_local(home/'model',device=device,t3_model='v3')
    send({'type':'progress','message':'Seçilen sesin referans kaydı hazırlanıyor…'})
    model.prepare_conditionals(str(home/'reference.wav'),exaggeration=.35)
    return model

def main():
    home=Path(sys.argv[1]).resolve();output=Path(sys.argv[2]).resolve()
    if not output.is_dir() or not setup.ready(home):raise RuntimeError('Seçilen ses kurulumu eksik veya referans değişmiş.')
    setup.configure_runtime(home)
    send({'type':'progress','message':'Ses dosyaları doğrulanıyor (yaklaşık 3,2 GB)…'})
    # Verify weights and auxiliary data before loading any model or serialized tensor.
    for name,(size,sha) in setup.FILES.items():
        if not setup.verify(home/'model'/name,size,sha):raise ValueError('Ses modeli SHA256 doğrulaması başarısız: '+name)
    for name,(size,sha) in setup.TOKENIZER_FILES.items():
        if not setup.verify(home/'cache'/'pkuseg'/'spacy_ontonotes'/name,size,sha):raise ValueError('Ses tokenizer doğrulaması başarısız: '+name)
    if not setup.verify(home/'cache'/'pkuseg'/'spacy_ontonotes.zip',*setup.TOKENIZER_ZIP):raise ValueError('Ses tokenizer arşivi doğrulanamadı.')
    mapping=home/'model'/'models--ResembleAI--chatterbox'/'snapshots'/setup.REVISION/'Cangjie5_TC.json'
    if not setup.verify(mapping,*setup.FILES['Cangjie5_TC.json']):raise ValueError('Ses tokenizer eşleme önbelleği doğrulanamadı.')
    with contextlib.redirect_stdout(sys.stderr):
        import numpy as np
        import torch
        import soundfile as sf
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        torch.set_num_threads(min(4,os.cpu_count() or 1));torch.set_num_interop_threads(1)
        random.seed(42);np.random.seed(42);torch.manual_seed(42)
        requested=os.environ.get('WHISPER_CHATTERBOX_DEVICE','auto')
        device,reason=select_device(torch,requested)
        send({'type':'progress','message':reason})
        send({'type':'progress','message':'Chatterbox V3 modeli yükleniyor: '+device})
        try:model=load_model(torch,ChatterboxMultilingualTTS,home,device)
        except RuntimeError as exc:
            if requested!='auto' or device!='cuda' or not cuda_failure(torch,exc):raise
            send({'type':'progress','message':'CUDA hata ayrıntısı: '+str(exc)[:250]})
            gc.collect();torch.cuda.empty_cache();device='cpu'
            reason='CUDA modeli yüklenemedi; aynı seçilen ses CPU üzerinde hazırlandı.'
            model=load_model(torch,ChatterboxMultilingualTTS,home,device)
        if device=='cpu' and torch.cuda.is_available():torch.cuda.empty_cache()
    send({'type':'ready','device':device,'reason':reason})
    for line in sys.stdin:
        try:
            text,path=validate_job(json.loads(line),output)
            started=time.monotonic();fallback=''
            with contextlib.redirect_stdout(sys.stderr),torch.inference_mode():
                try:audio=model.generate(text,language_id='tr',exaggeration=.35,cfg_weight=.5,temperature=.65)
                except RuntimeError as exc:
                    if requested!='auto' or device!='cuda' or not cuda_failure(torch,exc):raise
                    send({'type':'progress','message':'CUDA hata ayrıntısı: '+str(exc)[:250]})
                    del model;gc.collect();torch.cuda.empty_cache();device='cpu'
                    model=load_model(torch,ChatterboxMultilingualTTS,home,device)
                    fallback='GPU belleği ses üretiminde yetmedi; aynı ses CPU üzerinde üretildi.'
                    audio=model.generate(text,language_id='tr',exaggeration=.35,cfg_weight=.5,temperature=.65)
                if fallback:torch.cuda.empty_cache()
                values=audio.squeeze().detach().cpu().numpy()
                if model.sr!=24000 or values.ndim!=1 or values.size==0 or not np.isfinite(values).all():
                    raise ValueError('Ses modeli geçerli PCM çıktı üretmedi.')
                sf.write(str(path),values,model.sr,subtype='PCM_16')
            send({'type':'done','seconds':round(time.monotonic()-started,2),'device':device,'reason':fallback})
        except Exception as exc:send({'type':'error','error':type(exc).__name__+': '+str(exc)[:200]})

if __name__=='__main__':
    try:main()
    except Exception as exc:send({'type':'error','error':type(exc).__name__+': '+str(exc)[:200]});raise SystemExit(1)
