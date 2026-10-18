"""Bounded, read-only Windows App Paths discovery; never execute registry commands."""
import os
import sys
from pathlib import Path
from ..common import fold

BLOCKED = {'cmd', 'powershell', 'pwsh', 'wscript', 'cscript', 'mshta', 'rundll32',
           'regsvr32', 'python', 'pythonw', 'bash', 'sh', 'wt', 'reg', 'shutdown'}

def safe_executable(value):
    if not isinstance(value, str):
        return None
    value = os.path.expandvars(value.strip().strip('"'))
    path = Path(value)
    if not path.is_absolute() or path.suffix.lower() != '.exe':
        return None
    if path.stem.lower() in BLOCKED or not path.is_file() or path.is_symlink():
        return None
    return str(path)

class AppCatalog:
    def __init__(self, loader=None):
        self.loader = loader or self._registry
        self._entries = None

    @staticmethod
    def _registry():
        if sys.platform != 'win32':
            return []
        import winreg
        rows = []
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, r'Software\Microsoft\Windows\CurrentVersion\App Paths',
                                        0, winreg.KEY_READ | view) as root:
                        for index in range(256):
                            try:
                                name = winreg.EnumKey(root, index)
                            except OSError:
                                break
                            try:
                                with winreg.OpenKey(root, name) as key:
                                    value, _ = winreg.QueryValueEx(key, '')
                                rows.append((Path(name).stem, value))
                            except OSError:
                                continue
                except OSError:
                    continue
        return rows

    def entries(self):
        if self._entries is None:
            entries = {}
            for name, value in self.loader():
                path = safe_executable(value)
                key = fold(name)
                if path and key and len(key) <= 80:
                    entries.setdefault(key, set()).add(path)
            # Conflicting registrations require an explicit user mapping.
            self._entries = {key: next(iter(paths)) for key, paths in entries.items() if len(paths) == 1}
        return dict(self._entries)

    def resolve(self, name):
        value = self.entries().get(fold(name))
        return safe_executable(value) if value else None
