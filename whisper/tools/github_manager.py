from __future__ import annotations
import json, re, sqlite3, subprocess, time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from ..common import *

class GitBrain:

    def __init__(self, repo=None):
        self.repo = Path(repo).resolve() if repo else None

    def query(self, command):
        if self.repo is None:
            return 'Repo klasörü seçilmedi. --repo ile yerel Git projesinin klasörünü belirt.'
        if not self.repo.is_dir():
            return 'Repo klasörü bulunamadı.'
        commands = {'repo durumu ne': ['status', '--short', '--untracked-files=no'], 'repo durumu': ['status', '--short', '--untracked-files=no'], 'son commit ne yapti': ['log', '-1', '--format=%h %s', '--stat'], 'son commit': ['log', '-1', '--format=%h %s', '--stat']}
        args = commands.get(fold(command))
        if args is None:
            return None
        try:
            r = subprocess.run(['git', '--no-pager', '--no-optional-locks', '-c', 'core.fsmonitor=false', '-C', str(self.repo), *args], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
            if r.returncode:
                return 'Git bilgisi alınamadı; klasörün Git deposu olduğunu kontrol et.'
            return r.stdout.strip()[:4000] or 'Takip edilen dosyalarda değişiklik yok. Takip edilmeyen dosyalar bu özette yok.'
        except FileNotFoundError:
            return 'Git kurulu değil veya PATH içinde bulunamadı.'
        except subprocess.TimeoutExpired:
            return 'Git sorgusu zaman aşımına uğradı.'

class GitHubBrain:

    def __init__(self, repo=None, enabled=False):
        if repo and (not re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo)):
            raise ValueError('GitHub repo adı owner/repo şeklinde olmalı.')
        self.repo, self.enabled = (repo, enabled)

    def query(self, command):
        if not self.repo:
            return ('GitHub deposu seçilmedi. --github-repo owner/repo kullan.', [])
        if not self.enabled:
            return ('GitHub sorgusu için internet erişimini --web ile aç.', [])
        from urllib.request import Request, urlopen
        from urllib.error import URLError, HTTPError
        t = fold(command)
        endpoint = 'commits?per_page=1' if 'commit' in t else 'issues?state=open&per_page=10'
        url = 'https://api.github.com/repos/' + self.repo + '/' + endpoint
        request = Request(url, headers={'User-Agent': 'Whisper-Local-Assistant', 'Accept': 'application/vnd.github+json'})
        try:
            with urlopen(request, timeout=10) as response:
                raw = response.read(100001)
            if len(raw) > 100000:
                return ('GitHub yanıtı boyut sınırını aştı.', [])
            data = json.loads(raw)
            if not isinstance(data, list):
                return ('GitHub beklenen liste yanıtını vermedi.', [])
            if 'commit' in t:
                if not data:
                    return ('GitHub deposunda commit bulunamadı.', [])
                item = data[0]
                if not isinstance(item, dict) or not isinstance(item.get('commit'), dict):
                    return ('GitHub commit yanıtı geçersiz.', [])
                message = str(item.get('commit', {}).get('message', '')).split('\n')[0][:500]
                urls = [u for u in [item.get('html_url')] if isinstance(u, str) and u.startswith('https://github.com/')]
                return (str(item.get('sha', ''))[:8] + ': ' + message, urls)
            items = [i for i in data if isinstance(i, dict) and 'pull_request' not in i]
            urls = [i['html_url'] for i in items if isinstance(i.get('html_url'), str) and i['html_url'].startswith('https://github.com/')]
            return ('; '.join((f"#{i.get('number')}: {str(i.get('title', ''))[:200]}" for i in items)) or 'İlk sonuç sayfasında açık issue yok.', urls)
        except (URLError, HTTPError, ValueError, KeyError, TypeError, TimeoutError):
            return ('GitHub bilgisi alınamadı. Ağ, repo görünürlüğü veya API kotası engel olabilir.', [])
