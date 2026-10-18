"""Find user files by name without passing paths or commands to an LLM."""
import os
import re
import sys
import time
from pathlib import Path
from whisper.common import fold

SAFE_EXTENSIONS = {'.pdf','.txt','.md','.csv','.docx','.xlsx','.pptx','.odt','.ods','.odp',
                   '.png','.jpg','.jpeg','.webp','.bmp','.gif','.wav','.mp3','.m4a','.mp4','.mkv','.avi'}
SKIP_DIRS = {'.git','.venv','venv','node_modules','__pycache__','appdata','.cache','models'}

def default_roots():
    home=Path.home()
    paths=[home/name for name in ('Desktop','Documents','Downloads')]
    if sys.platform=='win32':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
                for name in ('Desktop','Personal','{374DE290-123F-4565-9164-39C4925E467B}'):
                    try:
                        value,_=winreg.QueryValueEx(key,name)
                        paths.append(Path(os.path.expandvars(value)))
                    except OSError:
                        pass
        except OSError:
            pass
    for env in ('OneDrive','OneDriveCommercial','OneDriveConsumer'):
        if os.environ.get(env):
            paths.extend(Path(os.environ[env])/name for name in ('Desktop','Documents'))
    return paths

def name_key(name):
    return re.sub(r'\s+',' ',re.sub(r'[\W_]',' ',fold(name))).strip()

def request(command):
    text=fold(command).strip().rstrip('.!?')
    match=re.fullmatch(r'(?:lutfen\s+)?(.+?)\s+(?:ac|acar misin|acabilir misin)',text)
    if not match:
        return None
    name=match.group(1)
    if re.search(r'[;|/\\:<>\n]',name):
        return None
    kind='folder' if re.search(r'\bklasor(?:unu|u)?$',name) else 'any'
    name=re.sub(r'\s+(?:dosyasini|dosyasi|dosyayi|dosya|klasorunu|klasoru|klasor)$','',name)
    name=name.strip(' "\'“”')
    if not name or name in ('dosya','klasor'):
        return None
    return name,kind

class FileManager:
    def __init__(self, roots=None, opener=None, clock=time.monotonic):
        self.roots=[]
        for path in list(default_roots())+list(roots or []):
            try:
                resolved=Path(path).expanduser().resolve()
                if resolved.is_dir() and resolved not in self.roots:
                    self.roots.append(resolved)
            except OSError:
                pass
        self.opener=opener
        self.clock=clock
        self.pending=None

    def result(self, text, status='success'):
        return {'response':text,'status':status,'tool':'dosya_ac','source':'KAYNAK_SISTEM'}

    def _contained(self, path):
        try:
            return any(path.resolve().is_relative_to(root) for root in self.roots)
        except OSError:
            return False

    def _open(self, path):
        # Recheck at execution time: a stale selection or symlink must not escape roots.
        if not path.exists() or path.is_symlink() or not self._contained(path):
            return self.result('Dosya artık yok veya arama kapsamının dışında.','error')
        if path.is_file() and path.suffix.lower() not in SAFE_EXTENSIONS:
            return self.result('Bu dosya türü otomatik açılmıyor. Belge, görsel veya medya dosyası seçin.','blocked')
        if self.opener is None and sys.platform!='win32':
            return self.result('Yerel dosya açma Windows üzerinde destekleniyor.','error')
        try:
            (self.opener or os.startfile)(str(path))
        except OSError as exc:
            return self.result(f'Dosya açma hatası: {type(exc).__name__}.','error')
        return self.result(f'{path.name} için açma isteği Windows’a gönderildi.\nKonum: {path}')

    def select(self, command, enabled=True):
        if not self.pending:
            return None
        pending=self.pending
        self.pending=None
        text=fold(command).strip().rstrip('.!?')
        numbers={'bir':1,'iki':2,'uc':3,'dort':4,'bes':5,'alti':6,'yedi':7,'sekiz':8,'dokuz':9,'on':10,
                 'on bir':11,'on iki':12,'on uc':13,'on dort':14,'on bes':15,'on alti':16,'on yedi':17,
                 'on sekiz':18,'on dokuz':19,'yirmi':20}
        for word,number in sorted(numbers.items(),key=lambda item:len(item[0]),reverse=True):
            if re.match(r'^'+word+r'\b',text):
                text=str(number)+text[len(word):]
                break
        if text in ('iptal','vazgec','hayir'):
            return self.result('Dosya seçimi iptal edildi.','cancelled')
        match=re.fullmatch(r'(?:dosya sec\s*:?\s*)?(\d+)(?:\.?\s*(?:numarali|numara|numarayi))?(?:\s+dosyayi)?(?:\s+ac)?',text)
        if not match:
            return None
        if not enabled:
            return self.result('Bilgisayar kontrolü kapalı; --enable-tools gerekli.','blocked')
        if self.clock()>pending['expires']:
            return self.result('Dosya seçiminin süresi doldu. Dosyayı yeniden arayın.','error')
        index=int(match.group(1))-1
        if not 0<=index<len(pending['paths']):
            return self.result('Listede bu numara yok. Dosyayı yeniden arayın.','error')
        return self._open(pending['paths'][index])

    def find_and_open(self, command, enabled=True):
        parsed=request(command)
        if parsed is None:
            return None
        self.pending=None
        if not enabled:
            return self.result('Bilgisayar kontrolü kapalı; --enable-tools gerekli.','blocked')
        query,kind=parsed
        key=name_key(query)
        keys={key}
        # Turkish accusative endings: "raporunu aç" can refer to "rapor".
        for _ in range(2):
            for value in tuple(keys):
                trimmed=re.sub(r'(?:yi|yu|ni|nu|i|u)$','',value)
                if len(trimmed)>=3:
                    keys.add(trimmed)
        exact=[];partial=[];seen=set();count=0;incomplete=False
        started=self.clock()
        for root in self.roots:
            for base,dirs,files in os.walk(root,followlinks=False):
                depth=len(Path(base).relative_to(root).parts)
                dirs[:]=[d for d in dirs if depth<8 and d.lower() not in SKIP_DIRS and not d.startswith('.')
                         and not (Path(base)/d).is_symlink()
                         and not (hasattr(Path(base)/d,'is_junction') and (Path(base)/d).is_junction())]
                for name in dirs+files:
                    count+=1
                    if count>20000 or self.clock()-started>3:
                        incomplete=True;break
                    path=Path(base)/name
                    if path in seen or path.is_symlink():continue
                    seen.add(path)
                    if kind=='folder' and not path.is_dir():continue
                    candidates={name_key(name)}
                    if path.is_file():candidates.add(name_key(path.stem))
                    if keys & candidates:
                        exact.append(path)
                    elif len(key)>=3 and any(key in c for c in candidates):
                        partial.append(path)
                if incomplete:break
            if incomplete:break
        matches=sorted(set(exact or partial),key=lambda p:str(p).lower())
        if not matches:
            suffix=' Tarama süre/derinlik sınırı nedeniyle kısmi olabilir.' if incomplete else ''
            return self.result(f'“{query}” adını arama klasörlerinde bulamadım.{suffix} Başka konum için --file-root ile klasör eklenebilir.','not_found')
        # Only a unique exact match in a completed scan is opened automatically.
        if len(matches)==1 and exact and not incomplete:
            return self._open(matches[0])
        paths=matches[:20]
        self.pending={'paths':paths,'expires':self.clock()+60}
        rows='\n'.join(f'{i}. {p}' for i,p in enumerate(paths,1))
        suffix='\nTarama kısmi; gösterilen konumu kontrol edin.' if incomplete else ''
        return self.result('Eşleşmeleri buldum. Açmak için “Dosya seç: 1” yazın veya “bir numaralı dosyayı aç” deyin.\n'+rows+suffix,'choice')
