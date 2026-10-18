"""Sequential, voice-free development session using one installed local model."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time


@contextmanager
def session_lock(root):
    """OS lock releases after a crash; a stale filename cannot block future sessions."""
    path=Path(root)/'.whisper-development-session.lock'
    with path.open('a+b') as stream:
        stream.seek(0);stream.write(b'0');stream.flush();stream.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:raise RuntimeError('Bir geliştirme oturumu zaten açık.') from exc
        try:yield
        finally:
            stream.seek(0)
            if os.name=='nt':msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(stream.fileno(),fcntl.LOCK_UN)


def test_environment(root,build=False):
    docker=shutil.which('docker')
    if not docker:return {'status':'blocked','response':'Docker Desktop kurulu değil veya docker PATH içinde yok. Docker Desktop Linux konteynerleriyle gerekli.'}
    try:
        server=subprocess.run([docker,'info','--format','{{.OSType}}'],capture_output=True,text=True,timeout=15)
        if server.returncode or server.stdout.strip()!='linux':
            return {'status':'blocked','response':'Docker Desktop çalışmıyor veya Linux konteynerleri seçili değil. Docker Desktop açıldıktan sonra tekrar başlatın.'}
        image=subprocess.run([docker,'image','inspect','--format','{{index .Config.Labels "org.whisper.test-runtime"}}',
                              'whisper-test:local'],capture_output=True,text=True,timeout=15)
        if image.returncode or image.stdout.strip()!='v32.13':
            if not build:return {'status':'blocked','response':'whisper-test:local test imajı bulunamadı.'}
            print('İzole test imajı hazırlanıyor; ilk kurulum internet gerektirir.',flush=True)
            made=subprocess.run([docker,'build','-t','whisper-test:local',str(Path(root)/'docker-test')],timeout=900)
            if made.returncode:return {'status':'blocked','response':'Test imajı kurulamadı; kod geliştirme başlatılmadı.'}
        return {'status':'ready','response':'Docker Linux test ortamı hazır.'}
    except (OSError,subprocess.TimeoutExpired) as exc:
        return {'status':'blocked','response':'Test ortamı kontrol edilemedi: '+type(exc).__name__}


class DevelopmentSession:
    def __init__(self,brain,profile='security',clock=time.monotonic):
        self.brain=brain;self.clock=clock;self.stop=threading.Event();self.next_research=0
        self.last_phase='ready';self.processed=0;self.drafts=0;self.updates=0
        brain.autonomous_research.set_profile(profile)
        brain.autonomous_research.enable(True);brain.self_development.enable(True)
        # Fast mode is an explicit user choice; remove the old ten-minute idle delay.
        with brain.self_development.connect() as db:
            db.execute("UPDATE self_development_settings SET value='0' WHERE key='next_run'")
        with brain.development_engine.connect() as db:
            db.execute("UPDATE development_meta SET value=0 WHERE key='next_analysis'")

    def step(self):
        b=self.brain
        if self.stop.is_set():return None
        self.last_phase='code'
        outcome=b.self_development.tick(b.llm,cancelled=self.stop,interval=60,
                                       knowledge_provider=b.knowledge_processor.recall)
        if outcome:
            if outcome.get('live_code_changed'):self.updates+=1
            return outcome
        if self.clock()>=self.next_research:
            self.last_phase='research';self.next_research=self.clock()+60
            result=b.autonomous_research.tick()
            if result and result.get('status')=='error':print('Kaynak okuma: '+str(result.get('detail',''))[:300],flush=True)
        if self.stop.is_set():return None
        self.last_phase='knowledge'
        card=b.knowledge_processor.tick(b.llm,self.stop)
        if card and card.get('status')=='processed':self.processed+=1
        if self.stop.is_set():return card
        b.development_engine.failures(b.autonomous_research)
        self.last_phase='proposal'
        draft=b.development_engine.tick(b.llm,self.stop,interval=60)
        if draft:
            if draft.get('status')=='draft':self.drafts+=1
            return draft
        self.last_phase='knowledge' if card else 'idle'
        return card

    def snapshot(self,outcome=None):
        b=self.brain
        with b.self_development.connect() as db:
            applied=db.execute("SELECT count(*) FROM self_development_jobs WHERE state IN ('restart_required','active')").fetchone()[0]
        memory={}
        try:
            import psutil
            memory['application_rss_mb']=round(psutil.Process().memory_info().rss/1048576,1)
            memory['scope']='Yalnız Whisper istemcisi; Ollama sunucusu ve GPU belleği bu ölçüme dahil değil.'
        except (ImportError,OSError):pass
        return {'mode':'single_model_security_development','model':getattr(b.llm,'model',''),
                'phase':self.last_phase,'session_processed_chunks':self.processed,
                'session_drafts':self.drafts,'session_applied_updates':self.updates,
                'total_updated_jobs':applied,'memory':memory,'last_llm_metrics':getattr(b.llm,'last_metrics',{}),
                'last_result':outcome,'learning_status':b.knowledge_processor.daily_summary(),
                'development_status':b.self_development.report(),
                'note':'Kaynak hafızası ve test edilmiş uygulama kodu gelişir; model ağırlıkları eğitilmez.'}


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--build-test-image',action='store_true')
    parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--profile',choices=('security','development'),default='security')
    parser.add_argument('--max-steps',type=int,default=0)
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[2]
    ready=test_environment(root,build=args.build_test_image and not args.check_only)
    print(ready['response'],flush=True)
    if ready['status']!='ready':return 1
    if args.check_only:return 0
    from whisper_ses_v12 import Config,WhisperBrain,OpenAICompatLLM,OllamaLLM
    names=OpenAICompatLLM.list_models('http://127.0.0.1:11434/v1','',timeout=5)
    model=next((name for name in ('qwen2.5-coder:7b','qwen3:8b') if name in names),None)
    if not model:
        print('Ollama açık olmalı; mevcut qwen2.5-coder:7b veya qwen3:8b modeli gerekli. Otomatik model indirilmedi.',flush=True)
        return 1
    cfg=Config(model=model,tts_engine='none',voice_loop_enabled=False,tools_enabled=True,internet=True,
               llm_context=6144,model_roles={'chat':model,'code':model})
    cfg._mode_text=True
    brain=WhisperBrain(cfg)
    if not isinstance(brain.llm,OllamaLLM):
        print('Geliştirme modu için yerel Ollama bağlantısı gerekli.',flush=True);return 1
    brain.llm.low_memory=True
    try:brain.llm.release_for_voice(['qwen3:8b','qwen2.5-coder:7b'])
    except Exception as exc:print('Önceki uygulama modeli boşaltılamadı: '+type(exc).__name__,flush=True)
    session=DevelopmentSession(brain,args.profile)
    print('Geliştirme açık: ses/STT yüklenmez; tek model, 128 işlem grubu, en fazla 4 CPU iş parçacığı. Durdurmak için Ctrl+C.',flush=True)
    report=root/'WHISPER_GELISIM_RAPORU.json';steps=0
    try:
        while not session.stop.is_set():
            result=session.step();steps+=1
            report.write_text(json.dumps(session.snapshot(result),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            if result:print(session.last_phase+': '+json.dumps(result,ensure_ascii=False),flush=True)
            if result and result.get('restart_required'):
                print('Test edilmiş güncelleme uygulandı; başlatıcı yeni kodla oturumu yenileyecek.',flush=True)
                return 42
            if args.max_steps and steps>=args.max_steps:return 0
            if result is None:session.stop.wait(5)
    except KeyboardInterrupt:
        session.stop.set();print('\nGeliştirme durduruldu.',flush=True)
    except Exception as exc:
        session.stop.set()
        print('Geliştirme durduruldu: '+type(exc).__name__+': '+str(exc)[:500],flush=True)
        return 1
    finally:brain.close_services()
    return 0


if __name__=='__main__':raise SystemExit(main())
