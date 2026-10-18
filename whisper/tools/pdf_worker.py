"""Isolated text extraction worker. PDF actions and embedded files are not executed."""
import json,sys

def extract(path):
    from pypdf import PdfReader
    reader=PdfReader(path)
    if reader.is_encrypted:raise ValueError('Şifreli PDF bu sürümde desteklenmiyor.')
    if len(reader.pages)>1000:raise ValueError('En fazla 1000 sayfa destekleniyor.')
    pages=[];total=0
    for i,page in enumerate(reader.pages,1):
        text=page.extract_text() or ''
        total+=len(text)
        if total>5_000_000:raise ValueError('Çıkarılan metin 5 milyon karakter sınırını aştı.')
        if text.strip():pages.append({'page':i,'text':text})
    return {'page_count':len(reader.pages),'pages':pages}

def main():
    # Pipes on Windows may default to a legacy code page. Use bytes explicitly.
    try:
        args=json.loads(sys.stdin.buffer.read().decode('utf-8'))
        result=extract(args['path'])
        code=0
    except ImportError:
        result={'error':'pypdf eksik. Sanal ortamda python -m pip install pypdf çalıştırın.'}
        code=1
    except Exception as exc:
        message=str(exc) if isinstance(exc,ValueError) else 'PDF metni okunamadı: '+type(exc).__name__
        result={'error':message}
        code=1
    sys.stdout.buffer.write(json.dumps(result,ensure_ascii=True).encode('utf-8')+b'\n')
    sys.stdout.buffer.flush()
    return code

if __name__=='__main__':
    sys.exit(main())
