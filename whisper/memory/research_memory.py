"""Source snapshots and explicit research watches, not model weight training."""
import hashlib
import json
import sqlite3
import time
from html.parser import HTMLParser
from urllib.parse import urlsplit

ACADEMIC_HOSTS = {'arxiv.org', 'pmc.ncbi.nlm.nih.gov'}

def article_url(value):
    if not isinstance(value, str) or len(value) > 1000:
        raise ValueError('Makale adresi geçersiz.')
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or parsed.hostname not in ACADEMIC_HOSTS or parsed.username
            or parsed.password or parsed.port not in (None, 443)):
        raise ValueError('Makale okuma yalnız arxiv.org ve pmc.ncbi.nlm.nih.gov HTTPS adreslerinde açık.')
    if parsed.hostname == 'arxiv.org' and not parsed.path.startswith('/abs/'):
        raise ValueError('arXiv için makalenin /abs/ özet sayfasını kullanın; PDF için PDF öğrenme aracını kullanın.')
    if parsed.hostname == 'pmc.ncbi.nlm.nih.gov' and not parsed.path.startswith('/articles/PMC'):
        raise ValueError('PMC için bir makale sayfası seçin.')
    return value

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(); self.skip = 0; self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript', 'nav', 'footer'): self.skip += 1
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript', 'nav', 'footer') and self.skip: self.skip -= 1
    def handle_data(self, data):
        if not self.skip and data.strip(): self.parts.append(data.strip())

def read_article(url, cancelled=None):
    import requests
    for _ in range(4):
        article_url(url)
        if cancelled is not None and cancelled.is_set():
            raise RuntimeError('Okuma iptal edildi.')
        with requests.get(url, stream=True, timeout=(5, 10), allow_redirects=False,
                          headers={'User-Agent': 'WhisperResearch/1.0'}) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                from urllib.parse import urljoin
                url = urljoin(url, response.headers.get('Location', ''))
                continue
            response.raise_for_status()
            if not response.headers.get('Content-Type', '').lower().startswith(('text/html', 'text/plain')):
                raise ValueError('Bu kaynak HTML/metin değil; PDF dosyasını PDF öğrenme bölümüne verin.')
            blocks = []; size = 0; deadline = time.monotonic() + 20
            for chunk in response.iter_content(8192):
                if time.monotonic() > deadline or (cancelled is not None and cancelled.is_set()):
                    raise RuntimeError('Makale okuması durduruldu.')
                size += len(chunk)
                if size > 1000000: raise ValueError('Makale boyut sınırı 1 MB.')
                blocks.append(chunk)
            html = b''.join(blocks).decode(response.encoding or 'utf-8', errors='replace')
            parser = VisibleText(); parser.feed(html)
            text = '\n'.join(parser.parts)
            if len(text) < 100: raise ValueError('Yeterli makale metni okunamadı.')
            # Retain a bounded snapshot; never claim an entire truncated article was learned.
            return url, text[:30000], len(text) > 30000
    raise ValueError('Makale yönlendirme sınırı aşıldı.')

class ResearchMemory:
    def __init__(self, database_path):
        self.path = str(database_path)
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS research_sources(
                id INTEGER PRIMARY KEY, query TEXT NOT NULL, source_type TEXT NOT NULL,
                body TEXT NOT NULL, sources TEXT NOT NULL, fingerprint TEXT UNIQUE NOT NULL,
                retrieved_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS research_watches(
                id INTEGER PRIMARY KEY, topic TEXT UNIQUE NOT NULL, hours INTEGER NOT NULL,
                next_due REAL NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
                last_status TEXT NOT NULL DEFAULT 'pending');''')
    def connect(self): return sqlite3.connect(self.path, timeout=5)
    def capture(self, query, body, sources, source_type='search_excerpt'):
        if not body or not sources: raise ValueError('Kaynaklı araştırma sonucu yok.')
        identities = sorted(str(source.get('url', '')) for source in sources)
        fingerprint = hashlib.sha256(json.dumps([source_type, body, identities], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO research_sources(query,source_type,body,sources,fingerprint,retrieved_at) VALUES(?,?,?,?,?,?)',
                       (query[:200], source_type, body[:30000], json.dumps(sources, ensure_ascii=False), fingerprint, time.time()))
            db.execute('UPDATE research_sources SET sources=?,retrieved_at=? WHERE fingerprint=?', (json.dumps(sources, ensure_ascii=False), time.time(), fingerprint))
            return db.execute('SELECT id FROM research_sources WHERE fingerprint=?', (fingerprint,)).fetchone()[0]
    def get(self, record_id):
        """Read one exact production input; never substitute the latest unrelated record."""
        if type(record_id) is not int or record_id < 1:
            raise ValueError('Araştırma numarası geçersiz.')
        with self.connect() as db:
            row = db.execute('SELECT id,source_type,body,sources,retrieved_at FROM research_sources WHERE id=?',
                             (record_id,)).fetchone()
        if row is None:
            return None
        i, kind, body, sources, stamp = row
        return dict(id=i, source_type=kind, body=body, sources=json.loads(sources), retrieved_at=stamp)

    def find(self, query):
        # Literal LIKE with escaped wildcard characters; bounded source snapshots.
        value = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        with self.connect() as db:
            rows = db.execute("SELECT id,source_type,body,sources,retrieved_at FROM research_sources WHERE query LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\' ORDER BY retrieved_at DESC LIMIT 4", ('%'+value+'%', '%'+value+'%')).fetchall()
        return [{'id': i, 'source_type': kind, 'excerpt': body[:1500], 'sources': json.loads(sources), 'retrieved_at': stamp} for i, kind, body, sources, stamp in rows]
    def watch(self, topic, hours):
        if not isinstance(topic, str) or not 3 <= len(topic.strip()) <= 200 or type(hours) is not int or not 6 <= hours <= 168:
            raise ValueError('Araştırma konusu 3–200 karakter, aralık 6–168 saat olmalı.')
        with self.connect() as db:
            db.execute('INSERT INTO research_watches(topic,hours,next_due) VALUES(?,?,?) ON CONFLICT(topic) DO UPDATE SET hours=excluded.hours,next_due=excluded.next_due,enabled=1', (topic.strip(), hours, time.time()))
            return db.execute('SELECT id FROM research_watches WHERE topic=?', (topic.strip(),)).fetchone()[0]
    def due(self):
        now = time.time()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT id,topic,hours FROM research_watches WHERE enabled=1 AND next_due<=? ORDER BY next_due LIMIT 1', (now,)).fetchone()
            if row: db.execute("UPDATE research_watches SET next_due=?,last_status='running' WHERE id=?", (now+row[2]*3600, row[0]))
        return row
    def finish(self, watch_id, status):
        with self.connect() as db: db.execute('UPDATE research_watches SET last_status=? WHERE id=?', (status, watch_id))
    def watches(self):
        with self.connect() as db: return db.execute('SELECT id,topic,hours,enabled,last_status FROM research_watches ORDER BY id').fetchall()
    def stop(self, watch_id):
        with self.connect() as db: return bool(db.execute('UPDATE research_watches SET enabled=0 WHERE id=?', (watch_id,)).rowcount)
