"""Explicit website intents and shell-free browser dispatch."""
import os
import re
import subprocess
import sys
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit
from ..common import fold

BROWSERS = {'brave', 'chrome', 'edge', 'firefox'}

def website_url(value):
    if not isinstance(value, str) or len(value) > 2000 or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError('Web adresi geçersiz.')
    if not value.startswith(('https://', 'http://')):
        value = 'https://' + value
    p = urlsplit(value)
    if p.scheme not in ('http', 'https') or p.username or p.password or not p.hostname or '\\' in value:
        raise ValueError('Yalnız http(s) web adresleri açılabilir.')
    host = p.hostname.encode('idna').decode('ascii')
    if not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}', host, re.I):
        raise ValueError('Tam bir site adresi belirtin: örneğin x.com.')
    if p.port not in (None, 80, 443):
        raise ValueError('Bu araç yalnız standart web portlarını açar.')
    return value


def website_intent(text, pending=None):
    """Only complete single-action grammar; other requests stay with the planner."""
    t = fold(text).strip().rstrip('.!?')
    browser = 'default'
    choice = re.fullmatch(r"(brave|chrome|edge|firefox)(?:['’]?(?:i|yi|u|yu))?(?: tarayicisini)?(?: kullan| ile| olsun)?", t)
    if choice and pending:
        old = website_intent(pending['request'])
        if old:
            return dict(old, browser=choice[1])
    # Matching the whole sentence avoids executing quoted, negative or composed requests.
    match = re.fullmatch(
        r"(?:lutfen )?(?:(brave|chrome|edge|firefox)(?: tarayicisini)? (?:kullanarak|ile) )?"
        r"((?:https?://)?(?:www\.)?[a-z0-9][a-z0-9.-]*\.[a-z]{2,63}(?:/[^\s]*)?)"
        r"(?:['’](?:i|yi|u|yu))?(?: sitesini| sitesine| sayfasini| adresini)? "
        r"(?:ac|acar misin|acabilir misin|git|gider misin|giris yap)(?: lutfen)?", t)
    if not match:
        return None
    # Turkish folding preserves ASCII offsets after trimming; URL case is retained.
    original = text.strip().rstrip('.!?')[match.start(2):match.end(2)]
    return {'url': website_url(original), 'browser': match[1] or browser}



def open_website(url, browser, cfg, catalog):
    url = website_url(url)
    if browser not in BROWSERS | {'default'}:
        raise ValueError('Tarayıcı adı desteklenmiyor.')
    if not cfg.tools_enabled:
        return {'status': 'blocked', 'response': 'Bilgisayar araçları kapalı.'}
    if browser == 'default':
        ok = webbrowser.open(url)
        if not ok:
            return {'status': 'clarification', 'response': 'Varsayılan tarayıcı başlatılamadı. Hangi tarayıcıyı kullanayım?'}
    else:
        path = cfg.allowed_apps.get(browser) or catalog.resolve(browser)
        if not path and sys.platform == 'win32':
            suffix = {'brave':'BraveSoftware/Brave-Browser/Application/brave.exe',
                      'chrome':'Google/Chrome/Application/chrome.exe',
                      'edge':'Microsoft/Edge/Application/msedge.exe',
                      'firefox':'Mozilla Firefox/firefox.exe'}[browser]
            for name in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA'):
                root = os.environ.get(name)
                if root and (Path(root) / suffix).is_file():
                    path = str(Path(root) / suffix)
                    break
        if not path:
            return {'status': 'clarification', 'response': f'{browser.capitalize()} kurulumunu bulamadım. Başka hangi tarayıcıyı kullanayım?'}
        subprocess.Popen([path, url], shell=False)
    return {'status':'dispatched', 'response':f'{url} adresini {browser if browser != "default" else "varsayılan tarayıcı"} ile açma isteğini gönderdim.',
            'verification':'browser_request_only', 'page_loaded_verified':False}
