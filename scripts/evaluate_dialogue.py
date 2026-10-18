"""Real local-model routing probe with temporary memory and fail-closed tools.

This is not an automated score for factual accuracy or natural Turkish. The JSON
report includes actual replies for review. No model is downloaded or service started.
"""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import whisper_ses_v12 as core
from whisper.tools.file_manager import FileManager


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--backend',choices=('ollama','llamacpp','lmstudio'),default='ollama')
    parser.add_argument('--base-url',default='http://127.0.0.1:11434/v1')
    parser.add_argument('--model',required=True)
    parser.add_argument('--max-tokens',type=int,default=96)
    args=parser.parse_args(argv)
    if not 1<=args.max_tokens<=512:parser.error('--max-tokens must be 1–512.')
    if not core.is_loopback_url(args.base_url):parser.error('Only a local loopback model endpoint is allowed.')
    calls={'chat':0,'plan':0,'tools':0};turns=[]
    with tempfile.TemporaryDirectory(prefix='whisper-dialogue-eval-') as tmp:
        cfg=core.Config(backend=args.backend,base_url=args.base_url,model=args.model,
            db_path=str(Path(tmp)/'evaluation.db'),tools_enabled=True,internet=False,
            tts_engine='none',voice_loop_enabled=False,tts_sentence_stream=False,
            max_tokens=args.max_tokens,request_timeout=60)
        cfg._mode_text=True
        with redirect_stdout(io.StringIO()):brain=core.WhisperBrain(cfg)
        if brain.llm is None:
            print(json.dumps({'routing_passed':False,'error':'Local model endpoint unavailable.'}))
            return 1
        client=brain.llm;chat=client.chat;plan=client.chat_json
        def observed_chat(*a,**kw):
            calls['chat']+=1
            return chat(*a,**kw)
        def observed_plan(*a,**kw):
            calls['plan']+=1
            return plan(*a,**kw)
        def reject_tools(*a,**kw):
            calls['tools']+=1
            raise RuntimeError('Host tools are disabled by the evaluation harness.')
        client.chat=observed_chat;client.chat_json=observed_plan
        brain._agent_tool=reject_tools
        brain.tool_runner.run=reject_tools
        brain.file_manager=FileManager(opener=reject_tools)
        brain.file_manager.roots=[]
        brain.file_manager._open=reject_tools
        try:
            script=[('fresh','nasılsın'),('followup','siber güvenlik'),
                    ('pending','nasılsın'),('followup','siber güvenlik'),
                    ('pending','nasilssin'),('expired','siber güvenlik'),('profile','nasılsın'),
                    ('followup','hayır, konuyu değiştirelim: mantıksal tutarlılık')]
            for state,text in script:
                if state=='profile':brain.profile_interview.next_question()
                if state in ('pending','expired'):
                    brain.agent.ask_followup('Bir konuyu araştır','Hangi konuyu araştırayım?')
                    if state=='expired':brain.agent.dialogue.pending['created']-=brain.agent.dialogue.ttl+1
                with redirect_stdout(io.StringIO()):result=brain.process_command(text)
                turns.append({'state':state,'user':text,'status':result['status'],
                              'route':result.get('route'),'response':result['response']})
        finally:brain.close_services()
    passed=all(t['status']=='success' and t['route'].get('target')=='llm' for t in turns) and not calls['plan'] and not calls['tools']
    print(json.dumps({'model':args.model,'backend':args.backend,'responses':'real local HTTP',
        'routing_passed':passed,'quality_scored':False,'host_tool_execution':False,
        'calls':calls,'turns':turns},ensure_ascii=False,indent=2))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
