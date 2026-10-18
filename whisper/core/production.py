"""Bounded PDF production workflow using the existing source-checked answer engine.

No generated code execution, web research, model training or autonomous PC actions.
The store protocol is path/connect()/now(); inference is injected via llm.chat().
"""
import json
import re
import uuid
from urllib.parse import urlsplit
from pathlib import Path

from ..common import SOURCES, fold
from ..memory.document_memory import DocumentMemory
from ..memory.document_answer import parse_question, answer_from_documents, save_answer_report
from ..tools.report_export import export_report


class ProductionWorkflow:
    STEPS = ('Kaynakları bul', 'Kaynaklı cevap üret', 'Markdown raporu kaydet',
             'Word oluştur', 'PDF oluştur', 'PowerPoint oluştur')

    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS production_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request TEXT NOT NULL, created_at TEXT NOT NULL,
                    state TEXT NOT NULL, steps TEXT NOT NULL,
                    artifacts TEXT NOT NULL, sources TEXT NOT NULL,
                    error TEXT NOT NULL DEFAULT '');
            ''')

    @staticmethod
    def result(text, status='success', **extra):
        return dict(status=status, response=text, spoken_response=text,
                    source=SOURCES[2],
                    route={'target': 'production', 'reason': 'Kaynaklı PDF üretim zinciri'},
                    **extra)

    def intercept(self, command):
        t = fold(command)
        if t.startswith(('pdf uretim paketi:', 'arastirma paketi:')):
            body = command.split(':', 1)[1].strip()
            question, _, _ = parse_question(body)
            if not 3 <= len(question) <= 1000 or len(body) > 1200:
                return self.result('Konu 3–1000 karakter olmalı. Örnek: PDF üretim paketi: '
                                   'belge 1; karar değiştirme', 'clarification')
            return self.result('Üretim isteği hazır.', production_request=body,
                               production_kind='research' if t.startswith('arastirma paketi:') else 'pdf')
        m = re.fullmatch(r'uretim durumu\s*:\s*(\d+)', t)
        if m:
            return self.show(int(m[1]))
        if t == 'uretimlerim':
            with self.store.connect() as db:
                rows = db.execute('SELECT id,request,state FROM production_runs ORDER BY id DESC LIMIT 20').fetchall()
            return self.result('\n'.join(f'{i}: {request} | {state}' for i, request, state in rows)
                               or 'Kayıtlı üretim yok.')
        return None

    def show(self, run_id):
        with self.store.connect() as db:
            row = db.execute('SELECT request,state,steps,artifacts,sources,error FROM production_runs WHERE id=?',
                             (run_id,)).fetchone()
        if row is None:
            return self.result('Üretim kaydı bulunamadı.', 'error')
        request, state, steps_raw, artifacts_raw, sources_raw, error = row
        steps, artifacts = json.loads(steps_raw), json.loads(artifacts_raw)
        missing = [a['path'] for a in artifacts if not Path(a['path']).is_file()]
        labels = {'pending': 'Bekliyor', 'running': 'Başlatıldı; tamamlanma kaydı yok',
                  'done': 'Tamamlandı', 'failed': 'Başarısız', 'blocked': 'Kaynak/cevap yetersiz',
                  'cancelled': 'İptal edildi'}
        text = f'Üretim {run_id}: {request}\nDurum: {state}\n'
        text += '\n'.join(f"{i}. {s['title']}: {labels.get(s['state'], s['state'])}"
                          for i, s in enumerate(steps, 1))
        text += '\n\nDosyalar:\n' + ('\n'.join(a['path'] for a in artifacts) or 'Henüz dosya yok.')
        if error:
            text += '\n\nAçıklama: ' + error
        if missing:
            text += '\n\nArtık bulunamayan dosyalar:\n' + '\n'.join(missing)
        if state == 'running':
            text += '\nBu kayıt işlem sürerken veya uygulama kapanınca kalabilir; tamamlandı sayılmaz.'
        text += '\nKaynak dökümü veya model özeti bağımsız doğrulanmış bilgi değildir.'
        result = self.result(text, state if state != 'completed' else 'success',
                             run_id=run_id, artifacts=artifacts, missing_artifacts=missing,
                             document_sources=[x for x in json.loads(sources_raw) if 'document_id' in x],
                             sources=[x for x in json.loads(sources_raw) if 'url' in x],
                             answer_verified=False)
        result['spoken_response'] = (f'Üretim {run_id} tamamlandı. Dört dosya hazır. Dosya yolları ekranda.'
                                    if state == 'completed' and not missing else
                                    f'Üretim {run_id} durumu ekranda. Tüm çıktılar hazır değil.')
        if missing and state == 'completed':
            result['status'] = 'partial'
        return result

    def run(self, body, llm, cancelled=None, research=None):
        question, did, page = parse_question(body)
        if not 3 <= len(question) <= 1000 or len(body) > 1200:
            return self.result('Geçerli bir üretim konusu belirtin.', 'clarification')
        # Do not write through a pre-existing directory link.
        folder = Path(self.store.path).resolve().parent / 'raporlar'
        if folder.is_symlink() or getattr(folder, 'is_junction', lambda: False)():
            return self.result('Rapor klasörü bağlantı olamaz.', 'error')
        titles = list(self.STEPS)
        if research is not None:
            if not 3 <= len(body) <= 200:
                return self.result('Araştırma konusu 3–200 karakter olmalı.', 'clarification')
            titles[:2] = ['Web araştırmasını kaydet', 'Kaynak dökümünü hazırla']
        steps = [dict(title=title, state='pending') for title in titles]
        artifacts, sources = [], []
        with self.store.connect() as db:
            run_id = db.execute('INSERT INTO production_runs(request,created_at,state,steps,artifacts,sources) '
                                'VALUES(?,?,?,?,?,?)',
                                (body, self.store.now(), 'running', json.dumps(steps), '[]', '[]')).lastrowid

        def save(state='running', error=''):
            with self.store.connect() as db:
                db.execute('UPDATE production_runs SET state=?,steps=?,artifacts=?,sources=?,error=? WHERE id=?',
                           (state, json.dumps(steps, ensure_ascii=False), json.dumps(artifacts, ensure_ascii=False),
                            json.dumps(sources, ensure_ascii=False), error, run_id))

        def check_cancel():
            if cancelled is not None and cancelled.is_set():
                raise ProductionCancelled()

        def begin(index):
            check_cancel()
            steps[index]['state'] = 'running'
            save()

        def artifact(path, format):
            path = Path(path)
            if not path.is_file() or path.stat().st_size == 0:
                raise OSError('Çıktı dosyası doğrulanamadı.')
            artifacts.append(dict(format=format, path=str(path.resolve()), bytes=path.stat().st_size))

        index = 0
        try:
            begin(index)
            if research is None:
                found = DocumentMemory(self.store).search(question, document_id=did, page=page)
                sources = found.get('document_sources', [])
                if not sources:
                    steps[index]['state'] = 'blocked'
                    save('blocked', found['response'])
                    return self.show(run_id)
                steps[index]['state'] = 'done'
                index = 1
                begin(index)
                answer = answer_from_documents(llm, {**found, 'document_question': question})
                check_cancel()
                if answer.get('status') != 'success':
                    steps[index]['state'] = 'blocked'
                    save('blocked', answer['response'])
                    return self.show(run_id)
                sources = answer['document_sources']
                steps[index]['state'] = 'done'
                index = 2
                begin(index)
                report = save_answer_report({**answer, 'document_report_question': question}, self.store.path)
                if report.get('status') != 'success' or not report.get('artifact_path'):
                    raise OSError('Markdown raporu kaydedilemedi.')
            else:
                evidence = research(body)
                check_cancel()
                if evidence.get('status') != 'success':
                    steps[index]['state'] = 'blocked'
                    save('blocked', evidence.get('response', 'Araştırma başarısız.'))
                    return self.show(run_id)
                rid = evidence.get('research_id')
                if type(rid) is not int or rid < 1:
                    raise ValueError('Araştırmanın kayıt kimliği eksik.')
                steps[index]['state'] = 'done'
                index = 1
                begin(index)
                from ..memory.research_memory import ResearchMemory
                snapshot = ResearchMemory(self.store.path).get(rid)
                if snapshot is None:
                    raise ValueError('Araştırma kaydı bulunamadı.')
                sources = snapshot['sources']
                markdown = research_markdown(question, snapshot)
                steps[index]['state'] = 'done'
                index = 2
                begin(index)
                folder.mkdir(exist_ok=True)
                destination = folder / ('arastirma_raporu_' + uuid.uuid4().hex[:12] + '.md')
                created = False
                try:
                    with destination.open('x', encoding='utf-8') as stream:
                        created = True
                        stream.write(markdown)
                except OSError:
                    if created:
                        destination.unlink(missing_ok=True)
                    raise
                report = {'artifact_path': str(destination)}
            artifact(report['artifact_path'], 'md')
            steps[index]['state'] = 'done'
            save()
        except ProductionCancelled:
            steps[index]['state'] = 'cancelled'
            save('cancelled', 'Üretim durduruldu; önceki çıktılar korundu.')
            return self.show(run_id)
        except Exception as exc:
            if cancelled is not None and cancelled.is_set():
                steps[index]['state'] = 'cancelled'
                save('cancelled', 'Üretim durduruldu; önceki çıktılar korundu.')
                return self.show(run_id)
            steps[index]['state'] = 'failed'
            save('partial' if artifacts else 'error', f'{titles[index]}: {type(exc).__name__}')
            return self.show(run_id)

        # Independent exports continue after a failed format; never claim complete success.
        errors = []
        for index, format in enumerate(('docx', 'pdf', 'pptx'), 3):
            try:
                begin(index)
                destination = export_report(self.store.path, Path(report['artifact_path']).name, format)
                artifact(destination, format)
                steps[index]['state'] = 'done'
            except ProductionCancelled:
                steps[index]['state'] = 'cancelled'
                save('cancelled', 'Üretim durduruldu; önceki çıktılar korundu.')
                return self.show(run_id)
            except Exception as exc:
                steps[index]['state'] = 'failed'
                errors.append(f'{format}: {exc}' if isinstance(exc, ValueError) else f'{format}: {type(exc).__name__}')
            save()
        if cancelled is not None and cancelled.is_set():
            save('cancelled', 'Üretim sırasında iptal istendi; oluşan dosyalar korundu.')
        else:
            save('partial' if errors else 'completed', '; '.join(errors))
        return self.show(run_id)


class ProductionCancelled(Exception):
    pass


def research_markdown(question, snapshot):
    """Preserve one exact search snapshot; do not invent source attribution or synthesis."""
    from datetime import datetime, timezone
    sources = snapshot['sources']
    if not isinstance(sources, list) or not sources or len(sources) > 50:
        raise ValueError('Araştırma kaynakları eksik veya sınırı aşıyor.')
    lines = []
    for i, source in enumerate(sources, 1):
        if not isinstance(source, dict) or not isinstance(source.get('url'), str):
            raise ValueError('Kaynak adresi eksik.')
        url = urlsplit(source['url'])
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
            raise ValueError('Geçersiz kaynak adresi.')
        lines.append(f"[{i}] {source.get('title', 'Kaynak')}\n{source['url']}")
    timestamp = datetime.fromtimestamp(snapshot['retrieved_at'], timezone.utc).isoformat()
    text = ('# Araştırma kaynak dökümü\n\nSoru: ' + question +
            '\n\nAraştırma kaydı: ' + str(snapshot['id']) +
            '\nErişim zamanı (UTC): ' + timestamp +
            '\nKaynak türü: ' + snapshot['source_type'] +
            '\n\nBu dosya kayıtlı kaynak metni/arama özetlerinin dökümüdür. '
            'Tam makale incelemesi, doğrulanmış analiz veya fizibilite değildir.\n\n' +
            snapshot['body'] + '\n\nKaynaklar:\n' + '\n\n'.join(lines) + '\n')
    if len(text.encode('utf-8')) > 240000:
        raise ValueError('Araştırma dökümü çıktı sınırını aşıyor.')
    return text
