"""Exercise CUDA kernels before claiming GPU readiness; no model downloads here."""
import gc
import os
import numpy as np

def load_stt_model(factory, model_name, device, prepare_cuda=lambda:None):
    threads=max(2,min(8,(os.cpu_count() or 4)//2))
    compute='int8_float16' if device=='cuda' else 'int8'
    model=None
    try:
        if device=='cuda':prepare_cuda()
        model=factory(model_name,device=device,compute_type=compute,cpu_threads=threads)
        if device=='cuda':
            # CUDNN may load lazily: constructing the model alone is not a valid probe.
            segments,_=model.transcribe(np.zeros(16000,dtype=np.float32),language='tr',
                                       beam_size=1,vad_filter=False,condition_on_previous_text=False)
            list(segments)  # Trigger actual inference; discard synthetic output.
        return model,device
    except Exception as exc:
        if device!='cuda':raise
        print(f'⚠️ GPU tanıma testi başarısız ({type(exc).__name__}: {exc}). CPU ile devam.')
        model=None
        gc.collect()
        return factory(model_name,device='cpu',compute_type='int8',cpu_threads=threads),'cpu'
