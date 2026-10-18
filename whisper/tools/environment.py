"""Local machine awareness; only explicit tools can turn context into an action."""
import platform
import time
from pathlib import Path


def inventory(apps):
    result = {'measured_at': time.time(), 'os': platform.system(), 'os_release': platform.release(),
              'architecture': platform.machine(), 'python': platform.python_version(),
              'applications': sorted(set(apps))[:128],
              'folders': [name for name in ('Desktop', 'Documents', 'Downloads', 'Music', 'Pictures') if (Path.home()/name).is_dir()]}
    try:
        import psutil
        result['ram_gb'] = round(psutil.virtual_memory().total / 1024**3, 1)
        result['disk_free_gb'] = round(psutil.disk_usage(str(Path.home())).free / 1024**3, 1)
    except (ImportError, OSError):
        result['metrics'] = 'ölçülemedi'
    return result
