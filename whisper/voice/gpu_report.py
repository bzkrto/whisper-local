"""Read-only GPU diagnostics. No model loads, recordings, secrets or paid API calls."""
import http.client
import json
from pathlib import Path
import shutil
import subprocess
import sys
from .chatterbox_setup import voice_home,runtime_python

TORCH_PROBE="""
import json,torch
d={'torch':torch.__version__,'cuda_build':torch.version.cuda,'cuda_available':torch.cuda.is_available()}
if d['cuda_available']:
    try:
        free,total=torch.cuda.mem_get_info()
        d.update(gpu=torch.cuda.get_device_name(0),capability=list(torch.cuda.get_device_capability(0)),
                 free_mb=round(free/1048576),total_mb=round(total/1048576),compiled_arches=torch.cuda.get_arch_list())
        x=torch.ones((16,16),device='cuda');x=x@x;torch.cuda.synchronize()
        d['kernel_ok']=True
    except Exception as e:d.update(kernel_ok=False,kernel_error=str(e)[:500])
print(json.dumps(d))
"""
STT_PROBE="""
import json,ctranslate2
print(json.dumps({'ctranslate2':ctranslate2.__version__,'cuda_devices':ctranslate2.get_cuda_device_count()}))
"""

def probe(python,code):
    if not Path(python).is_file():return {'error':'Ses Python ortamı bulunamadı.'}
    try:
        r=subprocess.run([str(python),'-c',code],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=45)
        if r.returncode:return {'error':r.stderr.strip().splitlines()[-1][:500] if r.stderr.strip() else 'Alt işlem başarısız.'}
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (OSError,ValueError,IndexError,subprocess.TimeoutExpired) as exc:return {'error':type(exc).__name__}

def ollama_memory():
    connection=http.client.HTTPConnection('127.0.0.1',11434,timeout=5)
    try:
        connection.request('GET','/api/ps');response=connection.getresponse()
        if response.status!=200:return {'status':response.status}
        data=json.loads(response.read(1000000))
        return [{'model':str(m.get('name',''))[:100],'vram_mb':round(int(m.get('size_vram',0))/1048576)}
                for m in data.get('models',[])[:10]]
    except (OSError,ValueError,http.client.HTTPException) as exc:return {'error':type(exc).__name__}
    finally:connection.close()

def collect():
    report={'speech_runtime':probe(runtime_python(voice_home()),TORCH_PROBE),
            'speech_recognition':probe(sys.executable,STT_PROBE),'ollama_models':ollama_memory()}
    executable=shutil.which('nvidia-smi')
    if executable:
        try:
            result=subprocess.run([executable,'--query-gpu=name,driver_version,memory.total,memory.free',
                                   '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10)
            report['nvidia_smi']=result.stdout.strip()[:1000] if result.returncode==0 else 'nvidia-smi sorgusu başarısız.'
        except (OSError,subprocess.TimeoutExpired) as exc:report['nvidia_smi']=type(exc).__name__
    else:report['nvidia_smi']='nvidia-smi bulunamadı.'
    return report

def main():
    report=collect();text=json.dumps(report,ensure_ascii=False,indent=2)
    path=Path(__file__).resolve().parents[2]/'WHISPER_GPU_RAPORU.txt'
    path.write_text(text+'\n',encoding='utf-8')
    print(text);print('\nWHISPER_GPU_RAPORU.txt kaydedildi. Bu kontrol model indirmez ve kayıt/API anahtarı okumaz.')

if __name__=='__main__':main()
