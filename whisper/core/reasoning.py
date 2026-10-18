from __future__ import annotations
import json, re, sqlite3, subprocess, time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from ..common import *
from ..memory.user_memory import LayerStore
from ..tools.github_manager import GitBrain, GitHubBrain
from ..memory.vector_memory import VectorMemory
from ..memory.project_memory import ProjectMemory
from ..learning.self_analysis import SelfAnalysis

@dataclass(frozen=True)
class Route:
    target: str
    reason: str
    role: str = 'chat'

def conversational_turn(text):
    """Only standalone social turns; mixed requests still use semantic planning."""
    text = re.sub(r'[.!?,]+', ' ', fold(text))
    text = re.sub(r'\s+', ' ', text).strip()
    return bool(re.fullmatch(
        r'(?:(?:hey )?whisper )?(?:merhaba|selam|selamlar|nasilsin|nasilsiniz|'
        r'ne haber|naber|ne yapiyorsun|neler yapiyorsun|ne yapiyorsunuz|'
        r'beni duyuyor musun|sesim geliyor mu|orada misin|tesekkur ederim|'
        r'tesekkurler|sag ol|gunaydin|iyi aksamlar|iyi geceler|'
        r'seninle sohbet etmek istiyorum|biraz sohbet edelim)', text))

class ReasoningRouter:
    """Decides the execution path; does not pretend to expose model thoughts."""

    def decide(self, text, *, desktop=False, tool=False, fast=False):
        if desktop or tool:
            return Route('pc', 'İzinli bilgisayar komutu')
        if fast:
            return Route('fast', 'Model gerektirmeyen araç veya hafıza sorgusu')
        t = fold(text)
        if re.search('\\b(bugun|guncel|haber|duyurdu|son dakika|bu hafta|fiyat|kac tl|internette|arastir)\\b', t):
            return Route('web', 'Güncel veya dış kaynak gerektiren soru')
        if re.search('\\b(kod|python|javascript|typescript|programlama|debug|bug|fonksiyon|refactor)\\b', t):
            return Route('llm', 'Kod geliştirme sorusu', 'code')
        if re.search('\\b(mantik|matematik|denklem|ispat|problem|hesapla|analiz)\\b', t):
            return Route('llm', 'Analiz veya problem çözümü', 'reason')
        if re.search('\\b(cevir|ozetle|kisalt)\\b', t):
            return Route('llm', 'Kısa metin görevi', 'fast')
        return Route('llm', 'Genel bilgi veya sohbet', 'chat')

class AssistantLayers:

    def __init__(self, db_path, repo=None, github_repo=None, internet=False):
        self.store = LayerStore(db_path)
        self.project = ProjectMemory(self.store)
        self.vectors = VectorMemory(self.store)
        self.analysis = SelfAnalysis(self.store)
        self.router = ReasoningRouter()
        self.git = GitBrain(repo)
        self.github = GitHubBrain(github_repo, internet)
        self.last = None
        self.pending = None
        from .planner import Planner
        self.planner = Planner(self.store)

    def record(self, command, result):
        if result.get('source_query'):
            return result
        source = result.get('source')
        if not source and result.get('status') in ('error', 'unverified', 'empty'):
            source = SOURCES[2]
        if not source:
            if result.get('sources'):
                source = SOURCES[1]
            elif result.get('tool') or result.get('desktop_action') or result.get('fast'):
                source = SOURCES[2]
            else:
                source = SOURCES[3]
        result['source'] = source
        result.setdefault('route', {'target': 'llm', 'reason': 'Yerel model yanıtı'})
        details = {'route': result['route'], 'urls': result.get('sources', []), 'model': result.get('model'), 'status': result.get('status'), 'measurements': result.get('measurements'), 'document_sources': result.get('document_sources', [])}
        if result.get('generated_from_documents'):
            details.update(generated_from_documents=True, answer_verified=False)
        self.store.receipt(command, source, details)
        self.last = details | {'source': source, 'response': result.get('response', '')}
        return result

    @staticmethod
    def result(answer, source=SOURCES[2], **extra):
        return {'status': 'success', 'response': answer, 'source': source, 'route': {'target': 'layers', 'reason': 'Deterministik katman komutu'}, **extra}

    @staticmethod
    def command_clarification(command):
        t = re.sub('[.,]', ' ', fold(command))
        t = re.sub('\\s+', ' ', t).strip()
        if re.fullmatch('(?:klasoru|klasor) ac', t):
            return 'Hangi klasör? Belgeler, indirilenler veya masaüstü aç diyebilirsin.'
        if re.fullmatch('.+ (?:ac|baslat|calistir|acar misin|acabilir misin)', t):
            return 'Bu açma komutunu izinli araçlarla eşleştiremedim. Uygulamanın adını net söyle veya izin listesine ekle.'
        apps = '(?:google chrome|chrome|microsoft edge|edge|youtube|discord|vs code|steam|hesap makinesi)'
        if len(t.split()) <= 7 and re.search('\\b' + apps + '\\b', t) and (not re.search('\\b(nedir|ne|nasil|iyi|mi|fark|karsilastir|hakkinda|neden)\\b', t)):
            if re.search('\\b(watch|edge)\\s*$', t) or re.fullmatch(apps, t):
                return 'Bir uygulama açma komutu olabilir ama net algılanmadı. Örneğin “Google Chrome aç” diyerek tekrar et.'
        return None

    def intercept(self, command, now=None):
        t = fold(command)
        now = now or datetime.now(TZ)
        if t.startswith(('pdf uretim paketi:', 'arastirma paketi:', 'uretim durumu:')) or t == 'uretimlerim':
            from .production import ProductionWorkflow
            production = ProductionWorkflow(self.store).intercept(command)
            if production is not None:
                self.pending = None
                return production
        if t=='raporlarim':
            from ..tools.report_export import report_names
            names=report_names(self.store.path)
            return self.result('\n'.join(names) or 'Kayıtlı rapor yok.',spoken_response=f'{len(names)} rapor gösteriliyor.')
        if t.startswith(('raporu word yap:', 'raporu pdf yap:', 'raporu sunum yap:')):
            from ..tools.report_export import export_report
            format='docx' if t.startswith('raporu word yap:') else ('pptx' if t.startswith('raporu sunum yap:') else 'pdf')
            try:
                destination=export_report(self.store.path,command.split(':',1)[1],format)
            except (ValueError,OSError) as exc:
                return self.result(str(exc),status='error',spoken_response='Rapor dışa aktarılamadı. Ayrıntılar ekranda.')
            except Exception as exc:
                return self.result(f'Rapor dönüştürme tamamlanamadı ({type(exc).__name__}). Özgün rapor korundu.',status='error',spoken_response='Rapor dönüştürülemedi. Ayrıntılar ekranda.')
            self.pending=None
            return self.result('Rapor oluşturuldu: '+str(destination),artifact_path=str(destination),
                               spoken_response={'docx':'Word raporunu','pdf':'PDF raporunu','pptx':'PowerPoint sunumunu'}[format]+' oluşturdum. Dosya yolu ekranda.')
        if re.match(r'^(?:\.\\\.venv|python(?:3|\.exe)?\s+(?:-m\s+pip|.*whisper_ses)|pip\s+install|ollama\s+(?:ps|list|run)|nvidia-smi)',t):
            return self.result('Bu komutu Whisper yazı kutusunda değil, Windows PowerShell penceresinde çalıştırın. Burada çalıştırılmadı.', status='clarification', spoken_response='Bu bir PowerShell komutu. Whisper yazı kutusunda çalıştırılmaz.')
        if t.startswith(('pdf ogren:', 'pdfde ara:', "pdf'de ara:", 'belgede ara:', 'pdf sor:', 'pdf kaynak raporu:', 'pdf cevap raporu:', 'belgeyi unut:')) or t in ('belgelerim','pdf listesi'):
            from ..memory.document_memory import DocumentMemory
            if not hasattr(self,'documents'):
                self.documents = DocumentMemory(self.store)
            document = self.documents.intercept(command)
            if document is not None:
                self.pending = None
                return document
        planned = self.planner.intercept(command)
        if planned is not None:
            self.pending = None
            return planned
        # Explicit personal statements are committed before any model response.
        content = re.split(r"[,.;]\s*(?:bunu|bu bilgiyi)\b|\s+(?:bunu|bu bilgiyi)\s+(?:hatırla|hatirla|kaydet|hafızana|hafizana)", command.strip(), maxsplit=1, flags=re.I)[0].strip(' .,!')
        name = re.fullmatch(r"(?:benim\s+)?(?:adım|adim|ismim)\s+([A-Za-zÇĞİÖŞÜçğıöşü]+(?:[ -][A-Za-zÇĞİÖŞÜçğıöşü]+){0,3})", content, re.I)
        if name and '?' not in command and not re.search(r"\b(ne|nedir|neydi|degil|değil|mi|mu|mı|mü|olsun|hatirla|hatırla)\b", fold(name[1])):
            fact = 'Adım ' + name[1]
            self.store.remember('personality', fact, command)
            return self.result('Adınızı kaydettim: ' + name[1] + '.', SOURCES[0])
        explicit = re.search(r"\b(?:bunu|bu bilgiyi)\s+(?:hatirla|kaydet|unutma|hafizana (?:at|kaydet))(?: ve hatirla)?[.!]*$", t)
        if explicit:
            fact = command[:explicit.start()].strip(' ,.;:')
            if len(fact) < 2:
                return self.result('Hangi bilgiyi kaydedeyim? Bilgiyi aynı cümlede söyle.', SOURCES[0])
            ft = fold(fact)
            category = ('hardware' if re.search(r'\b(rtx|gtx|ram|islemci|ekran kart|bilgisayar|telefon)', ft) else
                        'projects' if 'proje' in ft else 'goals' if 'hedef' in ft else
                        'preferences' if re.search(r'seviyor|tercih|hosuma', ft) else 'personality')
            self.store.remember(category, fact, command)
            return self.result('Bilgiyi hafızaya kaydettim.', SOURCES[0])
        if self.pending and t not in ('evet', 'onayliyorum', 'uygula', 'iptal', 'vazgec', 'hayir'):
            self.pending = None
        if t in ('bilgisayarim yavasladi', 'bilgisayar yavasladi', 'pc yavasladi',
                 'bilgisayar neden yavas', 'bilgisayarim neden yavas', 'bilgisayarim yavas', 'performans kontrolu yap', 'performans kontrolu'):
            from ..tools.system_health import collect_snapshot, summarize_snapshot
            try:
                snapshot = collect_snapshot()
                return self.result(summarize_snapshot(snapshot), SOURCES[2],
                    spoken_response=f"İşlemci yüzde {snapshot['cpu_percent']:.0f}, bellek yüzde {snapshot['ram_percent']:.0f} dolu. Diskte {snapshot['disk_free_gb']:.0f} gigabayt boş alan var. Ayrıntılar ekranda; bu tek ölçüm kesin nedeni göstermez.",
                    measurements=snapshot, route={'target':'diagnostic','reason':'Sorun bildirimi: salt okunur kaynak ölçümü'})
            except ImportError:
                return self.result('Performans ölçümü için psutil paketi eksik. Mevcut requirements.txt kurulumunu kontrol et.', status='error')
            except Exception as exc:
                return self.result(f'Performans ölçümü tamamlanamadı: {type(exc).__name__}. Sistem ayarı değiştirilmedi.', status='error')
        if t in ('bu bilgiyi nereden ogrendin', 'bunu nereden biliyorsun', 'bilginin kaynagi ne', 'kaynak ne'):
            if not self.last:
                return self.result('Bu oturumda henüz kaynak kaydı olan bir cevabım yok.', source_query=True)
            labels = {SOURCES[0]: 'Bu bilgi kayıtlı hafızadan geldi; bağımsız doğrulama değildir.', SOURCES[1]: 'Bu cevap internet arama sonuçlarına dayanıyor; sonuçları bağımsız olarak doğrulamadım.', SOURCES[2]: 'Bu sonuç sistemden veya uygulamanın doğrudan aracından geldi.', SOURCES[3]: 'Bu cevap yerel modelin üretimi; dayanağını doğrulayamadım. Tahmin olarak işaretledim.'}
            if self.last.get('document_sources'):
                labels[SOURCES[0]] += '\nPDF kaynakları:\n'+'\n'.join(dict.fromkeys(
                    f"{s['name']}, sayfa {s['page']}, belge {s['document_id']}" for s in self.last['document_sources']))
            extra={}
            if self.last.get('document_sources'):
                extra['spoken_response']='Bu bilgi yüklediğiniz PDF alıntılarına dayanıyor; bağımsız doğrulama değil. Dosya adları ve sayfalar ekranda.'
            return self.result(labels[self.last['source']], self.last['source'], source_query=True, sources=self.last['urls'], document_sources=self.last.get('document_sources', []), evidence=self.last,**extra)
        if t in ('iptal', 'vazgec', 'hayir') and self.pending:
            self.pending = None
            return self.result('Bekleyen işlem iptal edildi.')
        if t in ('evet', 'onayliyorum', 'uygula') and self.pending:
            pending, self.pending = (self.pending, None)
            if time.monotonic() > pending['expires']:
                return self.result('Onayın süresi doldu; işlemi yeniden iste.')
            if pending['kind'] == 'evolution':
                ids = [self.store.task(title) for title in pending['titles']]
                return self.result('Onaylanan geliştirmeler görev listesine kaydedildi: ' + ', '.join(map(str, ids)) + '. Kod henüz değiştirilmedi.')
            return {'restart_confirmed': True}
        if t in ('bilgisayari yeniden baslat', 'pc yeniden baslat'):
            self.pending = {'kind': 'restart', 'expires': time.monotonic() + 60}
            return self.result('Bilgisayarı yeniden başlatmak için açık dosyalarını kaydet. 60 saniye içinde “evet” diyerek onayla veya “iptal” de.')
        if t in ('eksikler ne', 'gelistirme oner', 'kendini gelistir'):
            titles = ['Whisper GUI ve ses durumu iyileştirmeleri', 'GitHub uzak repo bağlantısı', 'Düşük güçlü wake-word ve yankı kontrolü']
            self.pending = {'kind': 'evolution', 'titles': titles, 'expires': time.monotonic() + 60}
            return self.result('Üç geliştirme öneriyorum: ' + '; '.join(titles) + '. Onaylarsan görev olarak kaydederim. Uygulamanın kendi kodunu otomatik değiştirme yetkisi yok. Kaydedelim mi?')
        if t in ('github son commit', 'github gorevleri', 'github yapilacaklar'):
            answer, urls = self.github.query(command)
            return self.result(answer, SOURCES[1] if urls else SOURCES[2], sources=urls)
        if t in ('repo durumu ne', 'repo durumu', 'son commit ne yapti', 'son commit'):
            return self.result(self.git.query(command))
        if t in ('proje durumu', 'whisper projesi ne durumda', 'yol haritasi'):
            return self.result(self.project.report(), SOURCES[0])
        if t in ('hatalari analiz et', 'hata raporu', 'kendini analiz et'):
            return self.result(self.analysis.report(), SOURCES[2], spoken_response='Kayıtlı işlem sonuçlarını analiz ettim. Ayrıntılar ekranda.')
        if t.startswith('hafizada ara:'):
            rows=self.vectors.search(command.split(':',1)[1])
            return self.result('Eşleşen hafıza kayıtları: '+ '; '.join(r['fact'] for r in rows) if rows else 'Eşleşen kayıt yok.', SOURCES[0])
        if t in ('benim ekran kartim neydi', 'ekran kartim ne', 'ekran kartim neydi'):
            rows=[r for r in self.store.knowledge('hardware') if re.search(r'\b(rtx|gtx|radeon|gpu)\b|ekran kart',fold(r['fact']))]
            return self.result('; '.join(r['fact'] for r in rows) or 'Ekran kartın kategorili hafızada kayıtlı değil.', SOURCES[0])
        if t in ('adim ne', 'benim adim ne'):
            names = [r['fact'] for r in self.store.knowledge('personality') if fold(r['fact']).startswith('adim ')]
            return self.result('Adınız ' + names[0].split(maxsplit=1)[1].rstrip('.!?') + '.' if names else 'Adınız henüz hafızada kayıtlı değil.', SOURCES[0])
        if t in ('yapilacaklar ne', 'gorevlerim', 'gorev listesi'):
            rows = self.store.tasks()
            answer = '; '.join((f'{i}: {title}' + (f' — {datetime.fromisoformat(due).astimezone(TZ):%d.%m %H:%M}' if due else '') for i, title, due in rows))
            return self.result(answer or 'Bekleyen görev yok.', SOURCES[0], spoken_response=f'{len(rows)} görev gösteriliyor. Ayrıntılar ekranda.' if rows else 'Bekleyen görev yok.')
        m = re.fullmatch('gorev(?:i)? tamamla\\s*:?\\s*(\\d+)', t)
        if m:
            return self.result('Görev tamamlandı.' if self.store.complete(int(m[1])) else 'Bekleyen görev bulunamadı.', SOURCES[0])
        m = re.match('^(?:gorev ekle|yapilacak ekle)\\s*:\\s*(.+)$', t)
        if m:
            task_id = self.store.task(command.split(':', 1)[1])
            return self.result(f'Görev {task_id} kaydedildi; henüz uygulanmadı.', SOURCES[0])
        if t in ('whisper gui yap', 'github modulu ekle'):
            task_id = self.store.task(command)
            return self.result(f'Geliştirme görevi {task_id} kaydedildi; kod henüz değiştirilmedi.', SOURCES[0])
        from ..tools.reminder_parser import parse_reminder
        reminder = parse_reminder(command, now)
        if reminder is not None:
            if reminder.error:
                return self.result(reminder.error, status='clarification')
            task_id = self.store.task(reminder.title, reminder.due.astimezone(timezone.utc).isoformat())
            return self.result(f'Hatırlatma {task_id} kaydedildi: {reminder.due:%d.%m.%Y %H:%M} — {reminder.title}. Whisper açıkken bildirilir.', SOURCES[0], spoken_response='Hatırlatmayı kaydettim. Zamanı ekranda.')
        m = re.fullmatch('hafizaya kaydet\\s*:\\s*(personality|projects|goals|hardware|relationships|preferences)\\s*=\\s*(.+)', t)
        if m:
            self.store.remember(m[1], command.split('=', 1)[1], command)
            return self.result('Bilgi belirtilen kategoride hafızaya kaydedildi.', SOURCES[0])
        m = re.fullmatch('(?:hafiza|hafizam)\\s*:\\s*(personality|projects|goals|hardware|relationships|preferences)', t)
        if m:
            rows = self.store.knowledge(m[1])
            return self.result('; '.join((r['fact'] for r in rows)) or 'Bu kategoride kayıt yok.', SOURCES[0])
        categories = {'donanimim ': 'hardware', 'projem ': 'projects', 'hedefim ': 'goals', 'tercihim ': 'preferences', 'kisiligim ': 'personality'}
        for prefix, category in categories.items():
            if t in (prefix.strip() + ' ne', prefix.strip() + ' nedir'):
                rows = self.store.knowledge(category)
                return self.result('; '.join((r['fact'] for r in rows)) or 'Bu kategoride kayıt yok.', SOURCES[0])
            if t.startswith(prefix) and '?' not in command and (not re.search('\\b(ne|nasil|mi|mu|midir|mudur)\\b', t)):
                self.store.remember(category, command, command)
                return self.result('Bilgiyi ' + category + ' kategorisine kaydettim.', SOURCES[0])
        return None
