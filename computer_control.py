"""WHISPER desktop adapter. Imports GUI dependencies only when used."""
from __future__ import annotations
import io
import re
import time


class ComputerControl:
    @staticmethod
    def _gui():
        try:
            import pyautogui
        except ImportError as exc:
            raise RuntimeError('Ekran kontrolü için: python -m pip install pyautogui pillow pyperclip') from exc
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.2
        return pyautogui

    @classmethod
    def screenshot(cls) -> bytes:
        """Primary monitor only; return JPEG in memory, never save to disk."""
        shot = cls._gui().screenshot().convert('RGB')
        shot.thumbnail((1600, 1600))
        buf = io.BytesIO()
        shot.save(buf, format='JPEG', quality=80)
        return buf.getvalue()

    @staticmethod
    def parse(command: str):
        folded = command.translate(str.maketrans('çğıöşüÇĞİÖŞÜ', 'cgiosuCGIOSU')).lower().strip().rstrip('.!?')
        if folded in ('ekran goruntusu al', 'ekran resmi al'):
            return ('capture', None)
        if folded in ('ses seviyesini artir', 'sesi artir', 'sesi ac', 'sesini artir'):
            return ('volume', 'volumeup')
        if folded in ('ses seviyesini azalt', 'sesi azalt', 'sesi kis', 'sesini kis', 'sesini azalt'):
            return ('volume', 'volumedown')
        if folded in ('ekrani incele', 'ekranda ne var', 'ekrani oku'):
            return ('screen', 'Ekranı Türkçe özetle; okunmayan yerleri tahmin etme.')
        if folded.startswith('ekrani incele:'):
            return ('screen', command.split(':', 1)[1].strip())
        match = re.fullmatch(r'tikla\s+(\d+)\s*[, ]\s*(\d+)', folded)
        if match:
            return ('click', (int(match[1]), int(match[2])))
        match = re.fullmatch(r'(asagi|yukari) kaydir(?:\s+(\d+))?', folded)
        if match:
            return ('scroll', (-1 if match[1] == 'asagi' else 1) * min(int(match[2] or 3), 10))
        if folded.startswith('ekrana yaz:'):
            return ('type', command.split(':', 1)[1].strip())
        shortcuts = {'sonraki alana gec': ('tab',), 'onceki alana gec': ('shift', 'tab'),
                     'esc tusuna bas': ('esc',), 'sekmeyi degistir': ('ctrl', 'tab')}
        if folded in shortcuts:
            return ('keys', shortcuts[folded])
        return None

    @classmethod
    def execute(cls, action, value) -> str:
        gui = cls._gui()
        if action == 'capture':
            from pathlib import Path
            from datetime import datetime
            folder = Path.home() / 'Pictures' / 'Whisper'
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / (datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.png')
            gui.screenshot().save(path)
            return f'Ekran görüntüsü kaydedildi: {path}'
        if action == 'volume':
            if value not in ('volumeup', 'volumedown'):
                return 'Ses komutu desteklenmiyor.'
            gui.press(value, presses=3, interval=0.1)
            return 'Windows ses seviyesi tuşları gönderildi.'
        if action == 'click':
            x, y = value
            width, height = gui.size()
            if not (0 <= x < width and 0 <= y < height):
                return 'Koordinat ana ekranın dışında; tıklanmadı.'
            gui.click(x, y)
            return f'{x}, {y} konumuna tıklama gönderildi; uygulama sonucunu kontrol edin.'
        if action == 'scroll':
            gui.scroll(value)
            return 'Kaydırma gönderildi.'
        if action == 'keys':
            if value not in (('tab',), ('shift', 'tab'), ('esc',), ('ctrl', 'tab'), ('ctrl','l'), ('ctrl','t'), ('ctrl','c'), ('ctrl','v'), ('ctrl','a')):
                return 'Bu tuş dizisi desteklenmiyor.'
            gui.hotkey(*value)
            return 'Tuş komutu gönderildi.'
        if action == 'type':
            if not value or len(value) > 2000 or any(ord(c) < 32 for c in value):
                return 'Metin 1–2000 karakter ve tek satır olmalı.'
            # Clipboard paste supports Turkish; never press Enter automatically.
            import pyperclip
            previous = pyperclip.paste()
            try:
                pyperclip.copy(value)
                gui.hotkey('ctrl', 'v')
                time.sleep(0.3)
            finally:
                if pyperclip.paste() == value:
                    pyperclip.copy(previous)
            return 'Metin odaktaki alana yapıştırıldı; Enter tuşuna basılmadı.'
        return 'Desteklenmeyen masaüstü işlemi.'
